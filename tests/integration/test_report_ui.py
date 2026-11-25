"""Integration tests for the self-contained HTML report (P032 T010).

Acceptance criteria (IMPLEMENTATION_PLAN T010):

1. Opens offline, self-contained, no remote request.
2. All five verdicts display correctly.
3. The 48-scenario summary displays correctly.
4. No body text leaks (only hashes and match flags).
5. HTML export matches the JSON report field by field.

The tests assert on the generated static HTML (embedded JSON
payloads, section markers, remote-reference scans) and, when a
headless Chromium is available in the environment, on the actually
rendered DOM. No test re-runs an experiment: the 48 pages are
built from the existing T009 report samples.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "evidence" / "Reports"
GOLDEN_DIR = ROOT / "evidence" / "Golden"
REPORT_UI_DIR = ROOT / "report-ui"
EMBED_SCRIPT = ROOT / "scripts" / "embed_report.py"

SENTINELS = ("AT_HTML_SENTINEL_001", "AT_MARKDOWN_SENTINEL_001")
VERDICTS = (
    "PASS_OBSERVED",
    "ORIGIN_NEGOTIATION_ERROR",
    "REPRESENTATION_BLEED",
    "CONTRACT_MISMATCH",
    "INCONCLUSIVE",
)
SECTION_IDS = (
    "section-verdict",
    "section-baseline",
    "section-experiments",
    "section-timeline",
    "section-cache",
    "section-first-error",
    "section-diagnostics",
    "section-oracle",
    "section-hash",
    "section-privacy",
)
EXPECTED_DISTRIBUTION = {
    "PASS_OBSERVED": 16,
    "ORIGIN_NEGOTIATION_ERROR": 7,
    "REPRESENTATION_BLEED": 8,
    "CONTRACT_MISMATCH": 4,
    "INCONCLUSIVE": 13,
}

# One sample per verdict (T009 distribution 16/7/8/4/13).
VERDICT_SAMPLES = {
    "PASS_OBSERVED": "C01",
    "ORIGIN_NEGOTIATION_ERROR": "C07",
    "REPRESENTATION_BLEED": "C11",
    "CONTRACT_MISMATCH": "C19",
    "INCONCLUSIVE": "C20",
}


def run_embed(*argv: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EMBED_SCRIPT), *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


def extract_payload(html: str, payload_id: str) -> object:
    match = re.search(
        rf'<script type="application/json" id="{payload_id}">\s*(.*?)\s*</script>',
        html,
        re.DOTALL,
    )
    assert match is not None, f"payload {payload_id} missing from HTML"
    return json.loads(match.group(1))


def assert_no_remote_references(html: str, *, allow_relative_links: bool) -> None:
    for sentinel in SENTINELS:
        assert sentinel not in html, f"Sentinel literal {sentinel} leaked into HTML"
    assert "<link" not in html
    assert "<iframe" not in html
    assert "<img" not in html
    assert "<script src" not in html
    assert html.count("<script") == 4, "expected exactly 4 inline <script> tags"
    assert "@import" not in html
    assert "url(" not in html
    assert "data:" not in html
    for match in re.finditer(r"https?://([^\s\"'<>/:]+)", html):
        host = match.group(1).strip("[]").lower()
        is_loopback = host == "localhost" or host == "::1" or (
            host.startswith("127.")
            and len(host.split(".")) == 4
            and all(part.isdigit() for part in host.split("."))
        )
        assert is_loopback, f"non-loopback URL in HTML: {match.group(0)}"
    hrefs = re.findall(r'href="([^"]*)"', html)
    if not allow_relative_links:
        assert hrefs == [], f"single-report page must have no links, got {hrefs}"
    else:
        for href in hrefs:
            assert re.fullmatch(r"[A-Za-z0-9_.\-]+\.html", href), f"non-relative href: {href}"


def load_report(sid: str) -> dict:
    return json.loads((REPORTS_DIR / f"{sid}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Single-report generation
# ---------------------------------------------------------------------------


def test_embed_single_report_round_trips_json(tmp_path: Path) -> None:
    out = tmp_path / "C11.html"
    result = run_embed(
        "evidence/Reports/C11.json",
        "--contract",
        "evidence/Golden/C11/contract.json",
        "-o",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    assert "PRIVACY PREVIEW" in result.stdout
    assert result.stdout.index("PRIVACY PREVIEW") < result.stdout.index("WROTE")
    html = out.read_text(encoding="utf-8")
    source = load_report("C11")
    assert extract_payload(html, "accepttwin-report") == source
    baseline = extract_payload(html, "accepttwin-baseline")
    assert baseline == {
        "html": {
            "accept": "text/html",
            "expected_status": 200,
            "expected_content_type": "text/html; charset=utf-8",
        },
        "markdown": {
            "accept": "text/markdown",
            "expected_status": 200,
            "expected_content_type": "text/markdown; charset=utf-8",
        },
    }
    for section_id in SECTION_IDS:
        assert f'id="{section_id}"' in html, f"missing section {section_id}"
    assert_no_remote_references(html, allow_relative_links=False)


def test_embed_without_contract_uses_frozen_baseline(tmp_path: Path) -> None:
    out = tmp_path / "C01.html"
    result = run_embed("evidence/Reports/C01.json", "-o", str(out))
    assert result.returncode == 0, result.stderr
    html = out.read_text(encoding="utf-8")
    baseline = extract_payload(html, "accepttwin-baseline")
    assert baseline["html"]["accept"] == "text/html"
    assert baseline["markdown"]["accept"] == "text/markdown"
    assert extract_payload(html, "accepttwin-report") == load_report("C01")


def test_embed_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.html"
    second = tmp_path / "second.html"
    for out in (first, second):
        result = run_embed(
            "evidence/Reports/C11.json",
            "--contract",
            "evidence/Golden/C11/contract.json",
            "-o",
            str(out),
        )
        assert result.returncode == 0, result.stderr
    assert first.read_bytes() == second.read_bytes()


def test_check_only_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "C11.html"
    result = run_embed(
        "evidence/Reports/C11.json", "-o", str(out), "--check-only"
    )
    assert result.returncode == 0, result.stderr
    assert "PRIVACY PREVIEW" in result.stdout
    assert "CHECK ONLY" in result.stdout
    assert not out.exists()


# ---------------------------------------------------------------------------
# Five verdicts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verdict,sid", sorted(VERDICT_SAMPLES.items()))
def test_all_five_verdicts_display(tmp_path: Path, verdict: str, sid: str) -> None:
    out = tmp_path / f"{sid}.html"
    result = run_embed(f"evidence/Reports/{sid}.json", "-o", str(out))
    assert result.returncode == 0, result.stderr
    html = out.read_text(encoding="utf-8")
    verdict_section = re.search(
        r'<section id="section-verdict">.*?</section>', html, re.DOTALL
    )
    assert verdict_section is not None
    # The verdict badge is static in the template only after JS
    # rendering; the payload is the source of truth here, and the
    # rendered-DOM test below checks the badge text itself.
    payload = extract_payload(html, "accepttwin-report")
    assert payload["verdict"] == verdict
    assert payload["scenario_id"] == sid
    assert payload["report_hash"] in html
    # The verdict badge text itself is produced at runtime by the
    # compiled bundle (rendered-DOM test below checks it); the
    # payload must carry the exact verdict string.
    assert verdict in html


# ---------------------------------------------------------------------------
# HTML <-> JSON consistency (spot check: one bleed + one pass sample)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sid", ["C11", "C01"])
def test_html_matches_json_report(tmp_path: Path, sid: str) -> None:
    out = tmp_path / f"{sid}.html"
    result = run_embed(
        f"evidence/Reports/{sid}.json",
        "--contract",
        f"evidence/Golden/{sid}/contract.json",
        "-o",
        str(out),
    )
    assert result.returncode == 0, result.stderr
    html = out.read_text(encoding="utf-8")
    payload = extract_payload(html, "accepttwin-report")
    source = load_report(sid)
    for field in (
        "verdict",
        "first_error",
        "first_error_experiment_id",
        "report_hash",
        "oracle",
        "oracle_parity",
        "final",
        "critical_count",
        "warning_count",
    ):
        assert payload[field] == source[field], f"{sid}: {field} mismatch"
    assert payload["diagnostics"] == source["diagnostics"]
    assert payload["observations"] == source["observations"]
    assert payload["input"] == source["input"]
    assert payload["reasons"] == source["reasons"]


# ---------------------------------------------------------------------------
# Fail-closed rejection
# ---------------------------------------------------------------------------


def test_embed_rejects_tampered_hash(tmp_path: Path) -> None:
    bad = load_report("C11")
    bad["report_hash"] = "0" * 64
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    result = run_embed(str(bad_path), "-o", str(tmp_path / "bad.html"))
    assert result.returncode == 1
    assert "EMBED_FAIL" in result.stderr
    assert not (tmp_path / "bad.html").exists()


def test_embed_rejects_forbidden_body_key(tmp_path: Path) -> None:
    bad = load_report("C01")
    bad["diagnostics"] = [
        {
            "code": "CONTRACT_MISMATCH",
            "severity": "CRITICAL",
            "message": "x",
            "experiment_id": "ORIGIN_HTML",
            "request_index": 1,
            "evidence": {"body": "leaked text"},
        }
    ]
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    result = run_embed(str(bad_path), "-o", str(tmp_path / "bad.html"))
    assert result.returncode == 1
    assert "EMBED_FAIL" in result.stderr
    assert not (tmp_path / "bad.html").exists()


def test_embed_rejects_sentinel_literal(tmp_path: Path) -> None:
    bad = load_report("C01")
    bad["reasons"] = ["contains AT_HTML_SENTINEL_001 verbatim"]
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    result = run_embed(str(bad_path), "-o", str(tmp_path / "bad.html"))
    assert result.returncode == 1
    assert "EMBED_FAIL" in result.stderr
    assert not (tmp_path / "bad.html").exists()


def test_embed_rejects_missing_file(tmp_path: Path) -> None:
    result = run_embed("evidence/Reports/ZZZ.json", "-o", str(tmp_path / "x.html"))
    assert result.returncode == 1
    assert "EMBED_FAIL" in result.stderr


# ---------------------------------------------------------------------------
# 48-scenario summary
# ---------------------------------------------------------------------------


def test_all_48_summary_matches_reports_and_record(tmp_path: Path) -> None:
    out_dir = tmp_path / "html"
    result = run_embed("--all-48", "--out-dir", str(out_dir))
    assert result.returncode == 0, result.stderr
    assert "PRIVACY PREVIEW" in result.stdout
    files = sorted(p.name for p in out_dir.iterdir())
    assert files == [f"{sid}.html" for sid in
                     [f"C{i:02d}" for i in range(1, 25)] + [f"E{i:02d}" for i in range(1, 25)]] + ["index.html"]
    summary = extract_payload(
        (out_dir / "index.html").read_text(encoding="utf-8"),
        "accepttwin-summary",
    )
    assert summary["total"] == 48
    assert summary["counts"] == EXPECTED_DISTRIBUTION
    recorded = json.loads((REPORTS_DIR / "REPORTS_SUMMARY.json").read_text(encoding="utf-8"))
    assert len(summary["rows"]) == 48
    for row in summary["rows"]:
        sid = row["scenario_id"]
        source = load_report(sid)
        assert row["verdict"] == source["verdict"] == recorded["samples"][sid]["verdict"]
        assert row["first_error"] == source["first_error"] == recorded["samples"][sid]["first_error"]
        assert row["oracle_parity"] == source["oracle_parity"] is True
        assert row["final"] is True
        assert row["report_hash"] == source["report_hash"] == recorded["samples"][sid]["report_hash"]
        assert row["critical_count"] == source["critical_count"]
        assert row["warning_count"] == source["warning_count"]
        page = (out_dir / f"{sid}.html").read_text(encoding="utf-8")
        assert extract_payload(page, "accepttwin-report") == source
        assert_no_remote_references(page, allow_relative_links=False)
    index_html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert_no_remote_references(index_html, allow_relative_links=True)
    # The per-scenario links are built at runtime by the bundle
    # from the summary payload (the rendered-DOM test below checks
    # href="C11.html" appears); the static file carries the data,
    # not the links.
    assert {row["scenario_id"] for row in summary["rows"]} == {
        f"C{i:02d}" for i in range(1, 25)
    } | {f"E{i:02d}" for i in range(1, 25)}


def test_no_sentinel_or_remote_in_committed_pages() -> None:
    html_dir = REPORTS_DIR / "html"
    assert html_dir.is_dir(), "evidence/Reports/html/ was not generated — run scripts/embed_report.py --all-48"
    pages = sorted(html_dir.glob("*.html"))
    assert len(pages) == 49
    for page in pages:
        html = page.read_text(encoding="utf-8")
        allow_links = page.name == "index.html"
        assert_no_remote_references(html, allow_relative_links=allow_links)


# ---------------------------------------------------------------------------
# Template and bundle hygiene
# ---------------------------------------------------------------------------


def test_template_and_assets_have_no_remote_references() -> None:
    for name in ("index.html", "styles.css", "report-ui.js"):
        text = (REPORT_UI_DIR / name).read_text(encoding="utf-8")
        for sentinel in SENTINELS:
            assert sentinel not in text, f"{name} contains a Sentinel literal"
        assert "http://" not in text, f"{name} contains http://"
        assert "https://" not in text, f"{name} contains https://"
        assert "@import" not in text, f"{name} contains @import"
        assert "url(" not in text, f"{name} contains url("
    template = (REPORT_UI_DIR / "index.html").read_text(encoding="utf-8")
    assert "未嵌入报告数据" in template
    for section_id in SECTION_IDS:
        assert f'id="{section_id}"' in template


def test_compiled_bundle_matches_typescript_sources() -> None:
    bundle = REPORT_UI_DIR / "report-ui.js"
    assert bundle.is_file()
    text = bundle.read_text(encoding="utf-8")
    assert "AcceptTwinUI.init();" in text
    assert "双向缓存时间线" in text
    assert "下载 JSON 报告" in text
    tsc = REPORT_UI_DIR / "node_modules" / ".bin" / "tsc"
    if tsc.is_file():
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = subprocess.run(
                [str(tsc), "-p", "tsconfig.json", "--outFile", str(tmp_path / "fresh.js")],
                cwd=REPORT_UI_DIR,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert result.returncode == 0, result.stderr
            fresh = (tmp_path / "fresh.js").read_text(encoding="utf-8")
            assert fresh == text, "committed report-ui.js is stale — run npm run build in report-ui/"
    else:
        # No local tsc: the marker assertions above still pin the
        # bundle content; a fresh recompile is verified in the T010
        # acceptance run (see report-ui/T010_NOTES.md).
        assert "AcceptTwinUI" in text


# ---------------------------------------------------------------------------
# Rendered DOM (headless Chromium, when available in the environment)
# ---------------------------------------------------------------------------


def _find_chrome() -> str | None:
    for candidate in (
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("google-chrome"),
        str(Path.home() / ".cache" / "ms-playwright" / "chromium-1255" / "chrome-linux64" / "chrome"),
        "/opt/meta-chromium/chrome",
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _dump_dom(chrome: str, html_path: Path, tmp_path: Path) -> str:
    out = tmp_path / (html_path.stem + ".dom.html")
    result = subprocess.run(
        [
            chrome,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--virtual-time-budget=5000",
            "--dump-dom",
            f"file://{html_path}",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[:500]
    out.write_text(result.stdout, encoding="utf-8")
    return result.stdout


def test_headless_chrome_renders_report_offline(tmp_path: Path) -> None:
    chrome = _find_chrome()
    if chrome is None:
        # T014 (T010 P2-2): fail hard instead of silently skipping —
        # these are offline acceptance tests, and a Chromium-less
        # environment must not silently drop them. CI must provide a
        # headless Chromium (this repo's _find_chrome covers the
        # Playwright chromium-1255 install).
        pytest.fail(
            "headless Chromium is required for this offline rendering "
            "acceptance test, but none was found"
        )
    page = tmp_path / "C11.html"
    result = run_embed(
        "evidence/Reports/C11.json",
        "--contract",
        "evidence/Golden/C11/contract.json",
        "-o",
        str(page),
    )
    assert result.returncode == 0, result.stderr
    dom = _dump_dom(chrome, page, tmp_path)
    assert "REPRESENTATION_BLEED · 表示串版" in dom
    assert "请求 006" in dom
    assert "下载 JSON 报告（C11.json）" in dom
    assert "双重证据一致" in dom
    for section_id in SECTION_IDS:
        match = re.search(
            rf'<section id="{section_id}">(.*?)</section>', dom, re.DOTALL
        )
        assert match is not None, f"missing section {section_id} in rendered DOM"
        assert len(match.group(1).strip()) > 50, f"section {section_id} rendered empty"
    assert 'id="no-payload" hidden=""' in dom


def test_headless_chrome_renders_summary_offline(tmp_path: Path) -> None:
    chrome = _find_chrome()
    if chrome is None:
        # T014 (T010 P2-2): fail hard instead of silently skipping —
        # these are offline acceptance tests, and a Chromium-less
        # environment must not silently drop them. CI must provide a
        # headless Chromium (this repo's _find_chrome covers the
        # Playwright chromium-1255 install).
        pytest.fail(
            "headless Chromium is required for this offline rendering "
            "acceptance test, but none was found"
        )
    out_dir = tmp_path / "html"
    result = run_embed("--all-48", "--out-dir", str(out_dir))
    assert result.returncode == 0, result.stderr
    dom = _dump_dom(chrome, out_dir / "index.html", tmp_path)
    assert "48 场景汇总" in dom
    assert "PASS_OBSERVED 16" in dom
    assert "INCONCLUSIVE 13" in dom
    assert dom.count("<tr>") >= 49  # header + 48 rows
    assert 'href="C11.html"' in dom
