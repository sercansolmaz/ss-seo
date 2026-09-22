import unittest

from ss_seo.api import audit_payload
from ss_seo.crawl import CrawlResult
from ss_seo.pipeline import AuditOutput


class APITests(unittest.TestCase):
    def test_payload_has_stable_sections(self):
        output = AuditOutput(CrawlResult(), [], [])
        payload = audit_payload("https://example.com", runner=lambda _: output)
        self.assertEqual(set(payload), {"url", "summary", "issues", "roadmap", "errors", "broken_links"})
        self.assertEqual(payload["summary"]["pages_crawled"], 0)


if __name__ == "__main__":
    unittest.main()
