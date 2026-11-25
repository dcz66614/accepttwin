"""Dual-evidence cache-state verification (P032 T004).

Implements the evidence contract of PROJECT_BOOK §5.3 and the
verification step of IMPLEMENTATION_PLAN T004 step 13:

* every cache state (MISS / HIT / BYPASS) is confirmed only when its
  *header* leg and its *behaviour* leg both hold;
* any conflict between the legs, or any missing leg, yields
  ``CACHE_STATE_UNKNOWN`` — never a guessed state.

The legs, per §5.3:

* MISS — header leg: ``X-AcceptTwin-Cache-Status: MISS`` plus a
  ``X-AcceptTwin-Cache-Key`` and a ``X-AcceptTwin-Entry-Id``;
  behaviour leg: the origin request counter increased by exactly 1,
  an origin event exists for this request, and a cache entry was
  created by this response.
* HIT — header leg: status HIT plus key and entry id; behaviour leg:
  the origin counter did not move, the entry id matches the entry
  actually stored, and the returned body hash matches the stored
  entry's body hash.
* BYPASS — header leg: status BYPASS; behaviour leg: the origin
  counter increased by exactly 1, an origin event exists for this
  request, and the entry count did not increase.

Rules applied here, all fail-closed:

* A leg supplied as ``None`` means "evidence unavailable", not "leg
  satisfied": a MISS whose entry creation was never checked, a HIT
  whose entry id was never compared, or a BYPASS whose entry-count
  delta was never measured is UNKNOWN (§5.3 D: "缺少源站事件日志" /
  "缓存键无法关联" / "缓存重置未确认成功" all forbid guessing).
* The origin-event leg applies to MISS and BYPASS only (those are the
  states where a request reaches the origin). For HIT no new origin
  event is expected, so ``origin_event_present`` is ignored there.
* ``Age``, ``Via``, ``Vary`` and ``Cache-Control`` are auxiliary only
  (§5.3 E): they are never consulted here and can never prove a HIT
  or a MISS on their own.
* An optional *expected* state may be supplied by the caller (e.g.
  the contract/mode prediction). A header state that disagrees with
  it is a conflict and yields UNKNOWN.
* The verifier never performs I/O and never invents origin counts: the
  caller measures the counter delta from
  :meth:`SyntheticOrigin.counter_snapshot` before/after the request
  and passes the measured number in. A fabricated delta would be a
  fabricated verdict, not evidence (§5.3, T004 prohibition).

This module is pure logic, which is why its tests live in
``tests/unit/test_cache_evidence.py`` while the end-to-end dual
evidence (real HTTP + real counters) is exercised in
``tests/integration/test_cache_proxy.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "CACHE_STATE_UNKNOWN",
    "CACHE_STATES",
    "BehaviorEvidence",
    "CacheEvidenceResult",
    "HeaderEvidence",
    "verify_cache_state",
]

#: The only "state" a conflict or an incomplete evidence pair may yield.
CACHE_STATE_UNKNOWN = "CACHE_STATE_UNKNOWN"

#: Cache states that count as confirmed (§5.3 A–C).
CACHE_STATES: frozenset[str] = frozenset({"MISS", "HIT", "BYPASS"})


@dataclass(frozen=True)
class HeaderEvidence:
    """The response-header leg of the dual evidence (§5.3).

    ``None`` on any field means the header was absent — a missing leg,
    never a satisfied one.
    """

    status: str | None
    cache_key_sha256: str | None = None
    entry_id: str | None = None


@dataclass(frozen=True)
class BehaviorEvidence:
    """The origin-behaviour leg of the dual evidence (§5.3).

    ``None`` on any field means that leg was not measured — a missing
    leg, never a satisfied one. ``origin_event_present`` is meaningful
    only for MISS/BYPASS (a HIT expects no new origin request);
    ``entry_created`` only for MISS; ``entry_id_matches`` /
    ``body_hash_matches`` only for HIT; ``entry_count_delta`` only for
    BYPASS.
    """

    origin_counter_delta: int | None = None
    origin_event_present: bool | None = None
    entry_created: bool | None = None
    entry_id_matches: bool | None = None
    body_hash_matches: bool | None = None
    entry_count_delta: int | None = None


@dataclass(frozen=True)
class CacheEvidenceResult:
    """The outcome of one dual-evidence verification.

    ``state`` is ``"MISS"``, ``"HIT"``, ``"BYPASS"`` or
    ``CACHE_STATE_UNKNOWN``. ``verified`` is true exactly when the
    state is confirmed (i.e. not UNKNOWN). ``reasons`` lists, in
    deterministic order, every leg that was checked and every leg that
    failed or was missing, so a caller (and T006) can report *why* a
    state is UNKNOWN instead of merely that it is.
    """

    state: str
    header_status: str | None
    verified: bool
    reasons: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.verified


def _missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value)


def verify_cache_state(
    header: HeaderEvidence,
    behavior: BehaviorEvidence,
    expected: str | None = None,
) -> CacheEvidenceResult:
    """Verify one cache observation against both evidence legs (§5.3).

    Returns a :class:`CacheEvidenceResult` whose ``state`` is the
    confirmed cache state, or ``CACHE_STATE_UNKNOWN`` when the header
    and behaviour legs disagree, when either leg is missing, or when
    the header state disagrees with *expected* (when given).
    """
    reasons: list[str] = []
    status = header.status

    def unknown(*new_reasons: str) -> CacheEvidenceResult:
        reasons.extend(new_reasons)
        return CacheEvidenceResult(
            state=CACHE_STATE_UNKNOWN,
            header_status=status,
            verified=False,
            reasons=tuple(reasons),
        )

    # -- header leg, common to all states -------------------------------
    if _missing(status):
        return unknown("missing cache-status header")
    assert status is not None  # _missing() above narrows it for readers
    if status not in CACHE_STATES:
        return unknown(f"unrecognised cache-status header value: {status!r}")
    if expected is not None and status != expected:
        return unknown(
            f"header cache state {status!r} does not match "
            f"expected state {expected!r}"
        )

    # -- MISS ------------------------------------------------------------
    if status == "MISS":
        if _missing(header.cache_key_sha256):
            reasons.append("missing cache-key header")
        if _missing(header.entry_id):
            reasons.append("missing entry-id header")
        if behavior.origin_counter_delta is None:
            reasons.append("origin counter delta not measured")
        elif behavior.origin_counter_delta != 1:
            reasons.append(
                "MISS requires origin counter delta +1, got "
                f"{behavior.origin_counter_delta:+d}"
            )
        if behavior.origin_event_present is None:
            reasons.append("origin event presence not checked")
        elif not behavior.origin_event_present:
            reasons.append("MISS requires a matching origin event")
        if behavior.entry_created is None:
            reasons.append("entry creation not checked")
        elif not behavior.entry_created:
            reasons.append("MISS requires a cache entry to be created")
        if reasons:
            return unknown()
        return CacheEvidenceResult(
            state="MISS",
            header_status=status,
            verified=True,
            reasons=(
                "header MISS with key and entry id; "
                "origin counter +1 with matching event; entry created",
            ),
        )

    # -- HIT -------------------------------------------------------------
    if status == "HIT":
        if _missing(header.cache_key_sha256):
            reasons.append("missing cache-key header")
        if _missing(header.entry_id):
            reasons.append("missing entry-id header")
        if behavior.origin_counter_delta is None:
            reasons.append("origin counter delta not measured")
        elif behavior.origin_counter_delta != 0:
            reasons.append(
                "HIT requires origin counter delta 0, got "
                f"{behavior.origin_counter_delta:+d}"
            )
        if behavior.entry_id_matches is None:
            reasons.append("entry-id match not checked")
        elif not behavior.entry_id_matches:
            reasons.append("HIT entry id does not match the stored entry")
        if behavior.body_hash_matches is None:
            reasons.append("body-hash match not checked")
        elif not behavior.body_hash_matches:
            reasons.append("HIT body hash does not match the stored entry")
        if reasons:
            return unknown()
        return CacheEvidenceResult(
            state="HIT",
            header_status=status,
            verified=True,
            reasons=(
                "header HIT with key and entry id; "
                "origin counter unchanged; entry id and body hash match",
            ),
        )

    # -- BYPASS ----------------------------------------------------------
    # The BYPASS header leg is the status header alone (§5.3 C;
    # acceptance text: "BYPASS: header BYPASS + origin counter +1").
    # This proxy also emits the cache key on BYPASS (§5.4), but its
    # absence is not a missing leg for BYPASS — there is no entry to
    # correlate with, and no entry id is expected either.
    if behavior.origin_counter_delta is None:
        reasons.append("origin counter delta not measured")
    elif behavior.origin_counter_delta != 1:
        reasons.append(
            "BYPASS requires origin counter delta +1, got "
            f"{behavior.origin_counter_delta:+d}"
        )
    if behavior.origin_event_present is None:
        reasons.append("origin event presence not checked")
    elif not behavior.origin_event_present:
        reasons.append("BYPASS requires a matching origin event")
    if behavior.entry_count_delta is None:
        reasons.append("entry-count delta not measured")
    elif behavior.entry_count_delta != 0:
        reasons.append(
            "BYPASS requires entry-count delta 0, got "
            f"{behavior.entry_count_delta:+d}"
        )
    if reasons:
        return unknown()
    return CacheEvidenceResult(
        state="BYPASS",
        header_status=status,
        verified=True,
        reasons=(
            "header BYPASS; origin counter +1 with matching event; "
            "entry count unchanged",
        ),
    )
