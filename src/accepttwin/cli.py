"""AcceptTwin command-line interface (P032 T012, extended P1-01 FIX-R1).

Thin delegation layer only — this module contains **no** Golden
execution, classification, Oracle, report-generation or HTML-embedding
logic of its own. Every subcommand calls the existing, already
reviewed implementation and reports its verdict:

* ``verify --suite`` -> ``scripts/run_s0.py`` (S0 gate, C01-C24 +
  Oracle parity + stable-bleed reproduction + repeat-100) and/or
  ``scripts/run_all_48.py`` (48-scenario Golden + Oracle parity).
* ``verify --report`` -> ``scripts/embed_report.py``'s report loader
  (independent Schema validation + report-hash recomputation) plus
  the :mod:`accepttwin.privacy` report scan; it verifies a report
  file, it never re-runs an experiment.
* ``run`` -> :mod:`accepttwin.experiment_runner` (frozen four
  experiments, real HTTP), :mod:`accepttwin.classifier`, the
  independent Oracle via ``scripts/s0_harness.py``, and
  :mod:`accepttwin.report_builder` for the formal report.
* ``demo`` -> the same ``run`` pipeline twice on the bundled
  ``contracts/site.json`` template (healthy, then a deliberate
  bleed), with HTML export for both runs.
* ``benchmark`` -> ``scripts/run_all_48.py`` for the 48 per-scenario
  timings, then a fresh 100-run repeat of C01 through
  ``scripts/s0_harness.run_scenario`` (fresh origin/proxy pair and
  fresh OS-assigned ports on every run — a hash that depended on a
  port could not pass), then ``scripts/build_reports_48.py`` (formal
  ``accepttwin.report/v1`` samples, independently Schema-validated)
  and ``scripts/embed_report.py --all-48`` (49 self-contained HTML
  pages), cross-checked with :mod:`accepttwin.privacy`.
* ``report preview`` / ``report export`` -> ``scripts/embed_report.py``
  (privacy preview first, per PROJECT_BOOK §4.2 constraint 7 and
  §17.3; export writes nothing before the preview is printed).
* ``report delete`` / ``contract delete`` / ``clean`` ->
  :mod:`accepttwin.privacy` workspace-bounded deletion (T011 rules:
  explicitly named regular files inside the workspace, never a
  symlink, never a directory, never outside the workspace; one bad
  target blocks the whole batch).

Canonical JSON is never re-implemented here: every hash check goes
through :func:`accepttwin.contract.canonical_json_bytes` (the single
source of truth, ADR-003; :mod:`accepttwin.canonical_json` is its
thin re-export).

Usage (from the repository root, with the frozen ``.venv``)::

    .venv/bin/python -m accepttwin verify --suite all
    .venv/bin/python -m accepttwin verify --suite s0
    .venv/bin/python -m accepttwin verify --report output/runs/demo-healthy/report.json
    .venv/bin/python -m accepttwin run --contract contracts/site.json
    .venv/bin/python -m accepttwin demo
    .venv/bin/python -m accepttwin report preview output/runs/demo-healthy/report.json
    .venv/bin/python -m accepttwin report export output/runs/demo-healthy/report.json
    .venv/bin/python -m accepttwin benchmark --suite all

Exit codes: 0 = the named command succeeded (for ``run``/``demo``
that means the run completed *and* Oracle parity held, so the
report is final — the verdict itself is data and is printed, not
gated: a real REPRESENTATION_BLEED finding still exits 0, because
the tool did its job; for ``verify --report`` it means the report
file is valid, its hash matches, and Oracle parity holds, whatever
its verdict says); 1 = the command ran but its gate failed (Oracle
parity mismatch, invalid report, infrastructure failure); 2 = bad
arguments or bad user input (missing file, invalid contract,
non-loopback URL, refused deletion). No subcommand ever declares
PASS on its own say-so: the exit code follows the underlying
``*_STATUS`` / parity / ``final`` field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
import time
from pathlib import Path

from accepttwin import __version__
from accepttwin.cache_proxy import ControlledCacheProxy
from accepttwin.classifier import classify_run
from accepttwin.contract import ContractError, load_contract, parse_contract
from accepttwin.experiment_runner import ExperimentError, run_experiments
from accepttwin.origin_server import SyntheticOrigin, load_scenario
from accepttwin.privacy import (
    PrivacyError,
    assert_report_clean,
    delete_evidence_files,
    resolve_cleanup_target,
    scan_html_for_remote_resources,
)
from accepttwin.report_builder import build_report, compute_report_hash

# ---------------------------------------------------------------------------
# Locating the already-reviewed script implementations
# ---------------------------------------------------------------------------


def find_repo_root() -> Path:
    """Repository root: the ancestor holding ``scripts/run_all_48.py``.

    Works for the source checkout (``src/accepttwin/cli.py`` -> root
    is two levels up) and for an installed copy run from anywhere
    inside the checkout. Raises a plain error — never a guess — if
    the scripts cannot be found.
    """
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "scripts" / "run_all_48.py").is_file():
            return parent
    cwd = Path.cwd()
    for parent in (cwd, *cwd.parents):
        if (parent / "scripts" / "run_all_48.py").is_file():
            return parent
    raise RuntimeError(
        "cannot locate the AcceptTwin repository root "
        "(no scripts/run_all_48.py found above "
        f"{here} or {cwd}); run from a checkout"
    )


def _load_script_modules(root: Path) -> dict[str, object]:
    """Import the script modules by file path (``scripts/`` is not a
    package). Each module is imported once and reused; nothing in
    them is copied here."""
    import importlib.util

    scripts_dir = root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    if str(root / "src") not in sys.path:
        sys.path.insert(0, str(root / "src"))
    modules: dict[str, object] = {}
    for name in ("run_s0", "run_all_48", "build_reports_48", "embed_report", "s0_harness"):
        spec = importlib.util.spec_from_file_location(name, scripts_dir / f"{name}.py")
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load scripts/{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault(name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


#: Canonical-JSON fields that must never appear (§10.4). Checked as
#: raw byte substrings of the canonical bytes, so a nested or
#: renamed occurrence cannot slip past a key-level scan.
FORBIDDEN_CANONICAL_SUBSTRINGS: tuple[bytes, ...] = (
    b"generated_at",
    b"duration_ms",
    b"process_id",
    b"temporary_path",
    b"ephemeral_port",
    b"timestamp",
    b"uuid",
    b"random",
)

#: The six controlled proxy modes (PROJECT_BOOK §10.3). A ``run``
#: derives its default from the contract's ``cache_behavior.mode``
#: (see below) and the caller may override it explicitly — a
#: fault-injection mode against a healthy contract is exactly how a
#: bleed is demonstrated on purpose.
PROXY_MODES: tuple[str, ...] = (
    "respect_vary",
    "force_uri_only",
    "manual_accept_key",
    "disabled",
    "opaque",
    "ignore_no_store",
)

#: Default proxy mode per contract ``cache_behavior.mode`` (§5.2).
DEFAULT_PROXY_MODE_BY_CONTRACT_MODE: dict[str, str] = {
    "variant_by_accept": "respect_vary",
    "no_store": "disabled",
}

#: Report ``scenario_id`` for a user run (P1-01). The frozen v1
#: report Schema only accepts ``^[CE][0-9]{2}$``, so a user run is
#: filed under the Golden configuration it reproduces — this label
#: records the *configuration*, not Golden membership. The run's
#: real identity is its ``contract_id`` + ``contract_sha256`` +
#: ``run-id``, recorded in ``run-summary.json`` next to the report.
#: Only S0 (C01–C24) configurations are mapped; any other
#: (origin scenario, proxy mode) pair must name its label
#: explicitly with ``--scenario-id``.
SCENARIO_ID_BY_CONFIG: dict[tuple[str, str], str] = {
    ("healthy", "respect_vary"): "C01",
    ("healthy", "disabled"): "C05",
    ("healthy", "force_uri_only"): "C11",
    ("healthy", "ignore_no_store"): "C19",
    ("healthy", "opaque"): "C20",
    ("no_vary", "manual_accept_key"): "C03",
    ("no_vary", "respect_vary"): "C13",
    ("no_vary", "force_uri_only"): "C15",
    ("no_vary", "disabled"): "C17",
    ("html_404", "respect_vary"): "C07",
    ("markdown_404", "respect_vary"): "C08",
    ("html_wrong_content_type", "respect_vary"): "C09",
    ("markdown_sentinel_missing", "respect_vary"): "C10",
}

#: The frozen report-Schema pattern for ``scenario_id`` (§14.3).
SCENARIO_ID_PATTERN = re.compile(r"^[CE][0-9]{2}$")

#: Run ids (``--run-id`` and ``clean --run-id``) are plain directory
#: names under ``output/runs/``: no separators, no leading dot, no
#: ``..`` — a traversal string is refused, never resolved.
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def environment_record() -> dict[str, object]:
    """Real execution environment for the evidence log."""
    import subprocess

    def _node_version() -> str:
        try:
            out = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, timeout=10
            )
            return out.stdout.strip() or "unknown"
        except (OSError, subprocess.SubprocessError):
            return "unknown"

    return {
        "python": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "node": _node_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "accepttwin_version": __version__,
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _validate_run_id(run_id: str) -> str:
    """Return *run_id* or raise ValueError (exit 2) for a traversal."""
    if not RUN_ID_PATTERN.match(run_id) or ".." in run_id:
        raise ValueError(
            f"invalid run-id {run_id!r}: use letters, digits, '.', '-' "
            "or '_' only, starting with a letter or digit (no '/' or '..')"
        )
    return run_id


def _resolve_scenario_id(
    scenario: str, proxy_mode: str, scenario_id: str | None
) -> str:
    """Return the report ``scenario_id`` for a run, or raise
    ValueError (exit 2) when none can be derived.

    An explicit ``--scenario-id`` must match the frozen Schema
    pattern; otherwise the S0 configuration table above supplies
    the label for a known (origin scenario, proxy mode) pair.
    """
    if scenario_id is not None:
        if not SCENARIO_ID_PATTERN.match(scenario_id):
            raise ValueError(
                f"invalid --scenario-id {scenario_id!r}: the frozen v1 "
                "report Schema only accepts C01-C24 / E01-E24"
            )
        return scenario_id
    mapped = SCENARIO_ID_BY_CONFIG.get((scenario, proxy_mode))
    if mapped is None:
        raise ValueError(
            f"no report scenario_id mapped for origin scenario "
            f"{scenario!r} with proxy mode {proxy_mode!r}; pass an "
            "explicit --scenario-id (C01-C24 / E01-E24)"
        )
    return mapped


# ---------------------------------------------------------------------------
# Shared single-contract execution (``run`` and ``demo``)
# ---------------------------------------------------------------------------


def _execute_contract_run(
    root: Path,
    modules: dict[str, object],
    contract: object,
    *,
    scenario: str,
    proxy_mode: str,
    scenario_id: str,
    run_id: str,
    out_dir: Path,
    namespace_prefix: str,
    origin: SyntheticOrigin | None = None,
    proxy: ControlledCacheProxy | None = None,
    report_name: str = "report.json",
) -> dict[str, object]:
    """Run one contract end to end and write its evidence.

    The pipeline is exactly the reviewed one, reused rather than
    re-implemented: frozen four experiments
    (:mod:`accepttwin.experiment_runner`), production classification,
    the independent Oracle (``scripts/s0_harness.py``), and the
    formal ``accepttwin.report/v1`` report
    (:mod:`accepttwin.report_builder`). Oracle parity is checked
    twice — once with the harness parity check and once inside the
    report builder — and the two must agree, or the run fails
    closed. Writes the formal report (``report_name``, default
    ``report.json``), ``raw-observations.json``, ``contract.json``,
    ``production.json``, ``oracle-input.json``, ``oracle.json`` and
    ``run-summary.json`` under *out_dir*. Returns the run summary;
    ``ok`` is True only when Oracle parity held and the report is
    final. Raises :class:`ValueError` for bad run inputs and
    :class:`RuntimeError` for infrastructure / parity failures.
    """
    if not SCENARIO_ID_PATTERN.match(scenario_id):
        raise RuntimeError(
            f"internal error: scenario_id {scenario_id!r} does not match "
            "the frozen report Schema pattern"
        )
    harness = modules["s0_harness"]
    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    from accepttwin.contract import canonical_contract_hash  # noqa: E402

    _write_json(out_dir / "contract.json", contract.as_dict())  # type: ignore[attr-defined]
    run = run_experiments(
        contract,  # type: ignore[arg-type]
        origin=origin,
        proxy=proxy,
        scenario=scenario,
        proxy_mode=proxy_mode,
        namespace_prefix=namespace_prefix,
    )
    duration = time.perf_counter() - started
    production = classify_run(
        contract,  # type: ignore[arg-type]
        run.observations,
        run.origin_events,
        run.reset_evidence,
        raw_observations=run.raw_observations,
    )
    run.write_evidence(out_dir / "raw-observations.json")
    _write_json(out_dir / "production.json", production.as_dict())
    oracle_input = harness.oracle_input_dict(  # type: ignore[attr-defined]
        contract, run, run.origin_events, origin_events_available=True
    )
    _write_json(out_dir / "oracle-input.json", oracle_input)
    oracle_result = harness.run_oracle(  # type: ignore[attr-defined]
        out_dir / "oracle-input.json", out_dir / "oracle.json"
    )
    outcome = harness.ScenarioOutcome(  # type: ignore[attr-defined]
        scenario_id=scenario_id,
        fixture={},
        contract=contract,
        run=run,
        duration_seconds=duration,
        production=production,
        adj_origin_events=run.origin_events,
    )
    parity = harness.check_parity(outcome, oracle_result)  # type: ignore[attr-defined]
    report = build_report(
        contract,  # type: ignore[arg-type]
        production,
        oracle_result,
        observations=list(run.observations),
        scenario_id=scenario_id,
    )
    if report["oracle_parity"] != parity["parity"]:
        raise RuntimeError(
            "Oracle parity disagreement between the harness check "
            f"({parity['parity']}) and the report builder "
            f"({report['oracle_parity']}): refusing to finalise the report"
        )
    _write_json(out_dir / report_name, report)
    assert_report_clean(report)
    if compute_report_hash(report) != report["report_hash"]:
        raise RuntimeError(
            f"report_hash recomputation mismatch after writing {report_name}"
        )
    summary: dict[str, object] = {
        "run_id": run_id,
        "contract_id": contract.contract_id,  # type: ignore[attr-defined]
        "contract_sha256": canonical_contract_hash(contract),  # type: ignore[arg-type]
        "scenario": scenario,
        "proxy_mode": proxy_mode,
        "scenario_id": scenario_id,
        "verdict": production.verdict,
        "first_error": production.first_error,
        "first_error_experiment_id": production.first_error_experiment_id,
        "diagnostics": outcome.diagnostics_projection,
        "oracle_verdict": oracle_result["verdict"],
        "oracle_parity": parity["parity"],
        "oracle_mismatches": parity["mismatches"],
        "final": report["final"],
        "report_hash": report["report_hash"],
        "duration_seconds": round(duration, 4),
        "request_count": len(run.observations),
        "out_dir": str(out_dir),
        "report_path": str(out_dir / report_name),
        "ok": bool(parity["parity"] and report["final"]),
    }
    _write_json(out_dir / "run-summary.json", summary)
    return summary


def _print_run_summary(summary: dict[str, object]) -> None:
    print(
        f"RUN {summary['run_id']}: verdict={summary['verdict']} "
        f"first_error={summary['first_error']} "
        f"oracle_parity={summary['oracle_parity']} "
        f"final={summary['final']} "
        f"report_hash={str(summary['report_hash'])[:12]} "
        f"({summary['duration_seconds']}s)"
    )
    print(f"  report: {summary['report_path']}")
    if summary["oracle_mismatches"]:
        for mismatch in summary["oracle_mismatches"]:  # type: ignore[union-attr]
            print(f"  oracle mismatch: {mismatch}")


# ---------------------------------------------------------------------------
# run --contract
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    """``run --contract <path>`` — run one user contract, for real."""
    root = find_repo_root()
    contract_path = Path(args.contract)
    if not contract_path.exists():
        print(f"accepttwin: contract file not found: {contract_path}", file=sys.stderr)
        return 2
    try:
        contract = load_contract(contract_path)
    except ContractError as exc:
        print(f"accepttwin: invalid contract: {exc}", file=sys.stderr)
        return 2
    try:
        load_scenario(args.scenario)
    except (ValueError, OSError) as exc:
        print(f"accepttwin: unknown origin scenario {args.scenario!r}: {exc}", file=sys.stderr)
        return 2
    proxy_mode = args.proxy_mode or DEFAULT_PROXY_MODE_BY_CONTRACT_MODE.get(
        contract.cache_behavior.get("mode"), "respect_vary"
    )
    try:
        scenario_id = _resolve_scenario_id(args.scenario, proxy_mode, args.scenario_id)
        run_id = _validate_run_id(args.run_id or contract.contract_id)
    except ValueError as exc:
        print(f"accepttwin: {exc}", file=sys.stderr)
        return 2
    modules = _load_script_modules(root)
    if args.output is not None:
        report_path = Path(args.output)
        out_dir = report_path.parent
        report_name = report_path.name
        if not report_name.endswith(".json"):
            print("accepttwin: --output must name a .json report file", file=sys.stderr)
            return 2
    else:
        out_dir = root / "output" / "runs" / run_id
        report_path = out_dir / "report.json"
        report_name = "report.json"
    try:
        summary = _execute_contract_run(
            root,
            modules,
            contract,
            scenario=args.scenario,
            proxy_mode=proxy_mode,
            scenario_id=scenario_id,
            run_id=run_id,
            out_dir=out_dir,
            namespace_prefix=f"run-{run_id}",
            report_name=report_name,
        )
    except (ExperimentError, RuntimeError, ValueError, OSError) as exc:
        # ValueError covers OriginServerError (bind failure, e.g. the
        # contract's ports are already in use) and ReportError; all
        # are run failures (exit 1), never a traceback to the user.
        print(f"accepttwin: run failed: {exc}", file=sys.stderr)
        return 1
    _print_run_summary(summary)
    print(
        f"RUN_STATUS: {'COMPLETE' if summary['ok'] else 'FAIL'} "
        f"(verdict={summary['verdict']}, oracle_parity={summary['oracle_parity']}, "
        f"final={summary['final']})"
    )
    return 0 if summary["ok"] else 1


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------


def _demo_contract(
    template: dict, proxy_url: str, origin_url: str, contract_id: str, name: str
) -> object:
    """A demo contract: the bundled template with live ephemeral URLs."""
    data = json.loads(json.dumps(template))
    data["contract_id"] = contract_id
    data["name"] = name
    data["url"] = proxy_url
    data["origin_url"] = origin_url
    return parse_contract(data)


def cmd_demo(args: argparse.Namespace) -> int:
    """``demo`` — healthy run, then a deliberate bleed, both real.

    Both cases use the bundled ``contracts/site.json`` template with
    fresh OS-assigned loopback ports (no fixed-port clashes): the
    healthy case runs the ``respect_vary`` proxy (the C01
    configuration, expected PASS_OBSERVED); the bleed case runs the
    same contract against a ``force_uri_only`` proxy (the C11
    configuration, expected REPRESENTATION_BLEED with first_error
    6). Each case also exports its HTML page, so the demo ends with
    two complete report + HTML pairs under ``output/runs/``.
    """
    root = find_repo_root()
    template_path = root / "contracts" / "site.json"
    if not template_path.exists():
        print(f"accepttwin: demo template not found: {template_path}", file=sys.stderr)
        return 2
    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"accepttwin: demo template is not valid JSON: {exc}", file=sys.stderr)
        return 2
    modules = _load_script_modules(root)
    cases = (
        ("demo-healthy", "respect_vary", "C01", "PASS_OBSERVED"),
        ("demo-bleed", "force_uri_only", "C11", "REPRESENTATION_BLEED"),
    )
    all_ok = True
    for run_id, proxy_mode, scenario_id, expected_verdict in cases:
        out_dir = root / "output" / "runs" / run_id
        origin: SyntheticOrigin | None = None
        proxy: ControlledCacheProxy | None = None
        try:
            origin = SyntheticOrigin(port=0, scenario="healthy")
            origin.start()
            proxy = ControlledCacheProxy(
                port=0, mode=proxy_mode, origin_url=origin.url
            )
            proxy.start()
            contract = _demo_contract(
                template,
                proxy.url,
                origin.url,
                f"{run_id}-001",
                f"Demo {run_id} (synthetic origin + controlled proxy)",
            )
            summary = _execute_contract_run(
                root,
                modules,
                contract,
                scenario="healthy",
                proxy_mode=proxy_mode,
                scenario_id=scenario_id,
                run_id=run_id,
                out_dir=out_dir,
                namespace_prefix=f"demo-{run_id}",
                origin=origin,
                proxy=proxy,
            )
        except (ExperimentError, RuntimeError, ContractError, ValueError) as exc:
            print(f"accepttwin: demo case {run_id} failed: {exc}", file=sys.stderr)
            all_ok = False
            continue
        finally:
            if proxy is not None:
                proxy.stop()
            if origin is not None:
                origin.stop()
        _print_run_summary(summary)
        if summary["verdict"] != expected_verdict:
            print(
                f"demo case {run_id}: expected verdict {expected_verdict}, "
                f"got {summary['verdict']}",
                file=sys.stderr,
            )
            all_ok = False
        if not summary["ok"]:
            all_ok = False
            continue
        try:
            html_path = _export_report_html(
                modules,
                out_dir / "report.json",
                out_dir / "contract.json",
                out_dir / "report.html",
                check_only=False,
            )
            print(f"  html: {html_path}")
        except (RuntimeError, ValueError) as exc:
            print(f"accepttwin: demo HTML export failed for {run_id}: {exc}", file=sys.stderr)
            all_ok = False
    print(
        f"DEMO_STATUS: {'PASS' if all_ok else 'FAIL'} "
        "(healthy PASS_OBSERVED + bleed REPRESENTATION_BLEED, "
        "both Oracle parity, both HTML exported)"
    )
    return 0 if all_ok else 1


# ---------------------------------------------------------------------------
# report export (shared by ``demo`` and ``report export``)
# ---------------------------------------------------------------------------


def _export_report_html(
    modules: dict[str, object],
    report_path: Path,
    contract_path: Path | None,
    out_path: Path,
    *,
    check_only: bool,
) -> str:
    """Export one formal report to a self-contained HTML page.

    Privacy preview first (printed before anything is written, per
    §4.2 constraint 7); the finished page is scanned for remote
    references and Sentinel literals. Returns the output path as a
    string. Raises RuntimeError/ValueError on any failure.
    """
    embed = modules["embed_report"]
    template, styles, script = embed._load_template_assets()  # type: ignore[attr-defined]
    html, report, baseline_source = embed.build_single(  # type: ignore[attr-defined]
        report_path, contract_path, template, styles, script
    )
    out_name = str(out_path)
    embed.print_privacy_preview(report, out_name, baseline_source)  # type: ignore[attr-defined]
    if check_only:
        print(f"CHECK ONLY: {report['scenario_id']} OK (nothing written)")
        return out_name
    remote = scan_html_for_remote_resources(html)
    if remote:
        raise RuntimeError(
            f"generated HTML contains remote references: {remote}"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"WROTE {out_path} ({len(html.encode('utf-8'))} bytes)")
    return out_name

# ---------------------------------------------------------------------------
# Shared report-file loading (verify --report / report preview/export)
# ---------------------------------------------------------------------------


def _load_report_file(root: Path, modules: dict[str, object], path: Path) -> tuple[dict, int] | tuple[None, int]:
    """Load and fully validate a report file, or return (None, rc).

    Missing file -> rc 2 (bad input); unreadable / invalid /
    privacy-dirty report -> rc 1 (verification failure). The loader
    is the reviewed ``embed_report`` one: independent Schema check,
    report-hash recomputation, Sentinel scan, forbidden-key scan.
    """
    if not path.exists():
        print(f"accepttwin: report file not found: {path}", file=sys.stderr)
        return None, 2
    embed = modules["embed_report"]
    try:
        report = embed.load_report(path)  # type: ignore[attr-defined]
        assert_report_clean(report)
    except (ValueError, PrivacyError) as exc:
        print(f"accepttwin: invalid report {path}: {exc}", file=sys.stderr)
        return None, 1
    return report, 0


def _json_schema_field(path: Path) -> str | None:
    """Return the ``schema`` field of a JSON file, or None when the
    file is missing, unreadable, not JSON, or not an object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    schema = data.get("schema")
    return schema if isinstance(schema, str) else None


