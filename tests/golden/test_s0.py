"""S0 Golden tests (P032 T007): C01-C24, independent Oracle, S0 gate.

Every test makes real HTTP requests over loopback through
``scripts/s0_harness.py`` (the same harness ``scripts/run_s0.py``
uses for the gate). Expected verdicts, diagnostics and first-error
locations come from the frozen fixtures in ``fixtures/s0/`` -- never
from the implementation under test.

Coverage (PROJECT_BOOK §13):
* 24/24 Golden match frozen expectations (§11.2);
* 24/24 Oracle parity, verdict + diagnostics + first error (§12);
* healthy scenarios zero false positives (§7, §11.2);
* known failures detected (§8, §11.2);
* both warm orders really executed, no mid-warm reset (§0.2, §6);
* independent cold requests with dual MISS/BYPASS proof (§5.4, §6);
* dual cache evidence, header + behaviour (§5.3);
* stable bleed reproduction 3/3 (§8.2, §11.2);
* missing-Vary healthy control (§7.11, §11.2);
* canonical report hash deterministic on re-execution (§7.8, §10.4)
  -- the full 100-run check lives in scripts/run_s0.py;
* single scenario < 1s (§10.5);
* insufficient evidence never misjudged (§8.4, §8.8, §9.4);
* first-error location (§6.3, §8);
* mandatory classify_run call convention (ADR-002 Decision 3).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from s0_harness import (  # noqa: E402
    ROOT,
    SCENARIO_IDS,
    check_parity,
    load_scenario,
    make_pair,
    oracle_input_dict,
    report_hash,
    run_oracle,
    run_scenario,
)

HEALTHY = ["C01", "C02", "C03", "C04", "C05", "C06", "C17", "C18"]
KNOWN_FAILURES = [
    "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14",
    "C15", "C16", "C19", "C24",
]
INSUFFICIENT = ["C20", "C21", "C22", "C23"]


def _oracle_for(outcome, tmp_path: Path) -> dict:
    """Run the independent Oracle on this outcome's adjudication input."""
    injection = outcome.fixture.get("injection") or {}
    input_path = tmp_path / f"{outcome.scenario_id}-oracle-input.json"
    output_path = tmp_path / f"{outcome.scenario_id}-oracle.json"
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
    return run_oracle(input_path, output_path)


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_golden_matches_frozen_expectation(scenario_id):
    outcome = run_scenario(scenario_id)
    fx = outcome.fixture
    assert outcome.production.verdict == fx["expected_verdict"]
    assert outcome.production.first_error == fx["expected_first_error"]
    assert (
        outcome.production.first_error_experiment_id
        == fx["expected_first_error_experiment_id"]
    )
    assert outcome.diagnostics_projection == fx["expected_diagnostics"]
    # Full four experiments, real requests, frozen order.
    assert len(outcome.run.observations) == 8
    assert [o.request_index for o in outcome.run.observations] == list(range(1, 9))
    assert [o.experiment_id for o in outcome.run.observations] == [
        "ORIGIN_HTML", "ORIGIN_MARKDOWN", "HTML_COLD", "MARKDOWN_COLD",
        "HTML_TO_MARKDOWN", "HTML_TO_MARKDOWN",
        "MARKDOWN_TO_HTML", "MARKDOWN_TO_HTML",
    ]
    assert len(outcome.run.reset_evidence) == 4
    assert len(outcome.run.step_log) == 25
    # No body text anywhere in the evidence (§7.12 I-12).
    evidence_text = json.dumps(outcome.run.as_dict())
    assert "AT_HTML_SENTINEL_001" not in evidence_text
    assert "AT_MARKDOWN_SENTINEL_001" not in evidence_text
    assert "<!DOCTYPE html>" not in evidence_text
    # Single scenario < 1s (§10.5).
    assert outcome.duration_seconds < 1.0


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_oracle_parity(scenario_id, tmp_path):
    outcome = run_scenario(scenario_id)
    oracle_result = _oracle_for(outcome, tmp_path)
    parity = check_parity(outcome, oracle_result)
    assert parity["parity"], "; ".join(parity["mismatches"])
    # The Oracle input must not carry a production verdict (§12.2).
    raw_input = json.loads(
        (tmp_path / f"{scenario_id}-oracle-input.json").read_text(encoding="utf-8")
    )
    assert "verdict" not in raw_input
    assert "diagnostics" not in raw_input


def test_healthy_zero_false_positives():
    for sid in HEALTHY:
        outcome = run_scenario(sid)
        assert outcome.production.verdict == "PASS_OBSERVED", sid
        assert outcome.production.critical_count == 0, sid


def test_known_failures_detected():
    for sid in KNOWN_FAILURES:
        outcome = run_scenario(sid)
        assert outcome.production.verdict == outcome.fixture["expected_verdict"], sid
        assert outcome.production.first_error is not None, sid


def test_both_warm_orders_real_and_no_mid_warm_reset():
    outcome = run_scenario("C11")
    names = [rec.name for rec in outcome.run.step_log]
    assert names[18:20] == ["HTMLWarmFirst", "MarkdownWarmSecond"]
    assert names[23:25] == ["MarkdownWarmFirst", "HTMLWarmSecond"]
    assert [rec.step for rec in outcome.run.step_log if rec.name == "ResetCache"] == [9, 13, 17, 22]
    # Both warm seconds are real requests with real origin evidence.
    assert outcome.run.observations[5].request_index == 6
    assert outcome.run.observations[7].request_index == 8


