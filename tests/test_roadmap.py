import unittest

from ss_seo.roadmap import build_roadmap, priority
from ss_seo.rules import RuleIssue


class RoadmapTests(unittest.TestCase):
    def test_priority_and_grouping(self):
        issues = [
            RuleIssue("HTTP-001", "http", "high", 100, 8, 2, "https://example.com/a", {}),
            RuleIssue("ONPAGE-001", "on-page", "medium", 100, 5, 2, "https://example.com/b", {}),
        ]
        self.assertGreater(priority(issues[0]), priority(issues[1]))
        roadmap = build_roadmap(issues)
        self.assertEqual(roadmap[0].issue_ids, ("HTTP-001",))
        self.assertEqual(roadmap[0].affected_urls, 1)


if __name__ == "__main__":
    unittest.main()