# ---------------------------------------------------------------------------
# verify (extended with --report)
# ---------------------------------------------------------------------------


def cmd_verify(args: argparse.Namespace) -> int:
    """``verify --suite s0|all`` — re-run the Golden gate(s) live.

    ``verify --report <path>`` instead verifies one formal report
    file: Schema + hash + privacy + Oracle parity/final. It never
    re-runs an experiment. Exit 0 means the report is verified as
    authentic and consistent — the verdict itself is reported, not
    gated: a valid REPRESENTATION_BLEED report still exits 0.
    """
    root = find_repo_root()
    modules = _load_script_modules(root)
    if getattr(args, "report", None) is not None:
        report_path = Path(args.report)
        report, rc = _load_report_file(root, modules, report_path)
        if report is None:
            return rc
        contract_ok: bool | None = None
        if getattr(args, "contract", None) is not None:
            from accepttwin.contract import canonical_contract_hash  # noqa: E402

            try:
                contract = load_contract(args.contract)
            except ContractError as exc:
                print(f"accepttwin: invalid contract: {exc}", file=sys.stderr)
                return 2
            contract_ok = (
                canonical_contract_hash(contract)
                == report["input"]["contract_sha256"]
            )
            if not contract_ok:
                print(
                    "accepttwin: report contract_sha256 does not match "
                    f"--contract {args.contract}",
                    file=sys.stderr,
                )
        ok = (
            report["oracle_parity"] is True
            and report["final"] is True
            and contract_ok is not False
        )
        print(
            f"VERIFY_REPORT: {report['scenario_id']} "
            f"verdict={report['verdict']} "
            f"first_error={report['first_error']} "
            f"oracle_parity={report['oracle_parity']} "
            f"final={report['final']} schema=OK hash=OK"
            + (
                f" contract_sha256={'OK' if contract_ok else 'MISMATCH'}"
                if contract_ok is not None
                else ""
            )
        )
        return 0 if ok else 1
    suite = getattr(args, "suite", None) or "all"
    if suite == "s0":
        summary = modules["run_s0"].run_all()  # type: ignore[attr-defined]
        ok = summary["S0_STATUS"] == "PASS"
        print(
            f"VERIFY_STATUS: {summary['S0_STATUS']} "
            f"(S0 {summary['S0_CORE_GOLDEN']} golden, "
            f"parity {summary['S0_ORACLE_PARITY']})"
        )
        return 0 if ok else 1
    # --suite all: the 48-scenario suite first, then the S0 gate
    # re-run (24/24 + repeat-100 + bleed reproduction). run_all_48
    # already contains the S0 scenarios as a subset; the separate
    # S0 run is the required re-run, not a second implementation.
    summary48 = modules["run_all_48"].run_all()  # type: ignore[attr-defined]
    summary_s0 = modules["run_s0"].run_all()  # type: ignore[attr-defined]
    ok = (
        summary48["ALL48_STATUS"] == "PASS"
        and summary_s0["S0_STATUS"] == "PASS"
    )
    print(
        f"VERIFY_STATUS: {'PASS' if ok else 'FAIL'} "
        f"(ALL48 {summary48['ALL48_GOLDEN']} golden, "
        f"parity {summary48['ALL48_ORACLE_PARITY']}; "
        f"S0 {summary_s0['S0_CORE_GOLDEN']} golden, "
        f"parity {summary_s0['S0_ORACLE_PARITY']}, "
        f"repeat-100 distinct_hashes="
        f"{summary_s0['repeat_100']['distinct_hashes']})"
    )
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# report preview / export / delete
# ---------------------------------------------------------------------------


