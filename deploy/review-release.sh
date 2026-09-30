#!/usr/bin/env bash
# Scoped release: keep the existing environment, ingestion services and unrelated apps intact.
set -Eeuo pipefail
umask 077
readonly PROJECT_DIR=/srv/projects/knowledge-review-system
readonly BUNDLE_PATH="${1:?Supply the application tar.gz bundle}"
readonly STAMP="$(date +%Y%m%d-%H%M%S)"
readonly COMPOSE=(docker compose -p knowledge-review -f docker-compose.prod.yml)
test "$(readlink -f "$PROJECT_DIR")" = "$PROJECT_DIR"
test -s "$BUNDLE_PATH"
cd "$PROJECT_DIR"
test -f .env
test -f deploy/.htpasswd
mkdir -p backups

echo "Backing up application, image tags and database: $STAMP"
tar --exclude=./backups --exclude='./.env*' --exclude='./deploy/.htpasswd*' --exclude=./.git \
    --exclude='*/node_modules' --exclude='*/.next' --exclude='*/.venv' \
    -czf "backups/pre-review-$STAMP.tgz" .
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl' \
  | gzip > "backups/pre-review-$STAMP.sql.gz"
gzip -t "backups/pre-review-$STAMP.sql.gz"
docker image tag knowledge-review-backend "knowledge-review-backend:pre-review-$STAMP"
docker image tag knowledge-review-frontend "knowledge-review-frontend:pre-review-$STAMP"

echo "Installing verified source and building images"
tar -xzf "$BUNDLE_PATH" -C "$PROJECT_DIR"
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build backend
"${COMPOSE[@]}" build frontend
echo "Checking new code against a disposable PostgreSQL database"
"${COMPOSE[@]}" run --rm --no-deps -T backend python - < deploy/verify-postgres.py

echo "Migrating application database and replacing application containers"
"${COMPOSE[@]}" run --rm --no-deps -T backend alembic upgrade head
"${COMPOSE[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 backend
"${COMPOSE[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 frontend
"${COMPOSE[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 gateway
"${COMPOSE[@]}" exec -T backend python -c 'import httpx; c=httpx.Client(base_url="http://127.0.0.1:8000", timeout=10); paths=["/health", "/api/v1/reviews/overview", "/api/v1/reviews/active", "/api/v1/knowledge-drafts", "/api/v1/knowledge-points", "/api/v1/source-documents?status=pending"]; [(c.get(p).raise_for_status(), print("OK", p)) for p in paths]'
curl -fsS http://127.0.0.1:3100/healthz
echo "Release complete; rollback marker: pre-review-$STAMP"
"${COMPOSE[@]}" ps
