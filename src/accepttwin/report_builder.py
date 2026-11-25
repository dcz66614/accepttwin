"""Formal machine report ``accepttwin.report/v1`` (P032 T009).

Implements IMPLEMENTATION_PLAN §5.8 / T009 and PROJECT_BOOK §14:

* :func:`build_report` — from a validated contract, the eight
  :class:`~accepttwin.evidence.RequestObservation` objects of one
  frozen four-experiment run, the production
  :class:`~accepttwin.classifier.ClassificationResult` and (when
  available) the independent Oracle result, build the formal
  machine report. The report carries no raw response body text
  (§7.12 I-12), no sensitive request header (§5.1.3, §17) and no
  non-loopback URL (§14.3).
* :func:`compute_report_hash` — ``SHA256(canonical_json_bytes)``
  (§10.4) over the report's hash payload (see below).

Canonical JSON — single source (ADR-003, T009): all normalisation
is :func:`accepttwin.contract.canonical_json_bytes`, reused here,
never re-implemented. The report's ``url`` / ``origin_url`` keep
their real (OS-assigned) ports — execution truth — and the
canonicaliser normalises those ports to 0 in the hash input
(ADR-003). No timestamp, duration, process id, temporary path or
random id is ever put in a report, so none can leak into the hash.

Report hash — what is excluded, and why (§10.4, ADR-003): the hash
input is the report minus :data:`REPORT_HASH_EXCLUDED_FIELDS`.
Those fields are all port-bearing or absolute-counter evidence
whose values cannot be port-normalised, because they are hashes or
copies of values that already contain an ephemeral port:

* ``cache_key_sha256`` — the cache key material is the origin URL
  (with its OS-assigned port) plus Accept (``cache_proxy``:
  ``cache_key_for``), so the key hash changes when the port
  changes; it is a hash, so no normaliser can rewrite it. The
  same holds for ``cache_entry_id``, which derives from the key
  (``entry-<first 16 hex>``). Both stay in the report itself
  (§5.3/§8 evidence, and §4.3 area C needs the cache-key summary)
  but never enter the hash.
* ``origin_counter_before`` / ``origin_counter_after`` — absolute
  counters. Only the delta is hashed, following the T007
  ``canonical_report`` precedent (absolute counters never enter
  the hash); the before/after values stay in the diagnostic
  evidence where §8.2 requires them.
* ``request_url`` / ``redirect_target`` — §8.6 evidence URLs that
  carry the run's ephemeral ports (E12/E22 shapes). They stay in
  the report (desensitised, see below) but never enter the hash.

Everything §10.4 requires in the hash still enters it: the input
contract hash, the scenario id, the four-experiment results, the
origin baselines, the cache-state evidence (state + delta),
diagnostic codes, the final verdict and the first-error location.

Privacy / desensitisation (§7.12, §8.6, §14.3, ADR-002 Decision 4):

* any forbidden key — raw body text (``body``, ``body_text``,
  ``response_body``) or a sensitive header (``authorization``,
  ``cookie``, ``proxy-authorization``, ``set-cookie``), matched
  case-insensitively at any depth of any input — raises
  :class:`ReportError`. A report is never built around forbidden
  content.
* ``redirect_target``: a non-loopback target is never recorded
  verbatim (§8.6: "only a verified desensitised address"); it is
  replaced with the fixed marker :data:`REDACTED_REDIRECT_TARGET`.
  A loopback target is kept (it is still excluded from the hash
  input, see above). A ``request_url`` that is not loopback is
  dropped rather than recorded.

Oracle parity (§4.2 constraint 6, §12.4): a report is marked
``final`` only when an Oracle result was supplied *and* it agrees
with production on verdict, diagnostic projection (code +
request_index, §8 order) and first-error location. Without an
Oracle result the report is still a complete, schema-valid record
of the run, but ``oracle`` is null, ``oracle_parity`` is null and
``final`` is false — never final-valid on production's say-so
alone.

This module deliberately has **no** ``validate`` method: report
validation is independent of the production generator (T009
acceptance). The independent checker lives in
``tests/unit/independent_schema_validator.py`` — it reads only the
Schema file and never imports this module.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from .canonical_json import canonical_json_bytes
from .classifier import VERDICTS, ClassificationResult
from .contract import (
    Contract,
    canonical_contract_hash,
    parse_contract,
    validate_contract,
)
from .diagnostics import (
    CODE_SEVERITY,
    DIAGNOSTIC_CODES,
    Diagnostic,
    diagnostic_order,
)
from .evidence import RequestObservation
from .url_guard import URLGuardError, validate_loopback_url

__all__ = [
    "REDACTED_REDIRECT_TARGET",
    "REPORT_HASH_EXCLUDED_FIELDS",
    "REPORT_SCHEMA",
    "ReportError",
    "build_report",
    "compute_report_hash",
    "report_hash_payload",
]

#: Schema identifier of every report this module builds (§14.3).
REPORT_SCHEMA = "accepttwin.report/v1"

#: Marker written in place of a non-loopback ``redirect_target``
#: (§8.6: only a verified desensitised address may be recorded).
REDACTED_REDIRECT_TARGET = "redacted:non-loopback"

#: Field names removed from the hash payload at any depth (§10.4,
#: ADR-003 — see the module docstring for why each is excluded).
REPORT_HASH_EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {
        "cache_key_sha256",
        "cache_entry_id",
        "origin_counter_before",
        "origin_counter_after",
        "request_url",
        "redirect_target",
    }
)

#: Keys that must never appear in a report, at any depth, matched
#: case-insensitively (§7.12 I-12: no raw body text; §5.1.3/§17: no
#: sensitive request headers).
_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "body",
        "body_text",
        "response_body",
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
    }
)

#: The six frozen experiment ids (§6.3).
EXPERIMENT_IDS: tuple[str, ...] = (
    "ORIGIN_HTML",
    "ORIGIN_MARKDOWN",
    "HTML_COLD",
    "MARKDOWN_COLD",
    "HTML_TO_MARKDOWN",
    "MARKDOWN_TO_HTML",
)

#: Expected number of observations in one complete run (§6.3).
_EXPECTED_OBSERVATIONS = 8


class ReportError(ValueError):
    """Raised when a report cannot be built fail-closed."""


# ---------------------------------------------------------------------------
# Input normalisation
# ---------------------------------------------------------------------------


def _reject_forbidden_keys(value: Any, where: str = "report input") -> None:
    """Recursively reject any :data:`_FORBIDDEN_KEYS` key in *value*."""
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ReportError(
                    f"report must not contain a {key!r} field ({where})"
                )
            _reject_forbidden_keys(item, f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_forbidden_keys(item, f"{where}[{index}]")


def _is_loopback_url(value: Any) -> bool:
    """True when *value* is an ``http`` URL whose host is loopback."""
    if not isinstance(value, str):
        return False
    try:
        validate_loopback_url(value)
    except (URLGuardError, ValueError):
        return False
    return True


def _sanitise_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Copy *evidence*, desensitising URL-bearing fields (§8.6).

    A non-loopback ``redirect_target`` is replaced with
    :data:`REDACTED_REDIRECT_TARGET` (never recorded verbatim); a
    non-loopback ``request_url`` is dropped. Loopback values are
    kept — they are still excluded from the hash input (see
    :data:`REPORT_HASH_EXCLUDED_FIELDS`), so their ephemeral ports
    cannot change the report hash.
    """
    cleaned = copy.deepcopy(evidence)
    if "redirect_target" in cleaned:
        target = cleaned["redirect_target"]
        if target is not None and not _is_loopback_url(target):
            cleaned["redirect_target"] = REDACTED_REDIRECT_TARGET
    if "request_url" in cleaned:
        if not _is_loopback_url(cleaned["request_url"]):
            del cleaned["request_url"]
    return cleaned


