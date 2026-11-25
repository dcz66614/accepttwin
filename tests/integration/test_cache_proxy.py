"""Integration tests for the controlled cache proxy (P032 T004).

Acceptance criteria (IMPLEMENTATION_PLAN T004):

1. MISS: header MISS + origin counter +1.
2. HIT: header HIT + origin counter 0.
3. BYPASS: header BYPASS + origin counter +1.
4. reset leaves entry_count == 0.
5. force_uri_only genuinely reproduces a representation bleed.
6. respect_vary separates representations when Vary: Accept exists.
7. manual_accept_key separates representations without Vary.
8. no-store responses are never stored.
9. Conflicting / incomplete evidence yields CACHE_STATE_UNKNOWN.

Every test makes real HTTP requests over localhost (``http.client``,
no proxy environment variables). The origin and the proxy bind
OS-assigned loopback ports (``port=0``) except for the one test that
pins the frozen default ports 18765/18766 from ``contracts/site.json``.
Dual evidence is verified end to end with
:func:`accepttwin.cache_evidence.verify_cache_state`, fed by the
response headers on the wire and by counter deltas measured from
:class:`accepttwin.origin_server.SyntheticOrigin` — never by a preset
answer.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from accepttwin.cache_evidence import (
    CACHE_STATE_UNKNOWN,
    BehaviorEvidence,
    HeaderEvidence,
    verify_cache_state,
)
from accepttwin.cache_proxy import (
    CacheProxyError,
    ControlledCacheProxy,
)
from accepttwin.contract import load_contract, parse_contract
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
# HTTP helpers (real localhost requests)
# ---------------------------------------------------------------------------


def get(port: int, path: str = "/doc", accept: str = HTML_ACCEPT):
    """One real GET over loopback; returns (status, headers, body)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path, headers={"Accept": accept})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    finally:
        conn.close()


def request_with_method(port: int, method: str, path: str = "/doc"):
    """One real non-GET request; returns (status, headers, body)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, headers={"Accept": HTML_ACCEPT})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    finally:
        conn.close()


def post_reset(port: int, namespace: str = "test"):
    """POST the proxy control endpoint; returns the parsed JSON body."""
    payload = json.dumps({"namespace": namespace}).encode("utf-8")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(
            "POST",
            "/__accepttwin/reset",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, json.loads(body.decode("utf-8"))
    finally:
        conn.close()


def get_snapshot(port: int):
    """GET the proxy control endpoint; returns the parsed JSON body."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/__accepttwin/snapshot")
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, json.loads(body.decode("utf-8"))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fixtures: origin + proxy pairs
# ---------------------------------------------------------------------------


class Pair:
    """A running (origin, proxy) pair; use as a context manager."""

    def __init__(self, mode, scenario="healthy", contract=None):
        self.origin = SyntheticOrigin(port=0, scenario=scenario)
        self.origin.start()
        kwargs: dict = {"port": 0, "mode": mode}
        if contract is not None:
            kwargs["contract"] = contract
        else:
            kwargs["origin_url"] = self.origin.url
        self.proxy = ControlledCacheProxy(**kwargs)
        self.proxy.start()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.proxy.stop()
        self.origin.stop()
        return False


def no_store_contract(origin_url: str):
    """A valid no_store contract pointing at *origin_url* (§5.2 ex. B)."""
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["origin_url"] = origin_url
    data["cache_behavior"] = {
        "mode": "no_store",
        "vary_accept": "not_required",
        "max_age_seconds": None,
    }
    return parse_contract(data)


