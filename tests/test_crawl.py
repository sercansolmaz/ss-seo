import unittest

from ss_seo.crawl import Crawler
from ss_seo.fetcher import FetchResult


class FakeFetcher:
    def fetch(self, url, scope):
        body = b'<html><title>Home</title><a href="/about">About</a></html>' if url.endswith("/") else b'<html><title>About</title></html>'
        return FetchResult(requested_url=url, final_url=url, status_code=200, headers={"content-type": "text/html"}, body=body)


class CrawlTests(unittest.TestCase):
    def test_crawl_discovers_internal_links(self):
        result = Crawler(fetcher=FakeFetcher(), max_urls=10).crawl("https://example.com/")
        self.assertEqual(len(result.pages), 2)
        self.assertEqual(result.pages[1].html.title, "About")


if __name__ == "__main__":
    unittest.main()

