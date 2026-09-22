"""Google Search Console integration: OAuth 2.0 flow and read-only reporting API.

Standard-library only. Token values are never logged and never returned by the
API layer; they are persisted encrypted at rest under DATA_DIR (TOKEN_ENCRYPTION_KEY).
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SITES_ENDPOINT = "https://searchconsole.googleapis.com/webmasters/v3/sites"
QUERY_ENDPOINT = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"

STATE_TTL_SECONDS = 600
ACCESS_TOKEN_MARGIN_SECONDS = 60
_PBKDF2_ITERATIONS = 200_000
_MAX_DETAIL_CHARS = 200


class GscError(RuntimeError):
    """OAuth / Search Console failure safe to surface in API responses."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message[:_MAX_DETAIL_CHARS])
        self.status = status


# ---------------------------------------------------------------------------
# Token encryption at rest (PBKDF2 + HMAC-SHA256 keystream, encrypt-then-MAC)
# ---------------------------------------------------------------------------

def _derive_keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
    material = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, _PBKDF2_ITERATIONS, dklen=64)
    return material[:32], material[32:]


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    blocks = [
        hmac.new(enc_key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        for counter in range((length + 31) // 32)
    ]
    return b"".join(blocks)[:length]


def encrypt_text(plaintext: str, passphrase: str) -> str:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    enc_key, mac_key = _derive_keys(passphrase, salt)
    data = plaintext.encode("utf-8")
    ciphertext = bytes(a ^ b for a, b in zip(data, _keystream(enc_key, nonce, len(data))))
    tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    return "v1:" + ":".join(base64.b64encode(part).decode("ascii") for part in (salt, nonce, ciphertext, tag))


def decrypt_text(blob: str, passphrase: str) -> str:
    try:
        version, salt_b64, nonce_b64, ciphertext_b64, tag_b64 = blob.split(":")
        if version != "v1":
            raise ValueError("unsupported version")
        salt = base64.b64decode(salt_b64)
        nonce = base64.b64decode(nonce_b64)
        ciphertext = base64.b64decode(ciphertext_b64)
        tag = base64.b64decode(tag_b64)
    except (ValueError, TypeError) as exc:
        raise GscError("stored token format is unreadable", 500) from None
    enc_key, mac_key = _derive_keys(passphrase, salt)
    expected = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise GscError("token integrity check failed (TOKEN_ENCRYPTION_KEY changed? reconnect Google)", 500)
    stream = _keystream(enc_key, nonce, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, stream)).decode("utf-8")


# ---------------------------------------------------------------------------
# OAuth state store (single-use, expiring)
# ---------------------------------------------------------------------------

_STATE_LOCK = threading.Lock()
_PENDING_STATES: dict[str, float] = {}


def issue_state() -> str:
    now = time.time()
    with _STATE_LOCK:
        for state, created in list(_PENDING_STATES.items()):
            if now - created > STATE_TTL_SECONDS:
                del _PENDING_STATES[state]
        state = secrets.token_urlsafe(24)
        _PENDING_STATES[state] = now
    return state


def consume_state(state: str) -> bool:
    now = time.time()
    with _STATE_LOCK:
        created = _PENDING_STATES.pop(state, None)
    return created is not None and now - created <= STATE_TTL_SECONDS


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_json(url: str, *, method: str = "GET", headers: dict | None = None, form: dict | None = None, body: dict | None = None) -> dict:
    data = None
    request_headers = {"User-Agent": "ss-seo/0.1", "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise GscError(f"google_rejected_{exc.code}: {_error_summary(exc)}", 502) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GscError(f"google_unreachable: {exc}", 502) from None


def _error_summary(exc: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:
        return "unknown_error"
    message = payload.get("error_description") or payload.get("error")
    if isinstance(message, dict):
        message = message.get("message") or "unknown_error"
    return str(message)[:120]


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------

def oauth_config() -> dict | None:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "https://seo.stuqio.com/integrations/search-console/callback"),
    }


def build_auth_url(config: dict, state: str) -> str:
    query = urllib.parse.urlencode({
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": GSC_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    return f"{AUTH_ENDPOINT}?{query}"


def exchange_code(code: str) -> dict:
    config = oauth_config()
    if config is None:
        raise GscError("oauth_not_configured: GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET missing", 503)
    payload = _http_json(TOKEN_ENDPOINT, method="POST", form={
        "code": code,
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "redirect_uri": config["redirect_uri"],
        "grant_type": "authorization_code",
    })
    if "access_token" not in payload:
        raise GscError("token_exchange_failed: no access_token in Google response")
    return payload


def refresh_access_token(refresh_token: str) -> dict:
    config = oauth_config()
    if config is None:
        raise GscError("oauth_not_configured", 503)
    payload = _http_json(TOKEN_ENDPOINT, method="POST", form={
        "refresh_token": refresh_token,
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "grant_type": "refresh_token",
    })
    if "access_token" not in payload:
        raise GscError("token_refresh_failed: no access_token in Google response")
    return payload


# ---------------------------------------------------------------------------
# Encrypted token store (file-based, survives restarts when DATA_DIR is a volume)
# ---------------------------------------------------------------------------

def default_token_path() -> Path:
    override = os.getenv("GSC_TOKEN_FILE")
    if override:
        return Path(override)
    base = Path(os.getenv("DATA_DIR") or (Path.cwd() / "data"))
    return base / "gsc_tokens.json"


class TokenStore:
    def __init__(self, path: Path | None = None, passphrase: str | None = None):
        self.path = path or default_token_path()
        self.passphrase = passphrase if passphrase is not None else os.getenv("TOKEN_ENCRYPTION_KEY", "")

    @property
    def usable(self) -> bool:
        return bool(self.passphrase)

    def _read_raw(self) -> dict | None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except (FileNotFoundError, NotADirectoryError):
            return None
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return record if isinstance(record, dict) else None

    def save_tokens(self, access_token: str, refresh_token: str | None, expires_in: int, scope: str) -> None:
        if not self.usable:
            raise GscError("token_encryption_missing: TOKEN_ENCRYPTION_KEY is not set", 503)
        existing = self._read_raw() or {}
        record = {
            "version": 1,
            "created_at": existing.get("created_at") or dt.datetime.now(dt.timezone.utc).isoformat(),
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "access_token": encrypt_text(access_token, self.passphrase),
            "refresh_token": encrypt_text(refresh_token, self.passphrase) if refresh_token else None,
            "expires_at": time.time() + int(expires_in or 3600),
            "scope": scope or GSC_SCOPE,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(record), encoding="utf-8")
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, self.path)

    def load(self) -> dict | None:
        """Returns decrypted record or None when no connection exists."""
        record = self._read_raw()
        if record is None:
            return None
        if not self.usable:
            raise GscError("token_encryption_missing: TOKEN_ENCRYPTION_KEY is not set", 503)
        try:
            loaded = {
                "access_token": decrypt_text(record["access_token"], self.passphrase),
                "expires_at": float(record.get("expires_at", 0)),
                "scope": record.get("scope", GSC_SCOPE),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
            }
            encrypted_refresh = record.get("refresh_token")
            loaded["refresh_token"] = decrypt_text(encrypted_refresh, self.passphrase) if encrypted_refresh else None
        except KeyError as exc:
            raise GscError(f"stored token record is incomplete: {exc}", 500) from None
        return loaded

    def clear(self) -> bool:
        existed = self.path.exists()
        try:
            self.path.unlink()
        except FileNotFoundError:
            existed = False
        return existed

    def valid_access_token(self) -> str | None:
        """Returns a live access token, refreshing it when needed.

        Raises GscError(401, "reconnect_required") when the refresh token is
        rejected; the stored connection is cleared in that case.
        """
        record = self.load()
        if record is None:
            return None
        if record["expires_at"] > time.time() + ACCESS_TOKEN_MARGIN_SECONDS:
            return record["access_token"]
        refresh_token = record.get("refresh_token")
        if not refresh_token:
            return None
        try:
            refreshed = refresh_access_token(refresh_token)
        except GscError as exc:
            if "invalid_grant" in str(exc):
                self.clear()
                raise GscError("reconnect_required: Google rejected the refresh token", 401) from None
            raise
        self.save_tokens(
            access_token=refreshed["access_token"],
            refresh_token=refreshed.get("refresh_token") or refresh_token,
            expires_in=int(refreshed.get("expires_in", 3600)),
            scope=refreshed.get("scope", record.get("scope", GSC_SCOPE)),
        )
        return refreshed["access_token"]


# ---------------------------------------------------------------------------
# Search Console API
# ---------------------------------------------------------------------------

def list_sites(access_token: str) -> list[dict]:
    payload = _http_json(SITES_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"})
    entries = payload.get("siteEntry", []) or []
    sites = [
        {"siteUrl": entry.get("siteUrl", ""), "permissionLevel": entry.get("permissionLevel", "")}
        for entry in entries
        if entry.get("permissionLevel") != "siteUnverifiedUser"
    ]
    sites.sort(key=lambda site: site["siteUrl"])
    return sites


def query_rows(access_token: str, site_url: str, start: str, end: str, dimensions: list[str] | None = None, row_limit: int = 1000) -> list[dict]:
    body: dict = {"startDate": start, "endDate": end, "rowLimit": min(row_limit, 1000)}
    if dimensions:
        body["dimensions"] = dimensions
    url = QUERY_ENDPOINT.format(site=urllib.parse.quote(site_url, safe=""))
    payload = _http_json(url, method="POST", headers={"Authorization": f"Bearer {access_token}"}, body=body)
    rows = payload.get("rows", []) or []
    return rows if isinstance(rows, list) else []


# ---------------------------------------------------------------------------
# Performance report assembly
# ---------------------------------------------------------------------------

def _parse_date(value: str) -> dt.date:
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise GscError(f"invalid_date: {value}", 400) from None


def previous_range(start: str, end: str) -> tuple[str, str]:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if end_date < start_date:
        raise GscError("invalid_range: end date before start date", 400)
    length = (end_date - start_date).days + 1
    prev_end = start_date - dt.timedelta(days=1)
    prev_start = prev_end - dt.timedelta(days=length - 1)
    return prev_start.isoformat(), prev_end.isoformat()


def _delta(current: float, previous: float | None) -> float | None:
    if previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _metric_row(rows: list[dict]) -> dict:
    if not rows:
        return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
    row = rows[0]
    return {
        "clicks": int(row.get("clicks", 0)),
        "impressions": int(row.get("impressions", 0)),
        "ctr": round(float(row.get("ctr", 0.0)), 4),
        "position": round(float(row.get("position", 0.0)), 1),
    }


def _table_rows(rows: list[dict], key_name: str, limit: int = 50) -> list[dict]:
    table = []
    for row in rows:
        keys = row.get("keys") or []
        if not keys:
            continue
        table.append({
            key_name: keys[0],
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr": round(float(row.get("ctr", 0.0)), 4),
            "position": round(float(row.get("position", 0.0)), 1),
        })
    table.sort(key=lambda item: item["clicks"], reverse=True)
    return table[:limit]


def performance_summary(access_token: str, site_url: str, start: str, end: str, compare: bool = True) -> dict:
    totals = _metric_row(query_rows(access_token, site_url, start, end))
    queries = _table_rows(query_rows(access_token, site_url, start, end, ["query"]), "query")
    pages = _table_rows(query_rows(access_token, site_url, start, end, ["page"]), "page")
    summary: dict = {
        "site": site_url,
        "start": start,
        "end": end,
        "totals": totals,
        "queries": queries,
        "pages": pages,
        "previous": None,
        "delta": None,
    }
    if compare:
        prev_start, prev_end = previous_range(start, end)
        prev_totals = _metric_row(query_rows(access_token, site_url, prev_start, prev_end))
        summary["previous"] = {"start": prev_start, "end": prev_end, "totals": prev_totals}
        summary["delta"] = {
            metric: _delta(totals[metric], prev_totals[metric])
            for metric in ("clicks", "impressions", "ctr", "position")
        }
    return summary