def observe(pair: Pair, accept: str):
    """One proxied request with before/after evidence measured live.

    Returns a dict with the response and the measured deltas; nothing
    here is preset — the counter and event log are read from the live
    origin, the snapshot from the live proxy.
    """
    before_counter = pair.origin.counter_snapshot().total_requests
    before_events = pair.origin.event_log()
    before_ids = {
        e.entry_id for e in pair.proxy.cache_snapshot().entries
    }
    before_count = pair.proxy.cache_snapshot().entry_count
    status, headers, body = get(pair.proxy.port, accept=accept)
    after_counter = pair.origin.counter_snapshot().total_requests
    after_snapshot = pair.proxy.cache_snapshot()
    after_events = pair.origin.event_log()
    new_events = after_events[len(before_events):]
    return {
        "status": status,
        "headers": headers,
        "body": body,
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "counter_delta": after_counter - before_counter,
        "entry_count_delta": after_snapshot.entry_count - before_count,
        "entry_ids_before": before_ids,
        "entry_ids_after": {e.entry_id for e in after_snapshot.entries},
        "snapshot_after": after_snapshot,
        "new_events": new_events,
        "origin_event_present": any(
            ev.accept == accept and ev.status == status for ev in new_events
        ),
    }


def verify_observation(obs, expected: str | None = None):
    """Run the dual-evidence verifier on a live observation."""
    headers = obs["headers"]
    header = HeaderEvidence(
        status=headers.get("x-accepttwin-cache-status"),
        cache_key_sha256=headers.get("x-accepttwin-cache-key"),
        entry_id=headers.get("x-accepttwin-entry-id"),
    )
    entry_id = header.entry_id
    stored = None
    if entry_id is not None:
        for entry in obs["snapshot_after"].entries:
            if entry.entry_id == entry_id:
                stored = entry
                break
    behavior = BehaviorEvidence(
        origin_counter_delta=obs["counter_delta"],
        origin_event_present=obs["origin_event_present"],
        entry_created=(
            entry_id is not None
            and entry_id not in obs["entry_ids_before"]
            and entry_id in obs["entry_ids_after"]
        ),
        entry_id_matches=stored is not None,
        body_hash_matches=(
            stored is not None and stored.body_sha256 == obs["body_sha256"]
        ),
        entry_count_delta=obs["entry_count_delta"],
    )
    return verify_cache_state(header, behavior, expected=expected)


# ---------------------------------------------------------------------------
# MISS / HIT / BYPASS dual evidence (§5.3 A–C)
# ---------------------------------------------------------------------------


