"""Extended Golden tests (P032 T008): E01-E24, independent Oracle.

Every test makes real HTTP requests over loopback through
``scripts/s0_harness.py`` (generalised by T008 to load the extended
fixtures; the same harness ``scripts/run_all_48.py`` uses for the
48-scenario gate). Expected verdicts, diagnostics and first-error
locations come from the frozen fixtures in ``fixtures/extended/`` --
never from the implementation under test.

Coverage (PROJECT_BOOK §11.3):
* 24/24 Golden match frozen expectations;
* 24/24 Oracle parity, verdict + diagnostics + first error (§12);
* healthy scenarios zero false positives (§7, §11.3);
* known failures detected (§8, §11.3);
* Vary lowercase field name (E01), multi-field Vary (E02),
  Vary:* (E03), no-store controls (E05/E06/E15/E16);
* revalidation limits (E07/E08), origin negotiation faults
  (E09–E11), cache-evidence faults (E17–E20), oversize body (E21),
  redirect limits (E12/E22), proxy response faults (E23/E24);
* stable bleed reproduction 3/3 for E13 (§8.2, §11.3);
* canonical report hash deterministic on re-execution (§7.8, §10.4);
* single scenario < 1s (§10.5);
* insufficient evidence never misjudged (§8.4, §8.8, §9.4).
"""

from __future__ import annotations

import http.client
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from s0_harness import (  # noqa: E402
    EXTENDED_FIXTURE_DIR,
    EXTENDED_SCENARIO_IDS,
    check_parity,
    load_scenario,
    make_pair,
    oracle_input_dict,
    run_oracle,
    run_scenario,
)
from accepttwin.origin_server import SyntheticOrigin  # noqa: E402

HEALTHY = ["E01", "E02", "E03", "E04", "E05", "E06", "E15", "E16"]
KNOWN_FAILURES = ["E09", "E10", "E11", "E13", "E14", "E23", "E24"]
INSUFFICIENT = ["E07", "E08", "E12", "E17", "E18", "E19", "E20", "E21", "E22"]


def _run(scenario_id: str, **kwargs):
    return run_scenario(
        scenario_id,
        fixture_dir=EXTENDED_FIXTURE_DIR,
        contract_prefix="ext",
        **kwargs,
    )


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


@pytest.mark.parametrize("scenario_id", EXTENDED_SCENARIO_IDS)
def test_golden_matches_frozen_expectation(scenario_id):
    outcome = _run(scenario_id, namespace_prefix=f"ext-{scenario_id}")
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


@pytest.mark.parametrize("scenario_id", EXTENDED_SCENARIO_IDS)
def test_oracle_parity(scenario_id, tmp_path):
    outcome = _run(scenario_id, namespace_prefix=f"ext-{scenario_id}")
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
        outcome = _run(sid, namespace_prefix=f"ext-{sid}")
        assert outcome.production.verdict == "PASS_OBSERVED", sid
        assert outcome.production.critical_count == 0, sid


def test_known_failures_detected():
    for sid in KNOWN_FAILURES:
        outcome = _run(sid, namespace_prefix=f"ext-{sid}")
        assert outcome.production.verdict == outcome.fixture["expected_verdict"], sid
        assert outcome.production.first_error is not None, sid


def test_insufficient_evidence_never_misjudged():
    for sid in INSUFFICIENT:
        outcome = _run(sid, namespace_prefix=f"ext-{sid}")
        assert outcome.production.verdict == "INCONCLUSIVE", sid
        codes = [d.code for d in outcome.production.diagnostics]
        assert "REPRESENTATION_BLEED" not in codes, sid
        assert "ORIGIN_NEGOTIATION_ERROR" not in codes, sid


