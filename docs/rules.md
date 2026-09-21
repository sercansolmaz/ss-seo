# Initial Rule Catalog

Rule IDs are stable API identifiers and must be versioned.

| Category | Initial rules |
|---|---|
| HTTP | 4xx, 5xx, soft 404 candidate, redirect chain, redirect loop, non-canonical host, mixed protocol |
| Robots | unavailable, syntax issue, sitemap missing, important resource blocked, crawl trap candidate |
| Sitemap | invalid XML, duplicate URL, redirect URL, 4xx URL, 5xx URL, noindex URL, blocked URL, non-canonical URL, invalid lastmod |
| Canonical | missing, multiple, non-200 target, redirect target, chain, loop, cross-domain mismatch, hreflang conflict |
| Indexing | meta noindex, X-Robots noindex, blocked indexable URL, conflicting signals |
| On-page | missing/duplicate title, title length signal, missing/duplicate description, missing/multiple H1, empty heading, heading hierarchy issue |
| Links | broken internal link, redirecting internal link, orphan candidate, near-orphan, deep URL, dead-end, excessive links, weak anchor signal |
| Images | broken image, missing alt, empty alt on informative image, oversized image when available |
| Schema | JSON-LD parse error, duplicate entity, invalid URL, missing identifier, irrelevant type, entity conflict |
| Hreflang | malformed value, missing return link, self-reference missing, canonical conflict |
| GEO candidates | missing author, missing organization, missing source/date signal, unclear primary entity, answer not extractable |

The catalog is intentionally evidence-first. Character limits are signals, not automatic failures.

