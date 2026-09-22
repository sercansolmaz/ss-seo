"""Minimal local HTTP server for development; production auth/queue come later."""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .api import audit_payload, payload_from_output
from .crawl import Crawler
from .pipeline import run_audit


JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def _update_job(job_id: str, **changes) -> None:
    with JOBS_LOCK:
        JOBS[job_id].update(changes)


def _run_job(job_id: str, url: str) -> None:
    def progress(details: dict[str, int]) -> None:
        _update_job(job_id, progress=details)

    _update_job(job_id, status="running")
    try:
        output = run_audit(url, crawler=Crawler(progress=progress))
        _update_job(job_id, status="completed", result=payload_from_output(url, output))
    except Exception as exc:  # keep the worker alive and expose a useful UI error
        _update_job(job_id, status="failed", error=str(exc))


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
        elif self.path.startswith("/audit/status/"):
            job_id = self.path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if job is None:
                    self._send_json(404, {"error": "job_not_found"})
                else:
                    self._send_json(200, {key: value for key, value in job.items() if key != "result" or job["status"] == "completed"})
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
        if self.path not in {"/audit", "/audit/start"}:
            self._send_json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            url = payload["url"]
            if self.path == "/audit":
                self._send_json(200, audit_payload(url))
                return
            job_id = uuid.uuid4().hex
            with JOBS_LOCK:
                JOBS[job_id] = {
                    "job_id": job_id,
                    "status": "queued",
                    "progress": {"scheduled": 0, "completed": 0, "queued": 0, "errors": 0},
                }
            threading.Thread(target=_run_job, args=(job_id, url), daemon=True).start()
            self._send_json(202, {"job_id": job_id, "status": "queued"})
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": "invalid_request", "detail": str(exc)})

    def log_message(self, format: str, *args) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    ThreadingHTTPServer((host, port), APIHandler).serve_forever()


if __name__ == "__main__":
    serve(host="0.0.0.0", port=8787)
