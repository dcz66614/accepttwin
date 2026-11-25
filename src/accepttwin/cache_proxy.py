"""Controlled cache proxy (P032 T004).

Implements IMPLEMENTATION_PLAN §5.4 / T004 and PROJECT_BOOK §5.2,
§5.3, §5.4 and §10.3:

* a real local HTTP proxy (stdlib :mod:`http.server` only) bound to
  loopback, default port 18765 — the same port as
  ``contracts/site.json`` ``url`` — forwarding to the synthetic origin
  (default port 18766);
* six proxy modes (§10.3), all local and synthetic, none of them a real
  CDN:

  ``respect_vary`` — the cache key carries the ``Accept`` dimension
  only when the origin response actually declares ``Vary: Accept``;
  without that declaration the key is URI-only, so a second
  representation genuinely reuses the first entry (PROJECT_BOOK §11.2
  C13/C14 bleed behaviour, reproduced rather than simulated);
  ``force_uri_only`` — the key is always URI-only, deliberately
  ignoring ``Accept`` (C11/C12/C15/C16 bleed behaviour);
  ``manual_accept_key`` — the key always carries the ``Accept``
  dimension, even when the origin sends no ``Vary`` (C03/C04 healthy
  behaviour);
  ``disabled`` — nothing is ever stored; every request is BYPASS
  (C05/C06, C17/C18);
  ``opaque`` — storage behaves like ``respect_vary`` but the
  ``X-AcceptTwin-*`` evidence headers are hidden, so a caller cannot
  confirm the cache state from headers (C20);
  ``ignore_no_store`` — deliberately stores responses even when the
  contract declares ``no_store`` or the origin answers
  ``Cache-Control: no-store`` (C19 negative test);

* cache-state response headers (§5.3): MISS and HIT carry
  ``X-AcceptTwin-Cache-Status``, ``X-AcceptTwin-Cache-Key`` (SHA-256 of
  the cache-key material) and ``X-AcceptTwin-Entry-Id``; BYPASS carries
  the status and the key that *would* have been used, but no entry id
  (no entry exists); ``opaque`` carries none of the three. A
  ``Vary: *`` response is fetched but never stored, so it is reported
  BYPASS, not MISS: MISS requires an entry to be created (§5.3 A),
  and a ``Vary: *`` response creates none, while its behaviour leg
  (origin +1, entry count unchanged) is exactly the BYPASS leg
  (§5.3 C);
* verifiable reset (§5.4): :meth:`ControlledCacheProxy.reset_cache`
  clears the store and returns a :class:`ResetEvidence` whose
  ``entries_after`` is 0 on success; :meth:`cache_snapshot` reports
  the live entry count and per-entry summaries (key hash, entry id,
  body SHA-256 — never body bytes);
* dual-evidence support (§5.3): the proxy never guesses a cache state
  from ``Age`` (it never emits or reads ``Age``), and every proxied
  response — including forwarded origin errors — carries its cache
  headers, so the header leg of the dual evidence exists on failure
  paths too (T001 §7: Hurl's failure short-circuit dropped exactly
  this). The behaviour leg (origin counter delta, origin events) is
  the caller's to measure against :meth:`SyntheticOrigin.counter_snapshot`
  / :meth:`SyntheticOrigin.event_log`; :mod:`accepttwin.cache_evidence`
  joins the two legs.

T004-local choices (not spec claims — the retrieved spec text does not
freeze them):

* The cache key is built from the *origin* URL (scheme, host, port,
  path, query), not the proxy URL, so the key is stable when the proxy
  binds an OS-assigned port (``port=0``) in tests.
* ``entry_id`` is deterministic: ``"entry-"`` + the first 16 hex chars
  of the cache-key SHA-256. The same key always yields the same entry
  id (so a HIT can be tied to the entry stored by the earlier MISS),
  and no random UUID ever enters an entry id (§10.4 forbids
  non-deterministic ids in canonical hashes).
* ``respect_vary`` lookup checks the Accept-dimensioned key first and
  the URI-only key second. A stored entry's key was fixed when the
  response was stored (its ``Vary`` was known then); a later request
  cannot know which key applies before fetching, so both candidate
  keys are consulted, most specific first. A ``Vary: *`` response is
  never stored and never reused (its stored entry, had one existed,
  could not be matched to any later request), and is reported BYPASS
  (fetched from the origin, nothing stored), never MISS — see the
  header bullet above.
* Every forwarded origin response is stored when the mode allows
  storage, whatever its status (including 404/406). A MISS is then
  always followed by a created entry, so the §5.3 MISS behaviour leg
  ("cache entry created by this response") is complete on failure
  paths as well. Origin errors are distinguished from cache errors by
  the direct-origin baseline (PROJECT_BOOK §6.3), not by the cache
  state, so storing an error response cannot mask an origin fault.
* Only ``GET`` is proxied (§0.2 item 2). Other methods are answered
  405 by the proxy itself, contact no origin, and carry no cache
  headers (there is no cache observation to report).
* Control endpoints (loopback only, never forwarded to the origin, so
  they never move the origin counter): ``POST /__accepttwin/reset``
  and ``GET /__accepttwin/snapshot``. They exist so a runner can
  verify reset/emptiness over real HTTP, not only in-process.
* ``reset_cache(namespace)`` clears the single store whatever label
  *namespace* carries: there is one store per proxy instance and a
  reset is defined (§6.2) as emptying it before an experiment. The
  namespace is recorded in the returned evidence.
* Forwarded request headers are rebuilt, not copied: the client's
  ``Accept`` verbatim plus the fixed ``Accept-Encoding: identity``,
  ``User-Agent: AcceptTwin/1.0.0`` and ``Accept-Language: en``
  (§5.1.3). Anything else the client sent (Cookie, Authorization,
  ...) is dropped, never forwarded.
* Stored entries keep status, Content-Type, Vary, Cache-Control and
  body bytes. Bodies here are synthetic (§5.1.2); no real user data is
  ever stored, and snapshots/logs never contain body bytes (§7.12
  I-12).
"""

