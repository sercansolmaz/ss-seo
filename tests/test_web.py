import unittest
from pathlib import Path


class WebTests(unittest.TestCase):
    def test_dashboard_exists(self):
        path = Path(__file__).parents[1] / "web" / "index.html"
        self.assertTrue(path.exists())
        self.assertIn("SS SEO Intelligence", path.read_text())


if __name__ == "__main__":
    unittest.main()

