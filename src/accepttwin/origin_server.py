"""Synthetic HTTP origin server (P032 T003).

Implements IMPLEMENTATION_PLAN §5.3 / T003 and PROJECT_BOOK §5, §10
(steps 03, 07-08):

* a real local HTTP server (stdlib :mod:`http.server` only) bound to
  loopback, default port 18766 — the same port as
  ``contracts/site.json`` ``origin_url``;
* content negotiation on ``Accept`` only: ``text/html`` returns the HTML
  representation, ``text/markdown`` returns the Markdown representation;
  each body is fixed synthetic text containing exactly one Sentinel
  (``AT_HTML_SENTINEL_001`` / ``AT_MARKDOWN_SENTINEL_001`` per §5.1.2);
  the two Sentinels are different and are matched byte-exactly;
* controllable faults, driven by scenario definitions in
  ``fixtures/origin/``: per-representation status, Content-Type,
  Sentinel (correct / missing / wrong) and ``Vary`` — the fault
  fixtures a cache proxy / classifier must be able to distinguish from
  healthy behaviour (§8.1 ORIGIN_NEGOTIATION_ERROR, §11.2 C07-C10);
* an accurate request counter and an append-only event log: one event
  per request received, carrying method, path, Accept, status and a
  monotonically non-decreasing timestamp (§5.3);
* no HTML-to-Markdown conversion anywhere: both bodies are fixed
  synthetic strings, never derived from each other;
* no network access beyond loopback, no proxy environment variables,
  no public content, no body text in ordinary logs (§0.2 items 4, 7,
  17; §7.12 I-12).

The server is deliberately dumb: it serves one fixed path with fixed
synthetic scenarios and cannot infer a representation from natural
language or an LLM (§5.3). Anything not covered by the retrieved spec
text is documented below as a T003-local choice, not a spec claim:

* ``Accept`` values other than the two frozen ones (or an ``Accept``
  listing both) are answered 406 — the spec freezes only the two
  representations, so there is no correct body to return.
* Requests to a path other than the configured one are answered 404.
  Both still increment the counter and append one event: the counter
  records "a request reached the origin", which is exactly what the
  cache-evidence contract (§5.3) needs.
* ``Accept`` with quality values is resolved by highest ``q`` (first
  listed wins a tie) among ``text/html`` / ``text/markdown``.
* T008 extensions (PROJECT_BOOK §11.3 E01–E03/E07–E08, ADR-004):
  per-representation ``vary`` also accepts the literal values
  ``"Accept"``, ``"Accept, Accept-Encoding"`` and ``"*"`` (the legacy
  ``"accept"`` still means ``"Accept"``); ``vary_header_name`` may be
  ``"vary"`` (lowercase field name, E01); ``cache_control`` may carry
  a literal ``Cache-Control`` value such as ``"max-age=0"`` /
  ``"no-cache"`` (E07/E08). The 406-for-unknown-Accept behaviour and
  the ``q`` rules are unchanged (T003 P2-01/P2-02 deferred to T014).
* The counter is append-only: there is no reset method. Later stages
  (T004/T005) take a baseline with :meth:`SyntheticOrigin.counter_snapshot`
  before a run and compare deltas (§10 step 06), so a reset would only
  destroy evidence.
* Event ``timestamp`` is :func:`time.monotonic` seconds, which is
  monotonic by construction; ``received_at`` is an ISO-8601 UTC wall
  clock string for human readability only and must never enter a
  canonical hash.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .contract import Contract
from .url_guard import URLGuardError, validate_loopback_url

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PATH",
    "DEFAULT_PORT",
    "CounterSnapshot",
    "OriginEvent",
    "OriginServerError",
    "ScenarioError",
    "SyntheticOrigin",
    "default_fixture_dir",
    "load_scenario",
]

#: Default bind host: IPv4 loopback only (§0.2 item 1).
DEFAULT_HOST = "127.0.0.1"
#: Default port, matching contracts/site.json ``origin_url`` (§5.1.1).
DEFAULT_PORT = 18766
#: Default served path, matching contracts/site.json (§5.1.1).
DEFAULT_PATH = "/doc"

#: Frozen Sentinels from PROJECT_BOOK §5.1.2 (via contracts/site.json).
HTML_SENTINEL = "AT_HTML_SENTINEL_001"
MARKDOWN_SENTINEL = "AT_MARKDOWN_SENTINEL_001"

#: Sentinel values used by the "wrong" fault fixtures. They are distinct
#: from both frozen Sentinels and from each other, so a wrong-Sentinel
#: body fails an exact match for either representation.
WRONG_HTML_SENTINEL = "AT_HTML_SENTINEL_999"
WRONG_MARKDOWN_SENTINEL = "AT_MARKDOWN_SENTINEL_999"

#: Fixed synthetic bodies. The Sentinel appears exactly once in each
#: body. The two bodies are independent literals — the Markdown body is
#: NOT derived from the HTML body (§3.2: no HTML-to-Markdown engine).
_HTML_BODY_TEMPLATE = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head><meta charset=\"utf-8\">"
    "<title>AcceptTwin synthetic document</title></head>\n"
    "<body>\n"
    "<h1>AcceptTwin synthetic document</h1>\n"
    "<p>{sentinel}</p>\n"
    "</body>\n"
    "</html>\n"
)
_HTML_BODY_NO_SENTINEL = (
    "<!DOCTYPE html>\n"
    "<html lang=\"en\">\n"
    "<head><meta charset=\"utf-8\">"
    "<title>AcceptTwin synthetic document</title></head>\n"
    "<body>\n"
    "<h1>AcceptTwin synthetic document</h1>\n"
    "<p>Synthetic document without sentinel.</p>\n"
    "</body>\n"
    "</html>\n"
)
_MARKDOWN_BODY_TEMPLATE = (
    "# AcceptTwin synthetic document\n"
    "\n"
    "Synthetic Markdown representation.\n"
    "\n"
    "{sentinel}\n"
)
_MARKDOWN_BODY_NO_SENTINEL = (
    "# AcceptTwin synthetic document\n"
    "\n"
    "Synthetic Markdown representation.\n"
    "\n"
    "Synthetic document without sentinel.\n"
)

#: Allowed per-representation ``sentinel_mode`` values in a scenario file.
_SENTINEL_MODES = ("correct", "missing", "wrong")
#: Allowed per-representation ``vary`` values in a scenario file
#: (T008: extended from ``"accept"`` / null so the E01–E03 Golden can
#: express the frozen §11.3 shapes). ``"accept"`` is the legacy
#: shorthand for ``"Accept"``; the value is sent verbatim otherwise.
#: ``"*"`` is ``Vary: *`` (RFC 9111 §4.1: the stored response must
#: never be reused); ``"Accept, Accept-Encoding"`` is the multi-field
#: form. ``None`` sends no Vary header at all.
_VARY_MODES = ("accept", "Accept", "Accept, Accept-Encoding", "*", None)
#: Allowed per-representation ``vary_header_name`` values (T008, E01):
#: the Vary field name as written on the wire. HTTP field names are
#: case-insensitive (RFC 9110 §5.1), so ``"vary"`` must behave exactly
#: like ``"Vary"``; the value is what distinguishes the E01 wire shape.
_VARY_HEADER_NAMES = ("Vary", "vary")

logger = logging.getLogger(__name__)


class OriginServerError(ValueError):
    """Raised for invalid origin configuration (non-loopback, bad port...)."""


class ScenarioError(ValueError):
    """Raised when a scenario definition is malformed or unknown."""


# ---------------------------------------------------------------------------
# Evidence types (§5.3, §5.5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CounterSnapshot:
    """Point-in-time origin request counts (§5.3, §10 step 06).

    ``total_requests`` counts every HTTP request the origin has received
    since start, whatever its path, method or status. ``html_requests``
    / ``markdown_requests`` classify by the requested representation
    (``Accept``); ``other_requests`` covers requests whose ``Accept``
    matched neither representation.
    """

    total_requests: int
    html_requests: int = 0
    markdown_requests: int = 0
    other_requests: int = 0


@dataclass(frozen=True)
class OriginEvent:
    """One origin event: exactly one per request received (§5.3).

    ``timestamp`` is :func:`time.monotonic` seconds and therefore
    monotonically non-decreasing across events. ``received_at`` is a
    UTC ISO-8601 string for readability only. No body text is stored
    here (§7.12 I-12).
    """

    index: int
    method: str
    path: str
    accept: str
    status: int
    timestamp: float
    received_at: str


# ---------------------------------------------------------------------------
# Scenario definitions (fixtures/origin/*.json)
# ---------------------------------------------------------------------------


def default_fixture_dir() -> Path:
    """Return the workspace ``fixtures/origin`` directory.

    Resolved from this file's location (``src/accepttwin/`` -> project
    root -> ``fixtures/origin``), so it works from a checkout without
    depending on the current working directory.
    """
    return Path(__file__).resolve().parents[2] / "fixtures" / "origin"


def _validate_representation_scenario(
    name: str, rep: object, *, scenario_id: str
) -> dict[str, Any]:
    if not isinstance(rep, dict):
        raise ScenarioError(
            f"scenario {scenario_id!r}: representations.{name} must be an object"
        )
    allowed = {
        "status",
        "content_type",
        "sentinel_mode",
        "vary",
        "vary_header_name",
        "cache_control",
    }
    unknown = set(rep) - allowed
    if unknown:
        raise ScenarioError(
            f"scenario {scenario_id!r}: representations.{name} has "
            f"unsupported field(s): {sorted(unknown)}"
        )
    status = rep.get("status", 200)
    if not isinstance(status, int) or isinstance(status, bool):
        raise ScenarioError(
            f"scenario {scenario_id!r}: representations.{name}.status "
            f"must be an integer, got {status!r}"
        )
    if not 100 <= status <= 599:
        raise ScenarioError(
            f"scenario {scenario_id!r}: representations.{name}.status "
            f"out of range: {status}"
        )
    content_type = rep.get("content_type")
    if content_type is not None and (
        not isinstance(content_type, str) or not content_type.strip()
    ):
        raise ScenarioError(
            f"scenario {scenario_id!r}: representations.{name}.content_type "
            "must be a non-empty string or null"
        )
    sentinel_mode = rep.get("sentinel_mode", "correct")
    if sentinel_mode not in _SENTINEL_MODES:
        raise ScenarioError(
            f"scenario {scenario_id!r}: representations.{name}.sentinel_mode "
            f"must be one of {_SENTINEL_MODES}, got {sentinel_mode!r}"
        )
    vary = rep.get("vary", "accept")
    if vary not in _VARY_MODES:
        raise ScenarioError(
            f"scenario {scenario_id!r}: representations.{name}.vary must be "
            f"one of {sorted(v for v in _VARY_MODES if v is not None)!r} "
            f"or null, got {vary!r}"
        )
    # Normalise the legacy shorthand to the literal header value.
    vary_value = None if vary is None else ("Accept" if vary == "accept" else vary)
    vary_header_name = rep.get("vary_header_name", "Vary")
    if vary_header_name not in _VARY_HEADER_NAMES:
        raise ScenarioError(
            f"scenario {scenario_id!r}: representations.{name}.vary_header_name "
            f"must be one of {_VARY_HEADER_NAMES!r}, got {vary_header_name!r}"
        )
    cache_control = rep.get("cache_control")
    if cache_control is not None and (
        not isinstance(cache_control, str) or not cache_control.strip()
    ):
        raise ScenarioError(
            f"scenario {scenario_id!r}: representations.{name}.cache_control "
            "must be a non-empty string or null"
        )
    return {
        "status": status,
        "content_type": content_type,
        "sentinel_mode": sentinel_mode,
        "vary": vary_value,
        "vary_header_name": vary_header_name,
        "cache_control": cache_control,
    }


def load_scenario(name_or_path: str | Path) -> dict[str, Any]:
    """Load and validate a scenario definition.

    *name_or_path* is either a scenario id (resolved as
    ``<default_fixture_dir()>/<id>.json``) or a path to a ``.json``
    file. Returns the validated scenario dict. Unknown fields are
    rejected, never silently ignored (fail-closed, as in T002).
    """
    path = Path(name_or_path)
    if path.suffix != ".json":
        path = default_fixture_dir() / f"{name_or_path}.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioError(
            f"cannot read scenario file {path}: {exc}"
        ) from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ScenarioError(
            f"scenario file {path} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ScenarioError(f"scenario file {path} must be a JSON object")
    allowed_top = {"scenario_id", "description", "path", "representations"}
    unknown = set(data) - allowed_top
    if unknown:
        raise ScenarioError(
            f"scenario file {path} has unsupported field(s): {sorted(unknown)}"
        )
    scenario_id = data.get("scenario_id")
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ScenarioError(f"scenario file {path}: 'scenario_id' is required")
    representations = data.get("representations")
    if not isinstance(representations, dict):
        raise ScenarioError(
            f"scenario {scenario_id!r}: 'representations' is required"
        )
    unknown_reps = set(representations) - {"html", "markdown"}
    if unknown_reps:
        raise ScenarioError(
            f"scenario {scenario_id!r}: unknown representation(s): "
            f"{sorted(unknown_reps)}"
        )
    validated: dict[str, Any] = {
        "scenario_id": scenario_id,
        "description": data.get("description", ""),
        "path": data.get("path"),
        "representations": {
            name: _validate_representation_scenario(
                name, representations.get(name, {}), scenario_id=scenario_id
            )
            for name in ("html", "markdown")
        },
    }
    return validated


# ---------------------------------------------------------------------------
# Body construction (fixed synthetic text; no conversion)
# ---------------------------------------------------------------------------


def _body_for(rep_name: str, sentinel_mode: str) -> bytes:
    if rep_name == "html":
        if sentinel_mode == "missing":
            return _HTML_BODY_NO_SENTINEL.encode("utf-8")
        sentinel = (
            HTML_SENTINEL if sentinel_mode == "correct" else WRONG_HTML_SENTINEL
        )
        return _HTML_BODY_TEMPLATE.format(sentinel=sentinel).encode("utf-8")
    if sentinel_mode == "missing":
        return _MARKDOWN_BODY_NO_SENTINEL.encode("utf-8")
    sentinel = (
        MARKDOWN_SENTINEL
        if sentinel_mode == "correct"
        else WRONG_MARKDOWN_SENTINEL
    )
    return _MARKDOWN_BODY_TEMPLATE.format(sentinel=sentinel).encode("utf-8")


def _parse_accept(accept: str) -> str | None:
    """Classify an ``Accept`` header as ``"html"``, ``"markdown"`` or None.

    Only the two frozen media types count. Quality values are honoured:
    the highest-``q`` of the two wins; a tie goes to the first listed.
    A ``q=0`` media type is "not acceptable" (RFC 9110 §12.5.1) and
    is skipped, so an Accept naming only ``q=0`` types classifies as
    neither (the handler then answers 406); an invalid ``q`` value
    is treated as 0 for the same fail-closed reason. Anything else
    (including a missing header) classifies as neither.
    """
    best: str | None = None
    best_q = -1.0
    for part in accept.split(","):
        part = part.strip()
        if not part:
            continue
        media, _, params = part.partition(";")
        media = media.strip().lower()
        if media not in ("text/html", "text/markdown"):
            continue
        q = 1.0
        for param in params.split(";"):
            param = param.strip()
            if param.startswith("q="):
                try:
                    q = float(param[2:])
                except ValueError:
                    q = 0.0
        if q <= 0:
            # T014 (T003 P2-01): q=0 means "not acceptable".
            continue
        rep = "html" if media == "text/html" else "markdown"
        if q > best_q:
            best_q = q
            best = rep
    return best


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class _OriginHandler(BaseHTTPRequestHandler):
    """Per-request handler. All state lives on the owning server object."""

    protocol_version = "HTTP/1.1"
    server_version = "AcceptTwinOrigin/1.0.0"

    # -- logging: never emit request bodies (§7.12 I-12). The default
    # BaseHTTPRequestHandler.log_message writes a request line to stderr;
    # suppress it entirely — the structured event log is the only record.
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A002
        return

    def _record(self, status: int) -> None:
        origin: SyntheticOrigin = self.server.origin  # type: ignore[attr-defined]
        origin._record_event(
            method=self.command,
            path=self.path,
            accept=self.headers.get("Accept", ""),
            status=status,
        )

    def _send(
        self,
        status: int,
        content_type: str,
        body: bytes,
        vary: str | None = None,
        vary_name: str = "Vary",
        cache_control: str | None = None,
    ) -> None:
        # Record BEFORE the bytes leave: a client that has received the
        # full response must already see the counter/event for it (§5.3).
        self._record(status)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if vary is not None:
            self.send_header(vary_name, vary)
        if cache_control is not None:
            self.send_header("Cache-Control", cache_control)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _handle(self) -> None:
        origin: SyntheticOrigin = self.server.origin  # type: ignore[attr-defined]
        accept = self.headers.get("Accept", "")
        rep = _parse_accept(accept)
        if self.path != origin.path:
            body = b"404 Not Found\n"
            self._send(404, "text/plain; charset=utf-8", body)
            return
        if rep is None:
            body = b"406 Not Acceptable\n"
            self._send(406, "text/plain; charset=utf-8", body, vary="Accept")
            return
        cfg = origin._scenario["representations"][rep]
        body = _body_for(rep, cfg["sentinel_mode"])
        content_type = cfg["content_type"]
        if content_type is None:
            content_type = (
                "text/html; charset=utf-8"
                if rep == "html"
                else "text/markdown; charset=utf-8"
            )
        self._send(
            cfg["status"],
            content_type,
            body,
            vary=cfg["vary"],
            vary_name=cfg["vary_header_name"],
            cache_control=cfg["cache_control"],
        )

    def do_GET(self) -> None:
        self._handle()

    def do_HEAD(self) -> None:
        # HEAD is not part of the frozen GET-only surface (§0.2 item 2):
        # answer 405 so no caller can mistake it for a GET observation.
        self._send(405, "text/plain; charset=utf-8", b"405 Method Not Allowed\n")

    def do_POST(self) -> None:
        self._send(405, "text/plain; charset=utf-8", b"405 Method Not Allowed\n")

    def do_PUT(self) -> None:
        self._send(405, "text/plain; charset=utf-8", b"405 Method Not Allowed\n")

    def do_DELETE(self) -> None:
        self._send(405, "text/plain; charset=utf-8", b"405 Method Not Allowed\n")

    def do_PATCH(self) -> None:
        self._send(405, "text/plain; charset=utf-8", b"405 Method Not Allowed\n")


class _OriginHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], origin: "SyntheticOrigin"):
        super().__init__(address, _OriginHandler)
        self.origin = origin


# ---------------------------------------------------------------------------
# Synthetic origin (§5.3)
# ---------------------------------------------------------------------------


@dataclass
class SyntheticOrigin:
    """A real local HTTP origin serving fixed synthetic representations.

    Construct with a :class:`Contract` (host/port/path are then taken
    from its ``origin_url`` and Sentinels from its representations) or
    with explicit ``host`` / ``port`` / ``path``. Explicit values that
    disagree with a supplied contract are rejected, never silently
    preferred. ``scenario`` is a scenario id (resolved under
    ``fixtures/origin/``), a path to a scenario JSON file, or an
    already-loaded scenario dict. ``port=0`` asks the OS for a free
    loopback port (useful for tests); :attr:`port` then reports the
    bound port after :meth:`start`.
    """

    contract: Contract | None = None
    host: str | None = None
    port: int | None = None
    path: str | None = None
    scenario: str | Path | dict[str, Any] = "healthy"

    _server: _OriginHTTPServer | None = field(default=None, init=False, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _total: int = field(default=0, init=False, repr=False)
    _html: int = field(default=0, init=False, repr=False)
    _markdown: int = field(default=0, init=False, repr=False)
    _other: int = field(default=0, init=False, repr=False)
    _events: list[OriginEvent] = field(default_factory=list, init=False, repr=False)
    _scenario: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        host = self.host if self.host is not None else DEFAULT_HOST
        port = self.port if self.port is not None else DEFAULT_PORT
        path = self.path if self.path is not None else DEFAULT_PATH
        if self.contract is not None:
            try:
                validated = validate_loopback_url(self.contract.origin_url)
            except URLGuardError as exc:
                raise OriginServerError(
                    f"contract origin_url failed loopback guard: {exc}"
                ) from exc
            if self.host is not None and host != validated.host:
                raise OriginServerError(
                    f"explicit host {host!r} disagrees with contract "
                    f"origin_url host {validated.host!r}"
                )
            if self.port is not None and port != validated.port:
                raise OriginServerError(
                    f"explicit port {port!r} disagrees with contract "
                    f"origin_url port {validated.port!r}"
                )
            if self.path is not None and path != validated.path:
                raise OriginServerError(
                    f"explicit path {path!r} disagrees with contract "
                    f"origin_url path {validated.path!r}"
                )
            host, port, path = validated.host, validated.port, validated.path
            expected_html = self.contract.representations["html"].sentinel
            expected_md = self.contract.representations["markdown"].sentinel
            if (
                expected_html != HTML_SENTINEL
                or expected_md != MARKDOWN_SENTINEL
            ):
                raise OriginServerError(
                    "contract Sentinels differ from the frozen §5.1.2 values "
                    f"({expected_html!r} / {expected_md!r}); refusing to serve"
                )
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise OriginServerError(
                f"origin host must be loopback, got {host!r}"
            )
        if not isinstance(port, int) or isinstance(port, bool):
            raise OriginServerError(f"origin port must be an integer, got {port!r}")
        if not 0 <= port <= 65535:
            raise OriginServerError(f"origin port out of range: {port}")
        if not path.startswith("/"):
            raise OriginServerError(f"origin path must start with '/', got {path!r}")
        if isinstance(self.scenario, dict):
            scenario = self.scenario
            # Validate the dict through the same rules as a file.
            scenario_id = scenario.get("scenario_id", "<inline>")
            reps = scenario.get("representations")
            if not isinstance(reps, dict):
                raise ScenarioError(
                    f"inline scenario {scenario_id!r}: 'representations' is required"
                )
            scenario = {
                "scenario_id": scenario_id,
                "description": scenario.get("description", ""),
                "path": scenario.get("path"),
                "representations": {
                    name: _validate_representation_scenario(
                        name, reps.get(name, {}), scenario_id=str(scenario_id)
                    )
                    for name in ("html", "markdown")
                },
            }
        else:
            scenario = load_scenario(self.scenario)
        if scenario.get("path") is not None and scenario["path"] != path:
            raise ScenarioError(
                f"scenario {scenario['scenario_id']!r} declares path "
                f"{scenario['path']!r} but origin serves {path!r}"
            )
        # Normalise the effective values back onto the (mutable) fields.
        object.__setattr__(self, "host", host)
        object.__setattr__(self, "port", port)
        object.__setattr__(self, "path", path)
        self._scenario = scenario

    # -- introspection ----------------------------------------------------

    @property
    def scenario_id(self) -> str:
        return str(self._scenario["scenario_id"])

    @property
    def scenario_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._scenario))

    @property
    def url(self) -> str:
        """Base URL of this origin, e.g. ``http://127.0.0.1:18766/doc``."""
        host = f"[{self.host}]" if ":" in str(self.host) else str(self.host)
        return f"http://{host}:{self.port}{self.path}"

    @property
    def is_running(self) -> bool:
        return self._server is not None

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        """Bind the loopback socket and start serving in a daemon thread."""
        if self._server is not None:
            raise OriginServerError("origin is already running")
        try:
            server = _OriginHTTPServer((str(self.host), int(self.port)), self)
        except OSError as exc:
            raise OriginServerError(
                f"cannot bind origin on {self.host}:{self.port}: {exc}"
            ) from exc
        # port=0: report the OS-assigned port.
        object.__setattr__(self, "port", server.server_address[1])
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.05},
            name=f"accepttwin-origin:{self.port}", daemon=True,
        )
        self._server = server
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        """Shut down and release the port. Idempotent."""
        server, thread = self._server, self._thread
        self._server = None
        self._thread = None
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=5.0)

    def __enter__(self) -> "SyntheticOrigin":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- scenario switching ------------------------------------------------

    def set_scenario(self, scenario: str | Path | dict[str, Any]) -> None:
        """Switch the active scenario for subsequent requests.

        The counter and event log are NOT reset: evidence is append-only,
        so a scenario change mid-run stays visible in the log.
        """
        if isinstance(scenario, dict):
            new = {
                "scenario_id": scenario.get("scenario_id", "<inline>"),
                "description": scenario.get("description", ""),
                "path": scenario.get("path"),
                "representations": {
                    name: _validate_representation_scenario(
                        name,
                        scenario.get("representations", {}).get(name, {}),
                        scenario_id=str(scenario.get("scenario_id", "<inline>")),
                    )
                    for name in ("html", "markdown")
                },
            }
        else:
            new = load_scenario(scenario)
        if new.get("path") is not None and new["path"] != self.path:
            raise ScenarioError(
                f"scenario {new['scenario_id']!r} declares path "
                f"{new['path']!r} but origin serves {self.path!r}"
            )
        with self._lock:
            self._scenario = new

    # -- evidence (§5.3) ---------------------------------------------------

    def _record_event(self, *, method: str, path: str, accept: str, status: int) -> None:
        rep = _parse_accept(accept) if method == "GET" else None
        with self._lock:
            self._total += 1
            if rep == "html":
                self._html += 1
            elif rep == "markdown":
                self._markdown += 1
            else:
                self._other += 1
            event = OriginEvent(
                index=self._total,
                method=method,
                path=path,
                accept=accept,
                status=status,
                timestamp=time.monotonic(),
                received_at=datetime.now(timezone.utc).isoformat(),
            )
            self._events.append(event)

    def counter_snapshot(self) -> CounterSnapshot:
        """Return the current request counts (a copy, never live state)."""
        with self._lock:
            return CounterSnapshot(
                total_requests=self._total,
                html_requests=self._html,
                markdown_requests=self._markdown,
                other_requests=self._other,
            )

    def event_log(self) -> list[OriginEvent]:
        """Return a snapshot copy of the append-only event log."""
        with self._lock:
            return list(self._events)