def cmd_report_preview(args: argparse.Namespace) -> int:
    """``report preview <path>`` — human-readable report, no files
    written (§4.2 constraint 7: preview before export)."""
    root = find_repo_root()
    modules = _load_script_modules(root)
    report_path = Path(args.report)
    report, rc = _load_report_file(root, modules, report_path)
    if report is None:
        return rc
    embed = modules["embed_report"]
    baseline_source = (
        f"contract {args.contract}"
        if getattr(args, "contract", None) is not None
        else "frozen §5.1.2 constants"
    )
    embed.print_privacy_preview(report, str(report_path), baseline_source)  # type: ignore[attr-defined]
    print()
    print(f"scenario:      {report['scenario_id']}")
    print(f"verdict:       {report['verdict']}")
    print(
        f"first error:   request {report['first_error']} "
        f"({report['first_error_experiment_id']})"
    )
    print(
        f"diagnostics:   {report['critical_count']} CRITICAL, "
        f"{report['warning_count']} WARNING"
    )
    for diag in report["diagnostics"]:
        print(
            f"  [{diag['severity']}] {diag['code']} "
            f"(request {diag['request_index']}, {diag['experiment_id']}): "
            f"{diag['message']}"
        )
    print("requests (001-008, execution order):")
    for obs in report["observations"]:
        print(
            f"  {obs['request_index']:03d} {obs['experiment_id']:<18} "
            f"{obs['requested_representation']:<8} "
            f"status={obs['response_status']} "
            f"content-type={obs['response_content_type']} "
            f"cache={obs['cache_status']} "
            f"sentinel_match={obs['sentinel_match']} "
            f"origin_delta={obs['origin_counter_delta']}"
        )
    print(f"oracle parity: {report['oracle_parity']} (final={report['final']})")
    print(f"report hash:   {report['report_hash']}")
    print(f"contract:      {report['input']['contract_id']} "
          f"({report['input']['contract_sha256'][:12]}…)")
    return 0