def test_miss_dual_evidence():
    with Pair("respect_vary") as pair:
        evidence = pair.proxy.reset_cache("test-miss")
        assert evidence.success and evidence.entries_after == 0
        obs = observe(pair, HTML_ACCEPT)
        assert obs["status"] == 200
        assert obs["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert len(obs["headers"]["x-accepttwin-cache-key"]) == 64
        assert obs["headers"]["x-accepttwin-entry-id"].startswith("entry-")
        assert HTML_SENTINEL.encode() in obs["body"]
        assert obs["counter_delta"] == 1
        assert obs["origin_event_present"] is True
        assert obs["entry_count_delta"] == 1
        assert verify_observation(obs, expected="MISS").state == "MISS"


def test_hit_dual_evidence():
    with Pair("respect_vary") as pair:
        pair.proxy.reset_cache("test-hit")
        first = observe(pair, HTML_ACCEPT)
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        second = observe(pair, HTML_ACCEPT)
        assert second["status"] == 200
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["headers"]["x-accepttwin-cache-key"] == (
            first["headers"]["x-accepttwin-cache-key"]
        )
        assert second["headers"]["x-accepttwin-entry-id"] == (
            first["headers"]["x-accepttwin-entry-id"]
        )
        assert second["body"] == first["body"]
        assert second["counter_delta"] == 0
        assert second["entry_count_delta"] == 0
        assert verify_observation(second, expected="HIT").state == "HIT"


def test_bypass_dual_evidence_disabled_mode():
    with Pair("disabled") as pair:
        pair.proxy.reset_cache("test-bypass")
        for _ in range(2):
            obs = observe(pair, HTML_ACCEPT)
            assert obs["status"] == 200
            assert obs["headers"]["x-accepttwin-cache-status"] == "BYPASS"
            assert "x-accepttwin-entry-id" not in obs["headers"]
            assert HTML_SENTINEL.encode() in obs["body"]
            assert obs["counter_delta"] == 1
            assert obs["origin_event_present"] is True
            assert obs["entry_count_delta"] == 0
            assert pair.proxy.cache_snapshot().entry_count == 0
            assert verify_observation(obs, expected="BYPASS").state == "BYPASS"


def test_no_store_contract_bypass_both_representations():
    with Pair("respect_vary") as pair:
        contract = no_store_contract(pair.origin.url)
        pair.proxy.stop()
        pair.proxy = ControlledCacheProxy(
            port=0, mode="respect_vary", contract=contract
        )
        pair.proxy.start()
        pair.proxy.reset_cache("test-no-store-contract")
        for accept, sentinel in (
            (HTML_ACCEPT, HTML_SENTINEL),
            (MARKDOWN_ACCEPT, MARKDOWN_SENTINEL),
        ):
            obs = observe(pair, accept)
            assert obs["headers"]["x-accepttwin-cache-status"] == "BYPASS"
            assert sentinel.encode() in obs["body"]
            assert obs["counter_delta"] == 1
            assert verify_observation(obs, expected="BYPASS").state == "BYPASS"
        assert pair.proxy.cache_snapshot().entry_count == 0


# ---------------------------------------------------------------------------
# Reset (§5.4)
# ---------------------------------------------------------------------------


def test_reset_leaves_entry_count_zero_in_process_and_over_http():
    with Pair("respect_vary") as pair:
        observe(pair, HTML_ACCEPT)
        observe(pair, MARKDOWN_ACCEPT)
        assert pair.proxy.cache_snapshot().entry_count == 2
        evidence = pair.proxy.reset_cache("experiment-1")
        assert evidence.success is True
        assert evidence.entries_before == 2
        assert evidence.entries_after == 0
        assert evidence.entries_removed == 2
        assert pair.proxy.cache_snapshot().entry_count == 0
        # Reset again over real HTTP; the control endpoint must confirm
        # the same empty state.
        observe(pair, HTML_ACCEPT)
        assert pair.proxy.cache_snapshot().entry_count == 1
        status, payload = post_reset(pair.proxy.port, "experiment-2")
        assert status == 200
        assert payload["success"] is True
        assert payload["entries_after"] == 0
        status, payload = get_snapshot(pair.proxy.port)
        assert status == 200
        assert payload["entry_count"] == 0


def test_reset_on_empty_store_succeeds():
    with Pair("respect_vary") as pair:
        evidence = pair.proxy.reset_cache("cold")
        assert evidence.success is True
        assert evidence.entries_before == 0
        assert evidence.entries_removed == 0


def test_reset_requires_non_empty_namespace():
    with Pair("respect_vary") as pair:
        with pytest.raises(CacheProxyError):
            pair.proxy.reset_cache("")


# ---------------------------------------------------------------------------
# Bleed reproduction (§11.2 C11–C16) and healthy separation (C01–C04)
# ---------------------------------------------------------------------------


def test_force_uri_only_reproduces_bleed_html_first():
    with Pair("force_uri_only") as pair:
        pair.proxy.reset_cache("test-bleed-hm")
        first = observe(pair, HTML_ACCEPT)
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert HTML_SENTINEL.encode() in first["body"]
        second = observe(pair, MARKDOWN_ACCEPT)
        # The Markdown request reuses the HTML entry: same key, HIT,
        # origin untouched, HTML body served for a Markdown request.
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["headers"]["x-accepttwin-cache-key"] == (
            first["headers"]["x-accepttwin-cache-key"]
        )
        assert second["counter_delta"] == 0
        assert HTML_SENTINEL.encode() in second["body"]
        assert MARKDOWN_SENTINEL.encode() not in second["body"]
        assert verify_observation(second, expected="HIT").state == "HIT"


def test_force_uri_only_reproduces_bleed_markdown_first():
    with Pair("force_uri_only") as pair:
        pair.proxy.reset_cache("test-bleed-mh")
        first = observe(pair, MARKDOWN_ACCEPT)
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        second = observe(pair, HTML_ACCEPT)
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["counter_delta"] == 0
        assert MARKDOWN_SENTINEL.encode() in second["body"]
        assert HTML_SENTINEL.encode() not in second["body"]
        assert verify_observation(second, expected="HIT").state == "HIT"


def test_respect_vary_separates_with_vary_accept():
    with Pair("respect_vary", scenario="healthy") as pair:
        pair.proxy.reset_cache("test-vary")
        html = observe(pair, HTML_ACCEPT)
        markdown = observe(pair, MARKDOWN_ACCEPT)
        assert html["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert markdown["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert html["counter_delta"] == 1
        assert markdown["counter_delta"] == 1
        assert HTML_SENTINEL.encode() in html["body"]
        assert MARKDOWN_SENTINEL.encode() in markdown["body"]
        assert html["headers"]["x-accepttwin-cache-key"] != (
            markdown["headers"]["x-accepttwin-cache-key"]
        )
        assert html["headers"]["x-accepttwin-entry-id"] != (
            markdown["headers"]["x-accepttwin-entry-id"]
        )
        assert pair.proxy.cache_snapshot().entry_count == 2
        assert verify_observation(html, expected="MISS").state == "MISS"
        assert verify_observation(markdown, expected="MISS").state == "MISS"


def test_respect_vary_without_vary_bleeds():
    # §11.2 C13: no Vary + respect_vary keys on the URI only, so the
    # second representation HITs the first entry.
    with Pair("respect_vary", scenario="no_vary") as pair:
        pair.proxy.reset_cache("test-no-vary")
        first = observe(pair, HTML_ACCEPT)
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        second = observe(pair, MARKDOWN_ACCEPT)
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["counter_delta"] == 0
        assert HTML_SENTINEL.encode() in second["body"]
        assert verify_observation(second, expected="HIT").state == "HIT"


def test_manual_accept_key_separates_without_vary():
    # §11.2 C03/C04: missing Vary alone is not a fault when the cache
    # still separates by Accept.
    with Pair("manual_accept_key", scenario="no_vary") as pair:
        pair.proxy.reset_cache("test-manual")
        html = observe(pair, HTML_ACCEPT)
        markdown = observe(pair, MARKDOWN_ACCEPT)
        assert html["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert markdown["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert HTML_SENTINEL.encode() in html["body"]
        assert MARKDOWN_SENTINEL.encode() in markdown["body"]
        assert pair.proxy.cache_snapshot().entry_count == 2
        assert verify_observation(html, expected="MISS").state == "MISS"
        assert verify_observation(markdown, expected="MISS").state == "MISS"


# ---------------------------------------------------------------------------
# no-store from the origin, ignore_no_store, opaque (§5.2, §10.3, §11.2)
# ---------------------------------------------------------------------------


class _StubOriginHandler(BaseHTTPRequestHandler):
    """Test-only origin that can emit Cache-Control / Vary the synthetic
    origin cannot (no-store, Vary: *). Records request headers so the
    test can prove the proxy forwards only the fixed header set."""

    protocol_version = "HTTP/1.1"
    server_version = "StubOrigin/1.0.0"

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        server = self.server  # type: ignore[attr-defined]
        server.requests.append(dict(self.headers.items()))
        accept = self.headers.get("Accept", "")
        if "text/markdown" in accept:
            body = f"# stub\n\n{MARKDOWN_SENTINEL}\n".encode()
            content_type = "text/markdown; charset=utf-8"
        else:
            body = f"<html><body>{HTML_SENTINEL}</body></html>\n".encode()
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if server.vary is not None:
            self.send_header("Vary", server.vary)
        if server.cache_control is not None:
            self.send_header("Cache-Control", server.cache_control)
        self.end_headers()
        self.wfile.write(body)


class _StubOrigin:
    """Minimal counting origin for header-level fault injection."""

    def __init__(self, *, vary="Accept", cache_control=None):
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _StubOriginHandler)
        self._server.daemon_threads = True
        self._server.vary = vary  # type: ignore[attr-defined]
        self._server.cache_control = cache_control  # type: ignore[attr-defined]
        self._server.requests = []  # type: ignore[attr-defined]
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.05},
            daemon=True,
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/doc"

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def request_count(self) -> int:
        return len(self._server.requests)  # type: ignore[attr-defined]

    @property
    def seen_headers(self) -> list[dict]:
        return list(self._server.requests)  # type: ignore[attr-defined]

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)
        return False


