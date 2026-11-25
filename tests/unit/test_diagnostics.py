"""Unit tests for the frozen diagnostic codes (P032 T006).

Covers PROJECT_BOOK §8 (all nine codes, each with at least one
positive and one negative test), §8 severity mapping, and the
deterministic ordering of §6.3 / §7.8 I-08.

These tests exercise :mod:`accepttwin.diagnostics` in isolation —
pure predicates over already-measured evidence, no I/O, no HTTP.
The end-to-end behaviour (verdicts, first-error location) is
covered in ``test_classifier.py``.
"""

from __future__ import annotations

import pytest

from accepttwin.diagnostics import (
    CODE_SEVERITY,
    DIAGNOSTIC_CODES,
    Diagnostic,
    check_bleed,
    check_cache_state,
    check_contract_response,
    check_inconclusive_limit,
    check_no_store_policy,
    check_origin_baseline,
    check_reset_evidence,
    check_sentinel,
    check_unexpected_hit,
    check_variant_by_accept_policy,
    check_vary,
    diagnostic_order,
    make_diagnostic,
    sort_diagnostics,
)
from accepttwin.cache_proxy import ResetEvidence

HTML_BODY = "h" * 64
MD_BODY = "m" * 64
HTML_SENTINEL_SHA = "a" * 64
MD_SENTINEL_SHA = "b" * 64
KEY_1 = "k" * 64
KEY_2 = "j" * 64
ENTRY_1 = "entry-aaa"
ENTRY_2 = "entry-bbb"

HTML_CT = "text/html; charset=utf-8"
MD_CT = "text/markdown; charset=utf-8"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def baseline_kwargs(**overrides):
    kwargs = {
        "request_index": 1,
        "experiment_id": "ORIGIN_HTML",
        "requested_representation": "html",
        "response_status": 200,
        "response_content_type": HTML_CT,
        "sentinel_match": True,
        "expected_status": 200,
        "expected_content_type": HTML_CT,
        "expected_sentinel_sha256": HTML_SENTINEL_SHA,
        "body_sha256": HTML_BODY,
    }
    kwargs.update(overrides)
    return kwargs


def bleed_kwargs(**overrides):
    """A complete §8.2 chain: HTML first (MISS), Markdown second (HIT
    of the same entry, HTML body, HTML Content-Type, no MD Sentinel)."""
    kwargs = {
        "first_request_index": 5,
        "second_request_index": 6,
        "experiment_id": "HTML_TO_MARKDOWN",
        "baseline_correct": True,
        "first_correct": True,
        "first_cache_status": "MISS",
        "first_cache_entry_id": ENTRY_1,
        "first_body_sha256": HTML_BODY,
        "second_cache_status": "HIT",
        "second_cache_entry_id": ENTRY_1,
        "second_cache_key_sha256": KEY_1,
        "second_body_sha256": HTML_BODY,
        "second_response_content_type": HTML_CT,
        "second_origin_counter_before": 5,
        "second_origin_counter_after": 5,
        "second_origin_counter_delta": 0,
        "second_sentinel_match": False,
        "first_expected_content_type": HTML_CT,
        "requested_representation": "markdown",
    }
    kwargs.update(overrides)
    return kwargs


def cache_state_kwargs(**overrides):
    kwargs = {
        "request_index": 3,
        "experiment_id": "HTML_COLD",
        "cache_status": "MISS",
        "origin_counter_delta": 1,
        "cache_key_sha256": KEY_1,
        "cache_entry_id": ENTRY_1,
        "header_status": "MISS",
        "origin_event_present": True,
    }
    kwargs.update(overrides)
    return kwargs


def reset_ok(namespace="t006-html-cold"):
    return ResetEvidence(
        namespace=namespace,
        success=True,
        entries_before=1,
        entries_after=0,
        entries_removed=1,
    )


# ---------------------------------------------------------------------------
# §8.0 — code table and severity mapping
# ---------------------------------------------------------------------------


