# Deployment

The current MVP can run as a single container and listens on port `8787`.

Recommended staging hostname:

```text
seo.stuqio.com
```

Required reverse-proxy behavior:

- Forward HTTPS traffic to the container on port `8787`.
- Preserve the `Host` header.
- Enable TLS at the proxy.
- Expose `/health` for health checks.
- Keep crawler concurrency and URL limits bounded.

The current image is intentionally stateless at runtime. Before production use, connect PostgreSQL and a durable job queue, add authentication, and move audit persistence from in-process/local storage to the configured database.

