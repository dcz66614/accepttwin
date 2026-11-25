"""Unit tests for Canonical JSON (§10.4) and contract-hash determinism.

Covers: volatile fields (generated time, duration_ms / bare ``duration``,
process id, temporary paths, dynamic ports, ``uuid``, ``request_id``,
receivedAt) never enter the canonical form; keys are sorted; no extra
whitespace; header names lower-cased; repeated hashing of the same contract
is identical (I-08). ``cache_entry_id`` is NOT volatile (§5.3/§8 evidence
field) and is retained.
"""

from __future__ import annotations

import json

from accepttwin.contract import (
    canonical_contract_hash,
    canonical_json_bytes,
    load_contract,
    parse_contract,
)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "contracts" / "site.json"


def test_no_extra_whitespace_and_sorted_keys():
    data = {"b": 1, "a": {"d": 4, "c": 3}}
    assert canonical_json_bytes(data) == b'{"a":{"c":3,"d":4},"b":1}'


def test_volatile_fields_stripped_at_any_depth():
    data = {
        "generated_at": "2026-11-24T13:00:00Z",
        "duration_ms": 12,
        "process_id": 1234,
        "temporary_path": "/tmp/xyz",
        "ephemeral_port": 54321,
        "receivedAt": "2026-11-24T13:00:00Z",
        "received_at": "2026-11-24T13:00:00Z",
        "nested": {
            "generated_at": "2026-11-24T13:00:00Z",
            "duration_ms": 5,
            "keep": "yes",
        },
        "keep": "yes",
    }
    decoded = json.loads(canonical_json_bytes(data))
    assert decoded == {"nested": {"keep": "yes"}, "keep": "yes"}


def test_volatile_uuid_request_id_duration_stripped():
    # P1-01 (§10.4): random UUIDs and non-deterministic cache request IDs
    # (bare ``uuid`` / ``request_id`` / ``duration`` keys) must never enter
    # the canonical form, at any depth.
    data = {
        "uuid": "11111111-2222-3333-4444-555555555555",
        "request_id": "req-9f8e7d6c-1234",
        "duration": 0.042,
        "nested": {
            "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "request_id": "req-other",
            "duration": 1.5,
            "keep": "yes",
        },
        "a": 1,
    }
    decoded = json.loads(canonical_json_bytes(data))
    assert decoded == {"nested": {"keep": "yes"}, "a": 1}
    assert "uuid" not in decoded and "uuid" not in decoded["nested"]
    assert "request_id" not in decoded
    assert "request_id" not in decoded["nested"]
    assert "duration" not in decoded and "duration" not in decoded["nested"]
    # Varying only a volatile value must not change the canonical bytes...
    changed_uuid = dict(data, uuid="99999999-8888-7777-6666-555555555555")
    assert canonical_json_bytes(changed_uuid) == canonical_json_bytes(data)
    # ...while changing a real field must (control: hash still sensitive
    # to genuine input changes).
    changed_real = dict(data, a=2)
    assert canonical_json_bytes(changed_real) != canonical_json_bytes(data)
    # cache_entry_id is an evidence field (§5.3/§8), NOT volatile: retained.
    assert json.loads(
        canonical_json_bytes({"cache_entry_id": "ce-001", "a": 1})
    ) == {"cache_entry_id": "ce-001", "a": 1}


def test_header_names_lowercased_and_values_normalised():
    data = {
        "request_headers": {
            "Accept-Encoding": "  identity  ",
            "User-Agent": "AcceptTwin/1.0.0",
        }
    }
    decoded = json.loads(canonical_json_bytes(data))
    assert decoded == {
        "request_headers": {
            "accept-encoding": "identity",
            "user-agent": "AcceptTwin/1.0.0",
        }
    }


def test_utf8_not_escaped():
    assert "中文".encode("utf-8") in canonical_json_bytes({"name": "中文"})


def test_canonical_bytes_deterministic_across_key_order():
    first = {"a": 1, "b": {"x": 1, "y": 2}, "c": [3, 2, 1]}
    second = {"c": [3, 2, 1], "b": {"y": 2, "x": 1}, "a": 1}
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_contract_hash_ignores_volatile_fields():
    contract = load_contract(EXAMPLE)
    base = canonical_contract_hash(contract)
    # The same contract dict plus volatile noise must hash identically,
    # because volatile fields never enter the canonical form.
    noisy = contract.as_dict()
    noisy.update(
        {
            "generated_at": "2026-11-24T13:00:00Z",
            "duration_ms": 99,
            "process_id": 1,
            "temporary_path": "/tmp/abc",
            "ephemeral_port": 40000,
        }
    )
    assert canonical_json_bytes(noisy) == canonical_json_bytes(
        contract.as_dict()
    )
    assert base == canonical_contract_hash(contract)


