import unittest

from ss_seo.crawl import CrawledPage, CrawlResult
from ss_seo.fetcher import FetchResult
from ss_seo.geo import analyze_geo
from ss_seo.parser import parse_html
from ss_seo.queue import CrawlItem


class GeoTests(unittest.TestCase):
    def test_findings_have_evidence_level(self):
        url = "https://example.com/"
        page = CrawledPage(CrawlItem(url), FetchResult(requested_url=url, status_code=200), parse_html(b"<h1>Topic</h1>", url))
        findings = analyze_geo(CrawlResult(pages=[page]))
        self.assertTrue(findings)
        self.assertTrue(all(item.evidence_level in {"High", "Medium", "Experimental"} for item in findings))


if __name__ == "__main__":
    unittest.main()