def _coerce_contract(contract: Contract | dict[str, Any]) -> Contract:
    """Return a validated :class:`Contract` for *contract*.

    A dict is parsed (and therefore fully validated) with
    :func:`parse_contract`; an instance is re-validated. Anything
    invalid fails here, before any report field is built.
    """
    if isinstance(contract, dict):
        try:
            return parse_contract(contract)
        except ValueError as exc:
            raise ReportError(f"invalid contract for report: {exc}") from exc
    if not isinstance(contract, Contract):
        raise ReportError(f"contract must be a Contract or dict, got {type(contract).__name__}")
    result = validate_contract(contract)
    if not result.ok:
        raise ReportError(
            "invalid contract for report: " + "; ".join(result.errors)
        )
    return contract


def _coerce_observation(obs: RequestObservation | dict[str, Any]) -> dict[str, Any]:
    """Project one observation to the frozen report shape (§5.5/§14)."""
    if isinstance(obs, RequestObservation):
        data = obs.as_dict()
    elif isinstance(obs, dict):
        data = dict(obs)
    else:
        raise ReportError(
            f"observation must be a RequestObservation or dict, got {type(obs).__name__}"
        )
    required = (
        "request_index",
        "experiment_id",
        "requested_representation",
        "response_status",
        "response_content_type",
        "body_sha256",
        "sentinel_match",
        "cache_status",
        "cache_key_sha256",
        "cache_entry_id",
        "origin_counter_delta",
    )
    missing = [key for key in required if key not in data]
    if missing:
        raise ReportError(
            f"observation {data.get('request_index')!r} is missing fields: {missing}"
        )
    if not isinstance(data["request_index"], int) or isinstance(
        data["request_index"], bool
    ):
        raise ReportError("request_index must be an integer")
    if data["request_index"] < 1:
        raise ReportError("request_index must be a positive integer")
    if data["experiment_id"] not in EXPERIMENT_IDS:
        raise ReportError(f"unknown experiment_id {data['experiment_id']!r}")
    if data["requested_representation"] not in ("html", "markdown"):
        raise ReportError(
            f"unknown requested_representation {data['requested_representation']!r}"
        )
    _reject_forbidden_keys(data, "observation")
    return {key: data[key] for key in required}


