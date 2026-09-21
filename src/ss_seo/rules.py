"""Deterministic V0.1 SEO rules."""

from __future__ import annotations

from dataclasses import dataclass, field

from .crawl import CrawledPage, CrawlResult
from .url_policy import normalize_url


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
    titles: dict[str, list[str]] = {}
    for page in result.pages:
        url = page.item.url
        status = page.fetch.status_code
        if status is not None and status >= 400:
            issues.append(RuleIssue("HTTP-001", "http", "high" if status >= 500 else "medium", 100, 8, 4, url, {"status_code": status}))
        if page.html is None:
            continue
        if not page.html.title:
            issues.append(RuleIssue("ONPAGE-001", "on-page", "medium", 100, 5, 2, url, {"title": None}))
        else:
            titles.setdefault(page.html.title.casefold(), []).append(url)
        if len(page.html.h1) == 0:
            issues.append(RuleIssue("ONPAGE-004", "on-page", "medium", 100, 5, 2, url, {"h1_count": 0}))
        elif len(page.html.h1) > 1:
            issues.append(RuleIssue("ONPAGE-003", "on-page", "low", 100, 3, 2, url, {"h1_count": len(page.html.h1)}))
        if not page.html.description:
            issues.append(RuleIssue("ONPAGE-005", "on-page", "low", 100, 3, 1, url, {"description": None}))
        if len(page.html.canonicals) == 0:
            issues.append(RuleIssue("CANON-001", "canonical", "medium", 100, 5, 2, url, {"canonical_count": 0}))
        elif len(page.html.canonicals) > 1:
            issues.append(RuleIssue("CANON-002", "canonical", "high", 100, 7, 3, url, {"canonical_count": len(page.html.canonicals), "canonicals": page.html.canonicals}))
        else:
            canonical = page.html.canonicals[0]
            if page.fetch.status_code and page.fetch.status_code >= 400:
                issues.append(RuleIssue("CANON-003", "canonical", "high", 90, 7, 4, url, {"canonical": canonical, "page_status": page.fetch.status_code}))
            try:
                if normalize_url(canonical) != normalize_url(url):
                    issues.append(RuleIssue("CANON-006", "canonical", "low", 75, 3, 3, url, {"canonical": canonical, "requested_url": url}))
            except ValueError:
                issues.append(RuleIssue("CANON-007", "canonical", "high", 100, 7, 2, url, {"canonical": canonical}))
        if "noindex" in page.html.robots_directives:
            issues.append(RuleIssue("INDEX-001", "indexing", "medium", 100, 5, 1, url, {"robots_directives": page.html.robots_directives}))
        for image in page.html.images:
            if image.get("alt") is None:
                issues.append(RuleIssue("IMAGE-001", "images", "low", 100, 2, 1, url, image))
    for title, urls in titles.items():
        if len(urls) > 1:
            for url in urls:
                issues.append(RuleIssue("ONPAGE-002", "on-page", "medium", 100, 5, 3, url, {"title": title, "duplicate_url_count": len(urls), "affected_urls": urls}))
    return issues