def test_origin_no_store_response_is_never_stored():
    with _StubOrigin(cache_control="no-store") as stub:
        proxy = ControlledCacheProxy(
            origin_url=stub.url, port=0, mode="respect_vary"
        )
        proxy.start()
        try:
            proxy.reset_cache("test-origin-no-store")
            for _ in range(2):
                before = stub.request_count
                status, headers, body = get(proxy.port, accept=HTML_ACCEPT)
                assert status == 200
                assert headers["x-accepttwin-cache-status"] == "BYPASS"
                assert stub.request_count == before + 1
            assert proxy.cache_snapshot().entry_count == 0
        finally:
            proxy.stop()


def test_ignore_no_store_stores_despite_contract():
    with Pair("respect_vary") as pair:
        contract = no_store_contract(pair.origin.url)
        pair.proxy.stop()
        pair.proxy = ControlledCacheProxy(
            port=0, mode="ignore_no_store", contract=contract
        )
        pair.proxy.start()
        pair.proxy.reset_cache("test-ignore-no-store")
        first = observe(pair, HTML_ACCEPT)
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        second = observe(pair, HTML_ACCEPT)
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["counter_delta"] == 0
        assert pair.proxy.cache_snapshot().entry_count == 1


def test_vary_star_is_never_reused():
    # §11.3 E03 groundwork: Vary: * entries must not be reused.
    # A Vary: * response is fetched but never stored, so it is
    # reported BYPASS, not MISS (P2-1): MISS requires an entry to be
    # created (§5.3 A), while the observed behaviour leg (origin +1,
    # entry count unchanged) is exactly the BYPASS leg (§5.3 C).
    with _StubOrigin(vary="*") as stub:
        proxy = ControlledCacheProxy(
            origin_url=stub.url, port=0, mode="respect_vary"
        )
        proxy.start()
        try:
            proxy.reset_cache("test-vary-star")
            for _ in range(2):
                before_count = stub.request_count
                before_entries = proxy.cache_snapshot().entry_count
                status, headers, _body = get(proxy.port, accept=HTML_ACCEPT)
                assert status == 200
                assert headers["x-accepttwin-cache-status"] == "BYPASS"
                assert "x-accepttwin-entry-id" not in headers
                # The stub origin recorded the request: the origin was
                # reached and nothing was reused.
                origin_hit = stub.request_count == before_count + 1
                assert origin_hit
                assert proxy.cache_snapshot().entry_count == 0
                result = verify_cache_state(
                    HeaderEvidence(
                        status=headers.get("x-accepttwin-cache-status"),
                        cache_key_sha256=headers.get(
                            "x-accepttwin-cache-key"
                        ),
                        entry_id=headers.get("x-accepttwin-entry-id"),
                    ),
                    BehaviorEvidence(
                        origin_counter_delta=(
                            stub.request_count - before_count
                        ),
                        origin_event_present=origin_hit,
                        entry_count_delta=(
                            proxy.cache_snapshot().entry_count
                            - before_entries
                        ),
                    ),
                    expected="BYPASS",
                )
                assert result.state == "BYPASS"
            assert proxy.cache_snapshot().entry_count == 0
        finally:
            proxy.stop()


