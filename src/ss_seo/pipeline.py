"""End-to-end in-process audit pipeline for V0.1."""

from __future__ import annotations

from dataclasses import dataclass

from .crawl import Crawler, CrawlResult
from .roadmap import RoadmapItem, build_roadmap
from .rules import RuleIssue, analyze


@dataclass
class AuditOutput:
    crawl: CrawlResult
    issues: list[RuleIssue]
    roadmap: list[RoadmapItem]


def run_audit(seed_url: str, crawler: Crawler | None = None) -> AuditOutput:
    crawl = (crawler or Crawler()).crawl(seed_url)
    issues = analyze(crawl)
    return AuditOutput(crawl=crawl, issues=issues, roadmap=build_roadmap(issues))

