"""S0 gate runner (P032 T007-C): execute C01-C24 + Oracle parity.

Writes per-scenario evidence under ``evidence/S0/<sid>/`` and the
gate summary to ``evidence/S0/S0_SUMMARY.json``:

* ``raw-observations.json`` -- the runner's raw-observations file
  (``accepttwin.raw-observations/v1``), 8 real HTTP requests;
* ``contract.json`` -- the contract actually used (live ports);
* ``oracle-input.json`` -- the exact adjudication input both the
  production classifier and the Oracle judged (§12.2);
* ``production.json`` -- the production classification result;
* ``oracle.json`` -- the independent Oracle result;
* ``scenario.json`` -- fixture + duration + report hash + parity.

Also performs the two multi-run checks of §13 / §11.4:

* stable bleed reproduction (§8.2, §11.2): C11 re-executed 3 times
  on fresh services (independent cache clears), each must yield
  REPRESENTATION_BLEED with the full dual-evidence chain;
* repeat-100 (§7.8, §10.4): C01 re-executed 100 times, each run on
  a fresh pair with fresh OS-assigned ports (same logical input, real
  requests every time), the canonical report hash must be identical
  all 100 times (ADR-003: the old single-pair form passed by
  construction, since 100 runs shared one pair of ports). A
  supplementary 3-run same-pair check must give the same hash as
  the fresh-pair runs.

Exit code 0 only when every §13 item passes; the verdict itself is
in S0_SUMMARY.json (``S0_STATUS``). ``scripts/verify_s0.py`` re-checks
the evidence independently -- this script never declares S0 PASS on
its own say-so.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from s0_harness import (  # noqa: E402
    ROOT,
    SCENARIO_IDS,
    check_parity,
    make_pair,
    oracle_input_dict,
    run_oracle,
    run_scenario,
)

EVIDENCE_DIR = ROOT / "evidence" / "S0"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run_all() -> dict:
    """Execute the full S0 gate and return the summary dict."""
    started = time.perf_counter()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    scenarios: dict[str, dict] = {}
    for sid in SCENARIO_IDS:
        outcome = run_scenario(sid)
        sdir = EVIDENCE_DIR / sid
        sdir.mkdir(parents=True, exist_ok=True)
        # Raw evidence file (runner format) + contract + oracle input.
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

    # -- stable bleed reproduction (§8.2, §11.2): C11, 3/3 ---------------
    bleed_runs = []
    for attempt in range(1, 4):
        outcome = run_scenario("C11", namespace_prefix=f"s0-C11-repro-{attempt}")
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
            f"C11 repro {attempt}/3: {outcome.production.verdict} "
            f"first_error={outcome.production.first_error}"
        )
    bleed_ok = all(
        r["verdict"] == "REPRESENTATION_BLEED"
        and r["first_error"] == 6
        and len(r["bleed_diagnostics"]) == 2
        for r in bleed_runs
    )

    # -- repeat-100 (§7.8, §10.4): C01, fresh pair per run ------------
    # ADR-003: every iteration starts fresh services on fresh
    # OS-assigned ports, so a port-dependent hash cannot pass this
    # gate (the old single-pair form passed by construction). The
    # supplementary same-pair check pins the other direction:
    # re-running on one fixed pair must give the same hash as the
    # fresh-pair runs.
    repeat_hashes: list[str] = []
    repeat_durations: list[float] = []
    for i in range(100):
        outcome = run_scenario("C01", namespace_prefix=f"s0-C01-repeat-{i+1}")
        repeat_hashes.append(outcome.report_hash)
        repeat_durations.append(outcome.duration_seconds)
        if outcome.production.verdict != "PASS_OBSERVED":
            print(f"C01 repeat {i+1}: unexpected verdict {outcome.production.verdict}")
    repeat_ok = len(set(repeat_hashes)) == 1 and all(
        h == repeat_hashes[0] for h in repeat_hashes
    )
    same_pair_hashes: list[str] = []
    with make_pair("C01") as pair:
        for i in range(3):
            outcome = run_scenario(
                "C01", pair=pair, namespace_prefix=f"s0-C01-samepair-{i+1}"
            )
            same_pair_hashes.append(outcome.report_hash)
            if outcome.production.verdict != "PASS_OBSERVED":
                print(f"C01 same-pair {i+1}: unexpected verdict {outcome.production.verdict}")
    same_pair_ok = (
        len(set(same_pair_hashes)) == 1
        and same_pair_hashes
        and same_pair_hashes[0] == repeat_hashes[0]
    )
    repeat_ok = repeat_ok and same_pair_ok
    print(
        f"repeat-100 C01: distinct_hashes={len(set(repeat_hashes))} "
        f"all_equal={repeat_ok} max_duration={max(repeat_durations):.3f}s "
        f"same_pair_equal={same_pair_ok}"
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
        "gate": "S0",
        "spec": "PROJECT_BOOK.md §13",
        "S0_STATUS": (
            "PASS"
            if passed == 24
            and parity_count == 24
            and bleed_ok
            and repeat_ok
            and max_duration < 1.0
            else "FAIL"
        ),
        "S0_CORE_GOLDEN": f"{passed}/24",
        "S0_ORACLE_PARITY": f"{parity_count}/24",
        "S0_FALSE_POSITIVE": sum(
            1
            for sid in ("C01", "C02", "C03", "C04", "C05", "C06", "C17", "C18")
            if scenarios[sid]["verdict"] != "PASS_OBSERVED"
        ),
        "S0_KNOWN_FAILURE_DETECTED": sum(
            1
            for sid in (
                "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14",
                "C15", "C16", "C19", "C24",
            )
            if scenarios[sid]["verdict"] == scenarios[sid]["expected_verdict"]
        ),
        "S0_KNOWN_FAILURE_TOTAL": 12,
        "bleed_reproduction": {
            "scenario": "C11",
            "runs": bleed_runs,
            "reproduced_3_of_3": bleed_ok,
        },
        "repeat_100": {
            "scenario": "C01",
            "runs": 100,
            "distinct_hashes": len(set(repeat_hashes)),
            "hash": repeat_hashes[0] if repeat_hashes else None,
            "all_equal": repeat_ok,
            "max_duration_seconds": round(max(repeat_durations), 4),
            "fresh_pair_per_run": True,
            "same_pair_runs": len(same_pair_hashes),
            "same_pair_hash": same_pair_hashes[0] if same_pair_hashes else None,
            "same_pair_all_equal": same_pair_ok,
        },
        "max_scenario_duration_seconds": max_duration,
        "total_seconds": round(total_seconds, 2),
        "scenarios": scenarios,
    }
    _write_json(EVIDENCE_DIR / "S0_SUMMARY.json", summary)
    print(f"S0_STATUS: {summary['S0_STATUS']} ({passed}/24 golden, parity {parity_count}/24)")
    return summary


if __name__ == "__main__":
    summary = run_all()
    sys.exit(0 if summary["S0_STATUS"] == "PASS" else 1)
