#!/usr/bin/env python3
"""Standalone HTTP server for the Aether sandbox guard - zero dependencies.

Runs with *any* Python 3.8+ (no pip install, no FastAPI). Useful when the
project you want to add a sandbox to is not Python at all: start this next to
your app and call it over HTTP.

    python3 standalone_server.py                       # http://127.0.0.1:8123
    python3 standalone_server.py --port 9000 --token s3cret
    python3 standalone_server.py --host 0.0.0.0        # expose on the LAN

Endpoints
    GET  /          - tiny built-in playground (HTML form)
    GET  /info      - guard description, limits, allowed modules
    GET  /health    - {"status": "ok"}
    POST /run       - {"code": "...", "timeout": 5} -> run_python() result

Auth (optional): pass --token, then send header ``X-Sandbox-Token: <token>``
(or ``Authorization: Bearer <token>``).
"""
from __future__ import annotations

import argparse
import hmac
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import code_sandbox

MAX_BODY_BYTES = 64 * 1024

PLAYGROUND_HTML = """<!doctype html>
<html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aether Sandbox</title>
<style>
 body{font-family:ui-sans-serif,system-ui,sans-serif;margin:0;background:#0b1020;color:#e8eefc}
 main{max-width:820px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} p{color:#93a4c8;margin:0 0 16px;font-size:13px}
 textarea{width:100%;height:190px;padding:12px;border-radius:12px;border:1px solid #26304a;
          background:#111731;color:#e8eefc;font-family:ui-monospace,monospace;font-size:13px}
 button{margin-top:10px;padding:9px 18px;border-radius:999px;border:1px solid #7dd3fc;
        background:transparent;color:#7dd3fc;font-size:14px;cursor:pointer}
 pre{margin-top:14px;padding:12px;border-radius:12px;background:#111731;border:1px solid #26304a;
     white-space:pre-wrap;min-height:22px;font-size:13px}
 .err{color:#fca5a5} code{color:#7dd3fc}
</style></head><body><main>
<h1>Aether Sandbox</h1>
<p>AST allow-list + isolated subprocess · allowed: <code id="mods">…</code></p>
<textarea id="code">import math, statistics

data = [2, 4, 4, 6, 6, 8]
print("mean:", statistics.mean(data))
print("sqrt:", round(math.sqrt(sum(data)), 3))</textarea>
<button onclick="run()">Run</button>
<pre id="out">พร้อมทำงาน — กด Run</pre>
<script>
async function run(){
  const out = document.getElementById('out');
  out.className = ''; out.textContent = 'กำลังรัน...';
  try {
    const r = await fetch('run', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({code: document.getElementById('code').value})});
    const j = await r.json();
    out.className = j.ok ? '' : 'err';
    out.textContent = j.ok ? (j.stdout || '(ไม่มี output)')
      : 'ถูกปฏิเสธ/ล้มเหลว: ' + (j.error || j.stderr || 'unknown');
    if (j.ok && j.stderr) out.textContent += '\\n[stderr] ' + j.stderr;
  } catch (e) { out.className = 'err'; out.textContent = 'เรียกเซิร์ฟเวอร์ไม่ได้: ' + e; }
}
fetch('info').then(r => r.json())
  .then(j => document.getElementById('mods').textContent = j.allowed_modules.join(' · '));
</script></main></body></html>
"""


class SandboxHandler(BaseHTTPRequestHandler):
    server_version = "AetherSandbox/1.0"
    protocol_version = "HTTP/1.1"

    # populated by main()
    token: str | None = None
    allow_origin: str = "*"

    # ------------------------------------------------------------------ utils
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self.allow_origin)
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Sandbox-Token, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _authorized(self) -> bool:
        if not self.token:
            return True
        supplied = self.headers.get("X-Sandbox-Token", "")
        if not supplied:
            auth = self.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                supplied = auth[7:].strip()
        return hmac.compare_digest(supplied, self.token)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - stdlib signature
        sys.stderr.write("%s - %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # --------------------------------------------------------------- handlers
    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib naming
        self._send(204, b"", "text/plain")

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path == "/":
            self._send(200, PLAYGROUND_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/info":
            description, limits = code_sandbox.describe()
            self._json(200, {
                "guard": description,
                "limits": limits,
                "allowed_modules": code_sandbox.allowed_modules(),
                "blocked": code_sandbox.blocked_features(),
                "auth_required": bool(self.token),
            })
        elif path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?")[0].rstrip("/") != "/run":
            self._json(404, {"error": "not found"})
            return
        if not self._authorized():
            self._json(401, {"error": "missing or invalid token"})
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._json(400, {"error": "empty body"})
            return
        if length > MAX_BODY_BYTES:
            self._json(413, {"error": f"body larger than {MAX_BODY_BYTES} bytes"})
            return

        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            self._json(400, {"error": f"invalid JSON: {exc}"})
            return
        if not isinstance(payload, dict) or not str(payload.get("code") or "").strip():
            self._json(400, {"error": "field 'code' is required"})
            return

        timeout = payload.get("timeout", code_sandbox.DEFAULT_TIMEOUT)
        try:
            timeout = max(1, min(int(timeout), 10))
        except (TypeError, ValueError):
            timeout = code_sandbox.DEFAULT_TIMEOUT

        self._json(200, code_sandbox.run_python(str(payload["code"]), timeout=timeout))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone Aether sandbox server (stdlib only)")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8123, help="port (default 8123)")
    parser.add_argument("--token", default=None, help="require this token on POST /run")
    parser.add_argument("--allow-origin", default="*", help="CORS allow-origin header")
    args = parser.parse_args(argv)

    SandboxHandler.token = args.token
    SandboxHandler.allow_origin = args.allow_origin

    description, limits = code_sandbox.describe()
    httpd = ThreadingHTTPServer((args.host, args.port), SandboxHandler)
    print(f"Aether sandbox on http://{args.host}:{args.port}  ({limits})")
    print(f"guard: {description}")
    if args.token:
        print("auth: required (header X-Sandbox-Token)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