from __future__ import annotations

import hashlib
import http.client
import json
import logging
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from .contract import DEFAULT_MAX_BODY_BYTES, Contract
from .privacy import read_http_body_bounded
from .url_guard import URLGuardError, validate_loopback_url

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "CacheEntry",
    "CacheEntrySummary",
    "CacheProxyError",
    "CacheSnapshot",
    "ControlledCacheProxy",
    "PROXY_MODES",
    "ResetEvidence",
    "cache_key_for",
]

#: Default bind host: IPv4 loopback only (§0.2 item 1).
DEFAULT_HOST = "127.0.0.1"
#: Default port, matching contracts/site.json ``url`` (§5.1.1).
DEFAULT_PORT = 18765

#: The six proxy modes frozen by PROJECT_BOOK §10.3.
PROXY_MODES: frozenset[str] = frozenset(
    {
        "respect_vary",
        "force_uri_only",
        "manual_accept_key",
        "disabled",
        "opaque",
        "ignore_no_store",
    }
)

#: Cache-state response header names (§5.3).
HEADER_STATUS = "X-AcceptTwin-Cache-Status"
HEADER_KEY = "X-AcceptTwin-Cache-Key"
HEADER_ENTRY_ID = "X-AcceptTwin-Entry-Id"

#: Contract cache-behavior mode that forbids storage (§5.2 example B).
CONTRACT_NO_STORE = "no_store"

#: Prefix for the proxy's own control endpoints (never forwarded).
_CONTROL_PREFIX = "/__accepttwin/"

logger = logging.getLogger(__name__)


class CacheProxyError(ValueError):
    """Raised for invalid proxy configuration or control requests."""


# ---------------------------------------------------------------------------
# Evidence types (§5.3, §5.4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CacheEntry:
    """One stored cache entry.

    ``body`` is kept so a HIT can serve the stored representation
    byte-for-byte; it is synthetic origin content only (§5.1.2) and is
    never copied into snapshots, logs or reports.
    """

    entry_id: str
    cache_key_sha256: str
    url: str
    accept: str | None  # Accept dimension value, or None for URI-only keys
    status: int
    content_type: str
    vary: str | None
    cache_control: str | None
    body: bytes

    @property
    def body_sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()

    def summary(self) -> "CacheEntrySummary":
        return CacheEntrySummary(
            entry_id=self.entry_id,
            cache_key_sha256=self.cache_key_sha256,
            url=self.url,
            accept=self.accept,
            status=self.status,
            content_type=self.content_type,
            body_sha256=self.body_sha256,
        )


