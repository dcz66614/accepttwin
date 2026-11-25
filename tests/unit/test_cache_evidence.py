"""Unit tests for the dual-evidence cache-state verifier (P032 T004).

The verifier is pure logic (no I/O, no HTTP): every case below feeds
crafted header + behaviour evidence to
:func:`accepttwin.cache_evidence.verify_cache_state` and checks the
confirmed state, or ``CACHE_STATE_UNKNOWN`` when any leg is missing
or the legs conflict (PROJECT_BOOK §5.3 D).

End-to-end dual evidence — real HTTP through the proxy, real origin
counter deltas, real snapshots — is exercised in
``tests/integration/test_cache_proxy.py``.
"""

from __future__ import annotations

import pytest

from accepttwin.cache_evidence import (
    CACHE_STATE_UNKNOWN,
    BehaviorEvidence,
    CacheEvidenceResult,
    HeaderEvidence,
    verify_cache_state,
)

KEY = "a" * 64
ENTRY = "entry-" + "b" * 16


def header(status, key=KEY, entry=ENTRY):
    return HeaderEvidence(status=status, cache_key_sha256=key, entry_id=entry)


def behavior(**overrides):
    base = {
        "origin_counter_delta": 1,
        "origin_event_present": True,
        "entry_created": True,
        "entry_id_matches": True,
        "body_hash_matches": True,
        "entry_count_delta": 0,
    }
    base.update(overrides)
    return BehaviorEvidence(**base)


# ---------------------------------------------------------------------------
# Confirmed states (§5.3 A–C)
# ---------------------------------------------------------------------------


def test_miss_confirmed_when_both_legs_hold():
    result = verify_cache_state(header("MISS"), behavior())
    assert result.state == "MISS"
    assert result.verified is True
    assert bool(result) is True


def test_hit_confirmed_when_both_legs_hold():
    result = verify_cache_state(
        header("HIT"), behavior(origin_counter_delta=0)
    )
    assert result.state == "HIT"
    assert result.verified is True


def test_bypass_confirmed_when_both_legs_hold():
    result = verify_cache_state(header("BYPASS"), behavior())
    assert result.state == "BYPASS"
    assert result.verified is True


def test_bypass_confirmed_without_cache_key():
    # §5.3 C lists only the status header for BYPASS; the key is not a
    # required leg (the proxy emits one anyway, but its absence must
    # not turn a confirmed BYPASS into UNKNOWN).
    result = verify_cache_state(
        header("BYPASS", key=None, entry=None), behavior()
    )
    assert result.state == "BYPASS"
    assert result.verified is True


def test_expected_state_matching_is_accepted():
    assert verify_cache_state(header("MISS"), behavior(), expected="MISS").state == "MISS"
    assert (
        verify_cache_state(
            header("HIT"), behavior(origin_counter_delta=0), expected="HIT"
        ).state
        == "HIT"
    )
    assert (
        verify_cache_state(header("BYPASS"), behavior(), expected="BYPASS").state
        == "BYPASS"
    )


