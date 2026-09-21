"""Polite, bounded HTTP fetching built on Python's standard library."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .url_policy import CrawlScope, URLPolicyError, assert_public_host, normalize_url


@dataclass(frozen=True)
class FetchConfig:
    timeout_seconds: float = 15.0
    max_retries: int = 2
    retry_delay_seconds: float = 0.5
    min_host_interval_seconds: float = 0.5
    user_agent: str = "SS-SEO-Crawler/0.1 (+polite audit crawler)"
    max_body_bytes: int = 2_000_000


@dataclass
class FetchResult:
    requested_url: str
    final_url: str | None = None
    status_code: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    elapsed_ms: int = 0
    redirect_chain: list[str] = field(default_factory=list)
    error: str | None = None


class PoliteFetcher:
    def __init__(self, config: FetchConfig | None = None, sleep: Callable[[float], None] = time.sleep):
        self.config = config or FetchConfig()
        self._sleep = sleep
        self._last_fetch_by_host: dict[str, float] = {}
        self._opener = build_opener()

    def fetch(self, raw_url: str, scope: CrawlScope) -> FetchResult:
        url = normalize_url(raw_url)
        if not scope.allows(url):
            raise URLPolicyError("URL is outside the configured crawl scope")
        host = url.split("/", 3)[2].split(":", 1)[0]
        assert_public_host(host)
        self._wait_for_host(host)

        result = FetchResult(requested_url=url)
        started = time.monotonic()
        for attempt in range(self.config.max_retries + 1):
            try:
                request = Request(url, headers={"User-Agent": self.config.user_agent, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.1"})
                with self._opener.open(request, timeout=self.config.timeout_seconds) as response:
                    result.status_code = response.status
                    result.final_url = normalize_url(response.geturl())
                    result.headers = {key.lower(): value for key, value in response.headers.items()}
                    result.body = response.read(self.config.max_body_bytes + 1)[: self.config.max_body_bytes]
                    result.redirect_chain = [url] if result.final_url != url else []
                    break
            except HTTPError as exc:
                result.status_code = exc.code
                result.final_url = url
                result.error = "HTTP %s" % exc.code
                if exc.code not in {408, 425, 429, 500, 502, 503, 504} or attempt >= self.config.max_retries:
                    break
            except (TimeoutError, URLError, OSError) as exc:
                result.error = str(exc)
                if attempt >= self.config.max_retries:
                    break
            self._sleep(self.config.retry_delay_seconds * (attempt + 1))
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
        return result

    def _wait_for_host(self, host: str) -> None:
        previous = self._last_fetch_by_host.get(host)
        if previous is not None:
            remaining = self.config.min_host_interval_seconds - (time.monotonic() - previous)
            if remaining > 0:
                self._sleep(remaining)
        self._last_fetch_by_host[host] = time.monotonic()

