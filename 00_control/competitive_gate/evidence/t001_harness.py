#!/usr/bin/env python3
"""THROWAWAY harness for P032-T001 competitive-gate probing ONLY.

NOT AcceptTwin product code. Used solely to give every competitor the same
synthetic origin + controlled cache to test against, so EQ01-EQ08 can be
judged on real behaviour rather than README claims.

Origin  (port 18766): GET /doc negotiates on Accept.
  - Accept containing text/markdown -> Markdown body, sentinel
    AT_MARKDOWN_SENTINEL_001, Content-Type text/markdown; charset=utf-8
  - otherwise -> HTML body, sentinel AT_HTML_SENTINEL_001,
    Content-Type text/html; charset=utf-8
  - always Vary: Accept. GET /__origin_stats__ -> JSON {count, events}.
Proxy   (port 18765): GET /doc forwards to origin, caches per mode.
  - mode=respect_vary (default): cache key = URI + Accept value
  - mode=force_uri_only: cache key = URI only (deliberately bleeds)
  - mode=disabled (no_store): never stores, always BYPASS
  - response headers: X-Test-Cache-Status MISS|HIT|BYPASS,
    X-Test-Cache-Key sha256, X-Test-Entry-Id
  - GET /__control__/reset -> clears cache, returns {"entry_count": 0}
  - GET /__control__/stats -> {"entry_count": N, "entries": [...]}
  - GET /__control__/mode?mode=<m> -> switches mode
Control endpoints never touch the cache and are not counted as origin hits.
"""
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

HTML_BODY = "<html><body><h1>Doc</h1><p>AT_HTML_SENTINEL_001</p></body></html>"
MD_BODY = "# Doc\n\nAT_MARKDOWN_SENTINEL_001\n"
ORIGIN_PORT = 18766
PROXY_PORT = 18765

origin_count = 0
origin_events = []
origin_lock = threading.Lock()
cache = {}          # key -> {"entry_id","body","content_type","accept"}
cache_lock = threading.Lock()
proxy_mode = "respect_vary"


def origin_stats():
    with origin_lock:
        return {"count": origin_count,
                "events": list(origin_events)}


class OriginHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        global origin_count
        if self.path == "/__origin_stats__":
            body = json.dumps(origin_stats()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path != "/doc":
            self.send_response(404)
            self.end_headers()
            return
        accept = self.headers.get("Accept", "")
        is_md = "text/markdown" in accept
        body = (MD_BODY if is_md else HTML_BODY).encode()
        ctype = ("text/markdown; charset=utf-8" if is_md
                 else "text/html; charset=utf-8")
        with origin_lock:
            origin_count += 1
            origin_events.append({"n": origin_count, "accept": accept,
                                  "path": self.path, "t": time.time()})
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Vary", "Accept")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def cache_key(path, accept, mode):
    if mode == "force_uri_only":
        raw = path.encode()
    else:
        raw = (path + "|" + accept).encode()
    return hashlib.sha256(raw).hexdigest()


class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        global proxy_mode
        if self.path.startswith("/__control__/"):
            if self.path == "/__control__/reset":
                with cache_lock:
                    cache.clear()
                body = json.dumps({"entry_count": 0,
                                   "reset_confirmed": True}).encode()
            elif self.path == "/__control__/stats":
                with cache_lock:
                    body = json.dumps(
                        {"entry_count": len(cache),
                         "entries": [{"key": k, "entry_id": v["entry_id"],
                                      "accept": v["accept"]}
                                     for k, v in cache.items()]}).encode()
            elif self.path.startswith("/__control__/mode"):
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(self.path).query)
                m = q.get("mode", [proxy_mode])[0]
                if m not in ("respect_vary", "force_uri_only", "disabled"):
                    self.send_response(400)
                    self.end_headers()
                    return
                proxy_mode = m
                with cache_lock:
                    cache.clear()
                body = json.dumps({"mode": proxy_mode,
                                   "entry_count": 0}).encode()
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path != "/doc":
            self.send_response(404)
            self.end_headers()
            return
        accept = self.headers.get("Accept", "")
        mode = proxy_mode
        key = cache_key(self.path, accept, mode)
        if mode != "disabled":
            with cache_lock:
                ent = cache.get(key)
            if ent is not None:
                body = ent["body"]
                self.send_response(200)
                self.send_header("Content-Type", ent["content_type"])
                self.send_header("Vary", "Accept")
                self.send_header("X-Test-Cache-Status", "HIT")
                self.send_header("X-Test-Cache-Key", key)
                self.send_header("X-Test-Entry-Id", ent["entry_id"])
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        req = Request(f"http://127.0.0.1:{ORIGIN_PORT}/doc",
                      headers={"Accept": accept})
        with urlopen(req, timeout=10) as r:
            body = r.read()
            ctype = r.headers.get("Content-Type", "")
        entry_id = "e-" + key[:12]
        status = "BYPASS" if mode == "disabled" else "MISS"
        if mode != "disabled":
            with cache_lock:
                cache[key] = {"entry_id": entry_id, "body": body,
                              "content_type": ctype, "accept": accept}
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Vary", "Accept")
        self.send_header("X-Test-Cache-Status", status)
        self.send_header("X-Test-Cache-Key", key)
        self.send_header("X-Test-Entry-Id", entry_id)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    o = ThreadingHTTPServer(("127.0.0.1", ORIGIN_PORT), OriginHandler)
    p = ThreadingHTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    threading.Thread(target=o.serve_forever, daemon=True).start()
    threading.Thread(target=p.serve_forever, daemon=True).start()
    print(f"origin on {ORIGIN_PORT}, proxy on {PROXY_PORT}, mode={proxy_mode}",
          flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
