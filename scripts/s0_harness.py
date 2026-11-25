"""S0 harness (P032 T007): run one C01-C24 Golden end to end.

Shared by ``scripts/run_s0.py`` and ``tests/golden/test_s0.py`` so the
gate script and the test suite execute exactly the same scenarios.

Per scenario (PROJECT_BOOK §11.2, §6, §10.2):

* a real synthetic origin + a real controlled cache proxy are started
  on OS-assigned loopback ports (``port=0``), a contract is built for
  those URLs, and :func:`accepttwin.experiment_runner.run_experiments`
  performs the frozen 25 steps / 8 real HTTP GETs (001-008). Nothing
  here simulates a request.
* the production classifier is called under the mandatory calling
  convention of ADR-002 Decision 3 (verbatim)::

      classify_run(contract, run.observations, run.origin_events,
                   run.reset_evidence, raw_observations=run.raw_observations)

  with exactly one documented deviation: scenario C21
  (``origin_events_unavailable``) passes ``()`` -- the empty tuple,
  meaning "the journal was checked and found nothing" -- instead of
  ``run.origin_events``. ``None`` is never passed for any of the
  four arguments. The deviation is recorded in the scenario fixture
  and in the per-scenario evidence, and the Oracle receives the same
  empty event list, so production and Oracle judge the same input.

Fault-injection proxies (harness-only subclasses of
:class:`~accepttwin.cache_proxy.ControlledCacheProxy`; production
code in ``src/`` is untouched -- T007 must not modify T002-T006):

* C22 ``proxy_lies_hit_on_warm_second`` -- the 4th proxied GET
  (request 006, HM-2) is served a real HTTP response whose
  ``X-AcceptTwin-Cache-Status`` header says HIT while the origin
  counter moved +1 (the proxy fetched from the origin). Header leg
  and behaviour leg conflict (§8.8).
* C23 ``reset_reports_failure`` -- the first cache reset reports
  ``success=False`` (the store is genuinely empty at that point, so
  ``entries_after`` is honestly 0); no cold-cache claim can then be
  confirmed (§8.4, §11.2 C23).
* C24 ``proxy_rewrites_markdown_content_type`` -- proxied responses
  to Markdown requests return ``Content-Type: text/html`` while the
  body is unchanged; the direct-origin baselines stay correct, so
  the fault is a proxy contract violation, not an origin error
  (§8.3, §11.2 C24).

Extended-Golden injections (P032 T008, same harness-only rule --
production code in ``src/`` is untouched except for the ADR-004
classifier/origin changes the §11.3 shapes themselves require):

* E12 ``proxy_returns_local_redirect`` -- every proxied GET is
  answered ``301`` with ``Location`` pointing at the origin URL
  (loopback); the proxy never contacts the origin. The first release
  does not follow redirects (§8.6, §11.3 E12).
* E22 ``proxy_returns_external_redirect`` -- as E12, but the
  ``Location`` points at ``http://example.com/doc`` (non-loopback);
  following it is forbidden (§8.6, §11.3 E22). The target is a
  synthetic fixture address, never a real user URL.
* E20 ``proxy_lies_miss_with_stash_replay`` -- the 4th proxied GET
  (request 006, HM-2) is served the Markdown body the proxy observed
  at request 004 (kept in a harness-side stash, not the cache store,
  so resets stay honest) without contacting the origin (counter
  delta 0), while the header claims MISS. Header leg and behaviour
  leg conflict (§8.8, §11.3 E20).
* E21 ``proxy_returns_oversize_body`` -- every proxied response body
  is padded past the 1 MiB contract limit (sentinel intact, so the
  only fault is size); the stored entry keeps the original body
  (§8.6, §11.3 E21).
* E23 ``proxy_rewrites_html_content_type`` -- the C24 mirror for
  HTML: proxied responses to HTML requests return ``Content-Type:
  text/markdown`` while the body is unchanged (§8.3, §11.3 E23).
* E24 ``proxy_corrupts_warm_second_sentinel`` -- the warm-second
  responses (requests 006, 008) are returned with their Sentinel
  bytes replaced by a wrong Sentinel; the stored entries keep the
  correct bodies (§8.5, §11.3 E24).
* E17 reuses the ``opaque`` proxy mode (as C20) and E18 reuses the
  ``origin_events_unavailable`` adjudication-input shape (as C21);
  E19 reuses ``proxy_lies_hit_on_warm_second`` (as C22).

Canonical report hash (§10.4): the hashed payload carries only
deterministic fields -- contract hash, scenario id, per-request
(experiment, requested representation, status, Content-Type, body
SHA-256, Sentinel match, verified cache state, origin counter
*delta*), diagnostics (code + request), verdict and first error.
Absolute origin counters, cache keys / entry ids, timestamps,
durations and process ids never enter it. Ports never enter it
either, but only because of an explicit normalisation step, not by
omission: the contract's ``url`` / ``origin_url`` carry OS-assigned
loopback ports (services start with ``port=0``), and
``canonical_contract_hash`` normalises those ports to 0 before
hashing (ADR-003, §10.4 "不包含动态端口"), so two runs of the same
logical contract on different ports hash identically. Execution
still uses the real ports; only the hash input is normalised.
``canonical_json_bytes`` from ``accepttwin.contract`` is the single
canonicalisation implementation (T009 will reuse it; T007 does not
write a second one).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from accepttwin.cache_proxy import (
    ControlledCacheProxy,
    ResetEvidence,
    _entry_id_for,
    cache_key_for,
)
from accepttwin.classifier import ClassificationResult, classify_run
from accepttwin.contract import (
    canonical_json_bytes,
    parse_contract,
)
from accepttwin.experiment_runner import ExperimentRun, run_experiments
from accepttwin.origin_server import SyntheticOrigin

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "s0"
EXTENDED_FIXTURE_DIR = ROOT / "fixtures" / "extended"
CONTRACT_TEMPLATE = ROOT / "contracts" / "site.json"
ORACLE_ENTRY = ROOT / "oracle" / "src" / "index.ts"

SCENARIO_IDS: tuple[str, ...] = tuple(f"C{i:02d}" for i in range(1, 25))
EXTENDED_SCENARIO_IDS: tuple[str, ...] = tuple(f"E{i:02d}" for i in range(1, 25))
ALL_SCENARIO_IDS: tuple[str, ...] = SCENARIO_IDS + EXTENDED_SCENARIO_IDS

#: The mandatory production-classifier call (ADR-002 Decision 3).
#: Kept as a literal string so scripts/verify_s0.py can assert the
#: call site in this file matches it.
MANDATORY_CALL_SNIPPET = (
    "classify_run(contract, run.observations, "
    "adj_origin_events, run.reset_evidence, "
    "raw_observations=run.raw_observations)"
)


# ---------------------------------------------------------------------------
# Fault-injection proxies (harness only, see module docstring)
# ---------------------------------------------------------------------------


class _LyingHitProxy(ControlledCacheProxy):
    """C22: the 4th proxied GET claims HIT while fetching from origin."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._proxied_gets = 0

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        self._proxied_gets += 1
        status, headers, body = super()._serve_once(path_and_query, accept)
        if self._proxied_gets == 4:  # request 006, HM-2
            headers = [
                (name, "HIT") if name.lower() == "x-accepttwin-cache-status"
                else (name, value)
                for name, value in headers
            ]
        return status, headers, body


