"""Deterministic V0.1 SEO rules."""

from __future__ import annotations

from dataclasses import dataclass, field

from .crawl import CrawledPage, CrawlResult


@dataclass
class RuleIssue:
    rule_id: str
    category: str
    severity: str
    confidence: int
    impact: int
    effort: int
    url: str
    evidence: dict[str, object] = field(default_factory=dict)


def analyze(result: CrawlResult) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    for page in result.pages:
        url = page.item.url
        status = page.fetch.status_code
        if status is not None and status >= 400:
            issues.append(RuleIssue("HTTP-001", "http", "high" if status >= 500 else "medium", 100, 8, 4, url, {"status_code": status}))
        if page.html is None:
            continue
        if not page.html.title:
            issues.append(RuleIssue("ONPAGE-001", "on-page", "medium", 100, 5, 2, url, {"title": None}))
        if len(page.html.h1) == 0:
            issues.append(RuleIssue("ONPAGE-004", "on-page", "medium", 100, 5, 2, url, {"h1_count": 0}))
        elif len(page.html.h1) > 1:
            issues.append(RuleIssue("ONPAGE-003", "on-page", "low", 100, 3, 2, url, {"h1_count": len(page.html.h1)}))
        if not page.html.description:
            issues.append(RuleIssue("ONPAGE-005", "on-page", "low", 100, 3, 1, url, {"description": None}))
        for image in page.html.images:
            if image.get("alt") is None:
                issues.append(RuleIssue("IMAGE-001", "images", "low", 100, 2, 1, url, image))
    return issues

