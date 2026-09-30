# Frontend-only release contract

## 1. Scope / trigger

Use `deploy/frontend-refresh.sh BUNDLE` when a verified change touches only `frontend/` and frontend code-spec/docs. The remote project is fixed at `/srv/projects/knowledge-review-system`. It preserves the running backend, PostgreSQL, RSSHub and Crawl4AI containers.

## 2. Signature

Run on the VPS from the project directory:

```bash
bash deploy/frontend-refresh.sh /absolute/path/to/frontend-bundle.tgz
```

The bundle contains `frontend/src`, `frontend/public`, package manifests and frontend build configuration, plus the deploy script and updated docs/spec. It must exclude `.env*`, `.htpasswd`, `node_modules`, `.next`, virtualenvs and QA databases.

## 3. Contracts

- Requires the exact resolved project directory, a nonempty bundle, existing project `.env` and `deploy/.htpasswd`.
- Backs up frontend source excluding build cache and local environment files to `backups/pre-frontend-TIMESTAMP.tgz`; tags the old image `knowledge-review-frontend:pre-frontend-TIMESTAMP` before extraction.
- Runs `docker compose ... config --quiet`, builds only `frontend`, then recreates `frontend` and `gateway` with `--no-deps --wait`. It does not run a database migration.
- Checks `/sources` inside the new frontend container and `/healthz` on the host gateway. Gateway Basic Auth still guards public app pages.
- The frontend `docker compose exec -T` check redirects stdin from `/dev/null`; this matters when the helper itself is streamed over SSH, otherwise `exec` consumes the remaining script and skips gateway checks.

## 4. Validation / error matrix

| Condition | Behavior |
| --- | --- |
| Missing or empty bundle / wrong project path / missing auth files | Exit before backup or deployment. |
| Build or container health check fails | Exit nonzero; keep rollback source archive and image tag. Inspect Compose health before recovery. |
| Frontend renders but API is unhealthy | Frontend smoke alone is insufficient; run read-only live UI/API check. |
| User data changes independently during release | Re-read before/after counts and draft status; do not infer the frontend changed them. |

## 5. Good / base / bad

Good: new `/sources` UI works, frontend/gateway healthy, and all source/knowledge/draft counts unchanged. Base: old data is still read through existing typed APIs. Bad: restarting ingestion or applying a schema migration for a frontend-only release.

## 6. Tests required

- Local: `npm run lint`, `npx tsc --noEmit`, `npm run build`, `node docs/visual-qa/check-workspace-structure.cjs`, `check-sources.cjs`, `check-source-content.cjs`.
- VPS: `docker compose ... ps`, frontend `/sources` HTTP 200, gateway `/healthz` HTTP 200, public app page HTTP 401 without Basic Auth, read-only status before and after, and `check-live-review.cjs` through localhost SSH forwards.
- All production browser smoke requests except `GET`/`HEAD`/`OPTIONS` are blocked; the smoke script must not generate, approve, edit, ignore, sync, or score.

## 7. Wrong vs correct

Wrong: `docker compose up -d --build` without selecting services, which can rebuild/restart backend and ingestion components. Also wrong: let `compose exec` inherit the stdin of a piped release script.

Correct: `bash deploy/frontend-refresh.sh BUNDLE` after preparing a frontend-only archive and validating its file list; its health command uses `< /dev/null`.