# ---------------------------------------------------------------------------
# Missing header leg (§5.3 D)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["MISS", "HIT", "BYPASS"])
def test_missing_status_header_is_unknown(status):
    result = verify_cache_state(
        HeaderEvidence(status=None), behavior(origin_counter_delta=0)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert result.verified is False
    assert any("missing cache-status" in r for r in result.reasons)


@pytest.mark.parametrize("status", ["MISS", "HIT"])
def test_missing_key_header_is_unknown(status):
    delta = 0 if status == "HIT" else 1
    result = verify_cache_state(
        header(status, key=None), behavior(origin_counter_delta=delta)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("cache-key" in r for r in result.reasons)


@pytest.mark.parametrize("status", ["MISS", "HIT"])
def test_missing_entry_id_header_is_unknown(status):
    delta = 0 if status == "HIT" else 1
    result = verify_cache_state(
        header(status, entry=None), behavior(origin_counter_delta=delta)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("entry-id" in r for r in result.reasons)


def test_unrecognised_status_value_is_unknown():
    result = verify_cache_state(header("STALE"), behavior())
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("unrecognised" in r for r in result.reasons)


def test_empty_status_header_is_unknown():
    result = verify_cache_state(header(""), behavior())
    assert result.state == CACHE_STATE_UNKNOWN


# ---------------------------------------------------------------------------
# Missing behaviour leg (§5.3 D)
# ---------------------------------------------------------------------------


def test_miss_without_measured_counter_delta_is_unknown():
    result = verify_cache_state(
        header("MISS"), behavior(origin_counter_delta=None)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("counter delta" in r for r in result.reasons)


def test_hit_without_measured_counter_delta_is_unknown():
    result = verify_cache_state(
        header("HIT"), behavior(origin_counter_delta=None)
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_bypass_without_measured_counter_delta_is_unknown():
    result = verify_cache_state(
        header("BYPASS"), behavior(origin_counter_delta=None)
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_miss_without_origin_event_check_is_unknown():
    result = verify_cache_state(
        header("MISS"), behavior(origin_event_present=None)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("origin event" in r for r in result.reasons)


def test_miss_without_entry_creation_check_is_unknown():
    result = verify_cache_state(header("MISS"), behavior(entry_created=None))
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("entry creation" in r for r in result.reasons)


def test_hit_without_entry_id_check_is_unknown():
    result = verify_cache_state(
        header("HIT"),
        behavior(origin_counter_delta=0, entry_id_matches=None),
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("entry-id match" in r for r in result.reasons)


def test_hit_without_body_hash_check_is_unknown():
    result = verify_cache_state(
        header("HIT"),
        behavior(origin_counter_delta=0, body_hash_matches=None),
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("body-hash" in r for r in result.reasons)


def test_bypass_without_entry_count_check_is_unknown():
    result = verify_cache_state(
        header("BYPASS"), behavior(entry_count_delta=None)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("entry-count" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Conflicts between the legs (§5.3 D)
# ---------------------------------------------------------------------------


def test_hit_header_with_counter_increase_is_unknown():
    # §5.3 D: header says HIT but the origin counter increased.
    result = verify_cache_state(
        header("HIT"), behavior(origin_counter_delta=1)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("delta 0" in r for r in result.reasons)


def test_miss_header_with_no_counter_increase_is_unknown():
    # §5.3 D: header says MISS but the origin counter did not move.
    result = verify_cache_state(
        header("MISS"), behavior(origin_counter_delta=0)
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("delta +1" in r for r in result.reasons)


def test_bypass_header_with_no_counter_increase_is_unknown():
    result = verify_cache_state(
        header("BYPASS"), behavior(origin_counter_delta=0)
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_miss_header_without_matching_origin_event_is_unknown():
    result = verify_cache_state(
        header("MISS"), behavior(origin_event_present=False)
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_miss_header_without_created_entry_is_unknown():
    result = verify_cache_state(header("MISS"), behavior(entry_created=False))
    assert result.state == CACHE_STATE_UNKNOWN


def test_hit_header_with_entry_id_mismatch_is_unknown():
    result = verify_cache_state(
        header("HIT"),
        behavior(origin_counter_delta=0, entry_id_matches=False),
    )
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("does not match" in r for r in result.reasons)


def test_hit_header_with_body_hash_mismatch_is_unknown():
    result = verify_cache_state(
        header("HIT"),
        behavior(origin_counter_delta=0, body_hash_matches=False),
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_bypass_header_with_entry_count_increase_is_unknown():
    result = verify_cache_state(
        header("BYPASS"), behavior(entry_count_delta=1)
    )
    assert result.state == CACHE_STATE_UNKNOWN


def test_header_state_disagreeing_with_expected_is_unknown():
    result = verify_cache_state(header("HIT"), behavior(), expected="MISS")
    assert result.state == CACHE_STATE_UNKNOWN
    assert any("does not match" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


def test_unknown_result_carries_reasons_and_header_status():
    result = verify_cache_state(header("MISS"), behavior(origin_counter_delta=0))
    assert isinstance(result, CacheEvidenceResult)
    assert result.header_status == "MISS"
    assert result.reasons
    assert all(isinstance(r, str) and r for r in result.reasons)


def test_confirmed_result_carries_a_reason():
    result = verify_cache_state(header("MISS"), behavior())
    assert result.reasons
