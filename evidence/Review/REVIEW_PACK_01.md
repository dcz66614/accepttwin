# FIX-R1 审查包 01 — 生产源码（src/accepttwin/ 全部）

审查对象 commit：`221f902798a245b7a2672f3a53a9a63ab176e014`（tag `P032-v1.0.1`，P032 FIX-R1 重冻结，规格 v1.0.1）。
本包全部内容取自该 tag 的 git 对象（`git show <tag>:<path>`），非工作区副本；
每节标题下均给出该文件在该 tag 下的 SHA-256（对内容字节计算）。
核对方法：`git show 221f902798a245b7a2672f3a53a9a63ab176e014:<path> | sha256sum`。

## src/accepttwin/__init__.py

- SHA-256：`d71659fee694dc6567c1dcecae5c5aaec540fe89edc8825d889ed0cc36451177`
- 字节数：106

```
"""AcceptTwin production package (P032, SPEC v1.0.0)."""

__version__ = "1.0.0"
__all__ = ["__version__"]
```

## src/accepttwin/__main__.py

- SHA-256：`22bff6c0b736d62194ce807d4d16cba20ac355d23af0828d1c03aa19ee84c2d8`
- 字节数：239

```
"""Entry point for ``python -m accepttwin`` (P032 T012).

Thin wrapper only: all logic lives in :mod:`accepttwin.cli`.
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

## src/accepttwin/cache_proxy.py

- SHA-256：`cd2d985f166346307c2848b4c3f4632a7ab2f9e67c83073671dd2eddf9c8d2a2`
- 字节数：34475

```
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
```

## src/accepttwin/cache_evidence.py

- SHA-256：`aeb6423bb78f0fc24c6899e95082c0b3e9d5c8119349a41500b94d94b048ab6a`
- 字节数：10530

```
"""Dual-evidence cache-state verification (P032 T004).

Implements the evidence contract of PROJECT_BOOK §5.3 and the
verification step of IMPLEMENTATION_PLAN T004 step 13:

* every cache state (MISS / HIT / BYPASS) is confirmed only when its
  *header* leg and its *behaviour* leg both hold;
* any conflict between the legs, or any missing leg, yields
  ``CACHE_STATE_UNKNOWN`` — never a guessed state.

The legs, per §5.3:

* MISS — header leg: ``X-AcceptTwin-Cache-Status: MISS`` plus a
  ``X-AcceptTwin-Cache-Key`` and a ``X-AcceptTwin-Entry-Id``;
  behaviour leg: the origin request counter increased by exactly 1,
  an origin event exists for this request, and a cache entry was
  created by this response.
* HIT — header leg: status HIT plus key and entry id; behaviour leg:
  the origin counter did not move, the entry id matches the entry
  actually stored, and the returned body hash matches the stored
  entry's body hash.
* BYPASS — header leg: status BYPASS; behaviour leg: the origin
  counter increased by exactly 1, an origin event exists for this
  request, and the entry count did not increase.

Rules applied here, all fail-closed:

* A leg supplied as ``None`` means "evidence unavailable", not "leg
  satisfied": a MISS whose entry creation was never checked, a HIT
  whose entry id was never compared, or a BYPASS whose entry-count
  delta was never measured is UNKNOWN (§5.3 D: "缺少源站事件日志" /
  "缓存键无法关联" / "缓存重置未确认成功" all forbid guessing).
* The origin-event leg applies to MISS and BYPASS only (those are the
  states where a request reaches the origin). For HIT no new origin
  event is expected, so ``origin_event_present`` is ignored there.
* ``Age``, ``Via``, ``Vary`` and ``Cache-Control`` are auxiliary only
  (§5.3 E): they are never consulted here and can never prove a HIT
  or a MISS on their own.
* An optional *expected* state may be supplied by the caller (e.g.
  the contract/mode prediction). A header state that disagrees with
  it is a conflict and yields UNKNOWN.
* The verifier never performs I/O and never invents origin counts: the
  caller measures the counter delta from
  :meth:`SyntheticOrigin.counter_snapshot` before/after the request
  and passes the measured number in. A fabricated delta would be a
  fabricated verdict, not evidence (§5.3, T004 prohibition).

This module is pure logic, which is why its tests live in
``tests/unit/test_cache_evidence.py`` while the end-to-end dual
evidence (real HTTP + real counters) is exercised in
``tests/integration/test_cache_proxy.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "CACHE_STATE_UNKNOWN",
    "CACHE_STATES",
    "BehaviorEvidence",
    "CacheEvidenceResult",
    "HeaderEvidence",
    "verify_cache_state",
]

#: The only "state" a conflict or an incomplete evidence pair may yield.
CACHE_STATE_UNKNOWN = "CACHE_STATE_UNKNOWN"

#: Cache states that count as confirmed (§5.3 A–C).
CACHE_STATES: frozenset[str] = frozenset({"MISS", "HIT", "BYPASS"})


@dataclass(frozen=True)
class HeaderEvidence:
    """The response-header leg of the dual evidence (§5.3).

    ``None`` on any field means the header was absent — a missing leg,
    never a satisfied one.
    """

    status: str | None
    cache_key_sha256: str | None = None
    entry_id: str | None = None


@dataclass(frozen=True)
class BehaviorEvidence:
    """The origin-behaviour leg of the dual evidence (§5.3).

    ``None`` on any field means that leg was not measured — a missing
    leg, never a satisfied one. ``origin_event_present`` is meaningful
    only for MISS/BYPASS (a HIT expects no new origin request);
    ``entry_created`` only for MISS; ``entry_id_matches`` /
    ``body_hash_matches`` only for HIT; ``entry_count_delta`` only for
    BYPASS.
    """

    origin_counter_delta: int | None = None
    origin_event_present: bool | None = None
    entry_created: bool | None = None
    entry_id_matches: bool | None = None
    body_hash_matches: bool | None = None
    entry_count_delta: int | None = None


@dataclass(frozen=True)
class CacheEvidenceResult:
    """The outcome of one dual-evidence verification.

    ``state`` is ``"MISS"``, ``"HIT"``, ``"BYPASS"`` or
    ``CACHE_STATE_UNKNOWN``. ``verified`` is true exactly when the
    state is confirmed (i.e. not UNKNOWN). ``reasons`` lists, in
    deterministic order, every leg that was checked and every leg that
    failed or was missing, so a caller (and T006) can report *why* a
    state is UNKNOWN instead of merely that it is.
    """

    state: str
    header_status: str | None
    verified: bool
    reasons: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.verified


def _missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value)


def verify_cache_state(
    header: HeaderEvidence,
    behavior: BehaviorEvidence,
    expected: str | None = None,
) -> CacheEvidenceResult:
    """Verify one cache observation against both evidence legs (§5.3).

    Returns a :class:`CacheEvidenceResult` whose ``state`` is the
    confirmed cache state, or ``CACHE_STATE_UNKNOWN`` when the header
    and behaviour legs disagree, when either leg is missing, or when
    the header state disagrees with *expected* (when given).
    """
    reasons: list[str] = []
    status = header.status

    def unknown(*new_reasons: str) -> CacheEvidenceResult:
        reasons.extend(new_reasons)
        return CacheEvidenceResult(
            state=CACHE_STATE_UNKNOWN,
            header_status=status,
            verified=False,
            reasons=tuple(reasons),
        )

    # -- header leg, common to all states -------------------------------
    if _missing(status):
        return unknown("missing cache-status header")
    assert status is not None  # _missing() above narrows it for readers
    if status not in CACHE_STATES:
        return unknown(f"unrecognised cache-status header value: {status!r}")
    if expected is not None and status != expected:
        return unknown(
            f"header cache state {status!r} does not match "
            f"expected state {expected!r}"
        )

    # -- MISS ------------------------------------------------------------
    if status == "MISS":
        if _missing(header.cache_key_sha256):
            reasons.append("missing cache-key header")
        if _missing(header.entry_id):
            reasons.append("missing entry-id header")
        if behavior.origin_counter_delta is None:
            reasons.append("origin counter delta not measured")
        elif behavior.origin_counter_delta != 1:
            reasons.append(
                "MISS requires origin counter delta +1, got "
                f"{behavior.origin_counter_delta:+d}"
            )
        if behavior.origin_event_present is None:
            reasons.append("origin event presence not checked")
        elif not behavior.origin_event_present:
            reasons.append("MISS requires a matching origin event")
        if behavior.entry_created is None:
            reasons.append("entry creation not checked")
        elif not behavior.entry_created:
            reasons.append("MISS requires a cache entry to be created")
        if reasons:
            return unknown()
        return CacheEvidenceResult(
            state="MISS",
            header_status=status,
            verified=True,
            reasons=(
                "header MISS with key and entry id; "
                "origin counter +1 with matching event; entry created",
            ),
        )

    # -- HIT -------------------------------------------------------------
    if status == "HIT":
        if _missing(header.cache_key_sha256):
            reasons.append("missing cache-key header")
        if _missing(header.entry_id):
            reasons.append("missing entry-id header")
        if behavior.origin_counter_delta is None:
            reasons.append("origin counter delta not measured")
        elif behavior.origin_counter_delta != 0:
            reasons.append(
                "HIT requires origin counter delta 0, got "
                f"{behavior.origin_counter_delta:+d}"
            )
        if behavior.entry_id_matches is None:
            reasons.append("entry-id match not checked")
        elif not behavior.entry_id_matches:
            reasons.append("HIT entry id does not match the stored entry")
        if behavior.body_hash_matches is None:
            reasons.append("body-hash match not checked")
        elif not behavior.body_hash_matches:
            reasons.append("HIT body hash does not match the stored entry")
        if reasons:
            return unknown()
        return CacheEvidenceResult(
            state="HIT",
            header_status=status,
            verified=True,
            reasons=(
                "header HIT with key and entry id; "
                "origin counter unchanged; entry id and body hash match",
            ),
        )

    # -- BYPASS ----------------------------------------------------------
    # The BYPASS header leg is the status header alone (§5.3 C;
    # acceptance text: "BYPASS: header BYPASS + origin counter +1").
    # This proxy also emits the cache key on BYPASS (§5.4), but its
    # absence is not a missing leg for BYPASS — there is no entry to
    # correlate with, and no entry id is expected either.
    if behavior.origin_counter_delta is None:
        reasons.append("origin counter delta not measured")
    elif behavior.origin_counter_delta != 1:
        reasons.append(
            "BYPASS requires origin counter delta +1, got "
            f"{behavior.origin_counter_delta:+d}"
        )
    if behavior.origin_event_present is None:
        reasons.append("origin event presence not checked")
    elif not behavior.origin_event_present:
        reasons.append("BYPASS requires a matching origin event")
    if behavior.entry_count_delta is None:
        reasons.append("entry-count delta not measured")
    elif behavior.entry_count_delta != 0:
        reasons.append(
            "BYPASS requires entry-count delta 0, got "
            f"{behavior.entry_count_delta:+d}"
        )
    if reasons:
        return unknown()
    return CacheEvidenceResult(
        state="BYPASS",
        header_status=status,
        verified=True,
        reasons=(
            "header BYPASS; origin counter +1 with matching event; "
            "entry count unchanged",
        ),
    )
```

## src/accepttwin/canonical_json.py

- SHA-256：`3f31bd8a127458801255a6e462700f489d95ba67bdd50761b71a8a0e4b7d0df4`
- 字节数：913

```
"""Canonical JSON — thin re-export of the single implementation.

Single source of truth (PROJECT_BOOK §10.4, ADR-003, T009): the only
Canonical JSON implementation is
:func:`accepttwin.contract.canonical_json_bytes` (with
:func:`accepttwin.contract.canonical_contract_hash` built on it).
This module re-exports those two names — and nothing else — so
callers that think in terms of "canonical JSON" have a stable import
path without a second implementation ever existing. No sorting,
encoding, volatile-field stripping, header normalisation or port
normalisation is implemented here: every behaviour, including the
ADR-003 loopback-port-to-0 normalisation, lives in
:mod:`accepttwin.contract` and is inherited verbatim by re-export.
"""

from __future__ import annotations

from .contract import canonical_contract_hash, canonical_json_bytes

__all__ = ["canonical_contract_hash", "canonical_json_bytes"]
```

## src/accepttwin/classifier.py

- SHA-256：`4d26dc3ba6926625c278165dd36440170637add63e93466d01aa3eb0cb59f99d`
- 字节数：41099

```
"""Production classifier (P032 T006).

Implements IMPLEMENTATION_PLAN §5.6 / T006 and PROJECT_BOOK §6.3,
§7, §8, §9, §10.2 (classification part):

* :func:`classify_run` — from a contract, the eight
  :class:`~accepttwin.evidence.RequestObservation` objects of one
  frozen four-experiment run, the origin events and the reset
  evidence, compute the five final verdicts of §9 in the §9.6
  priority order, the frozen §8 diagnostics, and the first-error
  request (§6.3).

Verdict priority (§9.6), applied literally:

1. input invalid or run out of scope → ``INCONCLUSIVE``;
2. direct-origin baseline error → ``ORIGIN_NEGOTIATION_ERROR``;
3. proven warm-cache bleed → ``REPRESENTATION_BLEED``;
4. other confirmed contract error → ``CONTRACT_MISMATCH``;
5. no problem above but key evidence insufficient → ``INCONCLUSIVE``;
6. everything conforms → ``PASS_OBSERVED``.

Fail-closed rules (the classifier never upgrades suspicion into a
proven fault):

* a bleed needs the full §8.2 chain — baseline correct, first warm
  request correct *and* a confirmed MISS, second request a verified
  HIT with counter delta 0, the same cache entry, and a body hash
  equal to the first request's body. Any missing link yields no
  bleed diagnostic at all;
* only a verified cache state (``MISS`` / ``HIT`` / ``BYPASS`` whose
  header leg and behaviour leg agree) counts as cache evidence. A
  claimed state contradicted by the origin counter is a
  ``CACHE_EVIDENCE_CONFLICT``, never a bleed and never a confirmed
  state;
* Vary alone never decides a verdict (I-11): a missing ``Vary:
  Accept`` is at most a WARNING (or a ``CONTRACT_MISMATCH`` when
  the contract *requires* it, §5.2), never a bleed;
* a lone 200 never means PASS (§9.5 needs baselines, cold requests,
  both warm orders, complete cache evidence and no CRITICAL);
* a Sentinel match alone never proves a HIT — a HIT needs the dual
  evidence of §5.3;
* when the evidence is insufficient the verdict is
  ``INCONCLUSIVE``, never a proven bleed.

Cache-policy rules (§8.9, two legs):

* under ``no_store`` a confirmed MISS (which creates an entry) or
  a confirmed HIT (which reuses one) is a
  ``CACHE_POLICY_MISMATCH``; a confirmed BYPASS is the expected
  behaviour and passes (C05/C06 shape);
* under ``variant_by_accept`` a *confirmed* BYPASS is a
  ``CACHE_POLICY_MISMATCH`` (§8.9 variant leg, ADR-002 P1-1):
  §5.4/§6.1 expect MISS there, and a BYPASS means the cache never
  stored anything, so per-representation isolation was never
  exercised. Only a BYPASS that survived dual-evidence
  verification counts — an unconfirmed BYPASS is an evidence
  problem (§8.4), never a proven policy violation. Exception
  (T008, ADR-004, §11.3 E03): a response whose ``Vary`` contains
  ``*`` must never be reused (RFC 9111 §4.1), so its BYPASS is
  compliant and exempts that request from this leg.

* a response carrying ``Cache-Control: no-cache`` or ``max-age=0``
  is out of scope (§8.6 ``revalidation_required``, T008, ADR-004,
  §11.3 E07/E08): the first release implements no revalidation, so
  the run is ``INCONCLUSIVE``, never PASS.

Vary fail-closed rule (§5.2, §9.6 step 5; ADR-002 P2-1): when the
contract requires ``Vary: Accept`` (``vary_accept == "required"``)
and whether Vary is present is *unknown* — neither
``raw_observations`` nor ``vary_accept_present`` was supplied, so
no Vary header was ever inspected — the run is ``INCONCLUSIVE``,
never PASS: the contract's own required evidence is missing, and
§5.2 states a missing ``Vary: Accept`` under ``required`` is a
contract violation, which cannot be ruled out without looking.
When Vary is known-absent under ``required`` the verdict is
``CONTRACT_MISMATCH`` instead (the violation is confirmed).

Calling convention for the optional evidence (ADR-002 P2-2,
route B): ``origin_events=None`` / ``reset_evidence=None`` mean
"the caller declares this cross-check is not performed" — the
classifier skips that check, it does *not* treat it as confirmed.
That meaning is reserved for unit tests; a production caller
(T007) must always pass the real ``run.origin_events`` /
``run.reset_evidence`` tuples and never pass ``None``. An empty
list/tuple is different: it means "the caller performed the check
and found nothing", which fails closed (no origin event →
``CACHE_STATE_UNKNOWN``; no reset recorded → ``CACHE_STATE_UNKNOWN``).

Body-size limit (§8.6, §17.4 1 MiB): the oversize-body check can
only run when ``raw_observations`` is supplied, because the frozen
:class:`RequestObservation` carries no body size. A production
caller (T007) must pass ``run.raw_observations``; without it that
one check cannot execute, and the classifier records this in the
module docstring and ADR-002 rather than guessing a size.

First-error location (§6.3): ``first_error`` is the smallest
request number (execution order 001–008) carrying any diagnostic
other than the advisory ``VARY_ACCEPT_ABSENT``. Diagnostics are
never re-ordered by severity and a later, more severe error never
rewrites the history: an origin-baseline error at 001/002 always
wins over a later cache problem, and secondary diagnostics are kept
alongside the final verdict, not hidden (§9.6).

Inputs beyond the frozen §5.6 signature are optional keyword-only
extensions, never requirements:

* ``raw_observations`` — the richer
  :class:`~accepttwin.evidence.RawObservation` records from the
  same run. They supply what :class:`RequestObservation` cannot
  carry: the ``Vary`` response header (for §8.7), the body size
  (for the §17.4 1 MiB limit), transport errors, and the raw
  cache-status header (to distinguish a header/behaviour conflict
  from merely missing evidence). Without them those three checks
  are skipped, never guessed. The body-size check has no other
  source at all, so a production caller (T007) **must** pass
  ``run.raw_observations`` — otherwise that check cannot execute
  (ADR-002 P2-1 note).
* ``vary_accept_present`` — an explicit per-request ``Vary:
  Accept`` map, an alternative to ``raw_observations`` for the
  §8.7 check.

``cache_status is None`` on a baseline request means "direct-origin
request, no cache evidence exists" (ADR-001) and is never read as a
cache state, never inferred from, and never conflated with
``"CACHE_STATE_UNKNOWN"``. A ``None`` on a *proxied* request is a
missing evidence leg (§8.4).

No body text is ever read, stored or emitted here (§7.12 I-12):
only hashes, statuses, counters and match flags.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .contract import Contract, Representation, validate_contract
from .diagnostics import (
    Diagnostic,
    check_bleed,
    check_cache_state,
    check_contract_response,
    check_inconclusive_limit,
    check_no_store_policy,
    check_origin_baseline,
    check_reset_evidence,
    check_sentinel,
    check_unexpected_hit,
    check_variant_by_accept_policy,
    check_vary,
    make_diagnostic,
    sort_diagnostics,
)
from .evidence import RawObservation, RequestObservation

__all__ = [
    "ClassificationResult",
    "VERDICTS",
    "classify_run",
]

#: The five frozen final verdicts (§9), in §9.6 priority order.
VERDICTS: tuple[str, ...] = (
    "INCONCLUSIVE",
    "ORIGIN_NEGOTIATION_ERROR",
    "REPRESENTATION_BLEED",
    "CONTRACT_MISMATCH",
    "PASS_OBSERVED",
)

#: Request numbers of the direct-origin baselines (§6.3).
_BASELINE_REQUESTS = (1, 2)

#: Request numbers of the cold requests (§6.3).
_COLD_REQUESTS = (3, 4)

#: (first, second) request numbers of the two warm experiments (§6.3).
_WARM_PAIRS = ((5, 6), (7, 8))

#: Request numbers of the warm first requests.
_WARM_FIRST_REQUESTS = (5, 7)

#: Request numbers of the warm second requests.
_WARM_SECOND_REQUESTS = (6, 8)

#: Expected number of observations in one complete run (§6.3: 001–008).
_EXPECTED_OBSERVATIONS = 8


@dataclass(frozen=True)
class ClassificationResult:
    """The outcome of classifying one complete run (§9, §6.3).

    ``diagnostics`` are in deterministic order
    (:func:`accepttwin.diagnostics.sort_diagnostics`). ``first_error``
    is the smallest request number carrying a violation diagnostic
    (any diagnostic except the advisory ``VARY_ACCEPT_ABSENT``), or
    ``None`` when no request violated the contract;
    ``first_error_experiment_id`` is that request's experiment.
    ``reasons`` explains, in verdict-priority order, why this
    verdict was reached. Nothing here carries body text (§7.12).
    ``confirmed_cache_states`` is the per-request cache state the
    classifier was willing to trust (T014, T013-F02): one
    ``{"request_index": n, "state": ...}`` entry per observation,
    with ``state`` the confirmed ``"MISS"`` / ``"HIT"`` /
    ``"BYPASS"`` or ``None`` when nothing was confirmed (baselines
    carry ``None`` per ADR-001). The Oracle parity check compares
    this list against the Oracle's own per-request states.
    """

    verdict: str
    diagnostics: tuple[Diagnostic, ...] = ()
    first_error: int | None = None
    first_error_experiment_id: str | None = None
    reasons: tuple[str, ...] = ()
    confirmed_cache_states: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"unknown verdict {self.verdict!r}")
        if self.first_error is not None and self.first_error < 1:
            raise ValueError("first_error must be a positive request number")

    @property
    def critical_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "CRITICAL")

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == "WARNING")

    def diagnostic_codes(self) -> tuple[str, ...]:
        return tuple(d.code for d in self.diagnostics)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "diagnostics": [d.as_dict() for d in self.diagnostics],
            "first_error": self.first_error,
            "first_error_experiment_id": self.first_error_experiment_id,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "reasons": list(self.reasons),
            "confirmed_cache_states": [
                dict(entry) for entry in self.confirmed_cache_states
            ],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sentinel_sha256(sentinel: str) -> str:
    return hashlib.sha256(sentinel.encode("utf-8")).hexdigest()


def _vary_accept_present(headers: dict[str, str] | None) -> bool | None:
    """True when the response headers declare ``Vary: Accept``.

    Returns None when no header map was supplied (unknown, not
    absent). Header names are matched case-insensitively; the Vary
    value is split on commas and matched token-wise, so ``Vary:
    accept`` and ``Vary: Accept, Accept-Encoding`` both count.
    """
    if headers is None:
        return None
    for name, value in headers.items():
        if name.strip().lower() == "vary":
            tokens = [tok.strip().lower() for tok in value.split(",")]
            return "accept" in tokens or "*" in tokens
    return False


def _header_value(
    raw: RawObservation | None, name: str
) -> str | None:
    """Value of response header *name* (case-insensitive) from a raw
    observation, or None when no raw record was supplied or the
    header is absent. None means "unknown", never "absent".
    """
    if raw is None:
        return None
    for key, value in raw.response_headers.items():
        if key.strip().lower() == name.strip().lower():
            return value
    return None


def _requires_revalidation(raw: RawObservation | None) -> bool:
    """True when a raw response demands revalidation this release
    does not implement (§8.6, PROJECT_BOOK §11.3 E07/E08).

    ``Cache-Control: no-cache`` or ``max-age=0`` on a response means
    a cached copy must be revalidated before reuse; the first
    release implements no revalidation, so any run containing such a
    response is out of scope (``INCONCLUSIVE_LIMIT`` with limit code
    ``revalidation_required``), never PASS. Only the raw response
    headers can supply this — without a raw record the check cannot
    run and is skipped, never guessed.
    """
    cache_control = _header_value(raw, "cache-control")
    if cache_control is None:
        return False
    for token in cache_control.split(","):
        directive = token.strip().lower()
        if not directive:
            continue
        # RFC 9111-tolerant parsing (T014, T008 P2-2): whitespace
        # around the '=' and quoted-string parameters are stripped,
        # so `max-age = 0`, `max-age="0"` and `no-cache="field"` are
        # recognised exactly like their compact forms. A `no-cache`
        # directive triggers with or without a field-name parameter
        # (this release implements no revalidation at all, so any
        # revalidation demand is out of scope).
        name, sep, value = directive.partition("=")
        name = name.strip()
        value = value.strip().strip("\"'").strip()
        if name == "no-cache":
            return True
        if name == "max-age" and sep:
            try:
                if int(value) == 0:
                    return True
            except ValueError:
                continue
    return False


def _events_support(
    observation: RequestObservation,
    origin_events: list[Any] | tuple[Any, ...] | None,
    expected_accept: str,
) -> bool | None:
    """Cross-check one observation against the origin event log.

    The origin's event ``index`` equals its request counter after
    the request (§5.3: one event per request received), so the
    events belonging to *observation* are exactly those with an
    index in ``(origin_counter_before, origin_counter_after]``.
    Returns True when at least one such event carries the expected
    Accept and status, False when the bracket is non-empty but no
    event matches (or the bracket should be non-empty but holds no
    event at all), and None when the check does not apply (no event
    log supplied, or the observation reached no origin request, so
    no event is expected). A False here means the behaviour leg is
    missing — it downgrades the cache state to UNKNOWN, it never
    invents a state.
    """
    if origin_events is None:
        return None
    if observation.origin_counter_delta <= 0:
        return None
    bracket = [
        ev
        for ev in origin_events
        if observation.origin_counter_before
        < getattr(ev, "index", -1)
        <= observation.origin_counter_after
    ]
    if not bracket:
        return False
    return any(
        getattr(ev, "accept", None) == expected_accept
        and getattr(ev, "status", None) == observation.response_status
        for ev in bracket
    )


def _representation_correct(
    observation: RequestObservation, rep: Representation
) -> bool:
    return (
        observation.response_status == rep.expected_status
        and observation.response_content_type.strip().lower()
        == rep.expected_content_type.strip().lower()
        and observation.sentinel_match
    )


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


