"""Production classifier (P032 T006).

Implements IMPLEMENTATION_PLAN §5.6 / T006 and PROJECT_BOOK §6.3,
§7, §8, §9, §10.2 (classification part):

* :func:`classify_run` — from a contract, the eight
  :class:`~accepttwin.evidence.RequestObservation` objects of one
  frozen four-experiment run, the origin events and the reset
  evidence, compute the five final verdicts of §9 in the §9.6
  priority order, the frozen §8 diagnostics, and the first-error
  request (§6.3).

Verdict priority (§9.6), applied literally:

1. input invalid or run out of scope → ``INCONCLUSIVE``;
2. direct-origin baseline error → ``ORIGIN_NEGOTIATION_ERROR``;
3. proven warm-cache bleed → ``REPRESENTATION_BLEED``;
4. other confirmed contract error → ``CONTRACT_MISMATCH``;
5. no problem above but key evidence insufficient → ``INCONCLUSIVE``;
6. everything conforms → ``PASS_OBSERVED``.

Fail-closed rules (the classifier never upgrades suspicion into a
proven fault):

* a bleed needs the full §8.2 chain — baseline correct, first warm
  request correct *and* a confirmed MISS, second request a verified
  HIT with counter delta 0, the same cache entry, and a body hash
  equal to the first request's body. Any missing link yields no
  bleed diagnostic at all;
* only a verified cache state (``MISS`` / ``HIT`` / ``BYPASS`` whose
  header leg and behaviour leg agree) counts as cache evidence. A
  claimed state contradicted by the origin counter is a
  ``CACHE_EVIDENCE_CONFLICT``, never a bleed and never a confirmed
  state;
* Vary alone never decides a verdict (I-11): a missing ``Vary:
  Accept`` is at most a WARNING (or a ``CONTRACT_MISMATCH`` when
  the contract *requires* it, §5.2), never a bleed;
* a lone 200 never means PASS (§9.5 needs baselines, cold requests,
  both warm orders, complete cache evidence and no CRITICAL);
* a Sentinel match alone never proves a HIT — a HIT needs the dual
  evidence of §5.3;
* when the evidence is insufficient the verdict is
  ``INCONCLUSIVE``, never a proven bleed.

Cache-policy rules (§8.9, two legs):

* under ``no_store`` a confirmed MISS (which creates an entry) or
  a confirmed HIT (which reuses one) is a
  ``CACHE_POLICY_MISMATCH``; a confirmed BYPASS is the expected
  behaviour and passes (C05/C06 shape);
* under ``variant_by_accept`` a *confirmed* BYPASS is a
  ``CACHE_POLICY_MISMATCH`` (§8.9 variant leg, ADR-002 P1-1):
  §5.4/§6.1 expect MISS there, and a BYPASS means the cache never
  stored anything, so per-representation isolation was never
  exercised. Only a BYPASS that survived dual-evidence
  verification counts — an unconfirmed BYPASS is an evidence
  problem (§8.4), never a proven policy violation. Exception
  (T008, ADR-004, §11.3 E03): a response whose ``Vary`` contains
  ``*`` must never be reused (RFC 9111 §4.1), so its BYPASS is
  compliant and exempts that request from this leg.

* a response carrying ``Cache-Control: no-cache`` or ``max-age=0``
  is out of scope (§8.6 ``revalidation_required``, T008, ADR-004,
  §11.3 E07/E08): the first release implements no revalidation, so
  the run is ``INCONCLUSIVE``, never PASS.

Vary fail-closed rule (§5.2, §9.6 step 5; ADR-002 P2-1): when the
contract requires ``Vary: Accept`` (``vary_accept == "required"``)
and whether Vary is present is *unknown* — neither
``raw_observations`` nor ``vary_accept_present`` was supplied, so
no Vary header was ever inspected — the run is ``INCONCLUSIVE``,
never PASS: the contract's own required evidence is missing, and
§5.2 states a missing ``Vary: Accept`` under ``required`` is a
contract violation, which cannot be ruled out without looking.
When Vary is known-absent under ``required`` the verdict is
``CONTRACT_MISMATCH`` instead (the violation is confirmed).

Calling convention for the optional evidence (ADR-002 P2-2,
route B): ``origin_events=None`` / ``reset_evidence=None`` mean
"the caller declares this cross-check is not performed" — the
classifier skips that check, it does *not* treat it as confirmed.
That meaning is reserved for unit tests; a production caller
(T007) must always pass the real ``run.origin_events`` /
``run.reset_evidence`` tuples and never pass ``None``. An empty
list/tuple is different: it means "the caller performed the check
and found nothing", which fails closed (no origin event →
``CACHE_STATE_UNKNOWN``; no reset recorded → ``CACHE_STATE_UNKNOWN``).

Body-size limit (§8.6, §17.4 1 MiB): the oversize-body check can
only run when ``raw_observations`` is supplied, because the frozen
:class:`RequestObservation` carries no body size. A production
caller (T007) must pass ``run.raw_observations``; without it that
one check cannot execute, and the classifier records this in the
module docstring and ADR-002 rather than guessing a size.

First-error location (§6.3): ``first_error`` is the smallest
request number (execution order 001–008) carrying any diagnostic
other than the advisory ``VARY_ACCEPT_ABSENT``. Diagnostics are
never re-ordered by severity and a later, more severe error never
rewrites the history: an origin-baseline error at 001/002 always
wins over a later cache problem, and secondary diagnostics are kept
alongside the final verdict, not hidden (§9.6).

Inputs beyond the frozen §5.6 signature are optional keyword-only
extensions, never requirements:

* ``raw_observations`` — the richer
  :class:`~accepttwin.evidence.RawObservation` records from the
  same run. They supply what :class:`RequestObservation` cannot
  carry: the ``Vary`` response header (for §8.7), the body size
  (for the §17.4 1 MiB limit), transport errors, and the raw
  cache-status header (to distinguish a header/behaviour conflict
  from merely missing evidence). Without them those three checks
  are skipped, never guessed. The body-size check has no other
  source at all, so a production caller (T007) **must** pass
  ``run.raw_observations`` — otherwise that check cannot execute
  (ADR-002 P2-1 note).
* ``vary_accept_present`` — an explicit per-request ``Vary:
  Accept`` map, an alternative to ``raw_observations`` for the
  §8.7 check.

``cache_status is None`` on a baseline request means "direct-origin
request, no cache evidence exists" (ADR-001) and is never read as a
cache state, never inferred from, and never conflated with
``"CACHE_STATE_UNKNOWN"``. A ``None`` on a *proxied* request is a
missing evidence leg (§8.4).

No body text is ever read, stored or emitted here (§7.12 I-12):
only hashes, statuses, counters and match flags.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .contract import Contract, Representation, validate_contract
from .diagnostics import (
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
    make_diagnostic,
    sort_diagnostics,
)
from .evidence import RawObservation, RequestObservation

__all__ = [
    "ClassificationResult",
    "VERDICTS",
    "classify_run",
]

#: The five frozen final verdicts (§9), in §9.6 priority order.
VERDICTS: tuple[str, ...] = (
    "INCONCLUSIVE",
    "ORIGIN_NEGOTIATION_ERROR",
    "REPRESENTATION_BLEED",
    "CONTRACT_MISMATCH",
    "PASS_OBSERVED",
)

#: Request numbers of the direct-origin baselines (§6.3).
_BASELINE_REQUESTS = (1, 2)

#: Request numbers of the cold requests (§6.3).
_COLD_REQUESTS = (3, 4)

#: (first, second) request numbers of the two warm experiments (§6.3).
_WARM_PAIRS = ((5, 6), (7, 8))

#: Request numbers of the warm first requests.
_WARM_FIRST_REQUESTS = (5, 7)

#: Request numbers of the warm second requests.
_WARM_SECOND_REQUESTS = (6, 8)

#: Expected number of observations in one complete run (§6.3: 001–008).
_EXPECTED_OBSERVATIONS = 8


@dataclass(frozen=True)
class ClassificationResult:
    """The outcome of classifying one complete run (§9, §6.3).

    ``diagnostics`` are in deterministic order
    (:func:`accepttwin.diagnostics.sort_diagnostics`). ``first_error``
    is the smallest request number carrying a violation diagnostic
    (any diagnostic except the advisory ``VARY_ACCEPT_ABSENT``), or
    ``None`` when no request violated the contract;
    ``first_error_experiment_id`` is that request's experiment.
    ``reasons`` explains, in verdict-priority order, why this
    verdict was reached. Nothing here carries body text (§7.12).
    ``confirmed_cache_states`` is the per-request cache state the
    classifier was willing to trust (T014, T013-F02): one
    ``{"request_index": n, "state": ...}`` entry per observation,
    with ``state`` the confirmed ``"MISS"`` / ``"HIT"`` /
    ``"BYPASS"`` or ``None`` when nothing was confirmed (baselines
    carry ``None`` per ADR-001). The Oracle parity check compares
    this list against the Oracle's own per-request states.
    """

    verdict: str
    diagnostics: tuple[Diagnostic, ...] = ()
    first_error: int | None = None
    first_error_experiment_id: str | None = None
    reasons: tuple[str, ...] = ()
    confirmed_cache_states: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"unknown verdict {self.verdict!r}")
        if self.first_error is not None and self.first_error < 1:
            raise ValueError("first_error must be a positive request number")

    @property
    def critical_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "CRITICAL")

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "WARNING")

    def diagnostic_codes(self) -> tuple[str, ...]:
        return tuple(d.code for d in self.diagnostics)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "diagnostics": [d.as_dict() for d in self.diagnostics],
            "first_error": self.first_error,
            "first_error_experiment_id": self.first_error_experiment_id,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "reasons": list(self.reasons),
            "confirmed_cache_states": [
                dict(entry) for entry in self.confirmed_cache_states
            ],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sentinel_sha256(sentinel: str) -> str:
    return hashlib.sha256(sentinel.encode("utf-8")).hexdigest()


def _vary_accept_present(headers: dict[str, str] | None) -> bool | None:
    """True when the response headers declare ``Vary: Accept``.

    Returns None when no header map was supplied (unknown, not
    absent). Header names are matched case-insensitively; the Vary
    value is split on commas and matched token-wise, so ``Vary:
    accept`` and ``Vary: Accept, Accept-Encoding`` both count.
    """
    if headers is None:
        return None
    for name, value in headers.items():
        if name.strip().lower() == "vary":
            tokens = [tok.strip().lower() for tok in value.split(",")]
            return "accept" in tokens or "*" in tokens
    return False


def _header_value(
    raw: RawObservation | None, name: str
) -> str | None:
    """Value of response header *name* (case-insensitive) from a raw
    observation, or None when no raw record was supplied or the
    header is absent. None means "unknown", never "absent".
    """
    if raw is None:
        return None
    for key, value in raw.response_headers.items():
        if key.strip().lower() == name.strip().lower():
            return value
    return None


def _requires_revalidation(raw: RawObservation | None) -> bool:
    """True when a raw response demands revalidation this release
    does not implement (§8.6, PROJECT_BOOK §11.3 E07/E08).

    ``Cache-Control: no-cache`` or ``max-age=0`` on a response means
    a cached copy must be revalidated before reuse; the first
    release implements no revalidation, so any run containing such a
    response is out of scope (``INCONCLUSIVE_LIMIT`` with limit code
    ``revalidation_required``), never PASS. Only the raw response
    headers can supply this — without a raw record the check cannot
    run and is skipped, never guessed.
    """
    cache_control = _header_value(raw, "cache-control")
    if cache_control is None:
        return False
    for token in cache_control.split(","):
        directive = token.strip().lower()
        if not directive:
            continue
        # RFC 9111-tolerant parsing (T014, T008 P2-2): whitespace
        # around the '=' and quoted-string parameters are stripped,
        # so `max-age = 0`, `max-age="0"` and `no-cache="field"` are
        # recognised exactly like their compact forms. A `no-cache`
        # directive triggers with or without a field-name parameter
        # (this release implements no revalidation at all, so any
        # revalidation demand is out of scope).
        name, sep, value = directive.partition("=")
        name = name.strip()
        value = value.strip().strip("\"'").strip()
        if name == "no-cache":
            return True
        if name == "max-age" and sep:
            try:
                if int(value) == 0:
                    return True
            except ValueError:
                continue
    return False


def _events_support(
    observation: RequestObservation,
    origin_events: list[Any] | tuple[Any, ...] | None,
    expected_accept: str,
) -> bool | None:
    """Cross-check one observation against the origin event log.

    The origin's event ``index`` equals its request counter after
    the request (§5.3: one event per request received), so the
    events belonging to *observation* are exactly those with an
    index in ``(origin_counter_before, origin_counter_after]``.
    Returns True when at least one such event carries the expected
    Accept and status, False when the bracket is non-empty but no
    event matches (or the bracket should be non-empty but holds no
    event at all), and None when the check does not apply (no event
    log supplied, or the observation reached no origin request, so
    no event is expected). A False here means the behaviour leg is
    missing — it downgrades the cache state to UNKNOWN, it never
    invents a state.
    """
    if origin_events is None:
        return None
    if observation.origin_counter_delta <= 0:
        return None
    bracket = [
        ev
        for ev in origin_events
        if observation.origin_counter_before
        < getattr(ev, "index", -1)
        <= observation.origin_counter_after
    ]
    if not bracket:
        return False
    return any(
        getattr(ev, "accept", None) == expected_accept
        and getattr(ev, "status", None) == observation.response_status
        for ev in bracket
    )


def _representation_correct(
    observation: RequestObservation, rep: Representation
) -> bool:
    return (
        observation.response_status == rep.expected_status
        and observation.response_content_type.strip().lower()
        == rep.expected_content_type.strip().lower()
        and observation.sentinel_match
    )


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


def classify_run(
    contract: Contract,
    observations: list[RequestObservation] | tuple[RequestObservation, ...],
    origin_events: list[Any] | tuple[Any, ...] | None,
    reset_evidence: list[Any] | tuple[Any, ...] | None,
    *,
    raw_observations: list[RawObservation] | tuple[RawObservation, ...] | None = None,
    vary_accept_present: dict[int, bool] | None = None,
) -> ClassificationResult:
    """Classify one complete four-experiment run (§9.6 priority).

    *contract* is the frozen dual-representation contract,
    *observations* the eight §5.5 observations in any order (they
    are sorted by request number here), *origin_events* the origin
    event log for the run, *reset_evidence* the four reset records.
    ``None`` for *origin_events* / *reset_evidence* means "the
    caller declares this cross-check is not performed" and the
    check is skipped — that meaning is reserved for unit tests
    (ADR-002 P2-2, route B); a production caller (T007) must pass
    the real ``run.origin_events`` / ``run.reset_evidence`` tuples
    and never pass ``None``. An empty list/tuple means "checked and
    found nothing" and fails closed (no origin event or no reset
    recorded → ``CACHE_STATE_UNKNOWN``). Optional
    ``raw_observations`` / ``vary_accept_present`` supply Vary,
    body-size, transport and raw-header detail the frozen
    observation cannot carry (see the module docstring); without
    them those checks are skipped, never guessed — except that a
    ``vary_accept == "required"`` contract with unknown Vary
    presence fails closed to ``INCONCLUSIVE`` (§9.6 step 5), and
    the §8.6 body-size check cannot run at all without
    ``raw_observations``, so T007 must pass
    ``run.raw_observations``.
    """
    diagnostics: list[Diagnostic] = []
    reasons: list[str] = []

    # -- §9.6 step 1: input validity ------------------------------------
    contract_result = validate_contract(contract)
    if not contract_result.ok:
        reasons.append("contract is invalid")
        diagnostics.append(
            make_diagnostic(
                "INCONCLUSIVE_LIMIT",
                "contract is invalid: " + "; ".join(contract_result.errors),
                evidence={
                    "limit_code": "invalid_contract",
                    "detail": "; ".join(contract_result.errors),
                },
            )
        )
        return _finish(
            "INCONCLUSIVE", diagnostics, reasons, observations_by_index={}
        )

    obs_list = list(observations or [])
    indices = [obs.request_index for obs in obs_list]
    if (
        len(obs_list) != _EXPECTED_OBSERVATIONS
        or sorted(indices) != list(range(1, _EXPECTED_OBSERVATIONS + 1))
        or len(set(indices)) != len(indices)
    ):
        reasons.append("observations are incomplete")
        diagnostics.append(
            make_diagnostic(
                "INCONCLUSIVE_LIMIT",
                "observations are incomplete: expected exactly requests "
                f"001–{_EXPECTED_OBSERVATIONS:03d} once each, got "
                f"{sorted(indices)}",
                evidence={"limit_code": "incomplete_observations"},
            )
        )
        return _finish(
            "INCONCLUSIVE", diagnostics, reasons, observations_by_index={}
        )

    by_index: dict[int, RequestObservation] = {
        obs.request_index: obs for obs in obs_list
    }
    by_raw: dict[int, RawObservation] = {}
    if raw_observations:
        for raw in raw_observations:
            by_raw.setdefault(raw.request_index, raw)

    mode = contract.cache_behavior.get("mode", "variant_by_accept")
    vary_mode = contract.cache_behavior.get("vary_accept", "advisory")
    vary_required = vary_mode == "required"
    cacheable = mode == "variant_by_accept"
    max_body = int(contract.limits.get("max_body_bytes", 1048576))

    def rep_for(obs: RequestObservation) -> Representation | None:
        return contract.representations.get(
            obs.requested_representation.strip().lower()
        )

    # -- per-request out-of-scope checks (§8.6, §9.6 step 1) -------------
    out_of_scope = False
    for index in sorted(by_index):
        obs = by_index[index]
        rep = rep_for(obs)
        if rep is None:
            diagnostics.append(
                make_diagnostic(
                    "INCONCLUSIVE_LIMIT",
                    f"request {index:03d} asks for unknown representation "
                    f"{obs.requested_representation!r}",
                    experiment_id=obs.experiment_id,
                    request_index=index,
                    evidence={"limit_code": "unknown_representation"},
                )
            )
            out_of_scope = True
            continue
        raw = by_raw.get(index)
        body_size = raw.body_size if raw is not None else None
        transport_error = raw.transport_error if raw is not None else None
        limit_code = ""
        detail = ""
        if transport_error is not None:
            limit_code = "transport_error"
            detail = transport_error
        elif obs.response_status == 0:
            limit_code = "transport_error"
            detail = "no HTTP response was received"
        elif 300 <= obs.response_status < 400:
            limit_code = "redirect"
            detail = (
                f"status {obs.response_status} (redirects are not "
                "followed in this release)"
            )
        elif body_size is not None and body_size > max_body:
            limit_code = "body_too_large"
            detail = (
                f"body size {body_size} exceeds the {max_body} byte limit"
            )
        elif _requires_revalidation(raw):
            limit_code = "revalidation_required"
            detail = (
                "response requires revalidation "
                f"(Cache-Control: {_header_value(raw, 'cache-control')}), "
                "which this release does not implement"
            )
        if limit_code:
            diagnostics.append(
                check_inconclusive_limit(
                    request_index=index,
                    experiment_id=obs.experiment_id,
                    limit_code=limit_code,
                    response_status=obs.response_status,
                    body_size=body_size,
                    supported_limit=max_body,
                    transport_error=transport_error,
                    detail=detail,
                    # §8.6 evidence (P2-3): the URL only exists on
                    # the raw record — the frozen observation has
                    # no URL field, so without raw records it stays
                    # unknown (ADR-002) rather than guessed.
                    request_url=raw.url if raw is not None else None,
                    redirect_target=(
                        _header_value(raw, "location")
                        if limit_code == "redirect"
                        else None
                    ),
                )
            )
            out_of_scope = True

    # -- reset evidence (§8.4, §11.2 C23) ---------------------------------
    reset_diagnostic = check_reset_evidence(reset_evidence)
    reset_confirmed = reset_diagnostic is None
    if reset_diagnostic is not None:
        diagnostics.append(reset_diagnostic)

    # -- cache-state verification per proxied request (§5.3, §8.4/§8.8) --
    # ``confirmed_state`` records the cache state the classifier is
    # willing to trust for downstream checks (bleed, policy). Any
    # observation whose state did not survive verification maps to
    # None here: downstream checks treat it as "unknown", never as
    # the claimed state.
    confirmed_state: dict[int, str | None] = {}
    for index in sorted(by_index):
        obs = by_index[index]
        if index in _BASELINE_REQUESTS:
            # ADR-001: direct-origin baselines carry None — no cache
            # evidence exists and none is required.
            confirmed_state[index] = None
            continue
        rep = rep_for(obs)
        if rep is None:
            confirmed_state[index] = None
            continue
        raw = by_raw.get(index)
        event_support = _events_support(
            obs, origin_events, rep.accept
        )
        diag = check_cache_state(
            request_index=index,
            experiment_id=obs.experiment_id,
            cache_status=obs.cache_status,
            origin_counter_delta=obs.origin_counter_delta,
            cache_key_sha256=obs.cache_key_sha256,
            cache_entry_id=obs.cache_entry_id,
            header_status=raw.cache_status_header if raw is not None else None,
            origin_event_present=(
                raw.origin_event_present if raw is not None else None
            ),
            cache_reset_confirmed=reset_confirmed,
        )
        if diag is not None:
            diagnostics.append(diag)
            confirmed_state[index] = None
            continue
        if event_support is False:
            diagnostics.append(
                make_diagnostic(
                    "CACHE_STATE_UNKNOWN",
                    f"request {index:03d} claims {obs.cache_status} but "
                    "no matching origin event exists for it",
                    experiment_id=obs.experiment_id,
                    request_index=index,
                    evidence={
                        "cache_status": obs.cache_status,
                        "origin_counter_delta": obs.origin_counter_delta,
                        "cache_key_sha256": obs.cache_key_sha256,
                        "cache_entry_id": obs.cache_entry_id,
                        # §8.4 evidence fields (P2-3).
                        "proxy_cache_header_present": (
                            raw.cache_status_header is not None
                            if raw is not None
                            else None
                        ),
                        # T014 (T006 P3): this branch is only reachable
                        # when origin_events is not None (see the
                        # guard above), so the journal is available
                        # by construction — write the literal True
                        # instead of a condition that is constant
                        # here.
                        "origin_journal_available": True,
                        "cache_reset_confirmed": reset_confirmed,
                        "evidence_conflict": False,
                    },
                )
            )
            confirmed_state[index] = None
            continue
        confirmed_state[index] = obs.cache_status

    # -- origin baselines (§8.1, §9.1) ------------------------------------
    baseline_correct = True
    origin_error = False
    for index in _BASELINE_REQUESTS:
        obs = by_index[index]
        rep = rep_for(obs)
        if rep is None:
            baseline_correct = False
            continue
        correct = _representation_correct(obs, rep)
        baseline_correct = baseline_correct and correct
        if obs.response_status == 0 or 300 <= obs.response_status < 400:
            # Out of scope (already diagnosed as INCONCLUSIVE_LIMIT);
            # a redirect/transport failure is not also an origin
            # negotiation error, but the baseline is not correct
            # either, so no bleed can be proven from this run.
            baseline_correct = False
            continue
        diag = check_origin_baseline(
            request_index=index,
            experiment_id=obs.experiment_id,
            requested_representation=obs.requested_representation,
            response_status=obs.response_status,
            response_content_type=obs.response_content_type,
            sentinel_match=obs.sentinel_match,
            expected_status=rep.expected_status,
            expected_content_type=rep.expected_content_type,
            expected_sentinel_sha256=_sentinel_sha256(rep.sentinel),
            body_sha256=obs.body_sha256,
        )
        if diag is not None:
            diagnostics.append(diag)
            origin_error = True

    # -- Sentinel, status and Content-Type per request (§8.3, §8.5) -------
    contract_error = False
    for index in sorted(by_index):
        obs = by_index[index]
        rep = rep_for(obs)
        if rep is None:
            continue
        if 300 <= obs.response_status < 400 or obs.response_status == 0:
            # Out of scope (already diagnosed); a redirect/transport
            # failure carries no meaningful Sentinel or contract
            # content to judge, so neither check runs here.
            continue
        diag = check_sentinel(
            request_index=index,
            experiment_id=obs.experiment_id,
            requested_representation=obs.requested_representation,
            sentinel_match=obs.sentinel_match,
            response_content_type=obs.response_content_type,
            expected_sentinel_sha256=_sentinel_sha256(rep.sentinel),
            body_sha256=obs.body_sha256,
        )
        if diag is not None:
            diagnostics.append(diag)
            contract_error = True
        if index in _BASELINE_REQUESTS:
            continue
        diag = check_contract_response(
            request_index=index,
            experiment_id=obs.experiment_id,
            requested_representation=obs.requested_representation,
            response_status=obs.response_status,
            response_content_type=obs.response_content_type,
            cache_status=obs.cache_status,
            sentinel_match=obs.sentinel_match,
            expected_status=rep.expected_status,
            expected_content_type=rep.expected_content_type,
        )
        if diag is not None:
            diagnostics.append(diag)
            contract_error = True

    # -- cache-policy and unexpected-HIT checks (§8.9, §8.3) --------------
    policy_error = False
    for index in sorted(by_index):
        obs = by_index[index]
        if index in _BASELINE_REQUESTS:
            continue
        rep = rep_for(obs)
        if rep is None:
            continue
        state = confirmed_state[index]
        raw = by_raw.get(index)
        if mode == "no_store":
            diag = check_no_store_policy(
                request_index=index,
                experiment_id=obs.experiment_id,
                cache_status=state,
                cache_entry_count_before=(
                    raw.cache_entry_count_before if raw is not None else None
                ),
                cache_entry_count_after=(
                    raw.cache_entry_count_after if raw is not None else None
                ),
                cache_entry_id=obs.cache_entry_id,
                cache_control=_header_value(raw, "cache-control"),
            )
            if diag is not None:
                diagnostics.append(diag)
                policy_error = True
        elif cacheable and state == "BYPASS":
            # P1-1 (§8.9 variant leg): a confirmed BYPASS under
            # variant_by_accept means the cache never stored
            # anything, so isolation was never exercised — a
            # CACHE_POLICY_MISMATCH, never a silent PASS. Only the
            # *confirmed* state reaches this branch: an unconfirmed
            # BYPASS is already a §8.4 evidence problem above.
            diag = check_variant_by_accept_policy(
                request_index=index,
                experiment_id=obs.experiment_id,
                cache_status=state,
                cache_entry_count_before=(
                    raw.cache_entry_count_before if raw is not None else None
                ),
                cache_entry_count_after=(
                    raw.cache_entry_count_after if raw is not None else None
                ),
                cache_entry_id=obs.cache_entry_id,
                cache_control=_header_value(raw, "cache-control"),
                # Vary: * exempts the BYPASS (ADR-004, §11.3 E03):
                # a response that must never be reused is compliant
                # when it is not stored.
                vary=_header_value(raw, "vary"),
            )
            if diag is not None:
                diagnostics.append(diag)
                policy_error = True
        elif cacheable and state == "HIT" and reset_confirmed:
            # A confirmed HIT where no entry could exist yet (cold,
            # warm-first) or where the served representation is the
            # requested one (warm-second, correct body) contradicts
            # the cold-cache premise. A HIT serving the *wrong*
            # representation is the bleed check's job, not this one.
            diag = check_unexpected_hit(
                request_index=index,
                experiment_id=obs.experiment_id,
                requested_representation=obs.requested_representation,
                cache_status=state,
                response_status=obs.response_status,
                response_content_type=obs.response_content_type,
                sentinel_match=obs.sentinel_match,
                expected_status=rep.expected_status,
                expected_content_type=rep.expected_content_type,
                reset_confirmed=reset_confirmed,
            )
            if diag is not None:
                diagnostics.append(diag)
                contract_error = True

    # -- warm-cache bleed (§8.2, §9.2) -------------------------------------
    bleed = False
    for first_index, second_index in _WARM_PAIRS:
        first = by_index[first_index]
        second = by_index[second_index]
        first_rep = rep_for(first)
        second_rep = rep_for(second)
        if first_rep is None or second_rep is None:
            continue
        first_correct = _representation_correct(first, first_rep)
        diag = check_bleed(
            first_request_index=first_index,
            second_request_index=second_index,
            experiment_id=second.experiment_id,
            baseline_correct=baseline_correct,
            first_correct=first_correct,
            first_cache_status=confirmed_state[first_index],
            first_cache_entry_id=first.cache_entry_id,
            first_body_sha256=first.body_sha256,
            second_cache_status=confirmed_state[second_index],
            second_cache_entry_id=second.cache_entry_id,
            second_cache_key_sha256=second.cache_key_sha256,
            second_body_sha256=second.body_sha256,
            second_response_content_type=second.response_content_type,
            second_origin_counter_before=second.origin_counter_before,
            second_origin_counter_after=second.origin_counter_after,
            second_origin_counter_delta=second.origin_counter_delta,
            second_sentinel_match=second.sentinel_match,
            first_expected_content_type=first_rep.expected_content_type,
            requested_representation=second.requested_representation,
        )
        if diag is not None:
            diagnostics.append(diag)
            bleed = True

    # -- Vary (§8.7, I-11) --------------------------------------------------
    # Only the origin baselines declare Vary; only cacheable contracts
    # care. A missing Vary is never invented: when neither an explicit
    # map nor a raw record supplies the header, presence is unknown.
    # The explicit map wins when it has a value; the raw headers are
    # the fallback when the map is silent for a request.
    vary_map: dict[int, bool | None] = {}
    for index in _BASELINE_REQUESTS:
        present: bool | None = None
        if vary_accept_present is not None:
            present = vary_accept_present.get(index)
        if present is None and index in by_raw:
            present = _vary_accept_present(by_raw[index].response_headers)
        vary_map[index] = present
    vary_unknown_required = False
    for index in _BASELINE_REQUESTS:
        present = vary_map[index]
        if present is None:
            if vary_required and cacheable:
                # P2-1 fail-closed (§5.2, §9.6 step 5): the contract
                # requires Vary: Accept, but no Vary header was ever
                # inspected for this baseline, so the required
                # violation can neither be confirmed nor ruled out.
                # The run is INCONCLUSIVE, never PASS.
                obs = by_index[index]
                diagnostics.append(
                    check_inconclusive_limit(
                        request_index=index,
                        experiment_id=obs.experiment_id,
                        limit_code="vary_accept_unknown",
                        detail=(
                            "contract requires Vary: Accept but no "
                            "Vary header was supplied for this "
                            "baseline (neither raw_observations nor "
                            "vary_accept_present); the required "
                            "evidence is missing"
                        ),
                    )
                )
                vary_unknown_required = True
            continue
        obs = by_index[index]
        rep = rep_for(obs)
        if rep is None:
            continue
        diag = check_vary(
            request_index=index,
            experiment_id=obs.experiment_id,
            requested_representation=obs.requested_representation,
            vary_accept_present=present,
            vary_accept_required=vary_required,
            cacheable=cacheable,
        )
        if diag is not None:
            diagnostics.append(diag)
            if diag.code == "CONTRACT_MISMATCH":
                contract_error = True

    # -- verdict (§9.6 priority, applied literally) ------------------------
    ordered = sort_diagnostics(diagnostics)
    evidence_insufficient = (
        any(
            d.code in ("CACHE_STATE_UNKNOWN", "CACHE_EVIDENCE_CONFLICT")
            for d in ordered
        )
        or vary_unknown_required
    )
    if out_of_scope:
        verdict = "INCONCLUSIVE"
        reasons.append("run left the supported range (redirect, "
                       "transport failure, oversize body, revalidation "
                       "required, or unknown representation)")
    elif origin_error:
        verdict = "ORIGIN_NEGOTIATION_ERROR"
        reasons.append("a direct-origin baseline violates the contract")
    elif bleed:
        verdict = "REPRESENTATION_BLEED"
        reasons.append("a warm-cache second request was served the other "
                       "representation from a verified HIT")
    elif contract_error or policy_error:
        verdict = "CONTRACT_MISMATCH"
        reasons.append("a response violates the contract but is neither a "
                       "proven origin error nor a proven bleed")
    elif evidence_insufficient:
        verdict = "INCONCLUSIVE"
        if vary_unknown_required:
            reasons.append(
                "the contract requires Vary: Accept but whether any "
                "baseline declares it is unknown — the required "
                "evidence was never supplied"
            )
        else:
            reasons.append("key cache evidence is missing or conflicting")
    else:
        verdict = "PASS_OBSERVED"
        reasons.append("baselines, cold requests and both warm orders are "
                       "correct with complete cache evidence and no "
                       "CRITICAL diagnostic")

    return _finish(
        verdict,
        list(ordered),
        reasons,
        observations_by_index=by_index,
        confirmed_state=confirmed_state,
    )


def _finish(
    verdict: str,
    diagnostics: list[Diagnostic],
    reasons: list[str],
    *,
    observations_by_index: dict[int, RequestObservation],
    confirmed_state: dict[int, str | None] | None = None,
) -> ClassificationResult:
    """Sort diagnostics, locate the first error (§6.3), build the result."""
    ordered = sort_diagnostics(diagnostics)
    first_error: int | None = None
    first_error_experiment_id: str | None = None
    for diag in ordered:
        # The advisory Vary warning is not a contract violation: a
        # healthy run carrying only that WARNING has no first error.
        if diag.code == "VARY_ACCEPT_ABSENT":
            continue
        if diag.request_index is not None:
            first_error = diag.request_index
            obs = observations_by_index.get(diag.request_index)
            first_error_experiment_id = (
                obs.experiment_id if obs is not None else diag.experiment_id
            )
            break
    return ClassificationResult(
        verdict=verdict,
        diagnostics=ordered,
        first_error=first_error,
        first_error_experiment_id=first_error_experiment_id,
        reasons=tuple(reasons),
        # T014 (T013-F02): expose the per-request states the
        # classifier trusted, normalised the same way as the Oracle
        # side ("CACHE_STATE_UNKNOWN" means "confirmed nothing").
        # Early returns (invalid contract / incomplete observations)
        # have no per-request verification yet, so they carry none.
        confirmed_cache_states=tuple(
            {
                "request_index": index,
                "state": (
                    None
                    if state in (None, "CACHE_STATE_UNKNOWN")
                    else state
                ),
            }
            for index, state in sorted((confirmed_state or {}).items())
        ),
    )
