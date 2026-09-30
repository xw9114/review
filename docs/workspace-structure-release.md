# Workspace structure release / 2026-09-27

## Scope

The six existing routes are grouped by work stage. The source inbox has a bounded searchable queue, source-provider filter, deep-link selection, distinct failed-read/retry state, and a primary AI draft workflow with expandable manual acceptance. Manual edits are protected before they are discarded. No backend API, migration, category or topic data changed.

`AppShell` now reads one route configuration for sidebar, breadcrumb and active-link semantics. Inbox state/network orchestration lives in `use-source-workspace.ts`; queue, relevance and action panes are separate components. Source Markdown, supplementation, draft review and human approval stay on their existing APIs.

## Local verification

- `npm run lint`, `npx tsc --noEmit`, `npm run build`: passed. All eight Next routes built.
- Backend regression `pytest -q`: 68 passed, two existing dependency deprecation warnings.
- `check-workspace-structure.cjs`: 16 checks passed with a 107-item intercepted fixture, including filters, no hidden actions, deep-link reload, unsaved guards, accepted conflict/retry, optional topic, disabled controls during generation, stale draft reuse and 1440/768/390/320px light/dark screenshots. No real model or database writes.
- `check-sources.cjs`: 4 layout/Markdown checks passed.
- `check-source-content.cjs`: 8 preview/apply/stale-draft/restore and narrow-screen checks passed in a disposable SQLite fixture with fake crawler/LLM.
- `check-interactions.cjs`: dashboard/knowledge/navigation regression passed on desktop, mobile and tablet.
- `check-review-loop.cjs`: 26 checks passed in a fresh disposable SQLite fixture with a fake LLM, covering generation, save/resume, explicit approval, question edits, answer reveal and rating, service failure, plus 1440/390/320px light/dark views.

The in-app browser connection was unavailable, so the repository's local Chromium browser checks were used. Screenshots are in `docs/visual-qa/workspace-structure/`.

## Deployment and production verification

Pre-release production read was 106 pending sources, 7 knowledge points (1 with questions), and draft #1 approved with generation_count=1. This reflects user activity since the previous release. Backend, frontend, gateway and PostgreSQL were healthy; VPS had about 1.3 GiB available memory and 19 GiB free disk.

Frontend-only deployment completed with rollback marker `pre-frontend-20260927-193515`: source archive `backups/pre-frontend-20260927-193515.tgz` and image tag `knowledge-review-frontend:pre-frontend-20260927-193515`. The new frontend built on the VPS; frontend and gateway are healthy. Container `/sources` returned 200, host `/healthz` returned 200, and unauthenticated public `/sources` returned 401.

`check-live-review.cjs` passed ten read-only dashboard/source/draft/knowledge/review views at 1440px light and 320px dark. It blocks every non-GET/HEAD/OPTIONS request, so it did not call a model or modify production data. After deployment, 106 pending sources, 7 knowledge points (1 with questions), and approved draft #1 with generation_count=1 matched the pre-release snapshot.

The first release invocation streamed the helper script through stdin; `docker compose exec` consumed the remaining input after its frontend check. The gateway and data checks were therefore run separately. The saved `deploy/frontend-refresh.sh` now redirects that command's stdin from `/dev/null`, allowing all final checks to execute on future runs.

The release helper backs up frontend source and tags the previous frontend image before building. It recreates frontend and gateway only. Production browser QA uses read-only GET requests through local SSH forwards; public app routes must still require Basic Auth.
