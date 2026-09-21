import unittest

from ss_seo.crawl import Crawler
from ss_seo.fetcher import FetchResult
from ss_seo.pipeline import run_audit


class FakeFetcher:
    def fetch(self, url, scope):
        return FetchResult(requested_url=url, final_url=url, status_code=200, headers={"content-type": "text/html"}, body=b"<h1>Home</h1>")


class PipelineTests(unittest.TestCase):
    def test_pipeline_returns_issues_and_roadmap(self):
        output = run_audit("https://example.com/", Crawler(fetcher=FakeFetcher()))
        self.assertEqual(len(output.crawl.pages), 1)
        self.assertTrue(output.issues)
        self.assertTrue(output.roadmap)


if __name__ == "__main__":
    unittest.main()