@dataclass(frozen=True)
class CacheEntrySummary:
    """A cache entry as exposed by :meth:`ControlledCacheProxy.cache_snapshot`.

    Contains hashes and metadata only — never body bytes (§7.12 I-12).
    """

    entry_id: str
    cache_key_sha256: str
    url: str
    accept: str | None
    status: int
    content_type: str
    body_sha256: str


@dataclass(frozen=True)
class CacheSnapshot:
    """Point-in-time view of the proxy store (§5.4)."""

    entry_count: int
    entries: tuple[CacheEntrySummary, ...] = ()


@dataclass(frozen=True)
class ResetEvidence:
    """Evidence that a cache reset happened and was verified (§5.4).

    ``success`` is true exactly when the store is empty afterwards.
    """

    namespace: str
    success: bool
    entries_before: int
    entries_after: int
    entries_removed: int


# ---------------------------------------------------------------------------
# Cache keys
# ---------------------------------------------------------------------------


def _normalise_accept(accept: str) -> str:
    return accept.strip().lower()


def cache_key_for(url: str, accept: str | None) -> tuple[str, str]:
    """Return ``(key_material, sha256_hex)`` for a cache key.

    *accept* ``None`` means a URI-only key; any other value adds the
    Accept dimension. The material is human-readable (``url`` plus, when
    present, ``accept=<value>``); the SHA-256 is what travels in the
    ``X-AcceptTwin-Cache-Key`` header.
    """
    if accept is None:
        material = url
    else:
        material = f"{url}\naccept={_normalise_accept(accept)}"
    return material, hashlib.sha256(material.encode("utf-8")).hexdigest()


def _entry_id_for(key_sha256: str) -> str:
    """Deterministic entry id for a cache key (§10.4: no random ids)."""
    return f"entry-{key_sha256[:16]}"


def _vary_tokens(vary: str | None) -> list[str]:
    if not vary:
        return []
    return [token.strip().lower() for token in vary.split(",") if token.strip()]