class _FailingResetProxy(ControlledCacheProxy):
    """C23: the first reset reports failure (store genuinely empty)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._resets = 0

    def reset_cache(self, namespace: str) -> ResetEvidence:
        self._resets += 1
        if self._resets == 1:
            before = self.cache_snapshot().entry_count
            return ResetEvidence(
                namespace=namespace,
                success=False,
                entries_before=before,
                entries_after=before,
                entries_removed=0,
            )
        return super().reset_cache(namespace)


class _RewriteMarkdownContentTypeProxy(ControlledCacheProxy):
    """C24: proxied Markdown responses claim Content-Type text/html."""

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        status, headers, body = super()._serve_once(path_and_query, accept)
        if accept.strip().lower() == "text/markdown":
            headers = [
                (name, "text/html; charset=utf-8")
                if name.lower() == "content-type"
                else (name, value)
                for name, value in headers
            ]
        return status, headers, body


class _LocalRedirectProxy(ControlledCacheProxy):
    """E12: every proxied GET is a 301 to the (loopback) origin URL.

    The origin is never contacted, so the counter does not move; no
    cache headers are emitted, so no cache state can be confirmed.
    """

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        return (
            301,
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Location", str(self.origin_url)),
            ],
            b"301 Moved Permanently\n",
        )


class _ExternalRedirectProxy(ControlledCacheProxy):
    """E22: every proxied GET is a 301 to a non-loopback address.

    The target is a synthetic fixture address (``example.com``), never
    a real user URL; following it is forbidden (§8.6).
    """

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        return (
            301,
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Location", "http://example.com/doc"),
            ],
            b"301 Moved Permanently\n",
        )


class _LyingMissProxy(ControlledCacheProxy):
    """E20: the 4th proxied GET (006, HM-2) claims MISS with delta 0.

    The proxy replays the Markdown body it observed at request 004
    (kept in a harness-side stash, not the cache store, so the reset
    evidence stays honest) without contacting the origin, while the
    header claims MISS. The body is the genuine origin body, so no
    Sentinel or contract diagnostic fires — only the §8.8 conflict.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._proxied_gets = 0
        self._stashed_markdown: bytes | None = None

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        self._proxied_gets += 1
        if self._proxied_gets == 4 and self._stashed_markdown is not None:
            _material, key_sha = cache_key_for(
                self._origin_url_for(path_and_query), accept
            )
            headers = [
                ("Content-Type", "text/markdown; charset=utf-8"),
                ("Vary", "Accept"),
                ("X-AcceptTwin-Cache-Status", "MISS"),
                ("X-AcceptTwin-Cache-Key", key_sha),
                ("X-AcceptTwin-Entry-Id", _entry_id_for(key_sha)),
            ]
            return 200, headers, self._stashed_markdown
        status, headers, body = super()._serve_once(path_and_query, accept)
        if self._proxied_gets == 2 and accept.strip().lower() == "text/markdown":
            self._stashed_markdown = body
        return status, headers, body


