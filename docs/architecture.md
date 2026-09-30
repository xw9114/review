# Architecture

## Objective

Knowledge Review System is a single-user learning application. The first release keeps the
runtime simple while preserving clean boundaries for later knowledge ingestion, AI providers,
review scheduling, and notifications.

## Deployment topology

```text
Browser
  -> Cloudflare edge (TLS termination, host-level, shared across other projects on the VPS)
  -> cloudflared tunnel -> gateway (nginx, Basic Auth, 127.0.0.1-only)
  -> Next.js frontend / FastAPI backend (not published to the host)
  -> PostgreSQL (private Docker network, not published to the host)
  -> RSSHub (optional, private Docker network)
  -> Crawl4AI (optional, private Docker network, single concurrency)
```

Only `gateway` is published, and only on `127.0.0.1` — it is reachable solely through the
Cloudflare tunnel, never directly from the public internet. PostgreSQL, the backend, and the
frontend are never exposed. TLS and domain routing are handled by host-level infrastructure
outside this repo; see `docs/deployment.md` for the concrete topology and release/rollback/backup
procedures.

## Application boundaries

- `frontend`: user-facing dashboard and knowledge-structure management.
- `backend/app/api`: HTTP transport and validation only.
- `backend/app/services`: business operations and transaction boundaries.
- `backend/app/models`: SQLAlchemy persistence models.
- `backend/app/schemas`: Pydantic request and response contracts.
- `backend/alembic`: versioned database migrations.

Review scheduling, MediaCrawler, LLM providers, and notifications are deferred. Source adapters
live behind backend integration and service interfaces rather than being called from frontend
code.

The first source adapter imports private notes from the existing 日序 service. The browser never
receives the service token: FastAPI calls the token-protected notebook export endpoint, validates
the complete snapshot, and stores source documents before the user decides whether to create or
update a knowledge point. Failed upstream reads do not change source state.

RSS/Atom and RSSHub are the second source boundary. The user stores either a public Feed URL or an
RSSHub route. FastAPI fetches and parses the Feed, optionally asks Crawl4AI for article Markdown,
then writes through the same source-document upsert path. Browser cleaning is bounded to five
items per manual sync by default and Feed windows never stale older imported articles.

## Security baseline

- Secrets are supplied through environment variables and never embedded in frontend bundles.
- PostgreSQL is reachable only from the backend container.
- CORS is restricted to configured frontend origins.
- API validation is handled by Pydantic; database constraints enforce uniqueness and ownership.
- Private-source credentials are backend-only and use a dedicated service token rather than the
  notebook administrator password.
- Imported notes are not sent to an AI provider; later AI processing must be explicitly enabled.
- Public Feed and article URLs are DNS-resolved and rejected when they target loopback, private,
  link-local, reserved, multicast, or non-HTTP(S) addresses; redirects are validated again.
- RSSHub and Crawl4AI publish no host ports. Crawl4AI requires a backend-only Bearer token.