def test_nine_codes_in_spec_order():
    assert DIAGNOSTIC_CODES == (
        "ORIGIN_NEGOTIATION_ERROR",
        "REPRESENTATION_BLEED",
        "CONTRACT_MISMATCH",
        "CACHE_STATE_UNKNOWN",
        "SENTINEL_MISMATCH",
        "INCONCLUSIVE_LIMIT",
        "VARY_ACCEPT_ABSENT",
        "CACHE_EVIDENCE_CONFLICT",
        "CACHE_POLICY_MISMATCH",
    )


def test_severities_are_only_critical_or_warning():
    assert set(CODE_SEVERITY) == set(DIAGNOSTIC_CODES)
    assert set(CODE_SEVERITY.values()) <= {"CRITICAL", "WARNING"}
    assert CODE_SEVERITY["ORIGIN_NEGOTIATION_ERROR"] == "CRITICAL"
    assert CODE_SEVERITY["REPRESENTATION_BLEED"] == "CRITICAL"
    assert CODE_SEVERITY["CONTRACT_MISMATCH"] == "CRITICAL"
    assert CODE_SEVERITY["CACHE_STATE_UNKNOWN"] == "WARNING"
    assert CODE_SEVERITY["SENTINEL_MISMATCH"] == "CRITICAL"
    assert CODE_SEVERITY["INCONCLUSIVE_LIMIT"] == "WARNING"
    assert CODE_SEVERITY["VARY_ACCEPT_ABSENT"] == "WARNING"
    assert CODE_SEVERITY["CACHE_EVIDENCE_CONFLICT"] == "WARNING"
    assert CODE_SEVERITY["CACHE_POLICY_MISMATCH"] == "CRITICAL"


def test_make_diagnostic_rejects_unknown_code():
    with pytest.raises(ValueError, match="unknown diagnostic code"):
        make_diagnostic("NOT_A_CODE", "boom")


def test_diagnostic_rejects_wrong_severity():
    with pytest.raises(ValueError, match="must have severity"):
        Diagnostic(
            code="VARY_ACCEPT_ABSENT",
            severity="CRITICAL",
            message="Vary is only ever a WARNING",
        )


def test_diagnostic_rejects_blank_message():
    with pytest.raises(ValueError, match="must not be blank"):
        make_diagnostic("CACHE_STATE_UNKNOWN", "   ")


def test_diagnostic_rejects_body_text_evidence():
    # §7.12 I-12: raw body text must never enter a diagnostic.
    with pytest.raises(ValueError, match="must not contain"):
        make_diagnostic(
            "SENTINEL_MISMATCH",
            "sentinel missing",
            evidence={"body_text": "<html>secret</html>"},
        )


def test_diagnostic_as_dict_round_trip():
    diag = make_diagnostic(
        "CACHE_STATE_UNKNOWN",
        "unknown",
        experiment_id="HTML_COLD",
        request_index=3,
        evidence={"cache_status": "CACHE_STATE_UNKNOWN"},
    )
    data = diag.as_dict()
    assert data["code"] == "CACHE_STATE_UNKNOWN"
    assert data["severity"] == "WARNING"
    assert data["request_index"] == 3
    assert "body_text" not in data["evidence"]


# ---------------------------------------------------------------------------
# §8.1 ORIGIN_NEGOTIATION_ERROR
# ---------------------------------------------------------------------------


def test_origin_error_on_404_baseline():
    diag = check_origin_baseline(**baseline_kwargs(response_status=404))
    assert diag is not None
    assert diag.code == "ORIGIN_NEGOTIATION_ERROR"
    assert diag.severity == "CRITICAL"
    assert diag.request_index == 1
    assert diag.evidence["origin_direct"] is True
    assert diag.evidence["observed_status"] == 404


def test_origin_error_on_wrong_content_type():
    diag = check_origin_baseline(
        **baseline_kwargs(response_content_type="text/plain")
    )
    assert diag is not None
    assert diag.code == "ORIGIN_NEGOTIATION_ERROR"