def cmd_report_export(args: argparse.Namespace) -> int:
    """``report export <path>`` — self-contained HTML (§14.4).

    The privacy preview is printed before anything is written;
    ``--check-only`` validates and previews without writing.
    """
    root = find_repo_root()
    modules = _load_script_modules(root)
    report_path = Path(args.report)
    report, rc = _load_report_file(root, modules, report_path)
    if report is None:
        return rc
    if getattr(args, "out", None) is not None:
        out_path = Path(args.out)
    else:
        out_path = report_path.parent / f"{report_path.stem}.html"
    contract_path = (
        Path(args.contract)
        if getattr(args, "contract", None) is not None
        else None
    )
    try:
        _export_report_html(
            modules,
            report_path,
            contract_path,
            out_path,
            check_only=bool(getattr(args, "check_only", False)),
        )
    except (RuntimeError, ValueError) as exc:
        print(f"accepttwin: report export failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _delete_named_file(
    root: Path,
    target: str | Path,
    *,
    allowed_subtrees: tuple[str, ...],
    expected_schema: str,
    kind: str,
) -> int:
    """Delete one explicitly named file under the safety rules.

    The target must be an existing regular file inside the
    workspace (T011 rules via :func:`resolve_cleanup_target`),
    under one of *allowed_subtrees*, and its JSON ``schema`` field
    must be *expected_schema* — a report delete refuses a
    non-report file and a contract delete refuses a non-contract
    file, even inside an allowed subtree. One refusal blocks the
    deletion; nothing is deleted on any refusal.
    """
    if not Path(target).exists():
        print(f"accepttwin: file not found: {target}", file=sys.stderr)
        return 2
    schema = _json_schema_field(Path(target))
    if schema != expected_schema:
        print(
            f"accepttwin: refusing to delete {target}: not a {kind} "
            f"file (schema {schema!r} != {expected_schema!r})",
            file=sys.stderr,
        )
        return 2
    try:
        deleted = delete_evidence_files(
            root, [target], allowed_subtrees=allowed_subtrees
        )
    except PrivacyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    for path in deleted:
        print(f"deleted: {path}")
    return 0


