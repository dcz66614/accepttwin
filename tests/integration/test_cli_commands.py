"""CLI tests (P032 P1-01 FIX-R1): ``run`` / ``demo`` / ``verify --report`` /
``report preview|export|delete`` / ``clean`` / ``contract delete``.

Every positive test runs the real entry point
(``python -m accepttwin``) with real HTTP experiments and the real
independent Oracle — no Golden replay, no mocked runner. The two
custom contracts under ``tests/fixtures/contracts/`` are user-written
contracts (own contract_ids, own loopback ports), not Golden
fixtures: the healthy one must yield PASS_OBSERVED and the bleed one
(with ``--proxy-mode force_uri_only``) must yield
REPRESENTATION_BLEED with first_error 6.

Negative tests assert the exit-code contract (0 = command succeeded,
1 = gate/verification failure, 2 = bad input / refused deletion)
and that refused deletions never delete the victim file.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HEALTHY_CONTRACT = ROOT / "tests" / "fixtures" / "contracts" / "custom-healthy.json"
BLEED_CONTRACT = ROOT / "tests" / "fixtures" / "contracts" / "custom-bleed.json"
RUNS_DIR = ROOT / "output" / "runs"


def _run_cli(*argv: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "accepttwin", *argv],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=timeout,
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tracked_run_dir(run_id: str) -> Path:
    return RUNS_DIR / run_id


@pytest.fixture(scope="module")
def healthy_run() -> dict:
    """One live healthy custom-contract run, shared by read-only tests."""
    run_id = "cli-test-healthy"
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--run-id", run_id
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out_dir = _tracked_run_dir(run_id)
    report = _read_json(out_dir / "report.json")
    yield {"run_id": run_id, "out_dir": out_dir, "report": report, "proc": proc}
    # Leave the evidence in place: it is under output/ (git-ignored)
    # and documents the run. Tests that need a fresh copy duplicate it.


@pytest.fixture(scope="module")
def bleed_run() -> dict:
    """One live bleed custom-contract run, shared by read-only tests."""
    run_id = "cli-test-bleed"
    proc = _run_cli(
        "run",
        "--contract",
        str(BLEED_CONTRACT),
        "--proxy-mode",
        "force_uri_only",
        "--run-id",
        run_id,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out_dir = _tracked_run_dir(run_id)
    report = _read_json(out_dir / "report.json")
    yield {"run_id": run_id, "out_dir": out_dir, "report": report, "proc": proc}


# ---------------------------------------------------------------------------
# run --contract: healthy custom contract
# ---------------------------------------------------------------------------


def test_run_healthy_custom_contract(healthy_run):
    proc = healthy_run["proc"]
    assert "RUN_STATUS: COMPLETE" in proc.stdout
    assert "verdict=PASS_OBSERVED" in proc.stdout
    assert "oracle_parity=True" in proc.stdout
    report = healthy_run["report"]
    assert report["schema"] == "accepttwin.report/v1"
    assert report["verdict"] == "PASS_OBSERVED"
    assert report["first_error"] is None
    assert report["oracle_parity"] is True
    assert report["final"] is True
    assert report["scenario_id"] == "C01"
    assert report["input"]["contract_id"] == "custom-healthy-001"
    assert len(report["observations"]) == 8
    assert [o["request_index"] for o in report["observations"]] == list(range(1, 9))
    assert [o["cache_status"] for o in report["observations"][2:]] == ["MISS"] * 6
    # Sibling evidence files all exist.
    for name in (
        "contract.json",
        "raw-observations.json",
        "production.json",
        "oracle-input.json",
        "oracle.json",
        "run-summary.json",
    ):
        assert (healthy_run["out_dir"] / name).is_file(), name
    summary = _read_json(healthy_run["out_dir"] / "run-summary.json")
    assert summary["contract_id"] == "custom-healthy-001"
    assert summary["proxy_mode"] == "respect_vary"
    assert summary["ok"] is True


def test_run_report_hash_recomputes(healthy_run):
    from accepttwin.report_builder import compute_report_hash

    report = healthy_run["report"]
    assert compute_report_hash(report) == report["report_hash"]


def test_run_report_is_schema_valid(healthy_run):
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "tests" / "unit"))
    from independent_schema_validator import validate

    assert validate(healthy_run["report"]) == []


def test_run_oracle_agrees_with_production(healthy_run):
    out_dir = healthy_run["out_dir"]
    production = _read_json(out_dir / "production.json")
    oracle = _read_json(out_dir / "oracle.json")
    report = healthy_run["report"]
    assert oracle["verdict"] == production["verdict"] == report["verdict"]
    assert oracle["first_error"] == production["first_error"]
    assert oracle["verified_cache_states"] == production["confirmed_cache_states"]
    assert report["oracle"]["verdict"] == oracle["verdict"]


def test_run_bleed_custom_contract(bleed_run):
    proc = bleed_run["proc"]
    assert "verdict=REPRESENTATION_BLEED" in proc.stdout
    report = bleed_run["report"]
    assert report["verdict"] == "REPRESENTATION_BLEED"
    assert report["first_error"] == 6
    assert report["first_error_experiment_id"] == "HTML_TO_MARKDOWN"
    assert report["oracle_parity"] is True
    assert report["final"] is True
    assert report["scenario_id"] == "C11"
    states = {o["request_index"]: o["cache_status"] for o in report["observations"]}
    assert states[6] == "HIT" and states[8] == "HIT"
    oracle = _read_json(bleed_run["out_dir"] / "oracle.json")
    assert oracle["verdict"] == "REPRESENTATION_BLEED"
    assert oracle["verified_cache_states"] == _read_json(
        bleed_run["out_dir"] / "production.json"
    )["confirmed_cache_states"]


def test_run_with_output_path(tmp_path):
    out = tmp_path / "my-report.json"
    proc = _run_cli(
        "run",
        "--contract",
        str(HEALTHY_CONTRACT),
        "--run-id",
        "cli-test-output",
        "--output",
        str(out),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.is_file()
    assert (tmp_path / "run-summary.json").is_file()
    assert (tmp_path / "oracle.json").is_file()
    assert _read_json(out)["verdict"] == "PASS_OBSERVED"


def test_run_explicit_scenario_id_for_unmapped_config():
    # no_vary + opaque is not in the S0 configuration table, so it
    # needs an explicit label — and then it runs for real.
    proc = _run_cli(
        "run",
        "--contract",
        str(BLEED_CONTRACT),
        "--scenario",
        "no_vary",
        "--proxy-mode",
        "opaque",
        "--scenario-id",
        "E17",
        "--run-id",
        "cli-test-unmapped",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = _read_json(_tracked_run_dir("cli-test-unmapped") / "report.json")
    assert report["scenario_id"] == "E17"
    assert report["oracle_parity"] is True
    assert report["final"] is True


# ---------------------------------------------------------------------------
# run --contract: negative tests
# ---------------------------------------------------------------------------


def test_run_invalid_contract(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema": "accepttwin.contract/v1", "contract_id": 1}', encoding="utf-8")
    proc = _run_cli("run", "--contract", str(bad), "--run-id", "cli-test-bad")
    assert proc.returncode == 2
    assert not _tracked_run_dir("cli-test-bad").exists()


def test_run_missing_contract_file():
    proc = _run_cli(
        "run", "--contract", "tests/fixtures/contracts/does-not-exist.json"
    )
    assert proc.returncode == 2
    assert "not found" in proc.stderr


def test_run_non_loopback_contract(tmp_path):
    data = _read_json(HEALTHY_CONTRACT)
    data["url"] = "http://8.8.8.8:18771/doc"
    data["origin_url"] = "http://8.8.8.8:18772/doc"
    path = tmp_path / "public.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    proc = _run_cli("run", "--contract", str(path))
    assert proc.returncode == 2


def test_run_unknown_scenario():
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--scenario", "no-such-scenario"
    )
    assert proc.returncode == 2


def test_run_unknown_proxy_mode():
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--proxy-mode", "bogus"
    )
    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr


def test_run_invalid_scenario_id():
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--scenario-id", "CUSTOM"
    )
    assert proc.returncode == 2


def test_run_unmapped_config_without_scenario_id():
    proc = _run_cli(
        "run",
        "--contract",
        str(BLEED_CONTRACT),
        "--scenario",
        "no_vary",
        "--proxy-mode",
        "opaque",
    )
    assert proc.returncode == 2
    assert "--scenario-id" in proc.stderr


def test_run_bad_run_id():
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--run-id", "../escape"
    )
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------


def test_demo_passes_with_both_verdicts_and_html():
    proc = _run_cli("demo")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "DEMO_STATUS: PASS" in proc.stdout
    healthy = _read_json(RUNS_DIR / "demo-healthy" / "report.json")
    bleed = _read_json(RUNS_DIR / "demo-bleed" / "report.json")
    assert healthy["verdict"] == "PASS_OBSERVED"
    assert healthy["oracle_parity"] is True and healthy["final"] is True
    assert bleed["verdict"] == "REPRESENTATION_BLEED"
    assert bleed["first_error"] == 6
    assert bleed["oracle_parity"] is True and bleed["final"] is True
    for run_id in ("demo-healthy", "demo-bleed"):
        html = RUNS_DIR / run_id / "report.html"
        assert html.is_file()
        text = html.read_text(encoding="utf-8")
        assert _read_json(RUNS_DIR / run_id / "report.json")["report_hash"] in text
        assert "AT_HTML_SENTINEL_001" not in text
        assert "AT_MARKDOWN_SENTINEL_001" not in text


# ---------------------------------------------------------------------------
# verify --report
# ---------------------------------------------------------------------------


def test_verify_report_healthy(healthy_run):
    proc = _run_cli("verify", "--report", str(healthy_run["out_dir"] / "report.json"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERIFY_REPORT: C01" in proc.stdout
    assert "verdict=PASS_OBSERVED" in proc.stdout
    assert "schema=OK hash=OK" in proc.stdout


def test_verify_report_bleed_is_valid(bleed_run):
    proc = _run_cli(
        "verify", "--report", str(bleed_run["out_dir"] / "report.json")
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "verdict=REPRESENTATION_BLEED" in proc.stdout


def test_verify_report_with_matching_contract(healthy_run):
    proc = _run_cli(
        "verify",
        "--report",
        str(healthy_run["out_dir"] / "report.json"),
        "--contract",
        str(HEALTHY_CONTRACT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "contract_sha256=OK" in proc.stdout


def test_verify_report_with_wrong_contract(healthy_run):
    proc = _run_cli(
        "verify",
        "--report",
        str(healthy_run["out_dir"] / "report.json"),
        "--contract",
        str(BLEED_CONTRACT),
    )
    assert proc.returncode == 1
    assert "does not match" in proc.stderr


def test_verify_report_tampered_hash(healthy_run, tmp_path):
    report = dict(healthy_run["report"])
    report["verdict"] = "CONTRACT_MISMATCH"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(report), encoding="utf-8")
    proc = _run_cli("verify", "--report", str(tampered))
    assert proc.returncode == 1


def test_verify_report_missing_file():
    proc = _run_cli("verify", "--report", "output/runs/no-such-run/report.json")
    assert proc.returncode == 2


def test_verify_suite_and_report_mutually_exclusive(healthy_run):
    proc = _run_cli(
        "verify",
        "--suite",
        "s0",
        "--report",
        str(healthy_run["out_dir"] / "report.json"),
    )
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# report preview / export
# ---------------------------------------------------------------------------


def test_report_preview_writes_nothing(healthy_run):
    out_dir = healthy_run["out_dir"]
    before = {
        p.name: (p.stat().st_mtime_ns, p.stat().st_size)
        for p in out_dir.iterdir()
    }
    time.sleep(0.01)
    proc = _run_cli("report", "preview", str(out_dir / "report.json"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PRIVACY PREVIEW" in proc.stdout
    assert "verdict:       PASS_OBSERVED" in proc.stdout
    assert "001 ORIGIN_HTML" in proc.stdout
    after = {
        p.name: (p.stat().st_mtime_ns, p.stat().st_size)
        for p in out_dir.iterdir()
    }
    assert before == after


def test_report_export_writes_clean_html(healthy_run):
    out_dir = healthy_run["out_dir"]
    html_path = out_dir / "preview-export.html"
    if html_path.exists():
        html_path.unlink()
    proc = _run_cli(
        "report", "export", str(out_dir / "report.json"), "--out", str(html_path)
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PRIVACY PREVIEW" in proc.stdout
    assert html_path.is_file()
    text = html_path.read_text(encoding="utf-8")
    assert healthy_run["report"]["report_hash"] in text
    assert '"verdict": "PASS_OBSERVED"' in text
    from accepttwin.privacy import scan_html_for_remote_resources

    assert scan_html_for_remote_resources(text) == []
    assert "AT_HTML_SENTINEL_001" not in text
    assert "AT_MARKDOWN_SENTINEL_001" not in text


def test_report_export_default_out_next_to_report(healthy_run):
    out_dir = healthy_run["out_dir"]
    html_path = out_dir / "report.html"
    if html_path.exists():
        html_path.unlink()
    proc = _run_cli("report", "export", str(out_dir / "report.json"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert html_path.is_file()


def test_report_export_check_only_writes_nothing(healthy_run):
    out_dir = healthy_run["out_dir"]
    before = sorted(p.name for p in out_dir.iterdir())
    proc = _run_cli(
        "report", "export", str(out_dir / "report.json"), "--check-only"
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CHECK ONLY" in proc.stdout
    assert sorted(p.name for p in out_dir.iterdir()) == before


def test_report_preview_missing_file():
    proc = _run_cli("report", "preview", "output/runs/no-such-run/report.json")
    assert proc.returncode == 2


def test_report_export_invalid_report(healthy_run, tmp_path):
    report = dict(healthy_run["report"])
    report["verdict"] = "CONTRACT_MISMATCH"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(report), encoding="utf-8")
    proc = _run_cli("report", "export", str(tampered))
    assert proc.returncode == 1


# ---------------------------------------------------------------------------
# report delete / contract delete (safety boundaries)
# ---------------------------------------------------------------------------


def _copy_report_to_run_dir(run_id: str) -> Path:
    out_dir = _tracked_run_dir(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "report.json"
    target.write_text(
        (RUNS_DIR / "cli-test-healthy" / "report.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return target


def test_report_delete_removes_report(healthy_run):
    target = _copy_report_to_run_dir("cli-test-del-report")
    proc = _run_cli("report", "delete", str(target))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "deleted:" in proc.stdout
    assert not target.exists()


def test_report_delete_refuses_non_report():
    out_dir = _tracked_run_dir("cli-test-del-nonreport")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "contract.json"
    target.write_text(
        HEALTHY_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    proc = _run_cli("report", "delete", str(target))
    assert proc.returncode == 2
    assert target.exists(), "refused delete must not delete the file"


def test_report_delete_refuses_outside_workspace(healthy_run, tmp_path):
    victim = tmp_path / "victim-report.json"
    victim.write_text(
        (healthy_run["out_dir"] / "report.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    proc = _run_cli("report", "delete", str(victim))
    assert proc.returncode == 2
    assert victim.exists()


def test_report_delete_refuses_symlink(healthy_run):
    out_dir = _tracked_run_dir("cli-test-del-symlink")
    out_dir.mkdir(parents=True, exist_ok=True)
    real = healthy_run["out_dir"] / "report.json"
    link = out_dir / "report.json"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(real)
    proc = _run_cli("report", "delete", str(link))
    assert proc.returncode == 2
    assert real.exists()
    assert link.is_symlink()
    link.unlink()


def test_report_delete_refuses_directory(healthy_run):
    proc = _run_cli("report", "delete", str(healthy_run["out_dir"]))
    assert proc.returncode == 2


def test_report_delete_missing_file():
    proc = _run_cli("report", "delete", "output/runs/no-such-run/report.json")
    assert proc.returncode == 2


def test_contract_delete_removes_contract():
    out_dir = _tracked_run_dir("cli-test-del-contract")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "contract.json"
    target.write_text(HEALTHY_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
    proc = _run_cli("contract", "delete", str(target))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not target.exists()


def test_contract_delete_refuses_non_contract(healthy_run):
    target = _copy_report_to_run_dir("cli-test-del-noncontract")
    proc = _run_cli("contract", "delete", str(target))
    assert proc.returncode == 2
    assert target.exists()


def test_contract_delete_refuses_outside_workspace(tmp_path):
    victim = tmp_path / "victim-contract.json"
    victim.write_text(HEALTHY_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
    proc = _run_cli("contract", "delete", str(victim))
    assert proc.returncode == 2
    assert victim.exists()


def test_contract_delete_refuses_symlink():
    out_dir = _tracked_run_dir("cli-test-del-contract-symlink")
    out_dir.mkdir(parents=True, exist_ok=True)
    link = out_dir / "contract.json"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(HEALTHY_CONTRACT)
    proc = _run_cli("contract", "delete", str(link))
    assert proc.returncode == 2
    assert HEALTHY_CONTRACT.exists()
    assert link.is_symlink()
    link.unlink()


# ---------------------------------------------------------------------------
# clean --run-id
# ---------------------------------------------------------------------------


def test_clean_deletes_run_dir():
    run_id = "cli-test-clean"
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--run-id", run_id
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _tracked_run_dir(run_id).is_dir()
    proc = _run_cli("clean", "--run-id", run_id)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CLEAN_STATUS: OK" in proc.stdout
    assert not _tracked_run_dir(run_id).exists()


def test_clean_dry_run_deletes_nothing():
    run_id = "cli-test-clean-dry"
    proc = _run_cli(
        "run", "--contract", str(HEALTHY_CONTRACT), "--run-id", run_id
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    before = sorted(p.name for p in _tracked_run_dir(run_id).iterdir())
    proc = _run_cli("clean", "--run-id", run_id, "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "DRY-RUN" in proc.stdout
    assert sorted(p.name for p in _tracked_run_dir(run_id).iterdir()) == before
    proc = _run_cli("clean", "--run-id", run_id)
    assert proc.returncode == 0


def test_clean_missing_run():
    proc = _run_cli("clean", "--run-id", "no-such-run")
    assert proc.returncode == 2


def test_clean_traversal_run_id():
    # "../custom-healthy-001" would escape output/runs/ if resolved;
    # the run-id validator must refuse it before anything is touched.
    assert not (ROOT / "output" / "custom-healthy-001").exists()
    proc = _run_cli("clean", "--run-id", "../custom-healthy-001")
    assert proc.returncode == 2
    assert not (ROOT / "output" / "custom-healthy-001").exists()


def test_clean_refuses_symlink_inside():
    run_id = "cli-test-clean-symlink"
    out_dir = _tracked_run_dir(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    victim = out_dir / "keep.txt"
    victim.write_text("keep", encoding="utf-8")
    link = out_dir / "link.json"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(victim)
    proc = _run_cli("clean", "--run-id", run_id)
    assert proc.returncode == 2
    assert victim.exists()
    assert out_dir.is_dir()
    link.unlink()
    victim.unlink()
    out_dir.rmdir()


def test_clean_refuses_symlink_run_dir(tmp_path):
    real = tmp_path / "real-run"
    real.mkdir()
    (real / "report.json").write_text("{}", encoding="utf-8")
    link = RUNS_DIR / "cli-test-clean-linkdir"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(real)
    proc = _run_cli("clean", "--run-id", "cli-test-clean-linkdir")
    assert proc.returncode == 2
    assert (real / "report.json").exists()
    link.unlink()


# ---------------------------------------------------------------------------
# help / docs surface
# ---------------------------------------------------------------------------


def test_help_lists_all_commands():
    proc = _run_cli("--help")
    assert proc.returncode == 0, proc.stderr
    for name in ("run", "demo", "verify", "report", "clean", "contract", "benchmark"):
        assert name in proc.stdout


def test_report_subcommand_help_lists_preview_export_delete():
    proc = _run_cli("report", "--help")
    assert proc.returncode == 0, proc.stderr
    for name in ("preview", "export", "delete"):
        assert name in proc.stdout


def test_docs_name_the_new_commands():
    for doc in (ROOT / "README.md", ROOT / "docs" / "USAGE.md"):
        text = doc.read_text(encoding="utf-8")
        assert "accepttwin run --contract" in text
        assert "accepttwin demo" in text
        assert "accepttwin verify --report" in text
        assert "accepttwin report preview" in text
        assert "accepttwin report export" in text
        assert "accepttwin clean --run-id" in text
