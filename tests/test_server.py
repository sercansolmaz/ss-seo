import unittest

from ss_seo.server import APIHandler


class ServerTests(unittest.TestCase):
    def test_handler_exists(self):
        self.assertTrue(callable(APIHandler.do_GET))
        self.assertTrue(callable(APIHandler.do_POST))


if __name__ == "__main__":
    unittest.main()