def classify_run(
    contract: Contract,
    observations: list[RequestObservation] | tuple[RequestObservation, ...],
    origin_events: list[Any] | tuple[Any, ...] | None,
    reset_evidence: list[Any] | tuple[Any, ...] | None,
    *,
    raw_observations: list[RawObservation] | tuple[RawObservation, ...] | None = None,
    vary_accept_present: dict[int, bool] | None = None,
) -> ClassificationResult:
    """Classify one complete four-experiment run (§9.6 priority).

    *contract* is the frozen dual-representation contract,
    *observations* the eight §5.5 observations in any order (they
    are sorted by request number here), *origin_events* the origin
    event log for the run, *reset_evidence* the four reset records.
    ``None`` for *origin_events* / *reset_evidence* means "the
    caller declares this cross-check is not performed" and the
    check is skipped — that meaning is reserved for unit tests
    (ADR-002 P2-2, route B); a production caller (T007) must pass
    the real ``run.origin_events`` / ``run.reset_evidence`` tuples
    and never pass ``None``. An empty list/tuple means "checked and
    found nothing" and fails closed (no origin event or no reset
    recorded → ``CACHE_STATE_UNKNOWN``). Optional
    ``raw_observations`` / ``vary_accept_present`` supply Vary,
    body-size, transport and raw-header detail the frozen
    observation cannot carry (see the module docstring); without
    them those checks are skipped, never guessed — except that a
    ``vary_accept == "required"`` contract with unknown Vary
    presence fails closed to ``INCONCLUSIVE`` (§9.6 step 5), and
    the §8.6 body-size check cannot run at all without
    ``raw_observations``, so T007 must pass
    ``run.raw_observations``.
    """
    diagnostics: list[Diagnostic] = []
    reasons: list[str] = []

    # -- §9.6 step 1: input validity ------------------------------------
    contract_result = validate_contract(contract)
    if not contract_result.ok:
        reasons.append("contract is invalid")
        diagnostics.append(
            make_diagnostic(
                "INCONCLUSIVE_LIMIT",
                "contract is invalid: " + "; ".join(contract_result.errors),
                evidence={
                    "limit_code": "invalid_contract",
                    "detail": "; ".join(contract_result.errors),
                },
            )
        )
        return _finish(
            "INCONCLUSIVE", diagnostics, reasons, observations_by_index={}
        )

    obs_list = list(observations or [])
    indices = [obs.request_index for obs in obs_list]
    if (
        len(obs_list) != _EXPECTED_OBSERVATIONS
        or sorted(indices) != list(range(1, _EXPECTED_OBSERVATIONS + 1))
        or len(set(indices)) != len(indices)
    ):
        reasons.append("observations are incomplete")
        diagnostics.append(
            make_diagnostic(
                "INCONCLUSIVE_LIMIT",
                "observations are incomplete: expected exactly requests "
                f"001–{_EXPECTED_OBSERVATIONS:03d} once each, got "
                f"{sorted(indices)}",
                evidence={"limit_code": "incomplete_observations"},
            )
        )
        return _finish(
            "INCONCLUSIVE", diagnostics, reasons, observations_by_index={}
        )

    by_index: dict[int, RequestObservation] = {
        obs.request_index: obs for obs in obs_list
    }
    by_raw: dict[int, RawObservation] = {}
    if raw_observations:
        for raw in raw_observations:
            by_raw.setdefault(raw.request_index, raw)

    mode = contract.cache_behavior.get("mode", "variant_by_accept")
    vary_mode = contract.cache_behavior.get("vary_accept", "advisory")
    vary_required = vary_mode == "required"
    cacheable = mode == "variant_by_accept"
    max_body = int(contract.limits.get("max_body_bytes", 1048576))

    def rep_for(obs: RequestObservation) -> Representation | None:
        return contract.representations.get(
            obs.requested_representation.strip().lower()
        )

    # -- per-request out-of-scope checks (§8.6, §9.6 step 1) -------------
    out_of_scope = False
    for index in sorted(by_index):
        obs = by_index[index]
        rep = rep_for(obs)
        if rep is None:
            diagnostics.append(
                make_diagnostic(
                    "INCONCLUSIVE_LIMIT",
                    f"request {index:03d} asks for unknown representation "
                    f"{obs.requested_representation!r}",
                    experiment_id=obs.experiment_id,
                    request_index=index,
                    evidence={"limit_code": "unknown_representation"},
                )
            )
            out_of_scope = True
            continue
        raw = by_raw.get(index)
        body_size = raw.body_size if raw is not None else None
        transport_error = raw.transport_error if raw is not None else None
        limit_code = ""
        detail = ""
        if transport_error is not None:
            limit_code = "transport_error"
            detail = transport_error
        elif obs.response_status == 0:
            limit_code = "transport_error"
            detail = "no HTTP response was received"
        elif 300 <= obs.response_status < 400:
            limit_code = "redirect"
            detail = (
                f"status {obs.response_status} (redirects are not "
                "followed in this release)"
            )
        elif body_size is not None and body_size > max_body:
            limit_code = "body_too_large"
            detail = (
                f"body size {body_size} exceeds the {max_body} byte limit"
            )
        elif _requires_revalidation(raw):
            limit_code = "revalidation_required"
            detail = (
                "response requires revalidation "
                f"(Cache-Control: {_header_value(raw, 'cache-control')}), "
                "which this release does not implement"
            )
        if limit_code:
            diagnostics.append(
                check_inconclusive_limit(
                    request_index=index,
                    experiment_id=obs.experiment_id,
                    limit_code=limit_code,
                    response_status=obs.response_status,
                    body_size=body_size,
                    supported_limit=max_body,
                    transport_error=transport_error,
                    detail=detail,
                    # §8.6 evidence (P2-3): the URL only exists on
                    # the raw record — the frozen observation has
                    # no URL field, so without raw records it stays
                    # unknown (ADR-002) rather than guessed.
                    request_url=raw.url if raw is not None else None,
                    redirect_target=(
                        _header_value(raw, "location")
                        if limit_code == "redirect"
                        else None
                    ),
                )
            )
            out_of_scope = True

    # -- reset evidence (§8.4, §11.2 C23) ---------------------------------
    reset_diagnostic = check_reset_evidence(reset_evidence)
    reset_confirmed = reset_diagnostic is None
    if reset_diagnostic is not None:
        diagnostics.append(reset_diagnostic)

    # -- cache-state verification per proxied request (§5.3, §8.4/§8.8) --
    # ``confirmed_state`` records the cache state the classifier is
    # willing to trust for downstream checks (bleed, policy). Any
    # observation whose state did not survive verification maps to
    # None here: downstream checks treat it as "unknown", never as
    # the claimed state.
    confirmed_state: dict[int, str | None] = {}
    for index in sorted(by_index):
        obs = by_index[index]
        if index in _BASELINE_REQUESTS:
            # ADR-001: direct-origin baselines carry None — no cache
            # evidence exists and none is required.
            confirmed_state[index] = None
            continue
        rep = rep_for(obs)
        if rep is None:
            confirmed_state[index] = None
            continue
        raw = by_raw.get(index)
        event_support = _events_support(
            obs, origin_events, rep.accept
        )
        diag = check_cache_state(
            request_index=index,
            experiment_id=obs.experiment_id,
            cache_status=obs.cache_status,
            origin_counter_delta=obs.origin_counter_delta,
            cache_key_sha256=obs.cache_key_sha256,
            cache_entry_id=obs.cache_entry_id,
            header_status=raw.cache_status_header if raw is not None else None,
            origin_event_present=(
                raw.origin_event_present if raw is not None else None
            ),
            cache_reset_confirmed=reset_confirmed,
        )
        if diag is not None:
            diagnostics.append(diag)
            confirmed_state[index] = None
            continue
        if event_support is False:
            diagnostics.append(
                make_diagnostic(
                    "CACHE_STATE_UNKNOWN",
                    f"request {index:03d} claims {obs.cache_status} but "
                    "no matching origin event exists for it",
                    experiment_id=obs.experiment_id,
                    request_index=index,
                    evidence={
                        "cache_status": obs.cache_status,
                        "origin_counter_delta": obs.origin_counter_delta,
                        "cache_key_sha256": obs.cache_key_sha256,
                        "cache_entry_id": obs.cache_entry_id,
                        # §8.4 evidence fields (P2-3).
                        "proxy_cache_header_present": (
                            raw.cache_status_header is not None
                            if raw is not None
                            else None
                        ),
                        # T014 (T006 P3): this branch is only reachable
                        # when origin_events is not None (see the
                        # guard above), so the journal is available
                        # by construction — write the literal True
                        # instead of a condition that is constant
                        # here.
                        "origin_journal_available": True,
                        "cache_reset_confirmed": reset_confirmed,
                        "evidence_conflict": False,
                    },
                )
            )
            confirmed_state[index] = None
            continue
        confirmed_state[index] = obs.cache_status

    # -- origin baselines (§8.1, §9.1) ------------------------------------
    baseline_correct = True
    origin_error = False
    for index in _BASELINE_REQUESTS:
        obs = by_index[index]
        rep = rep_for(obs)
        if rep is None:
            baseline_correct = False
            continue
        correct = _representation_correct(obs, rep)
        baseline_correct = baseline_correct and correct
        if obs.response_status == 0 or 300 <= obs.response_status < 400:
            # Out of scope (already diagnosed as INCONCLUSIVE_LIMIT);
            # a redirect/transport failure is not also an origin
            # negotiation error, but the baseline is not correct
            # either, so no bleed can be proven from this run.
            baseline_correct = False
            continue
        diag = check_origin_baseline(
            request_index=index,
            experiment_id=obs.experiment_id,
            requested_representation=obs.requested_representation,
            response_status=obs.response_status,
            response_content_type=obs.response_content_type,
            sentinel_match=obs.sentinel_match,
            expected_status=rep.expected_status,
            expected_content_type=rep.expected_content_type,
            expected_sentinel_sha256=_sentinel_sha256(rep.sentinel),
            body_sha256=obs.body_sha256,
        )
        if diag is not None:
            diagnostics.append(diag)
            origin_error = True

    # -- Sentinel, status and Content-Type per request (§8.3, §8.5) -------
    contract_error = False
    for index in sorted(by_index):
        obs = by_index[index]
        rep = rep_for(obs)
        if rep is None:
            continue
        if 300 <= obs.response_status < 400 or obs.response_status == 0:
            # Out of scope (already diagnosed); a redirect/transport
            # failure carries no meaningful Sentinel or contract
            # content to judge, so neither check runs here.
            continue
        diag = check_sentinel(
            request_index=index,
            experiment_id=obs.experiment_id,
            requested_representation=obs.requested_representation,
            sentinel_match=obs.sentinel_match,
            response_content_type=obs.response_content_type,
            expected_sentinel_sha256=_sentinel_sha256(rep.sentinel),
            body_sha256=obs.body_sha256,
        )
        if diag is not None:
            diagnostics.append(diag)
            contract_error = True
        if index in _BASELINE_REQUESTS:
            continue
        diag = check_contract_response(
            request_index=index,
            experiment_id=obs.experiment_id,
            requested_representation=obs.requested_representation,
            response_status=obs.response_status,
            response_content_type=obs.response_content_type,
            cache_status=obs.cache_status,
            sentinel_match=obs.sentinel_match,
            expected_status=rep.expected_status,
            expected_content_type=rep.expected_content_type,
        )
        if diag is not None:
            diagnostics.append(diag)
            contract_error = True

    # -- cache-policy and unexpected-HIT checks (§8.9, §8.3) --------------
    policy_error = False
    for index in sorted(by_index):
        obs = by_index[index]
        if index in _BASELINE_REQUESTS:
            continue
        rep = rep_for(obs)
        if rep is None:
            continue
        state = confirmed_state[index]
        raw = by_raw.get(index)
        if mode == "no_store":
            diag = check_no_store_policy(
                request_index=index,
                experiment_id=obs.experiment_id,
                cache_status=state,
                cache_entry_count_before=(
                    raw.cache_entry_count_before if raw is not None else None
                ),
                cache_entry_count_after=(
                    raw.cache_entry_count_after if raw is not None else None
                ),
                cache_entry_id=obs.cache_entry_id,
                cache_control=_header_value(raw, "cache-control"),
            )
            if diag is not None:
                diagnostics.append(diag)
                policy_error = True
        elif cacheable and state == "BYPASS":
            # P1-1 (§8.9 variant leg): a confirmed BYPASS under
            # variant_by_accept means the cache never stored
            # anything, so isolation was never exercised — a
            # CACHE_POLICY_MISMATCH, never a silent PASS. Only the
            # *confirmed* state reaches this branch: an unconfirmed
            # BYPASS is already a §8.4 evidence problem above.
            diag = check_variant_by_accept_policy(
                request_index=index,
                experiment_id=obs.experiment_id,
                cache_status=state,
                cache_entry_count_before=(
                    raw.cache_entry_count_before if raw is not None else None
                ),
                cache_entry_count_after=(
                    raw.cache_entry_count_after if raw is not None else None
                ),
                cache_entry_id=obs.cache_entry_id,
                cache_control=_header_value(raw, "cache-control"),
                # Vary: * exempts the BYPASS (ADR-004, §11.3 E03):
                # a response that must never be reused is compliant
                # when it is not stored.
                vary=_header_value(raw, "vary"),
            )
            if diag is not None:
                diagnostics.append(diag)
                policy_error = True
        elif cacheable and state == "HIT" and reset_confirmed:
            # A confirmed HIT where no entry could exist yet (cold,
            # warm-first) or where the served representation is the
            # requested one (warm-second, correct body) contradicts
            # the cold-cache premise. A HIT serving the *wrong*
            # representation is the bleed check's job, not this one.
            diag = check_unexpected_hit(
                request_index=index,
                experiment_id=obs.experiment_id,
                requested_representation=obs.requested_representation,
                cache_status=state,
                response_status=obs.response_status,
                response_content_type=obs.response_content_type,
                sentinel_match=obs.sentinel_match,
                expected_status=rep.expected_status,
                expected_content_type=rep.expected_content_type,
                reset_confirmed=reset_confirmed,
            )
            if diag is not None:
                diagnostics.append(diag)
                contract_error = True

    # -- warm-cache bleed (§8.2, §9.2) -------------------------------------
    bleed = False
    for first_index, second_index in _WARM_PAIRS:
        first = by_index[first_index]
        second = by_index[second_index]
        first_rep = rep_for(first)
        second_rep = rep_for(second)
        if first_rep is None or second_rep is None:
            continue
        first_correct = _representation_correct(first, first_rep)
        diag = check_bleed(
            first_request_index=first_index,
            second_request_index=second_index,
            experiment_id=second.experiment_id,
            baseline_correct=baseline_correct,
            first_correct=first_correct,
            first_cache_status=confirmed_state[first_index],
            first_cache_entry_id=first.cache_entry_id,
            first_body_sha256=first.body_sha256,
            second_cache_status=confirmed_state[second_index],
            second_cache_entry_id=second.cache_entry_id,
            second_cache_key_sha256=second.cache_key_sha256,
            second_body_sha256=second.body_sha256,
            second_response_content_type=second.response_content_type,
            second_origin_counter_before=second.origin_counter_before,
            second_origin_counter_after=second.origin_counter_after,
            second_origin_counter_delta=second.origin_counter_delta,
            second_sentinel_match=second.sentinel_match,
            first_expected_content_type=first_rep.expected_content_type,
            requested_representation=second.requested_representation,
        )
        if diag is not None:
            diagnostics.append(diag)
            bleed = True

    # -- Vary (§8.7, I-11) --------------------------------------------------
    # Only the origin baselines declare Vary; only cacheable contracts
    # care. A missing Vary is never invented: when neither an explicit
    # map nor a raw record supplies the header, presence is unknown.
    # The explicit map wins when it has a value; the raw headers are
    # the fallback when the map is silent for a request.
    vary_map: dict[int, bool | None] = {}
    for index in _BASELINE_REQUESTS:
        present: bool | None = None
        if vary_accept_present is not None:
            present = vary_accept_present.get(index)
        if present is None and index in by_raw:
            present = _vary_accept_present(by_raw[index].response_headers)
        vary_map[index] = present
    vary_unknown_required = False
    for index in _BASELINE_REQUESTS:
        present = vary_map[index]
        if present is None:
            if vary_required and cacheable:
                # P2-1 fail-closed (§5.2, §9.6 step 5): the contract
                # requires Vary: Accept, but no Vary header was ever
                # inspected for this baseline, so the required
                # violation can neither be confirmed nor ruled out.
                # The run is INCONCLUSIVE, never PASS.
                obs = by_index[index]
                diagnostics.append(
                    check_inconclusive_limit(
                        request_index=index,
                        experiment_id=obs.experiment_id,
                        limit_code="vary_accept_unknown",
                        detail=(
                            "contract requires Vary: Accept but no "
                            "Vary header was supplied for this "
                            "baseline (neither raw_observations nor "
                            "vary_accept_present); the required "
                            "evidence is missing"
                        ),
                    )
                )
                vary_unknown_required = True
            continue
        obs = by_index[index]
        rep = rep_for(obs)
        if rep is None:
            continue
        diag = check_vary(
            request_index=index,
            experiment_id=obs.experiment_id,
            requested_representation=obs.requested_representation,
            vary_accept_present=present,
            vary_accept_required=vary_required,
            cacheable=cacheable,
        )
        if diag is not None:
            diagnostics.append(diag)
            if diag.code == "CONTRACT_MISMATCH":
                contract_error = True

    # -- verdict (§9.6 priority, applied literally) ------------------------
    ordered = sort_diagnostics(diagnostics)
    evidence_insufficient = (
        any(
            d.code in ("CACHE_STATE_UNKNOWN", "CACHE_EVIDENCE_CONFLICT")
            for d in ordered
        )
        or vary_unknown_required
    )
    if out_of_scope:
        verdict = "INCONCLUSIVE"
        reasons.append("run left the supported range (redirect, "
                       "transport failure, oversize body, revalidation "
                       "required, or unknown representation)")
    elif origin_error:
        verdict = "ORIGIN_NEGOTIATION_ERROR"
        reasons.append("a direct-origin baseline violates the contract")
    elif bleed:
        verdict = "REPRESENTATION_BLEED"
        reasons.append("a warm-cache second request was served the other "
                       "representation from a verified HIT")
    elif contract_error or policy_error:
        verdict = "CONTRACT_MISMATCH"
        reasons.append("a response violates the contract but is neither a "
                       "proven origin error nor a proven bleed")
    elif evidence_insufficient:
        verdict = "INCONCLUSIVE"
        if vary_unknown_required:
            reasons.append(
                "the contract requires Vary: Accept but whether any "
                "baseline declares it is unknown — the required "
                "evidence was never supplied"
            )
        else:
            reasons.append("key cache evidence is missing or conflicting")
    else:
        verdict = "PASS_OBSERVED"
        reasons.append("baselines, cold requests and both warm orders are "
                       "correct with complete cache evidence and no "
                       "CRITICAL diagnostic")

    return _finish(
        verdict,
        list(ordered),
        reasons,
        observations_by_index=by_index,
        confirmed_state=confirmed_state,
    )


def _finish(
    verdict: str,
    diagnostics: list[Diagnostic],
    reasons: list[str],
    *,
    observations_by_index: dict[int, RequestObservation],
    confirmed_state: dict[int, str | None] | None = None,
) -> ClassificationResult:
    """Sort diagnostics, locate the first error (§6.3), build the result."""
    ordered = sort_diagnostics(diagnostics)
    first_error: int | None = None
    first_error_experiment_id: str | None = None
    for diag in ordered:
        # The advisory Vary warning is not a contract violation: a
        # healthy run carrying only that WARNING has no first error.
        if diag.code == "VARY_ACCEPT_ABSENT":
            continue
        if diag.request_index is not None:
            first_error = diag.request_index
            obs = observations_by_index.get(diag.request_index)
            first_error_experiment_id = (
                obs.experiment_id if obs is not None else diag.experiment_id
            )
            break
    return ClassificationResult(
        verdict=verdict,
        diagnostics=ordered,
        first_error=first_error,
        first_error_experiment_id=first_error_experiment_id,
        reasons=tuple(reasons),
        # T014 (T013-F02): expose the per-request states the
        # classifier trusted, normalised the same way as the Oracle
        # side ("CACHE_STATE_UNKNOWN" means "confirmed nothing").
        # Early returns (invalid contract / incomplete observations)
        # have no per-request verification yet, so they carry none.
        confirmed_cache_states=tuple(
            {
                "request_index": index,
                "state": (
                    None
                    if state in (None, "CACHE_STATE_UNKNOWN")
                    else state
                ),
            }
            for index, state in sorted((confirmed_state or {}).items())
        ),
    )
