"""Frozen diagnostic codes (P032 T006).

Implements PROJECT_BOOK §8 (nine codes, severity CRITICAL / WARNING
only) and the deterministic ordering of §6.3. This module owns the
trigger condition of every code: each ``check_*`` function below is a
pure predicate over already-measured evidence — it never performs
I/O, never reads a response body (only hashes and match flags, §7.12
I-12), and never guesses a state from a single header (§5.3 E).

The nine codes, in §8 order (which is also the tie-break order used
by :func:`sort_diagnostics`):

* ``ORIGIN_NEGOTIATION_ERROR`` (CRITICAL, §8.1) — a direct-origin
  baseline request (001 O-H / 002 O-M) violates the representation
  contract (wrong status, wrong Content-Type, or missing Sentinel).
* ``REPRESENTATION_BLEED`` (CRITICAL, §8.2) — a warm-cache second
  request was served the *other* representation from a verified HIT
  with the full dual-evidence chain (baseline correct, first request
  correct and a confirmed MISS, second request HIT with counter
  delta 0, same cache entry as the first request, body hash equal
  to the first request's body, Sentinel of the requested
  representation absent).
* ``CONTRACT_MISMATCH`` (CRITICAL, §8.3) — a response violates the
  contract but is neither a proven origin error nor a proven bleed
  (wrong status / Content-Type on a proxied request, a ``no_store``
  contract violated by storage is reported as
  ``CACHE_POLICY_MISMATCH`` instead, see below).
* ``CACHE_STATE_UNKNOWN`` (WARNING, §8.4) — a MISS / HIT / BYPASS
  cannot be confirmed with dual evidence (missing header leg,
  missing behaviour leg, missing origin event, or an unconfirmed
  cache reset).
* ``SENTINEL_MISMATCH`` (CRITICAL, §8.5) — a response body lacks the
  exact Sentinel of the requested representation.
* ``INCONCLUSIVE_LIMIT`` (WARNING, §8.6) — the run left the
  supported range (redirect, transport failure, body over the
  contract limit, invalid contract, incomplete observations).
* ``VARY_ACCEPT_ABSENT`` (WARNING, §8.7) — a cacheable dual
  representation whose origin response carries no ``Vary: Accept``
  while the contract does not require it. This never changes a
  verdict on its own (I-11); when the contract *requires* Vary
  (§5.2) the same absence is a ``CONTRACT_MISMATCH`` instead.
* ``CACHE_EVIDENCE_CONFLICT`` (WARNING, §8.8) — the proxy-reported
  cache state contradicts the origin-behaviour evidence (e.g. header
  HIT but origin counter +1, header MISS but counter 0). This is
  never reported as a proven ``REPRESENTATION_BLEED``.
* ``CACHE_POLICY_MISMATCH`` (CRITICAL, §8.9) — the contract declares
  ``no_store`` but the proxy stored or reused a response (a
  confirmed MISS — which creates an entry — or a confirmed HIT
  under ``no_store``); or the contract declares
  ``variant_by_accept`` but a proxied request is a confirmed
  BYPASS — the cache never worked at all, so representation
  isolation was never exercised, and the run must not be certified
  PASS (ADR-002, P1-1).

Deterministic ordering (§6.3, §7.8 I-08): diagnostics sort by
(request order, §8 code order, message). ``request_index`` is
``None`` only for run-level diagnostics (invalid contract,
incomplete observations, failed reset); those sort after every
request-bound diagnostic. Sorting is stable, so equal keys keep
insertion order and repeated runs hash identically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CODE_SEVERITY",
    "DIAGNOSTIC_CODES",
    "Diagnostic",
    "check_bleed",
    "check_cache_state",
    "check_contract_response",
    "check_inconclusive_limit",
    "check_no_store_policy",
    "check_origin_baseline",
    "check_reset_evidence",
    "check_sentinel",
    "check_unexpected_hit",
    "check_variant_by_accept_policy",
    "check_vary",
    "diagnostic_order",
    "make_diagnostic",
    "sort_diagnostics",
]

#: The nine frozen codes, in PROJECT_BOOK §8 order.
DIAGNOSTIC_CODES: tuple[str, ...] = (
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

#: Severity per code (§8: only CRITICAL / WARNING exist).
CODE_SEVERITY: dict[str, str] = {
    "ORIGIN_NEGOTIATION_ERROR": "CRITICAL",
    "REPRESENTATION_BLEED": "CRITICAL",
    "CONTRACT_MISMATCH": "CRITICAL",
    "CACHE_STATE_UNKNOWN": "WARNING",
    "SENTINEL_MISMATCH": "CRITICAL",
    "INCONCLUSIVE_LIMIT": "WARNING",
    "VARY_ACCEPT_ABSENT": "WARNING",
    "CACHE_EVIDENCE_CONFLICT": "WARNING",
    "CACHE_POLICY_MISMATCH": "CRITICAL",
}

#: Evidence keys that must never appear: raw body text is forbidden in
#: diagnostics and reports (§7.12 I-12). Hashes (``body_sha256``) and
#: sizes are allowed.
_FORBIDDEN_EVIDENCE_KEYS = frozenset({"body_text", "response_body", "body"})

#: Cache states that count as confirmed (§5.3 A–C).
_CONFIRMED_STATES = frozenset({"MISS", "HIT", "BYPASS"})

#: Verified-state value meaning "the dual evidence did not confirm a
#: state" (§5.3 D).
_CACHE_STATE_UNKNOWN = "CACHE_STATE_UNKNOWN"


def diagnostic_order(code: str) -> int:
    """Position of *code* in the §8 order (used as a sort tie-break)."""
    try:
        return DIAGNOSTIC_CODES.index(code)
    except ValueError as exc:
        raise ValueError(f"unknown diagnostic code {code!r}") from exc


@dataclass(frozen=True)
class Diagnostic:
    """One frozen diagnostic (§8, §4.3 area E).

    ``evidence`` carries hashes, statuses, counters and identifiers
    only — never response body text (§7.12 I-12). ``request_index``
    is ``None`` only for run-level diagnostics (invalid contract,
    incomplete observations, failed reset); every request-bound
    diagnostic carries the 1-based request number of §6.3.
    """

    code: str
    severity: str
    message: str
    experiment_id: str | None = None
    request_index: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.code not in CODE_SEVERITY:
            raise ValueError(f"unknown diagnostic code {self.code!r}")
        if CODE_SEVERITY[self.code] != self.severity:
            raise ValueError(
                f"diagnostic {self.code} must have severity "
                f"{CODE_SEVERITY[self.code]!r}, got {self.severity!r}"
            )
        if not self.message or not self.message.strip():
            raise ValueError("diagnostic message must not be blank")
        if self.request_index is not None and self.request_index < 1:
            raise ValueError("request_index must be a positive integer")
        for key in self.evidence:
            if key in _FORBIDDEN_EVIDENCE_KEYS:
                raise ValueError(
                    f"diagnostic evidence must not contain {key!r} "
                    "(§7.12 I-12: no raw body text)"
                )

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "experiment_id": self.experiment_id,
            "request_index": self.request_index,
            "evidence": dict(self.evidence),
        }


def make_diagnostic(
    code: str,
    message: str,
    *,
    experiment_id: str | None = None,
    request_index: int | None = None,
    evidence: dict[str, Any] | None = None,
) -> Diagnostic:
    """Build a :class:`Diagnostic` with the §8 severity for *code*.

    Raises :class:`ValueError` for an unknown code, a blank message,
    or forbidden (body-text) evidence keys.
    """
    if code not in CODE_SEVERITY:
        raise ValueError(f"unknown diagnostic code {code!r}")
    return Diagnostic(
        code=code,
        severity=CODE_SEVERITY[code],
        message=message,
        experiment_id=experiment_id,
        request_index=request_index,
        evidence=dict(evidence) if evidence else {},
    )


def sort_diagnostics(
    diagnostics: list[Diagnostic] | tuple[Diagnostic, ...],
) -> tuple[Diagnostic, ...]:
    """Return *diagnostics* in deterministic order (§6.3, I-08).

    Sort key: request order first (``request_index`` ascending;
    run-level diagnostics with ``request_index is None`` sort last),
    then §8 code order, then message. The sort is stable, so
    diagnostics that compare equal keep their insertion order.
    """
    return tuple(
        sorted(
            diagnostics,
            key=lambda d: (
                d.request_index is None,
                d.request_index if d.request_index is not None else 0,
                diagnostic_order(d.code),
                d.message,
            ),
        )
    )


# ---------------------------------------------------------------------------
# Shared helpers for the check functions below.
#
# The checks take plain values (statuses, hashes, flags) rather than
# importing the classifier's dataclasses, so each trigger condition
# is testable in isolation.
# ---------------------------------------------------------------------------


def _content_type_matches(observed: str, expected: str) -> bool:
    """Case-insensitive, whitespace-tolerant Content-Type equality."""
    return observed.strip().lower() == expected.strip().lower()


def _representation_correct(
    *,
    response_status: int,
    response_content_type: str,
    sentinel_match: bool,
    expected_status: int,
    expected_content_type: str,
) -> bool:
    """True when a response matches its representation contract
    exactly: status, Content-Type and Sentinel (§7 I-01–I-06)."""
    return (
        response_status == expected_status
        and _content_type_matches(response_content_type, expected_content_type)
        and sentinel_match
    )


# ---------------------------------------------------------------------------
# Per-code trigger checks (§8.1–§8.9). Each returns a Diagnostic when
# its trigger condition holds, else None. A check returning None is a
# *negative* outcome for that code: the evidence does not support it.
# ---------------------------------------------------------------------------


def check_origin_baseline(
    *,
    request_index: int,
    experiment_id: str,
    requested_representation: str,
    response_status: int,
    response_content_type: str,
    sentinel_match: bool,
    expected_status: int,
    expected_content_type: str,
    expected_sentinel_sha256: str,
    body_sha256: str,
) -> Diagnostic | None:
    """§8.1 ORIGIN_NEGOTIATION_ERROR.

    Fires when a direct-origin baseline request violates the
    representation contract (wrong status, wrong Content-Type, or
    missing Sentinel). Returns None when the baseline is correct —
    a correct baseline is never an origin error, whatever the cache
    does later.
    """
    if _representation_correct(
        response_status=response_status,
        response_content_type=response_content_type,
        sentinel_match=sentinel_match,
        expected_status=expected_status,
        expected_content_type=expected_content_type,
    ):
        return None
    return make_diagnostic(
        "ORIGIN_NEGOTIATION_ERROR",
        f"direct-origin baseline for {requested_representation} violates "
        f"the contract: status {response_status} (expected "
        f"{expected_status}), content-type "
        f"{response_content_type!r} (expected "
        f"{expected_content_type!r}), sentinel_match={sentinel_match}",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "stage": experiment_id,
            "requested_representation": requested_representation,
            "expected_status": expected_status,
            "observed_status": response_status,
            "expected_content_type": expected_content_type,
            "observed_content_type": response_content_type,
            "expected_sentinel_sha256": expected_sentinel_sha256,
            "sentinel_match": sentinel_match,
            "body_sha256": body_sha256,
            "origin_direct": True,
        },
    )


def check_sentinel(
    *,
    request_index: int,
    experiment_id: str,
    requested_representation: str,
    sentinel_match: bool,
    response_content_type: str,
    expected_sentinel_sha256: str,
    body_sha256: str,
) -> Diagnostic | None:
    """§8.5 SENTINEL_MISMATCH.

    Fires when a response body lacks the exact Sentinel of the
    requested representation. Returns None when the Sentinel
    matches — a matching Sentinel is never a mismatch, even when
    some other field (status, Content-Type, cache state) is wrong.
    """
    if sentinel_match:
        return None
    return make_diagnostic(
        "SENTINEL_MISMATCH",
        f"response body for request {request_index:03d} lacks the exact "
        f"Sentinel of the requested {requested_representation} "
        f"representation",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "requested_representation": requested_representation,
            "expected_sentinel_sha256": expected_sentinel_sha256,
            "body_sha256": body_sha256,
            "sentinel_match": False,
            "observed_content_type": response_content_type,
        },
    )


def check_contract_response(
    *,
    request_index: int,
    experiment_id: str,
    requested_representation: str,
    response_status: int,
    response_content_type: str,
    cache_status: str | None,
    sentinel_match: bool,
    expected_status: int,
    expected_content_type: str,
) -> Diagnostic | None:
    """§8.3 CONTRACT_MISMATCH (status / Content-Type leg).

    Fires when a proxied response has the wrong status or the wrong
    Content-Type for its requested representation. Returns None when
    both match. Sentinel failures are *not* reported here — they are
    §8.5's job (``check_sentinel``) — so one bad response never
    yields two CONTRACT_MISMATCH diagnostics for the same leg.
    Redirects (3xx) are out of scope (§8.6) and are not contract
    mismatches: they return None here and are handled by
    ``check_inconclusive_limit``.
    """
    if 300 <= response_status < 400:
        return None
    mismatches: list[str] = []
    if response_status != expected_status:
        mismatches.append(
            f"status {response_status} (expected {expected_status})"
        )
    if not _content_type_matches(response_content_type, expected_content_type):
        mismatches.append(
            f"content-type {response_content_type!r} (expected "
            f"{expected_content_type!r})"
        )
    if not mismatches:
        return None
    return make_diagnostic(
        "CONTRACT_MISMATCH",
        f"response for request {request_index:03d} violates the "
        f"{requested_representation} contract: " + "; ".join(mismatches),
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "stage": experiment_id,
            "requested_representation": requested_representation,
            "expected": {
                "status": expected_status,
                "content_type": expected_content_type,
            },
            "observed": {
                "status": response_status,
                "content_type": response_content_type,
            },
            "expected_status": expected_status,
            "observed_status": response_status,
            "response_status": response_status,
            "expected_content_type": expected_content_type,
            "observed_content_type": response_content_type,
            "response_content_type": response_content_type,
            "cache_status": cache_status,
            "sentinel_match": sentinel_match,
        },
    )


def check_cache_state(
    *,
    request_index: int,
    experiment_id: str,
    cache_status: str | None,
    origin_counter_delta: int | None,
    cache_key_sha256: str | None,
    cache_entry_id: str | None,
    header_status: str | None = None,
    origin_event_present: bool | None = None,
    cache_reset_confirmed: bool | None = None,
) -> Diagnostic | None:
    """§8.4 CACHE_STATE_UNKNOWN / §8.8 CACHE_EVIDENCE_CONFLICT.

    Inspects one proxied observation's cache evidence:

    * ``cache_status is None`` on a proxied request — no cache
      evidence exists at all — is UNKNOWN (it is *not* a HIT/MISS,
      and it is distinct from the direct-origin ``None`` of ADR-001,
      which never reaches this check because baselines are not
      proxied).
    * A claimed state whose behaviour leg contradicts it (HIT with
      counter delta != 0; MISS/BYPASS with delta != 1; header state
      differing from the verified state) is a CONFLICT — never a
      proven bleed and never a confirmed state.
    * A verified ``CACHE_STATE_UNKNOWN``, a missing header leg
      (HIT/MISS without key or entry id), or a missing origin event
      where one is required (MISS/BYPASS) is UNKNOWN.
    * A confirmed state whose legs agree returns None.

    ``header_status`` is the raw ``X-AcceptTwin-Cache-Status`` header
    when the caller has it (from a RawObservation); ``None`` means
    "not supplied", not "header absent". ``origin_event_present``
    likewise: ``None`` means "not checked". ``cache_reset_confirmed``
    is the run-level reset outcome when the caller knows it (the
    classifier passes it); ``None`` means "not supplied". The
    evidence always carries the §8.4 fields, with ``None`` where a
    leg was not supplied — never a guessed value: ``None`` means
    "unknown", not "absent".
    """
    base_evidence: dict[str, Any] = {
        "cache_status": cache_status,
        "origin_counter_delta": origin_counter_delta,
        "cache_key_sha256": cache_key_sha256,
        "cache_entry_id": cache_entry_id,
        # §8.4 evidence fields (P2-3): header presence is only known
        # when the raw header was supplied; the origin journal counts
        # as available when it was actually consulted.
        "proxy_cache_header_present": (
            True if header_status is not None else None
        ),
        "origin_journal_available": (
            True if origin_event_present is not None else None
        ),
        "cache_reset_confirmed": cache_reset_confirmed,
    }
    if header_status is not None:
        base_evidence["proxy_reported_status"] = header_status

    def unknown(message: str) -> Diagnostic:
        evidence = dict(base_evidence)
        evidence["evidence_conflict"] = False
        return make_diagnostic(
            "CACHE_STATE_UNKNOWN",
            message,
            experiment_id=experiment_id,
            request_index=request_index,
            evidence=evidence,
        )

    def conflict(message: str) -> Diagnostic:
        evidence = dict(base_evidence)
        evidence["evidence_conflict"] = True
        evidence["evidence_consistent"] = False
        return make_diagnostic(
            "CACHE_EVIDENCE_CONFLICT",
            message,
            experiment_id=experiment_id,
            request_index=request_index,
            evidence=evidence,
        )

    if cache_status is None:
        return unknown(
            f"request {request_index:03d} went through the proxy but "
            "carries no cache state at all"
        )
    if cache_status == _CACHE_STATE_UNKNOWN:
        # A raw header that contradicts the behaviour leg is a
        # conflict, not merely unknown (§8.8).
        if (
            header_status in _CONFIRMED_STATES
            and origin_counter_delta is not None
            and (
                (header_status == "HIT" and origin_counter_delta != 0)
                or (
                    header_status in ("MISS", "BYPASS")
                    and origin_counter_delta != 1
                )
            )
        ):
            return conflict(
                f"proxy reported {header_status} for request "
                f"{request_index:03d} but the origin counter moved by "
                f"{origin_counter_delta:+d}"
            )
        return unknown(
            f"cache state for request {request_index:03d} could not be "
            "confirmed with dual evidence"
        )
    if cache_status not in _CONFIRMED_STATES:
        return unknown(
            f"request {request_index:03d} carries unrecognised cache "
            f"state {cache_status!r}"
        )
    # A confirmed state whose legs disagree is a conflict, not a
    # confirmation: the caller must not trust the label.
    if origin_counter_delta is not None:
        if cache_status == "HIT" and origin_counter_delta != 0:
            return conflict(
                f"request {request_index:03d} claims HIT but the origin "
                f"counter moved by {origin_counter_delta:+d}"
            )
        if (
            cache_status in ("MISS", "BYPASS")
            and origin_counter_delta != 1
        ):
            return conflict(
                f"request {request_index:03d} claims {cache_status} but "
                f"the origin counter moved by {origin_counter_delta:+d}"
            )
    if header_status is not None and header_status != cache_status:
        return conflict(
            f"request {request_index:03d} claims {cache_status} but the "
            f"proxy header reported {header_status!r}"
        )
    if cache_status in ("MISS", "HIT"):
        if not cache_key_sha256 or not cache_entry_id:
            return unknown(
                f"request {request_index:03d} claims {cache_status} but "
                "the cache-key or entry-id header leg is missing"
            )
    if cache_status in ("MISS", "BYPASS"):
        if origin_event_present is False:
            return unknown(
                f"request {request_index:03d} claims {cache_status} but "
                "no matching origin event exists"
            )
    return None


def check_bleed(
    *,
    first_request_index: int,
    second_request_index: int,
    experiment_id: str,
    baseline_correct: bool,
    first_correct: bool,
    first_cache_status: str | None,
    first_cache_entry_id: str | None,
    first_body_sha256: str,
    second_cache_status: str | None,
    second_cache_entry_id: str | None,
    second_cache_key_sha256: str | None,
    second_body_sha256: str,
    second_response_content_type: str,
    second_origin_counter_before: int,
    second_origin_counter_after: int,
    second_origin_counter_delta: int,
    second_sentinel_match: bool,
    first_expected_content_type: str,
    requested_representation: str,
) -> Diagnostic | None:
    """§8.2 REPRESENTATION_BLEED.

    Fires only when *all seven* §8.2 conditions hold:

    1. both origin baselines correct;
    2. the first warm request correct;
    3. the second warm request got the *other* representation (its
       body hash equals the first request's body hash, its
       Content-Type equals the first representation's expected
       Content-Type, and its own Sentinel is absent);
    4. the proxy header confirms HIT (verified state HIT);
    5. the origin counter did not move for the second request;
    6. the cache entry is the first request's entry (equal, non-null
       entry ids);
    7. (folded into 3) the second response's Sentinel evidence
       matches the first representation.

    The first request must itself be a confirmed MISS: only a MISS
    stores the entry a later HIT can reuse (a BYPASS stores
    nothing). Any missing link — including a missing entry id —
    fails closed to None: an unproven bleed is never reported as a
    proven one (§8.2, §9.6 step 5).
    """
    if not baseline_correct:
        return None
    if not first_correct:
        return None
    if first_cache_status != "MISS":
        return None
    if second_cache_status != "HIT":
        return None
    if second_origin_counter_delta != 0:
        return None
    if (
        first_cache_entry_id is None
        or second_cache_entry_id is None
        or first_cache_entry_id != second_cache_entry_id
    ):
        return None
    if second_body_sha256 != first_body_sha256:
        return None
    if not _content_type_matches(
        second_response_content_type, first_expected_content_type
    ):
        return None
    if second_sentinel_match:
        return None
    return make_diagnostic(
        "REPRESENTATION_BLEED",
        f"warm-cache request {second_request_index:03d} for "
        f"{requested_representation} was served the other "
        f"representation from a verified HIT of the entry stored by "
        f"request {first_request_index:03d}",
        experiment_id=experiment_id,
        request_index=second_request_index,
        evidence={
            "experiment_id": experiment_id,
            "requested_representation": requested_representation,
            "observed_representation": (
                "markdown" if requested_representation == "html" else "html"
            ),
            "cache_status": "HIT",
            "cache_key_sha256": second_cache_key_sha256,
            "cache_entry_id": second_cache_entry_id,
            "origin_counter_before": second_origin_counter_before,
            "origin_counter_after": second_origin_counter_after,
            "origin_counter_delta": second_origin_counter_delta,
            "sentinel_match": False,
            "body_sha256": second_body_sha256,
            "first_request_index": first_request_index,
        },
    )


def check_no_store_policy(
    *,
    request_index: int,
    experiment_id: str,
    cache_status: str | None,
    cache_entry_count_before: int | None = None,
    cache_entry_count_after: int | None = None,
    cache_entry_id: str | None = None,
    cache_control: str | None = None,
) -> Diagnostic | None:
    """§8.9 CACHE_POLICY_MISMATCH (``no_store`` leg).

    Fires when a confirmed MISS (which creates a cache entry) or a
    confirmed HIT (which reuses one) is observed under a ``no_store``
    contract. Returns None for BYPASS, for unconfirmed states
    (UNKNOWN / conflict — storage cannot be proven from them), and
    for a ``None`` state.
    """
    if cache_status not in ("MISS", "HIT"):
        return None
    return make_diagnostic(
        "CACHE_POLICY_MISMATCH",
        f"contract declares no_store but request {request_index:03d} "
        f"was {cache_status} — the proxy stored or reused a response",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "declared_cache_mode": "no_store",
            "observed_cache_status": cache_status,
            "cache_entry_count_before": cache_entry_count_before,
            "cache_entry_count_after": cache_entry_count_after,
            "cache_entry_id": cache_entry_id,
            "cache_control": cache_control,
        },
    )


def check_variant_by_accept_policy(
    *,
    request_index: int,
    experiment_id: str,
    cache_status: str | None,
    cache_entry_count_before: int | None = None,
    cache_entry_count_after: int | None = None,
    cache_entry_id: str | None = None,
    cache_control: str | None = None,
    vary: str | None = None,
) -> Diagnostic | None:
    """§8.9 CACHE_POLICY_MISMATCH (``variant_by_accept`` leg).

    Fires when a *confirmed* BYPASS is observed under a
    ``variant_by_accept`` contract. §5.4/§6.1 expect a cold or warm
    request under this mode to be MISS: a BYPASS means the cache
    never stored anything, so per-representation isolation was never
    exercised at all — certifying such a run PASS would authenticate
    isolation that was never tested (the ``disabled`` proxy mode
    under a variant contract is exactly this shape). Returns None
    for MISS/HIT (the mode's normal states), for unconfirmed states
    (UNKNOWN / conflict / ``None`` — a BYPASS that was not confirmed
    with dual evidence is an evidence problem, §8.4, not a proven
    policy violation), and under any other contract mode. The caller
    must pass only the *confirmed* state (see
    ``accepttwin.classifier``), never the raw claimed state.

    ``Vary: *`` exemption (T008, ADR-004, PROJECT_BOOK §11.3 E03):
    when the response's ``Vary`` contains ``*``, RFC 9111 §4.1
    forbids reusing the stored response at all, so *not* storing it
    (BYPASS) is the compliant outcome, not a policy violation — the
    isolation argument is moot because no entry exists to be reused,
    and every response is still judged on its own status /
    Content-Type / Sentinel. Pass the response's Vary value as
    ``vary`` (``None`` = unknown / not supplied, which does *not*
    exempt); a ``"*"`` token anywhere in the comma-separated value
    exempts this request.
    """
    if cache_status != "BYPASS":
        return None
    if vary is not None and "*" in [
        token.strip() for token in vary.split(",")
    ]:
        return None
    return make_diagnostic(
        "CACHE_POLICY_MISMATCH",
        f"contract declares variant_by_accept but request "
        f"{request_index:03d} was BYPASS — the proxy stored nothing, "
        "so per-representation cache isolation was never exercised",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "declared_cache_mode": "variant_by_accept",
            "observed_cache_status": "BYPASS",
            "cache_entry_count_before": cache_entry_count_before,
            "cache_entry_count_after": cache_entry_count_after,
            "cache_entry_id": cache_entry_id,
            "cache_control": cache_control,
        },
    )


def check_unexpected_hit(
    *,
    request_index: int,
    experiment_id: str,
    requested_representation: str,
    cache_status: str | None,
    response_status: int,
    response_content_type: str,
    sentinel_match: bool,
    expected_status: int,
    expected_content_type: str,
    reset_confirmed: bool,
) -> Diagnostic | None:
    """§8.3 CONTRACT_MISMATCH (unexpected-HIT leg).

    Fires when a request that must start from an empty cache — a cold
    request (003/004) or a warm first request (005/007) — or a warm
    second request (006/008) served its *correct* representation, is
    nevertheless a confirmed HIT. After a confirmed reset no entry
    for that representation can exist, so the HIT contradicts the
    cold-cache premise (§5.4). Returns None for MISS/BYPASS, for
    unconfirmed states, for a HIT serving the *wrong* representation
    (that is §8.2's job, via ``check_bleed``), and when the reset was
    not confirmed (then the HIT may be a stale entry from a failed
    reset, which is an evidence problem, not a proven violation).
    """
    if cache_status != "HIT" or not reset_confirmed:
        return None
    if not _representation_correct(
        response_status=response_status,
        response_content_type=response_content_type,
        sentinel_match=sentinel_match,
        expected_status=expected_status,
        expected_content_type=expected_content_type,
    ):
        return None
    return make_diagnostic(
        "CONTRACT_MISMATCH",
        f"request {request_index:03d} for {requested_representation} "
        "was a HIT immediately after a confirmed cache reset, but no "
        "entry for that representation could exist yet",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "stage": experiment_id,
            "requested_representation": requested_representation,
            "expected": {
                "status": expected_status,
                "content_type": expected_content_type,
            },
            "observed": {
                "status": response_status,
                "content_type": response_content_type,
            },
            "expected_status": expected_status,
            "observed_status": response_status,
            "response_status": response_status,
            "expected_content_type": expected_content_type,
            "observed_content_type": response_content_type,
            "response_content_type": response_content_type,
            "cache_status": "HIT",
            "sentinel_match": sentinel_match,
        },
    )


def check_inconclusive_limit(
    *,
    request_index: int | None,
    experiment_id: str | None,
    limit_code: str,
    response_status: int | None = None,
    body_size: int | None = None,
    supported_limit: int | None = None,
    transport_error: str | None = None,
    detail: str = "",
    request_url: str | None = None,
    redirect_target: str | None = None,
) -> Diagnostic | None:
    """§8.6 INCONCLUSIVE_LIMIT.

    Fires for exactly one *limit_code* at a time; the caller decides
    which out-of-scope condition applies. Returns None only when
    *limit_code* is empty (no limit was hit) — every named limit is
    by definition out of the supported range, so a named code always
    produces the diagnostic.

    ``request_url`` is the §8.6 evidence field of the same name; it
    is only available when the caller has a RawObservation (which
    carries ``url``) — the frozen RequestObservation has no URL
    field, so callers that only have frozen observations must leave
    it ``None`` (unknown, never guessed; see ADR-002). Likewise
    ``redirect_target`` is only recorded when the caller has a
    verified Location value.
    """
    if not limit_code:
        return None
    message = (
        f"out of supported range ({limit_code})"
        + (f": {detail}" if detail else "")
    )
    evidence: dict[str, Any] = {"limit_code": limit_code}
    if request_url is not None:
        evidence["request_url"] = request_url
    if redirect_target is not None:
        evidence["redirect_target"] = redirect_target
    if response_status is not None:
        evidence["response_status"] = response_status
    if body_size is not None:
        evidence["body_size"] = body_size
    if supported_limit is not None:
        evidence["supported_limit"] = supported_limit
    if transport_error is not None:
        evidence["transport_error"] = transport_error
    return make_diagnostic(
        "INCONCLUSIVE_LIMIT",
        message,
        experiment_id=experiment_id,
        request_index=request_index,
        evidence=evidence,
    )


def check_vary(
    *,
    request_index: int,
    experiment_id: str,
    requested_representation: str,
    vary_accept_present: bool,
    vary_accept_required: bool,
    cacheable: bool,
) -> Diagnostic | None:
    """§8.7 VARY_ACCEPT_ABSENT — or CONTRACT_MISMATCH when required.

    * Not cacheable (``no_store``) or Vary present: None — there is
      nothing to warn about.
    * Cacheable, Vary absent, contract requires it (§5.2): a
      CONTRACT_MISMATCH — a contract violation, but still never a
      REPRESENTATION_BLEED (I-11).
    * Cacheable, Vary absent, contract merely advisory / not
      required: a VARY_ACCEPT_ABSENT WARNING. This never changes a
      verdict on its own (§8.7, I-09).
    """
    if not cacheable or vary_accept_present:
        return None
    if vary_accept_required:
        return make_diagnostic(
            "CONTRACT_MISMATCH",
            f"contract requires Vary: Accept but the origin response "
            f"for request {request_index:03d} does not declare it",
            experiment_id=experiment_id,
            request_index=request_index,
            evidence={
                "stage": experiment_id,
                "requested_representation": requested_representation,
                "expected": "Vary: Accept",
                "observed": None,
                "vary_accept": "required",
            },
        )
    return make_diagnostic(
        "VARY_ACCEPT_ABSENT",
        f"origin response for request {request_index:03d} does not "
        "declare Vary: Accept; the cache must still be judged by its "
        "actual behaviour, not by this header alone (I-11)",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={"vary_accept": "advisory"},
    )


def check_reset_evidence(
    reset_evidence: list[Any] | tuple[Any, ...] | None,
) -> Diagnostic | None:
    """§8.4 CACHE_STATE_UNKNOWN (reset leg).

    Fires when no reset was recorded at all (``None`` is tolerated
    as "not supplied" and returns None; an empty list means the run
    recorded no confirmed reset) or when any recorded reset failed
    (``success`` false or entries left behind). A failed reset means
    no later cold-cache claim can be trusted (§5.3 D, §11.2 C23).
    Returns None when every recorded reset succeeded with zero
    entries left — or when the caller supplied no reset evidence at
    all (``None``).
    """
    if reset_evidence is None:
        return None
    if len(reset_evidence) == 0:
        return make_diagnostic(
            "CACHE_STATE_UNKNOWN",
            "no cache reset was recorded, so no cold-cache claim can "
            "be confirmed",
            evidence={
                "proxy_cache_header_present": None,
                "origin_journal_available": None,
                "origin_counter_delta": None,
                "cache_reset_confirmed": False,
                "evidence_conflict": False,
            },
        )
    for reset in reset_evidence:
        success = getattr(reset, "success", None)
        after = getattr(reset, "entries_after", None)
        if success is not True or after != 0:
            return make_diagnostic(
                "CACHE_STATE_UNKNOWN",
                "a cache reset did not reach a confirmed empty state "
                f"(namespace={getattr(reset, 'namespace', None)!r}, "
                f"success={success!r}, entries_after={after!r}), so "
                "cold-cache claims cannot be confirmed",
                evidence={
                    "proxy_cache_header_present": None,
                    "origin_journal_available": None,
                    "origin_counter_delta": None,
                    "cache_reset_confirmed": False,
                    "evidence_conflict": False,
                },
            )
    return None