def test_cold_requests_have_dual_miss_bypass_proof():
    for sid in ("C01", "C03", "C05", "C17"):
        outcome = run_scenario(sid)
        for idx in (3, 4):
            raw = outcome.run.raw_observations[idx - 1]
            assert raw.verified_cache_state in ("MISS", "BYPASS"), (sid, idx)
            assert raw.cache_entry_count_before == 0, (sid, idx)
            assert raw.origin_counter_delta == 1, (sid, idx)
            assert raw.origin_event_present is True, (sid, idx)


def test_bleed_reproduces_3_of_3_with_dual_evidence():
    for attempt in range(1, 4):
        outcome = run_scenario("C11", namespace_prefix=f"s0-C11-test-{attempt}")
        assert outcome.production.verdict == "REPRESENTATION_BLEED"
        assert outcome.production.first_error == 6
        bleed = [
            d for d in outcome.diagnostics_projection
            if d["code"] == "REPRESENTATION_BLEED"
        ]
        assert len(bleed) == 2  # both warm orders bleed
        # Dual evidence on the bleed itself (§8.2): HIT header + no
        # origin hit + same entry as the first request.
        second = outcome.run.raw_observations[5]
        first = outcome.run.raw_observations[4]
        assert second.cache_status_header == "HIT"
        assert second.origin_counter_delta == 0
        assert second.cache_entry_id == first.cache_entry_id
        assert second.body_sha256 == first.body_sha256


def test_missing_vary_healthy_control():
    for sid in ("C03", "C04"):
        outcome = run_scenario(sid)
        assert outcome.production.verdict == "PASS_OBSERVED"
        codes = [d.code for d in outcome.production.diagnostics]
        assert codes == ["VARY_ACCEPT_ABSENT", "VARY_ACCEPT_ABSENT"]
        assert "REPRESENTATION_BLEED" not in codes


def test_insufficient_evidence_never_misjudged():
    for sid in INSUFFICIENT:
        outcome = run_scenario(sid)
        assert outcome.production.verdict == "INCONCLUSIVE", sid
        codes = [d.code for d in outcome.production.diagnostics]
        assert "REPRESENTATION_BLEED" not in codes, sid
        assert "ORIGIN_NEGOTIATION_ERROR" not in codes, sid


def test_canonical_hash_deterministic_on_reexecution():
    # ADR-003: three real re-runs, each on a FRESH pair with fresh
    # OS-assigned ports, must give one hash (§10.4). The old form ran
    # all three on one fixed pair and passed by construction; a
    # port-dependent hash fails this test. The full 100-run check is
    # scripts/run_s0.py; this test proves re-execution (not
    # recomputation) is deterministic.
    hashes = []
    for i in range(3):
        outcome = run_scenario("C01", namespace_prefix=f"s0-C01-det-{i+1}")
        assert outcome.production.verdict == "PASS_OBSERVED"
        hashes.append(outcome.report_hash)
    assert len(set(hashes)) == 1
    # Supplementary same-pair check: re-running on one fixed pair
    # must give the same hash as the fresh-pair runs.
    same_pair_hashes = []
    with make_pair("C01") as pair:
        for i in range(3):
            outcome = run_scenario(
                "C01", pair=pair, namespace_prefix=f"s0-C01-det-pair-{i+1}"
            )
            assert outcome.production.verdict == "PASS_OBSERVED"
            same_pair_hashes.append(outcome.report_hash)
    assert len(set(same_pair_hashes)) == 1
    assert same_pair_hashes[0] == hashes[0]


def test_mandatory_call_convention():
    src = (ROOT / "scripts" / "s0_harness.py").read_text(encoding="utf-8")
    assert "raw_observations=run.raw_observations" in src
    # The real call site is a single line carrying both the contract
    # arguments and raw_observations; the MANDATORY_CALL_SNIPPET doc
    # constant above it is split over several lines and must not match.
    call_lines = [
        ln for ln in src.splitlines()
        if "classify_run(contract, run.observations" in ln
        and "raw_observations=run.raw_observations" in ln
    ]
    assert call_lines, "no classify_run call site found"
    for ln in call_lines:
        assert "None" not in ln, f"None passed at call site: {ln}"
        assert "run.reset_evidence" in ln
        assert "run.observations" in ln


def test_oracle_sources_do_not_reference_production():
    oracle_src = ""
    for path in sorted((ROOT / "oracle" / "src").glob("*.ts")):
        oracle_src += path.read_text(encoding="utf-8")
    for forbidden in ("classify_run", "production.json", ".py", "accepttwin.classifier"):
        assert forbidden not in oracle_src, forbidden


def test_fixtures_cover_all_24_scenarios():
    assert list(SCENARIO_IDS) == [f"C{i:02d}" for i in range(1, 25)]
    for sid in SCENARIO_IDS:
        fx = load_scenario(sid)
        assert fx["expected_verdict"] in (
            "PASS_OBSERVED", "ORIGIN_NEGOTIATION_ERROR",
            "REPRESENTATION_BLEED", "CONTRACT_MISMATCH", "INCONCLUSIVE",
        )
        assert isinstance(fx["expected_diagnostics"], list)