def _cache_control_no_store(cache_control: str | None) -> bool:
    if not cache_control:
        return False
    return any(
        token.strip().lower() == "no-store"
        for token in cache_control.split(",")
    )


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class _ProxyHandler(BaseHTTPRequestHandler):
    """Per-request handler. All state lives on the owning proxy object."""

    protocol_version = "HTTP/1.1"
    server_version = "AcceptTwinProxy/1.0.0"

    # -- logging: never emit response bodies (§7.12 I-12). Suppress the
    # default request-line log entirely; the structured evidence types
    # are the only record.
    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A002
        return

    @property
    def _proxy(self) -> "ControlledCacheProxy":
        return self.server.proxy  # type: ignore[attr-defined]

    def _send_bytes(
        self,
        status: int,
        headers: list[tuple[str, str]],
        body: bytes,
    ) -> None:
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _handle_control(self) -> bool:
        """Serve /__accepttwin/* control endpoints. Returns True if handled."""
        proxy = self._proxy
        if self.path == "/__accepttwin/snapshot":
            if self.command != "GET":
                self._send_bytes(
                    405,
                    [("Content-Type", "text/plain; charset=utf-8")],
                    b"405 Method Not Allowed\n",
                )
                return True
            snapshot = proxy.cache_snapshot()
            payload = {
                "entry_count": snapshot.entry_count,
                "entries": [
                    {
                        "entry_id": e.entry_id,
                        "cache_key_sha256": e.cache_key_sha256,
                        "url": e.url,
                        "accept": e.accept,
                        "status": e.status,
                        "content_type": e.content_type,
                        "body_sha256": e.body_sha256,
                    }
                    for e in snapshot.entries
                ],
            }
            self._send_bytes(
                200,
                [("Content-Type", "application/json; charset=utf-8")],
                json.dumps(payload, sort_keys=True).encode("utf-8"),
            )
            return True
        if self.path == "/__accepttwin/reset":
            if self.command != "POST":
                self._send_bytes(
                    405,
                    [("Content-Type", "text/plain; charset=utf-8")],
                    b"405 Method Not Allowed\n",
                )
                return True
            namespace = "default"
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                try:
                    raw = self.rfile.read(length)
                    data = json.loads(raw.decode("utf-8"))
                    if isinstance(data, dict) and isinstance(
                        data.get("namespace"), str
                    ) and data["namespace"]:
                        namespace = data["namespace"]
                except (ValueError, UnicodeDecodeError):
                    self._send_bytes(
                        400,
                        [("Content-Type", "text/plain; charset=utf-8")],
                        b"400 Bad Request\n",
                    )
                    return True
            evidence = proxy.reset_cache(namespace)
            payload = {
                "namespace": evidence.namespace,
                "success": evidence.success,
                "entries_before": evidence.entries_before,
                "entries_after": evidence.entries_after,
                "entries_removed": evidence.entries_removed,
            }
            self._send_bytes(
                200,
                [("Content-Type", "application/json; charset=utf-8")],
                json.dumps(payload, sort_keys=True).encode("utf-8"),
            )
            return True
        return False

    def _handle_get(self) -> None:
        proxy = self._proxy
        if self.path.startswith(_CONTROL_PREFIX):
            if not self._handle_control():
                self._send_bytes(
                    404,
                    [("Content-Type", "text/plain; charset=utf-8")],
                    b"404 Not Found\n",
                )
            return
        accept = self.headers.get("Accept", "")
        status, headers, body = proxy._serve_once(self.path, accept)
        self._send_bytes(status, headers, body)

    def do_GET(self) -> None:
        self._handle_get()

    def _reject_method(self) -> None:
        # Non-GET methods are rejected by the proxy itself: no origin
        # contact, no cache observation, hence no cache headers.
        if self.path.startswith(_CONTROL_PREFIX):
            self._handle_control()
            return
        self._send_bytes(
            405,
            [("Content-Type", "text/plain; charset=utf-8")],
            b"405 Method Not Allowed\n",
        )

    def do_HEAD(self) -> None:
        self._reject_method()

    def do_POST(self) -> None:
        self._reject_method()

    def do_PUT(self) -> None:
        self._reject_method()

    def do_DELETE(self) -> None:
        self._reject_method()

    def do_PATCH(self) -> None:
        self._reject_method()


class _ProxyHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], proxy: "ControlledCacheProxy"):
        super().__init__(address, _ProxyHandler)
        self.proxy = proxy


# ---------------------------------------------------------------------------
# Controlled cache proxy (§5.4, §10.3)
# ---------------------------------------------------------------------------


