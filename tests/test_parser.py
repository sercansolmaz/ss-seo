import unittest

from ss_seo.parser import parse_html, parse_robots, parse_sitemap


class ParserTests(unittest.TestCase):
    def test_html_observation(self):
        page = b'<title>Home</title><meta name="description" content="Desc"><meta name="robots" content="noindex"><link rel="canonical" href="/"> <h1>Main</h1><a href="/about">About</a><img src="/x.png">'
        result = parse_html(page, "https://example.com/")
        self.assertEqual(result.title, "Home")
        self.assertEqual(result.links, ["https://example.com/about"])
        self.assertIsNone(result.images[0]["alt"])
        self.assertEqual(result.canonicals, ["https://example.com/"])
        self.assertEqual(result.robots_directives, ["noindex"])

    def test_robots_and_sitemap(self):
        robots = parse_robots(b"User-agent: *\nDisallow: /private\nSitemap: https://example.com/sitemap.xml")
        self.assertIn("/private", robots["disallows"])
        sitemap = parse_sitemap(b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></urlset>')
        self.assertEqual(sitemap["urls"], ["https://example.com/"])


if __name__ == "__main__":
    unittest.main()
