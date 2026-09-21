import unittest

from ss_seo.crawl import CrawledPage, CrawlResult
from ss_seo.fetcher import FetchResult
from ss_seo.parser import parse_html
from ss_seo.queue import CrawlItem
from ss_seo.rules import analyze


class RuleTests(unittest.TestCase):
    def test_missing_metadata_creates_evidence_backed_issues(self):
        page = CrawledPage(
            CrawlItem("https://example.com/"),
            FetchResult(requested_url="https://example.com/", status_code=200),
            parse_html(b'<img src="/hero.jpg">', "https://example.com/"),
        )
        issues = analyze(CrawlResult(pages=[page]))
        ids = {issue.rule_id for issue in issues}
        self.assertIn("ONPAGE-001", ids)
        self.assertIn("ONPAGE-004", ids)
        self.assertIn("IMAGE-001", ids)
        self.assertTrue(all(issue.evidence for issue in issues))


if __name__ == "__main__":
    unittest.main()

