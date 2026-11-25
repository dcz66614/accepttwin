"""Privacy regression: logs and reports carry no body text or
sensitive headers (P032 T011, scenarios 9–10).

Acceptance scenarios (IMPLEMENTATION_PLAN T011, PROJECT_BOOK §7.12
I-12, §17.2):

9.  logs do not contain body text;
10. logs do not contain sensitive request headers.

Verified at three levels: the privacy scanners themselves
(positive/negative on crafted text), the live run (a real healthy
four-experiment run over loopback — its step log, failures, origin
event log and serialised observations are audited, and the logging
system is captured to prove nothing is emitted), and the frozen
evidence on disk (all 48 JSON reports in evidence/Reports/).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import dataclasses
import sys

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "scripts")
)

from s0_harness import run_scenario  # noqa: E402
from accepttwin.privacy import (
    FORBIDDEN_REPORT_KEYS,
    SENTINELS,
    PrivacyError,
    assert_log_clean,
    assert_report_clean,
    find_forbidden_keys,
    scan_text_for_body,
    scan_text_for_sensitive_headers,
    scan_text_for_sentinels,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"
REPORTS_DIR = ROOT / "evidence" / "Reports"

MARKER_BODY = (
    "<html><body>UNIQUE-MARKER-BODY-9f3c21 "
    "AT_HTML_SENTINEL_001</body></html>"
)


# ---------------------------------------------------------------------------
# The scanners themselves — positive and negative
# ---------------------------------------------------------------------------


def test_scan_sensitive_headers_finds_all_four_names():
    text = (
        "request failed\n"
        "Authorization: Bearer SECRET-TOKEN\n"
        "Cookie: session=SECRET-VALUE\n"
        "proxy-authorization: Basic dXNlcjpwYXNz\n"
        "Set-Cookie: id=SECRET; Path=/\n"
    )
    assert scan_text_for_sensitive_headers(text) == [
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
    ]


@pytest.mark.parametrize("name", ["AUTHORIZATION", "Cookie", "PROXY-AUTHORIZATION"])
def test_scan_sensitive_headers_is_case_insensitive(name):
    assert scan_text_for_sensitive_headers(f"{name}: secret") == [
        name.lower()
    ]


def test_scan_sensitive_headers_finds_json_keys():
    text = '{"headers": {"authorization": "Bearer SECRET", "cookie": "s=1"}}'
    assert scan_text_for_sensitive_headers(text) == [
        "authorization",
        "cookie",
    ]


def test_scan_sensitive_headers_clean_text_passes():
    text = (
        "Accept: text/html\n"
        "Accept-Encoding: identity\n"
        "User-Agent: AcceptTwin/1.0.0\n"
        "Accept-Language: en\n"
        "status=200 content_type=text/html; charset=utf-8\n"
        "body_sha256=ab12... sentinel_match=true\n"
    )
    assert scan_text_for_sensitive_headers(text) == []


def test_scan_sentinels_finds_both_literals():
    text = "body contained AT_HTML_SENTINEL_001 and AT_MARKDOWN_SENTINEL_001"
    assert scan_text_for_sentinels(text) == list(SENTINELS)


def test_scan_sentinels_clean_text_passes():
    assert scan_text_for_sentinels("sentinel_match=true body_sha256=ab12") == []


def test_scan_body_finds_verbatim_body():
    assert scan_text_for_body(f"log line {MARKER_BODY} end", MARKER_BODY) is True
    assert scan_text_for_body("unrelated log line", MARKER_BODY) is False
    assert scan_text_for_body("log", b"short") is False  # < 8 chars: ignored
    assert scan_text_for_body("log", "") is False


def test_assert_log_clean_accepts_hashes_and_flags():
    assert_log_clean(
        "step 05 ok body_sha256=ab12cd34 sentinel_match=true status=200",
        bodies=(MARKER_BODY,),
    )


def test_assert_log_clean_rejects_body_text():
    with pytest.raises(PrivacyError, match="raw response body text"):
        assert_log_clean(f"saw body: {MARKER_BODY}", bodies=(MARKER_BODY,))


def test_assert_log_clean_rejects_sensitive_header():
    with pytest.raises(PrivacyError, match="sensitive request header"):
        assert_log_clean("Authorization: Bearer SECRET-TOKEN")


def test_assert_log_clean_rejects_sentinel_literal():
    with pytest.raises(PrivacyError, match="Sentinel literal"):
        assert_log_clean("body contained AT_HTML_SENTINEL_001")


def test_assert_log_clean_never_echoes_the_secret():
    try:
        assert_log_clean("Authorization: Bearer DO-NOT-ECHO-ME-12345")
    except PrivacyError as exc:
        assert "DO-NOT-ECHO-ME-12345" not in str(exc)
    else:  # pragma: no cover - the audit must raise here
        raise AssertionError("assert_log_clean did not raise")


# ---------------------------------------------------------------------------
# Cross-check: the frozen forbidden-key set is the same everywhere
# ---------------------------------------------------------------------------


def test_forbidden_key_set_matches_report_builder_and_embed_script():
    """The ban must not silently narrow in any one layer (T009/T010)."""
    from accepttwin.report_builder import _FORBIDDEN_KEYS as builder_keys

    embed_text = (ROOT / "scripts" / "embed_report.py").read_text(
        encoding="utf-8"
    )
    assert FORBIDDEN_REPORT_KEYS == builder_keys
    for key in FORBIDDEN_REPORT_KEYS:
        assert f'"{key}"' in embed_text


def test_sentinel_literals_match_the_frozen_contract():
    """The scanner's literals are the contract's Sentinels (§5.1.2)."""
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_sentinels = {
        rep["sentinel"] for rep in data["representations"].values()
    }
    assert set(SENTINELS) == contract_sentinels
    assert len(SENTINELS) == 2


# ---------------------------------------------------------------------------
# Scenario 9 — live: a real run's logs contain no body text
# ---------------------------------------------------------------------------


def _run_c01():
    """A real healthy four-experiment run (frozen C01 Golden)."""
    return run_scenario("C01", namespace_prefix="t011-C01-logs")


def test_live_run_logs_contain_no_body_text(caplog):
    """The runner's own records and the logging system stay body-free."""
    with caplog.at_level(logging.DEBUG):
        outcome = _run_c01()
    assert outcome.production.verdict == "PASS_OBSERVED"
    # (a) nothing was emitted to the logging system at all: the HTTP
    # handlers suppress log_message and no module logs bodies (§7.12).
    assert caplog.records == []
    # (b) the run's own records carry hashes/flags, never body text.
    blob = json.dumps(
        {
            "evidence": outcome.run.as_dict(),
            "events": [
                dataclasses.asdict(event)
                for event in outcome.adj_origin_events
            ],
        },
        ensure_ascii=False,
        default=str,
    )
    assert "AT_HTML_SENTINEL_001" not in blob
    assert "AT_MARKDOWN_SENTINEL_001" not in blob
    assert_log_clean(blob, bodies=(MARKER_BODY,))
    assert find_forbidden_keys(json.loads(blob)) == []


