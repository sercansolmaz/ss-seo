"""Dependency-free JSON API helpers for the V0.1 audit pipeline."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .pipeline import run_audit


def audit_payload(url: str, runner=run_audit) -> dict[str, Any]:
    output = runner(url)
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
    }

