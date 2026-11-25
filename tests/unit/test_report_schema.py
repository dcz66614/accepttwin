"""Tests for the formal report Schema (P032 T009, §14.3).

Every assertion here runs through
``tests/unit/independent_schema_validator.py`` — a minimal
validator that reads only the Schema file and never imports
``accepttwin.report_builder`` (or any production module). The
production generator is therefore never trusted to validate
itself; a report passes here only because an independent checker
says so.

Coverage:

* Schema meta: Draft 2020-12, top-level ``additionalProperties:
  false``, and the Schema stays inside the keyword subset the
  independent validator implements (so the checker cannot silently
  weaken);
* a hand-written minimal valid report (built literally, with no
  production code) validates — proving the validator, not just
  the generator;
* one mutation per acceptance rule is rejected: extra top-level
  field, verdict outside the five frozen values, severity outside
  CRITICAL/WARNING, non-positive ``request_index``, non-integer
  ``origin_counter_delta``, malformed hashes, non-loopback URLs,
  sensitive fields (``Authorization`` / ``Cookie``) at top level
  and inside diagnostic evidence, body-text fields, wrong cache
  status, wrong observation count, missing required field;
* all 48 committed samples in ``evidence/Reports/`` validate,
  match the recorded Golden verdicts, carry no forbidden key and
  no non-loopback URL, and their hashes recompute independently;
* committed samples equal what the generator builds from the
  recorded evidence (reproducibility, checked for C01/C11/E22).
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from independent_schema_validator import (  # noqa: E402
    SUPPORTED_KEYWORDS,
    load_schema,
    validate,
    validate_report_file,
)
from accepttwin.contract import canonical_json_bytes  # noqa: E402
from accepttwin.report_builder import (  # noqa: E402
    REPORT_HASH_EXCLUDED_FIELDS,
    build_report,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "accepttwin.report.v1.schema.json"
REPORTS_DIR = ROOT / "evidence" / "Reports"
GOLDEN_DIR = ROOT / "evidence" / "Golden"

SCENARIO_IDS = tuple(
    [f"C{i:02d}" for i in range(1, 25)] + [f"E{i:02d}" for i in range(1, 25)]
)

_HASH = "ab" * 32
_KEY = "cd" * 32

_FORBIDDEN_KEYS = {
    "body",
    "body_text",
    "response_body",
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
}


def _minimal_valid_report():
    """A valid report written literally — no production code."""
    observations = []
    for index, (experiment_id, rep) in enumerate(
        [
            ("ORIGIN_HTML", "html"),
            ("ORIGIN_MARKDOWN", "markdown"),
            ("HTML_COLD", "html"),
            ("MARKDOWN_COLD", "markdown"),
            ("HTML_TO_MARKDOWN", "html"),
            ("HTML_TO_MARKDOWN", "markdown"),
            ("MARKDOWN_TO_HTML", "markdown"),
            ("MARKDOWN_TO_HTML", "html"),
        ],
        start=1,
    ):
        content_type = (
            "text/html; charset=utf-8"
            if rep == "html"
            else "text/markdown; charset=utf-8"
        )
        observations.append(
            {
                "request_index": index,
                "experiment_id": experiment_id,
                "requested_representation": rep,
                "response_status": 200,
                "response_content_type": content_type,
                "body_sha256": _HASH,
                "sentinel_match": True,
                "cache_status": "MISS" if index > 2 else None,
                "cache_key_sha256": _KEY if index > 2 else None,
                "cache_entry_id": "entry-" + "cd" * 8 if index > 2 else None,
                "origin_counter_delta": 1,
            }
        )
    return {
        "schema": "accepttwin.report/v1",
        "project": {"project_id": "P032", "version": "1.0.1"},
        "scenario_id": "C01",
        "input": {
            "contract_id": "s0-C01",
            "contract_sha256": _HASH,
            "url": "http://127.0.0.1:18765/doc",
            "origin_url": "http://127.0.0.1:18766/doc",
            "cache_behavior": {
                "mode": "variant_by_accept",
                "vary_accept": "advisory",
                "max_age_seconds": 60,
            },
            "request_headers": {
                "accept_encoding": "identity",
                "user_agent": "AcceptTwin/1.0.0",
                "accept_language": "en",
            },
        },
        "observations": observations,
        "diagnostics": [],
        "verdict": "PASS_OBSERVED",
        "first_error": None,
        "first_error_experiment_id": None,
        "critical_count": 0,
        "warning_count": 0,
        "reasons": ["all checks passed"],
        "oracle": {
            "verdict": "PASS_OBSERVED",
            "first_error": None,
            "first_error_experiment_id": None,
        },
        "oracle_parity": True,
        "final": True,
        "report_hash": _HASH,
    }


def _forbidden_keys_anywhere(value, found=None):
    found = found if found is not None else []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                found.append(key)
            _forbidden_keys_anywhere(item, found)
    elif isinstance(value, list):
        for item in value:
            _forbidden_keys_anywhere(item, found)
    return found


def _independent_hash(report):
    """Recompute the report hash without the production helper."""
    def strip(value):
        if isinstance(value, dict):
            return {
                k: strip(v)
                for k, v in value.items()
                if k not in REPORT_HASH_EXCLUDED_FIELDS
            }
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    payload = {k: v for k, v in report.items() if k != "report_hash"}
    return hashlib.sha256(canonical_json_bytes(strip(payload))).hexdigest()


def _schema_keywords(schema, found=None):
    """Collect the keyword names used by *schema*.

    Property names (keys of ``properties``) and definition names
    (keys of ``$defs``) are field names, not keywords, and are
    skipped; every other dict key of a schema object is a keyword.
    """
    found = found if found is not None else set()
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in ("properties", "$defs"):
                for sub in value.values():
                    _schema_keywords(sub, found)
            else:
                found.add(key)
                _schema_keywords(value, found)
    elif isinstance(schema, list):
        for item in schema:
            _schema_keywords(item, found)
    return found


# ---------------------------------------------------------------------------
# Schema meta
# ---------------------------------------------------------------------------


def test_schema_is_draft_2020_12_with_closed_top_level():
    schema = load_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema"]["const"] == "accepttwin.report/v1"
    for field in (
        "schema",
        "project",
        "scenario_id",
        "input",
        "observations",
        "diagnostics",
        "verdict",
        "first_error",
        "first_error_experiment_id",
        "critical_count",
        "warning_count",
        "reasons",
        "oracle",
        "oracle_parity",
        "final",
        "report_hash",
    ):
        assert field in schema["required"]


def test_schema_stays_inside_validator_subset():
    schema = load_schema()
    used = _schema_keywords(schema)
    unsupported = used - SUPPORTED_KEYWORDS - {
        "$schema",
        "$id",
        "title",
        "description",
    }
    assert unsupported == set(), f"unsupported keywords in schema: {unsupported}"


def test_hand_written_minimal_report_validates():
    assert validate(_minimal_valid_report()) == []


# ---------------------------------------------------------------------------
# One rejected mutation per acceptance rule
# ---------------------------------------------------------------------------


def _mutated(mutate):
    report = _minimal_valid_report()
    mutate(report)
    return report


@pytest.mark.parametrize(
    "name,mutate",
    [
        (
            "extra top-level field",
            lambda r: r.update({"body_text": "hello"}),
        ),
        (
            "extra top-level sensitive field",
            lambda r: r.update({"authorization": "Bearer x"}),
        ),
        ("verdict outside enum", lambda r: r.update({"verdict": "MAYBE"})),
        (
            "severity outside enum",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "INFO",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {},
                }
            ),
        ),
        (
            "unknown diagnostic code",
            lambda r: r["diagnostics"].append(
                {
                    "code": "NOT_A_CODE",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {},
                }
            ),
        ),
        (
            "request_index zero in observation",
            lambda r: r["observations"][0].update({"request_index": 0}),
        ),
        (
            "request_index zero in diagnostic",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 0,
                    "evidence": {},
                }
            ),
        ),
        (
            "origin_counter_delta as string",
            lambda r: r["observations"][0].update(
                {"origin_counter_delta": "1"}
            ),
        ),
        (
            "body_sha256 uppercase",
            lambda r: r["observations"][0].update(
                {"body_sha256": "AB" * 32}
            ),
        ),
        (
            "body_sha256 short",
            lambda r: r["observations"][0].update({"body_sha256": "abcd"}),
        ),
        (
            "contract_sha256 short",
            lambda r: r["input"].update({"contract_sha256": "abcd"}),
        ),
        (
            "report_hash wrong format",
            lambda r: r.update({"report_hash": "not-a-hash"}),
        ),
        (
            "non-loopback url",
            lambda r: r["input"].update({"url": "http://example.com/doc"}),
        ),
        (
            "non-loopback origin_url",
            lambda r: r["input"].update(
                {"origin_url": "http://192.168.1.10/doc"}
            ),
        ),
        (
            "https url",
            lambda r: r["input"].update(
                {"url": "https://127.0.0.1:18765/doc"}
            ),
        ),
        # T009-FIX (P2-1): the loopback URL pattern now checks octet
        # range (0-255) and port range (1-65535), not just digit count.
        (
            "url 127.999.0.1 octet out of range",
            lambda r: r["input"].update(
                {"url": "http://127.999.0.1:18765/doc"}
            ),
        ),
        (
            "url 127.0.0.256 octet out of range",
            lambda r: r["input"].update(
                {"url": "http://127.0.0.256/doc"}
            ),
        ),
        (
            "origin_url 127.999.0.1 octet out of range",
            lambda r: r["input"].update(
                {"origin_url": "http://127.999.0.1:18766/doc"}
            ),
        ),
        (
            "url port 0",
            lambda r: r["input"].update(
                {"url": "http://127.0.0.1:0/doc"}
            ),
        ),
        (
            "url port 65536",
            lambda r: r["input"].update(
                {"url": "http://127.0.0.1:65536/doc"}
            ),
        ),
        (
            "url port 99999",
            lambda r: r["input"].update(
                {"url": "http://127.0.0.1:99999/doc"}
            ),
        ),
        (
            "cookie inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"cookie": "session=1"},
                }
            ),
        ),
        (
            "authorization inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"Authorization": "Bearer x"},
                }
            ),
        ),
        (
            "body_text inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "SENTINEL_MISMATCH",
                    "severity": "CRITICAL",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"body_text": "<html>…"},
                }
            ),
        ),
        # T009-FIX (P1-1): the evidence propertyNames ban is
        # case-insensitive — every forbidden key must be rejected in
        # ALL-CAPS and mixed case too, not just its original casing.
        (
            "AUTHORIZATION inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"AUTHORIZATION": "Bearer x"},
                }
            ),
        ),
        (
            "COOKIE inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"COOKIE": "session=1"},
                }
            ),
        ),
        (
            "BODY inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "SENTINEL_MISMATCH",
                    "severity": "CRITICAL",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"BODY": "<html>…"},
                }
            ),
        ),
        (
            "BODY_TEXT inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "SENTINEL_MISMATCH",
                    "severity": "CRITICAL",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"BODY_TEXT": "<html>…"},
                }
            ),
        ),
        (
            "RESPONSE_BODY inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "SENTINEL_MISMATCH",
                    "severity": "CRITICAL",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"RESPONSE_BODY": "<html>…"},
                }
            ),
        ),
        (
            "PROXY-AUTHORIZATION inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"PROXY-AUTHORIZATION": "Basic x"},
                }
            ),
        ),
        (
            "SET-COOKIE inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"SET-COOKIE": "session=1"},
                }
            ),
        ),
        (
            "Proxy-Authorization mixed case inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"Proxy-Authorization": "Basic x"},
                }
            ),
        ),
        (
            "Set-Cookie mixed case inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"Set-Cookie": "session=1"},
                }
            ),
        ),
        (
            "AuThOrIzAtIoN mixed case inside diagnostic evidence",
            lambda r: r["diagnostics"].append(
                {
                    "code": "CACHE_STATE_UNKNOWN",
                    "severity": "WARNING",
                    "message": "x",
                    "experiment_id": "HTML_COLD",
                    "request_index": 3,
                    "evidence": {"AuThOrIzAtIoN": "Bearer x"},
                }
            ),
        ),
        (
            "cache_status outside enum",
            lambda r: r["observations"][2].update({"cache_status": "MAYBE"}),
        ),
        ("seven observations", lambda r: r["observations"].pop()),
        ("missing verdict", lambda r: r.pop("verdict")),
        ("missing report_hash", lambda r: r.pop("report_hash")),
        ("first_error zero", lambda r: r.update({"first_error": 0})),
        ("scenario_id outside pattern", lambda r: r.update({"scenario_id": "X99"})),
        (
            "unknown request header",
            lambda r: r["input"]["request_headers"].update(
                {"authorization": "Bearer x"}
            ),
        ),
    ],
)
def test_rejected_mutations(name, mutate):
    errors = validate(_mutated(mutate))
    assert errors, f"{name}: expected rejection, got none"


def test_valid_variants_still_pass():
    """Null cache status (baselines), null oracle and non-final
    reports are all schema-valid — the Schema must not over-reject."""
    report = _minimal_valid_report()
    report["oracle"] = None
    report["oracle_parity"] = None
    report["final"] = False
    assert validate(report) == []
    report = _minimal_valid_report()
    report["verdict"] = "INCONCLUSIVE"
    report["diagnostics"] = [
        {
            "code": "CACHE_STATE_UNKNOWN",
            "severity": "WARNING",
            "message": "evidence missing",
            "experiment_id": None,
            "request_index": None,
            "evidence": {"cache_reset_confirmed": False},
        }
    ]
    report["warning_count"] = 1
    assert validate(report) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:18765/doc",
        "http://127.0.0.2:18765/doc",
        "http://127.255.255.255/doc",
        "http://127.0.0.1:65535/doc",
        "http://127.0.0.1:1/doc",
        "http://[::1]:18765/doc",
        "http://[::1]/doc",
        "http://localhost:18765/doc",
        "http://localhost/doc",
    ],
)
def test_valid_loopback_url_variants_still_pass(url):
    """T009-FIX (P2-1): tightening the loopback pattern must not
    over-reject genuine loopback URLs — 127.0.0.1 / 127.0.0.2 /
    [::1] / localhost, at the port boundaries 1 and 65535, all stay
    valid."""
    report = _minimal_valid_report()
    report["input"]["url"] = url
    assert validate(report) == []


# ---------------------------------------------------------------------------
# The 48 committed samples
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sid", SCENARIO_IDS)
def test_all_48_samples_validate_independently(sid):
    path = REPORTS_DIR / f"{sid}.json"
    assert path.exists(), f"missing report sample {path}"
    errors = validate_report_file(path)
    assert errors == [], f"{sid}: {errors}"
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["report_hash"] == _independent_hash(report)
    assert report["oracle_parity"] is True
    assert report["final"] is True
    recorded = json.loads((GOLDEN_DIR / sid / "scenario.json").read_text(encoding="utf-8"))
    assert report["verdict"] == recorded["verdict"]
    assert report["first_error"] == recorded["first_error"]
    assert _forbidden_keys_anywhere(report) == []


@pytest.mark.parametrize("sid", SCENARIO_IDS)
def test_samples_contain_only_loopback_urls(sid):
    report = json.loads((REPORTS_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    urls: list[str] = []

    def walk(value):
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and value.startswith(("http://", "https://")):
            urls.append(value)

    walk(report)
    assert urls, f"{sid}: report carries no URL at all"
    for url in urls:
        parsed = urlsplit(url)
        assert parsed.scheme == "http", f"{sid}: non-http URL {url}"
        host = parsed.hostname or ""
        assert host in ("127.0.0.1", "localhost", "::1") or host.startswith(
            "127."
        ), f"{sid}: non-loopback URL {url}"


@pytest.mark.parametrize("sid", ["C01", "C11", "E22"])
def test_committed_samples_match_generator(sid):
    """Rebuilding a sample from the recorded evidence reproduces
    the committed file byte-for-byte in content (dict equality)."""
    sdir = GOLDEN_DIR / sid
    contract = json.loads((sdir / "contract.json").read_text(encoding="utf-8"))
    raw = json.loads((sdir / "raw-observations.json").read_text(encoding="utf-8"))
    production = json.loads((sdir / "production.json").read_text(encoding="utf-8"))
    oracle = json.loads((sdir / "oracle.json").read_text(encoding="utf-8"))
    observations = []
    for record in raw["observations"]:
        observations.append(
            {
                "request_index": record["request_index"],
                "experiment_id": record["experiment_id"],
                "requested_representation": record["requested_representation"],
                "response_status": record["response_status"],
                "response_content_type": record["response_content_type"],
                "body_sha256": record["body_sha256"],
                "sentinel_match": record["sentinel_match"],
                "cache_status": record.get("verified_cache_state"),
                "cache_key_sha256": record.get("cache_key_sha256"),
                "cache_entry_id": record.get("cache_entry_id"),
                "origin_counter_delta": record["origin_counter_delta"],
            }
        )
    rebuilt = build_report(
        contract, production, oracle, observations=observations, scenario_id=sid
    )
    committed = json.loads((REPORTS_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    assert rebuilt == committed