```

## src/accepttwin/cli.py

- SHA-256：`4fce15d80a8d269b1dc74603c1f09563dbd29c2db20d94fbf85b03e39934cd20`
- 字节数：54409

```
"""AcceptTwin command-line interface (P032 T012, extended P1-01 FIX-R1).

Thin delegation layer only — this module contains **no** Golden
execution, classification, Oracle, report-generation or HTML-embedding
logic of its own. Every subcommand calls the existing, already
reviewed implementation and reports its verdict:

* ``verify --suite`` -> ``scripts/run_s0.py`` (S0 gate, C01-C24 +
  Oracle parity + stable-bleed reproduction + repeat-100) and/or
  ``scripts/run_all_48.py`` (48-scenario Golden + Oracle parity).
* ``verify --report`` -> ``scripts/embed_report.py``'s report loader
  (independent Schema validation + report-hash recomputation) plus
  the :mod:`accepttwin.privacy` report scan; it verifies a report
  file, it never re-runs an experiment.
* ``run`` -> :mod:`accepttwin.experiment_runner` (frozen four
  experiments, real HTTP), :mod:`accepttwin.classifier`, the
  independent Oracle via ``scripts/s0_harness.py``, and
  :mod:`accepttwin.report_builder` for the formal report.
* ``demo`` -> the same ``run`` pipeline twice on the bundled
  ``contracts/site.json`` template (healthy, then a deliberate
  bleed), with HTML export for both runs.
* ``benchmark`` -> ``scripts/run_all_48.py`` for the 48 per-scenario
  timings, then a fresh 100-run repeat of C01 through
  ``scripts/s0_harness.run_scenario`` (fresh origin/proxy pair and
  fresh OS-assigned ports on every run — a hash that depended on a
  port could not pass), then ``scripts/build_reports_48.py`` (formal
  ``accepttwin.report/v1`` samples, independently Schema-validated)
  and ``scripts/embed_report.py --all-48`` (49 self-contained HTML
  pages), cross-checked with :mod:`accepttwin.privacy`.
* ``report preview`` / ``report export`` -> ``scripts/embed_report.py``
  (privacy preview first, per PROJECT_BOOK §4.2 constraint 7 and
  §17.3; export writes nothing before the preview is printed).
* ``report delete`` / ``contract delete`` / ``clean`` ->
  :mod:`accepttwin.privacy` workspace-bounded deletion (T011 rules:
  explicitly named regular files inside the workspace, never a
  symlink, never a directory, never outside the workspace; one bad
  target blocks the whole batch).

Canonical JSON is never re-implemented here: every hash check goes
through :func:`accepttwin.contract.canonical_json_bytes` (the single
source of truth, ADR-003; :mod:`accepttwin.canonical_json` is its
thin re-export).

Usage (from the repository root, with the frozen ``.venv``)::

    .venv/bin/python -m accepttwin verify --suite all
    .venv/bin/python -m accepttwin verify --suite s0
    .venv/bin/python -m accepttwin verify --report output/runs/demo-healthy/report.json
    .venv/bin/python -m accepttwin run --contract contracts/site.json
    .venv/bin/python -m accepttwin demo
    .venv/bin/python -m accepttwin report preview output/runs/demo-healthy/report.json
    .venv/bin/python -m accepttwin report export output/runs/demo-healthy/report.json
    .venv/bin/python -m accepttwin benchmark --suite all

Exit codes: 0 = the named command succeeded (for ``run``/``demo``
that means the run completed *and* Oracle parity held, so the
report is final — the verdict itself is data and is printed, not
gated: a real REPRESENTATION_BLEED finding still exits 0, because
the tool did its job; for ``verify --report`` it means the report
file is valid, its hash matches, and Oracle parity holds, whatever
its verdict says); 1 = the command ran but its gate failed (Oracle
parity mismatch, invalid report, infrastructure failure); 2 = bad
arguments or bad user input (missing file, invalid contract,
non-loopback URL, refused deletion). No subcommand ever declares
PASS on its own say-so: the exit code follows the underlying
``*_STATUS`` / parity / ``final`` field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
import time
from pathlib import Path

from accepttwin import __version__
from accepttwin.cache_proxy import ControlledCacheProxy
from accepttwin.classifier import classify_run
from accepttwin.contract import ContractError, load_contract, parse_contract
from accepttwin.experiment_runner import ExperimentError, run_experiments
from accepttwin.origin_server import SyntheticOrigin, load_scenario
from accepttwin.privacy import (
    PrivacyError,
    assert_report_clean,
    delete_evidence_files,
    resolve_cleanup_target,
    scan_html_for_remote_resources,
)
from accepttwin.report_builder import build_report, compute_report_hash

# ---------------------------------------------------------------------------
# Locating the already-reviewed script implementations
# ---------------------------------------------------------------------------


def find_repo_root() -> Path:
    """Repository root: the ancestor holding ``scripts/run_all_48.py``.

    Works for the source checkout (``src/accepttwin/cli.py`` -> root
    is two levels up) and for an installed copy run from anywhere
    inside the checkout. Raises a plain error — never a guess — if
    the scripts cannot be found.
    """
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "scripts" / "run_all_48.py").is_file():
            return parent
    cwd = Path.cwd()
    for parent in (cwd, *cwd.parents):
        if (parent / "scripts" / "run_all_48.py").is_file():
            return parent
    raise RuntimeError(
        "cannot locate the AcceptTwin repository root "
        "(no scripts/run_all_48.py found above "
        f"{here} or {cwd}); run from a checkout"
    )


def _load_script_modules(root: Path) -> dict[str, object]:
    """Import the script modules by file path (``scripts/`` is not a
    package). Each module is imported once and reused; nothing in
    them is copied here."""
    import importlib.util

    scripts_dir = root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    if str(root / "src") not in sys.path:
        sys.path.insert(0, str(root / "src"))
    modules: dict[str, object] = {}
    for name in ("run_s0", "run_all_48", "build_reports_48", "embed_report", "s0_harness"):
        spec = importlib.util.spec_from_file_location(name, scripts_dir / f"{name}.py")
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load scripts/{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault(name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


#: Canonical-JSON fields that must never appear (§10.4). Checked as
#: raw byte substrings of the canonical bytes, so a nested or
#: renamed occurrence cannot slip past a key-level scan.
FORBIDDEN_CANONICAL_SUBSTRINGS: tuple[bytes, ...] = (
    b"generated_at",
    b"duration_ms",
    b"process_id",
    b"temporary_path",
    b"ephemeral_port",
    b"timestamp",
    b"uuid",
    b"random",
)

#: The six controlled proxy modes (PROJECT_BOOK §10.3). A ``run``
#: derives its default from the contract's ``cache_behavior.mode``
#: (see below) and the caller may override it explicitly — a
#: fault-injection mode against a healthy contract is exactly how a
#: bleed is demonstrated on purpose.
PROXY_MODES: tuple[str, ...] = (
    "respect_vary",
    "force_uri_only",
    "manual_accept_key",
    "disabled",
    "opaque",
    "ignore_no_store",
)

#: Default proxy mode per contract ``cache_behavior.mode`` (§5.2).
DEFAULT_PROXY_MODE_BY_CONTRACT_MODE: dict[str, str] = {
    "variant_by_accept": "respect_vary",
    "no_store": "disabled",
}

#: Report ``scenario_id`` for a user run (P1-01). The frozen v1
#: report Schema only accepts ``^[CE][0-9]{2}$``, so a user run is
#: filed under the Golden configuration it reproduces — this label
#: records the *configuration*, not Golden membership. The run's
#: real identity is its ``contract_id`` + ``contract_sha256`` +
#: ``run-id``, recorded in ``run-summary.json`` next to the report.
#: Only S0 (C01–C24) configurations are mapped; any other
#: (origin scenario, proxy mode) pair must name its label
#: explicitly with ``--scenario-id``.
SCENARIO_ID_BY_CONFIG: dict[tuple[str, str], str] = {
    ("healthy", "respect_vary"): "C01",
    ("healthy", "disabled"): "C05",
    ("healthy", "force_uri_only"): "C11",
    ("healthy", "ignore_no_store"): "C19",
    ("healthy", "opaque"): "C20",
    ("no_vary", "manual_accept_key"): "C03",
    ("no_vary", "respect_vary"): "C13",
    ("no_vary", "force_uri_only"): "C15",
    ("no_vary", "disabled"): "C17",
    ("html_404", "respect_vary"): "C07",
    ("markdown_404", "respect_vary"): "C08",
    ("html_wrong_content_type", "respect_vary"): "C09",
    ("markdown_sentinel_missing", "respect_vary"): "C10",
}

#: The frozen report-Schema pattern for ``scenario_id`` (§14.3).
SCENARIO_ID_PATTERN = re.compile(r"^[CE][0-9]{2}$")

#: Run ids (``--run-id`` and ``clean --run-id``) are plain directory
#: names under ``output/runs/``: no separators, no leading dot, no
#: ``..`` — a traversal string is refused, never resolved.
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def environment_record() -> dict[str, object]:
    """Real execution environment for the evidence log."""
    import subprocess

    def _node_version() -> str:
        try:
            out = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, timeout=10
            )
            return out.stdout.strip() or "unknown"
        except (OSError, subprocess.SubprocessError):
            return "unknown"

    return {
        "python": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "node": _node_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "accepttwin_version": __version__,
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _validate_run_id(run_id: str) -> str:
    """Return *run_id* or raise ValueError (exit 2) for a traversal."""
    if not RUN_ID_PATTERN.match(run_id) or ".." in run_id:
        raise ValueError(
            f"invalid run-id {run_id!r}: use letters, digits, '.', '-' "
            "or '_' only, starting with a letter or digit (no '/' or '..')"
        )
    return run_id


def _resolve_scenario_id(
    scenario: str, proxy_mode: str, scenario_id: str | None
) -> str:
    """Return the report ``scenario_id`` for a run, or raise
    ValueError (exit 2) when none can be derived.

    An explicit ``--scenario-id`` must match the frozen Schema
    pattern; otherwise the S0 configuration table above supplies
    the label for a known (origin scenario, proxy mode) pair.
    """
    if scenario_id is not None:
        if not SCENARIO_ID_PATTERN.match(scenario_id):
            raise ValueError(
                f"invalid --scenario-id {scenario_id!r}: the frozen v1 "
                "report Schema only accepts C01-C24 / E01-E24"
            )
        return scenario_id
    mapped = SCENARIO_ID_BY_CONFIG.get((scenario, proxy_mode))
    if mapped is None:
        raise ValueError(
            f"no report scenario_id mapped for origin scenario "
            f"{scenario!r} with proxy mode {proxy_mode!r}; pass an "
            "explicit --scenario-id (C01-C24 / E01-E24)"
        )
    return mapped


# ---------------------------------------------------------------------------
# Shared single-contract execution (``run`` and ``demo``)
# ---------------------------------------------------------------------------


def _execute_contract_run(
    root: Path,
    modules: dict[str, object],
    contract: object,
    *,
    scenario: str,
    proxy_mode: str,
    scenario_id: str,
    run_id: str,
    out_dir: Path,
    namespace_prefix: str,
    origin: SyntheticOrigin | None = None,
    proxy: ControlledCacheProxy | None = None,
    report_name: str = "report.json",
) -> dict[str, object]:
    """Run one contract end to end and write its evidence.

    The pipeline is exactly the reviewed one, reused rather than
    re-implemented: frozen four experiments
    (:mod:`accepttwin.experiment_runner`), production classification,
    the independent Oracle (``scripts/s0_harness.py``), and the
    formal ``accepttwin.report/v1`` report
    (:mod:`accepttwin.report_builder`). Oracle parity is checked
    twice — once with the harness parity check and once inside the
    report builder — and the two must agree, or the run fails
    closed. Writes the formal report (``report_name``, default
    ``report.json``), ``raw-observations.json``, ``contract.json``,
    ``production.json``, ``oracle-input.json``, ``oracle.json`` and
    ``run-summary.json`` under *out_dir*. Returns the run summary;
    ``ok`` is True only when Oracle parity held and the report is
    final. Raises :class:`ValueError` for bad run inputs and
    :class:`RuntimeError` for infrastructure / parity failures.
    """
    if not SCENARIO_ID_PATTERN.match(scenario_id):
        raise RuntimeError(
            f"internal error: scenario_id {scenario_id!r} does not match "
            "the frozen report Schema pattern"
        )
    harness = modules["s0_harness"]
    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    from accepttwin.contract import canonical_contract_hash  # noqa: E402

    _write_json(out_dir / "contract.json", contract.as_dict())  # type: ignore[attr-defined]
    run = run_experiments(
        contract,  # type: ignore[arg-type]
        origin=origin,
        proxy=proxy,
        scenario=scenario,
        proxy_mode=proxy_mode,
        namespace_prefix=namespace_prefix,
    )
    duration = time.perf_counter() - started
    production = classify_run(
        contract,  # type: ignore[arg-type]
        run.observations,
        run.origin_events,
        run.reset_evidence,
        raw_observations=run.raw_observations,
    )
    run.write_evidence(out_dir / "raw-observations.json")
    _write_json(out_dir / "production.json", production.as_dict())
    oracle_input = harness.oracle_input_dict(  # type: ignore[attr-defined]
        contract, run, run.origin_events, origin_events_available=True
    )
    _write_json(out_dir / "oracle-input.json", oracle_input)
    oracle_result = harness.run_oracle(  # type: ignore[attr-defined]
        out_dir / "oracle-input.json", out_dir / "oracle.json"
    )
    outcome = harness.ScenarioOutcome(  # type: ignore[attr-defined]
        scenario_id=scenario_id,
        fixture={},
        contract=contract,
        run=run,
        duration_seconds=duration,
        production=production,
        adj_origin_events=run.origin_events,
    )
    parity = harness.check_parity(outcome, oracle_result)  # type: ignore[attr-defined]
    report = build_report(
        contract,  # type: ignore[arg-type]
        production,
        oracle_result,
        observations=list(run.observations),
        scenario_id=scenario_id,
    )
    if report["oracle_parity"] != parity["parity"]:
        raise RuntimeError(
            "Oracle parity disagreement between the harness check "
            f"({parity['parity']}) and the report builder "
            f"({report['oracle_parity']}): refusing to finalise the report"
        )
    _write_json(out_dir / report_name, report)
    assert_report_clean(report)
    if compute_report_hash(report) != report["report_hash"]:
        raise RuntimeError(
            f"report_hash recomputation mismatch after writing {report_name}"
        )
    summary: dict[str, object] = {
        "run_id": run_id,
        "contract_id": contract.contract_id,  # type: ignore[attr-defined]
        "contract_sha256": canonical_contract_hash(contract),  # type: ignore[arg-type]
        "scenario": scenario,
        "proxy_mode": proxy_mode,
        "scenario_id": scenario_id,
        "verdict": production.verdict,
        "first_error": production.first_error,
        "first_error_experiment_id": production.first_error_experiment_id,
        "diagnostics": outcome.diagnostics_projection,
        "oracle_verdict": oracle_result["verdict"],
        "oracle_parity": parity["parity"],
        "oracle_mismatches": parity["mismatches"],
        "final": report["final"],
        "report_hash": report["report_hash"],
        "duration_seconds": round(duration, 4),
        "request_count": len(run.observations),
        "out_dir": str(out_dir),
        "report_path": str(out_dir / report_name),
        "ok": bool(parity["parity"] and report["final"]),
    }
    _write_json(out_dir / "run-summary.json", summary)
    return summary


def _print_run_summary(summary: dict[str, object]) -> None:
    print(
        f"RUN {summary['run_id']}: verdict={summary['verdict']} "
        f"first_error={summary['first_error']} "
        f"oracle_parity={summary['oracle_parity']} "
        f"final={summary['final']} "
        f"report_hash={str(summary['report_hash'])[:12]} "
        f"({summary['duration_seconds']}s)"
    )
    print(f"  report: {summary['report_path']}")
    if summary["oracle_mismatches"]:
        for mismatch in summary["oracle_mismatches"]:  # type: ignore[union-attr]
            print(f"  oracle mismatch: {mismatch}")


# ---------------------------------------------------------------------------
# run --contract
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    """``run --contract <path>`` — run one user contract, for real."""
    root = find_repo_root()
    contract_path = Path(args.contract)
    if not contract_path.exists():
        print(f"accepttwin: contract file not found: {contract_path}", file=sys.stderr)
        return 2
    try:
        contract = load_contract(contract_path)
    except ContractError as exc:
        print(f"accepttwin: invalid contract: {exc}", file=sys.stderr)
        return 2
    try:
        load_scenario(args.scenario)
    except (ValueError, OSError) as exc:
        print(f"accepttwin: unknown origin scenario {args.scenario!r}: {exc}", file=sys.stderr)
        return 2
    proxy_mode = args.proxy_mode or DEFAULT_PROXY_MODE_BY_CONTRACT_MODE.get(
        contract.cache_behavior.get("mode"), "respect_vary"
    )
    try:
        scenario_id = _resolve_scenario_id(args.scenario, proxy_mode, args.scenario_id)
        run_id = _validate_run_id(args.run_id or contract.contract_id)
    except ValueError as exc:
        print(f"accepttwin: {exc}", file=sys.stderr)
        return 2
    modules = _load_script_modules(root)
    if args.output is not None:
        report_path = Path(args.output)
        out_dir = report_path.parent
        report_name = report_path.name
        if not report_name.endswith(".json"):
            print("accepttwin: --output must name a .json report file", file=sys.stderr)
            return 2
    else:
        out_dir = root / "output" / "runs" / run_id
        report_path = out_dir / "report.json"
        report_name = "report.json"
    try:
        summary = _execute_contract_run(
            root,
            modules,
            contract,
            scenario=args.scenario,
            proxy_mode=proxy_mode,
            scenario_id=scenario_id,
            run_id=run_id,
            out_dir=out_dir,
            namespace_prefix=f"run-{run_id}",
            report_name=report_name,
        )
    except (ExperimentError, RuntimeError, ValueError, OSError) as exc:
        # ValueError covers OriginServerError (bind failure, e.g. the
        # contract's ports are already in use) and ReportError; all
        # are run failures (exit 1), never a traceback to the user.
        print(f"accepttwin: run failed: {exc}", file=sys.stderr)
        return 1
    _print_run_summary(summary)
    print(
        f"RUN_STATUS: {'COMPLETE' if summary['ok'] else 'FAIL'} "
        f"(verdict={summary['verdict']}, oracle_parity={summary['oracle_parity']}, "
        f"final={summary['final']})"
    )
    return 0 if summary["ok"] else 1


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------


def _demo_contract(
    template: dict, proxy_url: str, origin_url: str, contract_id: str, name: str
) -> object:
    """A demo contract: the bundled template with live ephemeral URLs."""
    data = json.loads(json.dumps(template))
    data["contract_id"] = contract_id
    data["name"] = name
    data["url"] = proxy_url
    data["origin_url"] = origin_url
    return parse_contract(data)


def cmd_demo(args: argparse.Namespace) -> int:
    """``demo`` — healthy run, then a deliberate bleed, both real.

    Both cases use the bundled ``contracts/site.json`` template with
    fresh OS-assigned loopback ports (no fixed-port clashes): the
    healthy case runs the ``respect_vary`` proxy (the C01
    configuration, expected PASS_OBSERVED); the bleed case runs the
    same contract against a ``force_uri_only`` proxy (the C11
    configuration, expected REPRESENTATION_BLEED with first_error
    6). Each case also exports its HTML page, so the demo ends with
    two complete report + HTML pairs under ``output/runs/``.
    """
    root = find_repo_root()
    template_path = root / "contracts" / "site.json"
    if not template_path.exists():
        print(f"accepttwin: demo template not found: {template_path}", file=sys.stderr)
        return 2
    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"accepttwin: demo template is not valid JSON: {exc}", file=sys.stderr)
        return 2
    modules = _load_script_modules(root)
    cases = (
        ("demo-healthy", "respect_vary", "C01", "PASS_OBSERVED"),
        ("demo-bleed", "force_uri_only", "C11", "REPRESENTATION_BLEED"),
    )
    all_ok = True
    for run_id, proxy_mode, scenario_id, expected_verdict in cases:
        out_dir = root / "output" / "runs" / run_id
        origin: SyntheticOrigin | None = None
        proxy: ControlledCacheProxy | None = None
        try:
            origin = SyntheticOrigin(port=0, scenario="healthy")
            origin.start()
            proxy = ControlledCacheProxy(
                port=0, mode=proxy_mode, origin_url=origin.url
            )
            proxy.start()
            contract = _demo_contract(
                template,
                proxy.url,
                origin.url,
                f"{run_id}-001",
                f"Demo {run_id} (synthetic origin + controlled proxy)",
            )
            summary = _execute_contract_run(
                root,
                modules,
                contract,
                scenario="healthy",
                proxy_mode=proxy_mode,
                scenario_id=scenario_id,
                run_id=run_id,
                out_dir=out_dir,
                namespace_prefix=f"demo-{run_id}",
                origin=origin,
                proxy=proxy,
            )
        except (ExperimentError, RuntimeError, ContractError, ValueError) as exc:
            print(f"accepttwin: demo case {run_id} failed: {exc}", file=sys.stderr)
            all_ok = False
            continue
        finally:
            if proxy is not None:
                proxy.stop()
            if origin is not None:
                origin.stop()
        _print_run_summary(summary)
        if summary["verdict"] != expected_verdict:
            print(
                f"demo case {run_id}: expected verdict {expected_verdict}, "
                f"got {summary['verdict']}",
                file=sys.stderr,
            )
            all_ok = False
        if not summary["ok"]:
            all_ok = False
            continue
        try:
            html_path = _export_report_html(
                modules,
                out_dir / "report.json",
                out_dir / "contract.json",
                out_dir / "report.html",
                check_only=False,
            )
            print(f"  html: {html_path}")
        except (RuntimeError, ValueError) as exc:
            print(f"accepttwin: demo HTML export failed for {run_id}: {exc}", file=sys.stderr)
            all_ok = False
    print(
        f"DEMO_STATUS: {'PASS' if all_ok else 'FAIL'} "
        "(healthy PASS_OBSERVED + bleed REPRESENTATION_BLEED, "
        "both Oracle parity, both HTML exported)"
    )
    return 0 if all_ok else 1


# ---------------------------------------------------------------------------
# report export (shared by ``demo`` and ``report export``)
# ---------------------------------------------------------------------------


def _export_report_html(
    modules: dict[str, object],
    report_path: Path,
    contract_path: Path | None,
    out_path: Path,
    *,
    check_only: bool,
) -> str:
    """Export one formal report to a self-contained HTML page.

    Privacy preview first (printed before anything is written, per
    §4.2 constraint 7); the finished page is scanned for remote
    references and Sentinel literals. Returns the output path as a
    string. Raises RuntimeError/ValueError on any failure.
    """
    embed = modules["embed_report"]
    template, styles, script = embed._load_template_assets()  # type: ignore[attr-defined]
    html, report, baseline_source = embed.build_single(  # type: ignore[attr-defined]
        report_path, contract_path, template, styles, script
    )
    out_name = str(out_path)
    embed.print_privacy_preview(report, out_name, baseline_source)  # type: ignore[attr-defined]
    if check_only:
        print(f"CHECK ONLY: {report['scenario_id']} OK (nothing written)")
        return out_name
    remote = scan_html_for_remote_resources(html)
    if remote:
        raise RuntimeError(
            f"generated HTML contains remote references: {remote}"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"WROTE {out_path} ({len(html.encode('utf-8'))} bytes)")
    return out_name

# ---------------------------------------------------------------------------
# Shared report-file loading (verify --report / report preview/export)
# ---------------------------------------------------------------------------


def _load_report_file(root: Path, modules: dict[str, object], path: Path) -> tuple[dict, int] | tuple[None, int]:
    """Load and fully validate a report file, or return (None, rc).

    Missing file -> rc 2 (bad input); unreadable / invalid /
    privacy-dirty report -> rc 1 (verification failure). The loader
    is the reviewed ``embed_report`` one: independent Schema check,
    report-hash recomputation, Sentinel scan, forbidden-key scan.
    """
    if not path.exists():
        print(f"accepttwin: report file not found: {path}", file=sys.stderr)
        return None, 2
    embed = modules["embed_report"]
    try:
        report = embed.load_report(path)  # type: ignore[attr-defined]
        assert_report_clean(report)
    except (ValueError, PrivacyError) as exc:
        print(f"accepttwin: invalid report {path}: {exc}", file=sys.stderr)
        return None, 1
    return report, 0


def _json_schema_field(path: Path) -> str | None:
    """Return the ``schema`` field of a JSON file, or None when the
    file is missing, unreadable, not JSON, or not an object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    schema = data.get("schema")
    return schema if isinstance(schema, str) else None


# ---------------------------------------------------------------------------
# verify (extended with --report)
# ---------------------------------------------------------------------------


def cmd_verify(args: argparse.Namespace) -> int:
    """``verify --suite s0|all`` — re-run the Golden gate(s) live.

    ``verify --report <path>`` instead verifies one formal report
    file: Schema + hash + privacy + Oracle parity/final. It never
    re-runs an experiment. Exit 0 means the report is verified as
    authentic and consistent — the verdict itself is reported, not
    gated: a valid REPRESENTATION_BLEED report still exits 0.
    """
    root = find_repo_root()
    modules = _load_script_modules(root)
    if getattr(args, "report", None) is not None:
        report_path = Path(args.report)
        report, rc = _load_report_file(root, modules, report_path)
        if report is None:
            return rc
        contract_ok: bool | None = None
        if getattr(args, "contract", None) is not None:
            from accepttwin.contract import canonical_contract_hash  # noqa: E402

            try:
                contract = load_contract(args.contract)
            except ContractError as exc:
                print(f"accepttwin: invalid contract: {exc}", file=sys.stderr)
                return 2
            contract_ok = (
                canonical_contract_hash(contract)
                == report["input"]["contract_sha256"]
            )
            if not contract_ok:
                print(
                    "accepttwin: report contract_sha256 does not match "
                    f"--contract {args.contract}",
                    file=sys.stderr,
                )
        ok = (
            report["oracle_parity"] is True
            and report["final"] is True
            and contract_ok is not False
        )
        print(
            f"VERIFY_REPORT: {report['scenario_id']} "
            f"verdict={report['verdict']} "
            f"first_error={report['first_error']} "
            f"oracle_parity={report['oracle_parity']} "
            f"final={report['final']} schema=OK hash=OK"
            + (
                f" contract_sha256={'OK' if contract_ok else 'MISMATCH'}"
                if contract_ok is not None
                else ""
            )
        )
        return 0 if ok else 1
    suite = getattr(args, "suite", None) or "all"
    if suite == "s0":
        summary = modules["run_s0"].run_all()  # type: ignore[attr-defined]
        ok = summary["S0_STATUS"] == "PASS"
        print(
            f"VERIFY_STATUS: {summary['S0_STATUS']} "
            f"(S0 {summary['S0_CORE_GOLDEN']} golden, "
            f"parity {summary['S0_ORACLE_PARITY']})"
        )
        return 0 if ok else 1
    # --suite all: the 48-scenario suite first, then the S0 gate
    # re-run (24/24 + repeat-100 + bleed reproduction). run_all_48
    # already contains the S0 scenarios as a subset; the separate
    # S0 run is the required re-run, not a second implementation.
    summary48 = modules["run_all_48"].run_all()  # type: ignore[attr-defined]
    summary_s0 = modules["run_s0"].run_all()  # type: ignore[attr-defined]
    ok = (
        summary48["ALL48_STATUS"] == "PASS"
        and summary_s0["S0_STATUS"] == "PASS"
    )
    print(
        f"VERIFY_STATUS: {'PASS' if ok else 'FAIL'} "
        f"(ALL48 {summary48['ALL48_GOLDEN']} golden, "
        f"parity {summary48['ALL48_ORACLE_PARITY']}; "
        f"S0 {summary_s0['S0_CORE_GOLDEN']} golden, "
        f"parity {summary_s0['S0_ORACLE_PARITY']}, "
        f"repeat-100 distinct_hashes="
        f"{summary_s0['repeat_100']['distinct_hashes']})"
    )
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# report preview / export / delete
# ---------------------------------------------------------------------------


def cmd_report_preview(args: argparse.Namespace) -> int:
    """``report preview <path>`` — human-readable report, no files
    written (§4.2 constraint 7: preview before export)."""
    root = find_repo_root()
    modules = _load_script_modules(root)
    report_path = Path(args.report)
    report, rc = _load_report_file(root, modules, report_path)
    if report is None:
        return rc
    embed = modules["embed_report"]
    baseline_source = (
        f"contract {args.contract}"
        if getattr(args, "contract", None) is not None
        else "frozen §5.1.2 constants"
    )
    embed.print_privacy_preview(report, str(report_path), baseline_source)  # type: ignore[attr-defined]
    print()
    print(f"scenario:      {report['scenario_id']}")
    print(f"verdict:       {report['verdict']}")
    print(
        f"first error:   request {report['first_error']} "
        f"({report['first_error_experiment_id']})"
    )
    print(
        f"diagnostics:   {report['critical_count']} CRITICAL, "
        f"{report['warning_count']} WARNING"
    )
    for diag in report["diagnostics"]:
        print(
            f"  [{diag['severity']}] {diag['code']} "
            f"(request {diag['request_index']}, {diag['experiment_id']}): "
            f"{diag['message']}"
        )
    print("requests (001-008, execution order):")
    for obs in report["observations"]:
        print(
            f"  {obs['request_index']:03d} {obs['experiment_id']:<18} "
            f"{obs['requested_representation']:<8} "
            f"status={obs['response_status']} "
            f"content-type={obs['response_content_type']} "
            f"cache={obs['cache_status']} "
            f"sentinel_match={obs['sentinel_match']} "
            f"origin_delta={obs['origin_counter_delta']}"
        )
    print(f"oracle parity: {report['oracle_parity']} (final={report['final']})")
    print(f"report hash:   {report['report_hash']}")
    print(f"contract:      {report['input']['contract_id']} "
          f"({report['input']['contract_sha256'][:12]}…)")
    return 0


def cmd_report_export(args: argparse.Namespace) -> int:
    """``report export <path>`` — self-contained HTML (§14.4).

    The privacy preview is printed before anything is written;
    ``--check-only`` validates and previews without writing.
    """
    root = find_repo_root()
    modules = _load_script_modules(root)
    report_path = Path(args.report)
    report, rc = _load_report_file(root, modules, report_path)
    if report is None:
        return rc
    if getattr(args, "out", None) is not None:
        out_path = Path(args.out)
    else:
        out_path = report_path.parent / f"{report_path.stem}.html"
    contract_path = (
        Path(args.contract)
        if getattr(args, "contract", None) is not None
        else None
    )
    try:
        _export_report_html(
            modules,
            report_path,
            contract_path,
            out_path,
            check_only=bool(getattr(args, "check_only", False)),
        )
    except (RuntimeError, ValueError) as exc:
        print(f"accepttwin: report export failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _delete_named_file(
    root: Path,
    target: str | Path,
    *,
    allowed_subtrees: tuple[str, ...],
    expected_schema: str,
    kind: str,
) -> int:
    """Delete one explicitly named file under the safety rules.

    The target must be an existing regular file inside the
    workspace (T011 rules via :func:`resolve_cleanup_target`),
    under one of *allowed_subtrees*, and its JSON ``schema`` field
    must be *expected_schema* — a report delete refuses a
    non-report file and a contract delete refuses a non-contract
    file, even inside an allowed subtree. One refusal blocks the
    deletion; nothing is deleted on any refusal.
    """
    if not Path(target).exists():
        print(f"accepttwin: file not found: {target}", file=sys.stderr)
        return 2
    schema = _json_schema_field(Path(target))
    if schema != expected_schema:
        print(
            f"accepttwin: refusing to delete {target}: not a {kind} "
            f"file (schema {schema!r} != {expected_schema!r})",
            file=sys.stderr,
        )
        return 2
    try:
        deleted = delete_evidence_files(
            root, [target], allowed_subtrees=allowed_subtrees
        )
    except PrivacyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    for path in deleted:
        print(f"deleted: {path}")
    return 0


def cmd_report_delete(args: argparse.Namespace) -> int:
    """``report delete <path>`` — delete one formal report file.

    Only files under ``output/`` or ``evidence/Reports/`` whose
    JSON ``schema`` is ``accepttwin.report/v1`` are deletable.
    """
    root = find_repo_root()
    return _delete_named_file(
        root,
        args.report,
        allowed_subtrees=("output", "evidence"),
        expected_schema="accepttwin.report/v1",
        kind="accepttwin.report/v1",
    )


def cmd_contract_delete(args: argparse.Namespace) -> int:
    """``contract delete <path>`` — delete one contract file.

    Only files under ``contracts/`` or ``output/`` whose JSON
    ``schema`` is ``accepttwin.contract/v1`` are deletable.
    """
    root = find_repo_root()
    return _delete_named_file(
        root,
        args.contract,
        allowed_subtrees=("contracts", "output"),
        expected_schema="accepttwin.contract/v1",
        kind="accepttwin.contract/v1",
    )


# ---------------------------------------------------------------------------
# clean --run-id
# ---------------------------------------------------------------------------


def cmd_clean(args: argparse.Namespace) -> int:
    """``clean --run-id <RUN_ID>`` — delete one run's output files.

    Only the flat files directly inside
    ``output/runs/<RUN_ID>/`` are deleted: the run directory must
    exist, must not be a symlink, and must contain regular files
    only (a symlink or a subdirectory inside it refuses the whole
    batch — fail-closed, no partial deletion). The directory itself
    is removed once empty. ``--dry-run`` lists and deletes nothing.
    """
    root = find_repo_root()
    try:
        run_id = _validate_run_id(args.run_id)
    except ValueError as exc:
        print(f"accepttwin: {exc}", file=sys.stderr)
        return 2
    run_dir = root / "output" / "runs" / run_id
    if run_dir.is_symlink():
        print(f"REFUSED: refusing to clean symlink: {run_dir}", file=sys.stderr)
        return 2
    if not run_dir.is_dir():
        print(f"accepttwin: no such run: {run_id} ({run_dir})", file=sys.stderr)
        return 2
    entries = sorted(run_dir.iterdir())
    try:
        resolved = [resolve_cleanup_target(root, entry) for entry in entries]
    except PrivacyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    for entry in entries:
        if entry.is_symlink() or not entry.is_file():
            print(
                f"REFUSED: run directory {run_id} contains a non-regular "
                f"file: {entry.name} (nothing deleted)",
                file=sys.stderr,
            )
            return 2
    verb = "would delete" if args.dry_run else "deleted"
    for path in resolved:
        print(f"{verb}: {path}")
    if args.dry_run:
        print(f"CLEAN_STATUS: DRY-RUN ({len(resolved)} files, nothing deleted)")
        return 0
    for path in resolved:
        path.unlink()
    run_dir.rmdir()
    print(f"CLEAN_STATUS: OK (run {run_id}: {len(resolved)} files deleted)")
    return 0


# ---------------------------------------------------------------------------
# benchmark
# ---------------------------------------------------------------------------


