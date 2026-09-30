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

## Notifications (OpenClaw) — implemented

Phase 6's notification goal — a daily "you have N knowledge points due" digest — is live via
OpenClaw, running on a **separate VPS** ("friend-vps", not the one hosting this app) that the
account owner already uses as their personal chat-channel gateway (Feishu and WeChat both
connected there; run under `supervisord` as `openclaw-gateway`, profile home
`/opt/openclaw-home`).

**Integration shape**: OpenClaw polls this app, not the other way around. No code in this
repository calls out to OpenClaw — `GET /api/v1/reviews/overview` (public over HTTPS, gated only
by the gateway's Basic Auth) is the only integration surface, and it already returns `due_count`.
This keeps the "no model call while practicing" boundary intact and needed zero backend changes.

**What's deployed, on friend-vps**:
- A dedicated Basic Auth credential (`kr-digest`, its own line in this app's
  `deploy/.htpasswd` — separate from the interactive `xw` login so it can be rotated or revoked
  independently; the plaintext password lives only in the script below and is not committed to
  this repo).
- `/opt/openclaw-home/.openclaw/scripts/kr-due-digest.sh` (root-only, `chmod 700`): curls
  `https://review.xw9114.online/api/v1/reviews/overview` with that credential, extracts
  `due_count` via `python3 -c 'import json,sys; print(json.load(sys.stdin)["due_count"])'`, and
  echoes a digest line only when `due_count > 0` — deterministic, no model call, matches the L1–L5
  scheduler's own "transparent rules" philosophy.
- An OpenClaw automation (a **command** job, not an agent job — same reasoning) registered with:
  ```
  openclaw cron add kr-due-digest \
    --command '/opt/openclaw-home/.openclaw/scripts/kr-due-digest.sh' \
    --cron "0 9 * * *" --tz Asia/Shanghai \
    --channel feishu --to ou_0928f840a5f26a2283329e6de858b158 \
    --announce --best-effort-deliver
  ```
  Automation id `f17e6ccb-004c-49e5-9e47-6b4e870837de`. Verified end to end on 2026-09-30 with
  `openclaw cron run <id>` — the digest message was actually delivered to Feishu
  (`deliveryStatus: "delivered"`) — then enabled; next run is the following 09:00 Asia/Shanghai.

**Operating it**: `HOME=/opt/openclaw-home /opt/openclaw/bin/openclaw cron runs f17e6ccb-004c-49e5-9e47-6b4e870837de`
shows run history; `cron get`/`cron run`/`cron disable` need the automation's UUID, not its
friendly name (a CLI quirk — `cron list --all` prints both). To switch delivery to WeChat instead
of Feishu, `cron edit` the same job with `--channel wechat --to <peer id>` (look up the id with
`openclaw directory peers list --channel wechat`). To rotate the `kr-digest` credential: generate a
new password, `openssl passwd -apr1 '<new password>'`, replace its line in this app's
`deploy/.htpasswd` on the review-system VPS, and update the embedded password in
`kr-due-digest.sh` on friend-vps to match — the two must always agree since nginx re-reads the
htpasswd file on every request with no separate reload step.
