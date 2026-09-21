import sqlite3
import unittest

from ss_seo.contracts import Audit, AuditMode, IssueOccurrence, IssueStatus, Project
from ss_seo.storage import SQLiteStore


class StorageTests(unittest.TestCase):
    def test_core_entities_are_persisted(self):
        store = SQLiteStore(sqlite3.connect(":memory:"))
        store.save_project(Project("p1", "Example", "https://example.com"))
        store.save_audit(Audit("a1", "p1", AuditMode.QUICK))
        store.save_issue(IssueOccurrence("a1", "HTTP-001", IssueStatus.OPEN, "high", 8, 100, 2, {"status": 500}))
        self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0], 1)
        self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM audits").fetchone()[0], 1)
        self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM issue_occurrences").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()

