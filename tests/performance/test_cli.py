"""CLI tests (P032 T012): ``python -m accepttwin`` help + entry points.

Full ``verify``/``benchmark`` runs are NOT executed here: each one
re-runs all 48 live scenarios (plus repeat-100) and takes minutes;
they are the acceptance commands themselves, run by the T012
delivery and recorded under ``evidence/Performance/``. These tests
pin the cheap, deterministic surface: help text, argument errors,
and that both subcommands delegate to the reviewed implementations.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run_cli(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "accepttwin", *argv],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=60,
    )


def test_help_lists_verify_and_benchmark() -> None:
    proc = _run_cli("--help")
    assert proc.returncode == 0, proc.stderr
    assert "verify" in proc.stdout
    assert "benchmark" in proc.stdout
    assert "accepttwin" in proc.stdout


def test_verify_help_names_suites() -> None:
    proc = _run_cli("verify", "--help")
    assert proc.returncode == 0, proc.stderr
    assert "--suite" in proc.stdout
    assert "s0" in proc.stdout and "all" in proc.stdout


def test_benchmark_help_names_suite_all() -> None:
    proc = _run_cli("benchmark", "--help")
    assert proc.returncode == 0, proc.stderr
    assert "--suite" in proc.stdout
    assert "all" in proc.stdout


def test_no_subcommand_exits_2_and_prints_help() -> None:
    proc = _run_cli()
    assert proc.returncode == 2
    assert "verify" in proc.stdout and "benchmark" in proc.stdout


def test_unknown_suite_exits_2() -> None:
    proc = _run_cli("verify", "--suite", "bogus")
    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr


def test_unknown_subcommand_exits_2() -> None:
    proc = _run_cli("frobnicate")
    assert proc.returncode == 2


def test_version_reports_frozen_version() -> None:
    proc = _run_cli("--version")
    assert proc.returncode == 0, proc.stderr
    assert "1.0.0" in proc.stdout


def test_documented_acceptance_commands_match_help() -> None:
    """README/USAGE must quote the acceptance commands exactly as
    the CLI spells them (T012 acceptance: docs == --help)."""
    help_text = _run_cli("--help").stdout
    assert "verify" in help_text and "benchmark" in help_text
    for doc in (ROOT / "README.md", ROOT / "docs" / "USAGE.md"):
        text = doc.read_text(encoding="utf-8")
        assert "python -m accepttwin verify --suite all" in text
        assert "python -m accepttwin benchmark --suite all" in text
        assert "python -m accepttwin verify --suite s0" in text


def test_verify_and_benchmark_delegate_to_reviewed_runners() -> None:
    """The CLI calls the reviewed script entry points; it does not
    contain a second Golden runner, classifier or report builder."""
    from accepttwin.cli import cmd_benchmark, cmd_verify, main

    assert callable(main) and callable(cmd_verify) and callable(cmd_benchmark)
    source = Path(__import__("accepttwin.cli", fromlist=["cli"]).__file__).read_text(
        encoding="utf-8"
    )
    assert "run_all_48" in source and "run_s0" in source
    assert "def classify_run" not in source
    assert "def build_report" not in source
    assert "def run_experiments" not in source
    assert "def canonical_json_bytes" not in source
    # The only canonical-JSON use is the import of the single source.
    assert "from accepttwin.contract import canonical_json_bytes" in source
