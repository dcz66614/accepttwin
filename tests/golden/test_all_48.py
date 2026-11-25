"""48-scenario integration tests (P032 T008): C01-C24 + E01-E24.

One combined golden + Oracle-parity test per scenario over the full
48, plus set-level invariants (§11.3, §12, §18 AC03):

* 48/48 Golden match frozen expectations;
* 48/48 Oracle parity, verdict + diagnostics + first error;
* S0 24 re-run here still pass (the S0 gate itself is
  ``tests/golden/test_s0.py`` + ``scripts/run_s0.py``);
* healthy 16 zero false positives; known failures 19 detected;
* insufficient-evidence 13 never misjudged as bleed/origin error;
* every scenario ran the full four experiments on real HTTP.

The deep per-suite checks live in ``test_s0.py`` (S0) and
``test_extended.py`` (E01–E24); this file proves the combined set.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from s0_harness import (  # noqa: E402
    ALL_SCENARIO_IDS,
    EXTENDED_FIXTURE_DIR,
    EXTENDED_SCENARIO_IDS,
    FIXTURE_DIR,
    SCENARIO_IDS,
    check_parity,
    oracle_input_dict,
    run_oracle,
    run_scenario,
)

HEALTHY_48 = [
    "C01", "C02", "C03", "C04", "C05", "C06", "C17", "C18",
    "E01", "E02", "E03", "E04", "E05", "E06", "E15", "E16",
]
KNOWN_FAILURES_48 = [
    "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14",
    "C15", "C16", "C19", "C24",
    "E09", "E10", "E11", "E13", "E14", "E23", "E24",
]
INSUFFICIENT_48 = [
    "C20", "C21", "C22", "C23",
    "E07", "E08", "E12", "E17", "E18", "E19", "E20", "E21", "E22",
]


def _suite_of(scenario_id: str):
    if scenario_id in SCENARIO_IDS:
        return FIXTURE_DIR, "s0"
    return EXTENDED_FIXTURE_DIR, "ext"


def _run(scenario_id: str, **kwargs):
    fixture_dir, prefix = _suite_of(scenario_id)
    return run_scenario(
        scenario_id,
        fixture_dir=fixture_dir,
        contract_prefix=prefix,
        **kwargs,
    )


@pytest.mark.parametrize("scenario_id", ALL_SCENARIO_IDS)
def test_all_48_golden_and_parity(scenario_id, tmp_path):
    """Each of the 48 scenarios: frozen expectation + Oracle parity."""
    outcome = _run(scenario_id, namespace_prefix=f"all48-{scenario_id}")
    fx = outcome.fixture
    assert outcome.production.verdict == fx["expected_verdict"], scenario_id
    assert outcome.production.first_error == fx["expected_first_error"], scenario_id
    assert (
        outcome.production.first_error_experiment_id
        == fx["expected_first_error_experiment_id"]
    ), scenario_id
    assert outcome.diagnostics_projection == fx["expected_diagnostics"], scenario_id
    assert len(outcome.run.observations) == 8, scenario_id
    assert outcome.duration_seconds < 1.0, scenario_id

    injection = fx.get("injection") or {}
    input_path = tmp_path / f"{scenario_id}-oracle-input.json"
    output_path = tmp_path / f"{scenario_id}-oracle.json"
    input_path.write_text(
        json.dumps(
            oracle_input_dict(
                outcome.contract,
                outcome.run,
                outcome.adj_origin_events,
                origin_events_available=(
                    injection.get("kind") != "origin_events_unavailable"
                ),
            ),
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    oracle_result = run_oracle(input_path, output_path)
    parity = check_parity(outcome, oracle_result)
    assert parity["parity"], f"{scenario_id}: " + "; ".join(parity["mismatches"])


def test_all_48_healthy_zero_false_positives():
    assert len(HEALTHY_48) == 16
    for sid in HEALTHY_48:
        outcome = _run(sid, namespace_prefix=f"all48-{sid}-healthy")
        assert outcome.production.verdict == "PASS_OBSERVED", sid
        assert outcome.production.critical_count == 0, sid


def test_all_48_known_failures_detected():
    assert len(KNOWN_FAILURES_48) == 19
    for sid in KNOWN_FAILURES_48:
        outcome = _run(sid, namespace_prefix=f"all48-{sid}-known")
        assert outcome.production.verdict == outcome.fixture["expected_verdict"], sid
        assert outcome.production.first_error is not None, sid


def test_all_48_insufficient_evidence_never_misjudged():
    assert len(INSUFFICIENT_48) == 13
    for sid in INSUFFICIENT_48:
        outcome = _run(sid, namespace_prefix=f"all48-{sid}-insufficient")
        assert outcome.production.verdict == "INCONCLUSIVE", sid
        codes = [d.code for d in outcome.production.diagnostics]
        assert "REPRESENTATION_BLEED" not in codes, sid
        assert "ORIGIN_NEGOTIATION_ERROR" not in codes, sid


def test_all_48_verdict_distribution():
    # The 48 split is fixed by §11.2/§11.3: 16 PASS, 4 origin errors
    # in S0 + 3 in extended, 6 bleeds in S0 + 2 in extended, 2
    # contract mismatches in S0 + 2 in extended, 4 inconclusive in
    # S0 + 9 in extended. Recomputed live (one run per scenario is
    # already covered above; this test re-runs cheaply via the same
    # harness and pins the distribution, not individual verdicts).
    counts: dict[str, int] = {}
    for sid in ALL_SCENARIO_IDS:
        outcome = _run(sid, namespace_prefix=f"all48-{sid}-dist")
        counts[outcome.production.verdict] = (
            counts.get(outcome.production.verdict, 0) + 1
        )
    assert counts == {
        "PASS_OBSERVED": 16,
        "ORIGIN_NEGOTIATION_ERROR": 7,
        "REPRESENTATION_BLEED": 8,
        "CONTRACT_MISMATCH": 4,
        "INCONCLUSIVE": 13,
    }
    assert sum(counts.values()) == 48
