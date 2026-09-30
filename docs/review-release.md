# Review-loop release / 2026-09-26

## Scope

Manual source → saved AI draft → human approval → knowledge detail → persistent practice.
Also includes original-text comparison, draft reuse/version checks, question editing, answer
history, deterministic scheduling, home-page queue counts and narrow-screen navigation.

No automatic approval, automatic discarding, periodic model calls, Embedding deployment,
MediaCrawler accounts, new public ports or unrelated VPS services are included.

## Verification

- Backend: `backend/.venv/Scripts/python -m pytest -q` (47 tests), including migration
  upgrade/downgrade and data preservation. Two existing dependency deprecation warnings.
- Frontend: `npm run lint`, `npx tsc --noEmit`, telemetry-disabled `npm run build`.
- `docs/visual-qa/review-fixture.py`: localhost-only API with a disposable SQLite DB and fake
  LLM. Use `PYTHONPATH` pointing to backend. Never pass production DB settings to this script.
- Build frontend with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1` and run it on
  localhost port 3001. `node docs/visual-qa/check-review-loop.cjs` verifies generation does not
  publish, save/resume does not regenerate, explicit approval, content edits, reveal/reload/self-
  rating, source links, visible failures and 24 screenshots (four pages × three widths × themes).
- Existing source/draft visual checks also pass. Built-in browser control was unavailable in
  this environment; the repository's local headless Chromium path was used for QA.
- `deploy/verify-postgres.py` runs in the new production image against a newly created temporary
  database, including migration/schema checks and concurrent review operations, then removes
  only that database. It does not copy or modify production knowledge.
- Final regression also covers deleting derived knowledge: remove its provenance link, preserve
  the original source and draft, and retain past review snapshots. A loaded relationship cascade
  bug found during this check was fixed and verified in SQLite and PostgreSQL.

## Deployment result

- Live revision: `20260926_0006`; backend/frontend/gateway healthy. Existing RSSHub, Crawl4AI,
  PostgreSQL and unrelated VPS services were left running.
- Full pre-release backup: `backups/pre-review-20260926-140506.{tgz,sql.gz}` with matching old
  backend/frontend image tags. Final backend fix has the additional
  `backups/pre-backend-20260926-141223.{tgz,sql.gz}` and backend image tag.
- Public `/sources` and `/review` return 401 without login, as intended; `/healthz` returns 200.
  `check-live-review.cjs` exercised production UI/API read-only over localhost SSH forwards:
  dashboard, draft, existing knowledge detail and review in 1440px light / 320px dark. Eight
  checks passed; no approval, edits or model calls are performed by that script.
- One explicit real-model smoke used existing public source #86 (387-character RSS excerpt)
  and topic #3. It created draft #1 using `gpt-5.6-luna`, with four questions. The draft and
  source remain pending human review; existing six knowledge points were not altered. Model
  credentials remain server-side. No private diary text was used for this smoke.

## Deployment and recovery

`deploy/review-release.sh BUNDLE` is scoped to `/srv/projects/knowledge-review-system`.
Before replacing code it saves `backups/pre-review-TIMESTAMP.tgz`, a compressed PostgreSQL dump,
and `knowledge-review-{backend,frontend}:pre-review-TIMESTAMP` image tags. The bundle must not
contain `.env`, `.htpasswd`, caches, node_modules, local virtualenvs or QA databases. Secret files
remain in place. Ingestion services and PostgreSQL are not restarted.

After build and disposable-PostgreSQL verification, apply migration `20260926_0006`, recreate
backend/frontend/gateway in order and verify health plus authenticated routes. The migration is
additive, so the previous app images can run with it still present.

For an application rollback, first preserve any new writes, restore the saved source bundle and
retag the two saved images to `knowledge-review-backend:latest` and
`knowledge-review-frontend:latest`. Recreate only backend/frontend/gateway with `--no-deps`
and **without `--build`**. Do not downgrade the database as part of this app-only rollback.
Database restore/downgrade would discard new review records and needs an explicit recovery
decision; retain the pre-release dump for that case.

The scheduler is single-user and based on self-assessment. It is not automatic answer grading.
Legacy knowledge without questions will not appear in the review queue until questions are
added manually or an AI draft is reviewed and approved.
