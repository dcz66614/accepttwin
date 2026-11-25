"""Privacy regression: 1 MiB body cap (P032 T011, scenario 8).

Acceptance scenario 8 — oversize body rejected (PROJECT_BOOK §17.4
item 8; ``limits.max_body_bytes`` defaults to 1 MiB).

Verified at three levels:

1. unit: :func:`accepttwin.privacy.check_body_size` /
   :func:`accepttwin.privacy.enforce_body_limit` enforce the cap on
   measured sizes and raw bytes, with exact boundary behaviour;
2. classifier: a fabricated oversize observation is rejected by the
   production classifier with ``INCONCLUSIVE_LIMIT`` (the same path
   the E21 Golden exercises live);
3. live: the E21-style oversize run is re-run here through the real
   runner and the privacy angle is asserted — the oversize body is
   measured (``body_size`` recorded, hash recorded) but never stored
   as text anywhere in the run's evidence.

Deliberate boundary (recorded, not hidden): the cap is enforced on
the *measured* body at classification time, and since T014 the
socket read itself is bounded too — ``_http_get`` /
``_fetch_origin`` retain at most ``limit + 1`` bytes via
:func:`accepttwin.privacy.read_http_body_bounded`, while the exact
total size, whole-stream SHA-256 and Sentinel presence are still
measured over the full stream (see F-01 in
evidence/Privacy/PRIVACY_REPORT.md, closed by T014).
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from accepttwin.classifier import classify_run
from accepttwin.contract import parse_contract
from accepttwin.evidence import RequestObservation
from accepttwin.privacy import (
    MAX_BODY_BYTES,
    PrivacyError,
    check_body_size,
    enforce_body_limit,
    read_http_body_bounded,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"


# ---------------------------------------------------------------------------
# Level 1 — unit: the cap itself, including exact boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "size",
    [0, 1, 1024, MAX_BODY_BYTES - 1, MAX_BODY_BYTES],
)
def test_body_size_at_or_below_cap_accepted(size):
    assert check_body_size(size) == size
    assert enforce_body_limit(b"x" * size) == b"x" * size


@pytest.mark.parametrize(
    "size",
    [MAX_BODY_BYTES + 1, MAX_BODY_BYTES + 1024, 2 * MAX_BODY_BYTES],
)
def test_body_size_above_cap_rejected(size):
    with pytest.raises(PrivacyError, match="exceeds the 1048576 byte limit"):
        check_body_size(size)
    with pytest.raises(PrivacyError, match="exceeds the 1048576 byte limit"):
        enforce_body_limit(b"x" * size)


def test_negative_body_size_rejected():
    with pytest.raises(PrivacyError, match="must not be negative"):
        check_body_size(-1)


def test_non_integer_body_size_rejected():
    with pytest.raises(PrivacyError, match="must be an integer"):
        check_body_size(1.5)
        check_body_size("1048576")


def test_custom_limit_is_honoured():
    assert check_body_size(100, limit=100) == 100
    with pytest.raises(PrivacyError):
        check_body_size(101, limit=100)


def test_enforce_body_limit_rejects_non_bytes():
    with pytest.raises(PrivacyError, match="must be bytes"):
        enforce_body_limit("not bytes")


def test_cap_constant_is_1_mib():
    assert MAX_BODY_BYTES == 1_048_576


# ---------------------------------------------------------------------------
# Level 1b — bounded read: exact measurement, bounded retention (T014)
# ---------------------------------------------------------------------------


def test_bounded_read_returns_small_body_whole_with_exact_hash():
    body = b"<html>AT_HTML_SENTINEL_001</html>"
    retained, total, digest, match = read_http_body_bounded(
        io.BytesIO(body), 1024, sentinel=b"AT_HTML_SENTINEL_001"
    )
    assert retained == body
    assert total == len(body)
    assert digest == hashlib.sha256(body).hexdigest()
    assert match is True


def test_bounded_read_oversize_retains_limit_plus_one_but_measures_exact():
    # 2 MiB stream, limit 1 MiB: only 1 MiB + 1 bytes are retained,
    # but the reported size and hash are exact over the whole stream
    # (T011 F-01 / T013-F04: the old unbounded resp.read() returned
    # all 2 MiB).
    body = b"x" * (2 * MAX_BODY_BYTES)
    retained, total, digest, match = read_http_body_bounded(
        io.BytesIO(body), MAX_BODY_BYTES, sentinel=b"AT_HTML_SENTINEL_001"
    )
    assert len(retained) == MAX_BODY_BYTES + 1
    assert retained == body[: MAX_BODY_BYTES + 1]
    assert total == len(body)
    assert digest == hashlib.sha256(body).hexdigest()
    assert match is False


def test_bounded_read_finds_sentinel_past_the_retained_prefix():
    # Sentinel at offset 1.5 MiB — past the retained prefix — must
    # still be found: the scan covers the whole stream, not just the
    # retained bytes (a Sentinel straddling a 64 KiB chunk boundary
    # is covered by the overlap scan).
    sentinel = b"AT_HTML_SENTINEL_001"
    body = b"x" * (MAX_BODY_BYTES + 512) + sentinel + b"y" * 100
    retained, total, digest, match = read_http_body_bounded(
        io.BytesIO(body), MAX_BODY_BYTES, sentinel=sentinel
    )
    assert len(retained) == MAX_BODY_BYTES + 1
    assert sentinel not in retained
    assert total == len(body)
    assert digest == hashlib.sha256(body).hexdigest()
    assert match is True


def test_bounded_read_empty_body_and_negative_limit():
    retained, total, digest, match = read_http_body_bounded(
        io.BytesIO(b""), MAX_BODY_BYTES, sentinel=b"S"
    )
    assert (retained, total, digest, match) == (
        b"",
        0,
        hashlib.sha256(b"").hexdigest(),
        False,
    )
    with pytest.raises(PrivacyError):
        read_http_body_bounded(io.BytesIO(b"x"), -1)


# ---------------------------------------------------------------------------
# Level 2 — classifier: an oversize observation is rejected
# ---------------------------------------------------------------------------


def _healthy_observations(*, oversize_index=None):
    """Eight healthy observations; optionally make one oversize."""
    observations = []
    for index in range(1, 9):
        rep = "html" if index in (1, 3, 5, 8) else "markdown"
        experiment = {
            1: "ORIGIN_HTML",
            2: "ORIGIN_MARKDOWN",
            3: "HTML_COLD",
            4: "MARKDOWN_COLD",
            5: "HTML_TO_MARKDOWN",
            6: "HTML_TO_MARKDOWN",
            7: "MARKDOWN_TO_HTML",
            8: "MARKDOWN_TO_HTML",
        }[index]
        body = ("h" if rep == "html" else "m") * 64
        observations.append(
            RequestObservation(
                request_index=index,
                experiment_id=experiment,
                requested_representation=rep,
                response_status=200,
                response_content_type=(
                    "text/html; charset=utf-8"
                    if rep == "html"
                    else "text/markdown; charset=utf-8"
                ),
                body_sha256=hashlib.sha256(body.encode()).hexdigest(),
                sentinel_match=True,
                cache_status=(
                    None if index <= 2 else "MISS"
                ),
                cache_key_sha256="k" * 64 if index > 2 else None,
                cache_entry_id=f"entry-{index:03d}" if index > 2 else None,
                origin_counter_before=index - 1,
                origin_counter_after=index,
                origin_counter_delta=1,
            )
        )
    return observations


def _classify_with_raw(observations, raw_observations):
    contract = parse_contract(
        json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    )
    from accepttwin.cache_proxy import ResetEvidence

    resets = [
        ResetEvidence(
            namespace=f"t011-{name}",
            success=True,
            entries_before=1,
            entries_after=0,
            entries_removed=1,
        )
        for name in (
            "html-cold",
            "markdown-cold",
            "html-to-markdown",
            "markdown-to-html",
        )
    ]
    # origin_events=None: ADR-002 route B — the unit-test caller declares
    # the origin cross-check is not performed (an empty list would mean
    # "checked and found nothing" and fail closed).
    return classify_run(
        contract, observations, None, resets, raw_observations=raw_observations
    )


def test_oversize_observation_rejected_by_classifier():
    """One oversize warm-cache body -> INCONCLUSIVE_LIMIT, not PASS."""
    from accepttwin.evidence import RawObservation

    observations = _healthy_observations()
    raws = []
    for obs in observations:
        oversize = obs.request_index == 6
        raws.append(
            RawObservation(
                request_index=obs.request_index,
                experiment_id=obs.experiment_id,
                requested_representation=obs.requested_representation,
                method="GET",
                url="http://127.0.0.1:18765/doc",
                accept=(
                    "text/html"
                    if obs.requested_representation == "html"
                    else "text/markdown"
                ),
                response_status=200,
                response_content_type=obs.response_content_type,
                body_sha256=obs.body_sha256,
                body_size=(
                    MAX_BODY_BYTES + 1 if oversize else 64
                ),
                sentinel_match=True,
                sentinel_sha256="s" * 64,
                response_headers={},
                cache_status_header="MISS" if obs.request_index > 2 else None,
                cache_key_sha256=obs.cache_key_sha256,
                cache_entry_id=obs.cache_entry_id,
                verified_cache_state=None,
                cache_verification_reasons=(),
                cache_entry_count_before=None,
                cache_entry_count_after=None,
                origin_counter_before=obs.origin_counter_before,
                origin_counter_after=obs.origin_counter_after,
                origin_counter_delta=1,
                origin_event_present=True,
                transport_error=None,
            )
        )
    result = _classify_with_raw(observations, raws)
    assert result.verdict == "INCONCLUSIVE"
    assert any(
        d.code == "INCONCLUSIVE_LIMIT" for d in result.diagnostics
    )


def test_healthy_observations_at_cap_pass_classifier():
    """Control: the same run with all bodies at 64 bytes passes."""
    observations = _healthy_observations()
    raws = []
    for obs in observations:
        from accepttwin.evidence import RawObservation

        raws.append(
            RawObservation(
                request_index=obs.request_index,
                experiment_id=obs.experiment_id,
                requested_representation=obs.requested_representation,
                method="GET",
                url="http://127.0.0.1:18765/doc",
                accept=(
                    "text/html"
                    if obs.requested_representation == "html"
                    else "text/markdown"
                ),
                response_status=200,
                response_content_type=obs.response_content_type,
                body_sha256=obs.body_sha256,
                body_size=64,
                sentinel_match=True,
                sentinel_sha256="s" * 64,
                response_headers={},
                cache_status_header="MISS" if obs.request_index > 2 else None,
                cache_key_sha256=obs.cache_key_sha256,
                cache_entry_id=obs.cache_entry_id,
                verified_cache_state=None,
                cache_verification_reasons=(),
                cache_entry_count_before=None,
                cache_entry_count_after=None,
                origin_counter_before=obs.origin_counter_before,
                origin_counter_after=obs.origin_counter_after,
                origin_counter_delta=1,
                origin_event_present=True,
                transport_error=None,
            )
        )
    result = _classify_with_raw(observations, raws)
    assert result.verdict == "PASS_OBSERVED"


# ---------------------------------------------------------------------------
# Level 3 — live: oversize bodies are measured, never stored as text
# ---------------------------------------------------------------------------


def test_live_oversize_run_measures_but_never_stores_body():
    """E21 live run: bodies > 1 MiB are flagged, not persisted.

    Reuses the frozen E21 fixture through the same harness the
    Golden suite uses (``scripts/s0_harness.py``) — real loopback
    HTTP, real runner, real classifier.
    """
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from s0_harness import EXTENDED_FIXTURE_DIR, run_scenario

    outcome = run_scenario(
        "E21",
        fixture_dir=EXTENDED_FIXTURE_DIR,
        contract_prefix="ext-t011",
        namespace_prefix="t011-E21-size",
    )
    assert outcome.production.verdict == "INCONCLUSIVE"
    assert any(
        d.code == "INCONCLUSIVE_LIMIT"
        for d in outcome.production.diagnostics
    )
    for raw in outcome.run.raw_observations[2:]:
        assert raw.body_size > MAX_BODY_BYTES
    for raw in outcome.run.raw_observations[:2]:
        assert raw.body_size <= MAX_BODY_BYTES
    # Nothing in the run's serialised evidence contains body text:
    # only hashes, sizes and match flags are recorded (§7.12 I-12).
    from accepttwin.privacy import find_forbidden_keys

    raw_dicts = [raw.as_dict() for raw in outcome.run.raw_observations]
    assert find_forbidden_keys(raw_dicts) == []
    blob = json.dumps(raw_dicts, ensure_ascii=False)
    assert "AT_HTML_SENTINEL_001" not in blob
    assert "AT_MARKDOWN_SENTINEL_001" not in blob
    assert all(raw.body_sha256 and len(raw.body_sha256) == 64 for raw in outcome.run.raw_observations)


# ---------------------------------------------------------------------------
# Level 3b — live: both production read sites are bounded (T014)
# ---------------------------------------------------------------------------


def _serve_bytes(body: bytes):
    """A throwaway loopback origin serving *body* for one test."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_live_http_get_bounds_retention_but_measures_exact():
    """T011 F-01: _http_get on a 2 MiB origin retains 1 MiB + 1 bytes.

    The old unbounded read returned all 2 MiB; the bounded read
    retains only the prefix while body_size / body_sha256 /
    sentinel_match stay exact over the whole stream.
    """
    from accepttwin.experiment_runner import _http_get

    sentinel = b"AT_HTML_SENTINEL_001"
    body = sentinel + b"x" * (2 * MAX_BODY_BYTES - len(sentinel))
    server = _serve_bytes(body)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/doc"
        result = _http_get(
            url, "html", 5.0, max_body=MAX_BODY_BYTES, sentinel=sentinel
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result.status == 200
    assert len(result.body) == MAX_BODY_BYTES + 1
    assert result.body_size == len(body)
    assert result.body_sha256 == hashlib.sha256(body).hexdigest()
    assert result.sentinel_match is True


def test_live_proxy_fetch_bounds_retention():
    """T013-F04: proxy _fetch_origin on a 2 MiB origin is bounded too."""
    from accepttwin.cache_proxy import ControlledCacheProxy

    body = b"S" + b"x" * (2 * MAX_BODY_BYTES - 1)
    server = _serve_bytes(body)
    proxy = ControlledCacheProxy(
        port=0,
        mode="respect_vary",
        origin_url=f"http://127.0.0.1:{server.server_address[1]}/doc",
    )
    proxy.start()
    try:
        _, _, _, _, fetched = proxy._fetch_origin("/doc", "text/html")
    finally:
        proxy.stop()
        server.shutdown()
        server.server_close()
    assert len(fetched) == MAX_BODY_BYTES + 1
    assert fetched == body[: MAX_BODY_BYTES + 1]
