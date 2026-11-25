"""Privacy regression: redirects and environment proxies (P032 T011).

Acceptance scenario 4 — redirects are not followed (§0.2 item 6,
§17.4 item 4) — plus the §17.4 item 5 boundary the T005 runner
already implements (environment proxies are never read): both are
verified here against real loopback HTTP servers, with the
environment deliberately poisoned with a dead proxy.

No test contacts a public address: the redirect *target* is a second
loopback server whose hit counter proves it was never contacted, and
the public-URL redirect case asserts the client returns the 301
itself after exactly one request to the local server.
"""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from accepttwin.experiment_runner import _http_get


class _CountingHandler(BaseHTTPRequestHandler):
    """Serves one fixed response; counts every request received."""

    protocol_version = "HTTP/1.1"
    response_status = 200
    response_body = b"ok"
    location = None  # when set: send this Location with a 301
    hits = 0

    def log_message(self, *args):  # silence stderr logging
        return

    def do_GET(self):
        type(self).hits += 1
        body = type(self).response_body
        if type(self).location is not None:
            self.send_response(301)
            self.send_header("Location", type(self).location)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(type(self).response_status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve(handler_cls):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


@pytest.fixture
def reset_handler():
    _CountingHandler.hits = 0
    _CountingHandler.location = None
    _CountingHandler.response_status = 200
    _CountingHandler.response_body = b"ok"
    yield _CountingHandler
    _CountingHandler.hits = 0
    _CountingHandler.location = None


# ---------------------------------------------------------------------------
# Scenario 4 — redirects are not followed
# ---------------------------------------------------------------------------


def test_redirect_to_loopback_target_is_not_followed(reset_handler):
    """A 301 to another loopback URL is returned as-is; target: 0 hits."""
    target = _serve(reset_handler)
    try:
        target_port = target.server_address[1]
        redirector_cls = type(
            "Redirector",
            (_CountingHandler,),
            {"location": f"http://127.0.0.1:{target_port}/target", "hits": 0},
        )
        redirector = _serve(redirector_cls)
        try:
            redirector_port = redirector.server_address[1]
            result = _http_get(
                f"http://127.0.0.1:{redirector_port}/old",
                "html",
                timeout=5.0,
            )
            status, headers, body = result.status, result.headers, result.body
            assert status == 301
            assert headers.get("location") == (
                f"http://127.0.0.1:{target_port}/target"
            )
            assert body == b""
        finally:
            redirector.shutdown()
            redirector.server_close()
    finally:
        target.shutdown()
        target.server_close()
    # The redirector was hit exactly once; the target was never hit —
    # the 301 was observed, not followed.
    assert redirector_cls.hits == 1
    assert _CountingHandler.hits == 0


def test_redirect_to_public_url_is_not_followed(reset_handler):
    """A 301 to a public URL is returned as-is; nothing is fetched."""
    redirector_cls = type(
        "Redirector",
        (_CountingHandler,),
        {"location": "http://93.184.216.34/elsewhere", "hits": 0},
    )
    redirector = _serve(redirector_cls)
    try:
        port = redirector.server_address[1]
        result = _http_get(
            f"http://127.0.0.1:{port}/old", "html", timeout=5.0
        )
        status, headers, body = result.status, result.headers, result.body
        assert status == 301
        assert headers.get("location") == "http://93.184.216.34/elsewhere"
        assert body == b""
        # Exactly one request reached the local server: the client made
        # no second connection anywhere.
        assert redirector_cls.hits == 1
    finally:
        redirector.shutdown()
        redirector.server_close()


def test_direct_200_still_works(reset_handler):
    """Positive case: a plain 200 response is observed normally."""
    server = _serve(reset_handler)
    try:
        port = server.server_address[1]
        result = _http_get(
            f"http://127.0.0.1:{port}/doc", "html", timeout=5.0
        )
        status, headers, body = result.status, result.headers, result.body
        assert status == 200
        assert body == b"ok"
        assert reset_handler.hits == 1
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# §17.4 item 5 — environment proxies are never read
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "var",
    ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"],
)
def test_dead_environment_proxy_is_ignored(reset_handler, monkeypatch, var):
    """With a dead proxy in the environment, local GETs still succeed.

    The client opens a TCP connection to the URL's own host/port and
    never consults proxy variables (T005); if it did, every request
    would fail against the dead 127.0.0.1:1 proxy.
    """
    monkeypatch.setenv(var, "http://127.0.0.1:1")
    server = _serve(reset_handler)
    try:
        port = server.server_address[1]
        result = _http_get(
            f"http://127.0.0.1:{port}/doc", "markdown", timeout=5.0
        )
        status, body = result.status, result.body
        assert status == 200
        assert body == b"ok"
    finally:
        server.shutdown()
        server.server_close()


def test_all_environment_proxies_poisoned_at_once(reset_handler, monkeypatch):
    """Positive control for the parametrised case: all vars poisoned."""
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                "ALL_PROXY", "NO_PROXY"):
        monkeypatch.setenv(var, "http://127.0.0.1:1")
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:1"
    server = _serve(reset_handler)
    try:
        port = server.server_address[1]
        result = _http_get(
            f"http://127.0.0.1:{port}/doc", "html", timeout=5.0
        )
        status, body = result.status, result.body
        assert (status, body) == (200, b"ok")
    finally:
        server.shutdown()
        server.server_close()
