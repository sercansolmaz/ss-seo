"""V0.1 crawl orchestration without persistence or external services."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .fetcher import FetchResult, PoliteFetcher
from .parser import HTMLObservation, parse_html
from .queue import CrawlItem, CrawlQueue
from .url_policy import CrawlScope, normalize_url


@dataclass
class CrawledPage:
    item: CrawlItem
    fetch: FetchResult
    html: HTMLObservation | None = None


@dataclass
class CrawlResult:
    pages: list[CrawledPage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Crawler:
    def __init__(
        self,
        fetcher: PoliteFetcher | None = None,
        max_urls: int = 100,
        max_depth: int = 10,
        progress: Callable[[dict[str, int]], None] | None = None,
    ):
        self.fetcher = fetcher or PoliteFetcher()
        self.max_urls = max_urls
        self.max_depth = max_depth
        self.progress = progress

    def crawl(self, seed_url: str) -> CrawlResult:
        seed = normalize_url(seed_url)
        scope = CrawlScope(hostname=seed.split("/", 3)[2].split(":", 1)[0])
        queue = CrawlQueue(max_urls=self.max_urls, max_depth=self.max_depth)
        queue.add(CrawlItem(seed))
        result = CrawlResult()
        while (item := queue.pop()) is not None:
            try:
                fetched = self.fetcher.fetch(item.url, scope)
            except Exception as exc:  # crawl continues and records the failed URL
                result.errors.append("%s: %s" % (item.url, exc))
                self._report(queue, result)
                continue
            page = CrawledPage(item=item, fetch=fetched)
            content_type = fetched.headers.get("content-type", "").lower()
            if fetched.body and ("html" in content_type or not content_type):
                page.html = parse_html(fetched.body, fetched.final_url or item.url)
                for link in page.html.links:
                    try:
                        normalized = normalize_url(link)
                    except ValueError:
                        continue
                    if scope.allows(normalized):
                        queue.add(CrawlItem(normalized, item.depth + 1, "internal-link", item.url))
            result.pages.append(page)
            self._report(queue, result)
        return result

    def _report(self, queue: CrawlQueue, result: CrawlResult) -> None:
        if self.progress is not None:
            self.progress({
                "scheduled": queue.scheduled_count,
                "completed": len(result.pages) + len(result.errors),
                "queued": len(queue),
                "errors": len(result.errors),
            })
