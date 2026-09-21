"""Minimal local HTTP server for development; production auth/queue come later."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .api import audit_payload


class APIHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "ss-seo"})
        else:
            self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/audit":
            self._send_json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            url = payload["url"]
            self._send_json(200, audit_payload(url))
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": "invalid_request", "detail": str(exc)})

    def log_message(self, format: str, *args) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    HTTPServer((host, port), APIHandler).serve_forever()

