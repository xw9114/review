#!/usr/bin/env bash
# Scheduled, unattended PostgreSQL backup. Intended to run from cron, independent of any
# release. Does not touch application containers or release-time rollback backups
# (backups/pre-*.{tgz,sql.gz}), which stay under their own retention decided at release time.
set -Eeuo pipefail
umask 077
readonly PROJECT_DIR=/srv/projects/knowledge-review-system
readonly STAMP="$(date +%Y%m%d-%H%M%S)"
readonly COMPOSE=(docker compose -p knowledge-review -f docker-compose.prod.yml)
readonly RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

test "$(readlink -f "$PROJECT_DIR")" = "$PROJECT_DIR"
cd "$PROJECT_DIR"
mkdir -p backups

log "dumping database"
readonly DUMP_PATH="backups/daily-$STAMP.sql.gz"
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl' \
  | gzip > "$DUMP_PATH"
gzip -t "$DUMP_PATH"
log "wrote $DUMP_PATH ($(du -h "$DUMP_PATH" | cut -f1))"

log "pruning daily backups older than $RETENTION_DAYS days"
find backups -maxdepth 1 -name 'daily-*.sql.gz' -mtime "+$RETENTION_DAYS" -print -delete

log "backup complete"