def test_e01_vary_field_name_is_lowercase_on_the_wire():
    # The runner lowercases header names in evidence (HTTP field
    # names are case-insensitive), so the lowercase wire fact is
    # pinned here with a raw request, not from the evidence file.
    origin = SyntheticOrigin(port=0, scenario="vary_lowercase")
    origin.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", origin.port, timeout=5)
        try:
            conn.request("GET", "/doc", headers={"Accept": "text/html"})
            resp = conn.getresponse()
            resp.read()
            names = [name for name, _ in resp.getheaders()]
        finally:
            conn.close()
    finally:
        origin.stop()
    assert "vary" in names
    assert "Vary" not in names
    # ...while the end-to-end run still passes (E01 golden above).
    outcome = _run("E01", namespace_prefix="ext-E01-wire")
    assert outcome.production.verdict == "PASS_OBSERVED"


def test_e02_vary_multi_field_is_observed():
    outcome = _run("E02", namespace_prefix="ext-E02-vary")
    assert outcome.production.verdict == "PASS_OBSERVED"
    for raw in outcome.run.raw_observations[:2]:
        assert raw.response_headers.get("vary") == "Accept, Accept-Encoding"


def test_e03_vary_star_never_stores_and_bypasses():
    outcome = _run("E03", namespace_prefix="ext-E03-vary")
    assert outcome.production.verdict == "PASS_OBSERVED"
    assert outcome.production.diagnostics == ()
    for raw in outcome.run.raw_observations:
        assert raw.response_headers.get("vary") == "*"
    for raw in outcome.run.raw_observations[2:]:
        assert raw.verified_cache_state == "BYPASS"
        assert raw.cache_entry_count_after == 0
        assert raw.cache_entry_count_before == 0


def test_e07_e08_revalidation_limit_codes():
    for sid in ("E07", "E08"):
        outcome = _run(sid, namespace_prefix=f"ext-{sid}-limit")
        assert outcome.production.verdict == "INCONCLUSIVE", sid
        limits = [
            d for d in outcome.production.diagnostics
            if d.code == "INCONCLUSIVE_LIMIT"
        ]
        assert len(limits) == 8, sid
        assert {d.evidence["limit_code"] for d in limits} == {
            "revalidation_required"
        }, sid
        directive = "max-age=0" if sid == "E07" else "no-cache"
        assert outcome.run.raw_observations[0].response_headers.get(
            "cache-control"
        ) == directive, sid


def test_e12_e22_redirect_limit_codes_and_targets():
    for sid, target in (
        ("E12", None),  # loopback origin URL (port varies per run)
        ("E22", "http://example.com/doc"),
    ):
        outcome = _run(sid, namespace_prefix=f"ext-{sid}-redirect")
        assert outcome.production.verdict == "INCONCLUSIVE", sid
        limits = [
            d for d in outcome.production.diagnostics
            if d.code == "INCONCLUSIVE_LIMIT"
        ]
        assert len(limits) == 6, sid
        assert {d.evidence["limit_code"] for d in limits} == {"redirect"}, sid
        assert {d.request_index for d in limits} == {3, 4, 5, 6, 7, 8}, sid
        for raw in outcome.run.raw_observations[2:]:
            assert raw.response_status == 301, sid
            location = raw.response_headers.get("location")
            assert location is not None, sid
            if target is None:
                assert location.startswith("http://127.0.0.1:"), sid
                assert location.endswith("/doc"), sid
            else:
                assert location == target, sid
        # The redirect is never followed: the origin saw only the
        # two direct baselines.
        assert outcome.run.origin_events and all(
            ev.index <= 2 for ev in outcome.run.origin_events
        ), sid


def test_e20_miss_header_conflicts_with_counter():
    outcome = _run("E20", namespace_prefix="ext-E20-conflict")
    assert outcome.production.verdict == "INCONCLUSIVE"
    assert outcome.production.first_error == 6
    second = outcome.run.raw_observations[5]
    assert second.cache_status_header == "MISS"
    assert second.origin_counter_delta == 0
    assert second.verified_cache_state == "CACHE_STATE_UNKNOWN"
    # The replayed body is the genuine Markdown body: no Sentinel
    # or contract diagnostic may fire alongside the conflict.
    assert second.sentinel_match is True
    assert second.response_content_type == "text/markdown; charset=utf-8"


