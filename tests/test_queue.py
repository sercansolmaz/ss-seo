import unittest

from ss_seo.queue import CrawlItem, CrawlQueue


class QueueTests(unittest.TestCase):
    def test_deduplicates_and_respects_limits(self):
        queue = CrawlQueue(max_urls=2, max_depth=1)
        self.assertTrue(queue.add(CrawlItem("https://example.com/", 0)))
        self.assertFalse(queue.add(CrawlItem("https://example.com/", 0)))
        self.assertFalse(queue.add(CrawlItem("https://example.com/deep", 2)))
        self.assertTrue(queue.add(CrawlItem("https://example.com/a", 1)))
        self.assertFalse(queue.add(CrawlItem("https://example.com/b", 1)))
        self.assertEqual(queue.scheduled_count, 2)


if __name__ == "__main__":
    unittest.main()

