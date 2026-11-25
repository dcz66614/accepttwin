"""Unit tests for the formal report builder (P032 T009, §14, §10.4).

Covers the T009 acceptance criteria that belong to the generator:

* report shape (``accepttwin.report/v1``, five frozen verdicts,
  diagnostic severities, counts, first-error passthrough);
* report hash: recomputed independently in-test, repeat-identical,
  and unchanged when only the port changes (ADR-003) or when only
  hash-excluded evidence changes (cache keys, entry ids, absolute
  counters, port-bearing URLs);
* no raw body text and no sensitive header may enter a report, at
  any depth — forbidden content raises instead of being recorded;
* non-loopback ``redirect_target`` is desensitised (§8.6), loopback
  targets are kept;
* Oracle parity (§12.4, §4.2 constraint 6): matching Oracle makes
  the report final; a mismatch or a missing Oracle never does;
* ``canonical_json`` is a thin re-export of the single
  implementation in ``accepttwin.contract`` — no second
  canonicalisation exists;
* the T012 verify entry point (``scripts/run_all_48.run_all``) is
  importable — the CLI itself belongs to T012, not T009.

Schema conformance of the built reports is *not* asserted here:
that is the job of ``tests/unit/test_report_schema.py``, which
validates with the independent checker that shares no code with
this generator.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from accepttwin.canonical_json import (  # noqa: E402
    canonical_contract_hash,
    canonical_json_bytes,
)
from accepttwin.classifier import ClassificationResult  # noqa: E402
from accepttwin.contract import (  # noqa: E402
    canonical_json_bytes as contract_canonical_json_bytes,
)
from accepttwin.contract import load_contract, parse_contract  # noqa: E402
from accepttwin.diagnostics import make_diagnostic  # noqa: E402
from accepttwin.evidence import RequestObservation  # noqa: E402
from accepttwin.report_builder import (  # noqa: E402
    REDACTED_REDIRECT_TARGET,
    REPORT_HASH_EXCLUDED_FIELDS,
    ReportError,
    build_report,
    compute_report_hash,
    report_hash_payload,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "site.json"

_HASH = "ab" * 32
_KEY = "cd" * 32
_ENTRY = "entry-" + "cd" * 8

_FORBIDDEN_KEYS = {
    "body",
    "body_text",
    "response_body",
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
}


def _contract(ports=(18765, 18766)):
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    data["url"] = f"http://127.0.0.1:{ports[0]}/doc"
    data["origin_url"] = f"http://127.0.0.1:{ports[1]}/doc"
    return parse_contract(data)


def _observations(cache_key=_KEY, entry=_ENTRY):
    """Eight §5.5 observations for a healthy C01-shaped run."""
    experiments = [
        ("ORIGIN_HTML", "html", None, 1),
        ("ORIGIN_MARKDOWN", "markdown", None, 1),
        ("HTML_COLD", "html", "MISS", 1),
        ("MARKDOWN_COLD", "markdown", "MISS", 1),
        ("HTML_TO_MARKDOWN", "html", "MISS", 1),
        ("HTML_TO_MARKDOWN", "markdown", "MISS", 1),
        ("MARKDOWN_TO_HTML", "markdown", "MISS", 1),
        ("MARKDOWN_TO_HTML", "html", "MISS", 1),
    ]
    counter = 0
    observations = []
    for index, (experiment_id, rep, cache_status, delta) in enumerate(
        experiments, start=1
    ):
        before = counter
        counter += delta
        content_type = (
            "text/html; charset=utf-8"
            if rep == "html"
            else "text/markdown; charset=utf-8"
        )
        observations.append(
            RequestObservation(
                request_index=index,
                experiment_id=experiment_id,
                requested_representation=rep,
                response_status=200,
                response_content_type=content_type,
                body_sha256=_HASH,
                sentinel_match=True,
                cache_status=cache_status,
                cache_key_sha256=(cache_key if cache_status else None),
                cache_entry_id=(entry if cache_status else None),
                origin_counter_before=before,
                origin_counter_after=counter,
                origin_counter_delta=delta,
            )
        )
    return observations


def _pass_result():
    return ClassificationResult(
        verdict="PASS_OBSERVED",
        diagnostics=(),
        first_error=None,
        first_error_experiment_id=None,
        reasons=(
            "baselines, cold requests and both warm orders are correct "
            "with complete cache evidence and no CRITICAL diagnostic",
        ),
        # T014 (T013-F02): classifier-confirmed states matching
        # _observations() — baselines None (ADR-001), proxied MISS.
        confirmed_cache_states=tuple(_matching_cache_states()),
    )


def _matching_cache_states():
    """Per-request verified states for _observations(): baselines
    carry None (ADR-001), the six proxied requests are MISS (T014,
    T013-F02 — the parity check now compares these)."""
    return [
        {"request_index": 1, "state": None},
        {"request_index": 2, "state": None},
        *[
            {"request_index": index, "state": "MISS"}
            for index in range(3, 9)
        ],
    ]


def _matching_oracle():
    return {
        "verdict": "PASS_OBSERVED",
        "diagnostics": [],
        "first_error": None,
        "first_error_experiment_id": None,
        "reasons": ["oracle agrees"],
        "verified_cache_states": _matching_cache_states(),
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
    """Recompute the report hash without the production helper.

    Same rule as the builder documents (strip the excluded fields,
    drop ``report_hash`` itself), but written out here so the test
    does not just call the code under test and agree with itself.
    """
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

    payload = {
        k: v for k, v in report.items() if k != "report_hash"
    }
    return hashlib.sha256(
        canonical_json_bytes(strip(payload))
    ).hexdigest()


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


def test_report_shape_and_counts():
    report = build_report(
        _contract(),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["schema"] == "accepttwin.report/v1"
    assert report["project"] == {"project_id": "P032", "version": "1.0.1"}
    assert report["scenario_id"] == "C01"
    assert report["verdict"] == "PASS_OBSERVED"
    assert report["first_error"] is None
    assert report["critical_count"] == 0
    assert report["warning_count"] == 0
    assert report["oracle_parity"] is True
    assert report["final"] is True
    assert report["oracle"]["verdict"] == "PASS_OBSERVED"
    assert len(report["observations"]) == 8
    assert [o["request_index"] for o in report["observations"]] == list(range(1, 9))
    assert report["input"]["contract_sha256"] == canonical_contract_hash(
        _contract()
    )
    assert report["input"]["url"] == "http://127.0.0.1:18765/doc"
    assert report["input"]["request_headers"] == {
        "accept_encoding": "identity",
        "user_agent": "AcceptTwin/1.0.0",
        "accept_language": "en",
    }


def test_bleed_report_carries_diagnostics_and_counts():
    diag = make_diagnostic(
        "REPRESENTATION_BLEED",
        "warm-cache request 006 for markdown was served html",
        experiment_id="HTML_TO_MARKDOWN",
        request_index=6,
        evidence={
            "cache_status": "HIT",
            "cache_key_sha256": _KEY,
            "cache_entry_id": _ENTRY,
            "origin_counter_before": 5,
            "origin_counter_after": 5,
            "origin_counter_delta": 0,
            "body_sha256": _HASH,
        },
    )
    result = ClassificationResult(
        verdict="REPRESENTATION_BLEED",
        diagnostics=(diag,),
        first_error=6,
        first_error_experiment_id="HTML_TO_MARKDOWN",
        reasons=["a warm-cache second request was served the other representation"],
        confirmed_cache_states=tuple(_matching_cache_states()),
    )
    oracle = {
        "verdict": "REPRESENTATION_BLEED",
        "diagnostics": [diag.as_dict()],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "verified_cache_states": _matching_cache_states(),
    }
    report = build_report(
        _contract(),
        result,
        oracle,
        observations=_observations(),
        scenario_id="C11",
    )
    assert report["verdict"] == "REPRESENTATION_BLEED"
    assert report["first_error"] == 6
    assert report["first_error_experiment_id"] == "HTML_TO_MARKDOWN"
    assert report["critical_count"] == 1
    assert report["diagnostics"][0]["code"] == "REPRESENTATION_BLEED"
    assert report["oracle_parity"] is True
    assert report["final"] is True


# ---------------------------------------------------------------------------
# Hash: independent recomputation, determinism, port invariance
# ---------------------------------------------------------------------------


def test_report_hash_matches_independent_recomputation():
    report = build_report(
        _contract(),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["report_hash"] == _independent_hash(report)
    assert report["report_hash"] == compute_report_hash(report)


def test_repeat_build_is_identical():
    kwargs = dict(
        observations=_observations(),
        scenario_id="C01",
    )
    first = build_report(_contract(), _pass_result(), _matching_oracle(), **kwargs)
    second = build_report(_contract(), _pass_result(), _matching_oracle(), **kwargs)
    assert first == second
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_port_change_does_not_change_hash():
    """ADR-003: only the OS-assigned ports change — same report hash."""
    base = build_report(
        _contract(ports=(18765, 18766)),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    moved = build_report(
        _contract(ports=(39991, 39992)),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    assert moved["input"]["url"] == "http://127.0.0.1:39991/doc"
    assert moved["report_hash"] == base["report_hash"]
    # …but a semantic change still changes it.
    other_data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    other_data["contract_id"] = "site-example-002"
    changed = build_report(
        parse_contract(other_data),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    assert changed["report_hash"] != base["report_hash"]


def test_hash_excludes_port_derived_and_absolute_evidence():
    """Cache keys, entry ids, absolute counters and port-bearing
    URLs are report evidence, never hash input (§10.4, ADR-003)."""
    diag = make_diagnostic(
        "REPRESENTATION_BLEED",
        "warm-cache request 006 for markdown was served html",
        experiment_id="HTML_TO_MARKDOWN",
        request_index=6,
        evidence={
            "cache_status": "HIT",
            "cache_key_sha256": _KEY,
            "cache_entry_id": _ENTRY,
            "origin_counter_before": 5,
            "origin_counter_after": 5,
            "origin_counter_delta": 0,
            "body_sha256": _HASH,
            "request_url": "http://127.0.0.1:11111/doc",
            "redirect_target": "http://127.0.0.1:22222/doc",
        },
    )
    result = ClassificationResult(
        verdict="REPRESENTATION_BLEED",
        diagnostics=(diag,),
        first_error=6,
        first_error_experiment_id="HTML_TO_MARKDOWN",
        reasons=["bleed"],
        confirmed_cache_states=tuple(_matching_cache_states()),
    )
    oracle = {
        "verdict": "REPRESENTATION_BLEED",
        "diagnostics": [diag.as_dict()],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "verified_cache_states": _matching_cache_states(),
    }
    base = build_report(
        _contract(), result, oracle, observations=_observations(), scenario_id="C11"
    )
    other_key = "ee" * 32
    other_diag = make_diagnostic(
        "REPRESENTATION_BLEED",
        "warm-cache request 006 for markdown was served html",
        experiment_id="HTML_TO_MARKDOWN",
        request_index=6,
        evidence={
            "cache_status": "HIT",
            "cache_key_sha256": other_key,
            "cache_entry_id": "entry-" + "ee" * 8,
            "origin_counter_before": 500,
            "origin_counter_after": 500,
            "origin_counter_delta": 0,
            "body_sha256": _HASH,
            "request_url": "http://127.0.0.1:33333/doc",
            "redirect_target": "http://127.0.0.1:44444/doc",
        },
    )
    other_result = ClassificationResult(
        verdict="REPRESENTATION_BLEED",
        diagnostics=(other_diag,),
        first_error=6,
        first_error_experiment_id="HTML_TO_MARKDOWN",
        reasons=["bleed"],
        confirmed_cache_states=tuple(_matching_cache_states()),
    )
    other_oracle = {
        "verdict": "REPRESENTATION_BLEED",
        "diagnostics": [other_diag.as_dict()],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "verified_cache_states": _matching_cache_states(),
    }
    changed = build_report(
        _contract(),
        other_result,
        other_oracle,
        observations=_observations(cache_key=other_key),
        scenario_id="C11",
    )
    assert changed["report_hash"] == base["report_hash"]
    # The evidence itself is still in the report, just not hashed.
    assert changed["diagnostics"][0]["evidence"]["cache_key_sha256"] == other_key
    assert changed["diagnostics"][0]["evidence"]["origin_counter_before"] == 500
    assert report_hash_payload(changed)["diagnostics"][0]["evidence"] == {
        "cache_status": "HIT",
        "origin_counter_delta": 0,
        "body_sha256": _HASH,
    }


# ---------------------------------------------------------------------------
# Privacy: no body text, no sensitive headers, desensitised redirects
# ---------------------------------------------------------------------------


def test_no_forbidden_keys_anywhere_in_report():
    report = build_report(
        _contract(),
        _pass_result(),
        _matching_oracle(),
        observations=_observations(),
        scenario_id="C01",
    )
    assert _forbidden_keys_anywhere(report) == []


def _dict_diagnostic(code, severity, evidence):
    return {
        "code": code,
        "severity": severity,
        "message": "synthetic diagnostic",
        "experiment_id": "HTML_TO_MARKDOWN",
        "request_index": 6,
        "evidence": evidence,
    }


@pytest.mark.parametrize("key", sorted(_FORBIDDEN_KEYS))
def test_forbidden_evidence_key_is_rejected(key):
    production = {
        "verdict": "CONTRACT_MISMATCH",
        "diagnostics": [
            _dict_diagnostic(
                "CONTRACT_MISMATCH", "CRITICAL", {key: "secret-value"}
            )
        ],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "reasons": ["contract error"],
    }
    with pytest.raises(ReportError):
        build_report(
            _contract(),
            production,
            None,
            observations=_observations(),
            scenario_id="C11",
        )


def test_redirect_target_desensitisation():
    production = {
        "verdict": "INCONCLUSIVE",
        "diagnostics": [
            _dict_diagnostic(
                "INCONCLUSIVE_LIMIT",
                "WARNING",
                {
                    "limit_code": "redirect",
                    "redirect_target": "http://example.com/doc",
                    "request_url": "http://127.0.0.1:38977/doc",
                    "response_status": 301,
                },
            ),
            _dict_diagnostic(
                "INCONCLUSIVE_LIMIT",
                "WARNING",
                {
                    "limit_code": "redirect",
                    "redirect_target": "http://127.0.0.1:36321/doc",
                    "request_url": "http://127.0.0.1:38977/doc",
                    "response_status": 301,
                },
            ),
        ],
        "first_error": 3,
        "first_error_experiment_id": "HTML_COLD",
        "reasons": ["redirect"],
    }
    report = build_report(
        _contract(),
        production,
        None,
        observations=_observations(),
        scenario_id="E22",
    )
    targets = [
        d["evidence"]["redirect_target"] for d in report["diagnostics"]
    ]
    assert targets[0] == REDACTED_REDIRECT_TARGET
    assert targets[1] == "http://127.0.0.1:36321/doc"


# ---------------------------------------------------------------------------
# Oracle parity / final marking (§4.2 constraint 6)
# ---------------------------------------------------------------------------


def test_oracle_mismatch_is_never_final():
    oracle = _matching_oracle()
    oracle["verdict"] = "CONTRACT_MISMATCH"
    report = build_report(
        _contract(),
        _pass_result(),
        oracle,
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["oracle_parity"] is False
    assert report["final"] is False


def test_missing_oracle_is_never_final():
    report = build_report(
        _contract(),
        _pass_result(),
        None,
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["oracle"] is None
    assert report["oracle_parity"] is None
    assert report["final"] is False


def test_cache_state_disagreement_fails_parity_t014():
    """T014 (T013-F02): verdict, diagnostics and first error all
    agree, but one per-request verified cache state differs — the
    old parity check passed this silently; the widened check must
    fail it."""
    oracle = _matching_oracle()
    states = _matching_cache_states()
    states[2] = {"request_index": 3, "state": "HIT"}  # production says MISS
    oracle["verified_cache_states"] = states
    report = build_report(
        _contract(),
        _pass_result(),
        oracle,
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["oracle_parity"] is False
    assert report["final"] is False


def test_oracle_without_cache_states_fails_parity_t014():
    """T014 (T013-F02): an Oracle result without per-request cache
    states fails parity (fail-closed), even when everything else
    agrees."""
    oracle = _matching_oracle()
    del oracle["verified_cache_states"]
    report = build_report(
        _contract(),
        _pass_result(),
        oracle,
        observations=_observations(),
        scenario_id="C01",
    )
    assert report["oracle_parity"] is False
    assert report["final"] is False


# ---------------------------------------------------------------------------
# Fail-closed inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        lambda obs: obs[:7],
        lambda obs: obs + [obs[0]],
        lambda obs: [dict(o, request_index=9) if o["request_index"] == 8 else o for o in obs],
    ],
)
def test_observation_count_and_coverage_are_enforced(mutate):
    observations = mutate(
        [o.as_dict() for o in _observations()]
    )
    with pytest.raises(ReportError):
        build_report(
            _contract(),
            _pass_result(),
            None,
            observations=observations,
            scenario_id="C01",
        )


def test_invalid_verdict_and_diagnostic_are_rejected():
    bad_verdict = {
        "verdict": "MAYBE",
        "diagnostics": [],
        "first_error": None,
        "first_error_experiment_id": None,
        "reasons": [],
    }
    with pytest.raises(ReportError):
        build_report(
            _contract(), bad_verdict, None,
            observations=_observations(), scenario_id="C01",
        )
    bad_diag = {
        "verdict": "CONTRACT_MISMATCH",
        "diagnostics": [
            _dict_diagnostic("NOT_A_CODE", "CRITICAL", {})
        ],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "reasons": [],
    }
    with pytest.raises(ReportError):
        build_report(
            _contract(), bad_diag, None,
            observations=_observations(), scenario_id="C01",
        )
    wrong_severity = {
        "verdict": "CONTRACT_MISMATCH",
        "diagnostics": [
            _dict_diagnostic("CONTRACT_MISMATCH", "WARNING", {})
        ],
        "first_error": 6,
        "first_error_experiment_id": "HTML_TO_MARKDOWN",
        "reasons": [],
    }
    with pytest.raises(ReportError):
        build_report(
            _contract(), wrong_severity, None,
            observations=_observations(), scenario_id="C01",
        )


def test_missing_scenario_id_and_observations_are_rejected():
    with pytest.raises(ReportError):
        build_report(
            _contract(), _pass_result(), None,
            observations=_observations(), scenario_id=None,
        )
    with pytest.raises(ReportError):
        build_report(
            _contract(), _pass_result(), None,
            observations=None, scenario_id="C01",
        )


# ---------------------------------------------------------------------------
# Canonical JSON: single source, thin re-export only
# ---------------------------------------------------------------------------


def test_canonical_json_is_thin_reexport_of_contract():
    import accepttwin.canonical_json as cj

    assert cj.canonical_json_bytes is contract_canonical_json_bytes
    assert cj.canonical_contract_hash is canonical_contract_hash
    source = Path(cj.__file__).read_text(encoding="utf-8")
    assert "def canonical_json_bytes" not in source
    assert "def canonical_contract_hash" not in source
    assert "sort_keys" not in source
    assert "json.dumps" not in source
    assert "single source" in source.lower() or "Single source" in source


# ---------------------------------------------------------------------------
# T012 handoff: the verify entry point is importable (CLI is T012's)
# ---------------------------------------------------------------------------


def test_verify_entry_point_importable_for_t012():
    """``scripts/run_all_48.run_all`` is the importable verify
    function T012's ``verify --suite all`` CLI calls. The CLI entry
    itself (``__main__.py`` / ``cli.py``) belongs to T012: §4.2
    assigns no CLI file to T009, and T012's acceptance requires
    both ``verify`` and ``benchmark`` in one CLI file, so one task
    must own the file — T012. T008 P2-1 therefore stays open after
    T009 and is closed by T012, which flips this test from
    "CLI must not exist yet" to "CLI exists and delegates".
    """
    from run_all_48 import run_all

    assert callable(run_all)
    assert (ROOT / "src" / "accepttwin" / "__main__.py").is_file()
    assert (ROOT / "src" / "accepttwin" / "cli.py").is_file()
    from accepttwin.cli import cmd_benchmark, cmd_verify, main

    assert callable(main) and callable(cmd_verify) and callable(cmd_benchmark)