def cmd_report_delete(args: argparse.Namespace) -> int:
    """``report delete <path>`` — delete one formal report file.

    Only files under ``output/`` or ``evidence/Reports/`` whose
    JSON ``schema`` is ``accepttwin.report/v1`` are deletable.
    """
    root = find_repo_root()
    return _delete_named_file(
        root,
        args.report,
        allowed_subtrees=("output", "evidence"),
        expected_schema="accepttwin.report/v1",
        kind="accepttwin.report/v1",
    )


def cmd_contract_delete(args: argparse.Namespace) -> int:
    """``contract delete <path>`` — delete one contract file.

    Only files under ``contracts/`` or ``output/`` whose JSON
    ``schema`` is ``accepttwin.contract/v1`` are deletable.
    """
    root = find_repo_root()
    return _delete_named_file(
        root,
        args.contract,
        allowed_subtrees=("contracts", "output"),
        expected_schema="accepttwin.contract/v1",
        kind="accepttwin.contract/v1",
    )


# ---------------------------------------------------------------------------
# clean --run-id
# ---------------------------------------------------------------------------


def cmd_clean(args: argparse.Namespace) -> int:
    """``clean --run-id <RUN_ID>`` — delete one run's output files.

    Only the flat files directly inside
    ``output/runs/<RUN_ID>/`` are deleted: the run directory must
    exist, must not be a symlink, and must contain regular files
    only (a symlink or a subdirectory inside it refuses the whole
    batch — fail-closed, no partial deletion). The directory itself
    is removed once empty. ``--dry-run`` lists and deletes nothing.
    """
    root = find_repo_root()
    try:
        run_id = _validate_run_id(args.run_id)
    except ValueError as exc:
        print(f"accepttwin: {exc}", file=sys.stderr)
        return 2
    run_dir = root / "output" / "runs" / run_id
    if run_dir.is_symlink():
        print(f"REFUSED: refusing to clean symlink: {run_dir}", file=sys.stderr)
        return 2
    if not run_dir.is_dir():
        print(f"accepttwin: no such run: {run_id} ({run_dir})", file=sys.stderr)
        return 2
    entries = sorted(run_dir.iterdir())
    try:
        resolved = [resolve_cleanup_target(root, entry) for entry in entries]
    except PrivacyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    for entry in entries:
        if entry.is_symlink() or not entry.is_file():
            print(
                f"REFUSED: run directory {run_id} contains a non-regular "
                f"file: {entry.name} (nothing deleted)",
                file=sys.stderr,
            )
            return 2
    verb = "would delete" if args.dry_run else "deleted"
    for path in resolved:
        print(f"{verb}: {path}")
    if args.dry_run:
        print(f"CLEAN_STATUS: DRY-RUN ({len(resolved)} files, nothing deleted)")
        return 0
    for path in resolved:
        path.unlink()
    run_dir.rmdir()
    print(f"CLEAN_STATUS: OK (run {run_id}: {len(resolved)} files deleted)")
    return 0


