# Core Data Model

## Project

Owns one or more domains and audit configuration.

## Audit

One Quick, Full, or Deep run. Stores status, limits, versions, timestamps, and counters.

## URL snapshot

Stores requested URL, final URL, canonical URL, normalized URL, status, headers, content type, timing, body hash, extracted metadata, and crawl depth for one audit.

## Issue and occurrence

`Issue` is the versioned rule definition. `IssueOccurrence` is its evidence-backed result in an audit. Occurrences transition through `open`, `resolved`, and `reopened`.

## Graph records

Internal links, redirects, sitemap membership, schema entities, and external links are separate records so they can be queried without re-parsing HTML.

