"""Four-experiment runner (P032 T005).

Implements IMPLEMENTATION_PLAN §6 / T005 and PROJECT_BOOK §6, §7,
§10.2 (steps 01-25, frozen order), §5.3 (dual cache evidence) and
§5.4 (cold / warm definitions).

Frozen execution order (§10.2) — never reordered, never shortened:

    01 ValidateContract
    02 ValidateLoopbackTargets
    03 StartSyntheticOrigin
    04 StartControlledCacheProxy
    05 VerifyLocalPorts
    06 CaptureOriginCounterBaseline
    07 DirectOriginHTML            (request 001, O-H)
    08 DirectOriginMarkdown        (request 002, O-M)
    09 ResetCache
    10 VerifyCacheEmpty
    11 HTMLColdRequest             (request 003, H-COLD)
    12 VerifyMissOrBypass
    13 ResetCache
    14 VerifyCacheEmpty
    15 MarkdownColdRequest         (request 004, M-COLD)
    16 VerifyMissOrBypass
    17 ResetCache
    18 VerifyCacheEmpty
    19 HTMLWarmFirst               (request 005, HM-1)
    20 MarkdownWarmSecond          (request 006, HM-2)
    21 VerifyCacheEvidence
    22 ResetCache
    23 VerifyCacheEmpty
    24 MarkdownWarmFirst           (request 007, MH-1)
    25 HTMLWarmSecond              (request 008, MH-2)

Constraints enforced by construction, not by convention (§6.2):

* the four experiments are independently reset (steps 09, 13, 17,
  22 — the only resets in the run);
* no reset happens between steps 19-20 or between steps 24-25;
* all eight requests use one URL string per leg (the contract's
  ``url`` through the proxy, ``origin_url`` direct) — the second
  representation never gets a different URL;
* every request is a real HTTP GET over loopback (see
  :func:`_http_get`).

Proxy isolation (T002 review P2-03, hard requirement of this task
card): the HTTP client is :mod:`http.client` used directly. It never
consults ``HTTP_PROXY`` / ``HTTPS_PROXY`` / ``NO_PROXY`` or any other
environment variable, and this module never reads the process
environment at all. (``urllib`` is deliberately not used: its
default opener honours proxy environment variables.)

Evidence failures never abort the run: a failed ``Verify*`` step, a
failed reset, or a transport error is recorded in the step log /
``verification_failures`` and the run continues collecting evidence
(PROJECT_BOOK §6.3 / §11.2 C07-C08: later requests still run so the
first error can be located, not masked). Only hard infrastructure
failures — an invalid contract, a non-loopback target, a service
that does not listen (step 05), or a supplied origin/proxy that
disagrees with the contract — raise :class:`ExperimentError`
before / instead of producing observations.
"""

from __future__ import annotations

import hashlib
import http.client
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .cache_evidence import (
    CACHE_STATE_UNKNOWN,
    BehaviorEvidence,
    CacheEvidenceResult,
    HeaderEvidence,
    verify_cache_state,
)
from .cache_proxy import ControlledCacheProxy, ResetEvidence
from .contract import (
    Contract,
    canonical_contract_hash,
    load_contract,
    parse_contract,
    validate_contract,
)
from .evidence import (
    RAW_OBSERVATIONS_FORMAT,
    RawObservation,
    RequestObservation,
    sentinel_sha256,
    write_evidence_file,
)
from .origin_server import OriginEvent, SyntheticOrigin
from .privacy import MAX_BODY_BYTES, read_http_body_bounded
from .request_headers import build_request_headers
from .url_guard import URLGuardError, validate_loopback_url

__all__ = [
    "EXPERIMENT_IDS",
    "STEP_NAMES",
    "ExperimentError",
    "ExperimentRun",
    "StepRecord",
    "run_experiments",
]