class _OversizeBodyProxy(ControlledCacheProxy):
    """E21: every proxied body is padded past the 1 MiB limit.

    The padding is appended after the original body, so the Sentinel
    stays intact and the only fault is size (§8.6 ``body_too_large``).
    The stored entry keeps the original body.
    """

    _TARGET_SIZE = 1048577  # contract max_body_bytes (1 MiB) + 1

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        status, headers, body = super()._serve_once(path_and_query, accept)
        if len(body) < self._TARGET_SIZE:
            body = body + b"x" * (self._TARGET_SIZE - len(body))
        return status, headers, body


class _RewriteHtmlContentTypeProxy(ControlledCacheProxy):
    """E23: proxied HTML responses claim Content-Type text/markdown."""

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        status, headers, body = super()._serve_once(path_and_query, accept)
        if accept.strip().lower() == "text/html":
            headers = [
                (name, "text/markdown; charset=utf-8")
                if name.lower() == "content-type"
                else (name, value)
                for name, value in headers
            ]
        return status, headers, body


class _CorruptWarmSentinelProxy(ControlledCacheProxy):
    """E24: warm-second responses (006, 008) carry a wrong Sentinel.

    The Sentinel bytes in the returned body are replaced; the stored
    entries keep the correct bodies, so the fault is a proxy response
    fault (§8.5), not a bleed (body hashes differ from the first
    requests') and not an origin error (baselines stay correct).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._proxied_gets = 0

    def _serve_once(self, path_and_query: str, accept: str):  # type: ignore[no-untyped-def]
        self._proxied_gets += 1
        status, headers, body = super()._serve_once(path_and_query, accept)
        if self._proxied_gets in (4, 6):  # requests 006, 008
            body = body.replace(
                b"AT_HTML_SENTINEL_001", b"AT_HTML_SENTINEL_999"
            ).replace(
                b"AT_MARKDOWN_SENTINEL_001", b"AT_MARKDOWN_SENTINEL_999"
            )
        return status, headers, body


_INJECTION_PROXIES = {
    "proxy_lies_hit_on_warm_second": _LyingHitProxy,
    "reset_reports_failure": _FailingResetProxy,
    "proxy_rewrites_markdown_content_type": _RewriteMarkdownContentTypeProxy,
    "proxy_returns_local_redirect": _LocalRedirectProxy,
    "proxy_returns_external_redirect": _ExternalRedirectProxy,
    "proxy_lies_miss_with_stash_replay": _LyingMissProxy,
    "proxy_returns_oversize_body": _OversizeBodyProxy,
    "proxy_rewrites_html_content_type": _RewriteHtmlContentTypeProxy,
    "proxy_corrupts_warm_second_sentinel": _CorruptWarmSentinelProxy,
}


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------


def load_scenario(
    scenario_id: str, fixture_dir: str | Path | None = None
) -> dict[str, Any]:
    """Load and return the fixture JSON for *scenario_id*.

    *fixture_dir* defaults to the S0 directory (C01-C24); the
    extended Golden (E01-E24, T008) pass ``EXTENDED_FIXTURE_DIR``.
    """
    path = Path(fixture_dir or FIXTURE_DIR) / f"{scenario_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["scenario_id"] != scenario_id:
        raise ValueError(f"fixture {path} carries id {data['scenario_id']!r}")
    return data


def build_contract(
    proxy_url: str,
    origin_url: str,
    fixture: dict[str, Any],
    contract_prefix: str = "s0",
):
    """Build a validated contract for the live service URLs."""
    data = json.loads(CONTRACT_TEMPLATE.read_text(encoding="utf-8"))
    data["contract_id"] = f"{contract_prefix}-{fixture['scenario_id']}"
    data["name"] = (
        f"{contract_prefix.upper()} {fixture['scenario_id']} "
        f"({fixture['origin_scenario']})"
    )
    data["url"] = proxy_url
    data["origin_url"] = origin_url
    cb = fixture["contract"]
    data["cache_behavior"] = {
        "mode": cb["mode"],
        "vary_accept": cb["vary_accept"],
        "max_age_seconds": cb["max_age_seconds"],
    }
    return parse_contract(data)


@dataclass
class ScenarioOutcome:
    """Everything one scenario execution produced, for gate + tests."""

    scenario_id: str
    fixture: dict[str, Any]
    contract: Any
    run: ExperimentRun
    duration_seconds: float
    production: ClassificationResult
    # Adjudication inputs actually passed to the classifier (C21:
    # origin_events is () by fixture design, never None).
    adj_origin_events: tuple = ()
    report: dict[str, Any] = field(default_factory=dict)
    report_hash: str = ""

    @property
    def diagnostics_projection(self) -> list[dict[str, Any]]:
        """Production diagnostics as sorted {code, request_index} pairs."""
        from accepttwin.diagnostics import diagnostic_order

        pairs = [
            {"code": d.code, "request_index": d.request_index}
            for d in self.production.diagnostics
        ]
        return sorted(
            pairs,
            key=lambda p: (
                p["request_index"] is None,
                p["request_index"] if p["request_index"] is not None else 0,
                diagnostic_order(p["code"]),
            ),
        )


def canonical_report(contract: Any, run: ExperimentRun, result: ClassificationResult, scenario_id: str) -> dict[str, Any]:
    """Deterministic report payload for the §10.4 hash (see docstring)."""
    from accepttwin.contract import canonical_contract_hash

    return {
        "schema": "accepttwin.report/v1",
        "scenario_id": scenario_id,
        "contract_sha256": canonical_contract_hash(contract),
        "observations": [
            {
                "request_index": obs.request_index,
                "experiment_id": obs.experiment_id,
                "requested_representation": obs.requested_representation,
                "response_status": obs.response_status,
                "response_content_type": obs.response_content_type,
                "body_sha256": obs.body_sha256,
                "sentinel_match": obs.sentinel_match,
                "cache_status": obs.cache_status,
                "origin_counter_delta": obs.origin_counter_delta,
            }
            for obs in run.observations
        ],
        "diagnostics": [
            {"code": d.code, "request_index": d.request_index}
            for d in result.diagnostics
        ],
        "verdict": result.verdict,
        "first_error": result.first_error,
        "first_error_experiment_id": result.first_error_experiment_id,
    }


def report_hash(report: dict[str, Any]) -> str:
    """SHA-256 of the Canonical JSON of *report* (§10.4)."""
    return hashlib.sha256(canonical_json_bytes(report)).hexdigest()


def oracle_input_dict(contract: Any, run: ExperimentRun, adj_origin_events: tuple, *, origin_events_available: bool) -> dict[str, Any]:
    """The exact adjudication input the independent Oracle reads.

    Same observations / raw observations / resets as the production
    classifier received; the origin event list is the adjudication
    list (empty for C21, with ``origin_events_available`` false).
    No production verdict or diagnostic ever enters this file (§12.2).
    """
    return {
        "format": "accepttwin.oracle-input/v1",
        "contract": contract.as_dict(),
        "observations": [obs.as_dict() for obs in run.observations],
        "raw_observations": [raw.as_dict() for raw in run.raw_observations],
        "origin_events": [
            {
                "index": ev.index,
                "method": ev.method,
                "path": ev.path,
                "accept": ev.accept,
                "status": ev.status,
            }
            for ev in adj_origin_events
        ],
        "origin_events_available": origin_events_available,
        "resets": [
            {
                "namespace": ev.namespace,
                "success": ev.success,
                "entries_before": ev.entries_before,
                "entries_after": ev.entries_after,
                "entries_removed": ev.entries_removed,
            }
            for ev in run.reset_evidence
        ],
    }


class _Pair:
    """A running (origin, proxy, contract) triple for one scenario."""

    def __init__(
        self, fixture: dict[str, Any], contract_prefix: str = "s0"
    ) -> None:
        self.fixture = fixture
        self.origin = SyntheticOrigin(
            port=0, scenario=fixture["origin_scenario"]
        )
        self.origin.start()
        proxy_cls = ControlledCacheProxy
        injection = fixture.get("injection") or {}
        if injection.get("kind") in _INJECTION_PROXIES:
            proxy_cls = _INJECTION_PROXIES[injection["kind"]]
        self.proxy: ControlledCacheProxy = proxy_cls(
            port=0,
            mode=fixture["proxy_mode"],
            origin_url=self.origin.url,
        )
        self.proxy.start()
        self.contract = build_contract(
            self.proxy.url, self.origin.url, fixture, contract_prefix
        )
        if fixture["contract"]["mode"] == "no_store":
            # The proxy needs the contract to know storage is
            # forbidden; rebuild it bound to the contract (new port).
            self.proxy.stop()
            self.proxy = proxy_cls(
                port=0,
                mode=fixture["proxy_mode"],
                contract=self.contract,
            )
            self.proxy.start()
            self.contract = build_contract(
                self.proxy.url, self.origin.url, fixture, contract_prefix
            )

    def __enter__(self) -> "_Pair":
        return self

    def __exit__(self, *exc: object) -> bool:
        self.proxy.stop()
        self.origin.stop()
        return False


def run_scenario(
    scenario_id: str,
    *,
    pair: _Pair | None = None,
    namespace_prefix: str | None = None,
    fixture_dir: str | Path | None = None,
    contract_prefix: str = "s0",
) -> ScenarioOutcome:
    """Execute one S0/extended scenario end to end (real HTTP) and classify it.

    *fixture_dir* / *contract_prefix* default to the S0 Golden
    (``fixtures/s0/``, ``"s0"``); the extended Golden (T008) pass
    ``EXTENDED_FIXTURE_DIR`` / ``"ext"``. When *pair* is supplied,
    the run reuses those live services (used by the supplementary
    same-pair determinism check); otherwise a fresh pair is started
    for this scenario only -- the repeat-100 gate runs each iteration
    on a fresh pair with fresh OS-assigned ports, so a port-dependent
    hash cannot pass it (ADR-003).
    """
    fixture = load_scenario(scenario_id, fixture_dir)
    own_pair = pair is None
    if pair is None:
        pair = _Pair(fixture, contract_prefix)
    try:
        contract = pair.contract
        injection = fixture.get("injection") or {}
        started = time.perf_counter()
        run = run_experiments(
            contract,
            origin=pair.origin,
            proxy=pair.proxy,
            scenario=fixture["origin_scenario"],
            proxy_mode=fixture["proxy_mode"],
            namespace_prefix=namespace_prefix or f"s0-{scenario_id}",
        )
        duration = time.perf_counter() - started
        # Adjudication inputs (ADR-002 Decision 3). C21 passes the
        # empty tuple -- checked, found nothing -- never None.
        adj_origin_events: tuple = (
            () if injection.get("kind") == "origin_events_unavailable"
            else run.origin_events
        )
        # Mandatory call (ADR-002 Decision 3, verbatim argument
        # roles): real tuples, never None; raw_observations always.
        production = classify_run(contract, run.observations, adj_origin_events, run.reset_evidence, raw_observations=run.raw_observations)
        report = canonical_report(contract, run, production, scenario_id)
        return ScenarioOutcome(
            scenario_id=scenario_id,
            fixture=fixture,
            contract=contract,
            run=run,
            duration_seconds=duration,
            production=production,
            adj_origin_events=adj_origin_events,
            report=report,
            report_hash=report_hash(report),
        )
    finally:
        if own_pair:
            pair.proxy.stop()
            pair.origin.stop()


def make_pair(
    scenario_id: str,
    fixture_dir: str | Path | None = None,
    contract_prefix: str = "s0",
) -> _Pair:
    """Start a reusable (origin, proxy, contract) pair for *scenario_id*."""
    return _Pair(load_scenario(scenario_id, fixture_dir), contract_prefix)


# ---------------------------------------------------------------------------
# Independent Oracle invocation + parity (§12.4)
# ---------------------------------------------------------------------------


def run_oracle(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    """Run the independent TypeScript Oracle on *input_path*.

    The Oracle is a separate Node.js process reading only the
    oracle-input file; it never sees a production verdict (§12.3).
    Returns the Oracle result dict it wrote to *output_path*.
    """
    import subprocess

    proc = subprocess.run(
        [
            "node",
            str(ORACLE_ENTRY),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"oracle failed (exit {proc.returncode}): "
            f"{proc.stdout.strip()} {proc.stderr.strip()}"
        )
    return json.loads(Path(output_path).read_text(encoding="utf-8"))


def oracle_projection(oracle_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Oracle diagnostics as sorted {code, request_index} pairs."""
    from accepttwin.diagnostics import diagnostic_order

    pairs = [
        {"code": d["code"], "request_index": d["request_index"]}
        for d in oracle_result["diagnostics"]
    ]
    return sorted(
        pairs,
        key=lambda p: (
            p["request_index"] is None,
            p["request_index"] if p["request_index"] is not None else 0,
            diagnostic_order(p["code"]),
        ),
    )


