"""Dependency-free V0.1 contracts used by API, crawler, and persistence layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AuditMode(str, Enum):
    QUICK = "quick"
    FULL = "full"
    DEEP = "deep"


class AuditStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IssueStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    REOPENED = "reopened"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Project:
    id: str
    name: str
    base_url: str
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class Audit:
    id: str
    project_id: str
    mode: AuditMode
    status: AuditStatus = AuditStatus.QUEUED
    max_urls: int = 100
    max_depth: int = 10
    crawler_version: str = "0.1.0"
    rule_version: str = "0.1.0"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    counters: dict[str, int] = field(default_factory=dict)


@dataclass
class UrlSnapshot:
    audit_id: str
    requested_url: str
    normalized_url: str
    final_url: str | None = None
    canonical_url: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    response_time_ms: int | None = None
    redirect_chain: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class IssueOccurrence:
    audit_id: str
    rule_id: str
    status: IssueStatus
    severity: str
    impact: int
    confidence: int
    effort: int
    evidence: dict[str, Any]
    affected_urls: list[str] = field(default_factory=list)
    detected_at: datetime = field(default_factory=utc_now)
    resolved_at: datetime | None = None