def test_ignore_no_store_stores_origin_no_store_response():
    # P2-2: ignore_no_store + origin Cache-Control: no-store — the
    # origin response is stored despite no-store, so the first
    # request is a MISS, the second identical request is a HIT, the
    # origin is hit only once, and exactly one entry exists.
    with _StubOrigin(cache_control="no-store") as stub:
        proxy = ControlledCacheProxy(
            origin_url=stub.url, port=0, mode="ignore_no_store"
        )
        proxy.start()
        try:
            proxy.reset_cache("test-ignore-no-store-origin")
            before = stub.request_count
            status, headers, _body = get(proxy.port, accept=HTML_ACCEPT)
            assert status == 200
            assert headers["x-accepttwin-cache-status"] == "MISS"
            assert stub.request_count == before + 1
            before = stub.request_count
            status, headers, _body = get(proxy.port, accept=HTML_ACCEPT)
            assert status == 200
            assert headers["x-accepttwin-cache-status"] == "HIT"
            assert stub.request_count == before
            assert proxy.cache_snapshot().entry_count == 1
        finally:
            proxy.stop()


def test_opaque_hides_header_leg_so_state_is_unknown():
    # §11.2 C20: the proxy still caches (second identical request
    # does not reach the origin) but hides the header leg, so the
    # dual-evidence verifier must answer UNKNOWN, not guess HIT.
    with Pair("opaque") as pair:
        pair.proxy.reset_cache("test-opaque")
        first = observe(pair, HTML_ACCEPT)
        assert "x-accepttwin-cache-status" not in first["headers"]
        assert "x-accepttwin-cache-key" not in first["headers"]
        assert "x-accepttwin-entry-id" not in first["headers"]
        assert first["counter_delta"] == 1
        result = verify_observation(first)
        assert result.state == CACHE_STATE_UNKNOWN
        assert any("cache-status" in r for r in result.reasons)
        second = observe(pair, HTML_ACCEPT)
        assert "x-accepttwin-cache-status" not in second["headers"]
        assert second["counter_delta"] == 0  # stored, despite hidden headers
        assert second["body"] == first["body"]
        assert verify_observation(second).state == CACHE_STATE_UNKNOWN


