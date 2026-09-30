# Source content supplementation contract

## Scope and entry points

`services/source_content.py`, `services/content_quality.py`, `integrations/article.py`,
`integrations/crawl4ai.py`, `schemas/source_document.py`, `models/source_document.py`.
Migration: `20260926_0007_source_content.py`, additive and backfills existing collected snapshots.

```text
GET   /api/v1/source-documents/{id}/content-collected
POST  /api/v1/source-documents/{id}/content-preview   {expected_revision: int >= 1}
PATCH /api/v1/source-documents/{id}/content           {expected_revision, content: string}
POST  /api/v1/source-documents/{id}/content-restore   {expected_revision}
```

## Storage and flow

- `content_origin`: collected | supplement; `content_revision >= 1` starts at 1.
- `collected_title/content/hash`: latest ingestion snapshot, backfilled on migration, fallback to active content for old in-memory fixtures.
- `supplement_base_hash`: ingestion hash when supplement was confirmed. `collected_changed` compares this with latest ingestion hash.
- `content` / `content_hash` remain the active input used by relevance scoring, AI and provenance.
- Only pending sources whose provider begins `feed:` can preview/apply/restore. Diary content is not fetched or edited by this workflow.
- Preview fetches only saved `source_url`, releases its DB transaction before network I/O, and verifies revision/status/address afterward. No DB writes and no LLM call.
- Preview content is returned to an editable user form. Apply deliberately accepts user-edited plain text/Markdown, not a trusted crawler attestation.
- Apply normalizes newlines and trims; 1–50,000 Unicode characters. Origin becomes supplement. Collected content remains available; restore explicitly adopts the latest collected title/content and returns origin to collected.
- RSS sync updates the collected snapshot even when supplemented, never the confirmed active title/content. A changed snapshot or address increments revision (including when active content is protected).
- Apply, restore and ingestion lock sources with `SELECT FOR UPDATE`. CAS comparison happens under this lock. Ingestion locks source IDs in stable order.
- Effective hash changes clear relevance/embedding state and mark draft stale, retaining its text. Knowledge points are untouched. Same-content apply is idempotent at the current revision. A stale revision always returns 409.
- This is not a full edit-history system: only active content and latest collected content are retained. Replacing an existing supplement requires explicit UI confirmation.

## Read models

SourceDocumentRead adds `content_origin`, `content_revision`, `content_chars`,
`content_warnings: string[]`, `ai_input_chars`, `ai_input_truncated`,
`collected_changed`, `can_supplement`.

Preview: `{source_document_id, expected_revision, content, content_chars, warnings}`.
Collected: `{title, content}`. Apply/restore return the complete SourceDocumentRead.
Warnings are conservative hints, not proof of completeness. AI input budget stays at
configured `LLM_MAX_SOURCE_CHARS`; v2 prompt includes actual length and truncation flag.
Opening any existing draft (including stale) without `regenerate=true` must never overwrite it.

## Fetch boundary and errors

New manual preview uses static HTML: standard HTTP(S) ports, no credentials, all DNS addresses
must be global/non-multicast, validated IP is pinned with Host and TLS SNI preserved, certificate
validation on, no environment proxies or cookies, each redirect revalidated (max 6 requests).
30-second fetch deadline with per-request timeout <=15 s; identity encoding only; HTML content
type and <=2 MiB. DNS resolution still uses the platform resolver timeout. No JS/login/CAPTCHA workarounds.
Drop scripts/resources/forms/nav/comments, preserve inert math/tex, strip attributes except safe
links, then send sanitized `raw:` HTML to existing Crawl4AI using its default non-browser path.
Do not send `process_in_browser` or `base_url`: 0.9.2 REST rejects these untrusted config fields
(even False). Links have already been made absolute. Production synthetic-HTML smoke verifies
the actual HTTP contract, separately from public sites that may return 401/403.
Prefer article containers; heuristic extraction may need manual cleanup. >50,000 cleaned chars
is an error, never silent truncation. One preview per process; multi-worker needs a shared gate.
These stronger restrictions apply to the new manual endpoint; legacy feed auto-clean behavior is unchanged.

| Condition | HTTP / behavior |
| --- | --- |
| Missing source | 404 not_found |
| Non-pending/non-RSS, missing preview URL, stale revision, preview already running | 409 conflict |
| Blank/too-long content or invalid revision | 422 validation detail |
| Private URL, nonstandard port, credentials | 422 invalid_source_url |
| Crawler unconfigured | 503 connector_not_configured; manual paste remains available |
| Fetch/clean failure | 502 upstream_unavailable or upstream_invalid_response; source/draft unchanged |
| Source changes while fetching/generating (even change-and-restore) | 409; no overwrite |

## Cases and verification

- Good: RSS excerpt → preview → inspect/edit → confirm → stale draft → explicit regenerate → manual approve.
- Base: cancel preview or retry identical content; no duplicate records or model calls.
- Bad: private redirect or two browsers applying revision 1; block network / second writer.

`tests/test_source_content.py`: preview no-write; apply/restore; RSS resync; stale draft preservation;
empty/oversize; pending-only; conflict/failure; ABA; URL pin/redirect/body limits; inert cleaning; model budget.
`tests/test_migrations.py`: old-source snapshot backfill, upgrade/check/down/up.
`deploy/verify-postgres.py`: isolated DB, simultaneous CAS applies (one succeeds), resync protection,
restore, migrations plus existing draft/review/provenance regression. Never seed production.

Wrong: overwrite source immediately after fetching, or blindly follow redirects.
Correct: fetch read-only candidate → explicit versioned apply → retain collected snapshot.

Raw HTML API reference: https://docs.crawl4ai.com/core/local-files/ (also checked deployed 0.9.2 fast path).