def test_e21_oversize_bodies_are_measured_not_guessed():
    outcome = _run("E21", namespace_prefix="ext-E21-size")
    assert outcome.production.verdict == "INCONCLUSIVE"
    for raw in outcome.run.raw_observations[2:]:
        assert raw.body_size > 1048576
        assert raw.sentinel_match is True
    for raw in outcome.run.raw_observations[:2]:
        assert raw.body_size <= 1048576


def test_e24_warm_sentinel_corruption_is_not_a_bleed():
    outcome = _run("E24", namespace_prefix="ext-E24-sentinel")
    assert outcome.production.verdict == "CONTRACT_MISMATCH"
    assert outcome.production.first_error == 6
    for raw in (
        outcome.run.raw_observations[5],
        outcome.run.raw_observations[7],
    ):
        assert raw.sentinel_match is False
        assert raw.verified_cache_state == "MISS"
    # Corrupted bodies differ from the first requests' bodies, so
    # the bleed chain (equal body hash) cannot fire.
    assert outcome.run.raw_observations[5].body_sha256 != (
        outcome.run.raw_observations[4].body_sha256
    )
    assert outcome.run.raw_observations[7].body_sha256 != (
        outcome.run.raw_observations[6].body_sha256
    )


def test_bleed_reproduces_3_of_3_with_dual_evidence():
    for attempt in range(1, 4):
        outcome = _run("E13", namespace_prefix=f"ext-E13-test-{attempt}")
        assert outcome.production.verdict == "REPRESENTATION_BLEED"
        assert outcome.production.first_error == 6
        bleed = [
            d for d in outcome.diagnostics_projection
            if d["code"] == "REPRESENTATION_BLEED"
        ]
        assert len(bleed) == 2  # both warm orders bleed
        second = outcome.run.raw_observations[5]
        first = outcome.run.raw_observations[4]
        assert second.cache_status_header == "HIT"
        assert second.origin_counter_delta == 0
        assert second.cache_entry_id == first.cache_entry_id
        assert second.body_sha256 == first.body_sha256


def test_canonical_hash_deterministic_on_reexecution():
    # ADR-003: three real re-runs, each on a FRESH pair with fresh
    # OS-assigned ports, must give one hash (§10.4).
    hashes = []
    for i in range(3):
        outcome = _run("E01", namespace_prefix=f"ext-E01-det-{i+1}")
        assert outcome.production.verdict == "PASS_OBSERVED"
        hashes.append(outcome.report_hash)
    assert len(set(hashes)) == 1
    # Supplementary same-pair check: re-running on one fixed pair
    # must give the same hash as the fresh-pair runs.
    same_pair_hashes = []
    with make_pair(
        "E01", EXTENDED_FIXTURE_DIR, "ext"
    ) as pair:
        for i in range(3):
            outcome = run_scenario(
                "E01",
                pair=pair,
                fixture_dir=EXTENDED_FIXTURE_DIR,
                contract_prefix="ext",
                namespace_prefix=f"ext-E01-det-pair-{i+1}",
            )
            assert outcome.production.verdict == "PASS_OBSERVED"
            same_pair_hashes.append(outcome.report_hash)
    assert len(set(same_pair_hashes)) == 1
    assert same_pair_hashes[0] == hashes[0]


def test_fixtures_cover_all_24_scenarios():
    assert list(EXTENDED_SCENARIO_IDS) == [f"E{i:02d}" for i in range(1, 25)]
    for sid in EXTENDED_SCENARIO_IDS:
        fx = load_scenario(sid, EXTENDED_FIXTURE_DIR)
        assert fx["expected_verdict"] in (
            "PASS_OBSERVED", "ORIGIN_NEGOTIATION_ERROR",
            "REPRESENTATION_BLEED", "CONTRACT_MISMATCH", "INCONCLUSIVE",
        )
        assert isinstance(fx["expected_diagnostics"], list)
        assert fx["spec"] == "PROJECT_BOOK.md §11.3"
