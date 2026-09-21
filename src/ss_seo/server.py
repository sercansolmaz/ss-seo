"""Minimal local HTTP server for development; production auth/queue come later."""

from __future__ import annotations

import json
from pathlib import Path
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
        if self.path == "/":
            body = (Path(__file__).resolve().parents[2] / "web" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "ss-seo"})
        else:
            self._send_json(404, {"error": "not_found"})

    def do_HEAD(self) -> None:
        if self.path == "/health":
            payload = {"status": "ok", "service": "ss-seo"}
        elif self.path == "/":
            payload = None
        else:
            self.send_response(404)
            self.end_headers()
            return
        if payload is None:
            body_length = len((Path(__file__).resolve().parents[2] / "web" / "index.html").read_bytes())
            content_type = "text/html; charset=utf-8"
        else:
            body_length = len(json.dumps(payload).encode("utf-8"))
            content_type = "application/json"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(body_length))
        self.end_headers()

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


if __name__ == "__main__":
    serve(host="0.0.0.0", port=8787)
