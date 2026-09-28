#!/usr/bin/env python3
"""Minimal stand-in for http://supervisor used by scripts/addon/smoke-test.sh.

Answers the handful of Supervisor endpoints bashio touches at boot (/info,
/addons/self/info, /addons/self/options/config) and records the discovery message the
app sends. Stdlib only.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

HOSTNAME = os.environ.get("MOCK_APP_HOSTNAME", "local-mcp-grocy-api")
HA_VERSION = os.environ.get("MOCK_HA_VERSION", "2026.10.0")
RECORD = os.environ.get("MOCK_RECORD_FILE", "/tmp/discovery.json")
# bashio::config reads the options through GET /addons/self/options/config, not /data/options.json
OPTIONS_FILE = os.environ.get("MOCK_OPTIONS_FILE", "/data/options.json")
INFO = {
    "name": "MCP Grocy API",
    "slug": "local_mcp_grocy_api",
    "hostname": HOSTNAME,
    "version": "ci",
    "version_latest": "ci",
    "arch": "amd64",
    "supervisor": "ci",
    "homeassistant": HA_VERSION,
    "operating_system": "ci",
    "channel": "stable",
    "logging": "info",
    "ingress_port": 0,
    "ip_address": "172.30.33.9",
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_DELETE(self):  # noqa: N802
        # bashio::discovery.delete <uuid>
        self._send(200, {"result": "ok", "data": {}})

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") == "/discovery":
            self._send(200, {"result": "ok", "data": {"discovery": []}})
            return
        if self.path.rstrip("/").endswith("/options/config"):
            try:
                with open(OPTIONS_FILE, encoding="utf-8") as fh:
                    options = json.load(fh)
            except OSError:
                options = {}
            self._send(200, {"result": "ok", "data": options})
            return
        # /info, /addons/self/info, /supervisor/info, /core/info ... all get the same shape
        self._send(200, {"result": "ok", "data": INFO})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if self.path.rstrip("/") == "/discovery":
            msg = json.loads(raw or b"{}")
            with open(RECORD, "w", encoding="utf-8") as fh:
                json.dump(msg, fh)
            print(f"[mock-supervisor] discovery: {msg}", file=sys.stderr, flush=True)
            self._send(200, {"result": "ok", "data": {"uuid": "00000000000000000000000000000001"}})
            return
        self._send(200, {"result": "ok", "data": {}})

    def log_message(self, fmt, *args):
        print("[mock-supervisor]", fmt % args, file=sys.stderr, flush=True)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 80), Handler).serve_forever()
