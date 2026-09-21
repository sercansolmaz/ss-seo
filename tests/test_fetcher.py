import unittest

from ss_seo.fetcher import FetchConfig


class FetcherTests(unittest.TestCase):
    def test_safe_defaults(self):
        config = FetchConfig()
        self.assertEqual(config.max_retries, 2)
        self.assertEqual(config.max_body_bytes, 2_000_000)
        self.assertGreater(config.min_host_interval_seconds, 0)


if __name__ == "__main__":
    unittest.main()