# ---------------------------------------------------------------------------
# benchmark
# ---------------------------------------------------------------------------


def cmd_benchmark(args: argparse.Namespace) -> int:
    """``benchmark --suite all`` — timings, repeat-100, reports, HTML.

    Every number below comes from a real run made in this invocation:
    the 48 per-scenario durations are the live experiment durations
    recorded by ``run_all_48`` (8 real HTTP requests per scenario,
    no cached report is ever read for a timing), and the repeat-100
    re-executes C01 100 times on fresh pairs. Nothing is timed from
    a stored file.
    """
    if args.suite != "all":
        print("benchmark currently supports only --suite all", file=sys.stderr)
        return 2
    root = find_repo_root()
    modules = _load_script_modules(root)
    started = time.perf_counter()
    env = environment_record()

    # 1. The 48 live scenarios: verdicts, Oracle parity, durations.
    summary48 = modules["run_all_48"].run_all()  # type: ignore[attr-defined]
    scenarios = summary48["scenarios"]
    max_duration = max(s["duration_seconds"] for s in scenarios.values())
    per_scenario = {
        sid: {
            "duration_seconds": s["duration_seconds"],
            "verdict": s["verdict"],
            "oracle_parity": s["oracle_parity"],
            "request_count": s["request_count"],
        }
        for sid, s in sorted(scenarios.items())
    }
    timings_ok = (
        summary48["ALL48_STATUS"] == "PASS" and max_duration < 1.0
    )
    print(
        f"benchmark timings: max single-scenario "
        f"{max_duration:.3f}s (limit 1.000s), "
        f"total {summary48['total_seconds']:.2f}s"
    )

    # 2. Repeat-100 determinism (§10.4, §18 AC10): C01, fresh pair
    # per run, real experiments every time. The canonical report of
    # the first run is also scanned for non-deterministic fields.
    from accepttwin.contract import canonical_json_bytes  # noqa: E402

    harness = modules["s0_harness"]
    repeat_hashes: list[str] = []
    repeat_durations: list[float] = []
    canonical_clean = True
    canonical_recompute_ok = True
    for i in range(100):
        outcome = harness.run_scenario(  # type: ignore[attr-defined]
            "C01", namespace_prefix=f"bench-C01-repeat-{i + 1}"
        )
        repeat_hashes.append(outcome.report_hash)
        repeat_durations.append(outcome.duration_seconds)
        if outcome.production.verdict != "PASS_OBSERVED":
            print(f"C01 repeat {i + 1}: unexpected verdict {outcome.production.verdict}")
            canonical_clean = False
        if i == 0:
            raw = canonical_json_bytes(outcome.report)
            for needle in FORBIDDEN_CANONICAL_SUBSTRINGS:
                if needle in raw:
                    print(f"canonical JSON contains forbidden field {needle!r}")
                    canonical_clean = False
            recomputed = hashlib.sha256(raw).hexdigest()
            if recomputed != outcome.report_hash:
                print(
                    "canonical hash recompute mismatch: "
                    f"{recomputed} != {outcome.report_hash}"
                )
                canonical_recompute_ok = False
    repeat_ok = (
        len(set(repeat_hashes)) == 1
        and canonical_clean
        and canonical_recompute_ok
    )
    print(
        f"benchmark repeat-100 C01: distinct_hashes={len(set(repeat_hashes))} "
        f"all_equal={repeat_ok} max_duration={max(repeat_durations):.3f}s "
        f"hash={repeat_hashes[0] if repeat_hashes else None}"
    )

    # 3. Formal reports (T009 reuse): rebuild from the fresh Golden
    # evidence and validate each sample with the independent Schema
    # validator. 4. HTML export (T010 reuse): 49 self-contained
    # pages, then the T011 privacy scanner over the whole directory.
    reports = modules["build_reports_48"].build_all()  # type: ignore[attr-defined]
    reports_ok = reports["REPORTS_STATUS"] == "PASS"
    embed_rc = modules["embed_report"].main(["--all-48"])  # type: ignore[attr-defined]
    html_ok = embed_rc == 0
    from accepttwin.privacy import assert_html_directory_clean, assert_report_clean  # noqa: E402

    reports_dir = root / "evidence" / "Reports"
    html_dir = reports_dir / "html"
    html_scan: dict[str, object] = {}
    try:
        assert_html_directory_clean(html_dir)
        html_pages = sorted(p.name for p in html_dir.glob("*.html"))
        html_scan = {"pages": len(html_pages), "violations": 0, "clean": True}
    except Exception as exc:  # privacy.PrivacyError or OSError
        html_scan = {"pages": 0, "violations": 1, "clean": False, "error": str(exc)}
        html_ok = False
    reports_clean = True
    for sid in sorted(scenarios):
        try:
            report = json.loads((reports_dir / f"{sid}.json").read_text(encoding="utf-8"))
            assert_report_clean(report)
            # HTML/JSON consistency (§14.4): the page for this
            # scenario must carry the same verdict, first error and
            # report hash as the formal JSON report.
            page = (html_dir / f"{sid}.html").read_text(encoding="utf-8")
            # The page embeds the report JSON verbatim (json.dumps,
            # sort_keys, indent=2), so the exact field spellings
            # below must appear.
            if report["report_hash"] not in page:
                print(f"{sid}: HTML page does not carry report_hash")
                reports_clean = False
            if f'"verdict": "{report["verdict"]}"' not in page:
                print(f"{sid}: HTML page does not carry verdict {report['verdict']}")
                reports_clean = False
            if f'"first_error": {json.dumps(report["first_error"])}' not in page:
                print(f"{sid}: HTML page does not carry first_error {report['first_error']}")
                reports_clean = False
        except Exception as exc:
            print(f"{sid}: report/HTML cross-check failed: {exc}")
            reports_clean = False
    print(
        f"benchmark reports: schema {reports['SCHEMA_VALID']}, "
        f"verdict {reports['VERDICT_MATCHES_RECORD']}, "
        f"parity {reports['ORACLE_PARITY']}; "
        f"HTML pages clean: {html_scan}"
    )

    total_seconds = time.perf_counter() - started
    passed = timings_ok and repeat_ok and reports_ok and html_ok and reports_clean
    summary = {
        "gate": "BENCHMARK",
        "spec": "PROJECT_BOOK.md §18 AC10/AC11, §10.4, §10.5, §14",
        "BENCHMARK_STATUS": "PASS" if passed else "FAIL",
        "ALL48_GOLDEN": summary48["ALL48_GOLDEN"],
        "ALL48_ORACLE_PARITY": summary48["ALL48_ORACLE_PARITY"],
        "max_scenario_duration_seconds": max_duration,
        "per_scenario_duration_limit_seconds": 1.0,
        "per_scenario": per_scenario,
        "repeat_100": {
            "scenario": "C01",
            "runs": 100,
            "distinct_hashes": len(set(repeat_hashes)),
            "hash": repeat_hashes[0] if repeat_hashes else None,
            "all_equal": repeat_ok,
            "max_duration_seconds": round(max(repeat_durations), 4),
            "fresh_pair_per_run": True,
            "canonical_json_free_of_nondeterministic_fields": canonical_clean,
            "canonical_hash_recompute_matches": canonical_recompute_ok,
        },
        "reports": {
            "REPORTS_STATUS": reports["REPORTS_STATUS"],
            "SCHEMA_VALID": reports["SCHEMA_VALID"],
            "VERDICT_MATCHES_RECORD": reports["VERDICT_MATCHES_RECORD"],
            "ORACLE_PARITY": reports["ORACLE_PARITY"],
            "privacy_clean": reports_clean,
        },
        "html": html_scan,
        "environment": env,
        "total_seconds": round(total_seconds, 2),
    }
    out_dir = root / "evidence" / "Performance"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "BENCHMARK_SUMMARY.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"BENCHMARK_STATUS: {summary['BENCHMARK_STATUS']} "
        f"(max single-scenario {max_duration:.3f}s, "
        f"repeat-100 distinct={len(set(repeat_hashes))}, "
        f"reports {reports['REPORTS_STATUS']}, html_clean={html_scan.get('clean')})"
    )
    return 0 if passed else 1


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="accepttwin",
        description=(
            "AcceptTwin (P032): same URL, two representations — "
            "verify delivery is never mixed up. "
            "Local-only, offline, no real users."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"accepttwin {__version__}",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    p_run = sub.add_parser(
        "run",
        help="run one user contract end to end (real experiments + Oracle parity + formal report)",
    )
    p_run.add_argument(
        "--contract",
        required=True,
        help="contract JSON file (accepttwin.contract/v1, loopback URLs only)",
    )
    p_run.add_argument(
        "--scenario",
        default="healthy",
        help="synthetic origin scenario: a name under fixtures/origin/ "
        "or a path to a scenario JSON file (default: healthy)",
    )
    p_run.add_argument(
        "--proxy-mode",
        choices=PROXY_MODES,
        default=None,
        help="controlled proxy mode (§10.3); default follows the "
        "contract: variant_by_accept -> respect_vary, "
        "no_store -> disabled",
    )
    p_run.add_argument(
        "--scenario-id",
        default=None,
        help="report scenario_id label (C01-C24 / E01-E24); default "
        "follows the S0 configuration table for a known "
        "(origin scenario, proxy mode) pair",
    )
    p_run.add_argument(
        "--run-id",
        default=None,
        help="run id (output directory under output/runs/; "
        "default: the contract_id)",
    )
    p_run.add_argument(
        "--output",
        default=None,
        help="report JSON path (default: output/runs/<run-id>/report.json; "
        "sibling evidence files land next to it)",
    )
    p_run.set_defaults(func=cmd_run)
    p_demo = sub.add_parser(
        "demo",
        help="run the bundled example contract twice: healthy (PASS) then a deliberate bleed (REPRESENTATION_BLEED), with HTML export",
    )
    p_demo.set_defaults(func=cmd_demo)
    p_verify = sub.add_parser(
        "verify",
        help="re-run the Golden gate live (48 scenarios + Oracle parity; --suite all also re-runs S0 24/24), or verify one formal report file (--report)",
    )
    p_verify.add_argument(
        "--suite",
        choices=("s0", "all"),
        default=None,
        help="suite to verify: s0 (C01-C24 + repeat-100) or all (48 "
        "scenarios + S0 re-run) (default: all)",
    )
    p_verify.add_argument(
        "--report",
        default=None,
        help="verify one formal report JSON file instead of re-running "
        "a suite (Schema + hash + privacy + Oracle parity/final)",
    )
    p_verify.add_argument(
        "--contract",
        default=None,
        help="with --report: also check the report's contract_sha256 "
        "against this contract file",
    )
    p_verify.set_defaults(func=cmd_verify)
    p_report = sub.add_parser(
        "report",
        help="preview, export or delete a formal report JSON file",
    )
    rep_sub = p_report.add_subparsers(dest="report_command", metavar="REPORT_COMMAND")
    p_preview = rep_sub.add_parser(
        "preview",
        help="print the privacy preview + a human-readable summary of a report (writes nothing)",
    )
    p_preview.add_argument("report", help="formal report JSON file")
    p_preview.add_argument(
        "--contract",
        default=None,
        help="contract file for the baseline column (default: frozen §5.1.2 constants)",
    )
    p_preview.set_defaults(func=cmd_report_preview)
    p_export = rep_sub.add_parser(
        "export",
        help="export a report to a self-contained offline HTML page (privacy preview first)",
    )
    p_export.add_argument("report", help="formal report JSON file")
    p_export.add_argument(
        "--contract",
        default=None,
        help="contract file for the baseline column (default: frozen §5.1.2 constants)",
    )
    p_export.add_argument(
        "--out",
        default=None,
        help="output HTML path (default: <report-stem>.html next to the report)",
    )
    p_export.add_argument(
        "--check-only",
        action="store_true",
        help="validate + print the privacy preview, write nothing",
    )
    p_export.set_defaults(func=cmd_report_export)
    p_rdel = rep_sub.add_parser(
        "delete",
        help="delete one formal report JSON file (workspace-bounded, report files only)",
    )
    p_rdel.add_argument("report", help="formal report JSON file to delete")
    p_rdel.set_defaults(func=cmd_report_delete)
    p_clean = sub.add_parser(
        "clean",
        help="delete one run's output files under output/runs/<RUN_ID>",
    )
    p_clean.add_argument(
        "--run-id",
        required=True,
        help="run id whose output/runs/<RUN_ID>/ directory is deleted",
    )
    p_clean.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be deleted and delete nothing",
    )
    p_clean.set_defaults(func=cmd_clean)
    p_contract = sub.add_parser(
        "contract",
        help="manage stored contracts",
    )
    con_sub = p_contract.add_subparsers(dest="contract_command", metavar="CONTRACT_COMMAND")
    p_cdel = con_sub.add_parser(
        "delete",
        help="delete one contract JSON file (workspace-bounded, contract files only)",
    )
    p_cdel.add_argument("contract", help="contract JSON file to delete")
    p_cdel.set_defaults(func=cmd_contract_delete)
    p_bench = sub.add_parser(
        "benchmark",
        help="measure per-scenario time (<1s), repeat-100 determinism, and re-validate reports + self-contained HTML",
    )
    p_bench.add_argument(
        "--suite",
        choices=("all",),
        default="all",
        help="suite to benchmark (default: all)",
    )
    p_bench.set_defaults(func=cmd_benchmark)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    if getattr(args, "command", None) == "verify" and getattr(
        args, "report", None
    ) is not None and getattr(args, "suite", None) is not None:
        parser.error("--suite and --report are mutually exclusive")
    try:
        return int(args.func(args))
    except RuntimeError as exc:
        print(f"accepttwin: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
