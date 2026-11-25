"""Unit tests for the production classifier (P032 T006).

Covers IMPLEMENTATION_PLAN T006 acceptance criteria and PROJECT_BOOK
§6.3 (first-error location), §8 (diagnostics), §9 (five verdicts
and their priority), §7.11 I-11 (Vary never decides a verdict alone)
and §7.12 I-12 (no body text):

* all five verdicts are reachable;
* every diagnostic family is exercised through the classifier;
* origin errors are never misreported as cache bleed;
* a healthy cache without Vary is never misreported as a bleed;
* a HIT/MISS evidence conflict is never misreported as a bleed;
* first-error positions are exact, and a later more severe error
  never rewrites the history;
* a lone 200 / a lone Sentinel match never yields PASS or HIT.

Most cases feed crafted :class:`RequestObservation` objects to
:func:`accepttwin.classifier.classify_run` (pure logic, no I/O).
Two cases at the end run the real T005 runner over loopback and
classify the genuine observations, proving the classifier agrees
with live evidence.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import socket
from pathlib import Path

import pytest

from accepttwin.cache_proxy import ResetEvidence
from accepttwin.classifier import ClassificationResult, classify_run
from accepttwin.contract import Contract, parse_contract
from accepttwin.evidence import RawObservation, RequestObservation
from accepttwin.experiment_runner import run_experiments
from accepttwin.origin_server import OriginEvent

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"

HTML_CT = "text/html; charset=utf-8"
MD_CT = "text/markdown; charset=utf-8"
HTML_BODY = "h" * 64
MD_BODY = "m" * 64
KEY = "k" * 64


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_contract(*, mode="variant_by_accept", vary_accept="advisory"):
    """A valid contract; ports are placeholders — the classifier
    never performs I/O, so they only need to pass the loopback guard."""
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if mode == "no_store":
        data["cache_behavior"] = {
            "mode": "no_store",
            "vary_accept": "not_required",
            "max_age_seconds": None,
        }
    else:
        data["cache_behavior"] = {
            "mode": "variant_by_accept",
            "vary_accept": vary_accept,
            "max_age_seconds": 60,
        }
    return parse_contract(data)


def obs(
    index,
    rep,
    *,
    status=200,
    content_type=None,
    sentinel=True,
    cache=None,
    key=KEY,
    entry=None,
    before=0,
    after=0,
    body=None,
):
    """One crafted observation. ``before``/``after`` are cumulative
    origin counters; the delta is derived from them."""
    if content_type is None:
        content_type = HTML_CT if rep == "html" else MD_CT
    if body is None:
        body = HTML_BODY if rep == "html" else MD_BODY
    if entry is None and cache in ("MISS", "HIT"):
        entry = f"entry-{index:03d}"
    experiment = {
        1: "ORIGIN_HTML",
        2: "ORIGIN_MARKDOWN",
        3: "HTML_COLD",
        4: "MARKDOWN_COLD",
        5: "HTML_TO_MARKDOWN",
        6: "HTML_TO_MARKDOWN",
        7: "MARKDOWN_TO_HTML",
        8: "MARKDOWN_TO_HTML",
    }[index]
    return RequestObservation(
        request_index=index,
        experiment_id=experiment,
        requested_representation=rep,
        response_status=status,
        response_content_type=content_type,
        body_sha256=body,
        sentinel_match=sentinel,
        cache_status=cache,
        cache_key_sha256=key if cache in ("MISS", "HIT") else None,
        cache_entry_id=entry,
        origin_counter_before=before,
        origin_counter_after=after,
        origin_counter_delta=after - before,
    )


def healthy_observations(*, cache_mode="variant_by_accept"):
    """The eight observations of a fully healthy run: baselines
    correct, cold requests MISS (or BYPASS under no_store), both
    warm orders MISS (or BYPASS). Counters increase by exactly 1
    per origin visit."""
    state = "BYPASS" if cache_mode == "no_store" else "MISS"
    return [
        obs(1, "html", before=0, after=1),
        obs(2, "markdown", before=1, after=2),
        obs(3, "html", cache=state, before=2, after=3),
        obs(4, "markdown", cache=state, before=3, after=4),
        obs(5, "html", cache=state, before=4, after=5),
        obs(6, "markdown", cache=state, before=5, after=6),
        obs(7, "markdown", cache=state, before=6, after=7),
        obs(8, "html", cache=state, before=7, after=8),
    ]


def resets_ok():
    return [
        ResetEvidence(
            namespace=f"t006-{name}",
            success=True,
            entries_before=1,
            entries_after=0,
            entries_removed=1,
        )
        for name in (
            "html-cold",
            "markdown-cold",
            "html-to-markdown",
            "markdown-to-html",
        )
    ]


def classify(observations, *, contract=None, events=None, resets=None, **kwargs):
    return classify_run(
        contract if contract is not None else build_contract(),
        observations,
        events,
        resets if resets is not None else resets_ok(),
        **kwargs,
    )


def raw(
    index,
    rep,
    *,
    status=200,
    content_type=None,
    sentinel=True,
    cache_header=None,
    body_size=128,
    transport_error=None,
    headers=None,
    event_present=True,
):
    """A RawObservation for the same request, carrying the detail
    RequestObservation cannot: raw cache header, body size,
    transport error, Vary header, origin-event presence."""
    if content_type is None:
        content_type = HTML_CT if rep == "html" else MD_CT
    return RawObservation(
        request_index=index,
        experiment_id="HTML_TO_MARKDOWN" if index in (5, 6) else "HTML_COLD",
        requested_representation=rep,
        method="GET",
        url="http://127.0.0.1:18765/doc",
        accept="text/html" if rep == "html" else "text/markdown",
        response_status=status,
        response_content_type=content_type,
        body_sha256=HTML_BODY if rep == "html" else MD_BODY,
        body_size=body_size,
        sentinel_match=sentinel,
        sentinel_sha256=hashlib.sha256(
            b"AT_HTML_SENTINEL_001" if rep == "html" else b"AT_MARKDOWN_SENTINEL_001"
        ).hexdigest(),
        response_headers=dict(headers) if headers else {},
        cache_status_header=cache_header,
        origin_event_present=event_present,
        transport_error=transport_error,
    )


# ---------------------------------------------------------------------------
# §9.5 PASS_OBSERVED
# ---------------------------------------------------------------------------


def test_healthy_run_passes_with_no_diagnostics():
    result = classify(healthy_observations())
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()
    assert result.first_error is None
    assert result.first_error_experiment_id is None
    assert result.critical_count == 0
    assert result.warning_count == 0


def test_healthy_run_passes_when_observations_unsorted():
    observations = healthy_observations()
    result = classify(list(reversed(observations)))
    assert result.verdict == "PASS_OBSERVED"
    assert result.first_error is None


def test_no_store_bypass_run_passes():
    result = classify(
        healthy_observations(cache_mode="no_store"),
        contract=build_contract(mode="no_store"),
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()


def test_result_as_dict_has_no_body_text():
    result = classify(healthy_observations())
    data = result.as_dict()
    assert data["verdict"] == "PASS_OBSERVED"
    assert data["first_error"] is None
    assert "body_text" not in json.dumps(data)


def test_classification_result_rejects_unknown_verdict():
    with pytest.raises(ValueError, match="unknown verdict"):
        ClassificationResult(verdict="MAYBE")


# ---------------------------------------------------------------------------
# §9.1 ORIGIN_NEGOTIATION_ERROR (incl. "never misreported as bleed")
# ---------------------------------------------------------------------------


def test_origin_html_404():
    observations = healthy_observations()
    observations[0] = obs(1, "html", status=404, sentinel=False, before=0, after=1)
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    assert "ORIGIN_NEGOTIATION_ERROR" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 1
    assert result.first_error_experiment_id == "ORIGIN_HTML"


def test_origin_markdown_404():
    observations = healthy_observations()
    observations[1] = obs(
        2, "markdown", status=404, sentinel=False, before=1, after=2
    )
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    assert result.first_error == 2
    assert result.first_error_experiment_id == "ORIGIN_MARKDOWN"


def test_origin_markdown_wrong_content_type():
    observations = healthy_observations()
    observations[1] = obs(
        2, "markdown", content_type="text/html", before=1, after=2
    )
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    assert result.first_error == 2


def test_origin_markdown_sentinel_missing():
    observations = healthy_observations()
    observations[1] = obs(2, "markdown", sentinel=False, before=1, after=2)
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    # The missing Sentinel is kept as secondary evidence (§9.6).
    assert "SENTINEL_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 2


def test_origin_error_beats_later_cache_problem():
    # Baseline 404 at 001 plus a wrong-Content-Type cold request at
    # 003: the verdict is the origin error and first_error stays 1 —
    # the later problem never rewrites the history (§6.3, §9.6).
    observations = healthy_observations()
    observations[0] = obs(1, "html", status=404, sentinel=False, before=0, after=1)
    observations[2] = obs(
        3, "html", status=500, cache="MISS", before=2, after=3
    )
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    assert result.first_error == 1


def test_origin_error_not_bleed_even_with_bleed_shaped_warm_pair():
    # Baseline broken AND a warm pair shaped exactly like a bleed:
    # §8.2 condition 1 forbids confirming the bleed, and the verdict
    # stays the origin error.
    observations = healthy_observations()
    observations[0] = obs(1, "html", status=404, sentinel=False, before=0, after=1)
    observations[4] = obs(5, "html", cache="MISS", before=4, after=5)
    observations[5] = obs(
        6,
        "markdown",
        content_type=HTML_CT,
        sentinel=False,
        cache="HIT",
        entry="entry-005",
        before=5,
        after=5,
        body=HTML_BODY,
    )
    result = classify(observations)
    assert result.verdict == "ORIGIN_NEGOTIATION_ERROR"
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 1


# ---------------------------------------------------------------------------
# §9.2 REPRESENTATION_BLEED
# ---------------------------------------------------------------------------


def bleed_observations(*, second_index=6):
    """Healthy run with one warm pair turned into a proven bleed:
    HTML first (MISS, entry-005), Markdown second (verified HIT of
    the same entry, HTML body, HTML Content-Type, no MD Sentinel)."""
    observations = healthy_observations()
    if second_index == 6:
        observations[4] = obs(5, "html", cache="MISS", before=4, after=5)
        observations[5] = obs(
            6,
            "markdown",
            content_type=HTML_CT,
            sentinel=False,
            cache="HIT",
            entry="entry-005",
            before=5,
            after=5,
            body=HTML_BODY,
        )
    else:
        observations[6] = obs(7, "markdown", cache="MISS", before=6, after=7)
        observations[7] = obs(
            8,
            "html",
            content_type=MD_CT,
            sentinel=False,
            cache="HIT",
            entry="entry-007",
            before=7,
            after=7,
            body=MD_BODY,
        )
    return observations


def test_bleed_html_to_markdown():
    result = classify(bleed_observations(second_index=6))
    assert result.verdict == "REPRESENTATION_BLEED"
    assert "REPRESENTATION_BLEED" in result.diagnostic_codes()
    assert "SENTINEL_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 6
    assert result.first_error_experiment_id == "HTML_TO_MARKDOWN"
    assert result.critical_count >= 1


def test_bleed_markdown_to_html():
    result = classify(bleed_observations(second_index=8))
    assert result.verdict == "REPRESENTATION_BLEED"
    assert result.first_error == 8
    assert result.first_error_experiment_id == "MARKDOWN_TO_HTML"


def test_bleed_has_no_policy_mismatch():
    # P2-4: a proven bleed is a HIT reusing a stored entry — the
    # policy check must not also fire. CACHE_POLICY_MISMATCH has no
    # business in a bleed run under either warm order.
    for second_index in (6, 8):
        result = classify(bleed_observations(second_index=second_index))
        assert result.verdict == "REPRESENTATION_BLEED"
        assert "CACHE_POLICY_MISMATCH" not in result.diagnostic_codes()


def test_bleed_not_when_second_revisits_origin():
    # HIT claimed but the counter moved: a conflict, never a bleed.
    # The wrong representation itself is still directly observed, so
    # the verdict is CONTRACT_MISMATCH (§9.6 step 4, before the
    # evidence-insufficient step 5) — but never REPRESENTATION_BLEED.
    observations = bleed_observations(second_index=6)
    observations[5] = obs(
        6,
        "markdown",
        content_type=HTML_CT,
        sentinel=False,
        cache="HIT",
        entry="entry-005",
        before=5,
        after=6,
        body=HTML_BODY,
    )
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert "CACHE_EVIDENCE_CONFLICT" in result.diagnostic_codes()
    assert result.first_error == 6


def test_bleed_not_when_entry_differs():
    observations = bleed_observations(second_index=6)
    observations[5] = obs(
        6,
        "markdown",
        content_type=HTML_CT,
        sentinel=False,
        cache="HIT",
        entry="entry-other",
        before=5,
        after=5,
        body=HTML_BODY,
    )
    result = classify(observations)
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    # The wrong representation is still a confirmed contract error.
    assert result.verdict == "CONTRACT_MISMATCH"
    assert result.first_error == 6


def test_bleed_not_when_first_request_was_bypass():
    observations = bleed_observations(second_index=6)
    observations[4] = obs(5, "html", cache="BYPASS", before=4, after=5)
    result = classify(observations)
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.verdict == "CONTRACT_MISMATCH"


def test_bleed_not_when_second_is_miss():
    # Same wrong body, but the second request went to the origin
    # (MISS): the origin served the wrong representation — that is
    # a contract mismatch, not a cache bleed.
    observations = bleed_observations(second_index=6)
    observations[5] = obs(
        6,
        "markdown",
        content_type=HTML_CT,
        sentinel=False,
        cache="MISS",
        before=5,
        after=6,
        body=HTML_BODY,
    )
    result = classify(observations)
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.verdict == "CONTRACT_MISMATCH"


def test_first_error_stays_earliest_despite_later_bleed():
    # A contract error at 003 plus a proven bleed at 006: the
    # verdict follows the §9.6 priority (bleed wins over a plain
    # contract error) but first_error stays 3 — severity never
    # re-orders history (§6.3).
    observations = bleed_observations(second_index=6)
    observations[2] = obs(3, "html", status=500, cache="MISS", before=2, after=3)
    result = classify(observations)
    assert result.verdict == "REPRESENTATION_BLEED"
    assert result.first_error == 3
    assert result.first_error_experiment_id == "HTML_COLD"


# ---------------------------------------------------------------------------
# §9.3 CONTRACT_MISMATCH
# ---------------------------------------------------------------------------


def test_contract_mismatch_proxy_wrong_content_type():
    observations = healthy_observations()
    observations[5] = obs(
        6, "markdown", content_type=HTML_CT, cache="MISS", before=5, after=6
    )
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CONTRACT_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 6


def test_contract_mismatch_proxy_status_error():
    observations = healthy_observations()
    observations[2] = obs(3, "html", status=500, cache="MISS", before=2, after=3)
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert result.first_error == 3


def test_contract_mismatch_warm_sentinel_error():
    # E24 shape: origin fine, warm response Sentinel wrong, cache
    # state fine — a contract mismatch, not a bleed.
    observations = healthy_observations()
    observations[5] = obs(
        6, "markdown", sentinel=False, cache="MISS", before=5, after=6
    )
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "SENTINEL_MISMATCH" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 6


def test_contract_mismatch_no_store_ignored():
    # C19 shape: no_store contract, but the proxy stored the response.
    observations = healthy_observations(cache_mode="no_store")
    observations[2] = obs(3, "html", cache="MISS", before=2, after=3)
    result = classify(observations, contract=build_contract(mode="no_store"))
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CACHE_POLICY_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 3


def test_contract_mismatch_no_store_hit_reuses():
    observations = healthy_observations(cache_mode="no_store")
    observations[5] = obs(
        6,
        "markdown",
        cache="HIT",
        entry="entry-005",
        before=5,
        after=5,
        body=MD_BODY,
    )
    result = classify(observations, contract=build_contract(mode="no_store"))
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CACHE_POLICY_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 6


def test_policy_mismatch_variant_cold_bypass():
    # P1-1 (§8.9 variant leg, §5.4/§6.1): a confirmed BYPASS under
    # variant_by_accept — the cache never stored anything, so
    # isolation was never exercised. Must be CONTRACT_MISMATCH via
    # CACHE_POLICY_MISMATCH, never a silent PASS.
    observations = healthy_observations()
    observations[2] = obs(3, "html", cache="BYPASS", before=2, after=3)
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CACHE_POLICY_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 3
    diag = next(
        d for d in result.diagnostics if d.code == "CACHE_POLICY_MISMATCH"
    )
    assert diag.evidence["declared_cache_mode"] == "variant_by_accept"
    assert diag.evidence["observed_cache_status"] == "BYPASS"


def test_policy_mismatch_variant_warm_bypass():
    # P1-1, warm leg: the second warm request BYPASSes under a
    # variant contract — same policy violation, same verdict.
    observations = healthy_observations()
    observations[5] = obs(6, "markdown", cache="BYPASS", before=5, after=6)
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CACHE_POLICY_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 6


def test_policy_mismatch_variant_bypass_not_when_state_unconfirmed():
    # An *unconfirmed* BYPASS is an evidence problem (§8.4), not a
    # proven policy violation: INCONCLUSIVE, no CACHE_POLICY_MISMATCH.
    observations = healthy_observations()
    observations[2] = obs(
        3, "html", cache="CACHE_STATE_UNKNOWN", key=None, entry=None,
        before=2, after=3,
    )
    result = classify(observations)
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_POLICY_MISMATCH" not in result.diagnostic_codes()
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()


def test_contract_mismatch_unexpected_cold_hit():
    # A HIT on a cold request after a confirmed reset contradicts
    # the cold-cache premise (§5.4).
    observations = healthy_observations()
    observations[2] = obs(
        3, "html", cache="HIT", entry="entry-stale", before=2, after=2
    )
    result = classify(observations)
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CONTRACT_MISMATCH" in result.diagnostic_codes()
    assert result.first_error == 3


# ---------------------------------------------------------------------------
# §9.4 INCONCLUSIVE — evidence insufficient, never a proven bleed
# ---------------------------------------------------------------------------


def test_inconclusive_when_cache_state_unknown():
    observations = healthy_observations()
    observations[2] = obs(
        3, "html", cache="CACHE_STATE_UNKNOWN", key=None, entry=None,
        before=2, after=3,
    )
    result = classify(observations)
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 3


def test_inconclusive_when_header_hit_conflicts_with_counter():
    # §8.8 / C22 shape: the representation itself is correct, but
    # the proxy says HIT while the origin counter moved +1 — the two
    # cache legs contradict each other, so the verdict is
    # INCONCLUSIVE, never a bleed (and no contract error exists to
    # outrank it under §9.6).
    observations = healthy_observations()
    observations[5] = obs(
        6,
        "markdown",
        cache="CACHE_STATE_UNKNOWN",
        key=None,
        entry=None,
        before=5,
        after=6,
    )
    raws = [
        raw(6, "markdown", cache_header="HIT", event_present=True)
    ]
    result = classify(observations, raw_observations=raws)
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_EVIDENCE_CONFLICT" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()


def test_inconclusive_when_cache_header_missing():
    observations = healthy_observations()
    observations[2] = obs(
        3, "html", cache="CACHE_STATE_UNKNOWN", key=None, entry=None,
        before=2, after=3,
    )
    raws = [raw(3, "html", cache_header=None, event_present=True)]
    result = classify(observations, raw_observations=raws)
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()
    assert "CACHE_EVIDENCE_CONFLICT" not in result.diagnostic_codes()


def test_inconclusive_when_reset_failed():
    failed = resets_ok()
    failed[0] = ResetEvidence(
        namespace="t006-html-cold",
        success=False,
        entries_before=2,
        entries_after=2,
        entries_removed=0,
    )
    result = classify(healthy_observations(), resets=failed)
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()
    # The failure is run-level (no request violated the contract),
    # so there is no first error to point at.
    assert result.first_error is None


def test_inconclusive_when_no_reset_recorded():
    result = classify(healthy_observations(), resets=[])
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()


def test_inconclusive_when_observations_incomplete():
    result = classify(healthy_observations()[:7])
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()
    assert result.first_error is None


def test_inconclusive_when_contract_invalid():
    contract = build_contract()
    bad = dataclasses.replace(contract, url="http://example.com/doc")
    result = classify(healthy_observations(), contract=bad)
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()


def test_inconclusive_on_redirect():
    observations = healthy_observations()
    observations[5] = obs(
        6, "markdown", status=302, content_type="text/html",
        sentinel=False, cache="MISS", before=5, after=6,
    )
    result = classify(observations)
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()
    # A redirect is out of scope, not a contract mismatch or a bleed.
    assert "CONTRACT_MISMATCH" not in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 6


def test_inconclusive_on_oversize_body():
    observations = healthy_observations()
    raws = [raw(3, "html", body_size=2 * 1024 * 1024)]
    result = classify(observations, raw_observations=raws)
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()
    assert result.first_error == 3


def test_inconclusive_on_transport_error():
    observations = healthy_observations()
    observations[2] = obs(3, "html", status=0, cache=None, before=2, after=2)
    raws = [raw(3, "html", status=0, transport_error="ConnectionRefusedError")]
    result = classify(observations, raw_observations=raws)
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()


# ---------------------------------------------------------------------------
# "Only" rules — the negative guards of the task card
# ---------------------------------------------------------------------------


def test_vary_absent_alone_never_bleeds():
    # C03/C04 shape: no Vary anywhere, manual Accept keys, both
    # representations independently MISS — healthy, with only the
    # advisory WARNING kept.
    result = classify(
        healthy_observations(),
        vary_accept_present={1: False, 2: False},
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostic_codes() == (
        "VARY_ACCEPT_ABSENT",
        "VARY_ACCEPT_ABSENT",
    )
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    # An advisory WARNING is not a contract violation: no first error.
    assert result.first_error is None


def test_vary_present_no_warning():
    result = classify(
        healthy_observations(),
        vary_accept_present={1: True, 2: True},
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()


def test_vary_required_missing_is_contract_mismatch_not_bleed():
    result = classify(
        healthy_observations(),
        contract=build_contract(vary_accept="required"),
        vary_accept_present={1: False, 2: False},
    )
    assert result.verdict == "CONTRACT_MISMATCH"
    assert "CONTRACT_MISMATCH" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.first_error == 1


def test_vary_required_unknown_is_inconclusive_not_pass():
    # P2-1 fail-closed (§5.2, §9.6 step 5): vary_accept == "required"
    # but whether Vary is present is unknown — neither
    # raw_observations nor vary_accept_present was supplied — so the
    # required violation can neither be confirmed nor ruled out.
    # The run is INCONCLUSIVE, never a silent PASS.
    result = classify(
        healthy_observations(),
        contract=build_contract(vary_accept="required"),
    )
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()
    diag = next(
        d for d in result.diagnostics if d.code == "INCONCLUSIVE_LIMIT"
    )
    assert diag.evidence["limit_code"] == "vary_accept_unknown"
    assert result.first_error == 1


def test_vary_required_unknown_for_one_baseline_is_inconclusive():
    # Only one baseline's Vary is known (present): the other is
    # still unknown, so the run still fails closed.
    result = classify(
        healthy_observations(),
        contract=build_contract(vary_accept="required"),
        vary_accept_present={1: True},
    )
    assert result.verdict == "INCONCLUSIVE"
    assert "INCONCLUSIVE_LIMIT" in result.diagnostic_codes()


def test_vary_required_known_present_passes():
    # Control: when the raw records show Vary: Accept on both
    # baselines, the required contract is satisfied and the run
    # passes — the fail-closed rule only fires on *unknown* Vary.
    raws = [
        raw(1, "html", headers={"Vary": "Accept"}),
        raw(2, "markdown", headers={"Vary": "Accept"}),
    ]
    result = classify(
        healthy_observations(),
        contract=build_contract(vary_accept="required"),
        raw_observations=raws,
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()


def test_vary_absent_irrelevant_under_no_store():
    result = classify(
        healthy_observations(cache_mode="no_store"),
        contract=build_contract(mode="no_store"),
        vary_accept_present={1: False, 2: False},
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()


def test_200_alone_never_passes():
    # Every status is 200 and every Sentinel matches, but the cache
    # evidence is missing: INCONCLUSIVE, never PASS.
    observations = healthy_observations()
    observations[2] = obs(
        3, "html", cache="CACHE_STATE_UNKNOWN", key=None, entry=None,
        before=2, after=3,
    )
    result = classify(observations)
    assert result.verdict == "INCONCLUSIVE"
    assert result.verdict != "PASS_OBSERVED"


def test_sentinel_alone_never_proves_hit():
    # The warm second response matches its Sentinel, but its cache
    # state is unknown: no HIT is claimed and the run is
    # INCONCLUSIVE, not a pass and not a bleed.
    observations = healthy_observations()
    observations[5] = obs(
        6, "markdown", cache="CACHE_STATE_UNKNOWN", key=None, entry=None,
        before=5, after=6,
    )
    result = classify(observations)
    assert result.verdict == "INCONCLUSIVE"
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()


def test_insufficient_evidence_never_becomes_proven_bleed():
    # A warm second with the wrong body but UNKNOWN cache state is
    # suspicious, not proven: CONTRACT_MISMATCH via the observed
    # Content-Type/Sentinel, never REPRESENTATION_BLEED.
    observations = healthy_observations()
    observations[5] = obs(
        6,
        "markdown",
        content_type=HTML_CT,
        sentinel=False,
        cache="CACHE_STATE_UNKNOWN",
        key=None,
        entry=None,
        before=5,
        after=6,
        body=HTML_BODY,
    )
    result = classify(observations)
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()
    assert result.verdict == "CONTRACT_MISMATCH"


# ---------------------------------------------------------------------------
# Origin-event cross-check
# ---------------------------------------------------------------------------


def matching_events(observations):
    """Origin events that genuinely match each observation: index
    equals the counter after the request, Accept and status match."""
    events = []
    for o in observations:
        events.append(
            OriginEvent(
                index=o.origin_counter_after,
                method="GET",
                path="/doc",
                accept="text/html"
                if o.requested_representation == "html"
                else "text/markdown",
                status=o.response_status,
                timestamp=0.0,
                received_at="2026-11-24T00:00:00Z",
            )
        )
    return events


def test_origin_events_matching_keeps_healthy_pass():
    observations = healthy_observations()
    result = classify(observations, events=matching_events(observations))
    assert result.verdict == "PASS_OBSERVED"


def test_origin_events_missing_downgrades_to_unknown():
    # The caller supplied an event log, but it holds no event for
    # the proxied requests: the behaviour leg is missing.
    result = classify(healthy_observations(), events=[])
    assert result.verdict == "INCONCLUSIVE"
    assert "CACHE_STATE_UNKNOWN" in result.diagnostic_codes()
    assert "REPRESENTATION_BLEED" not in result.diagnostic_codes()


def test_none_means_skip_cross_check_not_confirmed():
    # P2-2, route B (ADR-002): origin_events=None / reset_evidence
    # =None mean "the caller declares this cross-check is not
    # performed" — the check is skipped, never treated as confirmed.
    # This meaning is reserved for unit tests; a production caller
    # (T007) must pass the real tuples and never pass None. The
    # contrast is [] (checked, found nothing) → INCONCLUSIVE, see
    # test_origin_events_missing_downgrades_to_unknown and
    # test_inconclusive_when_no_reset_recorded.
    result = classify(healthy_observations(), events=None, resets=None)
    assert result.verdict == "PASS_OBSERVED"
    assert result.diagnostics == ()


# ---------------------------------------------------------------------------
# Deterministic diagnostic ordering
# ---------------------------------------------------------------------------


def test_diagnostics_sorted_by_request_not_severity():
    result = classify(bleed_observations(second_index=6))
    indices = [
        d.request_index for d in result.diagnostics
        if d.request_index is not None
    ]
    assert indices == sorted(indices)
    # The bleed (CRITICAL, request 6) does not jump ahead of any
    # earlier diagnostic.
    assert result.diagnostics[0].request_index == 6


def test_repeat_classification_is_deterministic():
    first = classify(bleed_observations(second_index=6))
    second = classify(bleed_observations(second_index=6))
    assert first.as_dict() == second.as_dict()


# ---------------------------------------------------------------------------
# Live evidence: classify genuine T005 runs over loopback
# ---------------------------------------------------------------------------


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _live_contract():
    proxy_port = _free_port()
    origin_port = _free_port()
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["url"] = f"http://127.0.0.1:{proxy_port}/doc"
    data["origin_url"] = f"http://127.0.0.1:{origin_port}/doc"
    return parse_contract(data)


def test_live_healthy_run_classifies_pass():
    contract = _live_contract()
    run = run_experiments(
        contract, scenario="healthy", proxy_mode="respect_vary",
        namespace_prefix="t006-live",
    )
    result = classify_run(
        contract,
        run.observations,
        run.origin_events,
        run.reset_evidence,
        raw_observations=run.raw_observations,
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.first_error is None


def test_live_bleed_run_classifies_bleed_at_request_6():
    contract = _live_contract()
    run = run_experiments(
        contract, scenario="healthy", proxy_mode="force_uri_only",
        namespace_prefix="t006-live",
    )
    result = classify_run(
        contract,
        run.observations,
        run.origin_events,
        run.reset_evidence,
        raw_observations=run.raw_observations,
    )
    assert result.verdict == "REPRESENTATION_BLEED"
    assert result.first_error == 6
    assert result.first_error_experiment_id == "HTML_TO_MARKDOWN"
    assert "REPRESENTATION_BLEED" in result.diagnostic_codes()


# ---------------------------------------------------------------------------
# T008: revalidation limit (§8.6, §11.3 E07/E08) and Vary:* BYPASS
# exemption (§8.9, §11.3 E03, ADR-004)
# ---------------------------------------------------------------------------


def _raws_with_cache_control(directive, *, vary="Accept", cache_header="MISS"):
    """Raw records for all 8 requests carrying one Cache-Control
    directive (baselines included) and the given Vary value."""
    raws = []
    for index, rep in (
        (1, "html"), (2, "markdown"), (3, "html"), (4, "markdown"),
        (5, "html"), (6, "markdown"), (7, "markdown"), (8, "html"),
    ):
        raws.append(
            raw(
                index,
                rep,
                cache_header=cache_header if index >= 3 else None,
                headers={"vary": vary, "cache-control": directive},
            )
        )
    return raws


def test_inconclusive_when_response_requires_revalidation_no_cache():
    result = classify(
        healthy_observations(),
        raw_observations=_raws_with_cache_control("no-cache"),
    )
    assert result.verdict == "INCONCLUSIVE"
    assert result.first_error == 1
    assert result.first_error_experiment_id == "ORIGIN_HTML"
    limits = [d for d in result.diagnostics if d.code == "INCONCLUSIVE_LIMIT"]
    assert len(limits) == 8
    assert {d.evidence["limit_code"] for d in limits} == {"revalidation_required"}


def test_inconclusive_when_response_requires_revalidation_max_age_zero():
    result = classify(
        healthy_observations(),
        raw_observations=_raws_with_cache_control("max-age=0"),
    )
    assert result.verdict == "INCONCLUSIVE"
    assert result.first_error == 1
    limits = [d for d in result.diagnostics if d.code == "INCONCLUSIVE_LIMIT"]
    assert len(limits) == 8
    assert {d.evidence["limit_code"] for d in limits} == {"revalidation_required"}


@pytest.mark.parametrize(
    "directive",
    [
        "max-age = 0",
        "max-age= 0",
        "max-age =0",
        'max-age="0"',
        "max-age = 0, public",
        'no-cache="field"',
        "no-cache=field",
        "No-Cache",
        "MAX-AGE = 0",
    ],
)
def test_revalidation_tolerant_parsing_t014(directive):
    """T014 (T008 P2-2): spaced / quoted revalidation directives
    trigger exactly like their compact forms (RFC 9111-tolerant)."""
    result = classify(
        healthy_observations(),
        raw_observations=_raws_with_cache_control(directive),
    )
    assert result.verdict == "INCONCLUSIVE"
    assert result.first_error == 1
    limits = [d for d in result.diagnostics if d.code == "INCONCLUSIVE_LIMIT"]
    assert len(limits) == 8
    assert {d.evidence["limit_code"] for d in limits} == {"revalidation_required"}


@pytest.mark.parametrize("directive", ["max-age=0.0", "max-age=", "max-age=60"])
def test_revalidation_non_trigger_forms_t014(directive):
    """T014 (T008 P2-2): invalid / fresh max-age values still pass."""
    result = classify(
        healthy_observations(),
        raw_observations=_raws_with_cache_control(directive),
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.first_error is None


def test_fresh_max_age_does_not_require_revalidation():
    result = classify(
        healthy_observations(),
        raw_observations=_raws_with_cache_control("max-age=60"),
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.first_error is None


def test_vary_star_bypass_passes_under_variant_contract():
    # E03 shape: every proxied request is a confirmed BYPASS, but
    # the responses carry Vary: *, so not storing them is compliant.
    result = classify(
        healthy_observations(cache_mode="no_store"),
        raw_observations=_raws_with_cache_control(
            "max-age=60", vary="*", cache_header="BYPASS"
        ),
    )
    assert result.verdict == "PASS_OBSERVED"
    assert result.first_error is None
    assert "CACHE_POLICY_MISMATCH" not in result.diagnostic_codes()


def test_vary_accept_bypass_still_violates_variant_policy():
    # Same BYPASS run without Vary: * keeps the ADR-002 P1-1 rule.
    result = classify(
        healthy_observations(cache_mode="no_store"),
        raw_observations=_raws_with_cache_control(
            "max-age=60", vary="Accept", cache_header="BYPASS"
        ),
    )
    assert result.verdict == "CONTRACT_MISMATCH"
    assert result.first_error == 3
    assert "CACHE_POLICY_MISMATCH" in result.diagnostic_codes()
