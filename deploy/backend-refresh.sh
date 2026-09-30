#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
readonly PROJECT_DIR=/srv/projects/knowledge-review-system
readonly BUNDLE_PATH="${1:?Supply backend patch bundle}"
readonly STAMP="$(date +%Y%m%d-%H%M%S)"
readonly COMPOSE=(docker compose -p knowledge-review -f docker-compose.prod.yml)
test "$(readlink -f "$PROJECT_DIR")" = "$PROJECT_DIR"
test -s "$BUNDLE_PATH"
cd "$PROJECT_DIR"
tar -czf "backups/pre-backend-$STAMP.tgz" backend/app deploy/verify-postgres.py
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl' \
  | gzip > "backups/pre-backend-$STAMP.sql.gz"
gzip -t "backups/pre-backend-$STAMP.sql.gz"
docker image tag knowledge-review-backend "knowledge-review-backend:pre-backend-$STAMP"
echo "Backend rollback marker: pre-backend-$STAMP"
tar -xzf "$BUNDLE_PATH" -C "$PROJECT_DIR"
"${COMPOSE[@]}" build backend
"${COMPOSE[@]}" run --rm --no-deps -T backend python - < deploy/verify-postgres.py
"${COMPOSE[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 backend
"${COMPOSE[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 gateway
"${COMPOSE[@]}" exec -T backend python -c 'import httpx; c=httpx.Client(base_url="http://127.0.0.1:8000", timeout=10); [(c.get(p).raise_for_status(), print("OK", p)) for p in ["/health", "/api/v1/knowledge-drafts", "/api/v1/reviews/overview"]]'
echo "Backend refresh complete"
