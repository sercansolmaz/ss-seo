import unittest

from ss_seo.discovery import robots_url, sitemap_candidates, sitemap_links


class DiscoveryTests(unittest.TestCase):
    def test_robots_and_default_sitemaps(self):
        self.assertEqual(robots_url("https://example.com"), "https://example.com/robots.txt")
        candidates = sitemap_candidates("https://example.com", b"Sitemap: https://example.com/custom.xml")
        self.assertEqual(candidates[-1], "https://example.com/custom.xml")

    def test_sitemap_links(self):
        body = b'<sitemapindex xmlns="x"><sitemap><loc>https://example.com/a.xml</loc></sitemap></sitemapindex>'
        self.assertEqual(sitemap_links(body), ["https://example.com/a.xml"])


if __name__ == "__main__":
    unittest.main()

