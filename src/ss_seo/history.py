"""Audit comparison and issue lifecycle helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .rules import RuleIssue


@dataclass(frozen=True)
class IssueChange:
    rule_id: str
    url: str
    state: str
    previous: RuleIssue | None = None
    current: RuleIssue | None = None


def compare_issues(previous: list[RuleIssue], current: list[RuleIssue]) -> list[IssueChange]:
    old = {(issue.rule_id, issue.url): issue for issue in previous}
    new = {(issue.rule_id, issue.url): issue for issue in current}
    changes: list[IssueChange] = []
    for key in sorted(set(old) | set(new)):
        if key not in old:
            changes.append(IssueChange(key[0], key[1], "new", current=new[key]))
        elif key not in new:
            changes.append(IssueChange(key[0], key[1], "resolved", previous=old[key]))
        else:
            changes.append(IssueChange(key[0], key[1], "unchanged", previous=old[key], current=new[key]))
    return changes

