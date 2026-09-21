"""Safe URL normalization and crawl-scope policy."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


TRACKING_KEYS = {"gclid", "fbclid", "msclkid", "ref", "source"}


class URLPolicyError(ValueError):
    pass


def normalize_url(raw_url: str, base_url: str | None = None) -> str:
    candidate = urljoin(base_url, raw_url) if base_url else raw_url
    parts = urlsplit(candidate.strip())
    if parts.scheme.lower() not in {"http", "https"}:
        raise URLPolicyError("only http and https URLs are supported")
    if not parts.hostname:
        raise URLPolicyError("URL must include a hostname")

    host = parts.hostname.lower().rstrip(".")
    port = parts.port
    if (parts.scheme.lower(), port) in {("http", 80), ("https", 443)}:
        port = None
    netloc = host if port is None else "%s:%d" % (host, port)
    path = parts.path or "/"
    if path != "/":
        path = "/".join(segment for segment in path.split("/") if segment) 
        path = "/" + path
    query = urlencode(
        sorted((key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
               if not (key.lower().startswith("utm_") or key.lower() in TRACKING_KEYS)),
        doseq=True,
    )
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def _resolved_addresses(hostname: str) -> set[ipaddress._BaseAddress]:
    addresses = set()
    for result in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM):
        addresses.add(ipaddress.ip_address(result[4][0]))
    return addresses


def assert_public_host(hostname: str) -> None:
    try:
        addresses = _resolved_addresses(hostname)
    except socket.gaierror as exc:
        raise URLPolicyError("hostname cannot be resolved") from exc
    if not addresses:
        raise URLPolicyError("hostname has no resolved addresses")
    if any(address.is_private or address.is_loopback or address.is_link_local
           or address.is_reserved or address.is_multicast or address.is_unspecified
           for address in addresses):
        raise URLPolicyError("private or special-purpose address is not crawlable")


@dataclass(frozen=True)
class CrawlScope:
    hostname: str
    allow_subdomains: bool = False

    def allows(self, url: str) -> bool:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
        expected = self.hostname.lower().rstrip(".")
        return host == expected or (self.allow_subdomains and host.endswith("." + expected))