def test_live_run_origin_events_carry_no_headers_or_body():
    """Origin events record method/path/accept/status only (§5.3)."""
    outcome = _run_c01()
    events = outcome.adj_origin_events
    assert 6 <= len(events) <= 8
    for event in events:
        fields = set(dataclasses.asdict(event))
        assert fields.isdisjoint({"authorization", "cookie", "headers", "body"})
        assert event.accept in ("text/html", "text/markdown")


# ---------------------------------------------------------------------------
# Scenario 10 — live + frozen evidence: no sensitive headers anywhere
# ---------------------------------------------------------------------------


def test_live_run_records_contain_no_sensitive_headers():
    outcome = _run_c01()
    blob = json.dumps(
        {
            "evidence": outcome.run.as_dict(),
            "events": [
                dataclasses.asdict(event)
                for event in outcome.adj_origin_events
            ],
        },
        ensure_ascii=False,
        default=str,
    )
    assert scan_text_for_sensitive_headers(blob) == []
    assert find_forbidden_keys(json.loads(blob)) == []


def test_all_48_frozen_reports_are_clean():
    """All 48 saved JSON reports: no forbidden keys, no Sentinels."""
    import re

    reports = [
        path
        for path in sorted(REPORTS_DIR.glob("*.json"))
        if re.fullmatch(r"[CE]\d\d", path.stem)
    ]
    assert len(reports) == 48
    for path in reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        assert_report_clean(report)  # raises on any violation
        assert scan_text_for_sensitive_headers(
            path.read_text(encoding="utf-8")
        ) == []
    # The summary file (the 49th JSON) must be clean as well.
    assert_report_clean(
        json.loads((REPORTS_DIR / "REPORTS_SUMMARY.json").read_text(
            encoding="utf-8"
        ))
    )


def test_report_audit_rejects_tainted_dict_at_any_depth():
    """Positive control for the report audit: a tainted dict fails."""
    assert_report_clean({"verdict": "PASS_OBSERVED", "body_sha256": "ab12"})
    with pytest.raises(PrivacyError, match="forbidden key"):
        assert_report_clean({"observations": [{"BODY": "secret"}]})
    with pytest.raises(PrivacyError, match="Sentinel literal"):
        assert_report_clean({"reasons": ["saw AT_HTML_SENTINEL_001"]})
