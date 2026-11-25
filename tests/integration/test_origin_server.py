"""Integration tests for the synthetic origin server (P032 T003).

Acceptance criteria (IMPLEMENTATION_PLAN T003):

1. HTML Accept returns HTML.
2. Markdown Accept returns Markdown.
3. The two Sentinels are different.
4. Origin status is controllable (fault fixtures).
5. Origin Content-Type is controllable (fault fixtures).
6. Request counting is accurate.
7. Event order is accurate.
8. Response bodies are not written to ordinary logs.
9. The port is released after the server stops.

Every test makes real HTTP requests over localhost (``http.client``,
no proxy — the origin never consults proxy environment variables).
Servers bind an OS-assigned loopback port (``port=0``) except for the
one test that pins the frozen default port 18766 from
``contracts/site.json``.
"""

from __future__ import annotations

import http.client
import json
import logging
import socket
from pathlib import Path

import pytest

from accepttwin.contract import load_contract
from accepttwin.origin_server import (
    DEFAULT_PORT,
    HTML_SENTINEL,
    MARKDOWN_SENTINEL,
    OriginServerError,
    ScenarioError,
    SyntheticOrigin,
    default_fixture_dir,
    load_scenario,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"

HTML_ACCEPT = "text/html"
MARKDOWN_ACCEPT = "text/markdown"


def get(port: int, path: str = "/doc", accept: str = HTML_ACCEPT):
    """One real GET over loopback; returns (status, headers dict, body)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path, headers={"Accept": accept})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    finally:
        conn.close()


@pytest.fixture()
def origin():
    """A healthy origin on an OS-assigned loopback port."""
    server = SyntheticOrigin(port=0, scenario="healthy")
    server.start()
    yield server
    server.stop()


@pytest.fixture()
def contract():
    return load_contract(CONTRACT_PATH)


# ---------------------------------------------------------------------------
# AC1: HTML Accept returns HTML
# ---------------------------------------------------------------------------


def test_html_accept_returns_html(origin):
    status, headers, body = get(origin.port, accept=HTML_ACCEPT)
    assert status == 200
    assert headers["content-type"] == "text/html; charset=utf-8"
    text = body.decode("utf-8")
    assert HTML_SENTINEL in text
    assert MARKDOWN_SENTINEL not in text
    assert text.lstrip().lower().startswith("<!doctype html>")
    assert headers.get("vary") == "Accept"


# ---------------------------------------------------------------------------
# AC2: Markdown Accept returns Markdown
# ---------------------------------------------------------------------------


def test_markdown_accept_returns_markdown(origin):
    status, headers, body = get(origin.port, accept=MARKDOWN_ACCEPT)
    assert status == 200
    assert headers["content-type"] == "text/markdown; charset=utf-8"
    text = body.decode("utf-8")
    assert MARKDOWN_SENTINEL in text
    assert HTML_SENTINEL not in text
    assert text.startswith("# AcceptTwin synthetic document")


# ---------------------------------------------------------------------------
# AC3: the two Sentinels are different
# ---------------------------------------------------------------------------


def test_sentinels_are_different(contract):
    html_sentinel = contract.representations["html"].sentinel
    markdown_sentinel = contract.representations["markdown"].sentinel
    assert html_sentinel != markdown_sentinel
    assert html_sentinel == HTML_SENTINEL
    assert markdown_sentinel == MARKDOWN_SENTINEL
    # Each body carries exactly one Sentinel occurrence, and only its own.
    origin = SyntheticOrigin(port=0, scenario="healthy")
    origin.start()
    try:
        _, _, html_body = get(origin.port, accept=HTML_ACCEPT)
        _, _, md_body = get(origin.port, accept=MARKDOWN_ACCEPT)
    finally:
        origin.stop()
    assert html_body.decode("utf-8").count(HTML_SENTINEL) == 1
    assert md_body.decode("utf-8").count(MARKDOWN_SENTINEL) == 1


# ---------------------------------------------------------------------------
# AC4: origin status is controllable (fault fixtures)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario, html_status, md_status",
    [
        ("markdown_404", 200, 404),
        ("html_404", 404, 200),
    ],
)
def test_status_fault_fixture(scenario, html_status, md_status):
    server = SyntheticOrigin(port=0, scenario=scenario)
    server.start()
    try:
        h_status, _, _ = get(server.port, accept=HTML_ACCEPT)
        m_status, _, _ = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_status == html_status
    assert m_status == md_status


def test_healthy_fixture_is_200_for_both():
    server = SyntheticOrigin(port=0, scenario="healthy")
    server.start()
    try:
        assert get(server.port, accept=HTML_ACCEPT)[0] == 200
        assert get(server.port, accept=MARKDOWN_ACCEPT)[0] == 200
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# AC5: origin Content-Type is controllable (fault fixtures)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario, html_ct, md_ct",
    [
        (
            "html_wrong_content_type",
            "text/plain; charset=utf-8",
            "text/markdown; charset=utf-8",
        ),
        (
            "markdown_wrong_content_type",
            "text/html; charset=utf-8",
            "text/html; charset=utf-8",
        ),
    ],
)
def test_content_type_fault_fixture(scenario, html_ct, md_ct):
    server = SyntheticOrigin(port=0, scenario=scenario)
    server.start()
    try:
        _, h_headers, _ = get(server.port, accept=HTML_ACCEPT)
        _, m_headers, _ = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_headers["content-type"] == html_ct
    assert m_headers["content-type"] == md_ct


# ---------------------------------------------------------------------------
# AC5b/AC4b: Sentinel is controllable (fault fixtures)
# ---------------------------------------------------------------------------


def test_sentinel_fault_fixtures():
    server = SyntheticOrigin(port=0, scenario="markdown_sentinel_missing")
    server.start()
    try:
        _, _, md_body = get(server.port, accept=MARKDOWN_ACCEPT)
        _, _, html_body = get(server.port, accept=HTML_ACCEPT)
    finally:
        server.stop()
    assert MARKDOWN_SENTINEL not in md_body.decode("utf-8")
    assert HTML_SENTINEL in html_body.decode("utf-8")

    server = SyntheticOrigin(port=0, scenario="html_sentinel_wrong")
    server.start()
    try:
        _, _, html_body = get(server.port, accept=HTML_ACCEPT)
    finally:
        server.stop()
    text = html_body.decode("utf-8")
    assert HTML_SENTINEL not in text
    assert "AT_HTML_SENTINEL_999" in text


# ---------------------------------------------------------------------------
# AC6: request counting is accurate
# ---------------------------------------------------------------------------


def test_request_count_is_accurate(origin):
    before = origin.counter_snapshot()
    assert before.total_requests == 0
    get(origin.port, accept=HTML_ACCEPT)
    get(origin.port, accept=HTML_ACCEPT)
    get(origin.port, accept=MARKDOWN_ACCEPT)
    get(origin.port, accept="application/json")  # 406, still a request
    get(origin.port, path="/other", accept=HTML_ACCEPT)  # 404, still a request
    after = origin.counter_snapshot()
    assert after.total_requests == before.total_requests + 5
    assert after.html_requests == 3  # 2 x /doc HTML + 1 x /other HTML
    assert after.markdown_requests == 1
    assert after.other_requests == 1  # the application/json request


def test_counter_delta_matches_requests_across_scenarios():
    server = SyntheticOrigin(port=0, scenario="markdown_404")
    server.start()
    try:
        before = server.counter_snapshot()
        get(server.port, accept=MARKDOWN_ACCEPT)  # 404 still counts
        get(server.port, accept=MARKDOWN_ACCEPT)
        after = server.counter_snapshot()
    finally:
        server.stop()
    assert after.total_requests - before.total_requests == 2
    assert after.markdown_requests - before.markdown_requests == 2


# ---------------------------------------------------------------------------
# AC7: event order is accurate
# ---------------------------------------------------------------------------


def test_event_log_order_is_accurate(origin):
    plan = [
        ("GET", "/doc", HTML_ACCEPT, 200),
        ("GET", "/doc", MARKDOWN_ACCEPT, 200),
        ("GET", "/doc", HTML_ACCEPT, 200),
        ("GET", "/other", HTML_ACCEPT, 404),
        ("GET", "/doc", "application/json", 406),
    ]
    for _, path, accept, _ in plan:
        get(origin.port, path=path, accept=accept)
    events = origin.event_log()
    assert len(events) == len(plan)
    for i, (event, (method, path, accept, status)) in enumerate(zip(events, plan), start=1):
        assert event.index == i
        assert event.method == method
        assert event.path == path
        assert event.accept == accept
        assert event.status == status
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps), "event timestamps must be monotonic"
    assert all(t2 >= t1 for t1, t2 in zip(timestamps, timestamps[1:]))
    # The log is a snapshot copy: mutating it must not corrupt the origin.
    events.clear()
    assert len(origin.event_log()) == len(plan)


# ---------------------------------------------------------------------------
# AC8: response bodies are not written to ordinary logs
# ---------------------------------------------------------------------------


def test_body_not_written_to_ordinary_logs(origin, caplog):
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = CaptureHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    old_level = root.level
    root.setLevel(logging.DEBUG)
    logging.getLogger("accepttwin").setLevel(logging.DEBUG)
    try:
        with caplog.at_level(logging.DEBUG):
            get(origin.port, accept=HTML_ACCEPT)
            get(origin.port, accept=MARKDOWN_ACCEPT)
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
    forbidden = [
        HTML_SENTINEL,
        MARKDOWN_SENTINEL,
        "AcceptTwin synthetic document",
        "Synthetic Markdown representation",
    ]
    for record in records:
        message = record.getMessage()
        for fragment in forbidden:
            assert fragment not in message, f"log record leaks body text: {message!r}"
    for fragment in forbidden:
        assert fragment not in caplog.text


# ---------------------------------------------------------------------------
# AC9: the port is released after the server stops
# ---------------------------------------------------------------------------


def test_port_released_after_stop():
    server = SyntheticOrigin(port=0, scenario="healthy")
    server.start()
    port = server.port
    assert get(port, accept=HTML_ACCEPT)[0] == 200
    server.stop()
    assert not server.is_running
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
    # The same port can be bound again immediately.
    again = SyntheticOrigin(port=port, scenario="healthy")
    again.start()
    try:
        assert get(port, accept=MARKDOWN_ACCEPT)[0] == 200
    finally:
        again.stop()


def test_stop_is_idempotent():
    server = SyntheticOrigin(port=0, scenario="healthy")
    server.start()
    server.stop()
    server.stop()  # must not raise


# ---------------------------------------------------------------------------
# Contract / default-port wiring (§5.1.1)
# ---------------------------------------------------------------------------


def test_default_port_matches_contract_origin_url(contract):
    assert contract.origin_url == f"http://127.0.0.1:{DEFAULT_PORT}/doc"
    assert DEFAULT_PORT == 18766
    server = SyntheticOrigin(contract=contract)
    assert server.port == 18766
    assert server.url == contract.origin_url
    server.start()
    try:
        assert get(18766, accept=HTML_ACCEPT)[0] == 200
    finally:
        server.stop()


def test_explicit_values_disagreeing_with_contract_are_rejected(contract):
    with pytest.raises(OriginServerError):
        SyntheticOrigin(contract=contract, port=19999)
    with pytest.raises(OriginServerError):
        SyntheticOrigin(contract=contract, path="/other")


def test_double_start_is_rejected(origin):
    with pytest.raises(OriginServerError):
        origin.start()


def test_non_loopback_host_is_rejected():
    with pytest.raises(OriginServerError):
        SyntheticOrigin(host="8.8.8.8", port=0)


# ---------------------------------------------------------------------------
# Scenario loading (fail-closed)
# ---------------------------------------------------------------------------


def test_all_fixture_files_load_and_validate():
    names = sorted(p.stem for p in default_fixture_dir().glob("*.json"))
    assert names == [
        "cache_max_age_0",
        "cache_no_cache",
        "healthy",
        "html_404",
        "html_markdown_content_type",
        "html_sentinel_wrong",
        "html_wrong_content_type",
        "markdown_404",
        "markdown_406",
        "markdown_sentinel_missing",
        "markdown_wrong_content_type",
        "no_vary",
        "vary_lowercase",
        "vary_multi",
        "vary_star",
    ]
    for name in names:
        scenario = load_scenario(name)
        assert scenario["scenario_id"] == name
        assert set(scenario["representations"]) == {"html", "markdown"}


def test_unknown_scenario_is_rejected():
    with pytest.raises(ScenarioError):
        load_scenario("does_not_exist")


def test_scenario_with_unknown_field_is_rejected(tmp_path):
    bad = {
        "scenario_id": "bad",
        "representations": {
            "html": {"status": 200, "surprise": True},
            "markdown": {"status": 200},
        },
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ScenarioError):
        load_scenario(path)


def test_no_vary_fixture_serves_bodies_without_vary():
    server = SyntheticOrigin(port=0, scenario="no_vary")
    server.start()
    try:
        _, h_headers, h_body = get(server.port, accept=HTML_ACCEPT)
        _, m_headers, m_body = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert "vary" not in h_headers
    assert "vary" not in m_headers
    assert HTML_SENTINEL in h_body.decode("utf-8")
    assert MARKDOWN_SENTINEL in m_body.decode("utf-8")


def test_set_scenario_does_not_reset_evidence(origin):
    get(origin.port, accept=HTML_ACCEPT)
    assert origin.counter_snapshot().total_requests == 1
    origin.set_scenario("markdown_404")
    assert origin.scenario_id == "markdown_404"
    assert origin.counter_snapshot().total_requests == 1
    assert get(origin.port, accept=MARKDOWN_ACCEPT)[0] == 404
    assert origin.counter_snapshot().total_requests == 2
    assert len(origin.event_log()) == 2


def test_accept_quality_values_pick_highest_q(origin):
    status, _, body = get(
        origin.port, accept="text/html;q=0.1, text/markdown;q=0.9"
    )
    assert status == 200
    assert MARKDOWN_SENTINEL in body.decode("utf-8")


@pytest.mark.parametrize(
    "accept",
    [
        "text/markdown;q=0",
        "text/html;q=0",
        "text/html;q=0, text/markdown;q=0",
    ],
)
def test_accept_q_zero_returns_406_t014(origin, accept):
    """T014 (T003 P2-01): q=0 means "not acceptable" (RFC 9110
    §12.5.1) — a live origin must answer 406, not 200."""
    assert get(origin.port, accept=accept)[0] == 406


def test_accept_q_zero_loses_to_positive_q_t014(origin):
    status, _, body = get(
        origin.port, accept="text/html;q=0, text/markdown;q=0.5"
    )
    assert status == 200
    assert MARKDOWN_SENTINEL in body.decode("utf-8")
    status, _, body = get(
        origin.port, accept="text/html;q=0.5, text/markdown;q=0"
    )
    assert status == 200
    assert HTML_SENTINEL in body.decode("utf-8")


@pytest.mark.parametrize(
    ("accept", "sentinel"),
    [
        ("text/html;q=0.9, text/markdown;q=0.9", HTML_SENTINEL),
        ("text/markdown;q=0.9, text/html;q=0.9", MARKDOWN_SENTINEL),
        ("text/html;q=0.5, text/markdown;q=0.5", HTML_SENTINEL),
        ("text/markdown;q=0.5, text/html;q=0.5", MARKDOWN_SENTINEL),
    ],
)
def test_accept_q_tie_goes_to_first_listed_t014(origin, accept, sentinel):
    """T014 (T003 P2-02): a q-value tie goes to the first listed
    media type (documented _parse_accept rule, previously untested)."""
    status, _, body = get(origin.port, accept=accept)
    assert status == 200
    assert sentinel in body.decode("utf-8")


# ---------------------------------------------------------------------------
# T008 extended-Golden origin shapes (PROJECT_BOOK §11.3 E01–E03, E07–E11)
# ---------------------------------------------------------------------------


def test_vary_multi_fixture_serves_two_field_vary():
    server = SyntheticOrigin(port=0, scenario="vary_multi")
    server.start()
    try:
        _, h_headers, _ = get(server.port, accept=HTML_ACCEPT)
        _, m_headers, _ = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_headers["vary"] == "Accept, Accept-Encoding"
    assert m_headers["vary"] == "Accept, Accept-Encoding"


def test_vary_star_fixture_serves_vary_star():
    server = SyntheticOrigin(port=0, scenario="vary_star")
    server.start()
    try:
        _, h_headers, _ = get(server.port, accept=HTML_ACCEPT)
        _, m_headers, _ = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_headers["vary"] == "*"
    assert m_headers["vary"] == "*"


def test_vary_lowercase_field_name_on_the_wire():
    # E01: the Vary field NAME is lowercase on the wire. The `get`
    # helper lowercases header names, so this test reads the raw
    # header list, where http.client preserves the case as sent.
    server = SyntheticOrigin(port=0, scenario="vary_lowercase")
    server.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        try:
            conn.request("GET", "/doc", headers={"Accept": HTML_ACCEPT})
            resp = conn.getresponse()
            resp.read()
            names = [name for name, _ in resp.getheaders()]
        finally:
            conn.close()
    finally:
        server.stop()
    assert "vary" in names
    assert "Vary" not in names


def test_cache_control_fixtures_emit_directives():
    for scenario, directive in (
        ("cache_max_age_0", "max-age=0"),
        ("cache_no_cache", "no-cache"),
    ):
        server = SyntheticOrigin(port=0, scenario=scenario)
        server.start()
        try:
            _, h_headers, _ = get(server.port, accept=HTML_ACCEPT)
            _, m_headers, _ = get(server.port, accept=MARKDOWN_ACCEPT)
        finally:
            server.stop()
        assert h_headers["cache-control"] == directive
        assert m_headers["cache-control"] == directive


def test_markdown_406_fixture():
    server = SyntheticOrigin(port=0, scenario="markdown_406")
    server.start()
    try:
        h_status, _, _ = get(server.port, accept=HTML_ACCEPT)
        m_status, m_headers, m_body = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_status == 200
    assert m_status == 406
    assert m_headers["content-type"] == "text/plain; charset=utf-8"
    assert MARKDOWN_SENTINEL in m_body.decode("utf-8")


def test_html_markdown_content_type_fixture():
    server = SyntheticOrigin(port=0, scenario="html_markdown_content_type")
    server.start()
    try:
        h_status, h_headers, h_body = get(server.port, accept=HTML_ACCEPT)
        m_status, _, _ = get(server.port, accept=MARKDOWN_ACCEPT)
    finally:
        server.stop()
    assert h_status == 200
    assert h_headers["content-type"] == "text/markdown; charset=utf-8"
    assert HTML_SENTINEL in h_body.decode("utf-8")
    assert m_status == 200


def test_scenario_with_unknown_vary_value_is_rejected(tmp_path):
    bad = {
        "scenario_id": "bad-vary",
        "representations": {
            "html": {"status": 200, "vary": "Accept-Language"},
            "markdown": {"status": 200},
        },
    }
    path = tmp_path / "bad-vary.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ScenarioError):
        load_scenario(path)
