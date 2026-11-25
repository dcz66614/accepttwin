"""Unit tests for accepttwin.request_headers (T002 acceptance criteria).

Covers: the fixed header set is built exactly; any header outside the
whitelist — Cookie, Authorization, X-*, Cache-Control, Referer, Origin,
or a wrong fixed value — is rejected, never silently dropped.
"""

from __future__ import annotations

import pytest

from accepttwin.request_headers import (
    HeaderError,
    assert_request_headers,
    build_request_headers,
    validate_request_headers,
)


def test_build_html_headers():
    assert build_request_headers("html") == {
        "Accept": "text/html",
        "Accept-Encoding": "identity",
        "User-Agent": "AcceptTwin/1.0.0",
        "Accept-Language": "en",
    }


def test_build_markdown_headers():
    assert build_request_headers("markdown") == {
        "Accept": "text/markdown",
        "Accept-Encoding": "identity",
        "User-Agent": "AcceptTwin/1.0.0",
        "Accept-Language": "en",
    }


def test_build_unknown_representation_rejected():
    with pytest.raises(HeaderError, match="unknown representation"):
        build_request_headers("text")


def test_fixed_sets_validate():
    for representation in ("html", "markdown"):
        assert validate_request_headers(build_request_headers(representation)) == []


def test_lowercase_names_validate():
    headers = {
        "accept": "text/html",
        "accept-encoding": "identity",
        "user-agent": "AcceptTwin/1.0.0",
        "accept-language": "en",
    }
    assert validate_request_headers(headers) == []
    assert assert_request_headers(headers) == build_request_headers("html")


@pytest.mark.parametrize(
    "name",
    [
        "Cookie",
        "cookie",
        "COOKIE",
        "Authorization",
        "Proxy-Authorization",
        "Referer",
        "Origin",
        "Cache-Control",
        "X-Custom",
        "X-AcceptTwin-Debug",
        "X-Forwarded-For",
    ],
)
def test_forbidden_headers_rejected(name):
    headers = build_request_headers("html")
    headers[name] = "x"
    errors = validate_request_headers(headers)
    assert errors, f"{name} should have been rejected"
    with pytest.raises(HeaderError):
        assert_request_headers(headers)


def test_unknown_header_rejected():
    headers = build_request_headers("html")
    headers["DNT"] = "1"
    assert any("not in the fixed" in e for e in validate_request_headers(headers))


@pytest.mark.parametrize("accept", ["text/plain", "text/html;q=0.9", ""])
def test_wrong_accept_rejected(accept):
    headers = build_request_headers("html")
    headers["Accept"] = accept
    assert any("Accept" in e for e in validate_request_headers(headers))


def test_missing_accept_rejected():
    headers = build_request_headers("html")
    del headers["Accept"]
    assert any("missing required header 'Accept'" in e for e in validate_request_headers(headers))


@pytest.mark.parametrize(
    "name,value",
    [
        ("User-Agent", "curl/8.0"),
        ("Accept-Encoding", "gzip"),
        ("Accept-Language", "fr"),
    ],
)
def test_wrong_fixed_value_rejected(name, value):
    headers = build_request_headers("markdown")
    headers[name] = value
    assert validate_request_headers(headers)


def test_missing_fixed_header_rejected():
    headers = build_request_headers("html")
    del headers["User-Agent"]
    assert any("User-Agent" in e for e in validate_request_headers(headers))


def test_case_duplicate_header_rejected():
    headers = {"Accept": "text/html", "accept": "text/html"}
    # A plain dict cannot hold both spellings as separate keys only if the
    # spellings differ; here they do, so the validator must flag it.
    errors = validate_request_headers(headers)
    assert any("differs only by case" in e for e in errors)


def test_non_string_value_rejected():
    errors = validate_request_headers({"Accept": 42})  # type: ignore[dict-item]
    assert errors


def test_assert_returns_canonical_build():
    mixed_case = {
        "accept": "text/markdown",
        "ACCEPT-ENCODING": "identity",
        "user-agent": "AcceptTwin/1.0.0",
        "Accept-Language": "en",
    }
    assert assert_request_headers(mixed_case) == build_request_headers("markdown")
