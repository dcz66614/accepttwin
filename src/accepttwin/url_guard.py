"""Loopback URL guard (PROJECT_BOOK §5.1.1, IMPLEMENTATION_PLAN §5.2).

Only ``http`` URLs whose *resolved* addresses are all loopback are accepted.
The check is fail-closed: anything that cannot be proven loopback — an
unresolvable name, a name resolving to a mix of loopback and non-loopback
addresses, a missing host, userinfo, a non-HTTP scheme, an out-of-range
port — is rejected.

Rules enforced by :func:`validate_loopback_url`:

* scheme must be ``http`` (case-insensitive, per RFC 9110);
* no URL userinfo (no ``user@`` / ``user:pass@`` in the authority);
* a host must be present; IPv6 zone identifiers (``%...``) are rejected;
* every address returned by DNS resolution of the host must satisfy
  :attr:`ipaddress.IPv4Address.is_loopback` /
  :attr:`ipaddress.IPv6Address.is_loopback`. Literal IP hosts are checked
  directly; names such as ``localhost`` are resolved and *all* results
  must be loopback;
* the port, when present, must be an integer in 1..65535. ``urllib.parse``
  raises :class:`ValueError` for out-of-range or non-numeric ports; that is
  surfaced as an invalid-port error. A missing port defaults to 80 (the
  HTTP default);
* no fragment (a fragment is never sent to a server and has no meaning in
  a contract URL);
* no whitespace or control characters anywhere in the URL.

Deliberately NOT done here: following redirects, reading proxy environment
variables, or fetching anything. The future HTTP client (T005) must pass
``proxies`` disabled / never consult ``HTTP_PROXY`` / ``HTTPS_PROXY`` —
this module only validates the URL string itself, and it never reads the
environment.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_HTTP_PORT = 80


class URLGuardError(ValueError):
    """Raised when a URL fails the loopback guard."""


@dataclass(frozen=True)
class ValidatedURL:
    """A URL that has passed the loopback guard."""

    url: str
    scheme: str
    host: str
    port: int
    addresses: tuple[str, ...]
    path: str
    query: str

    @property
    def origin(self) -> str:
        """``scheme://host:port`` (host bracketed for IPv6)."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{self.scheme}://{host}:{self.port}"


def _resolve_host(host: str, port: int) -> list[str]:
    """Resolve *host* and return every address as a string.

    Raises :class:`URLGuardError` if resolution fails or yields no address.
    """
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OverflowError) as exc:
        raise URLGuardError(f"cannot resolve host {host!r}: {exc}") from exc
    addresses: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr:
            addresses.append(str(sockaddr[0]))
    if not addresses:
        raise URLGuardError(f"host {host!r} resolved to no addresses")
    # De-duplicate while preserving order.
    return list(dict.fromkeys(addresses))


def validate_loopback_url(url: str) -> ValidatedURL:
    """Validate *url* and return its :class:`ValidatedURL`.

    Raises :class:`URLGuardError` with a specific reason on any failure.
    The input is never silently corrected.
    """
    if not isinstance(url, str) or not url:
        raise URLGuardError("URL must be a non-empty string")
    if any(ord(ch) <= 0x20 or ord(ch) == 0x7F for ch in url):
        raise URLGuardError(f"URL {url!r} contains whitespace/control characters")

    parsed = urlparse(url)
    if parsed.scheme.lower() != "http":
        raise URLGuardError(
            f"URL {url!r} uses scheme {parsed.scheme!r}; only 'http' is allowed"
        )
    if parsed.fragment:
        raise URLGuardError(f"URL {url!r} must not contain a fragment")
    if parsed.username is not None or parsed.password is not None:
        raise URLGuardError(f"URL {url!r} must not contain userinfo")
    if "@" in (parsed.netloc or ""):
        raise URLGuardError(f"URL {url!r} must not contain userinfo")

    host = parsed.hostname
    if not host:
        raise URLGuardError(f"URL {url!r} has no host")
    if "%" in host:
        raise URLGuardError(
            f"URL {url!r} must not contain an IPv6 zone identifier"
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise URLGuardError(f"URL {url!r} has an invalid port: {exc}") from exc
    if port is None:
        port = DEFAULT_HTTP_PORT
    if not 1 <= port <= 65535:
        raise URLGuardError(
            f"URL {url!r} has an invalid port {port}; must be 1..65535"
        )

    addresses = _resolve_host(host, port)
    non_loopback: list[str] = []
    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError as exc:
            raise URLGuardError(
                f"host {host!r} resolved to unparsable address {addr!r}"
            ) from exc
        if not ip.is_loopback:
            non_loopback.append(addr)
    if non_loopback:
        raise URLGuardError(
            f"host {host!r} resolves to non-loopback address(es): "
            + ", ".join(non_loopback)
        )

    return ValidatedURL(
        url=url,
        scheme="http",
        host=host,
        port=port,
        addresses=tuple(addresses),
        path=parsed.path or "",
        query=parsed.query or "",
    )
