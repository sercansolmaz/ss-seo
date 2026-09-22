import json
import os
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from ss_seo import gsc


class EncryptionTests(unittest.TestCase):
    def test_roundtrip(self):
        blob = gsc.encrypt_text("super-secret-token", "passphrase")
        self.assertTrue(blob.startswith("v1:"))
        self.assertNotIn("super-secret-token", blob)
        self.assertEqual(gsc.decrypt_text(blob, "passphrase"), "super-secret-token")

    def test_wrong_passphrase_rejected(self):
        blob = gsc.encrypt_text("secret", "right-key")
        with self.assertRaises(gsc.GscError) as ctx:
            gsc.decrypt_text(blob, "wrong-key")
        self.assertIn("integrity", str(ctx.exception))

    def test_tampered_ciphertext_rejected(self):
        blob = gsc.encrypt_text("secret", "key")
        parts = blob.split(":")
        import base64
        ciphertext = bytearray(base64.b64decode(parts[3]))
        ciphertext[0] ^= 0xFF
        parts[3] = base64.b64encode(bytes(ciphertext)).decode()
        with self.assertRaises(gsc.GscError):
            gsc.decrypt_text(":".join(parts), "key")

    def test_invalid_format_rejected(self):
        with self.assertRaises(gsc.GscError):
            gsc.decrypt_text("garbage", "key")


class StateTests(unittest.TestCase):
    def test_state_single_use(self):
        state = gsc.issue_state()
        self.assertTrue(gsc.consume_state(state))
        self.assertFalse(gsc.consume_state(state))  # replay rejected

    def test_state_rejects_unknown(self):
        self.assertFalse(gsc.consume_state("forged-state"))

    def test_state_expires(self):
        state = gsc.issue_state()
        with mock.patch("ss_seo.gsc.time.time", return_value=time.time() + gsc.STATE_TTL_SECONDS + 1):
            self.assertFalse(gsc.consume_state(state))


class TokenStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "gsc_tokens.json"
        self.store = gsc.TokenStore(path=self.path, passphrase="unit-test-key")

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_load_roundtrip(self):
        self.store.save_tokens("access-1", "refresh-1", 3600, gsc.GSC_SCOPE)
        record = self.store.load()
        self.assertEqual(record["access_token"], "access-1")
        self.assertEqual(record["refresh_token"], "refresh-1")
        raw = self.path.read_text()
        self.assertNotIn("access-1", raw)
        self.assertNotIn("refresh-1", raw)

    def test_missing_file_returns_none(self):
        self.assertIsNone(self.store.load())

    def test_clear(self):
        self.store.save_tokens("a", "r", 60, gsc.GSC_SCOPE)
        self.assertTrue(self.store.clear())
        self.assertFalse(self.path.exists())
        self.assertIsNone(self.store.load())
        self.assertFalse(self.store.clear())

    def test_no_passphrase_blocks_save(self):
        store = gsc.TokenStore(path=self.path, passphrase="")
        with self.assertRaises(gsc.GscError) as ctx:
            store.save_tokens("a", "r", 60, gsc.GSC_SCOPE)
        self.assertEqual(ctx.exception.status, 503)

    def test_valid_access_token_uses_cached_token(self):
        self.store.save_tokens("cached-access", "refresh-1", 3600, gsc.GSC_SCOPE)
        self.assertEqual(self.store.valid_access_token(), "cached-access")

    def test_valid_access_token_refreshes_when_expired(self):
        self.store.save_tokens("expired-access", "refresh-1", 3600, gsc.GSC_SCOPE)
        # force expiry
        record = json.loads(self.path.read_text())
        record["expires_at"] = time.time() - 10
        self.path.write_text(json.dumps(record))
        with mock.patch.object(gsc, "refresh_access_token", return_value={"access_token": "new-access", "expires_in": 3600, "scope": gsc.GSC_SCOPE}) as refresh:
            token = self.store.valid_access_token()
        self.assertEqual(token, "new-access")
        refresh.assert_called_once_with("refresh-1")
        # refresh token persisted, access token updated
        loaded = self.store.load()
        self.assertEqual(loaded["access_token"], "new-access")
        self.assertEqual(loaded["refresh_token"], "refresh-1")

    def test_valid_access_token_clears_on_invalid_grant(self):
        self.store.save_tokens("expired", "refresh-1", 3600, gsc.GSC_SCOPE)
        record = json.loads(self.path.read_text())
        record["expires_at"] = time.time() - 10
        self.path.write_text(json.dumps(record))
        with mock.patch.object(gsc, "refresh_access_token", side_effect=gsc.GscError("google_rejected_400: invalid_grant")):
            with self.assertRaises(gsc.GscError) as ctx:
                self.store.valid_access_token()
        self.assertEqual(ctx.exception.status, 401)
        self.assertFalse(self.path.exists())

    def test_valid_access_token_none_when_no_refresh_token(self):
        self.store.save_tokens("expired", None, 3600, gsc.GSC_SCOPE)
        record = json.loads(self.path.read_text())
        record["expires_at"] = time.time() - 10
        self.path.write_text(json.dumps(record))
        self.assertIsNone(self.store.valid_access_token())


