"""Evidence-backed issue prioritization and fix roadmap generation."""

from __future__ import annotations

from dataclasses import dataclass

from .rules import RuleIssue


@dataclass(frozen=True)
class RoadmapItem:
    phase: int
    title: str
    reason: str
    issue_ids: tuple[str, ...]
    affected_urls: int
    difficulty: int
    verification: str


def priority(issue: RuleIssue) -> float:
    """Ranking aid only; it is not a scientific SEO score."""
    return (issue.impact * issue.confidence / 100) / max(issue.effort, 1)


def build_roadmap(issues: list[RuleIssue]) -> list[RoadmapItem]:
    groups: dict[str, list[RuleIssue]] = {}
    for issue in issues:
        groups.setdefault(issue.category, []).append(issue)
    ordered = sorted(groups.items(), key=lambda pair: max(priority(item) for item in pair[1]), reverse=True)
    roadmap: list[RoadmapItem] = []
    for index, (category, category_issues) in enumerate(ordered, 1):
        ranked = sorted(category_issues, key=priority, reverse=True)
        ids = tuple(dict.fromkeys(item.rule_id for item in ranked))
        urls = len({item.url for item in category_issues})
        difficulty = round(sum(item.effort for item in category_issues) / len(category_issues))
        roadmap.append(RoadmapItem(index, category.title() + " fixes", "Address the highest-impact " + category + " findings first.", ids, urls, difficulty, "Re-run the affected rules and compare evidence with the previous audit."))
    return roadmap

