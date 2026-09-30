# Development roadmap

## Phase 1 — foundation and knowledge structure

- Next.js, FastAPI, PostgreSQL, Alembic, and Docker Compose
- Category, Topic, and KnowledgePoint CRUD
- Knowledge-management interface
- Backend API tests and production builds

## Phase 2 — deterministic review loop (implemented, single-user MVP)

- Fixed, manually authored questions
- Study sessions and session items
- Answer records
- L1-L5 mastery update rules
- Review schedule with deterministic unit tests
- Persisted question snapshots, refresh/resume, weakest-rating scheduling per point
- Knowledge detail/editor, provenance, daily counts and recent session history

## Phase 3 — source ingestion

- 日序 text-note synchronization and a manual source inbox (implemented MVP)
- Content hashes and knowledge-point provenance (implemented MVP)
- RSS/Atom and RSSHub source management with manual sync (implemented MVP)
- Optional, bounded Crawl4AI page cleaning (implemented MVP)
- MediaCrawler platform adapters, account boundaries, and low-concurrency workers
- Markdown upload, source chunks, versions, and attachment copies
- Safe invalidation when source content changes

## Phase 4 — AI-assisted knowledge and questions (implemented, manual-review MVP)

- Replaceable LLM provider interface
- Structured and validated AI responses
- Knowledge extraction, question generation, and manual verification
- Original-text comparison, saved draft reuse, explicit regeneration and revision conflict checks

## Phase 5 — analysis and adaptation (implemented)

- Error classification — explicit, LLM-assisted; one current diagnosis per knowledge point
- Question variants — explicit, LLM-assisted; generated as `pending` and require manual
  approval before joining a point's `quiz_items`
- Actionable learning advice — deterministic Chinese tips derived from `review_progress`
  streak/level counters, no model call
- Dashboard analytics — mastery distribution, weak-point list, and error-type breakdown via
  `GET /analysis/overview`

Weak-point detection and the dashboard's tips are plain counter thresholds, in keeping with the
L1–L5 scheduler's transparent rules; only the two explicit "分析错题" / "生成变式题" actions call
the model, mirroring how AI knowledge drafts are generated and reviewed.

## Phase 6 — notification and deployment hardening

- OpenClaw adapter and idempotent notification logs
- Reverse proxy, TLS, backups, observability, and VPS deployment runbook