def test_origin_error_on_missing_sentinel():
    diag = check_origin_baseline(**baseline_kwargs(sentinel_match=False))
    assert diag is not None
    assert diag.code == "ORIGIN_NEGOTIATION_ERROR"


def test_origin_no_error_when_baseline_correct():
    assert check_origin_baseline(**baseline_kwargs()) is None


def test_origin_no_error_when_only_cache_would_differ():
    # A correct baseline is never an origin error, even if the
    # caller worries about the cache: §8.1 is about the origin only.
    assert check_origin_baseline(**baseline_kwargs()) is None


# ---------------------------------------------------------------------------
# §8.2 REPRESENTATION_BLEED
# ---------------------------------------------------------------------------


def test_bleed_on_full_evidence_chain():
    diag = check_bleed(**bleed_kwargs())
    assert diag is not None
    assert diag.code == "REPRESENTATION_BLEED"
    assert diag.severity == "CRITICAL"
    assert diag.request_index == 6
    assert diag.evidence["cache_status"] == "HIT"
    assert diag.evidence["cache_entry_id"] == ENTRY_1
    assert diag.evidence["origin_counter_delta"] == 0
    assert diag.evidence["body_sha256"] == HTML_BODY


def test_bleed_not_when_baseline_wrong():
    assert check_bleed(**bleed_kwargs(baseline_correct=False)) is None


def test_bleed_not_when_first_request_wrong():
    assert check_bleed(**bleed_kwargs(first_correct=False)) is None


def test_bleed_not_when_first_request_bypass():
    # A BYPASS stores nothing, so a later HIT cannot reuse its entry.
    assert check_bleed(**bleed_kwargs(first_cache_status="BYPASS")) is None


def test_bleed_not_when_second_is_miss():
    assert check_bleed(**bleed_kwargs(second_cache_status="MISS")) is None


def test_bleed_not_when_origin_revisited():
    assert check_bleed(**bleed_kwargs(second_origin_counter_delta=1)) is None


def test_bleed_not_when_entry_differs():
    assert (
        check_bleed(**bleed_kwargs(second_cache_entry_id=ENTRY_2)) is None
    )


def test_bleed_not_when_entry_id_missing():
    assert (
        check_bleed(**bleed_kwargs(second_cache_entry_id=None)) is None
    )


def test_bleed_not_when_body_differs():
    assert check_bleed(**bleed_kwargs(second_body_sha256=MD_BODY)) is None


def test_bleed_not_when_content_type_is_correct():
    assert (
        check_bleed(**bleed_kwargs(second_response_content_type=MD_CT))
        is None
    )


def test_bleed_not_when_sentinel_matches():
    assert check_bleed(**bleed_kwargs(second_sentinel_match=True)) is None


# ---------------------------------------------------------------------------
# §8.3 CONTRACT_MISMATCH (status / Content-Type leg)
# ---------------------------------------------------------------------------


def test_contract_mismatch_on_wrong_status():
    diag = check_contract_response(
        request_index=3,
        experiment_id="HTML_COLD",
        requested_representation="html",
        response_status=500,
        response_content_type=HTML_CT,
        cache_status="MISS",
        sentinel_match=True,
        expected_status=200,
        expected_content_type=HTML_CT,
    )
    assert diag is not None
    assert diag.code == "CONTRACT_MISMATCH"
    assert diag.severity == "CRITICAL"


def test_contract_mismatch_on_wrong_content_type():
    diag = check_contract_response(
        request_index=6,
        experiment_id="HTML_TO_MARKDOWN",
        requested_representation="markdown",
        response_status=200,
        response_content_type="text/html",
        cache_status="MISS",
        sentinel_match=True,
        expected_status=200,
        expected_content_type=MD_CT,
    )
    assert diag is not None
    assert diag.code == "CONTRACT_MISMATCH"


def test_contract_no_mismatch_when_response_correct():
    assert (
        check_contract_response(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            response_status=200,
            response_content_type=HTML_CT,
            cache_status="MISS",
            sentinel_match=True,
            expected_status=200,
            expected_content_type=HTML_CT,
        )
        is None
    )


