"""Performance + determinism tests (P032 T012, §10.4/§10.5, §18 AC10/AC11).

Every test here executes real local HTTP (fresh origin + proxy pair
per scenario, via ``s0_harness.run_scenario``) — no cached report is
ever read for a timing or a hash. The full 100-run check lives in
``python -m accepttwin benchmark --suite all`` (and in
``scripts/run_s0.py``); these tests pin the same mechanism at small
scale so the suite stays fast.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from accepttwin.contract import canonical_json_bytes  # noqa: E402
from s0_harness import load_scenario, run_scenario  # noqa: E402

FORBIDDEN = (
    b"generated_at",
    b"duration_ms",
    b"process_id",
    b"temporary_path",
    b"ephemeral_port",
    b"timestamp",
    b"uuid",
    b"random",
)


@pytest.mark.parametrize("scenario_id", ["C01", "C11", "E13"])
def test_single_scenario_four_experiments_under_one_second(scenario_id: str) -> None:
    fixture_dir = ROOT / "fixtures" / (
        "s0" if scenario_id.startswith("C") else "extended"
    )
    fixture = load_scenario(scenario_id, fixture_dir)
    outcome = run_scenario(
        scenario_id,
        fixture_dir=fixture_dir,
        contract_prefix="s0" if scenario_id.startswith("C") else "ext",
    )
    # 8 real HTTP requests: 2 direct-origin baselines + 6 proxied
    # (2 cold + 2 x 2 warm). §10.5: report generation is excluded
    # from this duration; duration_seconds covers run_experiments.
    assert len(outcome.run.observations) == 8
    assert len(outcome.run.reset_evidence) == 4
    assert outcome.duration_seconds < 1.0, (
        f"{scenario_id} took {outcome.duration_seconds:.3f}s, limit 1.0s"
    )
    assert outcome.production.verdict == fixture["expected_verdict"]
    assert outcome.production.first_error == fixture["expected_first_error"]


def test_canonical_json_has_no_nondeterministic_fields() -> None:
    outcome = run_scenario("C01")
    raw = canonical_json_bytes(outcome.report)
    for needle in FORBIDDEN:
        assert needle not in raw, f"canonical JSON contains {needle!r}"
    assert hashlib.sha256(raw).hexdigest() == outcome.report_hash


def test_repeat_three_fresh_pairs_same_hash() -> None:
    """Small-scale form of the repeat-100 gate: fresh pair (fresh
    OS-assigned ports) per run, real experiments every time."""
    hashes = set()
    for i in range(3):
        outcome = run_scenario("C01", namespace_prefix=f"perf-repeat-{i + 1}")
        assert outcome.production.verdict == "PASS_OBSERVED"
        hashes.add(outcome.report_hash)
    assert len(hashes) == 1


def test_run_ignores_environment_proxies() -> None:
    """With every proxy variable pointed at a dead proxy, a live
    scenario still passes: the product never reads the environment
    proxy (§0.2 item 7, §17.4 item 5)."""
    for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ[var] = "http://127.0.0.1:1"
    try:
        outcome = run_scenario("C01")
    finally:
        for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            os.environ.pop(var, None)
    assert outcome.production.verdict == "PASS_OBSERVED"
    assert outcome.duration_seconds < 1.0
