import unittest

from ss_seo.crawl import CrawledPage, CrawlResult
from ss_seo.fetcher import FetchResult
from ss_seo.parser import parse_html
from ss_seo.queue import CrawlItem
from ss_seo.rules import analyze_sitemap_urls


class SitemapRuleTests(unittest.TestCase):
    def test_noindex_sitemap_url_is_reported(self):
        url = "https://example.com/page"
        page = CrawledPage(CrawlItem(url), FetchResult(requested_url=url, status_code=200), parse_html(b'<meta name="robots" content="noindex">', url))
        issues = analyze_sitemap_urls([url], CrawlResult(pages=[page]))
        self.assertEqual([issue.rule_id for issue in issues], ["SITEMAP-006"])


if __name__ == "__main__":
    unittest.main()

