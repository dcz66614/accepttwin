"""Unit tests (P032 P2-01 FIX-R1): the widened Oracle parity check in
``scripts/verify_s0.py``.

The runtime parity (``scripts/s0_harness.py`` check_parity) and the
report-builder parity already compare the eight per-request verified
MISS/HIT/BYPASS states; the independent verifier did not. These tests
pin the verifier's widened definition
(:func:`verify_s0.check_oracle_parity`): verdict + diagnostics +
first error + all eight states, with a missing or malformed state
list failing closed instead of counting as agreement.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFY_S0 = ROOT / "scripts" / "verify_s0.py"


def _load_verify_s0():
    spec = importlib.util.spec_from_file_location("verify_s0", VERIFY_S0)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("verify_s0", module)
    spec.loader.exec_module(module)
    return module


verify_s0 = _load_verify_s0()


def _load_evidence(sid: str) -> tuple[dict, dict]:
    production = json.loads(
        (ROOT / "evidence" / "S0" / sid / "production.json").read_text(
            encoding="utf-8"
        )
    )
    oracle = json.loads(
        (ROOT / "evidence" / "S0" / sid / "oracle.json").read_text(encoding="utf-8")
    )
    return production, oracle


def test_parity_passes_on_real_c01_evidence():
    production, oracle = _load_evidence("C01")
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert ok, detail


def test_parity_passes_on_real_c11_bleed_evidence():
    production, oracle = _load_evidence("C11")
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert ok, detail
    states = {s["request_index"]: s["state"] for s in oracle["verified_cache_states"]}
    assert states[6] == "HIT" and states[8] == "HIT"


def test_parity_passes_on_real_c21_unconfirmed_evidence():
    # C21: the classifier confirms nothing (CACHE_STATE_UNKNOWN) and
    # the Oracle reports None — the widened check must accept that
    # agreement, not treat "unknown" as a mismatch.
    production, oracle = _load_evidence("C21")
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert ok, detail


def test_parity_fails_on_single_state_mismatch():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    oracle["verified_cache_states"][5]["state"] = "HIT"
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok
    assert "verified_cache_states" in detail


def test_parity_fails_when_oracle_states_missing():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    del oracle["verified_cache_states"]
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok
    assert "verified_cache_states" in detail


def test_parity_fails_when_oracle_states_short():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    oracle["verified_cache_states"] = oracle["verified_cache_states"][:7]
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok


def test_parity_fails_on_illegal_state_value():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    oracle["verified_cache_states"][2]["state"] = "MAYBE"
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok


def test_parity_fails_on_duplicate_request_index():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    oracle["verified_cache_states"][7]["request_index"] = 7
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok


def test_parity_fails_when_production_states_missing():
    production, oracle = _load_evidence("C01")
    production = copy.deepcopy(production)
    del production["confirmed_cache_states"]
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok
    assert "confirmed_cache_states" in detail


def test_parity_still_fails_on_verdict_mismatch():
    production, oracle = _load_evidence("C01")
    oracle = copy.deepcopy(oracle)
    oracle["verdict"] = "CONTRACT_MISMATCH"
    ok, detail = verify_s0.check_oracle_parity(production, oracle)
    assert not ok
    assert "verdict" in detail


def test_normalise_rejects_malformed_states():
    assert verify_s0._normalise_cache_states(None, production=False) is None
    assert verify_s0._normalise_cache_states([], production=False) is None
    assert (
        verify_s0._normalise_cache_states(
            [{"request_index": i, "state": "MISS"} for i in range(1, 8)],
            production=False,
        )
        is None
    )
    states = verify_s0._normalise_cache_states(
        [{"request_index": i, "state": "MISS"} for i in range(1, 9)],
        production=False,
    )
    assert states is not None and len(states) == 8
    # Production-side CACHE_STATE_UNKNOWN normalises to None.
    states = verify_s0._normalise_cache_states(
        [
            {"request_index": i, "state": "CACHE_STATE_UNKNOWN"}
            for i in range(1, 9)
        ],
        production=True,
    )
    assert states is not None and all(s["state"] is None for s in states)
    # ... but the Oracle side must not use it.
    assert (
        verify_s0._normalise_cache_states(
            [
                {"request_index": i, "state": "CACHE_STATE_UNKNOWN"}
                for i in range(1, 9)
            ],
            production=False,
        )
        is None
    )
