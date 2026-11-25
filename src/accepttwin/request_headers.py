"""Fixed request-header whitelist (PROJECT_BOOK §5.1.3, §17.2).

The first release sends exactly four headers, and nothing else:

* ``Accept`` — ``text/html`` for the HTML representation,
  ``text/markdown`` for the Markdown representation (§5.1.2; never modified);
* ``Accept-Encoding: identity``;
* ``User-Agent: AcceptTwin/1.0.0``;
* ``Accept-Language: en``.

Forbidden in the first release (never sent, never accepted from a contract
or a caller): ``Cookie``, ``Authorization``, ``Proxy-Authorization``,
``Referer``, ``Origin``, any user-defined ``X-*`` header, and any
uncontrolled ``Cache-Control`` request directive. Cache control and debug
information are produced inside the controlled proxy, not as user request
headers (§5.1.3).

Header names are compared case-insensitively (RFC 9110 §5.1); values are
compared exactly. Nothing is silently dropped or corrected: validation
returns every violation found.
"""

from __future__ import annotations

from collections.abc import Mapping

ACCEPT_BY_REPRESENTATION: dict[str, str] = {
    "html": "text/html",
    "markdown": "text/markdown",
}

FIXED_COMMON_HEADERS: dict[str, str] = {
    "Accept-Encoding": "identity",
    "User-Agent": "AcceptTwin/1.0.0",
    "Accept-Language": "en",
}

#: Lower-cased names a request may ever carry.
ALLOWED_HEADER_NAMES: frozenset[str] = frozenset(
    {"accept", "accept-encoding", "user-agent", "accept-language"}
)

#: Lower-cased names that are explicitly forbidden (§5.1.3, §17.2).
FORBIDDEN_HEADER_NAMES: frozenset[str] = frozenset(
    {
        "cookie",
        "authorization",
        "proxy-authorization",
        "referer",
        "origin",
        "cache-control",
    }
)


class HeaderError(ValueError):
    """Raised when a request-header set violates the fixed whitelist."""


def build_request_headers(representation: str) -> dict[str, str]:
    """Return the exact fixed header set for *representation*.

    *representation* must be ``"html"`` or ``"markdown"``; anything else
    raises :class:`HeaderError`. The returned mapping is a fresh dict in
    canonical order: ``Accept`` first, then the fixed common headers.
    """
    try:
        accept = ACCEPT_BY_REPRESENTATION[representation]
    except KeyError as exc:
        raise HeaderError(
            f"unknown representation {representation!r}; "
            "expected 'html' or 'markdown'"
        ) from exc
    return {"Accept": accept, **FIXED_COMMON_HEADERS}


def validate_request_headers(headers: Mapping[str, str]) -> list[str]:
    """Validate a caller-supplied header mapping against the whitelist.

    Returns the list of violations (empty means the set is exactly the
    fixed set for one representation). Checks, in order: the mapping is a
    mapping of strings; no duplicate names differing only by case; every
    name is whitelisted (anything else — including ``X-*``, ``Cookie``,
    ``Authorization``, ``Cache-Control`` — is rejected, never ignored);
    ``Accept`` is exactly ``text/html`` or ``text/markdown``; the three
    fixed common headers are present with exactly the frozen values.
    """
    errors: list[str] = []
    if not isinstance(headers, Mapping):
        return ["request headers must be a mapping of header name to value"]

    lowered: dict[str, str] = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            errors.append(
                f"header {name!r}: names and values must both be strings"
            )
            continue
        key = name.lower()
        if key in lowered:
            errors.append(
                f"duplicate header {name!r} (differs only by case from an "
                "earlier header)"
            )
        lowered[key] = value

    for key in sorted(lowered):
        if key.startswith("x-"):
            errors.append(
                f"header {key!r} is a user-defined X-* header, "
                "which is forbidden in the first release"
            )
        elif key in FORBIDDEN_HEADER_NAMES:
            errors.append(f"header {key!r} is forbidden in the first release")
        elif key not in ALLOWED_HEADER_NAMES:
            errors.append(
                f"header {key!r} is not in the fixed request-header whitelist"
            )

    accept = lowered.get("accept")
    if accept is None:
        errors.append("missing required header 'Accept'")
    elif accept not in ACCEPT_BY_REPRESENTATION.values():
        errors.append(
            f"header 'Accept' must be exactly 'text/html' or "
            f"'text/markdown', got {accept!r}"
        )

    for canonical_name, frozen_value in FIXED_COMMON_HEADERS.items():
        key = canonical_name.lower()
        if key not in lowered:
            errors.append(f"missing required header {canonical_name!r}")
        elif lowered[key] != frozen_value:
            errors.append(
                f"header {canonical_name!r} must be exactly "
                f"{frozen_value!r}, got {lowered[key]!r}"
            )

    return errors


def assert_request_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Validate *headers* and return a normalised copy, or raise.

    The returned dict uses the canonical capitalisation (``Accept``,
    ``Accept-Encoding``, ``User-Agent``, ``Accept-Language``).
    """
    errors = validate_request_headers(headers)
    if errors:
        raise HeaderError("; ".join(errors))
    accept = next(
        value for name, value in headers.items() if name.lower() == "accept"
    )
    representation = "html" if accept == "text/html" else "markdown"
    # Rebuild from the frozen values so casing/order can never drift.
    return build_request_headers(representation)