class DateRangeTests(unittest.TestCase):
    def test_previous_range_same_length(self):
        self.assertEqual(gsc.previous_range("2026-09-15", "2026-09-21"), ("2026-09-08", "2026-09-14"))

    def test_previous_range_single_day(self):
        self.assertEqual(gsc.previous_range("2026-09-15", "2026-09-15"), ("2026-09-14", "2026-09-14"))

    def test_invalid_dates(self):
        with self.assertRaises(gsc.GscError):
            gsc.previous_range("not-a-date", "2026-09-15")
        with self.assertRaises(gsc.GscError):
            gsc.previous_range("2026-09-20", "2026-09-15")


class PerformanceSummaryTests(unittest.TestCase):
    def test_summary_assembles_tables_and_delta(self):
        def fake_query_rows(token, site, start, end, dimensions=None, row_limit=1000):
            if start == "2026-09-15":
                if dimensions == ["query"]:
                    return [{"keys": ["seo audit"], "clicks": 120, "impressions": 4000, "ctr": 0.03, "position": 4.2},
                            {"keys": ["site audit"], "clicks": 30, "impressions": 900, "ctr": 0.033, "position": 7.8}]
                if dimensions == ["page"]:
                    return [{"keys": ["https://example.com/audit"], "clicks": 140, "impressions": 5000, "ctr": 0.028, "position": 3.9}]
                return [{"clicks": 150, "impressions": 5000, "ctr": 0.03, "position": 4.5}]
            return [{"clicks": 100, "impressions": 4000, "ctr": 0.025, "position": 5.5}]

        with mock.patch.object(gsc, "query_rows", side_effect=fake_query_rows):
            summary = gsc.performance_summary("token", "sc-domain:example.com", "2026-09-15", "2026-09-21")
        self.assertEqual(summary["site"], "sc-domain:example.com")
        self.assertEqual(summary["totals"]["clicks"], 150)
        self.assertEqual(summary["queries"][0]["query"], "seo audit")
        self.assertEqual(summary["pages"][0]["page"], "https://example.com/audit")
        self.assertEqual(summary["previous"]["totals"]["clicks"], 100)
        self.assertEqual(summary["delta"]["clicks"], 50.0)

    def test_empty_rows_zero_metrics(self):
        with mock.patch.object(gsc, "query_rows", return_value=[]):
            summary = gsc.performance_summary("token", "sc-domain:x.com", "2026-09-15", "2026-09-21")
        self.assertEqual(summary["totals"], {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0})
        self.assertEqual(summary["queries"], [])
        self.assertIsNone(summary["delta"]["clicks"])


class SitesListingTests(unittest.TestCase):
    def test_list_sites_filters_unverified_and_sorts(self):
        payload = {"siteEntry": [
            {"siteUrl": "https://example.com/", "permissionLevel": "siteRestrictedUser"},
            {"siteUrl": "sc-domain:zexample.com", "permissionLevel": "siteFullUser"},
            {"siteUrl": "sc-domain:aexample.com", "permissionLevel": "siteUnverifiedUser"},
            {"siteUrl": "sc-domain:bexample.com", "permissionLevel": "siteOwner"},
        ]}
        with mock.patch.object(gsc, "_http_json", return_value=payload):
            sites = gsc.list_sites("token")
        self.assertEqual([s["siteUrl"] for s in sites], ["https://example.com/", "sc-domain:bexample.com", "sc-domain:zexample.com"])

    def test_query_rows_builds_request(self):
        captured = {}

        def fake_http(url, method="GET", headers=None, form=None, body=None):
            captured["url"] = url
            captured["body"] = body
            return {"rows": [{"keys": ["k"], "clicks": 1, "impressions": 2, "ctr": 0.5, "position": 1.0}]}

        with mock.patch.object(gsc, "_http_json", side_effect=fake_http):
            rows = gsc.query_rows("token", "sc-domain:example.com", "2026-09-01", "2026-09-07", ["query"])
        self.assertEqual(rows[0]["keys"], ["k"])
        self.assertIn("sc-domain%3Aexample.com", captured["url"])
        self.assertEqual(captured["body"]["dimensions"], ["query"])
        self.assertEqual(captured["body"]["rowLimit"], 1000)


class OauthConfigTests(unittest.TestCase):
    def test_config_requires_secret_too(self):
        with mock.patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": ""}, clear=False):
            self.assertIsNone(gsc.oauth_config())

    def test_auth_url_contains_state_and_scopes(self):
        config = {"client_id": "cid", "client_secret": "sec", "redirect_uri": "https://seo.stuqio.com/integrations/search-console/callback"}
        url = gsc.build_auth_url(config, "state-123")
        self.assertIn("state=state-123", url)
        self.assertIn("access_type=offline", url)
        self.assertIn("webmasters.readonly", url)
        self.assertIn("prompt=consent", url)


if __name__ == "__main__":
    unittest.main()
