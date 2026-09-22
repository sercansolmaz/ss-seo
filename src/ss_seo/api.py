"""Dependency-free JSON API helpers for the V0.1 audit pipeline."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .pipeline import AuditOutput, run_audit


def audit_payload(url: str, runner=run_audit) -> dict[str, Any]:
    return payload_from_output(url, runner(url))


def payload_from_output(url: str, output: AuditOutput) -> dict[str, Any]:
    return {
        "url": url,
        "summary": {
            "pages_crawled": len(output.crawl.pages),
            "errors": len(output.crawl.errors),
            "issues": len(output.issues),
            "roadmap_phases": len(output.roadmap),
        },
        "issues": [asdict(issue) for issue in output.issues],
        "roadmap": [asdict(item) for item in output.roadmap],
        "errors": output.crawl.errors,
        "broken_links": [
            {"url": page.item.url, "source_url": page.item.source_url}
            for page in output.crawl.pages
            if page.fetch.status_code == 404
        ],
    }
