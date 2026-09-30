#!/usr/bin/env bash
# Frontend-only release. Existing backend, PostgreSQL, RSSHub and Crawl4AI containers stay running.
set -Eeuo pipefail
umask 077
readonly PROJECT_DIR=/srv/projects/knowledge-review-system
readonly BUNDLE_PATH="${1:?Supply frontend bundle}"
readonly STAMP="$(date +%Y%m%d-%H%M%S)"
readonly COMPOSE=(docker compose -p knowledge-review -f docker-compose.prod.yml)
test "$(readlink -f "$PROJECT_DIR")" = "$PROJECT_DIR"
test -s "$BUNDLE_PATH"
cd "$PROJECT_DIR"
test -f .env
test -f deploy/.htpasswd
mkdir -p backups

echo "Backing up frontend source and image: $STAMP"
tar --exclude='frontend/node_modules' --exclude='frontend/.next' --exclude='frontend/.env*' \
  -czf "backups/pre-frontend-$STAMP.tgz" frontend
docker image tag knowledge-review-frontend "knowledge-review-frontend:pre-frontend-$STAMP"

echo "Building frontend only"
tar -xzf "$BUNDLE_PATH" -C "$PROJECT_DIR"
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build frontend
"${COMPOSE[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 frontend
"${COMPOSE[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 gateway
"${COMPOSE[@]}" exec -T frontend node -e 'fetch("http://127.0.0.1:3000/sources").then(r => { if (r.status !== 200) process.exit(1); console.log("OK /sources", r.status) }).catch(() => process.exit(1))' < /dev/null
curl -fsS http://127.0.0.1:3100/healthz
echo "Frontend release complete; rollback marker: pre-frontend-$STAMP"
"${COMPOSE[@]}" ps
