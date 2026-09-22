"""Minimal local HTTP server for development; production auth/queue come later."""

from __future__ import annotations

import json
import os
import threading
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import gsc
from .api import audit_payload, payload_from_output
from .crawl import Crawler
from .discovery import robots_url, sitemap_candidates, sitemap_links
from .fetcher import PoliteFetcher
from .pipeline import run_audit
from .url_policy import CrawlScope, normalize_url


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
        max_urls = JOBS[job_id].get("max_urls", 100)
        output = run_audit(url, crawler=Crawler(max_urls=max_urls, progress=progress))
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

    # -- Search Console helpers ------------------------------------------

    def _gsc_html(self, status: int, title: str, message: str, extra_html: str = "") -> None:
        body = (
            "<!doctype html><html lang=\"tr\"><head><meta charset=\"utf-8\">"
            f"<title>{title}</title>"
            "<style>body{font-family:system-ui,sans-serif;background:#080d19;color:#e8eefc;"
            "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}"
            ".box{background:#111a2c;border:1px solid #22304a;border-radius:14px;padding:32px 40px;"
            "max-width:480px;text-align:center}h1{font-size:20px;margin:0 0 10px}"
            "p{color:#8d9bb8;line-height:1.5;margin:8px 0}a{color:#7185ff}</style></head>"
            f"<body><div class=\"box\"><h1>{title}</h1><p>{message}</p>{extra_html}</div></body></html>"
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _handle_gsc_callback(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        error = (params.get("error") or [None])[0]
        code = (params.get("code") or [None])[0]
        state = (params.get("state") or [None])[0]
        if error:
            self._gsc_html(400, "Yetkilendirme iptal edildi", f"Google hatası: {error}. Paneldeki Search Console sekmesinden tekrar deneyin.")
            return
        if not code or not state:
            self._gsc_html(400, "Eksik parametre", "Google'dan gelen yanıt eksik: code veya state bulunamadı.")
            return
        if not gsc.consume_state(state):
            self._gsc_html(400, "Oturum doğrulanamadı", "state bilgisi geçersiz ya da süresi dolmuş. Bağlantı ekranından işleme yeniden başlayın.")
            return
        try:
            tokens = gsc.exchange_code(code)
            store = gsc.TokenStore()
            if not store.usable:
                self._gsc_html(503, "Sunucu yapılandırması eksik", "TOKEN_ENCRYPTION_KEY tanımlı değil; token dosyası güvenle saklanamaz. Yöneticiye bildirin.")
                return
            store.save_tokens(tokens["access_token"], tokens.get("refresh_token"), int(tokens.get("expires_in", 3600)), tokens.get("scope", gsc.GSC_SCOPE))
        except gsc.GscError as exc:
            self._gsc_html(502, "Bağlantı tamamlanamadı", f"Ayrıntı: {exc}")
            return
        self._gsc_html(200, "Search Console bağlandı ✅", "Google Search Console hesabınız bağlandı. Sekmeyi kapatıp paneldeki Search Console ekranına dönebilirsiniz.", "<p><a href=\"/\">Panele dön</a></p>")

    def _handle_gsc_status(self) -> None:
        try:
            store = gsc.TokenStore()
            if not store.usable:
                self._send_json(200, {"connected": False, "configured": bool(gsc.oauth_config()), "encryption_ready": False, "error": "TOKEN_ENCRYPTION_KEY tanımlı değil"})
                return
            record = store.load()
            if record is None:
                self._send_json(200, {"connected": False, "configured": bool(gsc.oauth_config()), "encryption_ready": True})
                return
            self._send_json(200, {
                "connected": True,
                "configured": True,
                "encryption_ready": True,
                "scope": record.get("scope"),
                "connected_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "has_refresh_token": bool(record.get("refresh_token")),
            })
        except gsc.GscError as exc:
            self._send_json(200, {"connected": False, "configured": bool(gsc.oauth_config()), "encryption_ready": store.usable, "error": str(exc)})

    def _gsc_access_token_or_respond(self) -> str | None:
        try:
            store = gsc.TokenStore()
            token = store.valid_access_token()
        except gsc.GscError as exc:
            self._send_json(exc.status, {"error": "search_console_error", "detail": str(exc)})
            return None
        if token is None:
            self._send_json(401, {"error": "not_connected", "detail": "Search Console bağlı değil. Google ile bağlanın."})
            return None
        return token

    def _handle_gsc_sites(self) -> None:
        token = self._gsc_access_token_or_respond()
        if token is None:
            return
        try:
            sites = gsc.list_sites(token)
            self._send_json(200, {"connected": True, "sites": sites})
        except gsc.GscError as exc:
            self._send_json(exc.status, {"error": "search_console_error", "detail": str(exc)})

    def _handle_gsc_performance(self) -> None:
        token = self._gsc_access_token_or_respond()
        if token is None:
            return
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        site = (params.get("site") or [""])[0]
        start = (params.get("start") or [""])[0]
        end = (params.get("end") or [""])[0]
        if not site or not start or not end:
            self._send_json(400, {"error": "invalid_request", "detail": "site, start ve end parametreleri gerekli (YYYY-MM-DD)."})
            return
        try:
            summary = gsc.performance_summary(token, site, start, end)
            self._send_json(200, summary)
        except gsc.GscError as exc:
            self._send_json(exc.status, {"error": "search_console_error", "detail": str(exc)})

    def do_GET(self) -> None:
        route = urllib.parse.urlparse(self.path).path
        if route == "/":
            web_root = Path(__file__).resolve().parents[2] / "web"
            body = (web_root / "index.html").read_bytes().replace(b"</head>", b'<link rel="stylesheet" href="/modern.css"></head>')
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif route == "/health":
            self._send_json(200, {"status": "ok", "service": "ss-seo"})
        elif route == "/modern.css":
            body = (Path(__file__).resolve().parents[2] / "web" / "modern.css").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif route == "/integrations/search-console/connect":
            config = gsc.oauth_config()
            if config is None:
                self._send_json(503, {"error": "search_console_not_configured", "detail": "Google OAuth henüz yapılandırılmadı. Coolify'a GOOGLE_CLIENT_ID ve GOOGLE_CLIENT_SECRET eklenmeli."})
                return
            state = gsc.issue_state()
            self.send_response(302)
            self.send_header("Location", gsc.build_auth_url(config, state))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        elif route == "/integrations/search-console/callback":
            self._handle_gsc_callback()
        elif route == "/integrations/search-console/status":
            self._handle_gsc_status()
        elif route == "/integrations/search-console/disconnect":
            self._send_json(405, {"error": "method_not_allowed", "hint": "POST ile bağlantıyı kaldırın"})
        elif route == "/integrations/search-console/sites":
            self._handle_gsc_sites()
        elif route == "/integrations/search-console/performance":
            self._handle_gsc_performance()
        elif route == "/discover":
            self._send_json(405, {"error": "method_not_allowed"})
        elif route.startswith("/audit/status/"):
            job_id = route.rsplit("/", 1)[-1]
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
        if self.path == "/integrations/search-console/disconnect":
            try:
                removed = gsc.TokenStore().clear()
            except OSError:
                removed = False
            self._send_json(200, {"connected": False, "removed": removed})
            return
        if self.path not in {"/audit", "/audit/start", "/discover"}:
            self._send_json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            url = payload["url"]
            if self.path == "/audit":
                self._send_json(200, audit_payload(url))
                return
            if self.path == "/discover":
                seed = normalize_url(url)
                scope = CrawlScope(hostname=seed.split("/", 3)[2].split(":", 1)[0])
                fetcher = PoliteFetcher()
                robots = fetcher.fetch(robots_url(seed), scope)
                candidates = sitemap_candidates(seed, robots.body)
                sitemap_urls = []
                for candidate in candidates:
                    result = fetcher.fetch(candidate, scope)
                    if result.status_code == 200 and result.body:
                        sitemap_urls.extend(sitemap_links(result.body))
                unique_urls = sorted(set(sitemap_urls))
                self._send_json(200, {"url": seed, "sitemap_count": len(unique_urls), "sitemap_urls": unique_urls[:5000]})
                return
            job_id = uuid.uuid4().hex
            max_urls = int(payload.get("max_urls", 100))
            if max_urls not in {100, 500, 1000, 5000}:
                raise ValueError("max_urls must be 100, 500, 1000, or 5000")
            with JOBS_LOCK:
                JOBS[job_id] = {
                    "job_id": job_id,
                    "status": "queued",
                    "progress": {"scheduled": 0, "completed": 0, "queued": 0, "errors": 0},
                    "max_urls": max_urls,
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
