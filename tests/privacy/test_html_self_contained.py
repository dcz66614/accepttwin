"""Privacy regression: HTML reports are self-contained (P032 T011).

Acceptance scenario 11 — HTML does not access remote resources
(PROJECT_BOOK §14.4, §17.1; IMPLEMENTATION_PLAN T010/T011).

This test *pins* the result the T010 independent review already
verified by hand (49 pages, no remote references, no Sentinel
literals): it re-scans all 49 pages in ``evidence/Reports/html/``
with :mod:`accepttwin.privacy` on every run, so any later page that
gains a CDN link, a remote font, an image or a Sentinel literal
fails loudly. Positive cases (each forbidden construct, alone)
prove the scanner actually fires; negative cases (inline script,
relative link, loopback evidence URL) prove it does not over-fire.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from accepttwin.privacy import (
    PrivacyError,
    assert_html_directory_clean,
    scan_html_directory,
    scan_html_for_remote_resources,
)

ROOT = Path(__file__).resolve().parents[2]
HTML_DIR = ROOT / "evidence" / "Reports" / "html"


# ---------------------------------------------------------------------------
# The scanner fires on every forbidden construct (positive cases)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("snippet", "kind"),
    [
        ('<link rel="stylesheet" href="https://cdn.example.com/x.css">', "link-tag"),
        ('<link rel="stylesheet" href="local.css">', "link-tag"),
        ('<iframe src="https://example.com/"></iframe>', "iframe-tag"),
        ('<img src="https://example.com/pic.png">', "img-tag"),
        ('<img src="pic.png">', "img-tag"),
        ('<script src="https://cdn.example.com/app.js"></script>', "script-src"),
        ('<script src="app.js"></script>', "script-src"),
        ("<style>@import url('https://fonts.googleapis.com/css');</style>", "css-import"),
        ("<style>@import 'theme.css';</style>", "css-import"),
        ("<div style=\"background: url(https://example.com/bg.png)\"></div>", "css-url"),
        ("<div style=\"background: url(data:image/png;base64,AAAA)\"></div>", "css-url"),
        ('<a href="https://example.com/">out</a>', "remote-url"),
        ('<a href="http://example.com/">out</a>', "remote-url"),
        ('<img src="//cdn.example.com/pic.png">', "remote-url"),
        ('<p>see https://example.com/docs for details</p>', "remote-url"),
        ('<p>data:text/html,<b>x</b></p>', "data-uri"),
        ("<p>body contained AT_HTML_SENTINEL_001</p>", "sentinel-literal"),
        ("<p>body contained AT_MARKDOWN_SENTINEL_001</p>", "sentinel-literal"),
        ('<link href="https://fonts.googleapis.com/css2?family=X">', "link-tag"),
    ],
)
def test_scanner_fires_on_forbidden_construct(snippet, kind):
    refs = scan_html_for_remote_resources(snippet)
    assert any(ref.kind == kind for ref in refs), refs


# ---------------------------------------------------------------------------
# The scanner does not over-fire (negative cases)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "snippet",
    [
        "<script>document.getElementById('x').textContent = 'hi';</script>",
        '<a href="C11.html">C11</a>',
        '<a href="#section-verdict">jump</a>',
        # Loopback evidence URLs are diagnostic text (§8.6), not fetches.
        "<p>request_url: http://127.0.0.1:18765/doc</p>",
        "<p>redirect_target: http://localhost:18766/other</p>",
        "<p>redirect_target: http://[::1]:18766/other</p>",
        "<p>redirect_target: redacted:non-loopback</p>",
        "<p>body_sha256: ab12cd34 sentinel_match: true</p>",
        "<!DOCTYPE html><html><head><title>t</title></head><body></body></html>",
    ],
)
def test_scanner_passes_clean_html(snippet):
    assert scan_html_for_remote_resources(snippet) == []


# ---------------------------------------------------------------------------
# Scenario 11 — all 49 frozen pages are clean
# ---------------------------------------------------------------------------


def test_all_49_pages_scan_clean():
    """Pin of the T010 review finding: 49 pages, 0 violations."""
    result = assert_html_directory_clean(HTML_DIR, expected_count=49)
    assert len(result) == 49
    assert all(refs == [] for refs in result.values())
    expected_names = {f"C{i:02d}.html" for i in range(1, 25)}
    expected_names |= {f"E{i:02d}.html" for i in range(1, 25)}
    expected_names.add("index.html")
    assert set(result) == expected_names


def test_scan_directory_returns_per_file_results():
    result = scan_html_directory(HTML_DIR)
    assert len(result) == 49
    assert result["index.html"] == []
    assert result["C11.html"] == []


def test_scan_directory_rejects_missing_directory(tmp_path):
    with pytest.raises(PrivacyError, match="does not exist"):
        scan_html_directory(tmp_path / "no-such-dir")


def test_expected_count_mismatch_is_a_failure():
    with pytest.raises(PrivacyError, match="expected 48 HTML pages"):
        assert_html_directory_clean(HTML_DIR, expected_count=48)


def test_tainted_directory_fails(tmp_path):
    """Positive control: one bad page fails the whole directory."""
    good = tmp_path / "good.html"
    good.write_text("<html><body><script>var x = 1;</script></body></html>")
    bad = tmp_path / "bad.html"
    bad.write_text(
        '<html><body><img src="https://example.com/x.png"></body></html>'
    )
    result = scan_html_directory(tmp_path)
    assert result["good.html"] == []
    assert any(ref.kind == "img-tag" for ref in result["bad.html"])
    with pytest.raises(PrivacyError, match="bad.html"):
        assert_html_directory_clean(tmp_path, expected_count=2)