#: The 25 frozen step names of PROJECT_BOOK §10.2, in order.
STEP_NAMES: tuple[str, ...] = (
    "ValidateContract",
    "ValidateLoopbackTargets",
    "StartSyntheticOrigin",
    "StartControlledCacheProxy",
    "VerifyLocalPorts",
    "CaptureOriginCounterBaseline",
    "DirectOriginHTML",
    "DirectOriginMarkdown",
    "ResetCache",
    "VerifyCacheEmpty",
    "HTMLColdRequest",
    "VerifyMissOrBypass",
    "ResetCache",
    "VerifyCacheEmpty",
    "MarkdownColdRequest",
    "VerifyMissOrBypass",
    "ResetCache",
    "VerifyCacheEmpty",
    "HTMLWarmFirst",
    "MarkdownWarmSecond",
    "VerifyCacheEvidence",
    "ResetCache",
    "VerifyCacheEmpty",
    "MarkdownWarmFirst",
    "HTMLWarmSecond",
)

#: Experiment ids (§6.3, §4.3) keyed by request number 001-008.
EXPERIMENT_IDS: dict[int, str] = {
    1: "ORIGIN_HTML",
    2: "ORIGIN_MARKDOWN",
    3: "HTML_COLD",
    4: "MARKDOWN_COLD",
    5: "HTML_TO_MARKDOWN",
    6: "HTML_TO_MARKDOWN",
    7: "MARKDOWN_TO_HTML",
    8: "MARKDOWN_TO_HTML",
}

#: Request numbers of the warm-cache second requests (§6.3).
_WARM_SECOND_REQUESTS = (6, 8)

#: Reset namespaces, one per experiment (§6.2: four independent resets).
_RESET_NAMESPACES = (
    "html-cold",
    "markdown-cold",
    "html-to-markdown",
    "markdown-to-html",
)


class ExperimentError(ValueError):
    """Raised for hard infrastructure failures (invalid contract,
    non-loopback target, service not listening, supplied services
    disagreeing with the contract). Evidence failures never raise."""


@dataclass(frozen=True)
class StepRecord:
    """One executed §10.2 step: its frozen position, name, outcome,
    and a short human-readable detail. ``ok=False`` means the step's
    own check failed (e.g. a reset left entries behind, or a cold
    request was not MISS/BYPASS) — the run still continued."""

    step: int
    name: str
    ok: bool
    detail: str = ""


