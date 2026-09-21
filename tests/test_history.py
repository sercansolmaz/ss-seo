import unittest

from ss_seo.history import compare_issues
from ss_seo.rules import RuleIssue


def issue(rule_id, url):
    return RuleIssue(rule_id, "technical", "medium", 100, 5, 2, url, {"url": url})


class HistoryTests(unittest.TestCase):
    def test_new_resolved_and_unchanged(self):
        previous = [issue("HTTP-001", "https://example.com/old"), issue("ONPAGE-001", "https://example.com/same")]
        current = [issue("ONPAGE-001", "https://example.com/same"), issue("CANON-001", "https://example.com/new")]
        states = {(change.rule_id, change.url): change.state for change in compare_issues(previous, current)}
        self.assertEqual(states[("HTTP-001", "https://example.com/old")], "resolved")
        self.assertEqual(states[("CANON-001", "https://example.com/new")], "new")
        self.assertEqual(states[("ONPAGE-001", "https://example.com/same")], "unchanged")


if __name__ == "__main__":
    unittest.main()

