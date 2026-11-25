"""48-scenario Golden runner (P032 T008): execute C01-C24 + E01-E24.

Writes per-scenario evidence under ``evidence/Golden/<sid>/`` (same
file set as ``evidence/S0/``: ``raw-observations.json``,
``contract.json``, ``oracle-input.json``, ``production.json``,
``oracle.json``, ``scenario.json``) and the suite summary to
``evidence/Golden/ALL48_SUMMARY.json``.

Also performs the two multi-run checks that extend the S0 gate:

* stable bleed reproduction (§8.2, §11.3): E13 re-executed 3 times
  on fresh services (independent cache clears), each must yield
  REPRESENTATION_BLEED with the full dual-evidence chain;
* determinism spot check (§7.8, §10.4): E01 re-executed 3 times,
  each on a fresh pair with fresh OS-assigned ports, the canonical
  report hash must be identical all 3 times (the full 100-run check
  lives in scripts/run_s0.py for C01).

Exit code 0 only when every §11 item passes. This script never
declares the suite PASS on its own say-so: ``tests/golden/``
re-executes every scenario live and re-checks the same expectations.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from s0_harness import (  # noqa: E402
    ALL_SCENARIO_IDS,
    EXTENDED_FIXTURE_DIR,
    EXTENDED_SCENARIO_IDS,
    FIXTURE_DIR,
    ROOT,
    SCENARIO_IDS,
    check_parity,
    oracle_input_dict,
    run_oracle,
    run_scenario,
)

EVIDENCE_DIR = ROOT / "evidence" / "Golden"

HEALTHY_48 = [
    "C01", "C02", "C03", "C04", "C05", "C06", "C17", "C18",
    "E01", "E02", "E03", "E04", "E05", "E06", "E15", "E16",
]
KNOWN_FAILURES_48 = [
    "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14",
    "C15", "C16", "C19", "C24",
    "E09", "E10", "E11", "E13", "E14", "E23", "E24",
]


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _suite_of(scenario_id: str) -> tuple[Path, str]:
    """(fixture dir, contract prefix) for one scenario id."""
    if scenario_id in SCENARIO_IDS:
        return FIXTURE_DIR, "s0"
    return EXTENDED_FIXTURE_DIR, "ext"


def run_all() -> dict:
    """Execute the full 48-scenario suite and return the summary dict."""
    started = time.perf_counter()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    scenarios: dict[str, dict] = {}
    for sid in ALL_SCENARIO_IDS:
        fixture_dir, prefix = _suite_of(sid)
        outcome = run_scenario(
            sid,
            fixture_dir=fixture_dir,
            contract_prefix=prefix,
            namespace_prefix=f"all48-{sid}",
        )
        sdir = EVIDENCE_DIR / sid
        sdir.mkdir(parents=True, exist_ok=True)
        outcome.run.write_evidence(sdir / "raw-observations.json")
        _write_json(sdir / "contract.json", outcome.contract.as_dict())
        injection = outcome.fixture.get("injection") or {}
        oracle_input = oracle_input_dict(
            outcome.contract,
            outcome.run,
            outcome.adj_origin_events,
            origin_events_available=(
                injection.get("kind") != "origin_events_unavailable"
            ),
        )
        _write_json(sdir / "oracle-input.json", oracle_input)
        _write_json(sdir / "production.json", outcome.production.as_dict())
        oracle_result = run_oracle(
            sdir / "oracle-input.json", sdir / "oracle.json"
        )
        parity = check_parity(outcome, oracle_result)
        fixture = outcome.fixture
        expected_ok = (
            outcome.production.verdict == fixture["expected_verdict"]
            and outcome.production.first_error == fixture["expected_first_error"]
            and outcome.production.first_error_experiment_id
            == fixture["expected_first_error_experiment_id"]
            and outcome.diagnostics_projection == fixture["expected_diagnostics"]
        )
        scenarios[sid] = {
            "scenario_id": sid,
            "suite": "S0" if sid in SCENARIO_IDS else "extended",
            "expected_verdict": fixture["expected_verdict"],
            "verdict": outcome.production.verdict,
            "expected_first_error": fixture["expected_first_error"],
            "first_error": outcome.production.first_error,
            "first_error_experiment_id": outcome.production.first_error_experiment_id,
            "expected_diagnostics": fixture["expected_diagnostics"],
            "diagnostics": outcome.diagnostics_projection,
            "oracle_verdict": oracle_result["verdict"],
            "oracle_first_error": oracle_result["first_error"],
            "oracle_parity": parity["parity"],
            "oracle_mismatches": parity["mismatches"],
            "expected_ok": expected_ok,
            "duration_seconds": round(outcome.duration_seconds, 4),
            "report_hash": outcome.report_hash,
            "origin_counter_delta_total": sum(
                obs.origin_counter_delta for obs in outcome.run.observations
            ),
            "request_count": len(outcome.run.observations),
            "reset_count": len(outcome.run.reset_evidence),
            "step_count": len(outcome.run.step_log),
            "warm_hm_requests": [
                obs.request_index
                for obs in outcome.run.observations
                if obs.experiment_id == "HTML_TO_MARKDOWN"
            ],
            "warm_mh_requests": [
                obs.request_index
                for obs in outcome.run.observations
                if obs.experiment_id == "MARKDOWN_TO_HTML"
            ],
        }
        _write_json(sdir / "scenario.json", scenarios[sid])
        print(
            f"{sid}: {outcome.production.verdict} "
            f"(expected {fixture['expected_verdict']}) "
            f"first_error={outcome.production.first_error} "
            f"parity={'OK' if parity['parity'] else 'MISMATCH'} "
            f"{outcome.duration_seconds:.3f}s hash={outcome.report_hash[:12]}"
        )

    # -- stable bleed reproduction (§8.2, §11.3): E13, 3/3 ---------------
    bleed_runs = []
    for attempt in range(1, 4):
        outcome = run_scenario(
            "E13",
            fixture_dir=EXTENDED_FIXTURE_DIR,
            contract_prefix="ext",
            namespace_prefix=f"all48-E13-repro-{attempt}",
        )
        bleed_runs.append(
            {
                "attempt": attempt,
                "verdict": outcome.production.verdict,
                "first_error": outcome.production.first_error,
                "report_hash": outcome.report_hash,
                "bleed_diagnostics": [
                    d for d in outcome.diagnostics_projection
                    if d["code"] == "REPRESENTATION_BLEED"
                ],
            }
        )
        print(
            f"E13 repro {attempt}/3: {outcome.production.verdict} "
            f"first_error={outcome.production.first_error}"
        )
    bleed_ok = all(
        r["verdict"] == "REPRESENTATION_BLEED"
        and r["first_error"] == 6
        and len(r["bleed_diagnostics"]) == 2
        for r in bleed_runs
    )

    # -- determinism spot check (§7.8, §10.4): E01, fresh pair per run --
    det_hashes: list[str] = []
    for i in range(3):
        outcome = run_scenario(
            "E01",
            fixture_dir=EXTENDED_FIXTURE_DIR,
            contract_prefix="ext",
            namespace_prefix=f"all48-E01-det-{i+1}",
        )
        det_hashes.append(outcome.report_hash)
        if outcome.production.verdict != "PASS_OBSERVED":
            print(f"E01 determinism {i+1}: unexpected verdict {outcome.production.verdict}")
    det_ok = len(set(det_hashes)) == 1
    print(
        f"determinism E01: distinct_hashes={len(set(det_hashes))} "
        f"all_equal={det_ok}"
    )

    total_seconds = time.perf_counter() - started
    passed = sum(
        1
        for s in scenarios.values()
        if s["expected_ok"] and s["oracle_parity"]
    )
    parity_count = sum(1 for s in scenarios.values() if s["oracle_parity"])
    max_duration = max(s["duration_seconds"] for s in scenarios.values())
    summary = {
        "gate": "ALL48",
        "spec": "PROJECT_BOOK.md §11",
        "ALL48_STATUS": (
            "PASS"
            if passed == 48
            and parity_count == 48
            and bleed_ok
            and det_ok
            and max_duration < 1.0
            else "FAIL"
        ),
        "ALL48_GOLDEN": f"{passed}/48",
        "ALL48_ORACLE_PARITY": f"{parity_count}/48",
        "S0_GOLDEN": (
            f"{sum(1 for sid in SCENARIO_IDS if scenarios[sid]['expected_ok'] and scenarios[sid]['oracle_parity'])}/24"
        ),
        "EXTENDED_GOLDEN": (
            f"{sum(1 for sid in EXTENDED_SCENARIO_IDS if scenarios[sid]['expected_ok'] and scenarios[sid]['oracle_parity'])}/24"
        ),
        "FALSE_POSITIVE": sum(
            1
            for sid in HEALTHY_48
            if scenarios[sid]["verdict"] != "PASS_OBSERVED"
        ),
        "KNOWN_FAILURE_DETECTED": sum(
            1
            for sid in KNOWN_FAILURES_48
            if scenarios[sid]["verdict"] == scenarios[sid]["expected_verdict"]
        ),
        "KNOWN_FAILURE_TOTAL": len(KNOWN_FAILURES_48),
        "bleed_reproduction": {
            "scenario": "E13",
            "runs": bleed_runs,
            "reproduced_3_of_3": bleed_ok,
        },
        "determinism_spot_check": {
            "scenario": "E01",
            "runs": 3,
            "distinct_hashes": len(set(det_hashes)),
            "hash": det_hashes[0] if det_hashes else None,
            "all_equal": det_ok,
            "fresh_pair_per_run": True,
        },
        "max_scenario_duration_seconds": max_duration,
        "total_seconds": round(total_seconds, 2),
        "scenarios": scenarios,
    }
    _write_json(EVIDENCE_DIR / "ALL48_SUMMARY.json", summary)
    print(
        f"ALL48_STATUS: {summary['ALL48_STATUS']} "
        f"({passed}/48 golden, parity {parity_count}/48)"
    )
    return summary


if __name__ == "__main__":
    summary = run_all()
    sys.exit(0 if summary["ALL48_STATUS"] == "PASS" else 1)
