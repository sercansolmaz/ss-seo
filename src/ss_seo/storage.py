"""Small SQLite persistence adapter for local development and tests."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict

from .contracts import Audit, IssueOccurrence, Project, UrlSnapshot


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, base_url TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audits (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL, max_urls INTEGER NOT NULL, max_depth INTEGER NOT NULL, crawler_version TEXT NOT NULL, rule_version TEXT NOT NULL, started_at TEXT, finished_at TEXT, counters_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS url_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, audit_id TEXT NOT NULL, requested_url TEXT NOT NULL, normalized_url TEXT NOT NULL, final_url TEXT, canonical_url TEXT, status_code INTEGER, content_type TEXT, response_time_ms INTEGER, redirect_chain_json TEXT NOT NULL, meta_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS issue_occurrences (id INTEGER PRIMARY KEY AUTOINCREMENT, audit_id TEXT NOT NULL, rule_id TEXT NOT NULL, status TEXT NOT NULL, severity TEXT NOT NULL, impact INTEGER NOT NULL, confidence INTEGER NOT NULL, effort INTEGER NOT NULL, evidence_json TEXT NOT NULL, affected_urls_json TEXT NOT NULL, detected_at TEXT NOT NULL, resolved_at TEXT);
"""


class SQLiteStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def save_project(self, project: Project) -> None:
        self.connection.execute("INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?)", (project.id, project.name, project.base_url, project.created_at.isoformat()))
        self.connection.commit()

    def save_audit(self, audit: Audit) -> None:
        self.connection.execute("INSERT OR REPLACE INTO audits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (audit.id, audit.project_id, audit.mode.value, audit.status.value, audit.max_urls, audit.max_depth, audit.crawler_version, audit.rule_version, audit.started_at.isoformat() if audit.started_at else None, audit.finished_at.isoformat() if audit.finished_at else None, json.dumps(audit.counters)))
        self.connection.commit()

    def save_snapshot(self, snapshot: UrlSnapshot) -> None:
        self.connection.execute("INSERT INTO url_snapshots (audit_id, requested_url, normalized_url, final_url, canonical_url, status_code, content_type, response_time_ms, redirect_chain_json, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (snapshot.audit_id, snapshot.requested_url, snapshot.normalized_url, snapshot.final_url, snapshot.canonical_url, snapshot.status_code, snapshot.content_type, snapshot.response_time_ms, json.dumps(snapshot.redirect_chain), json.dumps(snapshot.meta)))
        self.connection.commit()

    def save_issue(self, issue: IssueOccurrence) -> None:
        self.connection.execute("INSERT INTO issue_occurrences (audit_id, rule_id, status, severity, impact, confidence, effort, evidence_json, affected_urls_json, detected_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (issue.audit_id, issue.rule_id, issue.status.value, issue.severity, issue.impact, issue.confidence, issue.effort, json.dumps(issue.evidence), json.dumps(issue.affected_urls), issue.detected_at.isoformat(), issue.resolved_at.isoformat() if issue.resolved_at else None))
        self.connection.commit()