def test_proxy_forwards_only_the_fixed_header_set():
    with _StubOrigin() as stub:
        proxy = ControlledCacheProxy(
            origin_url=stub.url, port=0, mode="respect_vary"
        )
        proxy.start()
        try:
            get(proxy.port, accept=HTML_ACCEPT)
            assert len(stub.seen_headers) == 1
            seen = {k.lower(): v for k, v in stub.seen_headers[0].items()}
            assert seen["accept"] == HTML_ACCEPT
            assert seen["accept-encoding"] == "identity"
            assert seen["user-agent"] == "AcceptTwin/1.0.0"
            assert seen["accept-language"] == "en"
            assert "cookie" not in seen
            assert "authorization" not in seen
        finally:
            proxy.stop()


# ---------------------------------------------------------------------------
# Failure paths still produce complete dual evidence (T001 §7 lesson)
# ---------------------------------------------------------------------------


def test_origin_error_response_still_carries_miss_evidence():
    # C07: the origin answers 404 for HTML. The proxy forwards the
    # error *and* its MISS headers, so the failure path yields complete
    # dual evidence instead of short-circuiting like Hurl (T001 §4).
    with Pair("respect_vary", scenario="html_404") as pair:
        pair.proxy.reset_cache("test-origin-error")
        first = observe(pair, HTML_ACCEPT)
        assert first["status"] == 404
        assert first["headers"]["x-accepttwin-cache-status"] == "MISS"
        assert first["headers"]["x-accepttwin-entry-id"].startswith("entry-")
        assert first["counter_delta"] == 1
        assert verify_observation(first, expected="MISS").state == "MISS"
        second = observe(pair, HTML_ACCEPT)
        assert second["status"] == 404
        assert second["headers"]["x-accepttwin-cache-status"] == "HIT"
        assert second["counter_delta"] == 0
        assert verify_observation(second, expected="HIT").state == "HIT"