def production_cache_states(outcome: ScenarioOutcome) -> list[dict[str, Any]]:
    """Per-request verified cache states, normalised for parity.

    These are the states the production *classifier* was willing to
    trust (``ClassificationResult.confirmed_cache_states``, T014 /
    T013-F02) — NOT the runner's observation-layer states: the
    classifier downgrades observation states it cannot confirm
    (e.g. C21, where the adjudication origin-event list is empty,
    so every proxied state is unconfirmed even though the runner
    verified them against its own live event log). ``None`` means
    "confirmed nothing" (baselines per ADR-001, or unconfirmed).
    """
    states = []
    for entry in sorted(
        outcome.production.confirmed_cache_states,
        key=lambda e: e["request_index"],
    ):
        state = entry.get("state")
        if state == "CACHE_STATE_UNKNOWN":
            state = None
        states.append({"request_index": entry["request_index"], "state": state})
    return states


def _normalise_oracle_cache_states(value: Any) -> list[dict[str, Any]] | None:
    """Normalise an Oracle ``verified_cache_states`` value, or None
    when it is not a well-formed 8-entry list (fail-closed: the
    caller treats None as a mismatch)."""
    if not isinstance(value, list) or len(value) != 8:
        return None
    states = []
    for entry in value:
        if not isinstance(entry, dict):
            return None
        index = entry.get("request_index")
        state = entry.get("state")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 1
            or index > 8
            or (state is not None and state not in ("MISS", "HIT", "BYPASS"))
        ):
            return None
        states.append({"request_index": index, "state": state})
    states.sort(key=lambda s: s["request_index"])
    if [s["request_index"] for s in states] != list(range(1, 9)):
        return None
    return states


