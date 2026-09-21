"""Bounded breadth-first crawl queue."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class CrawlItem:
    url: str
    depth: int = 0
    source: str = "seed"


class CrawlQueue:
    def __init__(self, max_urls: int = 100, max_depth: int = 10):
        self.max_urls = max_urls
        self.max_depth = max_depth
        self._items = deque()
        self._seen = set()

    def add(self, item: CrawlItem) -> bool:
        if item.depth > self.max_depth or item.url in self._seen or len(self._seen) >= self.max_urls:
            return False
        self._seen.add(item.url)
        self._items.append(item)
        return True

    def pop(self) -> CrawlItem | None:
        return self._items.popleft() if self._items else None

    def __len__(self) -> int:
        return len(self._items)

    @property
    def scheduled_count(self) -> int:
        return len(self._seen)

