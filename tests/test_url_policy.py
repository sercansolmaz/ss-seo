import unittest

from ss_seo.url_policy import CrawlScope, URLPolicyError, normalize_url


class URLPolicyTests(unittest.TestCase):
  def test_normalization_removes_tracking_query_and_fragment(self):
    self.assertEqual(normalize_url("HTTPS://Example.COM:443/a//b/?utm_source=x&z=2#section"), "https://example.com/a/b?z=2")


  def test_relative_url_uses_base(self):
    self.assertEqual(normalize_url("/about", "https://example.com/start"), "https://example.com/about")


  def test_non_http_url_is_rejected(self):
    with self.assertRaises(URLPolicyError):
        normalize_url("javascript:alert(1)")


  def test_scope_is_explicit(self):
    scope = CrawlScope("example.com")
    self.assertTrue(scope.allows("https://example.com/a"))
    self.assertFalse(scope.allows("https://www.example.com/a"))


if __name__ == "__main__":
  unittest.main()
