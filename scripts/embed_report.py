"""Embed an ``accepttwin.report/v1`` JSON report into a single
self-contained HTML page (P032 T010).

Reads one formal report (``evidence/Reports/<sid>.json``, built by
T009), validates it fail-closed, prints a privacy preview, and
writes one HTML file that opens fully offline: the stylesheet
(``report-ui/styles.css``) and the compiled UI bundle
(``report-ui/report-ui.js``, built from ``report-ui/src/*.ts``)
are inlined, the report JSON is embedded as a
``<script type="application/json">`` payload, and the page
contains no remote reference of any kind (no CDN, no webfont, no
image, no iframe, no external link).

Privacy (PROJECT_BOOK §7.12 I-12, §17.2, §4.2 constraint 7):

* the report itself never carries raw body text or a sensitive
  request header (T009 enforces this at build time); this script
  re-scans for forbidden keys (case-insensitive) and for the
  Sentinel literals before writing anything;
* the privacy preview is printed to stdout *before* any file is
  written, and the generated page repeats the same checklist as
  its §4.3 area F (item 10 of the T010 interface);
* the finished HTML is scanned again (Sentinel literals, remote
  references) — a single hit fails the run with exit code 1 and
  writes nothing.

Determinism: the embedded payload is ``json.dumps(sort_keys=True,
indent=2)`` of the report as loaded; the template, CSS and JS
bundle are fixed inputs, so re-running the script on the same
report produces byte-identical HTML. No timestamp, duration or
random value is ever added.

Hash check: the stored ``report_hash`` is recomputed with
:func:`accepttwin.report_builder.compute_report_hash` (the single
canonical implementation — this script never re-implements
canonical JSON) and must match, otherwise the run fails.

Baseline expectations (§4.3 area B): the "expected" column comes
from the run's contract (``--contract`` — only the three safe
fields per representation are copied: ``accept``,
``expected_status``, ``expected_content_type``; Sentinel values
are never copied) or, when no contract is given, from the frozen
§5.1.2 constants (identical across all 48 contracts, verified in
T010). The baseline block is embedded as a second, separate JSON
payload — the report JSON itself is never modified.

Usage (run from the repository root)::

    .venv/bin/python scripts/embed_report.py evidence/Reports/C11.json \\
        --contract evidence/Golden/C11/contract.json -o evidence/Reports/html/C11.html
    .venv/bin/python scripts/embed_report.py --all-48
    .venv/bin/python scripts/embed_report.py evidence/Reports/C11.json --check-only

``--all-48`` builds all 48 single-report pages plus
``index.html`` (the 48-scenario summary) from the existing report
samples — it never re-runs an experiment (live re-runs belong to
T012). The summary is derived from the 48 report JSONs and
cross-checked field by field against
``evidence/Reports/REPORTS_SUMMARY.json``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests" / "unit"))

from accepttwin.contract import parse_contract  # noqa: E402
from accepttwin.report_builder import compute_report_hash  # noqa: E402
from accepttwin.url_guard import URLGuardError, validate_loopback_url  # noqa: E402
from independent_schema_validator import validate as validate_schema  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORT_UI_DIR = ROOT / "report-ui"
REPORTS_DIR = ROOT / "evidence" / "Reports"
GOLDEN_DIR = ROOT / "evidence" / "Golden"

SCENARIO_IDS: tuple[str, ...] = tuple(
    [f"C{i:02d}" for i in range(1, 25)] + [f"E{i:02d}" for i in range(1, 25)]
)

VERDICTS: tuple[str, ...] = (
    "PASS_OBSERVED",
    "ORIGIN_NEGOTIATION_ERROR",
    "REPRESENTATION_BLEED",
    "CONTRACT_MISMATCH",
    "INCONCLUSIVE",
)

#: Frozen §5.1.2 baseline expectations (identical in all 48
#: contracts — verified by T010 against evidence/Golden/*/contract.json).
FROZEN_BASELINE: dict[str, dict[str, object]] = {
    "html": {
        "accept": "text/html",
        "expected_status": 200,
        "expected_content_type": "text/html; charset=utf-8",
    },
    "markdown": {
        "accept": "text/markdown",
        "expected_status": 200,
        "expected_content_type": "text/markdown; charset=utf-8",
    },
}

#: Keys that must never appear in a report or in generated HTML,
#: matched case-insensitively (§7.12 I-12, §5.1.3, §17.2).
_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "body",
        "body_text",
        "response_body",
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
    }
)

#: Sentinel literals — must never appear in generated HTML (§5.3).
_SENTINELS: tuple[str, ...] = ("AT_HTML_SENTINEL_001", "AT_MARKDOWN_SENTINEL_001")

def _is_loopback_host(host: str) -> bool:
    host = host.strip("[]").lower()
    if host == "localhost":
        return True
    if host.startswith("127."):
        parts = host.split(".")
        return (
            len(parts) == 4
            and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)
        )
    return host == "::1"


class EmbedError(ValueError):
    """Raised when a report cannot be embedded fail-closed."""


# ---------------------------------------------------------------------------
# Fail-closed input checks
# ---------------------------------------------------------------------------


def _reject_forbidden_keys(value: object, where: str = "report") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise EmbedError(f"forbidden key {key!r} in {where}")
            _reject_forbidden_keys(item, f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_forbidden_keys(item, f"{where}[{index}]")


def _check_no_sentinels(text: str, where: str) -> None:
    for sentinel in _SENTINELS:
        if sentinel in text:
            raise EmbedError(f"Sentinel literal {sentinel} found in {where}")


def _check_report_structure(report: dict) -> None:
    required = (
        "schema",
        "project",
        "scenario_id",
        "input",
        "observations",
        "diagnostics",
        "verdict",
        "first_error",
        "first_error_experiment_id",
        "critical_count",
        "warning_count",
        "reasons",
        "oracle",
        "oracle_parity",
        "final",
        "report_hash",
    )
    missing = [key for key in required if key not in report]
    if missing:
        raise EmbedError(f"report is missing top-level fields: {missing}")
    if report["schema"] != "accepttwin.report/v1":
        raise EmbedError(f"unexpected report schema: {report['schema']!r}")
    if report["verdict"] not in VERDICTS:
        raise EmbedError(f"unknown verdict: {report['verdict']!r}")
    observations = report["observations"]
    if not isinstance(observations, list) or len(observations) != 8:
        raise EmbedError(
            f"exactly 8 observations are required, got {len(observations) if isinstance(observations, list) else type(observations).__name__}"
        )
    indices = sorted(obs["request_index"] for obs in observations)
    if indices != list(range(1, 9)):
        raise EmbedError(f"observations must cover requests 001-008, got {indices}")
    diagnostics = report["diagnostics"]
    critical = sum(1 for d in diagnostics if d["severity"] == "CRITICAL")
    warning = sum(1 for d in diagnostics if d["severity"] == "WARNING")
    if critical != report["critical_count"] or warning != report["warning_count"]:
        raise EmbedError(
            "diagnostic counts disagree with the report: "
            f"critical {critical}!={report['critical_count']} or "
            f"warning {warning}!={report['warning_count']}"
        )
    for key in ("url", "origin_url"):
        url = report["input"][key]
        try:
            validate_loopback_url(url)
        except (URLGuardError, ValueError) as exc:
            raise EmbedError(f"input.{key} is not a loopback URL: {exc}") from exc


def load_report(path: Path) -> dict:
    """Load and fully validate one report JSON (fail-closed)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EmbedError(f"cannot read report {path}: {exc}") from exc
    _check_no_sentinels(text, f"report file {path}")
    try:
        report = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EmbedError(f"report {path} is not valid JSON: {exc}") from exc
    if not isinstance(report, dict):
        raise EmbedError(f"report {path} is not a JSON object")
    errors = validate_schema(report)
    if errors:
        raise EmbedError(f"report {path} fails the independent Schema check: {errors}")
    _reject_forbidden_keys(report)
    _check_report_structure(report)
    recomputed = compute_report_hash(report)
    if recomputed != report["report_hash"]:
        raise EmbedError(
            f"report_hash mismatch for {report.get('scenario_id')}: "
            f"stored {report['report_hash']}, recomputed {recomputed}"
        )
    return report


