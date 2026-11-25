"""Unit tests for accepttwin.contract (T002 acceptance criteria).

Covers: legal contract passes; missing field rejected; duplicate Sentinel
rejected; non-loopback URL rejected (via contract); request headers outside
the whitelist rejected; contract hash repeat-consistent.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from accepttwin.contract import (
    Contract,
    ContractError,
    canonical_contract_hash,
    load_contract,
    parse_contract,
    validate_contract,
)
from accepttwin.schema import CONTRACT_SCHEMA

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "contracts" / "site.json"
SCHEMA_FILE = ROOT / "schemas" / "accepttwin.contract.v1.schema.json"

REQUIRED_TOP_LEVEL = [
    "schema",
    "contract_id",
    "name",
    "url",
    "origin_url",
    "representations",
    "request_headers",
    "cache_behavior",
    "limits",
    "metadata",
]


@pytest.fixture()
def valid_data() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


@pytest.fixture()
def valid_contract(valid_data: dict):
    return parse_contract(copy.deepcopy(valid_data))


def test_example_contract_loads():
    contract = load_contract(EXAMPLE)
    assert contract.schema == "accepttwin.contract/v1"
    assert contract.contract_id == "site-example-001"
    assert contract.url == "http://127.0.0.1:18765/doc"
    assert contract.origin_url == "http://127.0.0.1:18766/doc"
    assert contract.representations["html"].accept == "text/html"
    assert contract.representations["markdown"].accept == "text/markdown"
    assert contract.representations["html"].sentinel == "AT_HTML_SENTINEL_001"
    assert (
        contract.representations["markdown"].sentinel
        == "AT_MARKDOWN_SENTINEL_001"
    )
    assert contract.cache_behavior["mode"] == "variant_by_accept"
    assert contract.limits["max_body_bytes"] == 1048576
    assert validate_contract(contract).ok


def test_valid_dict_parses(valid_data):
    contract = parse_contract(valid_data)
    assert contract.name.startswith("Example site")
    assert validate_contract(contract).ok


def test_schema_file_matches_module():
    on_disk = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert on_disk == CONTRACT_SCHEMA


@pytest.mark.parametrize("field", REQUIRED_TOP_LEVEL)
def test_missing_top_level_field_rejected(valid_data, field):
    del valid_data[field]
    with pytest.raises(ContractError, match="missing required field"):
        parse_contract(valid_data)


def test_missing_nested_field_rejected(valid_data):
    del valid_data["representations"]["html"]["sentinel"]
    with pytest.raises(ContractError, match="missing required field"):
        parse_contract(valid_data)


def test_unknown_top_level_field_rejected(valid_data):
    valid_data["surprise"] = True
    with pytest.raises(ContractError, match="unsupported field"):
        parse_contract(valid_data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["representations"]["html"].update({"extra": 1}),
        lambda d: d["representations"].update({"text": {}}),
        lambda d: d["cache_behavior"].update({"unknown_mode": "x"}),
        lambda d: d["request_headers"].update({"cookie": "abc"}),
        lambda d: d["limits"].update({"max_redirects": 3}),
    ],
)
def test_unknown_nested_field_rejected(valid_data, mutate):
    mutate(valid_data)
    with pytest.raises(ContractError, match="unsupported field"):
        parse_contract(valid_data)


def test_duplicate_sentinel_rejected(valid_data):
    valid_data["representations"]["markdown"]["sentinel"] = (
        valid_data["representations"]["html"]["sentinel"]
    )
    with pytest.raises(ContractError, match="must be different"):
        parse_contract(valid_data)


def test_sentinel_with_whitespace_rejected(valid_data):
    valid_data["representations"]["html"]["sentinel"] = "AT HTML SENTINEL"
    with pytest.raises(ContractError, match="whitespace"):
        parse_contract(valid_data)


@pytest.mark.parametrize(
    "rep,field,value",
    [
        ("html", "accept", "text/plain"),
        ("html", "accept", "text/markdown"),
        ("markdown", "accept", "text/html"),
        ("markdown", "accept", "text/markdown; charset=utf-8"),
        ("html", "expected_status", 404),
        ("markdown", "expected_status", 200.5),
        ("html", "expected_content_type", "text/html"),
        ("markdown", "expected_content_type", "text/html; charset=utf-8"),
    ],
)
def test_frozen_representation_value_rejected(valid_data, rep, field, value):
    valid_data["representations"][rep][field] = value
    with pytest.raises(ContractError):
        parse_contract(valid_data)


def test_public_url_rejected(valid_data):
    valid_data["url"] = "http://93.184.216.34:18765/doc"
    with pytest.raises(ContractError, match="non-loopback"):
        parse_contract(valid_data)


def test_public_origin_url_rejected(valid_data):
    valid_data["origin_url"] = "http://93.184.216.34:18766/doc"
    with pytest.raises(ContractError, match="non-loopback"):
        parse_contract(valid_data)


def test_https_url_rejected(valid_data):
    valid_data["url"] = "https://127.0.0.1:18765/doc"
    with pytest.raises(ContractError, match="only 'http'"):
        parse_contract(valid_data)


def test_url_origin_path_mismatch_rejected(valid_data):
    valid_data["origin_url"] = "http://127.0.0.1:18766/other"
    with pytest.raises(ContractError, match="same path"):
        parse_contract(valid_data)


def test_url_origin_same_port_rejected(valid_data):
    valid_data["origin_url"] = "http://127.0.0.1:18765/doc"
    with pytest.raises(ContractError, match="different ports"):
        parse_contract(valid_data)


def test_no_store_with_max_age_rejected(valid_data):
    valid_data["cache_behavior"] = {
        "mode": "no_store",
        "vary_accept": "not_required",
        "max_age_seconds": 60,
    }
    with pytest.raises(ContractError, match="no_store"):
        parse_contract(valid_data)


def test_no_store_contract_valid(valid_data):
    valid_data["cache_behavior"] = {
        "mode": "no_store",
        "vary_accept": "not_required",
        "max_age_seconds": None,
    }
    contract = parse_contract(valid_data)
    assert contract.cache_behavior["mode"] == "no_store"
    assert validate_contract(contract).ok


def test_unknown_cache_mode_rejected(valid_data):
    valid_data["cache_behavior"]["mode"] = "force_uri_only"
    with pytest.raises(ContractError):
        parse_contract(valid_data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("user_agent", "curl/8.0"),
        ("accept_encoding", "gzip"),
        ("accept_language", "fr"),
    ],
)
def test_fixed_request_header_value_rejected(valid_data, field, value):
    valid_data["request_headers"][field] = value
    with pytest.raises(ContractError):
        parse_contract(valid_data)


def test_cookie_in_request_headers_rejected(valid_data):
    # Unknown header names are rejected by the schema (additionalProperties)
    # and would also fail the whitelist check; either way it must fail.
    valid_data["request_headers"]["cookie"] = "session=abc"
    with pytest.raises(ContractError, match="unsupported field"):
        parse_contract(valid_data)


def test_limits_over_1mib_rejected(valid_data):
    valid_data["limits"]["max_body_bytes"] = 1048577
    with pytest.raises(ContractError):
        parse_contract(valid_data)


def test_metadata_free_form_allowed(valid_data):
    valid_data["metadata"] = {"anything": [1, 2, {"goes": True}]}
    contract = parse_contract(valid_data)
    assert validate_contract(contract).ok


def test_defaults_applied(valid_data):
    del valid_data["cache_behavior"]["vary_accept"]
    del valid_data["cache_behavior"]["max_age_seconds"]
    del valid_data["limits"]["max_body_bytes"]
    del valid_data["limits"]["request_timeout_seconds"]
    contract = parse_contract(valid_data)
    assert contract.cache_behavior["vary_accept"] == "advisory"
    assert contract.cache_behavior["max_age_seconds"] is None
    assert contract.limits["max_body_bytes"] == 1048576
    assert contract.limits["request_timeout_seconds"] == 5.0


def test_missing_file_rejected():
    with pytest.raises(ContractError, match="cannot read"):
        load_contract(ROOT / "contracts" / "does-not-exist.json")


def test_malformed_json_file_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ContractError, match="not valid JSON"):
        load_contract(bad)


def test_duplicate_json_key_rejected(tmp_path):
    dup = tmp_path / "dup.json"
    dup.write_text('{"schema": "a", "schema": "b"}', encoding="utf-8")
    with pytest.raises(ContractError, match="duplicate JSON key"):
        load_contract(dup)


def test_validate_contract_reports_errors(valid_data):
    # Build an unchecked Contract directly and prove validate_contract
    # catches it instead of trusting the constructor.
    bad = parse_contract(copy.deepcopy(valid_data))
    object.__setattr__(bad, "url", "http://93.184.216.34:18765/doc")
    result = validate_contract(bad)
    assert not result.ok
    assert any("non-loopback" in err for err in result.errors)


def test_validate_contract_rejects_non_contract():
    result = validate_contract("not a contract")  # type: ignore[arg-type]
    assert not result.ok


def test_contract_hash_repeat_consistent(valid_contract):
    first = canonical_contract_hash(valid_contract)
    assert re.fullmatch(r"[0-9a-f]{64}", first)
    assert canonical_contract_hash(valid_contract) == first
    # A second, independently parsed instance hashes identically.
    second = load_contract(EXAMPLE)
    assert canonical_contract_hash(second) == first


def test_contract_hash_key_order_independent(valid_data):
    forward = parse_contract(copy.deepcopy(valid_data))
    # Serialise with keys sorted and re-parse: same hash.
    sorted_keys_json = json.dumps(valid_data, sort_keys=True, indent=2)
    reparsed = parse_contract(json.loads(sorted_keys_json))
    assert canonical_contract_hash(reparsed) == canonical_contract_hash(forward)


def test_contract_hash_changes_when_input_changes(valid_data, valid_contract):
    valid_data["representations"]["html"]["sentinel"] = "AT_HTML_SENTINEL_002"
    changed = parse_contract(valid_data)
    assert canonical_contract_hash(changed) != canonical_contract_hash(
        valid_contract
    )