@dataclass
class ExperimentRun:
    """The complete result of one frozen four-experiment run.

    ``observations`` are the §5.5 :class:`RequestObservation` objects
    (001-008, in execution order); ``raw_observations`` are the
    richer records written to the evidence file. ``origin_events``
    are the origin events recorded during the run only (from the
    step-06 baseline onward). ``verification_failures`` lists every
    failed ``Verify*`` / reset check, in step order.
    """

    contract_id: str
    contract_sha256: str
    scenario_id: str
    proxy_mode: str
    observations: tuple[RequestObservation, ...] = ()
    raw_observations: tuple[RawObservation, ...] = ()
    reset_evidence: tuple[ResetEvidence, ...] = ()
    step_log: tuple[StepRecord, ...] = ()
    cache_verifications: tuple[CacheEvidenceResult | None, ...] = ()
    """Dual-evidence results aligned with ``raw_observations`` by
    position: ``None`` for the two direct-origin requests (001-002),
    a :class:`CacheEvidenceResult` for each proxied request."""
    origin_events: tuple[OriginEvent, ...] = ()
    origin_counter_baseline: int = 0
    origin_counter_final: int = 0
    verification_failures: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Deterministic evidence dict (no timestamps, no body text,
        no volatile fields) — the raw-observations file content."""
        return {
            "format": RAW_OBSERVATIONS_FORMAT,
            "contract_id": self.contract_id,
            "contract_sha256": self.contract_sha256,
            "scenario_id": self.scenario_id,
            "proxy_mode": self.proxy_mode,
            "steps": [
                {
                    "step": rec.step,
                    "name": rec.name,
                    "ok": rec.ok,
                    "detail": rec.detail,
                }
                for rec in self.step_log
            ],
            "observations": [raw.as_dict() for raw in self.raw_observations],
            "resets": [
                {
                    "namespace": ev.namespace,
                    "success": ev.success,
                    "entries_before": ev.entries_before,
                    "entries_after": ev.entries_after,
                    "entries_removed": ev.entries_removed,
                }
                for ev in self.reset_evidence
            ],
            "cache_verifications": [
                {
                    "request_index": raw.request_index,
                    "state": result.state,
                    "header_status": result.header_status,
                    "verified": result.verified,
                    "reasons": list(result.reasons),
                }
                for raw, result in zip(
                    self.raw_observations, self.cache_verifications
                )
                if result is not None
            ],
            "origin_events": [
                {
                    "index": ev.index,
                    "method": ev.method,
                    "path": ev.path,
                    "accept": ev.accept,
                    "status": ev.status,
                }
                for ev in self.origin_events
            ],
            "origin_counter_baseline": self.origin_counter_baseline,
            "origin_counter_final": self.origin_counter_final,
            "verification_failures": list(self.verification_failures),
        }

    def write_evidence(self, path: str | Path) -> Path:
        """Write the raw-observations file for T006 / T007."""
        return write_evidence_file(path, self.as_dict())


# ---------------------------------------------------------------------------
# HTTP client — http.client direct, proxy environment never consulted
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HttpGetResult:
    """One real GET's outcome (T014: bounded read, T011 F-01).

    *body* is the retained prefix only — at most ``max_body + 1``
    bytes — while *body_size* / *body_sha256* / *sentinel_match*
    are exact over the whole streamed response (see
    :func:`accepttwin.privacy.read_http_body_bounded`). A caller
    must use these fields, never re-derive size/hash from *body*:
    for an oversize body they differ (the prefix hash is not the
    stream hash).
    """

    status: int
    headers: dict[str, str]
    body: bytes
    body_size: int
    body_sha256: str
    sentinel_match: bool


def _http_get(
    url: str,
    representation: str,
    timeout: float,
    *,
    max_body: int = MAX_BODY_BYTES,
    sentinel: bytes = b"",
) -> HttpGetResult:
    """One real GET over loopback with the fixed header set (§5.1.3).

    Uses :class:`http.client.HTTPConnection` directly: it opens a TCP
    connection to the URL's own host/port and never reads
    ``HTTP_PROXY`` / ``HTTPS_PROXY`` / ``NO_PROXY`` (or any other
    environment variable). No redirects are followed (§0.2 item 6):
    whatever status the server returns is the observation.

    The response body is read with
    :func:`accepttwin.privacy.read_http_body_bounded`: at most
    ``max_body + 1`` bytes are retained, so a faulty origin can no
    longer force an unbounded allocation (T011 F-01); the exact
    total size, whole-stream SHA-256 and Sentinel presence are
    still measured over the full stream.
    """
    split = urlsplit(url)
    if split.scheme.lower() != "http" or not split.hostname:
        raise ExperimentError(f"cannot GET non-loopback-HTTP URL {url!r}")
    path = split.path or "/"
    if split.query:
        path += f"?{split.query}"
    headers = build_request_headers(representation)
    conn = http.client.HTTPConnection(
        split.hostname, split.port or 80, timeout=float(timeout)
    )
    try:
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        body, body_size, body_sha256, sentinel_match = (
            read_http_body_bounded(resp, max_body, sentinel=sentinel)
        )
        return HttpGetResult(
            status=resp.status,
            headers={k.lower(): v for k, v in resp.getheaders()},
            body=body,
            body_size=body_size,
            body_sha256=body_sha256,
            sentinel_match=sentinel_match,
        )
    finally:
        conn.close()


def _check_port_listening(host: str, port: int, timeout: float = 2.0) -> bool:
    """True when a TCP connect to *(host, port)* succeeds (§10.2 step 05)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Contract loading
# ---------------------------------------------------------------------------


