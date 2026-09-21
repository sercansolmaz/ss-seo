"""Discovery helpers for robots.txt and sitemap resources."""

from __future__ import annotations

from urllib.parse import urljoin

from .parser import parse_robots, parse_sitemap


def robots_url(base_url: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", "robots.txt")


def default_sitemap_urls(base_url: str) -> list[str]:
    root = base_url.rstrip("/") + "/"
    return [urljoin(root, "sitemap.xml"), urljoin(root, "sitemap_index.xml")]


def sitemap_candidates(base_url: str, robots_body: bytes | None = None) -> list[str]:
    candidates = list(default_sitemap_urls(base_url))
    if robots_body:
        for value in parse_robots(robots_body)["sitemaps"]:
            if value not in candidates:
                candidates.append(value)
    return candidates


def sitemap_links(body: bytes) -> list[str]:
    parsed = parse_sitemap(body)
    return parsed["sitemaps"] + parsed["urls"]