@dataclass
class ControlledCacheProxy:
    """A real local HTTP cache proxy with six controlled modes (§10.3).

    Construct with an ``origin_url`` (loopback, e.g.
    ``http://127.0.0.1:18766/doc``) or with a ``Contract`` (the origin
    URL and the ``cache_behavior`` mode are then taken from it).
    ``port=0`` asks the OS for a free loopback port (useful for tests);
    :attr:`port` then reports the bound port after :meth:`start`.
    ``mode`` is one of the six §10.3 names. ``request_timeout_seconds``
    bounds a single origin fetch. ``max_body_bytes`` bounds a single
    origin fetch body (T014, T013-F04): at most ``max_body_bytes + 1``
    bytes are retained from the origin response; when a contract is
    supplied its ``limits.max_body_bytes`` wins, otherwise the 1 MiB
    default applies. A truncated stored entry keeps hash consistency
    with what the runner later reads (the truncation happens once,
    here), and the classifier still rejects the oversize body via
    ``body_too_large`` (§8.6).
    """

    origin_url: str | None = None
    contract: Contract | None = None
    host: str | None = None
    port: int | None = None
    mode: str = "respect_vary"
    request_timeout_seconds: float = 5.0
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES

    _server: _ProxyHTTPServer | None = field(default=None, init=False, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _entries: dict[str, CacheEntry] = field(default_factory=dict, init=False, repr=False)
    _origin_host: str = field(default="", init=False, repr=False)
    _origin_port: int = field(default=0, init=False, repr=False)
    _origin_path: str = field(default="", init=False, repr=False)
    _contract_no_store: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.mode not in PROXY_MODES:
            raise CacheProxyError(
                f"unknown proxy mode {self.mode!r}; expected one of "
                f"{sorted(PROXY_MODES)}"
            )
        host = self.host if self.host is not None else DEFAULT_HOST
        port = self.port if self.port is not None else DEFAULT_PORT
        origin_url = self.origin_url
        if self.contract is not None:
            try:
                validated_origin = validate_loopback_url(
                    self.contract.origin_url
                )
            except URLGuardError as exc:
                raise CacheProxyError(
                    f"contract origin_url failed loopback guard: {exc}"
                ) from exc
            if origin_url is not None and origin_url != self.contract.origin_url:
                raise CacheProxyError(
                    f"explicit origin_url {origin_url!r} disagrees with "
                    f"contract origin_url {self.contract.origin_url!r}"
                )
            origin_url = self.contract.origin_url
            behaviour = self.contract.cache_behavior or {}
            self._contract_no_store = behaviour.get("mode") == CONTRACT_NO_STORE
            self.max_body_bytes = int(
                self.contract.limits.get(
                    "max_body_bytes", self.max_body_bytes
                )
            )
        if origin_url is None:
            raise CacheProxyError("origin_url (or a contract) is required")
        try:
            validated = validate_loopback_url(origin_url)
        except URLGuardError as exc:
            raise CacheProxyError(
                f"origin_url failed loopback guard: {exc}"
            ) from exc
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise CacheProxyError(
                f"proxy host must be loopback, got {host!r}"
            )
        if not isinstance(port, int) or isinstance(port, bool):
            raise CacheProxyError(f"proxy port must be an integer, got {port!r}")
        if not 0 <= port <= 65535:
            raise CacheProxyError(f"proxy port out of range: {port}")
        if not isinstance(self.request_timeout_seconds, (int, float)) or isinstance(
            self.request_timeout_seconds, bool
        ) or self.request_timeout_seconds <= 0:
            raise CacheProxyError(
                "request_timeout_seconds must be a positive number, got "
                f"{self.request_timeout_seconds!r}"
            )
        object.__setattr__(self, "host", host)
        object.__setattr__(self, "port", port)
        object.__setattr__(self, "origin_url", origin_url)
        self._origin_host = validated.host
        self._origin_port = validated.port
        self._origin_path = validated.path

    # -- introspection ----------------------------------------------------

    @property
    def url(self) -> str:
        """Base URL of this proxy, e.g. ``http://127.0.0.1:18765/doc``."""
        host = f"[{self.host}]" if ":" in str(self.host) else str(self.host)
        return f"http://{host}:{self.port}{self._origin_path}"

    @property
    def is_running(self) -> bool:
        return self._server is not None

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        """Bind the loopback socket and start serving in a daemon thread."""
        if self._server is not None:
            raise CacheProxyError("proxy is already running")
        try:
            server = _ProxyHTTPServer((str(self.host), int(self.port)), self)
        except OSError as exc:
            raise CacheProxyError(
                f"cannot bind proxy on {self.host}:{self.port}: {exc}"
            ) from exc
        # port=0: report the OS-assigned port.
        object.__setattr__(self, "port", server.server_address[1])
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.05},
            name=f"accepttwin-proxy:{self.port}", daemon=True,
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

    def __enter__(self) -> "ControlledCacheProxy":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- cache state (§5.4) -------------------------------------------------

    def reset_cache(self, namespace: str) -> ResetEvidence:
        """Empty the store and return verifiable reset evidence (§5.4).

        ``success`` is true exactly when the store holds 0 entries
        afterwards. The single store is cleared whatever label
        *namespace* carries; the label is recorded in the evidence.
        """
        if not isinstance(namespace, str) or not namespace:
            raise CacheProxyError("namespace must be a non-empty string")
        with self._lock:
            before = len(self._entries)
            self._entries.clear()
            after = len(self._entries)
        return ResetEvidence(
            namespace=namespace,
            success=after == 0,
            entries_before=before,
            entries_after=after,
            entries_removed=before - after,
        )

    def cache_snapshot(self) -> CacheSnapshot:
        """Return the current store contents (summaries only, no bodies)."""
        with self._lock:
            entries = tuple(
                entry.summary()
                for entry in sorted(
                    self._entries.values(), key=lambda e: e.cache_key_sha256
                )
            )
        return CacheSnapshot(entry_count=len(entries), entries=entries)

    # -- request serving ----------------------------------------------------

    def _origin_url_for(self, path_and_query: str) -> str:
        """Full origin URL for a client request path (path + optional query)."""
        split = urlsplit(path_and_query)
        path = split.path or "/"
        url = (
            f"http://{self._origin_host}:{self._origin_port}{path}"
        )
        if split.query:
            url += f"?{split.query}"
        return url

    def _candidate_keys(
        self, origin_url: str, accept: str
    ) -> list[tuple[str | None, str, str]]:
        """Candidate cache keys for a request, most specific first.

        Returns ``(accept_dimension, key_material, key_sha256)`` triples.
        ``respect_vary`` and ``opaque`` try the Accept-dimensioned key
        first, then the URI-only key (the stored entry's key was fixed
        when its response — and its Vary — arrived). ``force_uri_only``
        tries only the URI-only key; ``manual_accept_key`` and
        ``ignore_no_store`` only the Accept-dimensioned key; ``disabled``
        never looks anything up.
        """
        if self.mode in ("force_uri_only",):
            dims: list[str | None] = [None]
        elif self.mode in ("manual_accept_key", "ignore_no_store"):
            dims = [accept]
        else:  # respect_vary, opaque
            dims = [accept, None]
        out = []
        for dim in dims:
            material, key_sha = cache_key_for(origin_url, dim)
            out.append((dim, material, key_sha))
        return out

    def _lookup(
        self, origin_url: str, accept: str
    ) -> CacheEntry | None:
        if self.mode == "disabled":
            return None
        with self._lock:
            for _dim, _material, key_sha in self._candidate_keys(origin_url, accept):
                entry = self._entries.get(key_sha)
                if entry is not None:
                    return entry
        return None

    def _key_dimension(self, accept: str, vary: str | None) -> str | None:
        """Accept dimension for a response's cache key, per mode and Vary.

        ``force_uri_only`` never dimensions by Accept; ``manual_accept_key``
        and ``ignore_no_store`` always do; ``respect_vary`` / ``opaque``
        follow the response's actual ``Vary``.
        """
        if self.mode == "force_uri_only":
            return None
        if self.mode in ("manual_accept_key", "ignore_no_store"):
            return accept
        tokens = _vary_tokens(vary)
        return accept if "accept" in tokens else None

    def _store(
        self,
        *,
        origin_url: str,
        accept: str,
        status: int,
        content_type: str,
        vary: str | None,
        cache_control: str | None,
        body: bytes,
    ) -> CacheEntry | None:
        """Store a fetched response under the key its Vary dictates.

        Returns the stored entry, or ``None`` when this response must
        not be stored (disabled mode, no-store contract/origin response
        unless the mode is ``ignore_no_store``, or ``Vary: *``).
        """
        if self.mode == "disabled":
            return None
        if self.mode != "ignore_no_store":
            if self._contract_no_store:
                return None
            if _cache_control_no_store(cache_control):
                return None
        tokens = _vary_tokens(vary)
        if "*" in tokens:
            # Vary: * — a stored entry could never be reused (§11.3 E03).
            return None
        dim = self._key_dimension(accept, vary)
        _material, key_sha = cache_key_for(origin_url, dim)
        entry = CacheEntry(
            entry_id=_entry_id_for(key_sha),
            cache_key_sha256=key_sha,
            url=origin_url,
            accept=(_normalise_accept(accept) if dim is not None else None),
            status=status,
            content_type=content_type,
            vary=vary,
            cache_control=cache_control,
            body=body,
        )
        with self._lock:
            self._entries[key_sha] = entry
        return entry

    def _fetch_origin(
        self, path_and_query: str, accept: str
    ) -> tuple[int, str, str | None, str | None, bytes]:
        """Fetch one GET from the origin with the fixed header set (§5.1.3)."""
        conn = http.client.HTTPConnection(
            self._origin_host,
            self._origin_port,
            timeout=float(self.request_timeout_seconds),
        )
        try:
            conn.request(
                "GET",
                path_and_query,
                headers={
                    "Accept": accept,
                    "Accept-Encoding": "identity",
                    "User-Agent": "AcceptTwin/1.0.0",
                    "Accept-Language": "en",
                },
            )
            resp = conn.getresponse()
            # Bounded read (T014, T013-F04): at most max_body_bytes + 1
            # bytes are retained; the exact size/hash are not needed
            # here — the stored entry and everything downstream see
            # the same retained bytes, so hashes stay consistent.
            body = read_http_body_bounded(resp, self.max_body_bytes)[0]
            headers = {k.lower(): v for k, v in resp.getheaders()}
            return (
                resp.status,
                headers.get("content-type", "text/plain; charset=utf-8"),
                headers.get("vary"),
                headers.get("cache-control"),
                body,
            )
        finally:
            conn.close()

    def _evidence_headers(
        self,
        status: str,
        key_sha256: str,
        entry_id: str | None,
    ) -> list[tuple[str, str]]:
        """The X-AcceptTwin-* header leg (§5.3); empty in ``opaque`` mode."""
        if self.mode == "opaque":
            return []
        headers = [(HEADER_STATUS, status), (HEADER_KEY, key_sha256)]
        if entry_id is not None:
            headers.append((HEADER_ENTRY_ID, entry_id))
        return headers

    def _serve_once(
        self, path_and_query: str, accept: str
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        """Serve one proxied GET. Returns ``(status, headers, body)``.

        This is the single request path used by the HTTP handler, so
        in-process callers and real HTTP clients observe identical
        behaviour.
        """
        origin_url = self._origin_url_for(path_and_query)
        # Lookup first (``disabled`` mode and no-store contracts never
        # have entries, so their lookup always misses and they fall
        # through to the fetch branch, which reports BYPASS).
        hit = self._lookup(origin_url, accept)
        if hit is not None:
            headers: list[tuple[str, str]] = [
                ("Content-Type", hit.content_type),
            ]
            if hit.vary is not None:
                headers.append(("Vary", hit.vary))
            if hit.cache_control is not None:
                headers.append(("Cache-Control", hit.cache_control))
            headers.extend(
                self._evidence_headers(
                    "HIT", hit.cache_key_sha256, hit.entry_id
                )
            )
            return hit.status, headers, hit.body

        status, content_type, vary, cache_control, body = self._fetch_origin(
            path_and_query, accept
        )
        # A no-store origin response is BYPASS even in caching modes
        # (unless the mode deliberately ignores no-store).
        origin_no_store = _cache_control_no_store(cache_control)
        if (
            self.mode == "disabled"
            or (self._contract_no_store and self.mode != "ignore_no_store")
            or (origin_no_store and self.mode != "ignore_no_store")
        ):
            _material, key_sha = cache_key_for(
                origin_url, self._key_dimension(accept, vary)
            )
            headers = [("Content-Type", content_type)]
            if vary is not None:
                headers.append(("Vary", vary))
            if cache_control is not None:
                headers.append(("Cache-Control", cache_control))
            headers.extend(
                self._evidence_headers("BYPASS", key_sha, None)
            )
            return status, headers, body

        stored = self._store(
            origin_url=origin_url,
            accept=accept,
            status=status,
            content_type=content_type,
            vary=vary,
            cache_control=cache_control,
            body=body,
        )
        if stored is None:
            # Vary: * — fetched but not storable: report BYPASS, not
            # MISS. The response came from the origin and nothing was
            # stored (entry count unchanged), which is the BYPASS
            # behaviour leg (§5.3 C); MISS requires an entry to be
            # created (§5.3 A), and there is none here.
            _material, key_sha = cache_key_for(
                origin_url, self._key_dimension(accept, vary)
            )
            headers = [("Content-Type", content_type)]
            if vary is not None:
                headers.append(("Vary", vary))
            if cache_control is not None:
                headers.append(("Cache-Control", cache_control))
            headers.extend(self._evidence_headers("BYPASS", key_sha, None))
            return status, headers, body
        headers = [("Content-Type", content_type)]
        if vary is not None:
            headers.append(("Vary", vary))
        if cache_control is not None:
            headers.append(("Cache-Control", cache_control))
        headers.extend(
            self._evidence_headers(
                "MISS", stored.cache_key_sha256, stored.entry_id
            )
        )
        return status, headers, body