def _coerce_diagnostic(diag: Diagnostic | dict[str, Any]) -> dict[str, Any]:
    """Project one diagnostic to the frozen report shape (§8/§14)."""
    if isinstance(diag, Diagnostic):
        data = diag.as_dict()
    elif isinstance(diag, dict):
        data = dict(diag)
    else:
        raise ReportError(
            f"diagnostic must be a Diagnostic or dict, got {type(diag).__name__}"
        )
    for key in ("code", "severity", "message"):
        if key not in data:
            raise ReportError(f"diagnostic is missing {key!r}")
    if data["code"] not in DIAGNOSTIC_CODES:
        raise ReportError(f"unknown diagnostic code {data['code']!r}")
    if data["severity"] not in ("CRITICAL", "WARNING"):
        raise ReportError(f"unknown severity {data['severity']!r}")
    if CODE_SEVERITY[data["code"]] != data["severity"]:
        raise ReportError(
            f"diagnostic {data['code']} must have severity "
            f"{CODE_SEVERITY[data['code']]!r}, got {data['severity']!r}"
        )
    if not isinstance(data["message"], str) or not data["message"].strip():
        raise ReportError("diagnostic message must not be blank")
    experiment_id = data.get("experiment_id")
    if experiment_id is not None and experiment_id not in EXPERIMENT_IDS:
        raise ReportError(f"unknown experiment_id {experiment_id!r}")
    request_index = data.get("request_index")
    if request_index is not None and (
        not isinstance(request_index, int)
        or isinstance(request_index, bool)
        or request_index < 1
    ):
        raise ReportError("diagnostic request_index must be a positive integer or null")
    evidence = data.get("evidence", {})
    if not isinstance(evidence, dict):
        raise ReportError("diagnostic evidence must be an object")
    _reject_forbidden_keys(evidence, f"diagnostic {data['code']} evidence")
    return {
        "code": data["code"],
        "severity": data["severity"],
        "message": data["message"],
        "experiment_id": experiment_id,
        "request_index": request_index,
        "evidence": _sanitise_evidence(evidence),
    }


