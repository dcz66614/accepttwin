"""Raw observation evidence (P032 T005).

Implements IMPLEMENTATION_PLAN §5.5 / T005 and PROJECT_BOOK §5.3,
§5.4, §6, §7.12:

* :class:`RequestObservation` — the frozen §5.5 dataclass: one entry
  per HTTP request actually sent, carrying only hashes and match
  results, never the response body itself (§7.12 I-12);
* :class:`RawObservation` — the richer per-request record the runner
  writes to the raw-observations file for T006 (classifier) and T007
  (independent Oracle) to read independently: method, URL, Accept,
  status, Content-Type, Sentinel match, body SHA-256, the full cache
  response headers, and the measured origin-counter / cache-entry
  deltas. Still no body text anywhere;
* :func:`write_evidence_file` / :func:`read_evidence_file` — the
  raw-observations file format (``accepttwin.raw-observations/v1``),
  JSON with sorted keys, deterministic (no timestamps, no process
  ids, no ephemeral ports beyond the contract URLs themselves, no
  body bytes).

Nothing in this module performs I/O against a server, reads proxy
environment variables, or invents an observation: it only records
what the runner measured on the wire.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "RAW_OBSERVATIONS_FORMAT",
    "RawObservation",
    "RequestObservation",
    "read_evidence_file",
    "write_evidence_file",
]

#: Format marker written at the top of every raw-observations file.
RAW_OBSERVATIONS_FORMAT = "accepttwin.raw-observations/v1"


# ---------------------------------------------------------------------------
# §5.5 RequestObservation (frozen interface)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RequestObservation:
    """One observed request, per IMPLEMENTATION_PLAN §5.5.

    ``cache_status`` is the *verified* cache state from the dual
    evidence (§5.3: ``"MISS"`` / ``"HIT"`` / ``"BYPASS"`` /
    ``"CACHE_STATE_UNKNOWN"``) for requests sent through the proxy,
    and ``None`` for direct-origin baseline requests (001 O-H, 002
    O-M), which never touch the cache. The raw response body is never
    stored here (§7.12 I-12); only its SHA-256 and whether the
    requested representation's Sentinel matched byte-exactly.

    The ``str | None`` type (widened from the frozen §5.5 ``str``)
    is recorded in ``00_control/ADR-001.md``: only the two
    direct-origin baseline requests take ``None``; every proxied
    request (003–008) carries a verified state string. T006/T007
    must treat ``None`` as "direct-origin, no cache evidence", never
    as ``"CACHE_STATE_UNKNOWN"``.
    """

    request_index: int
    experiment_id: str
    requested_representation: str
    response_status: int
    response_content_type: str
    body_sha256: str
    sentinel_match: bool
    cache_status: str | None
    cache_key_sha256: str | None
    cache_entry_id: str | None
    origin_counter_before: int
    origin_counter_after: int
    origin_counter_delta: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_index": self.request_index,
            "experiment_id": self.experiment_id,
            "requested_representation": self.requested_representation,
            "response_status": self.response_status,
            "response_content_type": self.response_content_type,
            "body_sha256": self.body_sha256,
            "sentinel_match": self.sentinel_match,
            "cache_status": self.cache_status,
            "cache_key_sha256": self.cache_key_sha256,
            "cache_entry_id": self.cache_entry_id,
            "origin_counter_before": self.origin_counter_before,
            "origin_counter_after": self.origin_counter_after,
            "origin_counter_delta": self.origin_counter_delta,
        }


# ---------------------------------------------------------------------------
# Raw observation (runner -> evidence file -> T006 / T007)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawObservation:
    """The full per-request record written to the evidence file.

    Extends :class:`RequestObservation` with the request line
    (method / URL / Accept), the complete lower-cased response-header
    set, the body size, the SHA-256 of the *expected* Sentinel (so a
    reader can check which Sentinel was expected without the evidence
    file carrying the Sentinel string itself), the dual-evidence
    verification outcome, and the cache-entry counts before/after.
    No field here carries response body text.
    """

    request_index: int
    experiment_id: str
    requested_representation: str
    method: str
    url: str
    accept: str
    response_status: int
    response_content_type: str
    body_sha256: str
    body_size: int
    sentinel_match: bool
    sentinel_sha256: str
    response_headers: dict[str, str] = field(default_factory=dict)
    cache_status_header: str | None = None
    cache_key_sha256: str | None = None
    cache_entry_id: str | None = None
    verified_cache_state: str | None = None
    cache_verification_reasons: tuple[str, ...] = ()
    cache_entry_count_before: int | None = None
    cache_entry_count_after: int | None = None
    origin_counter_before: int = 0
    origin_counter_after: int = 0
    origin_counter_delta: int = 0
    origin_event_present: bool | None = None
    transport_error: str | None = None

    def to_request_observation(self) -> RequestObservation:
        """Project this record down to the frozen §5.5 observation."""
        return RequestObservation(
            request_index=self.request_index,
            experiment_id=self.experiment_id,
            requested_representation=self.requested_representation,
            response_status=self.response_status,
            response_content_type=self.response_content_type,
            body_sha256=self.body_sha256,
            sentinel_match=self.sentinel_match,
            cache_status=self.verified_cache_state,
            cache_key_sha256=self.cache_key_sha256,
            cache_entry_id=self.cache_entry_id,
            origin_counter_before=self.origin_counter_before,
            origin_counter_after=self.origin_counter_after,
            origin_counter_delta=self.origin_counter_delta,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_index": self.request_index,
            "experiment_id": self.experiment_id,
            "requested_representation": self.requested_representation,
            "method": self.method,
            "url": self.url,
            "accept": self.accept,
            "response_status": self.response_status,
            "response_content_type": self.response_content_type,
            "body_sha256": self.body_sha256,
            "body_size": self.body_size,
            "sentinel_match": self.sentinel_match,
            "sentinel_sha256": self.sentinel_sha256,
            "response_headers": dict(self.response_headers),
            "cache_status_header": self.cache_status_header,
            "cache_key_sha256": self.cache_key_sha256,
            "cache_entry_id": self.cache_entry_id,
            "verified_cache_state": self.verified_cache_state,
            "cache_verification_reasons": list(self.cache_verification_reasons),
            "cache_entry_count_before": self.cache_entry_count_before,
            "cache_entry_count_after": self.cache_entry_count_after,
            "origin_counter_before": self.origin_counter_before,
            "origin_counter_after": self.origin_counter_after,
            "origin_counter_delta": self.origin_counter_delta,
            "origin_event_present": self.origin_event_present,
            "transport_error": self.transport_error,
        }


def sentinel_sha256(sentinel: str) -> str:
    """SHA-256 of a Sentinel string (the evidence file never stores
    the Sentinel itself; §7.12 allows only the declared identifier,
    and the hash is what §8.1 diagnostics cite as
    ``expected_sentinel_sha256``)."""
    return hashlib.sha256(sentinel.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Evidence file (JSON)
# ---------------------------------------------------------------------------


#: Field names that must never appear in an evidence dict, at any
#: depth (§7.12 I-12). ``body_sha256`` / ``body_size`` are hashes and
#: sizes, not body text, and are allowed.
_FORBIDDEN_BODY_FIELDS = frozenset({"body_text", "response_body", "body"})


def _reject_body_fields(value: Any, where: str = "evidence") -> None:
    """Recursively reject any ``_FORBIDDEN_BODY_FIELDS`` key in
    *value* (dicts, lists and tuples are walked to any depth)."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _FORBIDDEN_BODY_FIELDS:
                raise ValueError(
                    f"evidence must not contain a {key!r} field ({where})"
                )
            _reject_body_fields(item, f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_body_fields(item, f"{where}[{index}]")


def write_evidence_file(path: str | Path, evidence: dict[str, Any]) -> Path:
    """Write *evidence* as deterministic JSON (sorted keys, UTF-8).

    The caller is responsible for the content: this function only
    serialises. It refuses to write anything carrying a ``body_text``
    / ``response_body`` / ``body`` field at *any* depth of the
    evidence dict — a fail-closed guard for §7.12 I-12, so body text
    cannot smuggle itself in nested inside an observation. (Body
    *hashes* such as ``body_sha256`` and sizes such as ``body_size``
    are fine; the check looks for the exact field names, not for
    hashes.)
    """
    path = Path(path)
    if "format" not in evidence:
        raise ValueError("evidence dict must carry a 'format' field")
    _reject_body_fields(evidence)
    text = json.dumps(evidence, sort_keys=True, indent=2, ensure_ascii=False)
    text += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def read_evidence_file(path: str | Path) -> dict[str, Any]:
    """Read back a raw-observations file written by
    :func:`write_evidence_file`. Raises :class:`ValueError` when the
    file is not a JSON object or does not carry the expected format
    marker."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read evidence file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"evidence file {path} must contain a JSON object")
    if data.get("format") != RAW_OBSERVATIONS_FORMAT:
        raise ValueError(
            f"evidence file {path} has format {data.get('format')!r}; "
            f"expected {RAW_OBSERVATIONS_FORMAT!r}"
        )
    return data