def _coerce_contract(contract: Contract | str | Path | dict) -> Contract:
    if isinstance(contract, Contract):
        return contract
    if isinstance(contract, dict):
        return parse_contract(contract)
    return load_contract(contract)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class _Runner:
    """Internal state for one run; the frozen step order is the literal
    order of statements in :meth:`execute` — nothing reorders it."""

    def __init__(
        self,
        contract: Contract,
        *,
        origin: SyntheticOrigin | None,
        proxy: ControlledCacheProxy | None,
        scenario: str,
        proxy_mode: str,
        namespace_prefix: str,
    ) -> None:
        self.contract = contract
        self.supplied_origin = origin
        self.supplied_proxy = proxy
        self.scenario = scenario
        self.proxy_mode = proxy_mode
        self.namespace_prefix = namespace_prefix
        self.origin: SyntheticOrigin | None = None
        self.proxy: ControlledCacheProxy | None = None
        self._own_origin = False
        self._own_proxy = False
        self.step_log: list[StepRecord] = []
        self.observations: list[RequestObservation] = []
        self.raw_observations: list[RawObservation] = []
        self.resets: list[ResetEvidence] = []
        self.verifications: list[CacheEvidenceResult | None] = []
        self.failures: list[str] = []
        self.baseline_total = 0
        self._timeout = float(
            contract.limits.get("request_timeout_seconds", 5.0)
        )
        self._max_body = int(contract.limits.get("max_body_bytes", 1048576))

    # -- step bookkeeping -------------------------------------------------

    def _step(self, number: int, ok: bool, detail: str = "") -> None:
        assert STEP_NAMES[number - 1]  # step numbers are 1-based, frozen
        self.step_log.append(
            StepRecord(step=number, name=STEP_NAMES[number - 1], ok=ok, detail=detail)
        )
        if not ok:
            self.failures.append(f"step {number:02d} {STEP_NAMES[number - 1]}: {detail}")

    # -- one request ------------------------------------------------------

    def _do_request(
        self,
        number: int,
        representation: str,
        *,
        via_proxy: bool,
    ) -> RawObservation:
        assert self.origin is not None and self.proxy is not None
        rep = self.contract.representations[representation]
        url = self.contract.url if via_proxy else self.contract.origin_url
        before_counter = self.origin.counter_snapshot().total_requests
        before_events = self.origin.event_log()
        before_snapshot = self.proxy.cache_snapshot()
        before_ids = {e.entry_id for e in before_snapshot.entries}

        transport_error: str | None = None
        try:
            result = _http_get(
                url,
                representation,
                self._timeout,
                max_body=self._max_body,
                sentinel=rep.sentinel.encode("utf-8"),
            )
            status, headers = result.status, result.headers
            # Exact whole-stream measurements (T014): for an oversize
            # body these differ from anything derived from the
            # retained prefix — never recompute them from result.body.
            body_hash = result.body_sha256
            body_size = result.body_size
            sentinel_match = result.sentinel_match
        except Exception as exc:  # noqa: BLE001 - recorded, run continues
            status, headers = 0, {}
            body_hash = hashlib.sha256(b"").hexdigest()
            body_size = 0
            sentinel_match = False
            transport_error = f"{type(exc).__name__}: {exc}"

        after_counter = self.origin.counter_snapshot().total_requests
        after_events = self.origin.event_log()
        after_snapshot = self.proxy.cache_snapshot()
        after_ids = {e.entry_id for e in after_snapshot.entries}
        new_events = after_events[len(before_events):]
        event_present = any(
            ev.accept == rep.accept and ev.status == status for ev in new_events
        )
        content_type = headers.get("content-type", "")
        cache_status_header = headers.get("x-accepttwin-cache-status")
        cache_key = headers.get("x-accepttwin-cache-key")
        entry_id = headers.get("x-accepttwin-entry-id")

        verified_state: str | None = None
        verification: CacheEvidenceResult | None = None
        reasons: tuple[str, ...] = ()
        if via_proxy:
            stored = None
            if entry_id is not None:
                for entry in after_snapshot.entries:
                    if entry.entry_id == entry_id:
                        stored = entry
                        break
            behavior = BehaviorEvidence(
                origin_counter_delta=after_counter - before_counter,
                origin_event_present=event_present,
                entry_created=(
                    entry_id is not None
                    and entry_id not in before_ids
                    and entry_id in after_ids
                ),
                entry_id_matches=stored is not None,
                body_hash_matches=(
                    stored is not None and stored.body_sha256 == body_hash
                ),
                entry_count_delta=(
                    after_snapshot.entry_count - before_snapshot.entry_count
                ),
            )
            verification = verify_cache_state(
                HeaderEvidence(
                    status=cache_status_header,
                    cache_key_sha256=cache_key,
                    entry_id=entry_id,
                ),
                behavior,
            )
            verified_state = verification.state
            reasons = verification.reasons

        raw = RawObservation(
            request_index=number,
            experiment_id=EXPERIMENT_IDS[number],
            requested_representation=representation,
            method="GET",
            url=url,
            accept=rep.accept,
            response_status=status,
            response_content_type=content_type,
            body_sha256=body_hash,
            body_size=body_size,
            sentinel_match=sentinel_match,
            sentinel_sha256=sentinel_sha256(rep.sentinel),
            response_headers=dict(headers),
            cache_status_header=cache_status_header,
            cache_key_sha256=cache_key,
            cache_entry_id=entry_id,
            verified_cache_state=verified_state,
            cache_verification_reasons=reasons,
            cache_entry_count_before=(
                before_snapshot.entry_count if via_proxy else None
            ),
            cache_entry_count_after=(
                after_snapshot.entry_count if via_proxy else None
            ),
            origin_counter_before=before_counter,
            origin_counter_after=after_counter,
            origin_counter_delta=after_counter - before_counter,
            origin_event_present=event_present,
            transport_error=transport_error,
        )
        self.raw_observations.append(raw)
        self.observations.append(raw.to_request_observation())
        self.verifications.append(verification)
        return raw

    # -- reset + verify helpers -------------------------------------------

    def _reset(self, step_number: int, namespace: str) -> bool:
        assert self.proxy is not None
        evidence = self.proxy.reset_cache(namespace)
        self.resets.append(evidence)
        empty = self.proxy.cache_snapshot().entry_count == 0
        ok = bool(evidence.success and empty)
        self._step(
            step_number,
            ok,
            f"namespace={namespace} entries_before={evidence.entries_before} "
            f"entries_after={evidence.entries_after} empty={empty}",
        )
        return ok

    def _verify_empty(self, step_number: int) -> bool:
        assert self.proxy is not None
        count = self.proxy.cache_snapshot().entry_count
        ok = count == 0
        self._step(step_number, ok, f"entry_count={count}")
        return ok

    def _verify_miss_or_bypass(self, step_number: int, number: int) -> bool:
        raw = self.raw_observations[number - 1]
        ok = raw.verified_cache_state in ("MISS", "BYPASS")
        detail = (
            f"request={number:03d} verified_cache_state="
            f"{raw.verified_cache_state} header={raw.cache_status_header}"
        )
        self._step(step_number, ok, detail)
        return ok

    def _verify_cache_evidence(self, step_number: int, first: int, second: int) -> bool:
        first_raw = self.raw_observations[first - 1]
        second_raw = self.raw_observations[second - 1]
        ok = (
            first_raw.verified_cache_state in ("MISS", "HIT", "BYPASS")
            and second_raw.verified_cache_state in ("MISS", "HIT", "BYPASS")
        )
        detail = (
            f"requests={first:03d}/{second:03d} first="
            f"{first_raw.verified_cache_state} second="
            f"{second_raw.verified_cache_state}"
        )
        self._step(step_number, ok, detail)
        return ok

    # -- frozen execution ---------------------------------------------------

    def execute(self) -> ExperimentRun:
        contract = self.contract

        # 01 ValidateContract
        result = validate_contract(contract)
        if not result.ok:
            raise ExperimentError(
                "contract failed validation: " + "; ".join(result.errors)
            )
        self._step(1, True, f"contract_id={contract.contract_id}")

        # 02 ValidateLoopbackTargets
        try:
            validated_url = validate_loopback_url(contract.url)
            validated_origin = validate_loopback_url(contract.origin_url)
        except URLGuardError as exc:
            raise ExperimentError(f"loopback guard failed: {exc}") from exc
        self._step(
            2,
            True,
            f"url={validated_url.url} origin_url={validated_origin.url}",
        )

        # 03 StartSyntheticOrigin
        if self.supplied_origin is not None:
            self.origin = self.supplied_origin
            if self.origin.url != contract.origin_url:
                raise ExperimentError(
                    f"supplied origin url {self.origin.url!r} disagrees with "
                    f"contract origin_url {contract.origin_url!r}"
                )
        else:
            self.origin = SyntheticOrigin(contract=contract, scenario=self.scenario)
            self._own_origin = True
        if not self.origin.is_running:
            self.origin.start()
        self._step(3, True, f"origin={self.origin.url} scenario={self.origin.scenario_id}")

        # 04 StartControlledCacheProxy
        if self.supplied_proxy is not None:
            self.proxy = self.supplied_proxy
            if self.proxy.url != contract.url:
                raise ExperimentError(
                    f"supplied proxy url {self.proxy.url!r} disagrees with "
                    f"contract url {contract.url!r}"
                )
            # Fail-closed (T005 review P2-4): a supplied proxy must
            # run in the mode the run was asked to use. Before this
            # check, ``proxy_mode`` was silently ignored whenever a
            # proxy was supplied, so a run could proceed under a
            # different proxy mode than its caller declared. Note
            # the two mode vocabularies differ — proxy modes (§10.3:
            # ``respect_vary`` / ``force_uri_only`` / ...) versus
            # contract ``cache_behavior.mode`` (§5.2:
            # ``variant_by_accept`` / ``no_store``) — so the check
            # is against the run's declared ``proxy_mode`` (default
            # ``"respect_vary"``), not a string equality against the
            # contract mode, which is undefined across vocabularies.
            # Fault-injection modes (``force_uri_only``,
            # ``ignore_no_store``) are *supposed* to run against a
            # ``variant_by_accept`` / ``no_store`` contract so the
            # runner can observe and verdict the bleed/mismatch
            # (PROJECT_BOOK §11 C11–C16, C19); such a run must
            # declare its mode explicitly via ``proxy_mode``.
            if self.proxy.mode != self.proxy_mode:
                raise ExperimentError(
                    f"supplied proxy mode {self.proxy.mode!r} disagrees "
                    f"with requested proxy_mode {self.proxy_mode!r} "
                    f"(contract cache_behavior.mode "
                    f"{contract.cache_behavior.get('mode')!r})"
                )
        else:
            # ControlledCacheProxy takes its origin URL and cache
            # behaviour from the contract, but NOT its bind port
            # (T004 design): pass the contract url's host/port
            # explicitly so the proxy listens where the contract says.
            self.proxy = ControlledCacheProxy(
                contract=contract,
                mode=self.proxy_mode,
                host=validated_url.host,
                port=validated_url.port,
            )
            self._own_proxy = True
        if not self.proxy.is_running:
            self.proxy.start()
        self._step(
            4, True, f"proxy={self.proxy.url} mode={self.proxy.mode}"
        )

        try:
            # 05 VerifyLocalPorts
            origin_ok = _check_port_listening(
                validated_origin.host, validated_origin.port
            )
            proxy_ok = _check_port_listening(
                validated_url.host, validated_url.port
            )
            if not (origin_ok and proxy_ok):
                raise ExperimentError(
                    "local ports not listening: origin="
                    f"{validated_origin.host}:{validated_origin.port} ok={origin_ok}, "
                    f"proxy={validated_url.host}:{validated_url.port} ok={proxy_ok}"
                )
            self._step(
                5,
                True,
                f"origin={validated_origin.host}:{validated_origin.port} "
                f"proxy={validated_url.host}:{validated_url.port}",
            )

            # 06 CaptureOriginCounterBaseline
            assert self.origin is not None
            self.baseline_total = self.origin.counter_snapshot().total_requests
            self._step(6, True, f"origin_counter_baseline={self.baseline_total}")

            # 07 DirectOriginHTML (001) — direct, never via the proxy.
            raw = self._do_request(1, "html", via_proxy=False)
            self._step(
                7,
                raw.transport_error is None,
                f"status={raw.response_status} sentinel_match={raw.sentinel_match}",
            )

            # 08 DirectOriginMarkdown (002).
            raw = self._do_request(2, "markdown", via_proxy=False)
            self._step(
                8,
                raw.transport_error is None,
                f"status={raw.response_status} sentinel_match={raw.sentinel_match}",
            )

            # 09-12 Experiment 1: HTML independent cold request.
            self._reset(9, f"{self.namespace_prefix}-{_RESET_NAMESPACES[0]}")
            self._verify_empty(10)
            raw = self._do_request(3, "html", via_proxy=True)
            self._step(
                11,
                raw.transport_error is None,
                f"status={raw.response_status} cache={raw.verified_cache_state}",
            )
            self._verify_miss_or_bypass(12, 3)

            # 13-16 Experiment 2: Markdown independent cold request.
            self._reset(13, f"{self.namespace_prefix}-{_RESET_NAMESPACES[1]}")
            self._verify_empty(14)
            raw = self._do_request(4, "markdown", via_proxy=True)
            self._step(
                15,
                raw.transport_error is None,
                f"status={raw.response_status} cache={raw.verified_cache_state}",
            )
            self._verify_miss_or_bypass(16, 4)

            # 17-21 Experiment 3: HTML -> Markdown warm cache.
            # No reset between steps 19 and 20 (§6.2 / §10.2).
            self._reset(17, f"{self.namespace_prefix}-{_RESET_NAMESPACES[2]}")
            self._verify_empty(18)
            raw = self._do_request(5, "html", via_proxy=True)
            self._step(
                19,
                raw.transport_error is None,
                f"status={raw.response_status} cache={raw.verified_cache_state}",
            )
            raw = self._do_request(6, "markdown", via_proxy=True)
            self._step(
                20,
                raw.transport_error is None,
                f"status={raw.response_status} cache={raw.verified_cache_state}",
            )
            self._verify_cache_evidence(21, 5, 6)

            # 22-25 Experiment 4: Markdown -> HTML warm cache.
            # No reset between steps 24 and 25 (§6.2 / §10.2).
            self._reset(22, f"{self.namespace_prefix}-{_RESET_NAMESPACES[3]}")
            self._verify_empty(23)
            raw = self._do_request(7, "markdown", via_proxy=True)
            self._step(
                24,
                raw.transport_error is None,
                f"status={raw.response_status} cache={raw.verified_cache_state}",
            )
            raw = self._do_request(8, "html", via_proxy=True)
            self._step(
                25,
                raw.transport_error is None,
                f"status={raw.response_status} cache={raw.verified_cache_state}",
            )
        finally:
            if self._own_proxy and self.proxy is not None:
                self.proxy.stop()
            if self._own_origin and self.origin is not None:
                self.origin.stop()

        assert self.origin is not None and self.proxy is not None
        assert len(self.step_log) == 25, (
            f"frozen step log must hold exactly 25 steps, got {len(self.step_log)}"
        )
        assert [rec.step for rec in self.step_log] == list(range(1, 26))
        assert [rec.name for rec in self.step_log] == list(STEP_NAMES)
        assert len(self.observations) == 8
        final_total = self.origin.counter_snapshot().total_requests
        run_events = tuple(
            ev for ev in self.origin.event_log() if ev.index > self.baseline_total
        )
        return ExperimentRun(
            contract_id=contract.contract_id,
            contract_sha256=canonical_contract_hash(contract),
            scenario_id=self.origin.scenario_id,
            proxy_mode=self.proxy.mode,
            observations=tuple(self.observations),
            raw_observations=tuple(self.raw_observations),
            reset_evidence=tuple(self.resets),
            step_log=tuple(self.step_log),
            cache_verifications=tuple(self.verifications),
            origin_events=run_events,
            origin_counter_baseline=self.baseline_total,
            origin_counter_final=final_total,
            verification_failures=tuple(self.failures),
        )


