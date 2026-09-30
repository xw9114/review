#!/usr/bin/env bash
set -Eeuo pipefail

readonly PROJECT_DIR="/srv/projects/knowledge-review-system"
readonly BUNDLE_PATH="${1:-/tmp/knowledge-review-system.tgz}"
readonly COMPOSE=(docker compose -p knowledge-review -f docker-compose.prod.yml --profile ingestion)

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

wait_healthy() {
  local container="$1"
  local attempts="${2:-60}"
  local status
  for ((i = 1; i <= attempts; i++)); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
    if [[ "$status" == "healthy" || "$status" == "running" ]]; then
      log "$container is $status"
      return 0
    fi
    if [[ "$status" == "unhealthy" || "$status" == "exited" || "$status" == "dead" ]]; then
      log "$container entered terminal state: $status"
      docker logs --tail 80 "$container" || true
      return 1
    fi
    sleep 5
  done
  log "$container did not become healthy in time"
  docker logs --tail 80 "$container" || true
  return 1
}

append_env_if_missing() {
  local key="$1"
  local value="$2"
  if ! grep -q "^${key}=" .env; then
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

log "validating deployment inputs"
test "$(readlink -f "$PROJECT_DIR")" = "$PROJECT_DIR"
test -s "$BUNDLE_PATH"
test -f "$PROJECT_DIR/.env"
test -f "$PROJECT_DIR/deploy/.htpasswd"

log "installing application bundle"
tar -xzf "$BUNDLE_PATH" -C "$PROJECT_DIR"
cd "$PROJECT_DIR"

umask 077
append_env_if_missing RSSHUB_BASE_URL http://rsshub:1200
append_env_if_missing CRAWL4AI_API_URL http://crawl4ai:11235
if ! grep -q '^CRAWL4AI_API_TOKEN=' .env; then
  append_env_if_missing CRAWL4AI_API_TOKEN "$(openssl rand -hex 32)"
fi
append_env_if_missing CRAWL4AI_TIMEOUT_SECONDS 45
append_env_if_missing FEED_FETCH_TIMEOUT_SECONDS 15
append_env_if_missing FEED_MAX_BYTES 5242880
append_env_if_missing FEED_MAX_ITEMS 30
append_env_if_missing FEED_MAX_CRAWL_ITEMS 5
append_env_if_missing FEED_AUTO_CRAWL_THRESHOLD 280
chmod 600 .env deploy/.htpasswd

log "validating compose configuration"
"${COMPOSE[@]}" config --quiet

log "pulling ingestion images"
"${COMPOSE[@]}" pull rsshub crawl4ai

log "building backend and frontend"
"${COMPOSE[@]}" build backend frontend

log "running database migration"
"${COMPOSE[@]}" run --rm --no-deps backend alembic upgrade head

log "starting internal ingestion services"
"${COMPOSE[@]}" up -d --no-deps rsshub crawl4ai
wait_healthy knowledge-review-rsshub-1 36
wait_healthy knowledge-review-crawl4ai-1 60

log "recreating backend"
"${COMPOSE[@]}" up -d --no-deps --force-recreate backend
wait_healthy knowledge-review-backend-1 36

log "recreating frontend"
"${COMPOSE[@]}" up -d --no-deps --force-recreate frontend
wait_healthy knowledge-review-frontend-1 36

log "recreating gateway to refresh upstream addresses"
"${COMPOSE[@]}" up -d --no-deps --force-recreate gateway
wait_healthy knowledge-review-gateway-1 24

log "running internal smoke tests"
docker exec knowledge-review-backend-1 python -c "import json, urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).status == 200; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/feed-sources', timeout=5)); assert isinstance(data, list)"
docker exec knowledge-review-backend-1 python -c "import urllib.request; assert urllib.request.urlopen('http://rsshub:1200', timeout=10).status == 200"
docker exec knowledge-review-backend-1 python -c "import urllib.request; assert urllib.request.urlopen('http://crawl4ai:11235/health', timeout=10).status == 200"
curl -fsS http://127.0.0.1:3100/healthz >/dev/null

log "deployment completed"
"${COMPOSE[@]}" ps
free -h
df -h /
