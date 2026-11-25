"""Privacy regression: loopback URL guard (P032 T011, scenarios 1–3).

Acceptance scenarios (IMPLEMENTATION_PLAN T011, PROJECT_BOOK §5.1.1,
§17.4 items 1–3):

1. public IPv4 rejected;
2. public IPv6 rejected;
3. DNS resolving to a non-loopback address rejected.

Each scenario has a positive case (loopback accepted) and negative
cases (rejected). The DNS cases are tested by monkeypatching
``socket.getaddrinfo`` — no real DNS lookup and no network access —
because the guard's job is to judge *whatever addresses resolution
returns*, and the fake lets us feed it a public address, a mixed
loopback+public answer, and a loopback-only answer deterministically.
Literal-IP cases need no resolution at all.
"""

from __future__ import annotations

import socket

import pytest

from accepttwin.privacy import PrivacyError, check_loopback_url
from accepttwin.url_guard import validate_loopback_url


# ---------------------------------------------------------------------------
# Scenario 1 — public IPv4 rejected (positive: loopback accepted)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:18765/doc",
        "http://127.0.0.1/doc",
        "http://127.0.0.2:8080/",
        "http://127.255.255.255/",
    ],
)
def test_loopback_ipv4_accepted(url):
    assert check_loopback_url(url).host.startswith("127.")
    # The underlying T002 guard agrees (regression layer delegates).
    assert validate_loopback_url(url).url == url


@pytest.mark.parametrize(
    "url",
    [
        "http://93.184.216.34/doc",  # public IPv4 (example.com)
        "http://8.8.8.8/",
        "http://1.1.1.1:80/",
        "http://192.168.1.1/doc",  # private LAN — still not loopback (§5.1.1)
        "http://10.0.0.1/doc",
        "http://172.16.0.1/doc",
        "http://0.0.0.0/doc",
        "http://128.0.0.1/doc",  # one past the loopback block
        "http://126.255.255.255/doc",
    ],
)
def test_public_or_non_loopback_ipv4_rejected(url):
    with pytest.raises(PrivacyError):
        check_loopback_url(url)


# ---------------------------------------------------------------------------
# Scenario 2 — public IPv6 rejected (positive: ::1 accepted)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://[::1]:18766/doc",
        "http://[::1]/doc",
    ],
)
def test_loopback_ipv6_accepted(url):
    validated = check_loopback_url(url)
    assert validated.host == "::1"


@pytest.mark.parametrize(
    "url",
    [
        "http://[2606:4700:4700::1111]/",  # public IPv6
        "http://[2001:4860:4860::8888]/",
        "http://[fe80::1]/",  # link-local — not loopback
        "http://[::]/",  # unspecified — not loopback
        "http://[::ffff:93.184.216.34]/",  # IPv4-mapped public address
    ],
)
def test_public_or_non_loopback_ipv6_rejected(url):
    with pytest.raises(PrivacyError):
        check_loopback_url(url)


# ---------------------------------------------------------------------------
# Scenario 3 — DNS resolving to a non-loopback address rejected
# ---------------------------------------------------------------------------


def _fake_getaddrinfo_factory(answers):
    """Return a getaddrinfo replacement serving *answers* for any host.

    *answers* maps host -> list of address strings. Unknown hosts fall
    through to the real resolver (only used for hosts we never query).
    """
    real = socket.getaddrinfo

    def fake(host, port, family=0, type=0, proto=0, flags=0):
        if host in answers:
            infos = []
            for addr in answers[host]:
                if ":" in addr:
                    infos.append(
                        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (addr, port, 0, 0))
                    )
                else:
                    infos.append(
                        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (addr, port))
                    )
            return infos
        return real(host, port, family, type, proto, flags)

    return fake


def test_dns_resolving_to_public_ipv4_rejected(monkeypatch):
    """A name that resolves to a public address is rejected (§17.4.2)."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory({"host.example": ["93.184.216.34"]}),
    )
    with pytest.raises(PrivacyError, match="non-loopback"):
        check_loopback_url("http://host.example:18765/doc")


def test_dns_resolving_to_public_ipv6_rejected(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory(
            {"host.example": ["2606:4700:4700::1111"]}
        ),
    )
    with pytest.raises(PrivacyError, match="non-loopback"):
        check_loopback_url("http://host.example/doc")


def test_dns_mixed_loopback_and_public_rejected(monkeypatch):
    """One non-loopback answer poisons the whole name (fail-closed)."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory(
            {"host.example": ["127.0.0.1", "93.184.216.34"]}
        ),
    )
    with pytest.raises(PrivacyError, match="non-loopback"):
        check_loopback_url("http://host.example/doc")


def test_dns_resolving_to_loopback_only_accepted(monkeypatch):
    """Positive case: a name resolving only to loopback is accepted."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory({"host.example": ["127.0.0.1", "::1"]}),
    )
    validated = check_loopback_url("http://host.example:18765/doc")
    assert set(validated.addresses) == {"127.0.0.1", "::1"}


def test_localhost_resolves_to_loopback_without_mock():
    """Real resolution of localhost must be loopback-only (§5.1.1)."""
    validated = check_loopback_url("http://localhost:18765/doc")
    assert validated.addresses
    assert all(
        addr.startswith("127.") or addr == "::1"
        for addr in validated.addresses
    )


def test_unresolvable_host_rejected(monkeypatch):
    """A name that does not resolve is rejected, never trusted."""
    def boom(host, port, family=0, type=0, proto=0, flags=0):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", boom)
    with pytest.raises(PrivacyError, match="cannot resolve"):
        check_loopback_url("http://nonexistent.invalid/doc")


# --- guard extras pinned by the same section (scheme / userinfo) --------


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/doc",
        "http://user@127.0.0.1/doc",
        "http://user:pass@127.0.0.1/doc",
        "http://127.0.0.1/doc#frag",
        "ftp://127.0.0.1/doc",
    ],
)
def test_non_http_or_userinfo_or_fragment_rejected(url):
    with pytest.raises(PrivacyError):
        check_loopback_url(url)