def run_experiments(
    contract: Contract | str | Path | dict,
    *,
    origin: SyntheticOrigin | None = None,
    proxy: ControlledCacheProxy | None = None,
    scenario: str = "healthy",
    proxy_mode: str = "respect_vary",
    namespace_prefix: str = "t005",
    output_path: str | Path | None = None,
) -> ExperimentRun:
    """Run the frozen four experiments for *contract* (§10.2 steps 01-25).

    *contract* may be a :class:`Contract`, a path to a contract JSON
    file, or a decoded contract dict. When *origin* / *proxy* are not
    supplied, they are created from the contract (origin with
    *scenario*, proxy with *proxy_mode*) and stopped afterwards; when
    supplied, they must already agree with the contract URLs, are
    started if not running, and are left running for the caller. A
    supplied proxy must also run in mode *proxy_mode* (default
    ``"respect_vary"``); a supplied proxy in any other mode is
    rejected with :class:`ExperimentError` at step 04 (fail-closed) —
    callers supplying a fault-injection proxy (e.g.
    ``"force_uri_only"`` for a deliberate bleed run) must pass its
    mode explicitly as *proxy_mode*. When *output_path* is given,
    the raw-observations file is written there (see
    :mod:`accepttwin.evidence`).
    """
    parsed = _coerce_contract(contract)
    runner = _Runner(
        parsed,
        origin=origin,
        proxy=proxy,
        scenario=scenario,
        proxy_mode=proxy_mode,
        namespace_prefix=namespace_prefix,
    )
    run = runner.execute()
    if output_path is not None:
        run.write_evidence(output_path)
    return run
