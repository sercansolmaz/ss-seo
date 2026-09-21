# V0.1 Architecture

```text
Web UI -> API -> Audit Orchestrator -> Crawler -> Rule Engine
                                  |              |
                                  +-> PostgreSQL <-+
                                  |
                                  +-> Candidate selection -> Hermes reasoning
```

The first implementation must keep deterministic observations separate from interpretation. Every issue occurrence carries evidence, rule version, affected URLs, confidence, and verification instructions.

## Audit lifecycle

`queued -> running -> completed | failed | cancelled`

An audit stores crawler and rule-engine versions, limits, timings, URL counts, errors, and the resulting issue occurrences. A recheck is a new audit linked to the original issue; it never overwrites history.

## Safety boundaries

- Only `http` and `https` URLs are accepted.
- Resolve hostnames and reject loopback, link-local, private, multicast, unspecified, and cloud-metadata IP ranges.
- Restrict requests to the configured project host and approved subdomains.
- Apply per-host concurrency, delay, timeout, retry, maximum URL count, and maximum depth.
- Do not execute arbitrary page JavaScript by default.

