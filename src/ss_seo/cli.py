"""Minimal local audit command; no production deployment assumptions."""

from __future__ import annotations

import argparse

from .pipeline import run_audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded SS SEO audit")
    parser.add_argument("url")
    args = parser.parse_args()
    output = run_audit(args.url)
    print("pages=%d issues=%d roadmap_phases=%d" % (len(output.crawl.pages), len(output.issues), len(output.roadmap)))
    for issue in output.issues:
        print("%s [%s] %s" % (issue.rule_id, issue.severity, issue.url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