def cmd_benchmark(args: argparse.Namespace) -> int:
    """``benchmark --suite all`` — timings, repeat-100, reports, HTML.

    Every number below comes from a real run made in this invocation:
    the 48 per-scenario durations are the live experiment durations
    recorded by ``run_all_48`` (8 real HTTP requests per scenario,
    no cached report is ever read for a timing), and the repeat-100
    re-executes C01 100 times on fresh pairs. Nothing is timed from
    a stored file.
    """
    if args.suite != "all":
        print("benchmark currently supports only --suite all", file=sys.stderr)
        return 2
    root = find_repo_root()
    modules = _load_script_modules(root)
    started = time.perf_counter()
    env = environment_record()

    # 1. The 48 live scenarios: verdicts, Oracle parity, durations.
    summary48 = modules["run_all_48"].run_all()  # type: ignore[attr-defined]
    scenarios = summary48["scenarios"]
    max_duration = max(s["duration_seconds"] for s in scenarios.values())
    per_scenario = {
        sid: {
            "duration_seconds": s["duration_seconds"],
            "verdict": s["verdict"],
            "oracle_parity": s["oracle_parity"],
            "request_count": s["request_count"],
        }
        for sid, s in sorted(scenarios.items())
    }
    timings_ok = (
        summary48["ALL48_STATUS"] == "PASS" and max_duration < 1.0
    )
    print(
        f"benchmark timings: max single-scenario "
        f"{max_duration:.3f}s (limit 1.000s), "
        f"total {summary48['total_seconds']:.2f}s"
    )

    # 2. Repeat-100 determinism (§10.4, §18 AC10): C01, fresh pair
    # per run, real experiments every time. The canonical report of
    # the first run is also scanned for non-deterministic fields.
    from accepttwin.contract import canonical_json_bytes  # noqa: E402

    harness = modules["s0_harness"]
    repeat_hashes: list[str] = []
    repeat_durations: list[float] = []
    canonical_clean = True
    canonical_recompute_ok = True
    for i in range(100):
        outcome = harness.run_scenario(  # type: ignore[attr-defined]
            "C01", namespace_prefix=f"bench-C01-repeat-{i + 1}"
        )
        repeat_hashes.append(outcome.report_hash)
        repeat_durations.append(outcome.duration_seconds)
        if outcome.production.verdict != "PASS_OBSERVED":
            print(f"C01 repeat {i + 1}: unexpected verdict {outcome.production.verdict}")
            canonical_clean = False
        if i == 0:
            raw = canonical_json_bytes(outcome.report)
            for needle in FORBIDDEN_CANONICAL_SUBSTRINGS:
                if needle in raw:
                    print(f"canonical JSON contains forbidden field {needle!r}")
                    canonical_clean = False
            recomputed = hashlib.sha256(raw).hexdigest()
            if recomputed != outcome.report_hash:
                print(
                    "canonical hash recompute mismatch: "
                    f"{recomputed} != {outcome.report_hash}"
                )
                canonical_recompute_ok = False
    repeat_ok = (
        len(set(repeat_hashes)) == 1
        and canonical_clean
        and canonical_recompute_ok
    )
    print(
        f"benchmark repeat-100 C01: distinct_hashes={len(set(repeat_hashes))} "
        f"all_equal={repeat_ok} max_duration={max(repeat_durations):.3f}s "
        f"hash={repeat_hashes[0] if repeat_hashes else None}"
    )

    # 3. Formal reports (T009 reuse): rebuild from the fresh Golden
    # evidence and validate each sample with the independent Schema
    # validator. 4. HTML export (T010 reuse): 49 self-contained
    # pages, then the T011 privacy scanner over the whole directory.
    reports = modules["build_reports_48"].build_all()  # type: ignore[attr-defined]
    reports_ok = reports["REPORTS_STATUS"] == "PASS"
    embed_rc = modules["embed_report"].main(["--all-48"])  # type: ignore[attr-defined]
    html_ok = embed_rc == 0
    from accepttwin.privacy import assert_html_directory_clean, assert_report_clean  # noqa: E402

    reports_dir = root / "evidence" / "Reports"
    html_dir = reports_dir / "html"
    html_scan: dict[str, object] = {}
    try:
        assert_html_directory_clean(html_dir)
        html_pages = sorted(p.name for p in html_dir.glob("*.html"))
        html_scan = {"pages": len(html_pages), "violations": 0, "clean": True}
    except Exception as exc:  # privacy.PrivacyError or OSError
        html_scan = {"pages": 0, "violations": 1, "clean": False, "error": str(exc)}
        html_ok = False
    reports_clean = True
    for sid in sorted(scenarios):
        try:
            report = json.loads((reports_dir / f"{sid}.json").read_text(encoding="utf-8"))
            assert_report_clean(report)
            # HTML/JSON consistency (§14.4): the page for this
            # scenario must carry the same verdict, first error and
            # report hash as the formal JSON report.
            page = (html_dir / f"{sid}.html").read_text(encoding="utf-8")
            # The page embeds the report JSON verbatim (json.dumps,
            # sort_keys, indent=2), so the exact field spellings
            # below must appear.
            if report["report_hash"] not in page:
                print(f"{sid}: HTML page does not carry report_hash")
                reports_clean = False
            if f'"verdict": "{report["verdict"]}"' not in page:
                print(f"{sid}: HTML page does not carry verdict {report['verdict']}")
                reports_clean = False
            if f'"first_error": {json.dumps(report["first_error"])}' not in page:
                print(f"{sid}: HTML page does not carry first_error {report['first_error']}")
                reports_clean = False
        except Exception as exc:
            print(f"{sid}: report/HTML cross-check failed: {exc}")
            reports_clean = False
    print(
        f"benchmark reports: schema {reports['SCHEMA_VALID']}, "
        f"verdict {reports['VERDICT_MATCHES_RECORD']}, "
        f"parity {reports['ORACLE_PARITY']}; "
        f"HTML pages clean: {html_scan}"
    )

    total_seconds = time.perf_counter() - started
    passed = timings_ok and repeat_ok and reports_ok and html_ok and reports_clean
    summary = {
        "gate": "BENCHMARK",
        "spec": "PROJECT_BOOK.md §18 AC10/AC11, §10.4, §10.5, §14",
        "BENCHMARK_STATUS": "PASS" if passed else "FAIL",
        "ALL48_GOLDEN": summary48["ALL48_GOLDEN"],
        "ALL48_ORACLE_PARITY": summary48["ALL48_ORACLE_PARITY"],
        "max_scenario_duration_seconds": max_duration,
        "per_scenario_duration_limit_seconds": 1.0,
        "per_scenario": per_scenario,
        "repeat_100": {
            "scenario": "C01",
            "runs": 100,
            "distinct_hashes": len(set(repeat_hashes)),
            "hash": repeat_hashes[0] if repeat_hashes else None,
            "all_equal": repeat_ok,
            "max_duration_seconds": round(max(repeat_durations), 4),
            "fresh_pair_per_run": True,
            "canonical_json_free_of_nondeterministic_fields": canonical_clean,
            "canonical_hash_recompute_matches": canonical_recompute_ok,
        },
        "reports": {
            "REPORTS_STATUS": reports["REPORTS_STATUS"],
            "SCHEMA_VALID": reports["SCHEMA_VALID"],
            "VERDICT_MATCHES_RECORD": reports["VERDICT_MATCHES_RECORD"],
            "ORACLE_PARITY": reports["ORACLE_PARITY"],
            "privacy_clean": reports_clean,
        },
        "html": html_scan,
        "environment": env,
        "total_seconds": round(total_seconds, 2),
    }
    out_dir = root / "evidence" / "Performance"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "BENCHMARK_SUMMARY.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"BENCHMARK_STATUS: {summary['BENCHMARK_STATUS']} "
        f"(max single-scenario {max_duration:.3f}s, "
        f"repeat-100 distinct={len(set(repeat_hashes))}, "
        f"reports {reports['REPORTS_STATUS']}, html_clean={html_scan.get('clean')})"
    )
    return 0 if passed else 1


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="accepttwin",
        description=(
            "AcceptTwin (P032): same URL, two representations — "
            "verify delivery is never mixed up. "
            "Local-only, offline, no real users."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"accepttwin {__version__}",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    p_run = sub.add_parser(
        "run",
        help="run one user contract end to end (real experiments + Oracle parity + formal report)",
    )
    p_run.add_argument(
        "--contract",
        required=True,
        help="contract JSON file (accepttwin.contract/v1, loopback URLs only)",
    )
    p_run.add_argument(
        "--scenario",
        default="healthy",
        help="synthetic origin scenario: a name under fixtures/origin/ "
        "or a path to a scenario JSON file (default: healthy)",
    )
    p_run.add_argument(
        "--proxy-mode",
        choices=PROXY_MODES,
        default=None,
        help="controlled proxy mode (§10.3); default follows the "
        "contract: variant_by_accept -> respect_vary, "
        "no_store -> disabled",
    )
    p_run.add_argument(
        "--scenario-id",
        default=None,
        help="report scenario_id label (C01-C24 / E01-E24); default "
        "follows the S0 configuration table for a known "
        "(origin scenario, proxy mode) pair",
    )
    p_run.add_argument(
        "--run-id",
        default=None,
        help="run id (output directory under output/runs/; "
        "default: the contract_id)",
    )
    p_run.add_argument(
        "--output",
        default=None,
        help="report JSON path (default: output/runs/<run-id>/report.json; "
        "sibling evidence files land next to it)",
    )
    p_run.set_defaults(func=cmd_run)
    p_demo = sub.add_parser(
        "demo",
        help="run the bundled example contract twice: healthy (PASS) then a deliberate bleed (REPRESENTATION_BLEED), with HTML export",
    )
    p_demo.set_defaults(func=cmd_demo)
    p_verify = sub.add_parser(
        "verify",
        help="re-run the Golden gate live (48 scenarios + Oracle parity; --suite all also re-runs S0 24/24), or verify one formal report file (--report)",
    )
    p_verify.add_argument(
        "--suite",
        choices=("s0", "all"),
        default=None,
        help="suite to verify: s0 (C01-C24 + repeat-100) or all (48 "
        "scenarios + S0 re-run) (default: all)",
    )
    p_verify.add_argument(
        "--report",
        default=None,
        help="verify one formal report JSON file instead of re-running "
        "a suite (Schema + hash + privacy + Oracle parity/final)",
    )
    p_verify.add_argument(
        "--contract",
        default=None,
        help="with --report: also check the report's contract_sha256 "
        "against this contract file",
    )
    p_verify.set_defaults(func=cmd_verify)
    p_report = sub.add_parser(
        "report",
        help="preview, export or delete a formal report JSON file",
    )
    rep_sub = p_report.add_subparsers(dest="report_command", metavar="REPORT_COMMAND")
    p_preview = rep_sub.add_parser(
        "preview",
        help="print the privacy preview + a human-readable summary of a report (writes nothing)",
    )
    p_preview.add_argument("report", help="formal report JSON file")
    p_preview.add_argument(
        "--contract",
        default=None,
        help="contract file for the baseline column (default: frozen §5.1.2 constants)",
    )
    p_preview.set_defaults(func=cmd_report_preview)
    p_export = rep_sub.add_parser(
        "export",
        help="export a report to a self-contained offline HTML page (privacy preview first)",
    )
    p_export.add_argument("report", help="formal report JSON file")
    p_export.add_argument(
        "--contract",
        default=None,
        help="contract file for the baseline column (default: frozen §5.1.2 constants)",
    )
    p_export.add_argument(
        "--out",
        default=None,
        help="output HTML path (default: <report-stem>.html next to the report)",
    )
    p_export.add_argument(
        "--check-only",
        action="store_true",
        help="validate + print the privacy preview, write nothing",
    )
    p_export.set_defaults(func=cmd_report_export)
    p_rdel = rep_sub.add_parser(
        "delete",
        help="delete one formal report JSON file (workspace-bounded, report files only)",
    )
    p_rdel.add_argument("report", help="formal report JSON file to delete")
    p_rdel.set_defaults(func=cmd_report_delete)
    p_clean = sub.add_parser(
        "clean",
        help="delete one run's output files under output/runs/<RUN_ID>",
    )
    p_clean.add_argument(
        "--run-id",
        required=True,
        help="run id whose output/runs/<RUN_ID>/ directory is deleted",
    )
    p_clean.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be deleted and delete nothing",
    )
    p_clean.set_defaults(func=cmd_clean)
    p_contract = sub.add_parser(
        "contract",
        help="manage stored contracts",
    )
    con_sub = p_contract.add_subparsers(dest="contract_command", metavar="CONTRACT_COMMAND")
    p_cdel = con_sub.add_parser(
        "delete",
        help="delete one contract JSON file (workspace-bounded, contract files only)",
    )
    p_cdel.add_argument("contract", help="contract JSON file to delete")
    p_cdel.set_defaults(func=cmd_contract_delete)
    p_bench = sub.add_parser(
        "benchmark",
        help="measure per-scenario time (<1s), repeat-100 determinism, and re-validate reports + self-contained HTML",
    )
    p_bench.add_argument(
        "--suite",
        choices=("all",),
        default="all",
        help="suite to benchmark (default: all)",
    )
    p_bench.set_defaults(func=cmd_benchmark)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    if getattr(args, "command", None) == "verify" and getattr(
        args, "report", None
    ) is not None and getattr(args, "suite", None) is not None:
        parser.error("--suite and --report are mutually exclusive")
    try:
        return int(args.func(args))
    except RuntimeError as exc:
        print(f"accepttwin: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

## src/accepttwin/contract.py

- SHA-256：`17e9d1aa78135e10ce0c000dee1f3844482d3e1323f9e37bbf130d71d67591ba`
- 字节数：20063

```
"""Dual-representation contract: ``accepttwin.contract/v1``.

Implements IMPLEMENTATION_PLAN §5.1:

* :func:`load_contract` — read a contract JSON file, never silently
  correcting it;
* :func:`parse_contract` — validate a decoded JSON object into a
  :class:`Contract`;
* :func:`validate_contract` — re-validate an already built contract and
  return a :class:`ValidationResult`;
* :func:`canonical_json_bytes` / :func:`canonical_contract_hash` —
  Canonical JSON per PROJECT_BOOK §10.4.

Validation is layered and fail-closed:

1. Structural: :func:`accepttwin.schema.validate_with_schema` (required
   fields, types, enums, ``additionalProperties: false`` — unknown fields
   are rejected, never silently ignored).
2. Semantic: frozen per-representation values (§5.1.2), distinct
   Sentinels, loopback URLs (§5.1.1 via :mod:`accepttwin.url_guard`),
   ``url``/``origin_url`` sharing a path but using different ports,
   the fixed request-header set (§5.1.3 via
   :mod:`accepttwin.request_headers`), and legal ``cache_behavior``
   combinations (§5.2: ``no_store`` must not carry a ``max_age_seconds``).

Defaults applied at parse time (documented, not spec-frozen — the retrieved
spec text states only the ``vary_accept`` default):

* ``cache_behavior.vary_accept`` defaults to ``"advisory"`` (§5.2).
* ``cache_behavior.max_age_seconds`` defaults to ``None``.
* ``limits.max_body_bytes`` defaults to 1048576 (1 MiB, §17.4 body cap).
* ``limits.request_timeout_seconds`` defaults to 5.0 (§17.4 requires a
  bounded timeout but states no value).

Canonical JSON (§10.4): UTF-8, object keys in dictionary order, no extra
whitespace, header names lower-cased, header values whitespace-normalised.
The following fields never enter the canonical form or the hash, wherever
they appear: ``generated_at``, ``duration_ms``, ``duration``, ``process_id``,
``temporary_path``, ``ephemeral_port``, ``uuid``, ``request_id`` (§10.4:
random UUIDs and non-deterministic cache request IDs) and ``received_at`` /
``receivedAt`` (§14.1: run-time only). ``cache_entry_id`` is NOT volatile:
it is a §5.3/§8 evidence field whose handling belongs to the T009 report
design, not to canonicalisation. The report hash is
``SHA256(canonical_json_bytes)``; identical contracts hash identically
across runs (I-08).

Ephemeral ports (ADR-003, §10.4 "不包含动态端口"): the ``url`` /
``origin_url`` endpoint URLs carry OS-assigned loopback ports
(the harness starts services with ``port=0``), so their explicit
port is normalised to ``0`` in the canonical form -- the same value
the harness passes when asking the OS for a free port. Scheme, host,
path and query are preserved, a URL without an explicit port is left
untouched, and a non-loopback URL is left untouched (its port is part
of the service identity, not an OS-assigned ephemeral port). Only the
hash input is normalised; execution still uses the real ports, and
the semantic validation (``url`` / ``origin_url`` share a path, use
different ports) is unchanged and still runs on the real values.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .request_headers import validate_request_headers
from .schema import (
    CONTRACT_SCHEMA_VERSION,
    FROZEN_REPRESENTATIONS,
    validate_with_schema,
)
from .url_guard import URLGuardError, ValidatedURL, validate_loopback_url

__all__ = [
    "Contract",
    "ContractError",
    "Representation",
    "ValidationResult",
    "canonical_contract_hash",
    "canonical_json_bytes",
    "load_contract",
    "parse_contract",
    "validate_contract",
]

#: Fields that never enter Canonical JSON or any normalised hash (§10.4,
#: §14.1). Matched case-sensitively at any nesting depth.
VOLATILE_FIELDS: frozenset[str] = frozenset(
    {
        "generated_at",
        "duration_ms",
        "duration",
        "process_id",
        "temporary_path",
        "ephemeral_port",
        "uuid",
        "request_id",
        "received_at",
        "receivedAt",
    }
)

#: Keys whose dict values are HTTP headers: names are lower-cased and values
#: whitespace-normalised during canonicalisation (§10.4).
HEADER_CONTAINER_KEYS: frozenset[str] = frozenset(
    {"headers", "request_headers"}
)

#: Keys whose string values are endpoint URLs whose loopback port is
#: OS-assigned (ephemeral) and is therefore normalised to
#: :data:`NORMALISED_EPHEMERAL_PORT` in Canonical JSON (§10.4, ADR-003).
#: Only these keys are rewritten; any other URL-valued field keeps its
#: port, so the normalisation can never erase a semantically meaningful
#: port elsewhere in a payload.
URL_PORT_NORMALISED_KEYS: frozenset[str] = frozenset({"url", "origin_url"})

#: Placeholder port written into Canonical JSON for an OS-assigned
#: loopback port (ADR-003). 0 is the value the harness itself passes
#: when asking the OS for a free port (``port=0``); keeping the port
#: slot (rather than stripping it) preserves the distinction between
#: a URL with an explicit port and one without.
NORMALISED_EPHEMERAL_PORT = 0

DEFAULT_MAX_BODY_BYTES = 1048576
DEFAULT_REQUEST_TIMEOUT_SECONDS = 5.0
_DEFAULT_VARY_ACCEPT = "advisory"

_SENTINEL_WHITESPACE = re.compile(r"\s")


class ContractError(ValueError):
    """Raised when a contract file or object fails validation."""


@dataclass(frozen=True)
class Representation:
    """One representation of the dual-representation contract (§5.1.2)."""

    accept: str
    expected_status: int
    expected_content_type: str
    sentinel: str

    def as_dict(self) -> dict:
        return {
            "accept": self.accept,
            "expected_status": self.expected_status,
            "expected_content_type": self.expected_content_type,
            "sentinel": self.sentinel,
        }


@dataclass(frozen=True)
class Contract:
    """A validated ``accepttwin.contract/v1`` contract.

    Instances are normally produced by :func:`parse_contract` /
    :func:`load_contract`, which enforce every rule. A directly constructed
    instance is unchecked until :func:`validate_contract` is called on it.
    """

    schema: str
    contract_id: str
    name: str
    url: str
    origin_url: str
    representations: dict[str, Representation] = field(default_factory=dict)
    request_headers: dict = field(default_factory=dict)
    cache_behavior: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "schema": self.schema,
            "contract_id": self.contract_id,
            "name": self.name,
            "url": self.url,
            "origin_url": self.origin_url,
            "representations": {
                key: rep.as_dict()
                for key, rep in self.representations.items()
            },
            "request_headers": dict(self.request_headers),
            "cache_behavior": dict(self.cache_behavior),
            "limits": dict(self.limits),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.ok


# ---------------------------------------------------------------------------
# Canonical JSON (§10.4)
# ---------------------------------------------------------------------------


def _normalise_header_value(value: str) -> str:
    return " ".join(value.strip().split())


def _is_loopback_host(host: str) -> bool:
    """True when *host* is a loopback host, without doing DNS.

    Literal IP hosts are checked with :mod:`ipaddress` (so the whole
    127/8 range and ``::1`` count); the name ``localhost`` is loopback
    by definition. Any other name is not trusted here -- canonicalisation
    must stay pure and deterministic, and contracts in this system use
    literal ``127.0.0.1`` anyway.
    """
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _normalise_ephemeral_port(value: str) -> str:
    """Replace the port of a loopback ``http`` URL with 0 (ADR-003).

    Only an explicit port on a loopback ``http`` URL is rewritten:
    scheme, host, path and query are preserved, a URL without an
    explicit port is left untouched, and a non-loopback URL is left
    untouched (its port is part of the service identity, not an
    OS-assigned ephemeral port). Unparseable values are returned
    unchanged -- canonicalisation never raises; validation is a
    separate layer and still runs on the real values.
    """
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return value
    if parsed.scheme.lower() != "http" or port is None:
        return value
    host = parsed.hostname
    if host is None or not _is_loopback_host(host):
        return value
    netloc = parsed.netloc
    userinfo, sep, hostport = netloc.rpartition("@")
    if hostport.startswith("["):
        bracket = hostport.find("]")
        new_hostport = (
            hostport[: bracket + 1] + f":{NORMALISED_EPHEMERAL_PORT}"
        )
    else:
        host_part, _, _ = hostport.rpartition(":")
        new_hostport = f"{host_part}:{NORMALISED_EPHEMERAL_PORT}"
    new_netloc = (userinfo + sep if sep else "") + new_hostport
    return urlunsplit(
        (parsed.scheme, new_netloc, parsed.path, parsed.query, parsed.fragment)
    )


def _canonicalise(value: object) -> object:
    if isinstance(value, dict):
        out: dict[str, object] = {}
        for key, item in value.items():
            if key in VOLATILE_FIELDS:
                continue
            if key in URL_PORT_NORMALISED_KEYS and isinstance(item, str):
                out[str(key)] = _normalise_ephemeral_port(item)
            elif key.lower() in HEADER_CONTAINER_KEYS and isinstance(item, dict):
                normalised = {
                    str(hk).lower(): (
                        _normalise_header_value(str(hv))
                        if isinstance(hv, str)
                        else _canonicalise(hv)
                    )
                    for hk, hv in item.items()
                }
                out[str(key)] = normalised
            else:
                out[str(key)] = _canonicalise(item)
        return out
    if isinstance(value, list):
        return [_canonicalise(item) for item in value]
    return value


def canonical_json_bytes(data: object) -> bytes:
    """Return the Canonical JSON encoding of *data* as UTF-8 bytes.

    Keys are sorted, there is no extra whitespace, volatile fields
    (:data:`VOLATILE_FIELDS`) are removed at any depth, header
    containers are normalised per §10.4, and the explicit port of a
    loopback ``http`` URL under an ``url`` / ``origin_url`` key is
    normalised to 0 (ADR-003: OS-assigned ephemeral ports never enter
    the canonical form).
    """
    canonical = _canonicalise(data)
    return json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_contract_hash(contract: Contract) -> str:
    """Return the SHA-256 hex digest of the contract's Canonical JSON.

    The ``url`` / ``origin_url`` ports are normalised to 0 before
    hashing (ADR-003, §10.4): two contracts that differ only in their
    OS-assigned loopback ports hash identically, while a change of
    scheme, host, path, representation or any other semantic field
    still changes the hash. Validation still runs on the real ports.
    """
    return hashlib.sha256(canonical_json_bytes(contract.as_dict())).hexdigest()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _semantic_errors(data: dict) -> list[str]:
    errors: list[str] = []

    for field_name in ("contract_id", "name"):
        value = data.get(field_name)
        if isinstance(value, str) and not value.strip():
            errors.append(f"{field_name}: must not be blank")

    representations = data.get("representations")
    if isinstance(representations, dict):
        for rep_name in ("html", "markdown"):
            rep = representations.get(rep_name)
            if not isinstance(rep, dict):
                continue
            frozen = FROZEN_REPRESENTATIONS[rep_name]
            for key, expected in frozen.items():
                if key in rep and rep[key] != expected:
                    errors.append(
                        f"representations.{rep_name}.{key}: must be exactly "
                        f"{expected!r}, got {rep[key]!r}"
                    )
        html = representations.get("html")
        markdown = representations.get("markdown")
        if isinstance(html, dict) and isinstance(markdown, dict):
            html_sentinel = html.get("sentinel")
            markdown_sentinel = markdown.get("sentinel")
            for rep_name, sentinel in (
                ("html", html_sentinel),
                ("markdown", markdown_sentinel),
            ):
                if isinstance(sentinel, str):
                    if _SENTINEL_WHITESPACE.search(sentinel):
                        errors.append(
                            f"representations.{rep_name}.sentinel: must not "
                            "contain whitespace"
                        )
                    if sentinel != sentinel.strip():
                        errors.append(
                            f"representations.{rep_name}.sentinel: must not "
                            "have leading/trailing whitespace"
                        )
            if (
                isinstance(html_sentinel, str)
                and isinstance(markdown_sentinel, str)
                and html_sentinel
                and html_sentinel == markdown_sentinel
            ):
                errors.append(
                    "representations.html.sentinel and "
                    "representations.markdown.sentinel must be different"
                )

    validated: dict[str, ValidatedURL] = {}
    for field_name in ("url", "origin_url"):
        raw = data.get(field_name)
        if isinstance(raw, str) and raw:
            try:
                validated[field_name] = validate_loopback_url(raw)
            except URLGuardError as exc:
                errors.append(f"{field_name}: {exc}")
    if "url" in validated and "origin_url" in validated:
        proxy = validated["url"]
        origin = validated["origin_url"]
        if proxy.path != origin.path:
            errors.append(
                f"url and origin_url must share the same path: "
                f"{proxy.path!r} != {origin.path!r}"
            )
        if proxy.port == origin.port:
            errors.append(
                "url and origin_url must use different ports: both use "
                f"{proxy.port}"
            )

    headers = data.get("request_headers")
    if isinstance(headers, dict):
        canonical_headers = {
            "Accept-Encoding": headers.get("accept_encoding"),
            "User-Agent": headers.get("user_agent"),
            "Accept-Language": headers.get("accept_language"),
        }
        for rep_name in ("html", "markdown"):
            rep = (
                representations.get(rep_name)
                if isinstance(representations, dict)
                else None
            )
            accept = rep.get("accept") if isinstance(rep, dict) else None
            if isinstance(accept, str):
                merged = {"Accept": accept, **canonical_headers}
                for err in validate_request_headers(merged):
                    errors.append(f"request_headers ({rep_name}): {err}")
    # The frozen common-header values themselves are enforced by the schema
    # consts; the loop above additionally proves the merged per-representation
    # header set is exactly the fixed whitelist.

    cache_behavior = data.get("cache_behavior")
    if isinstance(cache_behavior, dict):
        if (
            cache_behavior.get("mode") == "no_store"
            and cache_behavior.get("max_age_seconds") is not None
        ):
            errors.append(
                "cache_behavior: mode 'no_store' must have "
                "max_age_seconds null"
            )

    return errors


def _validate_data(data: object) -> list[str]:
    if not isinstance(data, dict):
        return ["contract must be a JSON object"]
    errors = validate_with_schema(data)
    errors.extend(_semantic_errors(data))
    return errors


def _contract_from_valid_data(data: dict) -> Contract:
    cache_behavior = dict(data["cache_behavior"])
    cache_behavior.setdefault("vary_accept", _DEFAULT_VARY_ACCEPT)
    cache_behavior.setdefault("max_age_seconds", None)
    limits = dict(data["limits"])
    limits.setdefault("max_body_bytes", DEFAULT_MAX_BODY_BYTES)
    limits.setdefault(
        "request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS
    )
    return Contract(
        schema=data["schema"],
        contract_id=data["contract_id"],
        name=data["name"],
        url=data["url"],
        origin_url=data["origin_url"],
        representations={
            name: Representation(
                accept=rep["accept"],
                expected_status=rep["expected_status"],
                expected_content_type=rep["expected_content_type"],
                sentinel=rep["sentinel"],
            )
            for name, rep in data["representations"].items()
        },
        request_headers=dict(data["request_headers"]),
        cache_behavior=cache_behavior,
        limits=limits,
        metadata=dict(data["metadata"]),
    )


def parse_contract(data: object) -> Contract:
    """Validate decoded JSON *data* and return a :class:`Contract`.

    Raises :class:`ContractError` listing every violation found. Nothing
    is silently corrected: missing, unknown, or illegal fields all fail.
    """
    errors = _validate_data(data)
    if errors:
        raise ContractError(
            "invalid accepttwin.contract/v1 contract:\n"
            + "\n".join(f"  - {err}" for err in errors)
        )
    assert isinstance(data, dict)
    return _contract_from_valid_data(data)


def validate_contract(contract: Contract) -> ValidationResult:
    """Re-validate an already built contract; never raises for bad data."""
    if not isinstance(contract, Contract):
        return ValidationResult(False, ("not a Contract instance",))
    errors = _validate_data(contract.as_dict())
    return ValidationResult(ok=not errors, errors=tuple(errors))


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value!r} is not allowed")


def _object_no_duplicates(pairs: list) -> dict:
    obj: dict = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key {key!r}")
        obj[key] = value
    return obj


def load_contract(path: str | Path) -> Contract:
    """Read and validate the contract JSON file at *path*.

    Raises :class:`ContractError` if the file is missing, is not valid
    JSON, contains duplicate keys or non-standard constants, or fails any
    validation rule.
    """
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read contract file {path}: {exc}") from exc
    try:
        data = json.loads(
            raw,
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
    except ValueError as exc:
        raise ContractError(
            f"contract file {path} is not valid JSON: {exc}"
        ) from exc
    try:
        return parse_contract(data)
    except ContractError as exc:
        raise ContractError(f"contract file {path}: {exc}") from exc
```

## src/accepttwin/diagnostics.py

- SHA-256：`c795569b7f40d2ca43812941cc86940bd8af277e5497bf1ec7da8f861f56d632`
- 字节数：38169

```
"""Frozen diagnostic codes (P032 T006).

Implements PROJECT_BOOK §8 (nine codes, severity CRITICAL / WARNING
only) and the deterministic ordering of §6.3. This module owns the
trigger condition of every code: each ``check_*`` function below is a
pure predicate over already-measured evidence — it never performs
I/O, never reads a response body (only hashes and match flags, §7.12
I-12), and never guesses a state from a single header (§5.3 E).

The nine codes, in §8 order (which is also the tie-break order used
by :func:`sort_diagnostics`):

* ``ORIGIN_NEGOTIATION_ERROR`` (CRITICAL, §8.1) — a direct-origin
  baseline request (001 O-H / 002 O-M) violates the representation
  contract (wrong status, wrong Content-Type, or missing Sentinel).
* ``REPRESENTATION_BLEED`` (CRITICAL, §8.2) — a warm-cache second
  request was served the *other* representation from a verified HIT
  with the full dual-evidence chain (baseline correct, first request
  correct and a confirmed MISS, second request HIT with counter
  delta 0, same cache entry as the first request, body hash equal
  to the first request's body, Sentinel of the requested
  representation absent).
* ``CONTRACT_MISMATCH`` (CRITICAL, §8.3) — a response violates the
  contract but is neither a proven origin error nor a proven bleed
  (wrong status / Content-Type on a proxied request, a ``no_store``
  contract violated by storage is reported as
  ``CACHE_POLICY_MISMATCH`` instead, see below).
* ``CACHE_STATE_UNKNOWN`` (WARNING, §8.4) — a MISS / HIT / BYPASS
  cannot be confirmed with dual evidence (missing header leg,
  missing behaviour leg, missing origin event, or an unconfirmed
  cache reset).
* ``SENTINEL_MISMATCH`` (CRITICAL, §8.5) — a response body lacks the
  exact Sentinel of the requested representation.
* ``INCONCLUSIVE_LIMIT`` (WARNING, §8.6) — the run left the
  supported range (redirect, transport failure, body over the
  contract limit, invalid contract, incomplete observations).
* ``VARY_ACCEPT_ABSENT`` (WARNING, §8.7) — a cacheable dual
  representation whose origin response carries no ``Vary: Accept``
  while the contract does not require it. This never changes a
  verdict on its own (I-11); when the contract *requires* Vary
  (§5.2) the same absence is a ``CONTRACT_MISMATCH`` instead.
* ``CACHE_EVIDENCE_CONFLICT`` (WARNING, §8.8) — the proxy-reported
  cache state contradicts the origin-behaviour evidence (e.g. header
  HIT but origin counter +1, header MISS but counter 0). This is
  never reported as a proven ``REPRESENTATION_BLEED``.
* ``CACHE_POLICY_MISMATCH`` (CRITICAL, §8.9) — the contract declares
  ``no_store`` but the proxy stored or reused a response (a
  confirmed MISS — which creates an entry — or a confirmed HIT
  under ``no_store``); or the contract declares
  ``variant_by_accept`` but a proxied request is a confirmed
  BYPASS — the cache never worked at all, so representation
  isolation was never exercised, and the run must not be certified
  PASS (ADR-002, P1-1).

Deterministic ordering (§6.3, §7.8 I-08): diagnostics sort by
(request order, §8 code order, message). ``request_index`` is
``None`` only for run-level diagnostics (invalid contract,
incomplete observations, failed reset); those sort after every
request-bound diagnostic. Sorting is stable, so equal keys keep
insertion order and repeated runs hash identically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CODE_SEVERITY",
    "DIAGNOSTIC_CODES",
    "Diagnostic",
    "check_bleed",
    "check_cache_state",
    "check_contract_response",
    "check_inconclusive_limit",
    "check_no_store_policy",
    "check_origin_baseline",
    "check_reset_evidence",
    "check_sentinel",
    "check_unexpected_hit",
    "check_variant_by_accept_policy",
    "check_vary",
    "diagnostic_order",
    "make_diagnostic",
    "sort_diagnostics",
]

#: The nine frozen codes, in PROJECT_BOOK §8 order.
DIAGNOSTIC_CODES: tuple[str, ...] = (
    "ORIGIN_NEGOTIATION_ERROR",
    "REPRESENTATION_BLEED",
    "CONTRACT_MISMATCH",
    "CACHE_STATE_UNKNOWN",
    "SENTINEL_MISMATCH",
    "INCONCLUSIVE_LIMIT",
    "VARY_ACCEPT_ABSENT",
    "CACHE_EVIDENCE_CONFLICT",
    "CACHE_POLICY_MISMATCH",
)

#: Severity per code (§8: only CRITICAL / WARNING exist).
CODE_SEVERITY: dict[str, str] = {
    "ORIGIN_NEGOTIATION_ERROR": "CRITICAL",
    "REPRESENTATION_BLEED": "CRITICAL",
    "CONTRACT_MISMATCH": "CRITICAL",
    "CACHE_STATE_UNKNOWN": "WARNING",
    "SENTINEL_MISMATCH": "CRITICAL",
    "INCONCLUSIVE_LIMIT": "WARNING",
    "VARY_ACCEPT_ABSENT": "WARNING",
    "CACHE_EVIDENCE_CONFLICT": "WARNING",
    "CACHE_POLICY_MISMATCH": "CRITICAL",
}

#: Evidence keys that must never appear: raw body text is forbidden in
#: diagnostics and reports (§7.12 I-12). Hashes (``body_sha256``) and
#: sizes are allowed.
_FORBIDDEN_EVIDENCE_KEYS = frozenset({"body_text", "response_body", "body"})

#: Cache states that count as confirmed (§5.3 A–C).
_CONFIRMED_STATES = frozenset({"MISS", "HIT", "BYPASS"})

#: Verified-state value meaning "the dual evidence did not confirm a
#: state" (§5.3 D).
_CACHE_STATE_UNKNOWN = "CACHE_STATE_UNKNOWN"


def diagnostic_order(code: str) -> int:
    """Position of *code* in the §8 order (used as a sort tie-break)."""
    try:
        return DIAGNOSTIC_CODES.index(code)
    except ValueError as exc:
        raise ValueError(f"unknown diagnostic code {code!r}") from exc


@dataclass(frozen=True)
class Diagnostic:
    """One frozen diagnostic (§8, §4.3 area E).

    ``evidence`` carries hashes, statuses, counters and identifiers
    only — never response body text (§7.12 I-12). ``request_index``
    is ``None`` only for run-level diagnostics (invalid contract,
    incomplete observations, failed reset); every request-bound
    diagnostic carries the 1-based request number of §6.3.
    """

    code: str
    severity: str
    message: str
    experiment_id: str | None = None
    request_index: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.code not in CODE_SEVERITY:
            raise ValueError(f"unknown diagnostic code {self.code!r}")
        if CODE_SEVERITY[self.code] != self.severity:
            raise ValueError(
                f"diagnostic {self.code} must have severity "
                f"{CODE_SEVERITY[self.code]!r}, got {self.severity!r}"
            )
        if not self.message or not self.message.strip():
            raise ValueError("diagnostic message must not be blank")
        if self.request_index is not None and self.request_index < 1:
            raise ValueError("request_index must be a positive integer")
        for key in self.evidence:
            if key in _FORBIDDEN_EVIDENCE_KEYS:
                raise ValueError(
                    f"diagnostic evidence must not contain {key!r} "
                    "(§7.12 I-12: no raw body text)"
                )

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "experiment_id": self.experiment_id,
            "request_index": self.request_index,
            "evidence": dict(self.evidence),
        }


def make_diagnostic(
    code: str,
    message: str,
    *,
    experiment_id: str | None = None,
    request_index: int | None = None,
    evidence: dict[str, Any] | None = None,
) -> Diagnostic:
    """Build a :class:`Diagnostic` with the §8 severity for *code*.

    Raises :class:`ValueError` for an unknown code, a blank message,
    or forbidden (body-text) evidence keys.
    """
    if code not in CODE_SEVERITY:
        raise ValueError(f"unknown diagnostic code {code!r}")
    return Diagnostic(
        code=code,
        severity=CODE_SEVERITY[code],
        message=message,
        experiment_id=experiment_id,
        request_index=request_index,
        evidence=dict(evidence) if evidence else {},
    )


def sort_diagnostics(
    diagnostics: list[Diagnostic] | tuple[Diagnostic, ...],
) -> tuple[Diagnostic, ...]:
    """Return *diagnostics* in deterministic order (§6.3, I-08).

    Sort key: request order first (``request_index`` ascending;
    run-level diagnostics with ``request_index is None`` sort last),
    then §8 code order, then message. The sort is stable, so
    diagnostics that compare equal keep their insertion order.
    """
    return tuple(
        sorted(
            diagnostics,
            key=lambda d: (
                d.request_index is None,
                d.request_index if d.request_index is not None else 0,
                diagnostic_order(d.code),
                d.message,
            ),
        )
    )


# ---------------------------------------------------------------------------
# Shared helpers for the check functions below.
#
# The checks take plain values (statuses, hashes, flags) rather than
# importing the classifier's dataclasses, so each trigger condition
# is testable in isolation.
# ---------------------------------------------------------------------------


def _content_type_matches(observed: str, expected: str) -> bool:
    """Case-insensitive, whitespace-tolerant Content-Type equality."""
    return observed.strip().lower() == expected.strip().lower()


def _representation_correct(
    *,
    response_status: int,
    response_content_type: str,
    sentinel_match: bool,
    expected_status: int,
    expected_content_type: str,
) -> bool:
    """True when a response matches its representation contract
    exactly: status, Content-Type and Sentinel (§7 I-01–I-06)."""
    return (
        response_status == expected_status
        and _content_type_matches(response_content_type, expected_content_type)
        and sentinel_match
    )


# ---------------------------------------------------------------------------
# Per-code trigger checks (§8.1–§8.9). Each returns a Diagnostic when
# its trigger condition holds, else None. A check returning None is a
# *negative* outcome for that code: the evidence does not support it.
# ---------------------------------------------------------------------------


def check_origin_baseline(
    *,
    request_index: int,
    experiment_id: str,
    requested_representation: str,
    response_status: int,
    response_content_type: str,
    sentinel_match: bool,
    expected_status: int,
    expected_content_type: str,
    expected_sentinel_sha256: str,
    body_sha256: str,
) -> Diagnostic | None:
    """§8.1 ORIGIN_NEGOTIATION_ERROR.

    Fires when a direct-origin baseline request violates the
    representation contract (wrong status, wrong Content-Type, or
    missing Sentinel). Returns None when the baseline is correct —
    a correct baseline is never an origin error, whatever the cache
    does later.
    """
    if _representation_correct(
        response_status=response_status,
        response_content_type=response_content_type,
        sentinel_match=sentinel_match,
        expected_status=expected_status,
        expected_content_type=expected_content_type,
    ):
        return None
    return make_diagnostic(
        "ORIGIN_NEGOTIATION_ERROR",
        f"direct-origin baseline for {requested_representation} violates "
        f"the contract: status {response_status} (expected "
        f"{expected_status}), content-type "
        f"{response_content_type!r} (expected "
        f"{expected_content_type!r}), sentinel_match={sentinel_match}",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "stage": experiment_id,
            "requested_representation": requested_representation,
            "expected_status": expected_status,
            "observed_status": response_status,
            "expected_content_type": expected_content_type,
            "observed_content_type": response_content_type,
            "expected_sentinel_sha256": expected_sentinel_sha256,
            "sentinel_match": sentinel_match,
            "body_sha256": body_sha256,
            "origin_direct": True,
        },
    )


def check_sentinel(
    *,
    request_index: int,
    experiment_id: str,
    requested_representation: str,
    sentinel_match: bool,
    response_content_type: str,
    expected_sentinel_sha256: str,
    body_sha256: str,
) -> Diagnostic | None:
    """§8.5 SENTINEL_MISMATCH.

    Fires when a response body lacks the exact Sentinel of the
    requested representation. Returns None when the Sentinel
    matches — a matching Sentinel is never a mismatch, even when
    some other field (status, Content-Type, cache state) is wrong.
    """
    if sentinel_match:
        return None
    return make_diagnostic(
        "SENTINEL_MISMATCH",
        f"response body for request {request_index:03d} lacks the exact "
        f"Sentinel of the requested {requested_representation} "
        f"representation",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "requested_representation": requested_representation,
            "expected_sentinel_sha256": expected_sentinel_sha256,
            "body_sha256": body_sha256,
            "sentinel_match": False,
            "observed_content_type": response_content_type,
        },
    )


def check_contract_response(
    *,
    request_index: int,
    experiment_id: str,
    requested_representation: str,
    response_status: int,
    response_content_type: str,
    cache_status: str | None,
    sentinel_match: bool,
    expected_status: int,
    expected_content_type: str,
) -> Diagnostic | None:
    """§8.3 CONTRACT_MISMATCH (status / Content-Type leg).

    Fires when a proxied response has the wrong status or the wrong
    Content-Type for its requested representation. Returns None when
    both match. Sentinel failures are *not* reported here — they are
    §8.5's job (``check_sentinel``) — so one bad response never
    yields two CONTRACT_MISMATCH diagnostics for the same leg.
    Redirects (3xx) are out of scope (§8.6) and are not contract
    mismatches: they return None here and are handled by
    ``check_inconclusive_limit``.
    """
    if 300 <= response_status < 400:
        return None
    mismatches: list[str] = []
    if response_status != expected_status:
        mismatches.append(
            f"status {response_status} (expected {expected_status})"
        )
    if not _content_type_matches(response_content_type, expected_content_type):
        mismatches.append(
            f"content-type {response_content_type!r} (expected "
            f"{expected_content_type!r})"
        )
    if not mismatches:
        return None
    return make_diagnostic(
        "CONTRACT_MISMATCH",
        f"response for request {request_index:03d} violates the "
        f"{requested_representation} contract: " + "; ".join(mismatches),
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "stage": experiment_id,
            "requested_representation": requested_representation,
            "expected": {
                "status": expected_status,
                "content_type": expected_content_type,
            },
            "observed": {
                "status": response_status,
                "content_type": response_content_type,
            },
            "expected_status": expected_status,
            "observed_status": response_status,
            "response_status": response_status,
            "expected_content_type": expected_content_type,
            "observed_content_type": response_content_type,
            "response_content_type": response_content_type,
            "cache_status": cache_status,
            "sentinel_match": sentinel_match,
        },
    )


def check_cache_state(
    *,
    request_index: int,
    experiment_id: str,
    cache_status: str | None,
    origin_counter_delta: int | None,
    cache_key_sha256: str | None,
    cache_entry_id: str | None,
    header_status: str | None = None,
    origin_event_present: bool | None = None,
    cache_reset_confirmed: bool | None = None,
) -> Diagnostic | None:
    """§8.4 CACHE_STATE_UNKNOWN / §8.8 CACHE_EVIDENCE_CONFLICT.

    Inspects one proxied observation's cache evidence:

    * ``cache_status is None`` on a proxied request — no cache
      evidence exists at all — is UNKNOWN (it is *not* a HIT/MISS,
      and it is distinct from the direct-origin ``None`` of ADR-001,
      which never reaches this check because baselines are not
      proxied).
    * A claimed state whose behaviour leg contradicts it (HIT with
      counter delta != 0; MISS/BYPASS with delta != 1; header state
      differing from the verified state) is a CONFLICT — never a
      proven bleed and never a confirmed state.
    * A verified ``CACHE_STATE_UNKNOWN``, a missing header leg
      (HIT/MISS without key or entry id), or a missing origin event
      where one is required (MISS/BYPASS) is UNKNOWN.
    * A confirmed state whose legs agree returns None.

    ``header_status`` is the raw ``X-AcceptTwin-Cache-Status`` header
    when the caller has it (from a RawObservation); ``None`` means
    "not supplied", not "header absent". ``origin_event_present``
    likewise: ``None`` means "not checked". ``cache_reset_confirmed``
    is the run-level reset outcome when the caller knows it (the
    classifier passes it); ``None`` means "not supplied". The
    evidence always carries the §8.4 fields, with ``None`` where a
    leg was not supplied — never a guessed value: ``None`` means
    "unknown", not "absent".
    """
    base_evidence: dict[str, Any] = {
        "cache_status": cache_status,
        "origin_counter_delta": origin_counter_delta,
        "cache_key_sha256": cache_key_sha256,
        "cache_entry_id": cache_entry_id,
        # §8.4 evidence fields (P2-3): header presence is only known
        # when the raw header was supplied; the origin journal counts
        # as available when it was actually consulted.
        "proxy_cache_header_present": (
            True if header_status is not None else None
        ),
        "origin_journal_available": (
            True if origin_event_present is not None else None
        ),
        "cache_reset_confirmed": cache_reset_confirmed,
    }
    if header_status is not None:
        base_evidence["proxy_reported_status"] = header_status

    def unknown(message: str) -> Diagnostic:
        evidence = dict(base_evidence)
        evidence["evidence_conflict"] = False
        return make_diagnostic(
            "CACHE_STATE_UNKNOWN",
            message,
            experiment_id=experiment_id,
            request_index=request_index,
            evidence=evidence,
        )

    def conflict(message: str) -> Diagnostic:
        evidence = dict(base_evidence)
        evidence["evidence_conflict"] = True
        evidence["evidence_consistent"] = False
        return make_diagnostic(
            "CACHE_EVIDENCE_CONFLICT",
            message,
            experiment_id=experiment_id,
            request_index=request_index,
            evidence=evidence,
        )

    if cache_status is None:
        return unknown(
            f"request {request_index:03d} went through the proxy but "
            "carries no cache state at all"
        )
    if cache_status == _CACHE_STATE_UNKNOWN:
        # A raw header that contradicts the behaviour leg is a
        # conflict, not merely unknown (§8.8).
        if (
            header_status in _CONFIRMED_STATES
            and origin_counter_delta is not None
            and (
                (header_status == "HIT" and origin_counter_delta != 0)
                or (
                    header_status in ("MISS", "BYPASS")
                    and origin_counter_delta != 1
                )
            )
        ):
            return conflict(
                f"proxy reported {header_status} for request "
                f"{request_index:03d} but the origin counter moved by "
                f"{origin_counter_delta:+d}"
            )
        return unknown(
            f"cache state for request {request_index:03d} could not be "
            "confirmed with dual evidence"
        )
    if cache_status not in _CONFIRMED_STATES:
        return unknown(
            f"request {request_index:03d} carries unrecognised cache "
            f"state {cache_status!r}"
        )
    # A confirmed state whose legs disagree is a conflict, not a
    # confirmation: the caller must not trust the label.
    if origin_counter_delta is not None:
        if cache_status == "HIT" and origin_counter_delta != 0:
            return conflict(
                f"request {request_index:03d} claims HIT but the origin "
                f"counter moved by {origin_counter_delta:+d}"
            )
        if (
            cache_status in ("MISS", "BYPASS")
            and origin_counter_delta != 1
        ):
            return conflict(
                f"request {request_index:03d} claims {cache_status} but "
                f"the origin counter moved by {origin_counter_delta:+d}"
            )
    if header_status is not None and header_status != cache_status:
        return conflict(
            f"request {request_index:03d} claims {cache_status} but the "
            f"proxy header reported {header_status!r}"
        )
    if cache_status in ("MISS", "HIT"):
        if not cache_key_sha256 or not cache_entry_id:
            return unknown(
                f"request {request_index:03d} claims {cache_status} but "
                "the cache-key or entry-id header leg is missing"
            )
    if cache_status in ("MISS", "BYPASS"):
        if origin_event_present is False:
            return unknown(
                f"request {request_index:03d} claims {cache_status} but "
                "no matching origin event exists"
            )
    return None


def check_bleed(
    *,
    first_request_index: int,
    second_request_index: int,
    experiment_id: str,
    baseline_correct: bool,
    first_correct: bool,
    first_cache_status: str | None,
    first_cache_entry_id: str | None,
    first_body_sha256: str,
    second_cache_status: str | None,
    second_cache_entry_id: str | None,
    second_cache_key_sha256: str | None,
    second_body_sha256: str,
    second_response_content_type: str,
    second_origin_counter_before: int,
    second_origin_counter_after: int,
    second_origin_counter_delta: int,
    second_sentinel_match: bool,
    first_expected_content_type: str,
    requested_representation: str,
) -> Diagnostic | None:
    """§8.2 REPRESENTATION_BLEED.

    Fires only when *all seven* §8.2 conditions hold:

    1. both origin baselines correct;
    2. the first warm request correct;
    3. the second warm request got the *other* representation (its
       body hash equals the first request's body hash, its
       Content-Type equals the first representation's expected
       Content-Type, and its own Sentinel is absent);
    4. the proxy header confirms HIT (verified state HIT);
    5. the origin counter did not move for the second request;
    6. the cache entry is the first request's entry (equal, non-null
       entry ids);
    7. (folded into 3) the second response's Sentinel evidence
       matches the first representation.

    The first request must itself be a confirmed MISS: only a MISS
    stores the entry a later HIT can reuse (a BYPASS stores
    nothing). Any missing link — including a missing entry id —
    fails closed to None: an unproven bleed is never reported as a
    proven one (§8.2, §9.6 step 5).
    """
    if not baseline_correct:
        return None
    if not first_correct:
        return None
    if first_cache_status != "MISS":
        return None
    if second_cache_status != "HIT":
        return None
    if second_origin_counter_delta != 0:
        return None
    if (
        first_cache_entry_id is None
        or second_cache_entry_id is None
        or first_cache_entry_id != second_cache_entry_id
    ):
        return None
    if second_body_sha256 != first_body_sha256:
        return None
    if not _content_type_matches(
        second_response_content_type, first_expected_content_type
    ):
        return None
    if second_sentinel_match:
        return None
    return make_diagnostic(
        "REPRESENTATION_BLEED",
        f"warm-cache request {second_request_index:03d} for "
        f"{requested_representation} was served the other "
        f"representation from a verified HIT of the entry stored by "
        f"request {first_request_index:03d}",
        experiment_id=experiment_id,
        request_index=second_request_index,
        evidence={
            "experiment_id": experiment_id,
            "requested_representation": requested_representation,
            "observed_representation": (
                "markdown" if requested_representation == "html" else "html"
            ),
            "cache_status": "HIT",
            "cache_key_sha256": second_cache_key_sha256,
            "cache_entry_id": second_cache_entry_id,
            "origin_counter_before": second_origin_counter_before,
            "origin_counter_after": second_origin_counter_after,
            "origin_counter_delta": second_origin_counter_delta,
            "sentinel_match": False,
            "body_sha256": second_body_sha256,
            "first_request_index": first_request_index,
        },
    )


def check_no_store_policy(
    *,
    request_index: int,
    experiment_id: str,
    cache_status: str | None,
    cache_entry_count_before: int | None = None,
    cache_entry_count_after: int | None = None,
    cache_entry_id: str | None = None,
    cache_control: str | None = None,
) -> Diagnostic | None:
    """§8.9 CACHE_POLICY_MISMATCH (``no_store`` leg).

    Fires when a confirmed MISS (which creates a cache entry) or a
    confirmed HIT (which reuses one) is observed under a ``no_store``
    contract. Returns None for BYPASS, for unconfirmed states
    (UNKNOWN / conflict — storage cannot be proven from them), and
    for a ``None`` state.
    """
    if cache_status not in ("MISS", "HIT"):
        return None
    return make_diagnostic(
        "CACHE_POLICY_MISMATCH",
        f"contract declares no_store but request {request_index:03d} "
        f"was {cache_status} — the proxy stored or reused a response",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "declared_cache_mode": "no_store",
            "observed_cache_status": cache_status,
            "cache_entry_count_before": cache_entry_count_before,
            "cache_entry_count_after": cache_entry_count_after,
            "cache_entry_id": cache_entry_id,
            "cache_control": cache_control,
        },
    )


def check_variant_by_accept_policy(
    *,
    request_index: int,
    experiment_id: str,
    cache_status: str | None,
    cache_entry_count_before: int | None = None,
    cache_entry_count_after: int | None = None,
    cache_entry_id: str | None = None,
    cache_control: str | None = None,
    vary: str | None = None,
) -> Diagnostic | None:
    """§8.9 CACHE_POLICY_MISMATCH (``variant_by_accept`` leg).

    Fires when a *confirmed* BYPASS is observed under a
    ``variant_by_accept`` contract. §5.4/§6.1 expect a cold or warm
    request under this mode to be MISS: a BYPASS means the cache
    never stored anything, so per-representation isolation was never
    exercised at all — certifying such a run PASS would authenticate
    isolation that was never tested (the ``disabled`` proxy mode
    under a variant contract is exactly this shape). Returns None
    for MISS/HIT (the mode's normal states), for unconfirmed states
    (UNKNOWN / conflict / ``None`` — a BYPASS that was not confirmed
    with dual evidence is an evidence problem, §8.4, not a proven
    policy violation), and under any other contract mode. The caller
    must pass only the *confirmed* state (see
    ``accepttwin.classifier``), never the raw claimed state.

    ``Vary: *`` exemption (T008, ADR-004, PROJECT_BOOK §11.3 E03):
    when the response's ``Vary`` contains ``*``, RFC 9111 §4.1
    forbids reusing the stored response at all, so *not* storing it
    (BYPASS) is the compliant outcome, not a policy violation — the
    isolation argument is moot because no entry exists to be reused,
    and every response is still judged on its own status /
    Content-Type / Sentinel. Pass the response's Vary value as
    ``vary`` (``None`` = unknown / not supplied, which does *not*
    exempt); a ``"*"`` token anywhere in the comma-separated value
    exempts this request.
    """
    if cache_status != "BYPASS":
        return None
    if vary is not None and "*" in [
        token.strip() for token in vary.split(",")
    ]:
        return None
    return make_diagnostic(
        "CACHE_POLICY_MISMATCH",
        f"contract declares variant_by_accept but request "
        f"{request_index:03d} was BYPASS — the proxy stored nothing, "
        "so per-representation cache isolation was never exercised",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "declared_cache_mode": "variant_by_accept",
            "observed_cache_status": "BYPASS",
            "cache_entry_count_before": cache_entry_count_before,
            "cache_entry_count_after": cache_entry_count_after,
            "cache_entry_id": cache_entry_id,
            "cache_control": cache_control,
        },
    )


def check_unexpected_hit(
    *,
    request_index: int,
    experiment_id: str,
    requested_representation: str,
    cache_status: str | None,
    response_status: int,
    response_content_type: str,
    sentinel_match: bool,
    expected_status: int,
    expected_content_type: str,
    reset_confirmed: bool,
) -> Diagnostic | None:
    """§8.3 CONTRACT_MISMATCH (unexpected-HIT leg).

    Fires when a request that must start from an empty cache — a cold
    request (003/004) or a warm first request (005/007) — or a warm
    second request (006/008) served its *correct* representation, is
    nevertheless a confirmed HIT. After a confirmed reset no entry
    for that representation can exist, so the HIT contradicts the
    cold-cache premise (§5.4). Returns None for MISS/BYPASS, for
    unconfirmed states, for a HIT serving the *wrong* representation
    (that is §8.2's job, via ``check_bleed``), and when the reset was
    not confirmed (then the HIT may be a stale entry from a failed
    reset, which is an evidence problem, not a proven violation).
    """
    if cache_status != "HIT" or not reset_confirmed:
        return None
    if not _representation_correct(
        response_status=response_status,
        response_content_type=response_content_type,
        sentinel_match=sentinel_match,
        expected_status=expected_status,
        expected_content_type=expected_content_type,
    ):
        return None
    return make_diagnostic(
        "CONTRACT_MISMATCH",
        f"request {request_index:03d} for {requested_representation} "
        "was a HIT immediately after a confirmed cache reset, but no "
        "entry for that representation could exist yet",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={
            "stage": experiment_id,
            "requested_representation": requested_representation,
            "expected": {
                "status": expected_status,
                "content_type": expected_content_type,
            },
            "observed": {
                "status": response_status,
                "content_type": response_content_type,
            },
            "expected_status": expected_status,
            "observed_status": response_status,
            "response_status": response_status,
            "expected_content_type": expected_content_type,
            "observed_content_type": response_content_type,
            "response_content_type": response_content_type,
            "cache_status": "HIT",
            "sentinel_match": sentinel_match,
        },
    )


def check_inconclusive_limit(
    *,
    request_index: int | None,
    experiment_id: str | None,
    limit_code: str,
    response_status: int | None = None,
    body_size: int | None = None,
    supported_limit: int | None = None,
    transport_error: str | None = None,
    detail: str = "",
    request_url: str | None = None,
    redirect_target: str | None = None,
) -> Diagnostic | None:
    """§8.6 INCONCLUSIVE_LIMIT.

    Fires for exactly one *limit_code* at a time; the caller decides
    which out-of-scope condition applies. Returns None only when
    *limit_code* is empty (no limit was hit) — every named limit is
    by definition out of the supported range, so a named code always
    produces the diagnostic.

    ``request_url`` is the §8.6 evidence field of the same name; it
    is only available when the caller has a RawObservation (which
    carries ``url``) — the frozen RequestObservation has no URL
    field, so callers that only have frozen observations must leave
    it ``None`` (unknown, never guessed; see ADR-002). Likewise
    ``redirect_target`` is only recorded when the caller has a
    verified Location value.
    """
    if not limit_code:
        return None
    message = (
        f"out of supported range ({limit_code})"
        + (f": {detail}" if detail else "")
    )
    evidence: dict[str, Any] = {"limit_code": limit_code}
    if request_url is not None:
        evidence["request_url"] = request_url
    if redirect_target is not None:
        evidence["redirect_target"] = redirect_target
    if response_status is not None:
        evidence["response_status"] = response_status
    if body_size is not None:
        evidence["body_size"] = body_size
    if supported_limit is not None:
        evidence["supported_limit"] = supported_limit
    if transport_error is not None:
        evidence["transport_error"] = transport_error
    return make_diagnostic(
        "INCONCLUSIVE_LIMIT",
        message,
        experiment_id=experiment_id,
        request_index=request_index,
        evidence=evidence,
    )


def check_vary(
    *,
    request_index: int,
    experiment_id: str,
    requested_representation: str,
    vary_accept_present: bool,
    vary_accept_required: bool,
    cacheable: bool,
) -> Diagnostic | None:
    """§8.7 VARY_ACCEPT_ABSENT — or CONTRACT_MISMATCH when required.

    * Not cacheable (``no_store``) or Vary present: None — there is
      nothing to warn about.
    * Cacheable, Vary absent, contract requires it (§5.2): a
      CONTRACT_MISMATCH — a contract violation, but still never a
      REPRESENTATION_BLEED (I-11).
    * Cacheable, Vary absent, contract merely advisory / not
      required: a VARY_ACCEPT_ABSENT WARNING. This never changes a
      verdict on its own (§8.7, I-09).
    """
    if not cacheable or vary_accept_present:
        return None
    if vary_accept_required:
        return make_diagnostic(
            "CONTRACT_MISMATCH",
            f"contract requires Vary: Accept but the origin response "
            f"for request {request_index:03d} does not declare it",
            experiment_id=experiment_id,
            request_index=request_index,
            evidence={
                "stage": experiment_id,
                "requested_representation": requested_representation,
                "expected": "Vary: Accept",
                "observed": None,
                "vary_accept": "required",
            },
        )
    return make_diagnostic(
        "VARY_ACCEPT_ABSENT",
        f"origin response for request {request_index:03d} does not "
        "declare Vary: Accept; the cache must still be judged by its "
        "actual behaviour, not by this header alone (I-11)",
        experiment_id=experiment_id,
        request_index=request_index,
        evidence={"vary_accept": "advisory"},
    )


def check_reset_evidence(
    reset_evidence: list[Any] | tuple[Any, ...] | None,
) -> Diagnostic | None:
    """§8.4 CACHE_STATE_UNKNOWN (reset leg).

    Fires when no reset was recorded at all (``None`` is tolerated
    as "not supplied" and returns None; an empty list means the run
    recorded no confirmed reset) or when any recorded reset failed
    (``success`` false or entries left behind). A failed reset means
    no later cold-cache claim can be trusted (§5.3 D, §11.2 C23).
    Returns None when every recorded reset succeeded with zero
    entries left — or when the caller supplied no reset evidence at
    all (``None``).
    """
    if reset_evidence is None:
        return None
    if len(reset_evidence) == 0:
        return make_diagnostic(
            "CACHE_STATE_UNKNOWN",
            "no cache reset was recorded, so no cold-cache claim can "
            "be confirmed",
            evidence={
                "proxy_cache_header_present": None,
                "origin_journal_available": None,
                "origin_counter_delta": None,
                "cache_reset_confirmed": False,
                "evidence_conflict": False,
            },
        )
    for reset in reset_evidence:
        success = getattr(reset, "success", None)
        after = getattr(reset, "entries_after", None)
        if success is not True or after != 0:
            return make_diagnostic(
                "CACHE_STATE_UNKNOWN",
                "a cache reset did not reach a confirmed empty state "
                f"(namespace={getattr(reset, 'namespace', None)!r}, "
                f"success={success!r}, entries_after={after!r}), so "
                "cold-cache claims cannot be confirmed",
                evidence={
                    "proxy_cache_header_present": None,
                    "origin_journal_available": None,
                    "origin_counter_delta": None,
                    "cache_reset_confirmed": False,
                    "evidence_conflict": False,
                },
            )
    return None
```

## src/accepttwin/evidence.py

- SHA-256：`3b267f3df68e49f211ba7e6bd23db6a70322180405ed86b436a5c2a681ea9fb6`
- 字节数：11109

```
"""Raw observation evidence (P032 T005).

Implements IMPLEMENTATION_PLAN §5.5 / T005 and PROJECT_BOOK §5.3,
§5.4, §6, §7.12:

* :class:`RequestObservation` — the frozen §5.5 dataclass: one entry
  per HTTP request actually sent, carrying only hashes and match
  results, never the response body itself (§7.12 I-12);
* :class:`RawObservation` — the richer per-request record the runner
  writes to the raw-observations file for T006 (classifier) and T007
  (independent Oracle) to read independently: method, URL, Accept,
  status, Content-Type, Sentinel match, body SHA-256, the full cache
  response headers, and the measured origin-counter / cache-entry
  deltas. Still no body text anywhere;
* :func:`write_evidence_file` / :func:`read_evidence_file` — the
  raw-observations file format (``accepttwin.raw-observations/v1``),
  JSON with sorted keys, deterministic (no timestamps, no process
  ids, no ephemeral ports beyond the contract URLs themselves, no
  body bytes).

Nothing in this module performs I/O against a server, reads proxy
environment variables, or invents an observation: it only records
what the runner measured on the wire.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "RAW_OBSERVATIONS_FORMAT",
    "RawObservation",
    "RequestObservation",
    "read_evidence_file",
    "write_evidence_file",
]

#: Format marker written at the top of every raw-observations file.
RAW_OBSERVATIONS_FORMAT = "accepttwin.raw-observations/v1"


# ---------------------------------------------------------------------------
# §5.5 RequestObservation (frozen interface)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RequestObservation:
    """One observed request, per IMPLEMENTATION_PLAN §5.5.

    ``cache_status`` is the *verified* cache state from the dual
    evidence (§5.3: ``"MISS"`` / ``"HIT"`` / ``"BYPASS"`` /
    ``"CACHE_STATE_UNKNOWN"``) for requests sent through the proxy,
    and ``None`` for direct-origin baseline requests (001 O-H, 002
    O-M), which never touch the cache. The raw response body is never
    stored here (§7.12 I-12); only its SHA-256 and whether the
    requested representation's Sentinel matched byte-exactly.

    The ``str | None`` type (widened from the frozen §5.5 ``str``)
    is recorded in ``00_control/ADR-001.md``: only the two
    direct-origin baseline requests take ``None``; every proxied
    request (003–008) carries a verified state string. T006/T007
    must treat ``None`` as "direct-origin, no cache evidence", never
    as ``"CACHE_STATE_UNKNOWN"``.
    """

    request_index: int
    experiment_id: str
    requested_representation: str
    response_status: int
    response_content_type: str
    body_sha256: str
    sentinel_match: bool
    cache_status: str | None
    cache_key_sha256: str | None
    cache_entry_id: str | None
    origin_counter_before: int
    origin_counter_after: int
    origin_counter_delta: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_index": self.request_index,
            "experiment_id": self.experiment_id,
            "requested_representation": self.requested_representation,
            "response_status": self.response_status,
            "response_content_type": self.response_content_type,
            "body_sha256": self.body_sha256,
            "sentinel_match": self.sentinel_match,
            "cache_status": self.cache_status,
            "cache_key_sha256": self.cache_key_sha256,
            "cache_entry_id": self.cache_entry_id,
            "origin_counter_before": self.origin_counter_before,
            "origin_counter_after": self.origin_counter_after,
            "origin_counter_delta": self.origin_counter_delta,
        }


# ---------------------------------------------------------------------------
# Raw observation (runner -> evidence file -> T006 / T007)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawObservation:
    """The full per-request record written to the evidence file.

    Extends :class:`RequestObservation` with the request line
    (method / URL / Accept), the complete lower-cased response-header
    set, the body size, the SHA-256 of the *expected* Sentinel (so a
    reader can check which Sentinel was expected without the evidence
    file carrying the Sentinel string itself), the dual-evidence
    verification outcome, and the cache-entry counts before/after.
    No field here carries response body text.
    """

    request_index: int
    experiment_id: str
    requested_representation: str
    method: str
    url: str
    accept: str
    response_status: int
    response_content_type: str
    body_sha256: str
    body_size: int
    sentinel_match: bool
    sentinel_sha256: str
    response_headers: dict[str, str] = field(default_factory=dict)
    cache_status_header: str | None = None
    cache_key_sha256: str | None = None
    cache_entry_id: str | None = None
    verified_cache_state: str | None = None
    cache_verification_reasons: tuple[str, ...] = ()
    cache_entry_count_before: int | None = None
    cache_entry_count_after: int | None = None
    origin_counter_before: int = 0
    origin_counter_after: int = 0
    origin_counter_delta: int = 0
    origin_event_present: bool | None = None
    transport_error: str | None = None

    def to_request_observation(self) -> RequestObservation:
        """Project this record down to the frozen §5.5 observation."""
        return RequestObservation(
            request_index=self.request_index,
            experiment_id=self.experiment_id,
            requested_representation=self.requested_representation,
            response_status=self.response_status,
            response_content_type=self.response_content_type,
            body_sha256=self.body_sha256,
            sentinel_match=self.sentinel_match,
            cache_status=self.verified_cache_state,
            cache_key_sha256=self.cache_key_sha256,
            cache_entry_id=self.cache_entry_id,
            origin_counter_before=self.origin_counter_before,
            origin_counter_after=self.origin_counter_after,
            origin_counter_delta=self.origin_counter_delta,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_index": self.request_index,
            "experiment_id": self.experiment_id,
            "requested_representation": self.requested_representation,
            "method": self.method,
            "url": self.url,
            "accept": self.accept,
            "response_status": self.response_status,
            "response_content_type": self.response_content_type,
            "body_sha256": self.body_sha256,
            "body_size": self.body_size,
            "sentinel_match": self.sentinel_match,
            "sentinel_sha256": self.sentinel_sha256,
            "response_headers": dict(self.response_headers),
            "cache_status_header": self.cache_status_header,
            "cache_key_sha256": self.cache_key_sha256,
            "cache_entry_id": self.cache_entry_id,
            "verified_cache_state": self.verified_cache_state,
            "cache_verification_reasons": list(self.cache_verification_reasons),
            "cache_entry_count_before": self.cache_entry_count_before,
            "cache_entry_count_after": self.cache_entry_count_after,
            "origin_counter_before": self.origin_counter_before,
            "origin_counter_after": self.origin_counter_after,
            "origin_counter_delta": self.origin_counter_delta,
            "origin_event_present": self.origin_event_present,
            "transport_error": self.transport_error,
        }


def sentinel_sha256(sentinel: str) -> str:
    """SHA-256 of a Sentinel string (the evidence file never stores
    the Sentinel itself; §7.12 allows only the declared identifier,
    and the hash is what §8.1 diagnostics cite as
    ``expected_sentinel_sha256``)."""
    return hashlib.sha256(sentinel.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Evidence file (JSON)
# ---------------------------------------------------------------------------


#: Field names that must never appear in an evidence dict, at any
#: depth (§7.12 I-12). ``body_sha256`` / ``body_size`` are hashes and
#: sizes, not body text, and are allowed.
_FORBIDDEN_BODY_FIELDS = frozenset({"body_text", "response_body", "body"})


def _reject_body_fields(value: Any, where: str = "evidence") -> None:
    """Recursively reject any ``_FORBIDDEN_BODY_FIELDS`` key in
    *value* (dicts, lists and tuples are walked to any depth)."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _FORBIDDEN_BODY_FIELDS:
                raise ValueError(
                    f"evidence must not contain a {key!r} field ({where})"
                )
            _reject_body_fields(item, f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_body_fields(item, f"{where}[{index}]")


def write_evidence_file(path: str | Path, evidence: dict[str, Any]) -> Path:
    """Write *evidence* as deterministic JSON (sorted keys, UTF-8).

    The caller is responsible for the content: this function only
    serialises. It refuses to write anything carrying a ``body_text``
    / ``response_body`` / ``body`` field at *any* depth of the
    evidence dict — a fail-closed guard for §7.12 I-12, so body text
    cannot smuggle itself in nested inside an observation. (Body
    *hashes* such as ``body_sha256`` and sizes such as ``body_size``
    are fine; the check looks for the exact field names, not for
    hashes.)
    """
    path = Path(path)
    if "format" not in evidence:
        raise ValueError("evidence dict must carry a 'format' field")
    _reject_body_fields(evidence)
    text = json.dumps(evidence, sort_keys=True, indent=2, ensure_ascii=False)
    text += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def read_evidence_file(path: str | Path) -> dict[str, Any]:
    """Read back a raw-observations file written by
    :func:`write_evidence_file`. Raises :class:`ValueError` when the
    file is not a JSON object or does not carry the expected format
    marker."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read evidence file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"evidence file {path} must contain a JSON object")
    if data.get("format") != RAW_OBSERVATIONS_FORMAT:
        raise ValueError(
            f"evidence file {path} has format {data.get('format')!r}; "
            f"expected {RAW_OBSERVATIONS_FORMAT!r}"
        )
    return data
```

## src/accepttwin/experiment_runner.py

- SHA-256：`12030e60a05839849309beda0ac167cea5b9bc68a9ef43e742029d2d212650c5`
- 字节数：33159

```
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
```

## src/accepttwin/origin_server.py

- SHA-256：`b80d3cd6c54e6391561e3143db425f02e1b8e8fd2f6da3ad2815fabb736dcdc4`
- 字节数：30813

```
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
```

## src/accepttwin/privacy.py

- SHA-256：`911bd4cd519561983ded1c8783567dfe0f8d15ff60a14b9677fc13686f6e3f9d`
- 字节数：26181

```
"""Privacy and local-security regression layer (P032 T011).

Implements the checks behind PROJECT_BOOK §17 (privacy, security and
data management), §5.1.1 (loopback-only URLs), §5.1.3 (fixed request
headers) and §7.12 I-12 (no raw body text in logs or reports), as
specified by IMPLEMENTATION_PLAN T011.

This module is a *regression layer*, not a second implementation of
the boundaries it guards:

* URL loopback validation is delegated to
  :mod:`accepttwin.url_guard` (T002) — :func:`check_loopback_url`
  only re-raises its verdict as :class:`PrivacyError`;
* request-header validation is delegated to
  :mod:`accepttwin.request_headers` (T002) — :func:`check_request_headers`
  only re-raises its verdict as :class:`PrivacyError`;
* the forbidden report keys below are the same frozen set used by
  :mod:`accepttwin.report_builder` (T009) and ``scripts/embed_report.py``
  (T010); ``tests/privacy/test_log_confidentiality.py`` asserts the
  three sets stay identical, so a drift in any one of them fails loudly
  instead of silently narrowing the ban;
* the Sentinel literals are the frozen values from PROJECT_BOOK §5.1.2
  (see also VERIFY_LOG D-08); the same test file asserts they match
  ``contracts/site.json``.

What this module *does* own:

* the 1 MiB body cap (§17.4 item 8): :func:`check_body_size` /
  :func:`enforce_body_limit`;
* log/report auditing: :func:`scan_text_for_sensitive_headers`,
  :func:`scan_text_for_sentinels`, :func:`scan_text_for_body`,
  :func:`find_forbidden_keys`, :func:`assert_log_clean`,
  :func:`assert_report_clean`;
* self-contained-HTML auditing: :func:`scan_html_for_remote_resources`,
  :func:`scan_html_directory`, :func:`assert_html_directory_clean`;
* the workspace-bounded cleanup command (§17.3):
  :func:`resolve_cleanup_target` / :func:`delete_evidence_files`
  (CLI: ``scripts/clean_evidence.py``).

Fail-closed throughout: every checker raises :class:`PrivacyError`
(or returns the violations) instead of silently dropping the offending
input, and no checker ever reads an environment variable, the network,
or a credential. The module performs no I/O except the HTML-directory
scan and the explicit cleanup deletion, both of which take their root
as an argument.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Mapping

from .request_headers import (
    HeaderError,
    assert_request_headers,
)
from .url_guard import URLGuardError, ValidatedURL, validate_loopback_url

#: §17.4 item 8 — response bodies are limited to 1 MiB. The same value
#: is the default of ``limits.max_body_bytes`` in the contract schema
#: (T002) and the classifier's out-of-scope check (T006, E21).
MAX_BODY_BYTES: int = 1_048_576

#: Frozen Sentinel literals, PROJECT_BOOK §5.1.2. They must never appear
#: in a log, a report or generated HTML — only their SHA-256 and the
#: boolean ``sentinel_match`` flag may be recorded (§7.12 I-12).
SENTINELS: tuple[str, ...] = (
    "AT_HTML_SENTINEL_001",
    "AT_MARKDOWN_SENTINEL_001",
)

#: Keys that must never appear in a report, a log record or generated
#: HTML, matched case-insensitively (§7.12 I-12, §5.1.3, §17.2).
#: Identical to ``report_builder._FORBIDDEN_KEYS`` and
#: ``embed_report._FORBIDDEN_KEYS`` by construction (see the
#: cross-check test in tests/privacy/).
FORBIDDEN_REPORT_KEYS: frozenset[str] = frozenset(
    {
        "body",
        "body_text",
        "response_body",
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
    }
)

#: Request-header names that are sensitive and must never be sent,
#: stored or logged (§17.2, §5.1.3). Compared case-insensitively.
SENSITIVE_HEADER_NAMES: frozenset[str] = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
    }
)


class PrivacyError(ValueError):
    """Raised when a privacy or local-security boundary is violated."""


# ---------------------------------------------------------------------------
# Delegated boundary checks (T002 foundations, re-raised as PrivacyError)
# ---------------------------------------------------------------------------


def check_loopback_url(url: str) -> ValidatedURL:
    """Validate *url* against the loopback guard (§5.1.1, §17.4 1–3).

    Accepts only ``http`` URLs whose *resolved* addresses are all
    loopback. Raises :class:`PrivacyError` for a public IPv4/IPv6
    address, a name resolving to a non-loopback address, a non-HTTP
    scheme, userinfo, a fragment or an illegal port. Never corrects
    the input.
    """
    try:
        return validate_loopback_url(url)
    except (URLGuardError, ValueError) as exc:
        raise PrivacyError(f"URL rejected by the loopback guard: {exc}") from exc


def check_request_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Validate *headers* against the fixed whitelist (§5.1.3, §17.2).

    Returns the normalised fixed header set for the representation.
    Raises :class:`PrivacyError` for any non-whitelisted header —
    including ``Authorization`` and ``Cookie`` in any casing — for a
    wrong ``Accept`` value, or for a missing/altered fixed header.
    """
    try:
        return assert_request_headers(headers)
    except HeaderError as exc:
        raise PrivacyError(
            f"request headers rejected by the fixed whitelist: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Body-size cap (§17.4 item 8)
# ---------------------------------------------------------------------------


def check_body_size(size: int, limit: int = MAX_BODY_BYTES) -> int:
    """Return *size* when it is within the body cap, else raise.

    ``size`` must be a non-negative integer no larger than *limit*
    (default 1 MiB). A negative size is a caller bug and is rejected
    rather than clamped. The check is on the measured size, never on
    a claimed ``Content-Length``.
    """
    if not isinstance(size, int) or isinstance(size, bool):
        raise PrivacyError(f"body size must be an integer, got {size!r}")
    if size < 0:
        raise PrivacyError(f"body size must not be negative, got {size}")
    if size > limit:
        raise PrivacyError(
            f"body size {size} exceeds the {limit} byte limit"
        )
    return size


def enforce_body_limit(body: bytes, limit: int = MAX_BODY_BYTES) -> bytes:
    """Return *body* unchanged when it is within the cap, else raise.

    The guard for callers that hold raw bytes: the body is measured
    and rejected before it is stored, logged or classified.
    """
    if not isinstance(body, (bytes, bytearray)):
        raise PrivacyError(f"body must be bytes, got {type(body).__name__}")
    check_body_size(len(body), limit)
    return bytes(body)


#: Chunk size for :func:`read_http_body_bounded`: small enough that a
#: single read never dominates memory, large enough to keep the read
#: loop cheap.
_BOUNDED_READ_CHUNK = 65_536


def read_http_body_bounded(
    response: BinaryIO,
    limit: int = MAX_BODY_BYTES,
    *,
    sentinel: bytes = b"",
) -> tuple[bytes, int, str, bool]:
    """Stream-read one HTTP response body with a bounded allocation.

    T014 (T011 F-01 / T013-F04): the two production read sites
    (:func:`accepttwin.experiment_runner._http_get` and
    :meth:`accepttwin.cache_proxy.ControlledCacheProxy._fetch_origin`)
    used unbounded ``resp.read()``, so a faulty origin could force a
    single allocation of the whole body. This is the single bounded
    reader both sites use.

    Returns ``(retained, total_size, body_sha256, sentinel_match)``:

    * *retained* — the first ``limit + 1`` bytes only (one byte past
      the cap, so a caller can tell "over the limit" from "exactly at
      the limit" without holding the whole body). A body within the
      cap is returned whole.
    * *total_size* — the exact number of bytes streamed, even for an
      oversize body (counted, never allocated).
    * *body_sha256* — the SHA-256 of the *entire* stream, hashed
      incrementally, so evidence stays exact for oversize bodies.
    * *sentinel_match* — whether *sentinel* occurs anywhere in the
      stream (scanned with a one-sentinel overlap between chunks, so
      a Sentinel straddling a chunk boundary or lying past the
      retained prefix is still found). An empty *sentinel* matches,
      matching ``b"" in body``.

    The only allocation is the retained prefix (``<= limit + 1``
    bytes) plus one 64 KiB chunk and a short overlap buffer. The
    stream is always fully consumed (a truncated read would corrupt
    the connection accounting of the caller's HTTP client).
    """
    if limit < 0:
        raise PrivacyError(f"body limit must not be negative, got {limit}")
    hasher = hashlib.sha256()
    retained = bytearray()
    total = 0
    match = not sentinel
    overlap = b""
    keep = limit + 1
    tail_len = max(len(sentinel) - 1, 0)
    while True:
        chunk = response.read(_BOUNDED_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        hasher.update(chunk)
        if len(retained) < keep:
            retained += chunk[: keep - len(retained)]
        if sentinel and not match:
            window = overlap + chunk
            if sentinel in window:
                match = True
            overlap = window[-tail_len:] if tail_len else b""
    return bytes(retained), total, hasher.hexdigest(), match


# ---------------------------------------------------------------------------
# Log / report auditing (§7.12 I-12, §17.2)
# ---------------------------------------------------------------------------

#: A header line ``Authorization: ...`` / ``Cookie: ...`` (any casing,
#: optional leading whitespace) inside free-form log text.
_SENSITIVE_HEADER_LINE_RE = re.compile(
    r"(?im)^[ \t]*(authorization|cookie|proxy-authorization|set-cookie)[ \t]*:"
)

#: A JSON-style key ``"authorization": ...`` / ``'cookie': ...``.
_SENSITIVE_JSON_KEY_RE = re.compile(
    r"""(?i)["'](authorization|cookie|proxy-authorization|set-cookie)["']\s*:"""
)


def scan_text_for_sensitive_headers(text: str) -> list[str]:
    """Return the sorted sensitive header names found in *text*.

    Matches header lines (``Authorization: Bearer ...``) and JSON-style
    keys (``"cookie": "..."``), case-insensitively. The *values* are
    never returned — only the offending names, so the scan result
    itself cannot leak a credential. An empty list means no sensitive
    header was found.
    """
    found: set[str] = set()
    for match in _SENSITIVE_HEADER_LINE_RE.finditer(text):
        found.add(match.group(1).lower())
    for match in _SENSITIVE_JSON_KEY_RE.finditer(text):
        found.add(match.group(1).lower())
    return sorted(found)


def scan_text_for_sentinels(
    text: str, sentinels: tuple[str, ...] = SENTINELS
) -> list[str]:
    """Return the Sentinel literals found verbatim in *text*."""
    return [sentinel for sentinel in sentinels if sentinel in text]


def scan_text_for_body(text: str, body: bytes | str) -> bool:
    """True when the raw *body* appears verbatim in *text*.

    Bodies shorter than 8 characters/bytes are ignored: a match that
    short proves nothing and would false-positive on ordinary words.
    For bytes bodies the UTF-8 decoding is lossy on purpose — the scan
    is fail-closed (it flags more, never less) and the return value is
    a boolean, so no body bytes can leak through the result.
    """
    if isinstance(body, (bytes, bytearray)):
        needle = bytes(body).decode("utf-8", errors="ignore")
    else:
        needle = body
    if len(needle) < 8:
        return False
    return needle in text


def find_forbidden_keys(value: Any, _where: str = "") -> list[str]:
    """Return the forbidden keys found anywhere inside *value*.

    Recurses into dicts, lists and tuples; key comparison is
    case-insensitive exact match against :data:`FORBIDDEN_REPORT_KEYS`.
    Returns dotted paths (``"a.b[0].cookie"``) so the caller can report
    the location without echoing any value.
    """
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            where = f"{_where}.{key}" if _where else str(key)
            if str(key).lower() in FORBIDDEN_REPORT_KEYS:
                found.append(where)
            found.extend(find_forbidden_keys(item, where))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(find_forbidden_keys(item, f"{_where}[{index}]"))
    return found


def assert_log_clean(
    text: str,
    *,
    bodies: tuple[bytes | str, ...] = (),
    sentinels: tuple[str, ...] = SENTINELS,
) -> None:
    """Fail-closed audit for one log / report blob.

    Raises :class:`PrivacyError` listing every violation found —
    sensitive header names, Sentinel literals, forbidden keys in
    embedded JSON-looking text are *not* scanned here (use
    :func:`assert_report_clean` for structured data), and any raw
    body from *bodies* appearing verbatim. The violation listing
    names the *kind* of leak only; it never echoes the leaked text.
    """
    violations: list[str] = []
    headers = scan_text_for_sensitive_headers(text)
    if headers:
        violations.append(
            "sensitive request header(s): " + ", ".join(headers)
        )
    sentinels_found = scan_text_for_sentinels(text, sentinels)
    if sentinels_found:
        violations.append(
            "Sentinel literal(s): " + ", ".join(sentinels_found)
        )
    for body in bodies:
        if scan_text_for_body(text, body):
            violations.append("raw response body text present")
            break
    if violations:
        raise PrivacyError(
            "log/report text failed the privacy audit: " + "; ".join(violations)
        )


def assert_report_clean(report: Mapping[str, Any]) -> None:
    """Fail-closed audit for one structured report dict.

    Raises :class:`PrivacyError` when a forbidden key appears at any
    depth (case-insensitive) or when a Sentinel literal appears in
    the report's JSON serialisation. Hashes (``body_sha256``) and
    boolean ``sentinel_match`` flags are allowed — they are not body
    text and not forbidden keys.
    """
    forbidden = find_forbidden_keys(report)
    if forbidden:
        raise PrivacyError(
            "report contains forbidden key(s): " + ", ".join(forbidden)
        )
    import json

    text = json.dumps(report, ensure_ascii=False, sort_keys=True)
    sentinels_found = scan_text_for_sentinels(text)
    if sentinels_found:
        raise PrivacyError(
            "report contains Sentinel literal(s): "
            + ", ".join(sentinels_found)
        )


# ---------------------------------------------------------------------------
# Self-contained HTML auditing (T010 rule, pinned by T011)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RemoteReference:
    """One remote / non-self-contained reference found in HTML."""

    kind: str
    value: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.kind}: {self.value}"


#: Tags that must never appear in a self-contained report page at all.
_TAG_RES = (
    (re.compile(r"(?i)<link\b[^>]*>", re.DOTALL), "link-tag"),
    (re.compile(r"(?i)<iframe\b[^>]*>", re.DOTALL), "iframe-tag"),
    (re.compile(r"(?i)<img\b[^>]*>", re.DOTALL), "img-tag"),
    (re.compile(r"(?i)<script\b[^>]*\bsrc\s*=", re.DOTALL), "script-src"),
)

_IMPORT_RE = re.compile(r"(?i)@import\b")
_URL_FN_RE = re.compile(r"(?i)url\(\s*(['\"]?)(.*?)\1\s*\)", re.DOTALL)
#: CSS only lives in <style> blocks and style="..." attributes. The
#: ``url()`` / ``@import`` scan is restricted to those contexts on
#: purpose: JavaScript legitimately calls ``URL.createObjectURL`` /
#: ``URL.revokeObjectURL`` (blob download), which contains the letters
#: ``url(`` but is not a CSS fetch and must not false-positive.
_STYLE_BLOCK_RE = re.compile(r"(?is)<style\b[^>]*>(.*?)</style\s*>")
_STYLE_ATTR_RE = re.compile(
    r"(?is)\bstyle\s*=\s*\"([^\"]*)\"|\bstyle\s*=\s*'([^']*)'"
)
_DATA_URI_RE = re.compile(r"(?i)\bdata:[^\"'\s<>]*")
_BARE_URL_RE = re.compile(r"(?i)\bhttps?://[^\s\"'<>]+")
_PROTOCOL_RELATIVE_RE = re.compile(r"(?i)(?:src|href)\s*=\s*['\"]//[^\"']+")

_LOOPBACK_HOSTS = ("localhost", "::1")


def _is_loopback_url_string(url: str) -> bool:
    """True when *url* is an http(s) URL whose host is loopback.

    Only loopback http(s) URLs are tolerated in report text at all —
    they are diagnostic evidence (``request_url`` / ``redirect_target``
    of a local run, §8.6), not fetched resources. Any other host is
    remote.
    """
    from urllib.parse import urlsplit

    try:
        split = urlsplit(url)
    except ValueError:
        return False
    host = (split.hostname or "").lower()
    if host in _LOOPBACK_HOSTS:
        return True
    if host.startswith("127."):
        parts = host.split(".")
        return (
            len(parts) == 4
            and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)
        )
    return False


def scan_html_for_remote_resources(html: str) -> list[RemoteReference]:
    """Scan one HTML document for remote / non-self-contained references.

    Flags, each as a :class:`RemoteReference` (kind, offending snippet):

    * ``link-tag`` / ``iframe-tag`` / ``img-tag`` — any such tag;
    * ``script-src`` — a ``<script>`` with a ``src`` attribute
      (inline ``<script>`` without ``src`` is allowed);
    * ``css-import`` — ``@import`` inside a ``<style>`` block or a
      ``style="..."`` attribute;
    * ``css-url`` — any ``url(...)`` value inside a ``<style>`` block
      or a ``style="..."`` attribute (a CSS ``url()`` always fetches,
      even a loopback one; JavaScript ``URL.createObjectURL`` is not
      CSS and is not flagged);
    * ``data-uri`` — any ``data:`` URI;
    * ``remote-url`` — any bare or attribute ``http(s)://`` /
      protocol-relative URL whose host is not loopback;
    * ``sentinel-literal`` — a frozen Sentinel literal in the page.

    Loopback ``http://127.0.0.1:...`` / ``http://localhost:...`` /
    ``http://[::1]:...`` strings *outside* a ``url()`` are allowed:
    they are diagnostic evidence text (§8.6), not fetched resources.
    An empty list means the page is self-contained by this rule.
    """
    found: list[tuple[int, RemoteReference]] = []

    def add(match: re.Match, kind: str, value: str) -> None:
        found.append((match.start(), RemoteReference(kind=kind, value=value)))

    for pattern, kind in _TAG_RES:
        for match in pattern.finditer(html):
            snippet = re.sub(r"\s+", " ", match.group(0))[:120]
            add(match, kind, snippet)
    # CSS constructs are only meaningful inside <style> blocks and
    # style="..." attributes (see _STYLE_BLOCK_RE note above).
    css_spans: list[tuple[int, str]] = []
    for match in _STYLE_BLOCK_RE.finditer(html):
        css_spans.append((match.start(1), match.group(1)))
    for match in _STYLE_ATTR_RE.finditer(html):
        value = match.group(1) if match.group(1) is not None else match.group(2)
        css_spans.append((match.start(), value or ""))
    for base, css in css_spans:
        for match in _IMPORT_RE.finditer(css):
            found.append(
                (base + match.start(), RemoteReference(kind="css-import", value="@import"))
            )
        for match in _URL_FN_RE.finditer(css):
            value = match.group(2).strip()
            if value:
                found.append(
                    (
                        base + match.start(),
                        RemoteReference(kind="css-url", value=value[:120]),
                    )
                )
    for match in _DATA_URI_RE.finditer(html):
        add(match, "data-uri", match.group(0)[:80])
    for match in _BARE_URL_RE.finditer(html):
        url = match.group(0).rstrip(".,);")
        if not _is_loopback_url_string(url):
            add(match, "remote-url", url[:120])
    for match in _PROTOCOL_RELATIVE_RE.finditer(html):
        add(match, "remote-url", match.group(0)[:120])
    for sentinel in SENTINELS:
        start = 0
        while True:
            index = html.find(sentinel, start)
            if index < 0:
                break
            found.append(
                (index, RemoteReference(kind="sentinel-literal", value=sentinel))
            )
            start = index + len(sentinel)

    found.sort(key=lambda item: item[0])
    return [ref for _, ref in found]


def scan_html_directory(directory: str | Path) -> dict[str, list[RemoteReference]]:
    """Scan every ``*.html`` file in *directory* (non-recursive).

    Returns ``{filename: [violations]}`` for every HTML file found,
    sorted by filename; files with no violations map to ``[]``.
    Raises :class:`PrivacyError` when the directory does not exist.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise PrivacyError(f"HTML directory does not exist: {directory}")
    result: dict[str, list[RemoteReference]] = {}
    for path in sorted(directory.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        result[path.name] = scan_html_for_remote_resources(text)
    return result


def assert_html_directory_clean(
    directory: str | Path, *, expected_count: int | None = None
) -> dict[str, list[RemoteReference]]:
    """Scan *directory* and raise on any violation.

    Returns the per-file scan (all empty lists) on success. When
    *expected_count* is given, the number of ``*.html`` files must
    match it exactly — the count itself is part of the pin, so a
    silently dropped page cannot pass.
    """
    result = scan_html_directory(directory)
    if expected_count is not None and len(result) != expected_count:
        raise PrivacyError(
            f"expected {expected_count} HTML pages in {directory}, "
            f"found {len(result)}"
        )
    bad = {name: refs for name, refs in result.items() if refs}
    if bad:
        detail = "; ".join(
            f"{name}: " + ", ".join(str(ref) for ref in refs)
            for name, refs in sorted(bad.items())
        )
        raise PrivacyError(
            f"remote references in HTML output: {detail}"
        )
    return result


# ---------------------------------------------------------------------------
# Workspace-bounded cleanup (§17.3 — delete, never outside the workspace)
# ---------------------------------------------------------------------------


def resolve_cleanup_target(root: str | Path, target: str | Path) -> Path:
    """Resolve *target* inside *root* or raise :class:`PrivacyError`.

    Rules (fail-closed, checked in this order):

    * *root* must exist and be a directory;
    * *target* must exist, must be a regular file (never a directory),
      and must not itself be a symlink;
    * the fully resolved path (symlinks and ``..`` resolved) must
      still lie inside the resolved *root* — an absolute path outside
      the workspace, a ``..`` escape, or a symlink pointing outside
      are all refused;
    * the workspace root itself can never be a target.

    Returns the resolved absolute path. Nothing is deleted here.
    """
    root_resolved = Path(root).resolve()
    if not root_resolved.is_dir():
        raise PrivacyError(f"cleanup root is not a directory: {root}")
    raw = Path(target)
    candidate = raw if raw.is_absolute() else (root_resolved / raw)
    if candidate.is_symlink():
        raise PrivacyError(
            f"refusing to delete symlink target: {target}"
        )
    if not candidate.exists():
        raise PrivacyError(f"cleanup target does not exist: {target}")
    if not candidate.is_file():
        raise PrivacyError(
            f"cleanup target is not a regular file: {target}"
        )
    resolved = Path(os.path.realpath(candidate))
    if resolved == root_resolved:
        raise PrivacyError(
            f"refusing to delete the workspace root itself: {target}"
        )
    if not resolved.is_relative_to(root_resolved):
        raise PrivacyError(
            f"cleanup target {target} resolves outside the workspace "
            f"({root_resolved})"
        )
    return resolved


def delete_evidence_files(
    root: str | Path,
    targets: list[str | Path],
    *,
    dry_run: bool = False,
    allowed_subtrees: tuple[str, ...] | None = None,
) -> list[Path]:
    """Delete the named files inside *root* (§17.3).

    Every target is validated with :func:`resolve_cleanup_target`
    *before* anything is deleted, so one bad target blocks the whole
    batch — there are no partial deletions. With ``dry_run=True``
    nothing is deleted and the would-be-deleted paths are returned.
    Returns the list of resolved paths deleted (or that would be
    deleted). Raises :class:`PrivacyError` on any refusal.

    *allowed_subtrees* (T014, T011 P2): when given, a target must
    additionally lie under one of the named first-level subtrees
    of *root* (e.g. ``("evidence",)``). The command-line cleanup
    script passes ``("evidence",)`` so an operator explicitly
    naming a file can no longer delete source files by mistake;
    callers that omit it keep the plain workspace boundary.
    """
    if not targets:
        raise PrivacyError("no cleanup targets given")
    resolved = [resolve_cleanup_target(root, target) for target in targets]
    if allowed_subtrees is not None:
        root_resolved = Path(root).resolve()
        for path in resolved:
            rel = path.relative_to(root_resolved)
            if not rel.parts or rel.parts[0] not in allowed_subtrees:
                raise PrivacyError(
                    f"cleanup target {path} is outside the allowed "
                    f"subtree(s): {', '.join(allowed_subtrees)}"
                )
    if dry_run:
        return resolved
    for path in resolved:
        path.unlink()
    return resolved
```

## src/accepttwin/report_builder.py

- SHA-256：`d2f18d3a5d6ae9fd1652da3ec1a66e294ff675676854c5665899118603152a8e`
- 字节数：27048

```
"""Formal machine report ``accepttwin.report/v1`` (P032 T009).

Implements IMPLEMENTATION_PLAN §5.8 / T009 and PROJECT_BOOK §14:

* :func:`build_report` — from a validated contract, the eight
  :class:`~accepttwin.evidence.RequestObservation` objects of one
  frozen four-experiment run, the production
  :class:`~accepttwin.classifier.ClassificationResult` and (when
  available) the independent Oracle result, build the formal
  machine report. The report carries no raw response body text
  (§7.12 I-12), no sensitive request header (§5.1.3, §17) and no
  non-loopback URL (§14.3).
* :func:`compute_report_hash` — ``SHA256(canonical_json_bytes)``
  (§10.4) over the report's hash payload (see below).

Canonical JSON — single source (ADR-003, T009): all normalisation
is :func:`accepttwin.contract.canonical_json_bytes`, reused here,
never re-implemented. The report's ``url`` / ``origin_url`` keep
their real (OS-assigned) ports — execution truth — and the
canonicaliser normalises those ports to 0 in the hash input
(ADR-003). No timestamp, duration, process id, temporary path or
random id is ever put in a report, so none can leak into the hash.

Report hash — what is excluded, and why (§10.4, ADR-003): the hash
input is the report minus :data:`REPORT_HASH_EXCLUDED_FIELDS`.
Those fields are all port-bearing or absolute-counter evidence
whose values cannot be port-normalised, because they are hashes or
copies of values that already contain an ephemeral port:

* ``cache_key_sha256`` — the cache key material is the origin URL
  (with its OS-assigned port) plus Accept (``cache_proxy``:
  ``cache_key_for``), so the key hash changes when the port
  changes; it is a hash, so no normaliser can rewrite it. The
  same holds for ``cache_entry_id``, which derives from the key
  (``entry-<first 16 hex>``). Both stay in the report itself
  (§5.3/§8 evidence, and §4.3 area C needs the cache-key summary)
  but never enter the hash.
* ``origin_counter_before`` / ``origin_counter_after`` — absolute
  counters. Only the delta is hashed, following the T007
  ``canonical_report`` precedent (absolute counters never enter
  the hash); the before/after values stay in the diagnostic
  evidence where §8.2 requires them.
* ``request_url`` / ``redirect_target`` — §8.6 evidence URLs that
  carry the run's ephemeral ports (E12/E22 shapes). They stay in
  the report (desensitised, see below) but never enter the hash.

Everything §10.4 requires in the hash still enters it: the input
contract hash, the scenario id, the four-experiment results, the
origin baselines, the cache-state evidence (state + delta),
diagnostic codes, the final verdict and the first-error location.

Privacy / desensitisation (§7.12, §8.6, §14.3, ADR-002 Decision 4):

* any forbidden key — raw body text (``body``, ``body_text``,
  ``response_body``) or a sensitive header (``authorization``,
  ``cookie``, ``proxy-authorization``, ``set-cookie``), matched
  case-insensitively at any depth of any input — raises
  :class:`ReportError`. A report is never built around forbidden
  content.
* ``redirect_target``: a non-loopback target is never recorded
  verbatim (§8.6: "only a verified desensitised address"); it is
  replaced with the fixed marker :data:`REDACTED_REDIRECT_TARGET`.
  A loopback target is kept (it is still excluded from the hash
  input, see above). A ``request_url`` that is not loopback is
  dropped rather than recorded.

Oracle parity (§4.2 constraint 6, §12.4): a report is marked
``final`` only when an Oracle result was supplied *and* it agrees
with production on verdict, diagnostic projection (code +
request_index, §8 order) and first-error location. Without an
Oracle result the report is still a complete, schema-valid record
of the run, but ``oracle`` is null, ``oracle_parity`` is null and
``final`` is false — never final-valid on production's say-so
alone.

This module deliberately has **no** ``validate`` method: report
validation is independent of the production generator (T009
acceptance). The independent checker lives in
``tests/unit/independent_schema_validator.py`` — it reads only the
Schema file and never imports this module.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from .canonical_json import canonical_json_bytes
from .classifier import VERDICTS, ClassificationResult
from .contract import (
    Contract,
    canonical_contract_hash,
    parse_contract,
    validate_contract,
)
from .diagnostics import (
    CODE_SEVERITY,
    DIAGNOSTIC_CODES,
    Diagnostic,
    diagnostic_order,
)
from .evidence import RequestObservation
from .url_guard import URLGuardError, validate_loopback_url

__all__ = [
    "REDACTED_REDIRECT_TARGET",
    "REPORT_HASH_EXCLUDED_FIELDS",
    "REPORT_SCHEMA",
    "ReportError",
    "build_report",
    "compute_report_hash",
    "report_hash_payload",
]

#: Schema identifier of every report this module builds (§14.3).
REPORT_SCHEMA = "accepttwin.report/v1"

#: Marker written in place of a non-loopback ``redirect_target``
#: (§8.6: only a verified desensitised address may be recorded).
REDACTED_REDIRECT_TARGET = "redacted:non-loopback"

#: Field names removed from the hash payload at any depth (§10.4,
#: ADR-003 — see the module docstring for why each is excluded).
REPORT_HASH_EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {
        "cache_key_sha256",
        "cache_entry_id",
        "origin_counter_before",
        "origin_counter_after",
        "request_url",
        "redirect_target",
    }
)

#: Keys that must never appear in a report, at any depth, matched
#: case-insensitively (§7.12 I-12: no raw body text; §5.1.3/§17: no
#: sensitive request headers).
_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "body",
        "body_text",
        "response_body",
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
    }
)

#: The six frozen experiment ids (§6.3).
EXPERIMENT_IDS: tuple[str, ...] = (
    "ORIGIN_HTML",
    "ORIGIN_MARKDOWN",
    "HTML_COLD",
    "MARKDOWN_COLD",
    "HTML_TO_MARKDOWN",
    "MARKDOWN_TO_HTML",
)

#: Expected number of observations in one complete run (§6.3).
_EXPECTED_OBSERVATIONS = 8


class ReportError(ValueError):
    """Raised when a report cannot be built fail-closed."""


# ---------------------------------------------------------------------------
# Input normalisation
# ---------------------------------------------------------------------------


def _reject_forbidden_keys(value: Any, where: str = "report input") -> None:
    """Recursively reject any :data:`_FORBIDDEN_KEYS` key in *value*."""
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ReportError(
                    f"report must not contain a {key!r} field ({where})"
                )
            _reject_forbidden_keys(item, f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_forbidden_keys(item, f"{where}[{index}]")


def _is_loopback_url(value: Any) -> bool:
    """True when *value* is an ``http`` URL whose host is loopback."""
    if not isinstance(value, str):
        return False
    try:
        validate_loopback_url(value)
    except (URLGuardError, ValueError):
        return False
    return True


def _sanitise_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Copy *evidence*, desensitising URL-bearing fields (§8.6).

    A non-loopback ``redirect_target`` is replaced with
    :data:`REDACTED_REDIRECT_TARGET` (never recorded verbatim); a
    non-loopback ``request_url`` is dropped. Loopback values are
    kept — they are still excluded from the hash input (see
    :data:`REPORT_HASH_EXCLUDED_FIELDS`), so their ephemeral ports
    cannot change the report hash.
    """
    cleaned = copy.deepcopy(evidence)
    if "redirect_target" in cleaned:
        target = cleaned["redirect_target"]
        if target is not None and not _is_loopback_url(target):
            cleaned["redirect_target"] = REDACTED_REDIRECT_TARGET
    if "request_url" in cleaned:
        if not _is_loopback_url(cleaned["request_url"]):
            del cleaned["request_url"]
    return cleaned


def _coerce_contract(contract: Contract | dict[str, Any]) -> Contract:
    """Return a validated :class:`Contract` for *contract*.

    A dict is parsed (and therefore fully validated) with
    :func:`parse_contract`; an instance is re-validated. Anything
    invalid fails here, before any report field is built.
    """
    if isinstance(contract, dict):
        try:
            return parse_contract(contract)
        except ValueError as exc:
            raise ReportError(f"invalid contract for report: {exc}") from exc
    if not isinstance(contract, Contract):
        raise ReportError(f"contract must be a Contract or dict, got {type(contract).__name__}")
    result = validate_contract(contract)
    if not result.ok:
        raise ReportError(
            "invalid contract for report: " + "; ".join(result.errors)
        )
    return contract


def _coerce_observation(obs: RequestObservation | dict[str, Any]) -> dict[str, Any]:
    """Project one observation to the frozen report shape (§5.5/§14)."""
    if isinstance(obs, RequestObservation):
        data = obs.as_dict()
    elif isinstance(obs, dict):
        data = dict(obs)
    else:
        raise ReportError(
            f"observation must be a RequestObservation or dict, got {type(obs).__name__}"
        )
    required = (
        "request_index",
        "experiment_id",
        "requested_representation",
        "response_status",
        "response_content_type",
        "body_sha256",
        "sentinel_match",
        "cache_status",
        "cache_key_sha256",
        "cache_entry_id",
        "origin_counter_delta",
    )
    missing = [key for key in required if key not in data]
    if missing:
        raise ReportError(
            f"observation {data.get('request_index')!r} is missing fields: {missing}"
        )
    if not isinstance(data["request_index"], int) or isinstance(
        data["request_index"], bool
    ):
        raise ReportError("request_index must be an integer")
    if data["request_index"] < 1:
        raise ReportError("request_index must be a positive integer")
    if data["experiment_id"] not in EXPERIMENT_IDS:
        raise ReportError(f"unknown experiment_id {data['experiment_id']!r}")
    if data["requested_representation"] not in ("html", "markdown"):
        raise ReportError(
            f"unknown requested_representation {data['requested_representation']!r}"
        )
    _reject_forbidden_keys(data, "observation")
    return {key: data[key] for key in required}


def _coerce_diagnostic(diag: Diagnostic | dict[str, Any]) -> dict[str, Any]:
    """Project one diagnostic to the frozen report shape (§8/§14)."""
    if isinstance(diag, Diagnostic):
        data = diag.as_dict()
    elif isinstance(diag, dict):
        data = dict(diag)
    else:
        raise ReportError(
            f"diagnostic must be a Diagnostic or dict, got {type(diag).__name__}"
        )
    for key in ("code", "severity", "message"):
        if key not in data:
            raise ReportError(f"diagnostic is missing {key!r}")
    if data["code"] not in DIAGNOSTIC_CODES:
        raise ReportError(f"unknown diagnostic code {data['code']!r}")
    if data["severity"] not in ("CRITICAL", "WARNING"):
        raise ReportError(f"unknown severity {data['severity']!r}")
    if CODE_SEVERITY[data["code"]] != data["severity"]:
        raise ReportError(
            f"diagnostic {data['code']} must have severity "
            f"{CODE_SEVERITY[data['code']]!r}, got {data['severity']!r}"
        )
    if not isinstance(data["message"], str) or not data["message"].strip():
        raise ReportError("diagnostic message must not be blank")
    experiment_id = data.get("experiment_id")
    if experiment_id is not None and experiment_id not in EXPERIMENT_IDS:
        raise ReportError(f"unknown experiment_id {experiment_id!r}")
    request_index = data.get("request_index")
    if request_index is not None and (
        not isinstance(request_index, int)
        or isinstance(request_index, bool)
        or request_index < 1
    ):
        raise ReportError("diagnostic request_index must be a positive integer or null")
    evidence = data.get("evidence", {})
    if not isinstance(evidence, dict):
        raise ReportError("diagnostic evidence must be an object")
    _reject_forbidden_keys(evidence, f"diagnostic {data['code']} evidence")
    return {
        "code": data["code"],
        "severity": data["severity"],
        "message": data["message"],
        "experiment_id": experiment_id,
        "request_index": request_index,
        "evidence": _sanitise_evidence(evidence),
    }


def _diagnostic_projection(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Diagnostics as sorted ``{code, request_index}`` pairs (§12.4)."""
    pairs = [
        {"code": d["code"], "request_index": d["request_index"]}
        for d in diagnostics
    ]
    return sorted(
        pairs,
        key=lambda p: (
            p["request_index"] is None,
            p["request_index"] if p["request_index"] is not None else 0,
            diagnostic_order(p["code"]),
        ),
    )


def _coerce_oracle(oracle_result: Any) -> dict[str, Any] | None:
    """Project an Oracle result to the report's oracle block (§12.4).

    Accepts a dict (the ``oracle.json`` shape) or an object with an
    ``as_dict()`` method. Returns None when *oracle_result* is None.
    """
    if oracle_result is None:
        return None
    if hasattr(oracle_result, "as_dict"):
        data = oracle_result.as_dict()
    elif isinstance(oracle_result, dict):
        data = dict(oracle_result)
    else:
        raise ReportError(
            "oracle_result must be a dict, an object with as_dict(), or None; "
            f"got {type(oracle_result).__name__}"
        )
    _reject_forbidden_keys(data, "oracle result")
    if data.get("verdict") not in VERDICTS:
        raise ReportError(f"oracle verdict {data.get('verdict')!r} is not one of the five frozen verdicts")
    first_error = data.get("first_error")
    if first_error is not None and (
        not isinstance(first_error, int)
        or isinstance(first_error, bool)
        or first_error < 1
    ):
        raise ReportError("oracle first_error must be a positive integer or null")
    first_error_experiment_id = data.get("first_error_experiment_id")
    if (
        first_error_experiment_id is not None
        and first_error_experiment_id not in EXPERIMENT_IDS
    ):
        raise ReportError(
            f"unknown oracle first_error_experiment_id {first_error_experiment_id!r}"
        )
    return {
        "verdict": data["verdict"],
        "first_error": first_error,
        "first_error_experiment_id": first_error_experiment_id,
    }


def _normalise_oracle_cache_states(value: Any) -> list[dict[str, Any]] | None:
    """Normalise an Oracle ``verified_cache_states`` value, or None
    when it is not a well-formed 8-entry list (T014, T013-F02 —
    fail-closed: the caller treats None as a parity failure)."""
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


def _production_cache_states(
    production: dict[str, Any],
) -> list[dict[str, Any]] | None:
    """Per-request verified cache states from the production result,
    normalised the same way as the Oracle side (T014, T013-F02).

    These are the states the production *classifier* trusted
    (``ClassificationResult.confirmed_cache_states``) — not the
    runner's observation-layer states, which the classifier may
    have downgraded. ``"CACHE_STATE_UNKNOWN"`` and ``None`` both
    mean "confirmed nothing". Returns None when the production
    result carries no well-formed 8-entry list (fail-closed).
    """
    value = production.get("confirmed_cache_states")
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
            or (
                state is not None
                and state not in ("MISS", "HIT", "BYPASS", "CACHE_STATE_UNKNOWN")
            )
        ):
            return None
        if state == "CACHE_STATE_UNKNOWN":
            state = None
        states.append({"request_index": index, "state": state})
    states.sort(key=lambda s: s["request_index"])
    if [s["request_index"] for s in states] != list(range(1, 9)):
        return None
    return states


def _oracle_parity(
    production_verdict: str,
    production_diagnostics: list[dict[str, Any]],
    production_first_error: int | None,
    production_first_error_experiment_id: str | None,
    oracle: dict[str, Any],
    oracle_diagnostics: list[dict[str, Any]],
    production_cache_states: list[dict[str, Any]] | None = None,
    oracle_cache_states: Any = None,
) -> bool:
    """True when production and Oracle agree per §12.4.

    Compared: final verdict, diagnostic projection (code +
    request_index), first-error request and first-error experiment,
    and — since T014 / T013-F02 — the per-request verified
    MISS/HIT/BYPASS states. An Oracle result without well-formed
    per-request states fails parity (fail-closed): a state
    disagreement must no longer pass silently behind identical
    verdicts/diagnostics.
    """
    if oracle["verdict"] != production_verdict:
        return False
    if oracle_diagnostics != _diagnostic_projection(production_diagnostics):
        return False
    if oracle["first_error"] != production_first_error:
        return False
    if (
        oracle["first_error_experiment_id"]
        != production_first_error_experiment_id
    ):
        return False
    if production_cache_states is None:
        return False
    oracle_states = _normalise_oracle_cache_states(oracle_cache_states)
    if oracle_states is None:
        return False
    if oracle_states != production_cache_states:
        return False
    return True


# ---------------------------------------------------------------------------
# Report hash (§10.4)
# ---------------------------------------------------------------------------


def _strip_excluded(value: Any) -> Any:
    """Deep-copy *value* with :data:`REPORT_HASH_EXCLUDED_FIELDS` removed."""
    if isinstance(value, dict):
        return {
            key: _strip_excluded(item)
            for key, item in value.items()
            if key not in REPORT_HASH_EXCLUDED_FIELDS
        }
    if isinstance(value, list):
        return [_strip_excluded(item) for item in value]
    return value


def report_hash_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Return the hash payload for *report*: the report without its
    own ``report_hash`` field and without every field in
    :data:`REPORT_HASH_EXCLUDED_FIELDS` (at any depth). The
    ``url`` / ``origin_url`` ports in the payload are normalised to
    0 by :func:`canonical_json_bytes` itself (ADR-003).
    """
    payload = {key: value for key, value in report.items() if key != "report_hash"}
    return _strip_excluded(payload)


def compute_report_hash(report: dict[str, Any]) -> str:
    """Return ``SHA256(canonical_json_bytes(hash payload))`` (§10.4)."""
    if not isinstance(report, dict):
        raise ReportError("report must be a JSON object")
    return hashlib.sha256(
        canonical_json_bytes(report_hash_payload(report))
    ).hexdigest()


# ---------------------------------------------------------------------------
# Report construction (§5.8, §14)
# ---------------------------------------------------------------------------


def build_report(
    contract: Contract | dict[str, Any],
    production_result: ClassificationResult | dict[str, Any],
    oracle_result: Any = None,
    *,
    observations: list[RequestObservation] | tuple[RequestObservation, ...] | list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """Build the formal ``accepttwin.report/v1`` report for one run.

    *contract* is the validated dual-representation contract,
    *production_result* the production
    :class:`~accepttwin.classifier.ClassificationResult` (or its
    ``as_dict()`` shape), *oracle_result* the independent Oracle
    result (``oracle.json`` dict, or None when no Oracle ran).
    *observations* are the eight §5.5 observations in any order;
    *scenario_id* is the Golden id (``C01``–``C24``, ``E01``–``E24``).

    The report is fully deterministic given its inputs: it carries
    no timestamp, duration, process id, temporary path or random
    id. Its ``report_hash`` is computed over the hash payload (see
    :func:`compute_report_hash`), so two runs of the same logical
    scenario on different OS-assigned ports hash identically
    (§10.4, ADR-003). Raises :class:`ReportError` on any invalid,
    incomplete or forbidden input — a report is never built around
    bad evidence.
    """
    validated_contract = _coerce_contract(contract)
    if scenario_id is None or not str(scenario_id).strip():
        raise ReportError("scenario_id is required (Golden id, e.g. 'C11')")
    scenario_id = str(scenario_id)

    if isinstance(production_result, ClassificationResult):
        production = production_result.as_dict()
    elif isinstance(production_result, dict):
        production = dict(production_result)
    else:
        raise ReportError(
            "production_result must be a ClassificationResult or dict; "
            f"got {type(production_result).__name__}"
        )
    _reject_forbidden_keys(production, "production result")
    verdict = production.get("verdict")
    if verdict not in VERDICTS:
        raise ReportError(f"verdict {verdict!r} is not one of the five frozen verdicts")
    diagnostics = [
        _coerce_diagnostic(diag)
        for diag in production.get("diagnostics", [])
    ]
    first_error = production.get("first_error")
    if first_error is not None and (
        not isinstance(first_error, int)
        or isinstance(first_error, bool)
        or first_error < 1
    ):
        raise ReportError("first_error must be a positive integer or null")
    first_error_experiment_id = production.get("first_error_experiment_id")
    if (
        first_error_experiment_id is not None
        and first_error_experiment_id not in EXPERIMENT_IDS
    ):
        raise ReportError(
            f"unknown first_error_experiment_id {first_error_experiment_id!r}"
        )
    reasons = production.get("reasons", [])
    if not isinstance(reasons, list) or not all(
        isinstance(reason, str) for reason in reasons
    ):
        raise ReportError("reasons must be a list of strings")

    if observations is None:
        raise ReportError(
            "observations are required: exactly the eight §5.5 observations "
            "of the run (001–008)"
        )
    obs_list = [_coerce_observation(obs) for obs in observations]
    if len(obs_list) != _EXPECTED_OBSERVATIONS:
        raise ReportError(
            f"exactly {_EXPECTED_OBSERVATIONS} observations are required, got {len(obs_list)}"
        )
    indices = sorted(obs["request_index"] for obs in obs_list)
    if indices != list(range(1, _EXPECTED_OBSERVATIONS + 1)):
        raise ReportError(
            f"observations must cover requests 001–{_EXPECTED_OBSERVATIONS:03d} exactly once each, got {indices}"
        )
    obs_list.sort(key=lambda obs: obs["request_index"])

    oracle = _coerce_oracle(oracle_result)
    oracle_parity: bool | None = None
    if oracle is not None:
        if isinstance(oracle_result, dict):
            raw_diagnostics = oracle_result.get("diagnostics", [])
            raw_cache_states = oracle_result.get("verified_cache_states")
        else:
            raw_diagnostics = getattr(oracle_result, "diagnostics", [])
            raw_cache_states = getattr(
                oracle_result, "verified_cache_states", None
            )
        oracle_diag_projection = _diagnostic_projection(
            [_coerce_diagnostic(diag) for diag in raw_diagnostics]
        )
        oracle_parity = _oracle_parity(
            verdict,
            diagnostics,
            first_error,
            first_error_experiment_id,
            oracle,
            oracle_diag_projection,
            _production_cache_states(production),
            raw_cache_states,
        )

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "project": {"project_id": "P032", "version": "1.0.1"},
        "scenario_id": scenario_id,
        "input": {
            "contract_id": validated_contract.contract_id,
            "contract_sha256": canonical_contract_hash(validated_contract),
            "url": validated_contract.url,
            "origin_url": validated_contract.origin_url,
            "cache_behavior": dict(validated_contract.cache_behavior),
            "request_headers": dict(validated_contract.request_headers),
        },
        "observations": obs_list,
        "diagnostics": diagnostics,
        "verdict": verdict,
        "first_error": first_error,
        "first_error_experiment_id": first_error_experiment_id,
        "critical_count": sum(
            1 for diag in diagnostics if diag["severity"] == "CRITICAL"
        ),
        "warning_count": sum(
            1 for diag in diagnostics if diag["severity"] == "WARNING"
        ),
        "reasons": list(reasons),
        "oracle": oracle,
        "oracle_parity": oracle_parity,
        "final": bool(oracle_parity),
        "report_hash": "",
    }
    # The whole report is scanned once more before hashing: no
    # forbidden key may survive at any depth, whatever the inputs
    # carried (defence in depth — the per-field checks above are
    # the primary guard).
    _reject_forbidden_keys(report, "report")
    report["report_hash"] = compute_report_hash(report)
    return report
```

## src/accepttwin/request_headers.py

- SHA-256：`e3357741eb51649234786b3dfcf6117d9a47cf3bace5d7c4084fc30a7447fc78`
- 字节数：5722

```
"""Fixed request-header whitelist (PROJECT_BOOK §5.1.3, §17.2).

The first release sends exactly four headers, and nothing else:

* ``Accept`` — ``text/html`` for the HTML representation,
  ``text/markdown`` for the Markdown representation (§5.1.2; never modified);
* ``Accept-Encoding: identity``;
* ``User-Agent: AcceptTwin/1.0.0``;
* ``Accept-Language: en``.

Forbidden in the first release (never sent, never accepted from a contract
or a caller): ``Cookie``, ``Authorization``, ``Proxy-Authorization``,
``Referer``, ``Origin``, any user-defined ``X-*`` header, and any
uncontrolled ``Cache-Control`` request directive. Cache control and debug
information are produced inside the controlled proxy, not as user request
headers (§5.1.3).

Header names are compared case-insensitively (RFC 9110 §5.1); values are
compared exactly. Nothing is silently dropped or corrected: validation
returns every violation found.
"""

from __future__ import annotations

from collections.abc import Mapping

ACCEPT_BY_REPRESENTATION: dict[str, str] = {
    "html": "text/html",
    "markdown": "text/markdown",
}

FIXED_COMMON_HEADERS: dict[str, str] = {
    "Accept-Encoding": "identity",
    "User-Agent": "AcceptTwin/1.0.0",
    "Accept-Language": "en",
}

#: Lower-cased names a request may ever carry.
ALLOWED_HEADER_NAMES: frozenset[str] = frozenset(
    {"accept", "accept-encoding", "user-agent", "accept-language"}
)

#: Lower-cased names that are explicitly forbidden (§5.1.3, §17.2).
FORBIDDEN_HEADER_NAMES: frozenset[str] = frozenset(
    {
        "cookie",
        "authorization",
        "proxy-authorization",
        "referer",
        "origin",
        "cache-control",
    }
)


class HeaderError(ValueError):
    """Raised when a request-header set violates the fixed whitelist."""


def build_request_headers(representation: str) -> dict[str, str]:
    """Return the exact fixed header set for *representation*.

    *representation* must be ``"html"`` or ``"markdown"``; anything else
    raises :class:`HeaderError`. The returned mapping is a fresh dict in
    canonical order: ``Accept`` first, then the fixed common headers.
    """
    try:
        accept = ACCEPT_BY_REPRESENTATION[representation]
    except KeyError as exc:
        raise HeaderError(
            f"unknown representation {representation!r}; "
            "expected 'html' or 'markdown'"
        ) from exc
    return {"Accept": accept, **FIXED_COMMON_HEADERS}


def validate_request_headers(headers: Mapping[str, str]) -> list[str]:
    """Validate a caller-supplied header mapping against the whitelist.

    Returns the list of violations (empty means the set is exactly the
    fixed set for one representation). Checks, in order: the mapping is a
    mapping of strings; no duplicate names differing only by case; every
    name is whitelisted (anything else — including ``X-*``, ``Cookie``,
    ``Authorization``, ``Cache-Control`` — is rejected, never ignored);
    ``Accept`` is exactly ``text/html`` or ``text/markdown``; the three
    fixed common headers are present with exactly the frozen values.
    """
    errors: list[str] = []
    if not isinstance(headers, Mapping):
        return ["request headers must be a mapping of header name to value"]

    lowered: dict[str, str] = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            errors.append(
                f"header {name!r}: names and values must both be strings"
            )
            continue
        key = name.lower()
        if key in lowered:
            errors.append(
                f"duplicate header {name!r} (differs only by case from an "
                "earlier header)"
            )
        lowered[key] = value

    for key in sorted(lowered):
        if key.startswith("x-"):
            errors.append(
                f"header {key!r} is a user-defined X-* header, "
                "which is forbidden in the first release"
            )
        elif key in FORBIDDEN_HEADER_NAMES:
            errors.append(f"header {key!r} is forbidden in the first release")
        elif key not in ALLOWED_HEADER_NAMES:
            errors.append(
                f"header {key!r} is not in the fixed request-header whitelist"
            )

    accept = lowered.get("accept")
    if accept is None:
        errors.append("missing required header 'Accept'")
    elif accept not in ACCEPT_BY_REPRESENTATION.values():
        errors.append(
            f"header 'Accept' must be exactly 'text/html' or "
            f"'text/markdown', got {accept!r}"
        )

    for canonical_name, frozen_value in FIXED_COMMON_HEADERS.items():
        key = canonical_name.lower()
        if key not in lowered:
            errors.append(f"missing required header {canonical_name!r}")
        elif lowered[key] != frozen_value:
            errors.append(
                f"header {canonical_name!r} must be exactly "
                f"{frozen_value!r}, got {lowered[key]!r}"
            )

    return errors


def assert_request_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Validate *headers* and return a normalised copy, or raise.

    The returned dict uses the canonical capitalisation (``Accept``,
    ``Accept-Encoding``, ``User-Agent``, ``Accept-Language``).
    """
    errors = validate_request_headers(headers)
    if errors:
        raise HeaderError("; ".join(errors))
    accept = next(
        value for name, value in headers.items() if name.lower() == "accept"
    )
    representation = "html" if accept == "text/html" else "markdown"
    # Rebuild from the frozen values so casing/order can never drift.
    return build_request_headers(representation)
```

## src/accepttwin/schema.py

- SHA-256：`646b586b00f6ff532981f1a973e1fe9e655c7c56cb727a015b6071b6bb28976f`
- 字节数：10323

```
"""JSON Schema for ``accepttwin.contract/v1`` plus a minimal stdlib validator.

Source of truth for the field set: PROJECT_BOOK.md §5.1 (top-level fields),
§5.1.1 (URL rules — semantic checks live in :mod:`accepttwin.url_guard`),
§5.1.2 (per-representation fields and frozen values), §5.1.3 (fixed request
headers) and §5.2 (``cache_behavior`` modes).

Specification gaps (see VERIFY_LOG.md D-04 / D-06 / D-08): the §5.1.2 JSON
and the T002 output list were truncated in page extraction, so the schema
below is built only from the field tables and prose that *were* retrieved.
Where the spec gives no field name, this module documents the choice instead
of inventing a spec claim:

* Nested objects use the same ``snake_case`` naming as the top-level contract
  fields (``contract_id``, ``origin_url``, ``cache_behavior``).
* ``request_headers`` carries the three fixed common headers as
  ``accept_encoding`` / ``user_agent`` / ``accept_language``. ``Accept`` is
  per-representation (``representations.html.accept`` /
  ``representations.markdown.accept``) per §5.1.3 and is NOT a member of
  ``request_headers``.
* ``limits`` sub-fields are not enumerated in the retrieved spec text
  (§5.1 only says "request and body boundaries"; §17.4 fixes the body cap at
  1 MiB and requires a bounded request timeout). The schema therefore allows
  exactly ``max_body_bytes`` (1..1048576) and ``request_timeout_seconds``
  (> 0); both default when absent (see :mod:`accepttwin.contract`).
* ``metadata`` is a free-form object that does not participate in verdicts
  (§5.1); its keys are unrestricted.

This module uses only the standard library: there is no ``jsonschema``
dependency in the frozen stack (§16: stdlib only + pytest).
"""

from __future__ import annotations

CONTRACT_SCHEMA_VERSION = "accepttwin.contract/v1"

CONTRACT_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://accepttwin.local/schemas/accepttwin.contract.v1.schema.json",
    "title": "AcceptTwin contract",
    "type": "object",
    "required": [
        "schema",
        "contract_id",
        "name",
        "url",
        "origin_url",
        "representations",
        "request_headers",
        "cache_behavior",
        "limits",
        "metadata",
    ],
    "additionalProperties": False,
    "properties": {
        "schema": {"const": CONTRACT_SCHEMA_VERSION},
        "contract_id": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "url": {"type": "string", "minLength": 1},
        "origin_url": {"type": "string", "minLength": 1},
        "representations": {
            "type": "object",
            "required": ["html", "markdown"],
            "additionalProperties": False,
            "properties": {
                "html": {"$ref": "#/$defs/representation"},
                "markdown": {"$ref": "#/$defs/representation"},
            },
        },
        "request_headers": {
            "type": "object",
            "required": ["accept_encoding", "user_agent", "accept_language"],
            "additionalProperties": False,
            "properties": {
                "accept_encoding": {"const": "identity"},
                "user_agent": {"const": "AcceptTwin/1.0.0"},
                "accept_language": {"const": "en"},
            },
        },
        "cache_behavior": {
            "type": "object",
            "required": ["mode"],
            "additionalProperties": False,
            "properties": {
                "mode": {"enum": ["variant_by_accept", "no_store"]},
                "vary_accept": {"enum": ["required", "advisory", "not_required"]},
                "max_age_seconds": {"type": ["integer", "null"], "minimum": 0},
            },
        },
        "limits": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "max_body_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 1048576,
                },
                "request_timeout_seconds": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                },
            },
        },
        "metadata": {"type": "object"},
    },
    "$defs": {
        "representation": {
            "type": "object",
            "required": [
                "accept",
                "expected_status",
                "expected_content_type",
                "sentinel",
            ],
            "additionalProperties": False,
            "properties": {
                "accept": {"type": "string", "minLength": 1},
                "expected_status": {"type": "integer"},
                "expected_content_type": {"type": "string", "minLength": 1},
                "sentinel": {"type": "string", "minLength": 1},
            },
        },
    },
}

# Frozen per-representation values from PROJECT_BOOK §5.1.2. These are
# enforced semantically in contract.py (not merely as schema consts) so the
# error messages can name the representation and the expected value.
FROZEN_REPRESENTATIONS: dict[str, dict[str, object]] = {
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


def _type_name(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def _matches_type(value: object, expected: str) -> bool:
    # JSON Schema: "integer" accepts ints but not bools; "number" accepts
    # ints and floats but not bools.
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return _type_name(value) == expected


def _resolve_ref(ref: str, root: dict) -> dict:
    # Only local refs of the form "#/$defs/<name>" (and "#/properties/...")
    # are used by CONTRACT_SCHEMA.
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref: {ref!r}")
    node: object = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"unresolvable $ref: {ref!r}")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError(f"$ref does not point at a schema object: {ref!r}")
    return node


def _validate(
    value: object, schema: dict, root: dict, path: str, errors: list[str]
) -> None:
    if "$ref" in schema:
        _validate(value, _resolve_ref(schema["$ref"], root), root, path, errors)
        return

    schema_type = schema.get("type")
    if schema_type is not None:
        expected = (
            schema_type if isinstance(schema_type, list) else [schema_type]
        )
        if not any(_matches_type(value, t) for t in expected):
            errors.append(
                f"{path or '$'}: expected type "
                f"{'/'.join(expected)}, got {_type_name(value)}"
            )
            return

    if "const" in schema and value != schema["const"]:
        errors.append(
            f"{path or '$'}: expected {schema['const']!r}, got {value!r}"
        )
    if "enum" in schema and value not in schema["enum"]:
        errors.append(
            f"{path or '$'}: expected one of {schema['enum']!r}, got {value!r}"
        )
    if isinstance(value, str):
        if (
            "minLength" in schema
            and len(value) < schema["minLength"]
        ):
            errors.append(
                f"{path or '$'}: string shorter than "
                f"minLength {schema['minLength']}"
            )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(
                f"{path or '$'}: value {value!r} below minimum "
                f"{schema['minimum']!r}"
            )
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(
                f"{path or '$'}: value {value!r} above maximum "
                f"{schema['maximum']!r}"
            )
        if (
            "exclusiveMinimum" in schema
            and value <= schema["exclusiveMinimum"]
        ):
            errors.append(
                f"{path or '$'}: value {value!r} not above exclusiveMinimum "
                f"{schema['exclusiveMinimum']!r}"
            )
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path or '$'}: missing required field {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(
                        f"{path or '$'}: unsupported field {key!r} "
                        "(unknown fields are never silently ignored)"
                    )
        for key, subschema in properties.items():
            if key in value:
                child_path = f"{path}.{key}" if path else key
                _validate(value[key], subschema, root, child_path, errors)


def validate_with_schema(
    data: object, schema: dict | None = None
) -> list[str]:
    """Validate *data* against the contract schema.

    Returns the list of error strings (empty means valid). This is a
    structural check only; semantic rules (loopback URLs, distinct
    Sentinels, frozen Accept values, mode combinations) are enforced by
    :mod:`accepttwin.contract` on top of it.
    """
    schema = CONTRACT_SCHEMA if schema is None else schema
    errors: list[str] = []
    _validate(data, schema, schema, "", errors)
    return errors
```

## src/accepttwin/url_guard.py

- SHA-256：`88a3e7597c79343ae955059c262cc7fc15345960da6c6d1782aed5e71839ad2c`
- 字节数：5432

```
"""Loopback URL guard (PROJECT_BOOK §5.1.1, IMPLEMENTATION_PLAN §5.2).

Only ``http`` URLs whose *resolved* addresses are all loopback are accepted.
The check is fail-closed: anything that cannot be proven loopback — an
unresolvable name, a name resolving to a mix of loopback and non-loopback
addresses, a missing host, userinfo, a non-HTTP scheme, an out-of-range
port — is rejected.

Rules enforced by :func:`validate_loopback_url`:

* scheme must be ``http`` (case-insensitive, per RFC 9110);
* no URL userinfo (no ``user@`` / ``user:pass@`` in the authority);
* a host must be present; IPv6 zone identifiers (``%...``) are rejected;
* every address returned by DNS resolution of the host must satisfy
  :attr:`ipaddress.IPv4Address.is_loopback` /
  :attr:`ipaddress.IPv6Address.is_loopback`. Literal IP hosts are checked
  directly; names such as ``localhost`` are resolved and *all* results
  must be loopback;
* the port, when present, must be an integer in 1..65535. ``urllib.parse``
  raises :class:`ValueError` for out-of-range or non-numeric ports; that is
  surfaced as an invalid-port error. A missing port defaults to 80 (the
  HTTP default);
* no fragment (a fragment is never sent to a server and has no meaning in
  a contract URL);
* no whitespace or control characters anywhere in the URL.

Deliberately NOT done here: following redirects, reading proxy environment
variables, or fetching anything. The future HTTP client (T005) must pass
``proxies`` disabled / never consult ``HTTP_PROXY`` / ``HTTPS_PROXY`` —
this module only validates the URL string itself, and it never reads the
environment.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_HTTP_PORT = 80


class URLGuardError(ValueError):
    """Raised when a URL fails the loopback guard."""


@dataclass(frozen=True)
class ValidatedURL:
    """A URL that has passed the loopback guard."""

    url: str
    scheme: str
    host: str
    port: int
    addresses: tuple[str, ...]
    path: str
    query: str

    @property
    def origin(self) -> str:
        """``scheme://host:port`` (host bracketed for IPv6)."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{self.scheme}://{host}:{self.port}"


def _resolve_host(host: str, port: int) -> list[str]:
    """Resolve *host* and return every address as a string.

    Raises :class:`URLGuardError` if resolution fails or yields no address.
    """
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OverflowError) as exc:
        raise URLGuardError(f"cannot resolve host {host!r}: {exc}") from exc
    addresses: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr:
            addresses.append(str(sockaddr[0]))
    if not addresses:
        raise URLGuardError(f"host {host!r} resolved to no addresses")
    # De-duplicate while preserving order.
    return list(dict.fromkeys(addresses))


def validate_loopback_url(url: str) -> ValidatedURL:
    """Validate *url* and return its :class:`ValidatedURL`.

    Raises :class:`URLGuardError` with a specific reason on any failure.
    The input is never silently corrected.
    """
    if not isinstance(url, str) or not url:
        raise URLGuardError("URL must be a non-empty string")
    if any(ord(ch) <= 0x20 or ord(ch) == 0x7F for ch in url):
        raise URLGuardError(f"URL {url!r} contains whitespace/control characters")

    parsed = urlparse(url)
    if parsed.scheme.lower() != "http":
        raise URLGuardError(
            f"URL {url!r} uses scheme {parsed.scheme!r}; only 'http' is allowed"
        )
    if parsed.fragment:
        raise URLGuardError(f"URL {url!r} must not contain a fragment")
    if parsed.username is not None or parsed.password is not None:
        raise URLGuardError(f"URL {url!r} must not contain userinfo")
    if "@" in (parsed.netloc or ""):
        raise URLGuardError(f"URL {url!r} must not contain userinfo")

    host = parsed.hostname
    if not host:
        raise URLGuardError(f"URL {url!r} has no host")
    if "%" in host:
        raise URLGuardError(
            f"URL {url!r} must not contain an IPv6 zone identifier"
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise URLGuardError(f"URL {url!r} has an invalid port: {exc}") from exc
    if port is None:
        port = DEFAULT_HTTP_PORT
    if not 1 <= port <= 65535:
        raise URLGuardError(
            f"URL {url!r} has an invalid port {port}; must be 1..65535"
        )

    addresses = _resolve_host(host, port)
    non_loopback: list[str] = []
    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError as exc:
            raise URLGuardError(
                f"host {host!r} resolved to unparsable address {addr!r}"
            ) from exc
        if not ip.is_loopback:
            non_loopback.append(addr)
    if non_loopback:
        raise URLGuardError(
            f"host {host!r} resolves to non-loopback address(es): "
            + ", ".join(non_loopback)
        )

    return ValidatedURL(
        url=url,
        scheme="http",
        host=host,
        port=port,
        addresses=tuple(addresses),
        path=parsed.path or "",
        query=parsed.query or "",
    )
```