def test_hash_repeat_100_consistent():
    contract = load_contract(EXAMPLE)
    expected = canonical_contract_hash(contract)
    assert all(
        canonical_contract_hash(load_contract(EXAMPLE)) == expected
        for _ in range(100)
    )


def test_hash_differs_for_different_contracts():
    one = load_contract(EXAMPLE)
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["contract_id"] = "site-example-002"
    two = parse_contract(data)
    assert canonical_contract_hash(one) != canonical_contract_hash(two)


def test_contract_hash_ignores_loopback_port_change():
    # ADR-003 (T007 P1-1): the same logical contract on two different
    # pairs of OS-assigned loopback ports must hash identically --
    # §10.4 "不包含动态端口". Validation still runs on the real ports:
    # both contracts are valid (same path, different ports each).
    one = load_contract(EXAMPLE)
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["url"] = "http://127.0.0.1:51111/doc"
    data["origin_url"] = "http://127.0.0.1:52222/doc"
    two = parse_contract(data)
    assert canonical_contract_hash(one) == canonical_contract_hash(two)
    # The canonical bytes themselves are equal, and the port slot
    # reads 0 (the ADR-003 placeholder), not the real port.
    decoded = json.loads(canonical_json_bytes(two.as_dict()))
    assert decoded["url"] == "http://127.0.0.1:0/doc"
    assert decoded["origin_url"] == "http://127.0.0.1:0/doc"


def test_contract_hash_port_swap_collides_by_design_t013_f01():
    # T014 / T013-F01 (P2, accepted in ADR-007 — NOT fixed by code).
    # Two contracts differing ONLY by swapping the url/origin_url
    # ports hash identically, by force of §10.4: the hash must be
    # invariant to OS-assigned loopback port values (repeat-100 with
    # fresh pairs must give one hash, §7.8 I-08), and the port values
    # are the only difference between the two contracts. Any hash
    # satisfying §10.4 therefore collides them.
    #
    # The review's first suggested fix (role-distinct placeholders,
    # url -> :0, origin_url -> :1) was implemented and probed in
    # T014: it does NOT distinguish the swap, because the placeholder
    # is a per-key constant — the swapped contract normalises to the
    # very same bytes (url :0, origin_url :1). An order-based
    # placeholder (smaller port -> :0) would distinguish the swap
    # but would make the hash depend on OS allocation order and
    # break repeat-100 determinism, so it is rejected on spec
    # grounds. The residual risk is accepted: execution and
    # validation still use the real ports (the runner connects proxy
    # vs origin by role, never by hash), no Golden scenario
    # distinguishes the pair, and no verdict is affected.
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    url, origin_url = data["url"], data["origin_url"]
    assert url != origin_url
    one = parse_contract(data)
    data["url"], data["origin_url"] = origin_url, url
    two = parse_contract(data)
    assert canonical_contract_hash(one) == canonical_contract_hash(two)
    assert canonical_json_bytes(one.as_dict()) == canonical_json_bytes(
        two.as_dict()
    )


def test_contract_hash_still_sensitive_to_semantic_url_change():
    # ADR-003: normalisation must not over-erase. Changing the path
    # or the host must still change the hash, even when the ports
    # also change.
    one = load_contract(EXAMPLE)
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["url"] = "http://127.0.0.1:51111/other"
    data["origin_url"] = "http://127.0.0.1:52222/other"
    assert canonical_contract_hash(parse_contract(data)) != (
        canonical_contract_hash(one)
    )
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["url"] = "http://localhost:51111/doc"
    data["origin_url"] = "http://localhost:52222/doc"
    assert canonical_contract_hash(parse_contract(data)) != (
        canonical_contract_hash(one)
    )


def test_canonical_json_keeps_non_loopback_port():
    # ADR-003 bounds the normalisation to loopback URLs: a
    # non-loopback host's port is part of the service identity.
    assert canonical_json_bytes(
        {"url": "http://93.184.216.34:8080/doc"}
    ) != canonical_json_bytes({"url": "http://93.184.216.34:9090/doc"})
    # The scheme is preserved, not normalised away (only http loopback
    # ports are rewritten; an https URL keeps its port as-is).
    assert json.loads(
        canonical_json_bytes({"url": "https://127.0.0.1:51111/doc"})
    ) == {"url": "https://127.0.0.1:51111/doc"}
    # A loopback URL without an explicit port is left untouched -- it
    # stays distinct from the explicit-port form.
    assert json.loads(canonical_json_bytes({"url": "http://127.0.0.1/doc"})) == {
        "url": "http://127.0.0.1/doc"
    }
    # IPv6 loopback is normalised the same way.
    assert json.loads(
        canonical_json_bytes({"url": "http://[::1]:51111/doc"})
    ) == {"url": "http://[::1]:0/doc"}
    # An unparseable value is returned unchanged, never raised on.
    assert json.loads(canonical_json_bytes({"url": "not a url"})) == {
        "url": "not a url"
    }
