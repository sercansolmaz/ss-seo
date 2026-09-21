"""Small dependency-free parsers for robots, sitemaps, and HTML observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin
from xml.etree import ElementTree


@dataclass
class HTMLObservation:
    title: str | None = None
    description: str | None = None
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    h3: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    images: list[dict[str, str | None]] = field(default_factory=list)
    json_ld: list[str] = field(default_factory=list)
    canonicals: list[str] = field(default_factory=list)
    robots_directives: list[str] = field(default_factory=list)


class _PageParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.observation = HTMLObservation()
        self._active: str | None = None
        self._buffer: list[str] = []
        self._meta_description = False
        self._json_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs}
        tag = tag.lower()
        if tag == "title":
            self._active, self._buffer = "title", []
        elif tag in {"h1", "h2", "h3"}:
            self._active, self._buffer = tag, []
        elif tag == "meta" and values.get("name", "").lower() == "description":
            self.observation.description = values.get("content")
        elif tag == "meta" and values.get("name", "").lower() == "robots" and values.get("content"):
            self.observation.robots_directives.extend(part.strip().lower() for part in values["content"].split(","))
        elif tag == "link" and values.get("rel", "").lower() == "canonical" and values.get("href"):
            self.observation.canonicals.append(urljoin(self.base_url, values["href"]))
        elif tag == "a" and values.get("href"):
            self.observation.links.append(urljoin(self.base_url, values["href"]))
        elif tag == "img" and values.get("src"):
            self.observation.images.append({"src": urljoin(self.base_url, values["src"]), "alt": values.get("alt")})
        elif tag == "script" and values.get("type", "").lower() == "application/ld+json":
            self._json_ld, self._buffer = True, []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._active == tag:
            value = " ".join("".join(self._buffer).split())
            if tag == "title":
                self.observation.title = value or None
            elif tag in {"h1", "h2", "h3"} and value:
                getattr(self.observation, tag).append(value)
            self._active = None
            self._buffer = []
        if tag == "script" and self._json_ld:
            value = "".join(self._buffer).strip()
            if value:
                self.observation.json_ld.append(value)
            self._json_ld = False
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._active or self._json_ld:
            self._buffer.append(data)


def parse_html(body: bytes, base_url: str) -> HTMLObservation:
    parser = _PageParser(base_url)
    parser.feed(body.decode("utf-8", errors="replace"))
    return parser.observation


def parse_robots(body: bytes) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {"user_agents": [], "disallows": [], "sitemaps": []}
    for raw_line in body.decode("utf-8", errors="replace").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            result["user_agents"].append(value)
        elif key == "disallow" and value:
            result["disallows"].append(value)
        elif key == "sitemap" and value:
            result["sitemaps"].append(value)
    return result


def parse_sitemap(body: bytes) -> dict[str, list[str]]:
    root = ElementTree.fromstring(body)
    tag = root.tag.rsplit("}", 1)[-1].lower()
    values = [element.text.strip() for element in root.iter() if element.tag.rsplit("}", 1)[-1].lower() == "loc" and element.text]
    if tag == "sitemapindex":
        return {"sitemaps": values, "urls": []}
    return {"sitemaps": [], "urls": values}