def load_baseline(contract_path: Path | None) -> dict:
    """Baseline expectations from a contract, or §5.1.2 constants.

    Only the three safe fields per representation are copied —
    Sentinel values are never read into the baseline block.
    """
    if contract_path is None:
        return json.loads(json.dumps(FROZEN_BASELINE))
    try:
        contract = parse_contract(json.loads(contract_path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise EmbedError(f"cannot load contract {contract_path}: {exc}") from exc
    baseline: dict[str, dict[str, object]] = {}
    for rep in ("html", "markdown"):
        entry = contract.representations[rep]
        baseline[rep] = {
            "accept": entry.accept,
            "expected_status": entry.expected_status,
            "expected_content_type": entry.expected_content_type,
        }
    return baseline


# ---------------------------------------------------------------------------
# HTML assembly and output scanning
# ---------------------------------------------------------------------------


def _load_template_assets() -> tuple[str, str, str]:
    template = (REPORT_UI_DIR / "index.html").read_text(encoding="utf-8")
    styles = (REPORT_UI_DIR / "styles.css").read_text(encoding="utf-8")
    script = (REPORT_UI_DIR / "report-ui.js").read_text(encoding="utf-8")
    for name, asset in (("index.html", template), ("styles.css", styles), ("report-ui.js", script)):
        _check_no_sentinels(asset, name)
    return template, styles, script


def _embed_json(payload: object) -> str:
    """Serialise a payload for a ``<script type="application/json">``
    block. ``</`` is escaped as ``<\\/`` (valid JSON, identical
    value on parse) so no payload string can close the script tag.
    """
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)
    return text.replace("</", "<\\/")


def _scan_finished_html(html: str, *, allow_relative_links: bool) -> None:
    """Fail-closed scan of finished HTML: no Sentinel literal, no
    remote reference, no external-resource tag of any kind."""
    _check_no_sentinels(html, "generated HTML")
    if "<link" in html or "<iframe" in html or "<img" in html:
        raise EmbedError("generated HTML contains <link>, <iframe> or <img>")
    # Exactly four <script> tags: three application/json payloads
    # plus the one inline UI bundle. Any other script tag (in
    # particular one with a src) fails.
    if html.count("<script") != 4 or "<script src" in html:
        raise EmbedError("generated HTML does not contain exactly the four expected inline <script> tags")
    if "@import" in html or "url(" in html:
        raise EmbedError("generated HTML contains @import or url()")
    if "http://" in html or "https://" in html:
        # Only loopback http(s) URLs may appear (report evidence
        # request_url / redirect_target values, e.g. E12/E22).
        # Protocol-relative URLs cannot occur: href values are
        # validated strictly below, there is no src attribute, and
        # the CSS/JS contain no protocol-relative reference.
        for match in re.finditer(r"https?://([^\s\"'<>/:]+)", html):
            if not _is_loopback_host(match.group(1)):
                raise EmbedError(
                    f"generated HTML contains a non-loopback URL host: {match.group(0)}"
                )
    hrefs = re.findall(r'href="([^"]*)"', html)
    for href in hrefs:
        if not allow_relative_links:
            raise EmbedError(f"generated HTML contains a link href={href!r}")
        if not re.fullmatch(r"[A-Za-z0-9_.\-]+\.html", href):
            raise EmbedError(f"generated HTML contains a non-relative href={href!r}")
    if "data:" in html:
        raise EmbedError("generated HTML contains a data: URI")


def _render(
    template: str,
    styles: str,
    script: str,
    *,
    report: dict | None,
    baseline: dict | None,
    summary: dict | None,
    allow_relative_links: bool,
) -> str:
    html = template
    html = html.replace("<!--ACCEPTTWIN:STYLES-->", styles, 1)
    html = html.replace("<!--ACCEPTTWIN:SCRIPT-->", script, 1)
    html = html.replace(
        "<!--ACCEPTTWIN:REPORT_JSON-->",
        _embed_json(report) if report is not None else "",
        1,
    )
    html = html.replace(
        "<!--ACCEPTTWIN:BASELINE_JSON-->",
        _embed_json(baseline) if baseline is not None else "",
        1,
    )
    html = html.replace(
        "<!--ACCEPTTWIN:SUMMARY_JSON-->",
        _embed_json(summary) if summary is not None else "",
        1,
    )
    for token in ("ACCEPTTWIN:STYLES", "ACCEPTTWIN:SCRIPT", "ACCEPTTWIN:REPORT_JSON", "ACCEPTTWIN:BASELINE_JSON", "ACCEPTTWIN:SUMMARY_JSON"):
        if token in html:
            raise EmbedError(f"template placeholder {token} was not replaced")
    _scan_finished_html(html, allow_relative_links=allow_relative_links)
    return html


# ---------------------------------------------------------------------------
# Privacy preview (printed before any file is written)
# ---------------------------------------------------------------------------


def print_privacy_preview(report: dict, out_name: str, baseline_source: str) -> None:
    print("PRIVACY PREVIEW — export happens only after this preview")
    print(f"  report:        {report['scenario_id']} ({report['verdict']})")
    print(f"  report_hash:   {report['report_hash']}")
    print(f"  output file:   {out_name}")
    print(f"  baseline from: {baseline_source}")
    print("  contains raw body text:        false")
    print("  contains sensitive headers:    false (no Authorization / Cookie)")
    print("  contains allow-listed headers: true (Accept, User-Agent, Accept-Encoding, Accept-Language)")
    print("  contains raw body content:     false")
    print("  contains body hashes:          true (SHA-256 + Sentinel match flags only)")
    print("  body text displayed:           never — hashes and match flags only")
    print("  remote references in output:   none (scan passed)")
    print("  Sentinel literals in output:   none (scan passed)")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def build_single(
    report_path: Path,
    contract_path: Path | None,
    template: str,
    styles: str,
    script: str,
) -> tuple[str, dict, str]:
    """Return (html, report, out_name) for one report file."""
    report = load_report(report_path)
    baseline = load_baseline(contract_path)
    baseline_source = (
        f"contract {contract_path}" if contract_path is not None else "frozen §5.1.2 constants"
    )
    html = _render(
        template,
        styles,
        script,
        report=report,
        baseline=baseline,
        summary=None,
        allow_relative_links=False,
    )
    return html, report, baseline_source


def cmd_single(args: argparse.Namespace) -> int:
    template, styles, script = _load_template_assets()
    html, report, baseline_source = build_single(
        args.report, args.contract, template, styles, script
    )
    out_name = str(args.out) if args.out is not None else f"{report['scenario_id']}.html"
    print_privacy_preview(report, out_name, baseline_source)
    if args.check_only:
        print(f"CHECK ONLY: {report['scenario_id']} OK (nothing written)")
        return 0
    if args.out is None:
        raise EmbedError("--out is required (no default output path)")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"WROTE {args.out} ({len(html.encode('utf-8'))} bytes)")
    return 0


