# Deployment runbook

This is the general, ongoing reference for running Knowledge Review System on the VPS. Individual
past releases have their own dated notes (`docs/review-release.md`, `docs/source-content-release.md`,
`docs/workspace-structure-release.md`); this file is the one to read before doing anything new.

## Topology

```text
Browser
  -> Cloudflare edge (TLS termination)
  -> cloudflared tunnel (host-level, shared across several projects on this VPS)
  -> 127.0.0.1:3100 -> gateway (nginx, Basic Auth, this project's docker-compose.prod.yml)
       -> backend  (FastAPI, not published to the host)
       -> frontend (Next.js, not published to the host)
  -> postgres (not published to the host)
  -> rsshub / crawl4ai (optional `ingestion` profile, internal-only)
```

- **Reverse proxy and TLS are already handled outside this repo.** `review.xw9114.online` is one
  entry in the host's shared `/etc/cloudflared/config.yml` (also routes `notes`, `status`,
  `tx-claw`, `control` for other projects on the same VPS). TLS is terminated at Cloudflare's
  edge; the `gateway` container only needs to answer plain HTTP on `127.0.0.1:3100`. Do not add a
  second TLS layer or a public port binding for this project — editing the shared cloudflared
  config affects other projects and should be a deliberate, separate change.
- The `gateway` container's Basic Auth (`deploy/.htpasswd`) is the only auth in front of the app.
  It protects `/` and `/api/`; only `/healthz` is exempt (used by health checks and monitoring).
- `postgres`, `backend`, and `frontend` are never published to the host; only `gateway` is
  (bound to `127.0.0.1` only, so it is unreachable from the public internet directly — only via
  the tunnel).

## Releasing a change

1. Build a bundle from a verified working tree (tests passing, lint/tsc clean):
   ```bash
   tar --exclude=./.git --exclude='./.env*' --exclude='./deploy/.htpasswd*' \
       --exclude='*/node_modules' --exclude='*/.next' --exclude='*/.venv' \
       --exclude='*/__pycache__' --exclude='*/.pytest_cache' --exclude='*/.ruff_cache' \
       --exclude='*.sqlite3' \
       -czf bundle.tgz .
   ```
2. Copy it to the VPS and run the matching release script under `deploy/`:
   - `review-release.sh` / `analysis-release.sh` are full releases (backend + frontend + a new
     migration). Copy one as a template for the next feature release — same shape: backup, tag
     images, build, verify against a disposable database, migrate, recreate, smoke test.
   - `backend-refresh.sh` / `frontend-refresh.sh` are narrower, for a backend- or frontend-only
     patch that needs no new migration.
3. Every release script backs up **before** touching anything: a full source+config tarball, a
   `pg_dump`, and `docker image tag ... :pre-<name>-<timestamp>` markers for both images. It then
   builds the new images and runs `deploy/verify-postgres.py` against a disposable, throwaway
   database (`knowledge_review_verify_<random>`, dropped afterward) **before** touching the real
   database or recreating any container. If that verification fails, the script aborts under
   `set -Eeuo pipefail` and production is untouched.
4. `deploy/verify-postgres.py` is a growing regression suite, not a one-off script — when you add
   a feature with its own service-layer behavior, add a short block exercising it there (see the
   Phase 5 block for the pattern: create fixtures, call the service functions directly, assert,
   let the temporary database get dropped in the `finally`).
5. After a successful release, confirm the printed smoke-test URLs returned `OK` and
   `docker compose ... ps` shows every container `healthy`.

## Rollback

Application-only rollback (no data loss expected, migration stays applied since migrations here
are additive-only):
```bash
docker image tag knowledge-review-backend:pre-<name>-<timestamp> knowledge-review-backend:latest
docker image tag knowledge-review-frontend:pre-<name>-<timestamp> knowledge-review-frontend:latest
tar -xzf backups/pre-<name>-<timestamp>.tgz -C /srv/projects/knowledge-review-system
docker compose -p knowledge-review -f docker-compose.prod.yml up -d --no-deps --force-recreate backend frontend gateway
```
Do **not** pass `--build` (that would rebuild from the just-restored source instead of using the
saved image tag). Do not downgrade the database as part of an app-only rollback — that discards
any real rows written since the release. A database rollback is a separate, explicit decision;
restore from `backups/pre-<name>-<timestamp>.sql.gz` (or the nearest daily dump) only after
preserving any new writes you still want to keep.

