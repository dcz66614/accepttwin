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