def test_contract_no_mismatch_on_redirect():
    # Redirects are out of scope (§8.6), not contract mismatches.
    assert (
        check_contract_response(
            request_index=6,
            experiment_id="HTML_TO_MARKDOWN",
            requested_representation="markdown",
            response_status=302,
            response_content_type="text/html",
            cache_status="MISS",
            sentinel_match=False,
            expected_status=200,
            expected_content_type=MD_CT,
        )
        is None
    )


def test_contract_no_mismatch_on_sentinel_only():
    # A lone Sentinel failure is §8.5's job, not §8.3's.
    assert (
        check_contract_response(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            response_status=200,
            response_content_type=HTML_CT,
            cache_status="MISS",
            sentinel_match=False,
            expected_status=200,
            expected_content_type=HTML_CT,
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.4 CACHE_STATE_UNKNOWN / §8.8 CACHE_EVIDENCE_CONFLICT
# ---------------------------------------------------------------------------


def test_cache_unknown_when_verified_state_unknown():
    diag = check_cache_state(**cache_state_kwargs(cache_status="CACHE_STATE_UNKNOWN"))
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"
    assert diag.severity == "WARNING"


def test_cache_unknown_when_no_state_at_all():
    # A proxied request carrying None has no cache evidence (§8.4).
    diag = check_cache_state(**cache_state_kwargs(cache_status=None))
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"


def test_cache_unknown_when_key_header_missing():
    diag = check_cache_state(
        **cache_state_kwargs(cache_status="MISS", cache_key_sha256=None)
    )
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"


def test_cache_unknown_when_origin_event_missing():
    diag = check_cache_state(
        **cache_state_kwargs(cache_status="MISS", origin_event_present=False)
    )
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"


def test_cache_conflict_hit_with_origin_revisit():
    # Header HIT but the origin counter moved: §8.8, never a bleed.
    diag = check_cache_state(
        **cache_state_kwargs(
            cache_status="HIT", origin_counter_delta=1, header_status="HIT"
        )
    )
    assert diag is not None
    assert diag.code == "CACHE_EVIDENCE_CONFLICT"
    assert diag.severity == "WARNING"
    assert diag.evidence["evidence_consistent"] is False


def test_cache_conflict_miss_without_origin_revisit():
    diag = check_cache_state(
        **cache_state_kwargs(
            cache_status="MISS", origin_counter_delta=0, header_status="MISS"
        )
    )
    assert diag is not None
    assert diag.code == "CACHE_EVIDENCE_CONFLICT"


def test_cache_conflict_unknown_state_with_contradicting_header():
    # Verified UNKNOWN + a raw header HIT contradicted by delta +1.
    diag = check_cache_state(
        **cache_state_kwargs(
            cache_status="CACHE_STATE_UNKNOWN",
            origin_counter_delta=1,
            header_status="HIT",
        )
    )
    assert diag is not None
    assert diag.code == "CACHE_EVIDENCE_CONFLICT"


def test_cache_state_evidence_carries_section_84_fields():
    # P2-3 (§8.4): UNKNOWN diagnostics carry proxy_cache_header_
    # present, origin_journal_available, cache_reset_confirmed and
    # evidence_conflict — None where the leg was not supplied.
    diag = check_cache_state(
        **cache_state_kwargs(
            cache_status="CACHE_STATE_UNKNOWN",
            cache_reset_confirmed=True,
        )
    )
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"
    assert diag.evidence["proxy_cache_header_present"] is True
    assert diag.evidence["origin_journal_available"] is True
    assert diag.evidence["cache_reset_confirmed"] is True
    assert diag.evidence["evidence_conflict"] is False


def test_cache_state_evidence_conflict_flag_is_true_on_conflict():
    diag = check_cache_state(
        **cache_state_kwargs(
            cache_status="HIT",
            origin_counter_delta=1,
            header_status="HIT",
            cache_reset_confirmed=True,
        )
    )
    assert diag is not None
    assert diag.code == "CACHE_EVIDENCE_CONFLICT"
    assert diag.evidence["evidence_conflict"] is True
    assert diag.evidence["evidence_consistent"] is False
    assert diag.evidence["cache_reset_confirmed"] is True


def test_cache_state_evidence_fields_unknown_when_not_supplied():
    # A leg that was never supplied stays None (unknown), never a
    # guessed False.
    diag = check_cache_state(
        request_index=3,
        experiment_id="HTML_COLD",
        cache_status="CACHE_STATE_UNKNOWN",
        origin_counter_delta=1,
        cache_key_sha256=None,
        cache_entry_id=None,
        header_status=None,
        origin_event_present=None,
    )
    assert diag is not None
    assert diag.evidence["proxy_cache_header_present"] is None
    assert diag.evidence["origin_journal_available"] is None
    assert diag.evidence["cache_reset_confirmed"] is None


def test_cache_no_diagnostic_when_miss_confirmed():
    assert check_cache_state(**cache_state_kwargs()) is None


def test_cache_no_diagnostic_when_hit_confirmed():
    assert (
        check_cache_state(
            **cache_state_kwargs(
                cache_status="HIT",
                origin_counter_delta=0,
                header_status="HIT",
            )
        )
        is None
    )


def test_cache_no_diagnostic_when_bypass_confirmed():
    assert (
        check_cache_state(
            **cache_state_kwargs(
                cache_status="BYPASS",
                cache_key_sha256=None,
                cache_entry_id=None,
                header_status="BYPASS",
            )
        )
        is None
    )


def test_cache_no_conflict_when_header_matches_verified_state():
    assert (
        check_cache_state(
            **cache_state_kwargs(cache_status="MISS", header_status="MISS")
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.5 SENTINEL_MISMATCH
# ---------------------------------------------------------------------------


def test_sentinel_mismatch_when_sentinel_absent():
    diag = check_sentinel(
        request_index=3,
        experiment_id="HTML_COLD",
        requested_representation="html",
        sentinel_match=False,
        response_content_type=HTML_CT,
        expected_sentinel_sha256=HTML_SENTINEL_SHA,
        body_sha256=MD_BODY,
    )
    assert diag is not None
    assert diag.code == "SENTINEL_MISMATCH"
    assert diag.severity == "CRITICAL"
    assert diag.evidence["sentinel_match"] is False
    assert diag.evidence["body_sha256"] == MD_BODY


def test_sentinel_no_mismatch_when_sentinel_present():
    assert (
        check_sentinel(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            sentinel_match=True,
            response_content_type=HTML_CT,
            expected_sentinel_sha256=HTML_SENTINEL_SHA,
            body_sha256=HTML_BODY,
        )
        is None
    )


def test_sentinel_no_mismatch_when_only_status_wrong():
    # A wrong status with a matching Sentinel is not a Sentinel
    # problem; §8.3 covers the status.
    assert (
        check_sentinel(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            sentinel_match=True,
            response_content_type=HTML_CT,
            expected_sentinel_sha256=HTML_SENTINEL_SHA,
            body_sha256=HTML_BODY,
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.6 INCONCLUSIVE_LIMIT
# ---------------------------------------------------------------------------


def test_inconclusive_limit_on_redirect():
    diag = check_inconclusive_limit(
        request_index=6,
        experiment_id="HTML_TO_MARKDOWN",
        limit_code="redirect",
        response_status=302,
        detail="status 302 (redirects are not followed in this release)",
    )
    assert diag is not None
    assert diag.code == "INCONCLUSIVE_LIMIT"
    assert diag.severity == "WARNING"
    assert diag.evidence["limit_code"] == "redirect"
    assert diag.evidence["response_status"] == 302


def test_inconclusive_limit_on_oversize_body():
    diag = check_inconclusive_limit(
        request_index=3,
        experiment_id="HTML_COLD",
        limit_code="body_too_large",
        body_size=2 * 1024 * 1024,
        supported_limit=1024 * 1024,
    )
    assert diag is not None
    assert diag.code == "INCONCLUSIVE_LIMIT"
    assert diag.evidence["body_size"] == 2 * 1024 * 1024


def test_inconclusive_limit_none_when_no_limit_hit():
    assert (
        check_inconclusive_limit(
            request_index=3,
            experiment_id="HTML_COLD",
            limit_code="",
        )
        is None
    )


def test_inconclusive_limit_carries_request_url_when_supplied():
    # P2-3 (§8.6): request_url is recorded when the caller has a
    # raw record; it is absent (not guessed) when not supplied.
    diag = check_inconclusive_limit(
        request_index=6,
        experiment_id="HTML_TO_MARKDOWN",
        limit_code="redirect",
        response_status=302,
        request_url="http://127.0.0.1:18765/doc",
        redirect_target="http://127.0.0.1:18765/other",
    )
    assert diag is not None
    assert diag.evidence["request_url"] == "http://127.0.0.1:18765/doc"
    assert diag.evidence["redirect_target"] == "http://127.0.0.1:18765/other"
    plain = check_inconclusive_limit(
        request_index=6,
        experiment_id="HTML_TO_MARKDOWN",
        limit_code="redirect",
        response_status=302,
    )
    assert plain is not None
    assert "request_url" not in plain.evidence
    assert "redirect_target" not in plain.evidence


# ---------------------------------------------------------------------------
# §8.7 VARY_ACCEPT_ABSENT
# ---------------------------------------------------------------------------


def test_vary_warning_when_absent_and_advisory():
    diag = check_vary(
        request_index=1,
        experiment_id="ORIGIN_HTML",
        requested_representation="html",
        vary_accept_present=False,
        vary_accept_required=False,
        cacheable=True,
    )
    assert diag is not None
    assert diag.code == "VARY_ACCEPT_ABSENT"
    assert diag.severity == "WARNING"


def test_vary_absent_when_required_is_contract_mismatch():
    # §5.2: required + absent is a contract violation — but still
    # never a bleed (I-11).
    diag = check_vary(
        request_index=1,
        experiment_id="ORIGIN_HTML",
        requested_representation="html",
        vary_accept_present=False,
        vary_accept_required=True,
        cacheable=True,
    )
    assert diag is not None
    assert diag.code == "CONTRACT_MISMATCH"
    assert diag.severity == "CRITICAL"


def test_vary_no_diagnostic_when_present():
    assert (
        check_vary(
            request_index=1,
            experiment_id="ORIGIN_HTML",
            requested_representation="html",
            vary_accept_present=True,
            vary_accept_required=False,
            cacheable=True,
        )
        is None
    )


def test_vary_no_diagnostic_when_not_cacheable():
    # no_store: Vary is not required and its absence means nothing.
    assert (
        check_vary(
            request_index=1,
            experiment_id="ORIGIN_HTML",
            requested_representation="html",
            vary_accept_present=False,
            vary_accept_required=False,
            cacheable=False,
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.9 CACHE_POLICY_MISMATCH (no_store leg)
# ---------------------------------------------------------------------------


def test_policy_mismatch_when_no_store_miss():
    diag = check_no_store_policy(
        request_index=3,
        experiment_id="HTML_COLD",
        cache_status="MISS",
        cache_entry_count_before=0,
        cache_entry_count_after=1,
    )
    assert diag is not None
    assert diag.code == "CACHE_POLICY_MISMATCH"
    assert diag.severity == "CRITICAL"
    assert diag.evidence["declared_cache_mode"] == "no_store"
    assert diag.evidence["observed_cache_status"] == "MISS"


def test_policy_mismatch_when_no_store_hit():
    diag = check_no_store_policy(
        request_index=6,
        experiment_id="HTML_TO_MARKDOWN",
        cache_status="HIT",
    )
    assert diag is not None
    assert diag.code == "CACHE_POLICY_MISMATCH"


def test_policy_no_mismatch_when_bypass():
    assert (
        check_no_store_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status="BYPASS",
        )
        is None
    )


def test_policy_no_mismatch_when_state_unknown():
    # Storage cannot be proven from an unconfirmed state.
    assert (
        check_no_store_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status="CACHE_STATE_UNKNOWN",
        )
        is None
    )


def test_policy_no_mismatch_when_no_state():
    assert (
        check_no_store_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status=None,
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.9 CACHE_POLICY_MISMATCH (variant_by_accept leg, P1-1)
# ---------------------------------------------------------------------------


def test_variant_policy_mismatch_when_bypass():
    diag = check_variant_by_accept_policy(
        request_index=3,
        experiment_id="HTML_COLD",
        cache_status="BYPASS",
        cache_entry_count_before=0,
        cache_entry_count_after=0,
    )
    assert diag is not None
    assert diag.code == "CACHE_POLICY_MISMATCH"
    assert diag.severity == "CRITICAL"
    assert diag.request_index == 3
    assert diag.evidence["declared_cache_mode"] == "variant_by_accept"
    assert diag.evidence["observed_cache_status"] == "BYPASS"
    assert diag.evidence["cache_entry_count_before"] == 0
    assert diag.evidence["cache_entry_count_after"] == 0


def test_variant_policy_no_mismatch_when_miss_or_hit():
    # MISS and HIT are the mode's normal states, not violations.
    assert (
        check_variant_by_accept_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status="MISS",
        )
        is None
    )
    assert (
        check_variant_by_accept_policy(
            request_index=6,
            experiment_id="HTML_TO_MARKDOWN",
            cache_status="HIT",
        )
        is None
    )


def test_variant_policy_no_mismatch_when_state_unknown_or_absent():
    # An unconfirmed BYPASS is an evidence problem (§8.4), never a
    # proven policy violation — the caller must pass only the
    # confirmed state.
    assert (
        check_variant_by_accept_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status="CACHE_STATE_UNKNOWN",
        )
        is None
    )
    assert (
        check_variant_by_accept_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status=None,
        )
        is None
    )


def test_variant_policy_exempt_when_vary_star():
    # T008 (ADR-004, §11.3 E03): Vary: * forbids reuse (RFC 9111
    # §4.1), so a BYPASS there is compliant, not a policy violation.
    for vary in ("*", "Accept, *", "*, Accept-Encoding"):
        assert (
            check_variant_by_accept_policy(
                request_index=3,
                experiment_id="HTML_COLD",
                cache_status="BYPASS",
                cache_entry_count_before=0,
                cache_entry_count_after=0,
                vary=vary,
            )
            is None
        )


def test_variant_policy_still_fires_without_vary_star():
    # No Vary at all, or a Vary without *, keeps the P1-1 rule: a
    # confirmed BYPASS under variant_by_accept is a violation.
    for vary in (None, "Accept", "Accept, Accept-Encoding"):
        diag = check_variant_by_accept_policy(
            request_index=3,
            experiment_id="HTML_COLD",
            cache_status="BYPASS",
            cache_entry_count_before=0,
            cache_entry_count_after=0,
            vary=vary,
        )
        assert diag is not None
        assert diag.code == "CACHE_POLICY_MISMATCH"


# ---------------------------------------------------------------------------
# §8.3 unexpected-HIT leg (cold-cache premise)
# ---------------------------------------------------------------------------


def test_unexpected_hit_on_cold_request():
    diag = check_unexpected_hit(
        request_index=3,
        experiment_id="HTML_COLD",
        requested_representation="html",
        cache_status="HIT",
        response_status=200,
        response_content_type=HTML_CT,
        sentinel_match=True,
        expected_status=200,
        expected_content_type=HTML_CT,
        reset_confirmed=True,
    )
    assert diag is not None
    assert diag.code == "CONTRACT_MISMATCH"


def test_unexpected_hit_none_when_miss():
    assert (
        check_unexpected_hit(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            cache_status="MISS",
            response_status=200,
            response_content_type=HTML_CT,
            sentinel_match=True,
            expected_status=200,
            expected_content_type=HTML_CT,
            reset_confirmed=True,
        )
        is None
    )


def test_unexpected_hit_none_when_wrong_representation():
    # A HIT serving the wrong representation is the bleed check's
    # job, not this leg's.
    assert (
        check_unexpected_hit(
            request_index=6,
            experiment_id="HTML_TO_MARKDOWN",
            requested_representation="markdown",
            cache_status="HIT",
            response_status=200,
            response_content_type=HTML_CT,
            sentinel_match=False,
            expected_status=200,
            expected_content_type=MD_CT,
            reset_confirmed=True,
        )
        is None
    )


def test_unexpected_hit_none_when_reset_unconfirmed():
    assert (
        check_unexpected_hit(
            request_index=3,
            experiment_id="HTML_COLD",
            requested_representation="html",
            cache_status="HIT",
            response_status=200,
            response_content_type=HTML_CT,
            sentinel_match=True,
            expected_status=200,
            expected_content_type=HTML_CT,
            reset_confirmed=False,
        )
        is None
    )


# ---------------------------------------------------------------------------
# §8.4 reset leg
# ---------------------------------------------------------------------------


def test_reset_unknown_when_no_reset_recorded():
    diag = check_reset_evidence([])
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"
    assert diag.evidence["cache_reset_confirmed"] is False


def test_reset_unknown_when_reset_failed():
    failed = ResetEvidence(
        namespace="t006-html-cold",
        success=False,
        entries_before=2,
        entries_after=2,
        entries_removed=0,
    )
    diag = check_reset_evidence([reset_ok(), failed])
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"


def test_reset_unknown_when_entries_left_behind():
    left = ResetEvidence(
        namespace="t006-html-cold",
        success=True,
        entries_before=1,
        entries_after=1,
        entries_removed=0,
    )
    diag = check_reset_evidence([left])
    assert diag is not None
    assert diag.code == "CACHE_STATE_UNKNOWN"


def test_reset_no_diagnostic_when_all_resets_confirmed():
    assert check_reset_evidence([reset_ok(), reset_ok("t006-md-cold")]) is None


def test_reset_no_diagnostic_when_not_supplied():
    assert check_reset_evidence(None) is None


# ---------------------------------------------------------------------------
# Deterministic ordering (§6.3, I-08)
# ---------------------------------------------------------------------------


def test_sort_orders_by_request_not_severity():
    # A WARNING at request 3 must sort before a CRITICAL at request 6:
    # §6.3 forbids re-ordering requests by diagnostic severity.
    late_critical = make_diagnostic(
        "REPRESENTATION_BLEED", "bleed", request_index=6
    )
    early_warning = make_diagnostic(
        "CACHE_STATE_UNKNOWN", "unknown", request_index=3
    )
    assert sort_diagnostics([late_critical, early_warning]) == (
        early_warning,
        late_critical,
    )


def test_sort_tie_break_is_spec_code_order():
    first = make_diagnostic("SENTINEL_MISMATCH", "s", request_index=3)
    second = make_diagnostic("CONTRACT_MISMATCH", "c", request_index=3)
    # §8 order: CONTRACT_MISMATCH (8.3) before SENTINEL_MISMATCH (8.5).
    assert sort_diagnostics([first, second]) == (second, first)


def test_sort_run_level_diagnostics_last():
    run_level = make_diagnostic("CACHE_STATE_UNKNOWN", "reset failed")
    bound = make_diagnostic(
        "CACHE_STATE_UNKNOWN", "unknown", request_index=3
    )
    assert sort_diagnostics([run_level, bound]) == (bound, run_level)


def test_sort_is_stable_for_equal_keys():
    a = make_diagnostic("CACHE_STATE_UNKNOWN", "same", request_index=3)
    b = make_diagnostic("CACHE_STATE_UNKNOWN", "same", request_index=3)
    assert sort_diagnostics([a, b]) == (a, b)
    assert sort_diagnostics([b, a]) == (b, a)


def test_diagnostic_order_rejects_unknown_code():
    with pytest.raises(ValueError, match="unknown diagnostic code"):
        diagnostic_order("NOPE")