## Backups

- **Automated**: `deploy/backup-postgres.sh` runs daily via cron (`17 3 * * *`, host is already
  Asia/Shanghai) as `flock -xn /tmp/kr-backup.lock -c '.../backup-postgres.sh >> /var/log/knowledge-review/backup.log 2>&1'`,
  independent of releases. It writes `backups/daily-<timestamp>.sql.gz`, verifies the gzip, and
  prunes daily dumps older than 14 days (`BACKUP_RETENTION_DAYS` env var overrides). It never
  touches the release-time `backups/pre-*` markers — those are rollback points tied to a specific
  release and are pruned manually if disk pressure ever requires it.
- **Restoring** a dump into a running `postgres` container:
  ```bash
  gunzip -c backups/daily-<timestamp>.sql.gz | docker compose -p knowledge-review -f docker-compose.prod.yml exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
  ```
  Restoring into the live database is destructive to anything written since the dump; take a
  fresh dump first if there is any chance you will want to go back.

## Observability

- Host-level monitoring (CPU/memory/disk/network/uptime) already runs via the existing Nezha
  dashboard (`status.xw9114.online`), shared across projects on this VPS. Add an HTTP(S) monitor
  there for `https://review.xw9114.online/healthz` (200, no auth required) to get uptime alerting
  for this app specifically — that is a two-minute task in Nezha's own UI, not something to
  duplicate with a second monitoring stack.
- Container-level health checks already exist in `docker-compose.prod.yml` for every service and
  gate each release's recreate step (`--wait --wait-timeout 120`).
- Backup failures are visible in `/var/log/knowledge-review/backup.log` and via cron's default
  mail-to-root on non-zero exit; check that log if a daily dump looks missing.

## Notifications (OpenClaw) — blocked on channel setup

Phase 6's original notification goal is a daily "you have N knowledge points due" digest,
delivered through OpenClaw (already running on this host as a systemd service, managing chat
channels and scheduled automations independently of this app).

**Current state**: `openclaw channels status` reports no chat channel is configured yet (Feishu
and WeCom are both installed as available channel plugins but not connected). Connecting one
needs an app/bot created in that platform's own admin console and its credentials entered via
`openclaw channels add --channel feishu` (or `wecom`) — this is a one-time, interactive, credential-
bearing step only the account owner should run directly on the host, not something to script or
paste into a chat transcript.

**Chosen integration shape** (decided 2026-09-30): OpenClaw polls this app, not the other way
around. No code in this repository calls out to OpenClaw — `GET /api/v1/reviews/overview` (already
public, `no auth` beyond the gateway's Basic Auth) is the only integration surface, and it already
returns `due_count`. This keeps the "no model call while practicing" boundary intact and needs zero
backend changes.

**Once a channel is connected**, register a deterministic command automation (not an agent job —
no model call needed for a threshold check) along these lines:
```bash
openclaw cron add "kr-due-digest" --cron "0 9 * * *" --tz Asia/Shanghai \
  --command 'n=$(curl -fsS -u "<gateway-user>:<gateway-pass>" http://127.0.0.1:3100/api/v1/reviews/overview | python3 -c "import json,sys;print(json.load(sys.stdin)[\"due_count\"])"); if [ "$n" -gt 0 ]; then echo "今日有 $n 个知识点待复习：https://review.xw9114.online/review"; fi' \
  --announce --channel feishu --to <feishu-target> --best-effort-deliver
```
Use a dedicated Basic Auth credential for this (add a second line to `deploy/.htpasswd` rather than
reusing the interactive login), so it can be rotated or revoked independently. Test with
`openclaw cron run kr-due-digest` before trusting the schedule, and check `openclaw cron runs` for
history once it is live.
