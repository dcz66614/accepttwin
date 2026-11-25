"""Integration tests for the four-experiment runner (P032 T005).

Acceptance criteria (IMPLEMENTATION_PLAN T005 / PROJECT_BOOK §6,
§10.2):

1. Every scenario has O-H, O-M, H-COLD, M-COLD, H->M, M->H.
2. Each warm-cache order contains two real requests.
3. A reset record exists between the four experiments.
4. No reset happens between the two requests of a warm experiment.
5. At least one healthy and one bleed scenario really complete all
   four experiments.
6. (Hard requirement, T002 review P2-03) The HTTP client never reads
   proxy environment variables: with HTTP_PROXY/HTTPS_PROXY pointing
   at a dead proxy, the run still succeeds.

Every test makes real HTTP requests over localhost (``http.client``
inside the runner, never a preset report). The origin and the proxy
bind OS-assigned loopback ports (``port=0``) except for the one test
that exercises runner-owned services on explicitly allocated ports.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import socket
from pathlib import Path

import pytest

from accepttwin.cache_evidence import CACHE_STATE_UNKNOWN
from accepttwin.contract import parse_contract
from accepttwin.evidence import (
    RAW_OBSERVATIONS_FORMAT,
    read_evidence_file,
)
from accepttwin.experiment_runner import (
    STEP_NAMES,
    ExperimentError,
    ExperimentRun,
    run_experiments,
)
from accepttwin.cache_proxy import ControlledCacheProxy
from accepttwin.origin_server import (
    HTML_SENTINEL,
    MARKDOWN_SENTINEL,
    SyntheticOrigin,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"

HTML_ACCEPT = "text/html"
MARKDOWN_ACCEPT = "text/markdown"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_contract(proxy_url: str, origin_url: str, *, mode="variant_by_accept"):
    """A valid contract pointing at the given live service URLs."""
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["url"] = proxy_url
    data["origin_url"] = origin_url
    if mode == "no_store":
        data["cache_behavior"] = {
            "mode": "no_store",
            "vary_accept": "not_required",
            "max_age_seconds": None,
        }
    else:
        data["cache_behavior"] = {
            "mode": "variant_by_accept",
            "vary_accept": "advisory",
            "max_age_seconds": 60,
        }
    return parse_contract(data)


class Pair:
    """A running (origin, proxy, contract) triple; use as a context manager."""

    def __init__(self, mode, scenario="healthy", *, no_store=False):
        self.origin = SyntheticOrigin(port=0, scenario=scenario)
        self.origin.start()
        kwargs: dict = {"port": 0, "mode": mode, "origin_url": self.origin.url}
        self.proxy = ControlledCacheProxy(**kwargs)
        self.proxy.start()
        if no_store:
            contract = build_contract(self.proxy.url, self.origin.url, mode="no_store")
            self.proxy.stop()
            self.proxy = ControlledCacheProxy(
                port=0, mode=mode, contract=contract
            )
            self.proxy.start()
            # The rebuilt proxy binds a new port: rebuild the contract.
            contract = build_contract(self.proxy.url, self.origin.url, mode="no_store")
        else:
            contract = build_contract(self.proxy.url, self.origin.url)
        self.contract = contract

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.proxy.stop()
        self.origin.stop()
        return False


def run_pair(pair: Pair, **kwargs) -> ExperimentRun:
    return run_experiments(
        pair.contract, origin=pair.origin, proxy=pair.proxy, **kwargs
    )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Frozen order, request numbers, one URL per leg
# ---------------------------------------------------------------------------


def test_frozen_step_order_and_request_numbers():
    with Pair("respect_vary") as pair:
        run = run_pair(pair)
    assert [rec.name for rec in run.step_log] == list(STEP_NAMES)
    assert [rec.step for rec in run.step_log] == list(range(1, 26))
    assert len(run.observations) == 8
    assert [obs.request_index for obs in run.observations] == list(range(1, 9))
    assert [obs.experiment_id for obs in run.observations] == [
        "ORIGIN_HTML",
        "ORIGIN_MARKDOWN",
        "HTML_COLD",
        "MARKDOWN_COLD",
        "HTML_TO_MARKDOWN",
        "HTML_TO_MARKDOWN",
        "MARKDOWN_TO_HTML",
        "MARKDOWN_TO_HTML",
    ]
    assert [obs.requested_representation for obs in run.observations] == [
        "html", "markdown", "html", "markdown",
        "html", "markdown", "markdown", "html",
    ]
    # One URL string per leg: direct requests use origin_url, proxied
    # requests all use the same contract url (§6.2).
    assert [raw.url for raw in run.raw_observations[:2]] == [
        pair.contract.origin_url,
        pair.contract.origin_url,
    ]
    assert {raw.url for raw in run.raw_observations[2:]} == {
        pair.contract.url,
    }
    assert [raw.method for raw in run.raw_observations] == ["GET"] * 8
    assert [raw.accept for raw in run.raw_observations] == [
        HTML_ACCEPT, MARKDOWN_ACCEPT, HTML_ACCEPT, MARKDOWN_ACCEPT,
        HTML_ACCEPT, MARKDOWN_ACCEPT, MARKDOWN_ACCEPT, HTML_ACCEPT,
    ]


def test_request_observation_matches_spec_5_5_fields():
    from accepttwin.evidence import RequestObservation

    names = {f.name for f in dataclasses.fields(RequestObservation)}
    assert names == {
        "request_index",
        "experiment_id",
        "requested_representation",
        "response_status",
        "response_content_type",
        "body_sha256",
        "sentinel_match",
        "cache_status",
        "cache_key_sha256",
        "cache_entry_id",
        "origin_counter_before",
        "origin_counter_after",
        "origin_counter_delta",
    }


# ---------------------------------------------------------------------------
# Healthy scenario: all four experiments complete
# ---------------------------------------------------------------------------


def test_healthy_scenario_completes_four_experiments():
    with Pair("respect_vary") as pair:
        run = run_pair(pair)
    assert all(obs.response_status == 200 for obs in run.observations)
    assert all(obs.sentinel_match for obs in run.observations)
    assert all(raw.transport_error is None for raw in run.raw_observations)
    # Direct baselines carry no cache state; every proxied request is
    # a verified MISS in a healthy respect_vary setup.
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "MISS", "MISS", "MISS", "MISS", "MISS", "MISS",
    ]
    # Every request reached the origin exactly once (8 requests, 8
    # origin events, counter delta 8).
    assert run.origin_counter_final - run.origin_counter_baseline == 8
    assert [obs.origin_counter_delta for obs in run.observations] == [1] * 8
    assert len(run.origin_events) == 8
    assert run.verification_failures == ()
    assert len(run.step_log) == 25
    assert all(rec.ok for rec in run.step_log)


def test_resets_between_experiments_and_empty_before_each_cold():
    with Pair("respect_vary") as pair:
        run = run_pair(pair)
    # Exactly four resets, at the frozen steps 09/13/17/22 only.
    assert len(run.reset_evidence) == 4
    assert all(ev.success and ev.entries_after == 0 for ev in run.reset_evidence)
    assert [rec.step for rec in run.step_log if rec.name == "ResetCache"] == [
        9, 13, 17, 22,
    ]
    assert [ev.namespace for ev in run.reset_evidence] == [
        "t005-html-cold",
        "t005-markdown-cold",
        "t005-html-to-markdown",
        "t005-markdown-to-html",
    ]
    # Each cold / warm-first request starts from an empty cache.
    assert run.raw_observations[2].cache_entry_count_before == 0  # 003 H-COLD
    assert run.raw_observations[3].cache_entry_count_before == 0  # 004 M-COLD
    assert run.raw_observations[4].cache_entry_count_before == 0  # 005 HM-1
    assert run.raw_observations[6].cache_entry_count_before == 0  # 007 MH-1


def test_warm_experiments_have_two_real_requests_no_reset_between():
    with Pair("respect_vary") as pair:
        run = run_pair(pair)
    # Steps 19-20 and 24-25 are consecutive request steps with no
    # ResetCache step between them (§6.2 / §10.2).
    names = [rec.name for rec in run.step_log]
    assert names[18:20] == ["HTMLWarmFirst", "MarkdownWarmSecond"]
    assert names[23:25] == ["MarkdownWarmFirst", "HTMLWarmSecond"]
    for number in (5, 6, 7, 8):
        raw = run.raw_observations[number - 1]
        assert raw.transport_error is None
        assert raw.response_status == 200
        assert raw.origin_event_present is True
    # The two requests of each warm experiment are distinct origin
    # events, in order (H then M; M then H).
    accepts = [ev.accept for ev in run.origin_events]
    assert accepts == [
        HTML_ACCEPT, MARKDOWN_ACCEPT, HTML_ACCEPT, MARKDOWN_ACCEPT,
        HTML_ACCEPT, MARKDOWN_ACCEPT, MARKDOWN_ACCEPT, HTML_ACCEPT,
    ]


# ---------------------------------------------------------------------------
# Bleed scenario: all four experiments complete, bleed visible
# ---------------------------------------------------------------------------


def test_bleed_scenario_completes_four_experiments():
    with Pair("force_uri_only") as pair:
        run = run_pair(pair, proxy_mode="force_uri_only")
    assert len(run.observations) == 8
    assert all(raw.transport_error is None for raw in run.raw_observations)
    # Cold requests are MISS; each warm second request HITs the first
    # representation's entry (verified dual evidence, §5.3 B).
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "MISS", "MISS", "MISS", "HIT", "MISS", "HIT",
    ]
    # HM-2 asked for Markdown but got the HTML body; MH-2 the reverse.
    assert run.observations[5].sentinel_match is False  # 006 HM-2
    assert run.observations[7].sentinel_match is False  # 008 MH-2
    assert run.observations[5].body_sha256 == run.observations[4].body_sha256
    assert run.observations[7].body_sha256 == run.observations[6].body_sha256
    # HITs did not reach the origin: 6 origin requests, not 8.
    assert run.origin_counter_final - run.origin_counter_baseline == 6
    assert [obs.origin_counter_delta for obs in run.observations] == [
        1, 1, 1, 1, 1, 0, 1, 0,
    ]
    assert run.verification_failures == ()


def test_respect_vary_without_vary_bleeds_both_orders():
    # §11.2 C13/C14: no Vary + respect_vary keys on the URI only.
    with Pair("respect_vary", scenario="no_vary") as pair:
        run = run_pair(pair)
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "MISS", "MISS", "MISS", "HIT", "MISS", "HIT",
    ]
    assert run.observations[5].sentinel_match is False
    assert run.observations[7].sentinel_match is False


def test_manual_accept_key_healthy_without_vary():
    # §11.2 C03/C04: missing Vary alone is not a fault.
    with Pair("manual_accept_key", scenario="no_vary") as pair:
        run = run_pair(pair, proxy_mode="manual_accept_key")
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "MISS", "MISS", "MISS", "MISS", "MISS", "MISS",
    ]
    assert all(obs.sentinel_match for obs in run.observations)
    assert run.verification_failures == ()


# ---------------------------------------------------------------------------
# no-store / opaque / origin-fault scenarios still run all four experiments
# ---------------------------------------------------------------------------


def test_no_store_bypass_scenario():
    with Pair("disabled", no_store=True) as pair:
        run = run_pair(pair, proxy_mode="disabled")
    assert len(run.observations) == 8
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "BYPASS", "BYPASS", "BYPASS", "BYPASS", "BYPASS", "BYPASS",
    ]
    assert all(obs.sentinel_match for obs in run.observations)
    assert all(
        raw.cache_entry_count_after == 0 for raw in run.raw_observations[2:]
    )
    assert run.verification_failures == ()


def test_origin_fault_still_completes_all_experiments():
    # §11.2 C07: the HTML baseline is a 404, but the run must still
    # collect the remaining requests so the first error stays locatable.
    with Pair("respect_vary", scenario="html_404") as pair:
        run = run_pair(pair)
    assert len(run.observations) == 8
    assert run.observations[0].response_status == 404  # 001 O-H
    assert run.observations[1].response_status == 200  # 002 O-M
    assert all(raw.transport_error is None for raw in run.raw_observations)
    assert len(run.origin_events) == 8


def test_opaque_unknown_evidence_does_not_abort_run():
    # §11.2 C20: header evidence is hidden, so cache states are
    # UNKNOWN — but all eight requests still run and are recorded.
    with Pair("opaque") as pair:
        run = run_pair(pair, proxy_mode="opaque")
    assert len(run.observations) == 8
    assert [obs.cache_status for obs in run.observations[2:]] == [
        CACHE_STATE_UNKNOWN
    ] * 6
    assert run.verification_failures, "VerifyMissOrBypass must fail, not abort"
    assert len(run.step_log) == 25


# ---------------------------------------------------------------------------
# Hard requirement: proxy environment variables are never used (P2-03)
# ---------------------------------------------------------------------------


def test_proxy_environment_variables_ignored(monkeypatch):
    # Point every proxy variable at a dead proxy. If the client honoured
    # any of them, every request would fail; http.client never reads them.
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:1"
    with Pair("respect_vary") as pair:
        run = run_pair(pair)
    assert len(run.observations) == 8
    assert all(obs.response_status == 200 for obs in run.observations)
    assert all(raw.transport_error is None for raw in run.raw_observations)
    assert run.verification_failures == ()


def test_proxy_environment_variables_ignored_in_bleed_run(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "example.invalid")
    with Pair("force_uri_only") as pair:
        run = run_pair(pair, proxy_mode="force_uri_only")
    assert [obs.cache_status for obs in run.observations] == [
        None, None, "MISS", "MISS", "MISS", "HIT", "MISS", "HIT",
    ]


# ---------------------------------------------------------------------------
# Evidence file (T006 / T007 input): round-trip, no body text
# ---------------------------------------------------------------------------


def test_evidence_file_roundtrip_and_no_body_text(tmp_path):
    with Pair("force_uri_only") as pair:
        out = tmp_path / "raw-observations.json"
        run = run_pair(pair, output_path=out, proxy_mode="force_uri_only")
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # No response body text may enter the evidence file (§7.12 I-12):
    # neither the HTML body nor the Markdown body, nor either Sentinel
    # string (only its SHA-256 is recorded).
    assert "<!DOCTYPE html>" not in text
    assert "# AcceptTwin synthetic document" not in text
    assert HTML_SENTINEL not in text
    assert MARKDOWN_SENTINEL not in text
    assert "body_text" not in text
    assert "response_body" not in text
    data = read_evidence_file(out)
    assert data["format"] == RAW_OBSERVATIONS_FORMAT
    assert data["contract_id"] == pair.contract.contract_id
    assert len(data["observations"]) == 8
    assert len(data["steps"]) == 25
    assert [s["name"] for s in data["steps"]] == list(STEP_NAMES)
    assert len(data["resets"]) == 4
    assert len(data["origin_events"]) == 6  # bleed run: 2 HITs, no origin hit
    assert data["origin_counter_baseline"] == 0
    assert data["origin_counter_final"] == 6
    # The §5.5 projection is recoverable from each raw observation.
    for raw in data["observations"]:
        assert hashlib.sha256(b"").hexdigest() != raw["body_sha256"]
        assert len(raw["body_sha256"]) == 64
        assert len(raw["sentinel_sha256"]) == 64
        assert raw["cache_status_header"] in (
            None, "MISS", "HIT", "BYPASS",
        )
    # The run object and the file agree.
    assert run.as_dict() == data


def test_evidence_file_rejects_wrong_format(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"format": "other/v1"}), encoding="utf-8")
    with pytest.raises(ValueError, match="format"):
        read_evidence_file(bad)


# ---------------------------------------------------------------------------
# Runner-owned services and contract validation
# ---------------------------------------------------------------------------


def test_runner_creates_and_stops_own_services():
    origin_port = free_port()
    proxy_port = free_port()
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["url"] = f"http://127.0.0.1:{proxy_port}/doc"
    data["origin_url"] = f"http://127.0.0.1:{origin_port}/doc"
    contract = parse_contract(data)
    run = run_experiments(contract, scenario="healthy", proxy_mode="respect_vary")
    assert len(run.observations) == 8
    assert all(obs.response_status == 200 for obs in run.observations)
    assert run.verification_failures == ()
    # Services the runner created are stopped again afterwards.
    assert not port_open(origin_port)
    assert not port_open(proxy_port)


def test_non_loopback_contract_rejected():
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["url"] = "http://93.184.216.34/doc"
    data["origin_url"] = "http://93.184.216.34:18766/doc"
    with pytest.raises((ExperimentError, ValueError)):
        run_experiments(data)


def test_supplied_origin_disagreeing_with_contract_rejected():
    with Pair("respect_vary") as pair:
        other_origin = SyntheticOrigin(port=0, scenario="healthy")
        other_origin.start()
        try:
            with pytest.raises(ExperimentError, match="disagrees"):
                run_experiments(
                    pair.contract, origin=other_origin, proxy=pair.proxy
                )
        finally:
            other_origin.stop()


def test_supplied_proxy_with_mismatched_mode_rejected():
    # Step 04 fail-closed (T005 review P2-4): a supplied proxy whose
    # mode disagrees with the mode the run was asked to use is
    # rejected before any request is sent. Here a "force_uri_only"
    # proxy is supplied against a "variant_by_accept" contract with
    # the default proxy_mode ("respect_vary"): the modes disagree,
    # so the run raises instead of silently proceeding under the
    # wrong proxy mode. A deliberate bleed run must declare its mode
    # explicitly via proxy_mode="force_uri_only".
    with Pair("force_uri_only") as pair:
        with pytest.raises(ExperimentError, match="disagrees"):
            run_pair(pair)


def test_ports_not_listening_rejected(monkeypatch):
    # Step 05 fail-closed: if the port check reports a service down,
    # the run raises before any request is sent (simulated here by
    # stubbing the check — a runner-created service always listens,
    # so the live path cannot produce this state on its own).
    monkeypatch.setattr(
        "accepttwin.experiment_runner._check_port_listening",
        lambda *args, **kwargs: False,
    )
    with Pair("respect_vary") as pair:
        with pytest.raises(ExperimentError, match="not listening"):
            run_pair(pair)