def cmd_all_48(args: argparse.Namespace) -> int:
    template, styles, script = _load_template_assets()
    summary_path = REPORTS_DIR / "REPORTS_SUMMARY.json"
    try:
        recorded = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EmbedError(f"cannot read {summary_path}: {exc}") from exc
    recorded_samples = recorded.get("samples", {})

    pages: dict[str, str] = {}
    rows: list[dict] = []
    counts: dict[str, int] = {verdict: 0 for verdict in VERDICTS}
    for sid in SCENARIO_IDS:
        report_path = REPORTS_DIR / f"{sid}.json"
        contract_path = GOLDEN_DIR / sid / "contract.json"
        html, report, _baseline_source = build_single(
            report_path, contract_path, template, styles, script
        )
        recorded_row = recorded_samples.get(sid)
        if recorded_row is None:
            raise EmbedError(f"REPORTS_SUMMARY.json has no row for {sid}")
        for field in ("verdict", "first_error", "oracle_parity", "report_hash"):
            if recorded_row[field] != report[field]:
                raise EmbedError(
                    f"{sid}: {field} disagrees with REPORTS_SUMMARY.json "
                    f"({recorded_row[field]!r} != {report[field]!r})"
                )
        pages[sid] = html
        counts[report["verdict"]] += 1
        rows.append(
            {
                "scenario_id": sid,
                "verdict": report["verdict"],
                "first_error": report["first_error"],
                "critical_count": report["critical_count"],
                "warning_count": report["warning_count"],
                "oracle_parity": report["oracle_parity"],
                "final": report["final"],
                "report_hash": report["report_hash"],
            }
        )
    summary = {
        "generated_from": "evidence/Reports/<sid>.json (48 report samples, no experiment re-run)",
        "total": len(rows),
        "counts": counts,
        "rows": rows,
    }
    index_html = _render(
        template,
        styles,
        script,
        report=None,
        baseline=None,
        summary=summary,
        allow_relative_links=True,
    )

    out_dir = args.out_dir
    print("PRIVACY PREVIEW — 48 pages (export happens only after this preview)")
    print(f"  pages:         48 single-report pages + index.html -> {out_dir}")
    print(f"  verdicts:      {counts}")
    print(f"  oracle parity: {sum(1 for r in rows if r['oracle_parity'] is True)}/48")
    print("  contains raw body text:        false (all 48 reports scanned)")
    print("  contains sensitive headers:    false (all 48 reports scanned)")
    print("  contains body hashes:          true (SHA-256 + Sentinel match flags only)")
    print("  remote references in output:   none (all 49 pages scanned)")
    print("  Sentinel literals in output:   none (all 49 pages scanned)")
    if args.check_only:
        print("CHECK ONLY: 48/48 + index OK (nothing written)")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for sid in SCENARIO_IDS:
        (out_dir / f"{sid}.html").write_text(pages[sid], encoding="utf-8")
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    total_bytes = sum(len(p.encode("utf-8")) for p in pages.values()) + len(
        index_html.encode("utf-8")
    )
    print(f"WROTE 49 files to {out_dir} ({total_bytes} bytes total)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Embed an accepttwin.report/v1 JSON report into a self-contained offline HTML page."
    )
    parser.add_argument("report", nargs="?", type=Path, help="report JSON file (single mode)")
    parser.add_argument("--contract", type=Path, default=None, help="run contract JSON (baseline expectations; default: frozen §5.1.2 constants)")
    parser.add_argument("-o", "--out", type=Path, default=None, help="output HTML file (single mode)")
    parser.add_argument("--all-48", action="store_true", help="build all 48 pages + index.html summary")
    parser.add_argument("--out-dir", type=Path, default=REPORTS_DIR / "html", help="output directory for --all-48 (default: evidence/Reports/html)")
    parser.add_argument("--check-only", action="store_true", help="validate + print the privacy preview, write nothing")
    args = parser.parse_args(argv)
    try:
        if args.all_48:
            if args.report is not None:
                raise EmbedError("do not pass a report file together with --all-48")
            return cmd_all_48(args)
        if args.report is None:
            parser.error("a report file is required (or --all-48)")
        return cmd_single(args)
    except EmbedError as exc:
        print(f"EMBED_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
