"""Evidence-level basic GEO/content signals; no fabricated visibility score."""

from __future__ import annotations

from dataclasses import dataclass, field

from .crawl import CrawlResult


@dataclass
class GEOFinding:
    rule_id: str
    url: str
    evidence_level: str
    evidence: dict[str, object] = field(default_factory=dict)


def analyze_geo(result: CrawlResult) -> list[GEOFinding]:
    findings: list[GEOFinding] = []
    for page in result.pages:
        if page.html is None:
            continue
        url = page.item.url
        if not page.html.author:
            findings.append(GEOFinding("GEO-001", url, "Medium", {"author": None, "basis": "no author metadata extracted"}))
        if not page.html.json_ld:
            findings.append(GEOFinding("GEO-002", url, "High", {"json_ld_blocks": 0, "basis": "no structured entity data extracted"}))
        if len(page.html.h1) != 1:
            findings.append(GEOFinding("GEO-003", url, "Medium", {"h1_count": len(page.html.h1), "basis": "primary topic signal is ambiguous"}))
        if not page.html.description:
            findings.append(GEOFinding("GEO-004", url, "Medium", {"description": None, "basis": "summary signal unavailable"}))
    return findings

