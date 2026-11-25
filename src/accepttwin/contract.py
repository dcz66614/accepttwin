"""Dual-representation contract: ``accepttwin.contract/v1``.

Implements IMPLEMENTATION_PLAN §5.1:

* :func:`load_contract` — read a contract JSON file, never silently
  correcting it;
* :func:`parse_contract` — validate a decoded JSON object into a
  :class:`Contract`;
* :func:`validate_contract` — re-validate an already built contract and
  return a :class:`ValidationResult`;
* :func:`canonical_json_bytes` / :func:`canonical_contract_hash` —
  Canonical JSON per PROJECT_BOOK §10.4.

Validation is layered and fail-closed:

1. Structural: :func:`accepttwin.schema.validate_with_schema` (required
   fields, types, enums, ``additionalProperties: false`` — unknown fields
   are rejected, never silently ignored).
2. Semantic: frozen per-representation values (§5.1.2), distinct
   Sentinels, loopback URLs (§5.1.1 via :mod:`accepttwin.url_guard`),
   ``url``/``origin_url`` sharing a path but using different ports,
   the fixed request-header set (§5.1.3 via
   :mod:`accepttwin.request_headers`), and legal ``cache_behavior``
   combinations (§5.2: ``no_store`` must not carry a ``max_age_seconds``).

Defaults applied at parse time (documented, not spec-frozen — the retrieved
spec text states only the ``vary_accept`` default):

* ``cache_behavior.vary_accept`` defaults to ``"advisory"`` (§5.2).
* ``cache_behavior.max_age_seconds`` defaults to ``None``.
* ``limits.max_body_bytes`` defaults to 1048576 (1 MiB, §17.4 body cap).
* ``limits.request_timeout_seconds`` defaults to 5.0 (§17.4 requires a
  bounded timeout but states no value).

Canonical JSON (§10.4): UTF-8, object keys in dictionary order, no extra
whitespace, header names lower-cased, header values whitespace-normalised.
The following fields never enter the canonical form or the hash, wherever
they appear: ``generated_at``, ``duration_ms``, ``duration``, ``process_id``,
``temporary_path``, ``ephemeral_port``, ``uuid``, ``request_id`` (§10.4:
random UUIDs and non-deterministic cache request IDs) and ``received_at`` /
``receivedAt`` (§14.1: run-time only). ``cache_entry_id`` is NOT volatile:
it is a §5.3/§8 evidence field whose handling belongs to the T009 report
design, not to canonicalisation. The report hash is
``SHA256(canonical_json_bytes)``; identical contracts hash identically
across runs (I-08).

Ephemeral ports (ADR-003, §10.4 "不包含动态端口"): the ``url`` /
``origin_url`` endpoint URLs carry OS-assigned loopback ports
(the harness starts services with ``port=0``), so their explicit
port is normalised to ``0`` in the canonical form -- the same value
the harness passes when asking the OS for a free port. Scheme, host,
path and query are preserved, a URL without an explicit port is left
untouched, and a non-loopback URL is left untouched (its port is part
of the service identity, not an OS-assigned ephemeral port). Only the
hash input is normalised; execution still uses the real ports, and
the semantic validation (``url`` / ``origin_url`` share a path, use
different ports) is unchanged and still runs on the real values.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .request_headers import validate_request_headers
from .schema import (
    CONTRACT_SCHEMA_VERSION,
    FROZEN_REPRESENTATIONS,
    validate_with_schema,
)
from .url_guard import URLGuardError, ValidatedURL, validate_loopback_url

__all__ = [
    "Contract",
    "ContractError",
    "Representation",
    "ValidationResult",
    "canonical_contract_hash",
    "canonical_json_bytes",
    "load_contract",
    "parse_contract",
    "validate_contract",
]

#: Fields that never enter Canonical JSON or any normalised hash (§10.4,
#: §14.1). Matched case-sensitively at any nesting depth.
VOLATILE_FIELDS: frozenset[str] = frozenset(
    {
        "generated_at",
        "duration_ms",
        "duration",
        "process_id",
        "temporary_path",
        "ephemeral_port",
        "uuid",
        "request_id",
        "received_at",
        "receivedAt",
    }
)

#: Keys whose dict values are HTTP headers: names are lower-cased and values
#: whitespace-normalised during canonicalisation (§10.4).
HEADER_CONTAINER_KEYS: frozenset[str] = frozenset(
    {"headers", "request_headers"}
)

#: Keys whose string values are endpoint URLs whose loopback port is
#: OS-assigned (ephemeral) and is therefore normalised to
#: :data:`NORMALISED_EPHEMERAL_PORT` in Canonical JSON (§10.4, ADR-003).
#: Only these keys are rewritten; any other URL-valued field keeps its
#: port, so the normalisation can never erase a semantically meaningful
#: port elsewhere in a payload.
URL_PORT_NORMALISED_KEYS: frozenset[str] = frozenset({"url", "origin_url"})

#: Placeholder port written into Canonical JSON for an OS-assigned
#: loopback port (ADR-003). 0 is the value the harness itself passes
#: when asking the OS for a free port (``port=0``); keeping the port
#: slot (rather than stripping it) preserves the distinction between
#: a URL with an explicit port and one without.
NORMALISED_EPHEMERAL_PORT = 0

DEFAULT_MAX_BODY_BYTES = 1048576
DEFAULT_REQUEST_TIMEOUT_SECONDS = 5.0
_DEFAULT_VARY_ACCEPT = "advisory"

_SENTINEL_WHITESPACE = re.compile(r"\s")


class ContractError(ValueError):
    """Raised when a contract file or object fails validation."""


@dataclass(frozen=True)
class Representation:
    """One representation of the dual-representation contract (§5.1.2)."""

    accept: str
    expected_status: int
    expected_content_type: str
    sentinel: str

    def as_dict(self) -> dict:
        return {
            "accept": self.accept,
            "expected_status": self.expected_status,
            "expected_content_type": self.expected_content_type,
            "sentinel": self.sentinel,
        }


@dataclass(frozen=True)
class Contract:
    """A validated ``accepttwin.contract/v1`` contract.

    Instances are normally produced by :func:`parse_contract` /
    :func:`load_contract`, which enforce every rule. A directly constructed
    instance is unchecked until :func:`validate_contract` is called on it.
    """

    schema: str
    contract_id: str
    name: str
    url: str
    origin_url: str
    representations: dict[str, Representation] = field(default_factory=dict)
    request_headers: dict = field(default_factory=dict)
    cache_behavior: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "schema": self.schema,
            "contract_id": self.contract_id,
            "name": self.name,
            "url": self.url,
            "origin_url": self.origin_url,
            "representations": {
                key: rep.as_dict()
                for key, rep in self.representations.items()
            },
            "request_headers": dict(self.request_headers),
            "cache_behavior": dict(self.cache_behavior),
            "limits": dict(self.limits),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.ok


# ---------------------------------------------------------------------------
# Canonical JSON (§10.4)
# ---------------------------------------------------------------------------


def _normalise_header_value(value: str) -> str:
    return " ".join(value.strip().split())


def _is_loopback_host(host: str) -> bool:
    """True when *host* is a loopback host, without doing DNS.

    Literal IP hosts are checked with :mod:`ipaddress` (so the whole
    127/8 range and ``::1`` count); the name ``localhost`` is loopback
    by definition. Any other name is not trusted here -- canonicalisation
    must stay pure and deterministic, and contracts in this system use
    literal ``127.0.0.1`` anyway.
    """
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _normalise_ephemeral_port(value: str) -> str:
    """Replace the port of a loopback ``http`` URL with 0 (ADR-003).

    Only an explicit port on a loopback ``http`` URL is rewritten:
    scheme, host, path and query are preserved, a URL without an
    explicit port is left untouched, and a non-loopback URL is left
    untouched (its port is part of the service identity, not an
    OS-assigned ephemeral port). Unparseable values are returned
    unchanged -- canonicalisation never raises; validation is a
    separate layer and still runs on the real values.
    """
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return value
    if parsed.scheme.lower() != "http" or port is None:
        return value
    host = parsed.hostname
    if host is None or not _is_loopback_host(host):
        return value
    netloc = parsed.netloc
    userinfo, sep, hostport = netloc.rpartition("@")
    if hostport.startswith("["):
        bracket = hostport.find("]")
        new_hostport = (
            hostport[: bracket + 1] + f":{NORMALISED_EPHEMERAL_PORT}"
        )
    else:
        host_part, _, _ = hostport.rpartition(":")
        new_hostport = f"{host_part}:{NORMALISED_EPHEMERAL_PORT}"
    new_netloc = (userinfo + sep if sep else "") + new_hostport
    return urlunsplit(
        (parsed.scheme, new_netloc, parsed.path, parsed.query, parsed.fragment)
    )


def _canonicalise(value: object) -> object:
    if isinstance(value, dict):
        out: dict[str, object] = {}
        for key, item in value.items():
            if key in VOLATILE_FIELDS:
                continue
            if key in URL_PORT_NORMALISED_KEYS and isinstance(item, str):
                out[str(key)] = _normalise_ephemeral_port(item)
            elif key.lower() in HEADER_CONTAINER_KEYS and isinstance(item, dict):
                normalised = {
                    str(hk).lower(): (
                        _normalise_header_value(str(hv))
                        if isinstance(hv, str)
                        else _canonicalise(hv)
                    )
                    for hk, hv in item.items()
                }
                out[str(key)] = normalised
            else:
                out[str(key)] = _canonicalise(item)
        return out
    if isinstance(value, list):
        return [_canonicalise(item) for item in value]
    return value


def canonical_json_bytes(data: object) -> bytes:
    """Return the Canonical JSON encoding of *data* as UTF-8 bytes.

    Keys are sorted, there is no extra whitespace, volatile fields
    (:data:`VOLATILE_FIELDS`) are removed at any depth, header
    containers are normalised per §10.4, and the explicit port of a
    loopback ``http`` URL under an ``url`` / ``origin_url`` key is
    normalised to 0 (ADR-003: OS-assigned ephemeral ports never enter
    the canonical form).
    """
    canonical = _canonicalise(data)
    return json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_contract_hash(contract: Contract) -> str:
    """Return the SHA-256 hex digest of the contract's Canonical JSON.

    The ``url`` / ``origin_url`` ports are normalised to 0 before
    hashing (ADR-003, §10.4): two contracts that differ only in their
    OS-assigned loopback ports hash identically, while a change of
    scheme, host, path, representation or any other semantic field
    still changes the hash. Validation still runs on the real ports.
    """
    return hashlib.sha256(canonical_json_bytes(contract.as_dict())).hexdigest()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _semantic_errors(data: dict) -> list[str]:
    errors: list[str] = []

    for field_name in ("contract_id", "name"):
        value = data.get(field_name)
        if isinstance(value, str) and not value.strip():
            errors.append(f"{field_name}: must not be blank")

    representations = data.get("representations")
    if isinstance(representations, dict):
        for rep_name in ("html", "markdown"):
            rep = representations.get(rep_name)
            if not isinstance(rep, dict):
                continue
            frozen = FROZEN_REPRESENTATIONS[rep_name]
            for key, expected in frozen.items():
                if key in rep and rep[key] != expected:
                    errors.append(
                        f"representations.{rep_name}.{key}: must be exactly "
                        f"{expected!r}, got {rep[key]!r}"
                    )
        html = representations.get("html")
        markdown = representations.get("markdown")
        if isinstance(html, dict) and isinstance(markdown, dict):
            html_sentinel = html.get("sentinel")
            markdown_sentinel = markdown.get("sentinel")
            for rep_name, sentinel in (
                ("html", html_sentinel),
                ("markdown", markdown_sentinel),
            ):
                if isinstance(sentinel, str):
                    if _SENTINEL_WHITESPACE.search(sentinel):
                        errors.append(
                            f"representations.{rep_name}.sentinel: must not "
                            "contain whitespace"
                        )
                    if sentinel != sentinel.strip():
                        errors.append(
                            f"representations.{rep_name}.sentinel: must not "
                            "have leading/trailing whitespace"
                        )
            if (
                isinstance(html_sentinel, str)
                and isinstance(markdown_sentinel, str)
                and html_sentinel
                and html_sentinel == markdown_sentinel
            ):
                errors.append(
                    "representations.html.sentinel and "
                    "representations.markdown.sentinel must be different"
                )

    validated: dict[str, ValidatedURL] = {}
    for field_name in ("url", "origin_url"):
        raw = data.get(field_name)
        if isinstance(raw, str) and raw:
            try:
                validated[field_name] = validate_loopback_url(raw)
            except URLGuardError as exc:
                errors.append(f"{field_name}: {exc}")
    if "url" in validated and "origin_url" in validated:
        proxy = validated["url"]
        origin = validated["origin_url"]
        if proxy.path != origin.path:
            errors.append(
                f"url and origin_url must share the same path: "
                f"{proxy.path!r} != {origin.path!r}"
            )
        if proxy.port == origin.port:
            errors.append(
                "url and origin_url must use different ports: both use "
                f"{proxy.port}"
            )

    headers = data.get("request_headers")
    if isinstance(headers, dict):
        canonical_headers = {
            "Accept-Encoding": headers.get("accept_encoding"),
            "User-Agent": headers.get("user_agent"),
            "Accept-Language": headers.get("accept_language"),
        }
        for rep_name in ("html", "markdown"):
            rep = (
                representations.get(rep_name)
                if isinstance(representations, dict)
                else None
            )
            accept = rep.get("accept") if isinstance(rep, dict) else None
            if isinstance(accept, str):
                merged = {"Accept": accept, **canonical_headers}
                for err in validate_request_headers(merged):
                    errors.append(f"request_headers ({rep_name}): {err}")
    # The frozen common-header values themselves are enforced by the schema
    # consts; the loop above additionally proves the merged per-representation
    # header set is exactly the fixed whitelist.

    cache_behavior = data.get("cache_behavior")
    if isinstance(cache_behavior, dict):
        if (
            cache_behavior.get("mode") == "no_store"
            and cache_behavior.get("max_age_seconds") is not None
        ):
            errors.append(
                "cache_behavior: mode 'no_store' must have "
                "max_age_seconds null"
            )

    return errors


def _validate_data(data: object) -> list[str]:
    if not isinstance(data, dict):
        return ["contract must be a JSON object"]
    errors = validate_with_schema(data)
    errors.extend(_semantic_errors(data))
    return errors


def _contract_from_valid_data(data: dict) -> Contract:
    cache_behavior = dict(data["cache_behavior"])
    cache_behavior.setdefault("vary_accept", _DEFAULT_VARY_ACCEPT)
    cache_behavior.setdefault("max_age_seconds", None)
    limits = dict(data["limits"])
    limits.setdefault("max_body_bytes", DEFAULT_MAX_BODY_BYTES)
    limits.setdefault(
        "request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS
    )
    return Contract(
        schema=data["schema"],
        contract_id=data["contract_id"],
        name=data["name"],
        url=data["url"],
        origin_url=data["origin_url"],
        representations={
            name: Representation(
                accept=rep["accept"],
                expected_status=rep["expected_status"],
                expected_content_type=rep["expected_content_type"],
                sentinel=rep["sentinel"],
            )
            for name, rep in data["representations"].items()
        },
        request_headers=dict(data["request_headers"]),
        cache_behavior=cache_behavior,
        limits=limits,
        metadata=dict(data["metadata"]),
    )


def parse_contract(data: object) -> Contract:
    """Validate decoded JSON *data* and return a :class:`Contract`.

    Raises :class:`ContractError` listing every violation found. Nothing
    is silently corrected: missing, unknown, or illegal fields all fail.
    """
    errors = _validate_data(data)
    if errors:
        raise ContractError(
            "invalid accepttwin.contract/v1 contract:\n"
            + "\n".join(f"  - {err}" for err in errors)
        )
    assert isinstance(data, dict)
    return _contract_from_valid_data(data)


def validate_contract(contract: Contract) -> ValidationResult:
    """Re-validate an already built contract; never raises for bad data."""
    if not isinstance(contract, Contract):
        return ValidationResult(False, ("not a Contract instance",))
    errors = _validate_data(contract.as_dict())
    return ValidationResult(ok=not errors, errors=tuple(errors))


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value!r} is not allowed")


def _object_no_duplicates(pairs: list) -> dict:
    obj: dict = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key {key!r}")
        obj[key] = value
    return obj


def load_contract(path: str | Path) -> Contract:
    """Read and validate the contract JSON file at *path*.

    Raises :class:`ContractError` if the file is missing, is not valid
    JSON, contains duplicate keys or non-standard constants, or fails any
    validation rule.
    """
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read contract file {path}: {exc}") from exc
    try:
        data = json.loads(
            raw,
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
    except ValueError as exc:
        raise ContractError(
            f"contract file {path} is not valid JSON: {exc}"
        ) from exc
    try:
        return parse_contract(data)
    except ContractError as exc:
        raise ContractError(f"contract file {path}: {exc}") from exc