def _diagnostic_projection(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Diagnostics as sorted ``{code, request_index}`` pairs (§12.4)."""
    pairs = [
        {"code": d["code"], "request_index": d["request_index"]}
        for d in diagnostics
    ]
    return sorted(
        pairs,
        key=lambda p: (
            p["request_index"] is None,
            p["request_index"] if p["request_index"] is not None else 0,
            diagnostic_order(p["code"]),
        ),
    )


def _coerce_oracle(oracle_result: Any) -> dict[str, Any] | None:
    """Project an Oracle result to the report's oracle block (§12.4).

    Accepts a dict (the ``oracle.json`` shape) or an object with an
    ``as_dict()`` method. Returns None when *oracle_result* is None.
    """
    if oracle_result is None:
        return None
    if hasattr(oracle_result, "as_dict"):
        data = oracle_result.as_dict()
    elif isinstance(oracle_result, dict):
        data = dict(oracle_result)
    else:
        raise ReportError(
            "oracle_result must be a dict, an object with as_dict(), or None; "
            f"got {type(oracle_result).__name__}"
        )
    _reject_forbidden_keys(data, "oracle result")
    if data.get("verdict") not in VERDICTS:
        raise ReportError(f"oracle verdict {data.get('verdict')!r} is not one of the five frozen verdicts")
    first_error = data.get("first_error")
    if first_error is not None and (
        not isinstance(first_error, int)
        or isinstance(first_error, bool)
        or first_error < 1
    ):
        raise ReportError("oracle first_error must be a positive integer or null")
    first_error_experiment_id = data.get("first_error_experiment_id")
    if (
        first_error_experiment_id is not None
        and first_error_experiment_id not in EXPERIMENT_IDS
    ):
        raise ReportError(
            f"unknown oracle first_error_experiment_id {first_error_experiment_id!r}"
        )
    return {
        "verdict": data["verdict"],
        "first_error": first_error,
        "first_error_experiment_id": first_error_experiment_id,
    }


def _normalise_oracle_cache_states(value: Any) -> list[dict[str, Any]] | None:
    """Normalise an Oracle ``verified_cache_states`` value, or None
    when it is not a well-formed 8-entry list (T014, T013-F02 —
    fail-closed: the caller treats None as a parity failure)."""
    if not isinstance(value, list) or len(value) != 8:
        return None
    states = []
    for entry in value:
        if not isinstance(entry, dict):
            return None
        index = entry.get("request_index")
        state = entry.get("state")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 1
            or index > 8
            or (state is not None and state not in ("MISS", "HIT", "BYPASS"))
        ):
            return None
        states.append({"request_index": index, "state": state})
    states.sort(key=lambda s: s["request_index"])
    if [s["request_index"] for s in states] != list(range(1, 9)):
        return None
    return states


def _production_cache_states(
    production: dict[str, Any],
) -> list[dict[str, Any]] | None:
    """Per-request verified cache states from the production result,
    normalised the same way as the Oracle side (T014, T013-F02).

    These are the states the production *classifier* trusted
    (``ClassificationResult.confirmed_cache_states``) — not the
    runner's observation-layer states, which the classifier may
    have downgraded. ``"CACHE_STATE_UNKNOWN"`` and ``None`` both
    mean "confirmed nothing". Returns None when the production
    result carries no well-formed 8-entry list (fail-closed).
    """
    value = production.get("confirmed_cache_states")
    if not isinstance(value, list) or len(value) != 8:
        return None
    states = []
    for entry in value:
        if not isinstance(entry, dict):
            return None
        index = entry.get("request_index")
        state = entry.get("state")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 1
            or index > 8
            or (
                state is not None
                and state not in ("MISS", "HIT", "BYPASS", "CACHE_STATE_UNKNOWN")
            )
        ):
            return None
        if state == "CACHE_STATE_UNKNOWN":
            state = None
        states.append({"request_index": index, "state": state})
    states.sort(key=lambda s: s["request_index"])
    if [s["request_index"] for s in states] != list(range(1, 9)):
        return None
    return states


def _oracle_parity(
    production_verdict: str,
    production_diagnostics: list[dict[str, Any]],
    production_first_error: int | None,
    production_first_error_experiment_id: str | None,
    oracle: dict[str, Any],
    oracle_diagnostics: list[dict[str, Any]],
    production_cache_states: list[dict[str, Any]] | None = None,
    oracle_cache_states: Any = None,
) -> bool:
    """True when production and Oracle agree per §12.4.

    Compared: final verdict, diagnostic projection (code +
    request_index), first-error request and first-error experiment,
    and — since T014 / T013-F02 — the per-request verified
    MISS/HIT/BYPASS states. An Oracle result without well-formed
    per-request states fails parity (fail-closed): a state
    disagreement must no longer pass silently behind identical
    verdicts/diagnostics.
    """
    if oracle["verdict"] != production_verdict:
        return False
    if oracle_diagnostics != _diagnostic_projection(production_diagnostics):
        return False
    if oracle["first_error"] != production_first_error:
        return False
    if (
        oracle["first_error_experiment_id"]
        != production_first_error_experiment_id
    ):
        return False
    if production_cache_states is None:
        return False
    oracle_states = _normalise_oracle_cache_states(oracle_cache_states)
    if oracle_states is None:
        return False
    if oracle_states != production_cache_states:
        return False
    return True


# ---------------------------------------------------------------------------
# Report hash (§10.4)
# ---------------------------------------------------------------------------


def _strip_excluded(value: Any) -> Any:
    """Deep-copy *value* with :data:`REPORT_HASH_EXCLUDED_FIELDS` removed."""
    if isinstance(value, dict):
        return {
            key: _strip_excluded(item)
            for key, item in value.items()
            if key not in REPORT_HASH_EXCLUDED_FIELDS
        }
    if isinstance(value, list):
        return [_strip_excluded(item) for item in value]
    return value


def report_hash_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Return the hash payload for *report*: the report without its
    own ``report_hash`` field and without every field in
    :data:`REPORT_HASH_EXCLUDED_FIELDS` (at any depth). The
    ``url`` / ``origin_url`` ports in the payload are normalised to
    0 by :func:`canonical_json_bytes` itself (ADR-003).
    """
    payload = {key: value for key, value in report.items() if key != "report_hash"}
    return _strip_excluded(payload)


def compute_report_hash(report: dict[str, Any]) -> str:
    """Return ``SHA256(canonical_json_bytes(hash payload))`` (§10.4)."""
    if not isinstance(report, dict):
        raise ReportError("report must be a JSON object")
    return hashlib.sha256(
        canonical_json_bytes(report_hash_payload(report))
    ).hexdigest()


# ---------------------------------------------------------------------------
# Report construction (§5.8, §14)
# ---------------------------------------------------------------------------


def build_report(
    contract: Contract | dict[str, Any],
    production_result: ClassificationResult | dict[str, Any],
    oracle_result: Any = None,
    *,
    observations: list[RequestObservation] | tuple[RequestObservation, ...] | list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """Build the formal ``accepttwin.report/v1`` report for one run.

    *contract* is the validated dual-representation contract,
    *production_result* the production
    :class:`~accepttwin.classifier.ClassificationResult` (or its
    ``as_dict()`` shape), *oracle_result* the independent Oracle
    result (``oracle.json`` dict, or None when no Oracle ran).
    *observations* are the eight §5.5 observations in any order;
    *scenario_id* is the Golden id (``C01``–``C24``, ``E01``–``E24``).

    The report is fully deterministic given its inputs: it carries
    no timestamp, duration, process id, temporary path or random
    id. Its ``report_hash`` is computed over the hash payload (see
    :func:`compute_report_hash`), so two runs of the same logical
    scenario on different OS-assigned ports hash identically
    (§10.4, ADR-003). Raises :class:`ReportError` on any invalid,
    incomplete or forbidden input — a report is never built around
    bad evidence.
    """
    validated_contract = _coerce_contract(contract)
    if scenario_id is None or not str(scenario_id).strip():
        raise ReportError("scenario_id is required (Golden id, e.g. 'C11')")
    scenario_id = str(scenario_id)

    if isinstance(production_result, ClassificationResult):
        production = production_result.as_dict()
    elif isinstance(production_result, dict):
        production = dict(production_result)
    else:
        raise ReportError(
            "production_result must be a ClassificationResult or dict; "
            f"got {type(production_result).__name__}"
        )
    _reject_forbidden_keys(production, "production result")
    verdict = production.get("verdict")
    if verdict not in VERDICTS:
        raise ReportError(f"verdict {verdict!r} is not one of the five frozen verdicts")
    diagnostics = [
        _coerce_diagnostic(diag)
        for diag in production.get("diagnostics", [])
    ]
    first_error = production.get("first_error")
    if first_error is not None and (
        not isinstance(first_error, int)
        or isinstance(first_error, bool)
        or first_error < 1
    ):
        raise ReportError("first_error must be a positive integer or null")
    first_error_experiment_id = production.get("first_error_experiment_id")
    if (
        first_error_experiment_id is not None
        and first_error_experiment_id not in EXPERIMENT_IDS
    ):
        raise ReportError(
            f"unknown first_error_experiment_id {first_error_experiment_id!r}"
        )
    reasons = production.get("reasons", [])
    if not isinstance(reasons, list) or not all(
        isinstance(reason, str) for reason in reasons
    ):
        raise ReportError("reasons must be a list of strings")

    if observations is None:
        raise ReportError(
            "observations are required: exactly the eight §5.5 observations "
            "of the run (001–008)"
        )
    obs_list = [_coerce_observation(obs) for obs in observations]
    if len(obs_list) != _EXPECTED_OBSERVATIONS:
        raise ReportError(
            f"exactly {_EXPECTED_OBSERVATIONS} observations are required, got {len(obs_list)}"
        )
    indices = sorted(obs["request_index"] for obs in obs_list)
    if indices != list(range(1, _EXPECTED_OBSERVATIONS + 1)):
        raise ReportError(
            f"observations must cover requests 001–{_EXPECTED_OBSERVATIONS:03d} exactly once each, got {indices}"
        )
    obs_list.sort(key=lambda obs: obs["request_index"])

    oracle = _coerce_oracle(oracle_result)
    oracle_parity: bool | None = None
    if oracle is not None:
        if isinstance(oracle_result, dict):
            raw_diagnostics = oracle_result.get("diagnostics", [])
            raw_cache_states = oracle_result.get("verified_cache_states")
        else:
            raw_diagnostics = getattr(oracle_result, "diagnostics", [])
            raw_cache_states = getattr(
                oracle_result, "verified_cache_states", None
            )
        oracle_diag_projection = _diagnostic_projection(
            [_coerce_diagnostic(diag) for diag in raw_diagnostics]
        )
        oracle_parity = _oracle_parity(
            verdict,
            diagnostics,
            first_error,
            first_error_experiment_id,
            oracle,
            oracle_diag_projection,
            _production_cache_states(production),
            raw_cache_states,
        )

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "project": {"project_id": "P032", "version": "1.0.1"},
        "scenario_id": scenario_id,
        "input": {
            "contract_id": validated_contract.contract_id,
            "contract_sha256": canonical_contract_hash(validated_contract),
            "url": validated_contract.url,
            "origin_url": validated_contract.origin_url,
            "cache_behavior": dict(validated_contract.cache_behavior),
            "request_headers": dict(validated_contract.request_headers),
        },
        "observations": obs_list,
        "diagnostics": diagnostics,
        "verdict": verdict,
        "first_error": first_error,
        "first_error_experiment_id": first_error_experiment_id,
        "critical_count": sum(
            1 for diag in diagnostics if diag["severity"] == "CRITICAL"
        ),
        "warning_count": sum(
            1 for diag in diagnostics if diag["severity"] == "WARNING"
        ),
        "reasons": list(reasons),
        "oracle": oracle,
        "oracle_parity": oracle_parity,
        "final": bool(oracle_parity),
        "report_hash": "",
    }
    # The whole report is scanned once more before hashing: no
    # forbidden key may survive at any depth, whatever the inputs
    # carried (defence in depth — the per-field checks above are
    # the primary guard).
    _reject_forbidden_keys(report, "report")
    report["report_hash"] = compute_report_hash(report)
    return report