# ---------------------------------------------------------------------------
# Determinism, snapshots, methods, configuration
# ---------------------------------------------------------------------------


def test_cache_key_and_entry_id_are_deterministic_across_reset():
    with Pair("respect_vary") as pair:
        pair.proxy.reset_cache("test-determinism")
        first = observe(pair, HTML_ACCEPT)
        key1 = first["headers"]["x-accepttwin-cache-key"]
        entry1 = first["headers"]["x-accepttwin-entry-id"]
        pair.proxy.reset_cache("test-determinism-2")
        second = observe(pair, HTML_ACCEPT)
        assert second["headers"]["x-accepttwin-cache-key"] == key1
        assert second["headers"]["x-accepttwin-entry-id"] == entry1


def test_snapshot_contains_hashes_not_bodies():
    with Pair("respect_vary") as pair:
        pair.proxy.reset_cache("test-snapshot")
        observe(pair, HTML_ACCEPT)
        status, payload = get_snapshot(pair.proxy.port)
        assert status == 200
        assert payload["entry_count"] == 1
        entry = payload["entries"][0]
        assert "body" not in entry
        assert HTML_SENTINEL not in json.dumps(payload)
        _s, _h, body = get(pair.proxy.port, accept=HTML_ACCEPT)
        assert entry["body_sha256"] == hashlib.sha256(body).hexdigest()


def test_non_get_is_rejected_without_origin_contact_or_cache_headers():
    with Pair("respect_vary") as pair:
        before = pair.origin.counter_snapshot().total_requests
        status, headers, _body = request_with_method(pair.proxy.port, "POST")
        assert status == 405
        assert "x-accepttwin-cache-status" not in headers
        assert pair.origin.counter_snapshot().total_requests == before


def test_control_endpoints_do_not_touch_origin_counter():
    with Pair("respect_vary") as pair:
        before = pair.origin.counter_snapshot().total_requests
        status, _payload = get_snapshot(pair.proxy.port)
        assert status == 200
        status, payload = post_reset(pair.proxy.port, "control-check")
        assert status == 200
        assert payload["success"] is True
        assert pair.origin.counter_snapshot().total_requests == before


def test_default_ports_from_site_contract():
    contract = load_contract(CONTRACT_PATH)
    origin = SyntheticOrigin(port=18766, scenario="healthy")
    origin.start()
    proxy = ControlledCacheProxy(port=18765, mode="respect_vary", contract=contract)
    proxy.start()
    try:
        assert proxy.url == "http://127.0.0.1:18765/doc"
        proxy.reset_cache("test-default-ports")
        status, headers, body = get(18765, accept=HTML_ACCEPT)
        assert status == 200
        assert headers["x-accepttwin-cache-status"] == "MISS"
        assert HTML_SENTINEL.encode() in body
    finally:
        proxy.stop()
        origin.stop()


def test_unknown_mode_rejected():
    with pytest.raises(CacheProxyError):
        ControlledCacheProxy(origin_url="http://127.0.0.1:18766/doc", mode="cdn")


def test_non_loopback_origin_rejected():
    with pytest.raises(CacheProxyError):
        ControlledCacheProxy(origin_url="http://93.184.216.34/doc")


def test_non_loopback_proxy_host_rejected():
    with pytest.raises(CacheProxyError):
        ControlledCacheProxy(
            origin_url="http://127.0.0.1:18766/doc", host="0.0.0.0"
        )


def test_explicit_origin_url_disagreeing_with_contract_rejected():
    contract = load_contract(CONTRACT_PATH)
    with pytest.raises(CacheProxyError):
        ControlledCacheProxy(
            origin_url="http://127.0.0.1:19999/doc", contract=contract
        )
