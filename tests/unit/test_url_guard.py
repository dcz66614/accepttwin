"""Unit tests for accepttwin.url_guard (T002 acceptance criteria).

Covers: loopback addresses accepted; non-loopback addresses rejected;
non-HTTP schemes rejected; URL userinfo rejected; illegal ports rejected.
"""

from __future__ import annotations

import pytest

from accepttwin.url_guard import URLGuardError, validate_loopback_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:18765/doc",
        "http://127.0.0.1/doc",
        "http://127.0.0.2:8080/",
        "http://[::1]:18766/doc",
        "http://[::1]/doc",
        "http://localhost:18765/doc",
        "http://localhost/doc",
        "HTTP://127.0.0.1:18765/doc",
    ],
)
def test_loopback_urls_accepted(url):
    validated = validate_loopback_url(url)
    assert validated.scheme == "http"
    assert validated.port >= 1
    assert validated.addresses
    assert all(
        addr.startswith("127.") or addr == "::1"
        for addr in validated.addresses
    )


def test_validated_url_fields():
    validated = validate_loopback_url("http://127.0.0.1:18765/doc?x=1")
    assert validated.host == "127.0.0.1"
    assert validated.port == 18765
    assert validated.path == "/doc"
    assert validated.query == "x=1"
    assert validated.addresses == ("127.0.0.1",)
    assert validated.origin == "http://127.0.0.1:18765"


def test_default_port_is_80():
    assert validate_loopback_url("http://127.0.0.1/doc").port == 80


def test_ipv6_validated_url_origin_bracketed():
    validated = validate_loopback_url("http://[::1]:18766/doc")
    assert validated.host == "::1"
    assert validated.origin == "http://[::1]:18766"


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8/doc",
        "http://93.184.216.34:18765/doc",
        "http://192.168.1.1:18765/doc",
        "http://10.0.0.5/doc",
        "http://172.16.0.1/doc",
        "http://0.0.0.0:18765/doc",
        "http://[2606:4700:4700::1111]/doc",
        "http://[2001:db8::1]/doc",
    ],
)
def test_non_loopback_rejected(url):
    with pytest.raises(URLGuardError, match="non-loopback"):
        validate_loopback_url(url)


def test_dns_name_resolving_to_public_rejected():
    # example.com resolves to public IPs (or not at all offline); either
    # way the guard must refuse it — it can never be proven loopback.
    with pytest.raises(URLGuardError):
        validate_loopback_url("http://example.com/doc")


def test_unresolvable_host_rejected():
    # In this VM a wildcard resolver answers even for .invalid names
    # (198.18.179.212); either way the guard must refuse: the name can
    # never be proven loopback.
    with pytest.raises(URLGuardError):
        validate_loopback_url("http://nonexistent.invalid/doc")


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:18765/doc",
        "ftp://127.0.0.1/doc",
        "http://127.0.0.1:18765/doc".replace("http", "ws"),
        "",
    ],
)
def test_non_http_rejected(url):
    with pytest.raises(URLGuardError, match="only 'http'|non-empty"):
        validate_loopback_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://user@127.0.0.1:18765/doc",
        "http://user:pass@127.0.0.1:18765/doc",
        "http://:pass@127.0.0.1/doc",
        "http://user@[::1]:18766/doc",
    ],
)
def test_userinfo_rejected(url):
    with pytest.raises(URLGuardError, match="userinfo"):
        validate_loopback_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:0/doc",
        "http://127.0.0.1:65536/doc",
        "http://127.0.0.1:99999/doc",
        "http://127.0.0.1:abc/doc",
        "http://127.0.0.1:-1/doc",
    ],
)
def test_illegal_port_rejected(url):
    with pytest.raises(URLGuardError, match="port"):
        validate_loopback_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http:///doc",
        "http://:18765/doc",
        "http://127.0.0.1:18765/doc#frag",
        "http://[::1%lo]:18766/doc",
        "http://127.0.0.1:18765/do c",
        "not a url",
    ],
)
def test_malformed_urls_rejected(url):
    with pytest.raises(URLGuardError):
        validate_loopback_url(url)


def test_localhost_resolves_to_loopback_only():
    validated = validate_loopback_url("http://localhost:18765/doc")
    assert validated.addresses
    assert all(
        addr.startswith("127.") or addr == "::1"
        for addr in validated.addresses
    )
