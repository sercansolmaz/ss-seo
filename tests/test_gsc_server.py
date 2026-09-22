import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

from ss_seo import gsc, server


class _ServerFixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.token_file = Path(self.tmp.name) / "gsc_tokens.json"
        env = {
            "GOOGLE_CLIENT_ID": "test-client-id",
            "GOOGLE_CLIENT_SECRET": "test-client-secret",
            "GOOGLE_REDIRECT_URI": "https://seo.stuqio.com/integrations/search-console/callback",
            "TOKEN_ENCRYPTION_KEY": "test-encryption-key",
            "GSC_TOKEN_FILE": str(self.token_file),
        }
        self.env_patch = mock.patch.dict(os.environ, env, clear=False)
        self.env_patch.start()
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.APIHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def request(self, path, method="GET", body=None, follow_redirects=True):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *_args, **_kwargs):
                return None

        opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=10) as response:
                return response.status, response.read().decode(), dict(response.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode(), dict(exc.headers)

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.env_patch.stop()
        self.tmp.cleanup()


class GscServerRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = _ServerFixture()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.stop()

    def test_health_still_ok(self):
        status, body, _ = self.fixture.request("/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")

    def test_connect_redirects_to_google_with_state(self):
        status, _, headers = self.fixture.request("/integrations/search-console/connect", follow_redirects=False)
        self.assertEqual(status, 302)
        location = headers.get("Location", "")
        self.assertIn("accounts.google.com/o/oauth2/v2/auth", location)
        self.assertIn("state=", location)
        self.assertIn("webmasters.readonly", location)

    def test_callback_rejects_missing_state(self):
        status, body, _ = self.fixture.request("/integrations/search-console/callback?code=x")
        self.assertEqual(status, 400)
        self.assertIn("eksik", body.lower())

    def test_callback_rejects_forged_state(self):
        status, body, _ = self.fixture.request("/integrations/search-console/callback?code=x&state=forged")
        self.assertEqual(status, 400)
        self.assertIn("state", body.lower())

    def test_callback_rejects_replayed_state(self):
        state = gsc.issue_state()
        path = f"/integrations/search-console/callback?code=x&state={urllib.parse.quote(state)}"
        self.fixture.request(path)  # first attempt consumes state
        status, body, _ = self.fixture.request(path)  # replay
        self.assertEqual(status, 400)
        self.assertIn("state", body.lower())

    def test_callback_rejects_error_param(self):
        status, body, _ = self.fixture.request("/integrations/search-console/callback?error=access_denied&state=x")
        self.assertEqual(status, 400)
        self.assertIn("access_denied", body)

    def test_callback_success_flow_saves_encrypted_tokens(self):
        state = gsc.issue_state()
        tokens = {"access_token": "live-access", "refresh_token": "live-refresh", "expires_in": 3600, "scope": gsc.GSC_SCOPE}
        with mock.patch.object(gsc, "exchange_code", return_value=tokens) as exchange:
            status, body, _ = self.fixture.request(f"/integrations/search-console/callback?code=authz-code&state={urllib.parse.quote(state)}")
        self.assertEqual(status, 200)
        self.assertIn("bağlandı", body.lower())
        exchange.assert_called_once_with("authz-code")
        raw = self.fixture.token_file.read_text()
        self.assertNotIn("live-access", raw)
        self.assertNotIn("live-refresh", raw)
        record = json.loads(raw)
        self.assertTrue(record["access_token"].startswith("v1:"))
        self.assertTrue(record["refresh_token"].startswith("v1:"))
        # status now reports connected
        status, body, _ = self.fixture.request("/integrations/search-console/status")
        payload = json.loads(body)
        self.assertTrue(payload["connected"])
        self.assertTrue(payload["has_refresh_token"])

    def test_sites_requires_connection(self):
        self.fixture.token_file.unlink(missing_ok=True)
        status, body, _ = self.fixture.request("/integrations/search-console/sites")
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body)["error"], "not_connected")

    def test_performance_requires_connection(self):
        self.fixture.token_file.unlink(missing_ok=True)
        status, body, _ = self.fixture.request("/integrations/search-console/performance?site=sc-domain:x.com&start=2026-09-01&end=2026-09-07")
        self.assertEqual(status, 401)

    def test_performance_validates_params(self):
        gsc.TokenStore(path=self.fixture.token_file, passphrase="test-encryption-key").save_tokens("a", "r", 3600, gsc.GSC_SCOPE)
        status, body, _ = self.fixture.request("/integrations/search-console/performance?site=sc-domain:x.com")
        self.assertEqual(status, 400)

    def test_performance_returns_real_shape(self):
        gsc.TokenStore(path=self.fixture.token_file, passphrase="test-encryption-key").save_tokens("a", "r", 3600, gsc.GSC_SCOPE)
        summary = {"site": "sc-domain:x.com", "totals": {"clicks": 1}, "queries": [], "pages": [], "previous": None, "delta": None}
        with mock.patch.object(gsc, "performance_summary", return_value=summary) as perf:
            status, body, _ = self.fixture.request("/integrations/search-console/performance?site=sc-domain:x.com&start=2026-09-01&end=2026-09-07")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["totals"]["clicks"], 1)
        perf.assert_called_once_with("a", "sc-domain:x.com", "2026-09-01", "2026-09-07")

    def test_sites_lists_properties(self):
        gsc.TokenStore(path=self.fixture.token_file, passphrase="test-encryption-key").save_tokens("a", "r", 3600, gsc.GSC_SCOPE)
        with mock.patch.object(gsc, "list_sites", return_value=[{"siteUrl": "sc-domain:x.com", "permissionLevel": "siteOwner"}]):
            status, body, _ = self.fixture.request("/integrations/search-console/sites")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["connected"])
        self.assertEqual(payload["sites"][0]["siteUrl"], "sc-domain:x.com")

    def test_disconnect_via_post(self):
        gsc.TokenStore(path=self.fixture.token_file, passphrase="test-encryption-key").save_tokens("a", "r", 3600, gsc.GSC_SCOPE)
        status, body, _ = self.fixture.request("/integrations/search-console/disconnect", method="POST", body={})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["removed"])
        self.assertFalse(self.fixture.token_file.exists())
        status, body, _ = self.fixture.request("/integrations/search-console/status")
        self.assertFalse(json.loads(body)["connected"])

    def test_disconnect_get_rejected(self):
        status, body, _ = self.fixture.request("/integrations/search-console/disconnect")
        self.assertEqual(status, 405)

    def test_homepage_still_served(self):
        status, body, _ = self.fixture.request("/")
        self.assertEqual(status, 200)
        self.assertIn("SS SEO", body)
        self.assertIn("gsc-panel", body)

    def test_unconfigured_returns_503(self):
        env = {k: "" for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")}
        with mock.patch.dict(os.environ, env, clear=False):
            status, body, _ = self.fixture.request("/integrations/search-console/connect", follow_redirects=False)
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["error"], "search_console_not_configured")



if __name__ == "__main__":
    unittest.main()
