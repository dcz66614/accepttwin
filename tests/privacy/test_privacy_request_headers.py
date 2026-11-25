"""Privacy regression: fixed request-header whitelist (P032 T011).

Acceptance scenarios (IMPLEMENTATION_PLAN T011, PROJECT_BOOK §5.1.3,
§17.2):

5. non-whitelisted request header rejected;
6. Authorization rejected;
7. Cookie rejected.

Each scenario has a positive case (the exact fixed set is accepted)
and negative cases (rejected, in several casings). Rejection is
verified at three levels: the whitelist validator, the privacy
re-raise, and the contract loader — a contract that smuggles a
sensitive header is refused at load time, before any request is
sent, so no I/O can ever carry it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from accepttwin.contract import parse_contract
from accepttwin.privacy import PrivacyError, check_request_headers
from accepttwin.request_headers import (
    build_request_headers,
    validate_request_headers,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"


def fixed_headers(representation="html"):
    return build_request_headers(representation)


# ---------------------------------------------------------------------------
# Positive cases — the exact fixed set is accepted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("representation", ["html", "markdown"])
def test_fixed_header_set_accepted(representation):
    headers = fixed_headers(representation)
    assert validate_request_headers(headers) == []
    assert check_request_headers(headers) == headers
    assert headers["Accept"] in ("text/html", "text/markdown")


def test_fixed_header_set_accepted_with_different_casing():
    """Header names are case-insensitive (RFC 9110 §5.1); values exact."""
    headers = {
        "accept": "text/html",
        "ACCEPT-ENCODING": "identity",
        "user-agent": "AcceptTwin/1.0.0",
        "Accept-Language": "en",
    }
    assert validate_request_headers(headers) == []
    assert check_request_headers(headers)["Accept"] == "text/html"


# ---------------------------------------------------------------------------
# Scenario 5 — non-whitelisted request header rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "Referer",
        "Origin",
        "Cache-Control",
        "X-Custom",
        "X-AcceptTwin-Debug",
        "x-trace-id",
        "DNT",
        "Accept-Charset",
    ],
)
def test_non_whitelisted_header_rejected(name):
    headers = {**fixed_headers(), name: "something"}
    assert validate_request_headers(headers)
    with pytest.raises(PrivacyError):
        check_request_headers(headers)


@pytest.mark.parametrize(
    "headers",
    [
        {"Accept": "text/html"},  # missing the three fixed common headers
        {
            "Accept": "text/html",
            "Accept-Encoding": "gzip",  # wrong fixed value
            "User-Agent": "AcceptTwin/1.0.0",
            "Accept-Language": "en",
        },
        {
            "Accept": "application/json",  # wrong Accept value
            "Accept-Encoding": "identity",
            "User-Agent": "AcceptTwin/1.0.0",
            "Accept-Language": "en",
        },
        {
            "Accept": "text/html",
            "Accept-Encoding": "identity",
            "User-Agent": "AcceptTwin/2.0.0",  # wrong User-Agent
            "Accept-Language": "en",
        },
    ],
)
def test_altered_or_incomplete_fixed_set_rejected(headers):
    assert validate_request_headers(headers)
    with pytest.raises(PrivacyError):
        check_request_headers(headers)


def test_duplicate_header_differing_only_by_case_rejected():
    """Two names differing only by case are a duplicate (§5.1.3)."""
    from accepttwin.request_headers import validate_request_headers as v

    class DupMapping(dict):
        def items(self):  # noqa: D102 - test double
            return [
                ("Accept", "text/html"),
                ("accept", "text/markdown"),
                ("Accept-Encoding", "identity"),
                ("User-Agent", "AcceptTwin/1.0.0"),
                ("Accept-Language", "en"),
            ]

    assert v(DupMapping())


# ---------------------------------------------------------------------------
# Scenario 6 — Authorization rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["Authorization", "AUTHORIZATION", "authorization", "AuThorization"],
)
def test_authorization_rejected_in_any_casing(name):
    headers = {**fixed_headers(), name: "Bearer SECRET-TOKEN"}
    errors = validate_request_headers(headers)
    assert any("authorization" in err for err in errors)
    with pytest.raises(PrivacyError):
        check_request_headers(headers)


def test_proxy_authorization_rejected():
    headers = {**fixed_headers(), "Proxy-Authorization": "Basic dXNlcjpwYXNz"}
    assert validate_request_headers(headers)
    with pytest.raises(PrivacyError):
        check_request_headers(headers)


# ---------------------------------------------------------------------------
# Scenario 7 — Cookie rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["Cookie", "COOKIE", "cookie", "CoOkIe"]
)
def test_cookie_rejected_in_any_casing(name):
    headers = {**fixed_headers(), name: "session=SECRET-VALUE"}
    errors = validate_request_headers(headers)
    assert any("cookie" in err for err in errors)
    with pytest.raises(PrivacyError):
        check_request_headers(headers)


# ---------------------------------------------------------------------------
# System level — a contract carrying a sensitive header is refused
# at load time, before any request can be sent
# ---------------------------------------------------------------------------


def _contract_with_header(name, value):
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    # Contract-level fixed headers live under request_headers; inject
    # the forbidden header there so the loader must reject it.
    data["request_headers"][name] = value
    return data


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("Authorization", "Bearer SECRET-TOKEN"),
        ("Cookie", "session=SECRET-VALUE"),
        ("Proxy-Authorization", "Basic dXNlcjpwYXNz"),
        ("X-Custom", "1"),
    ],
)
def test_contract_with_sensitive_header_refused_at_load(name, value):
    with pytest.raises(ValueError, match="request_headers"):
        parse_contract(_contract_with_header(name, value))


def test_clean_contract_loads():
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert parse_contract(data) is not None