def check_parity(outcome: ScenarioOutcome, oracle_result: dict[str, Any]) -> dict[str, Any]:
    """Compare production vs Oracle per §12.4 (verdict, diagnostics,
    first error, and — since T014 / T013-F02 — the per-request
    verified MISS/HIT/BYPASS states). Returns {"parity": bool,
    "mismatches": [...]}."""
    mismatches: list[str] = []
    if oracle_result["verdict"] != outcome.production.verdict:
        mismatches.append(
            f"verdict: production={outcome.production.verdict} "
            f"oracle={oracle_result['verdict']}"
        )
    if oracle_projection(oracle_result) != outcome.diagnostics_projection:
        mismatches.append(
            "diagnostics: production="
            f"{json.dumps(outcome.diagnostics_projection)} oracle="
            f"{json.dumps(oracle_projection(oracle_result))}"
        )
    if oracle_result["first_error"] != outcome.production.first_error:
        mismatches.append(
            f"first_error: production={outcome.production.first_error} "
            f"oracle={oracle_result['first_error']}"
        )
    if (
        oracle_result["first_error_experiment_id"]
        != outcome.production.first_error_experiment_id
    ):
        mismatches.append(
            "first_error_experiment_id: production="
            f"{outcome.production.first_error_experiment_id} oracle="
            f"{oracle_result['first_error_experiment_id']}"
        )
    oracle_states = _normalise_oracle_cache_states(
        oracle_result.get("verified_cache_states")
    )
    production_states = production_cache_states(outcome)
    if oracle_states is None:
        mismatches.append(
            "verified_cache_states: oracle result has no well-formed "
            "per-request cache states (expected 8 entries, requests "
            "001-008)"
        )
    elif oracle_states != production_states:
        mismatches.append(
            "verified_cache_states: production="
            f"{json.dumps(production_states)} oracle="
            f"{json.dumps(oracle_states)}"
        )
    return {"parity": not mismatches, "mismatches": mismatches}
