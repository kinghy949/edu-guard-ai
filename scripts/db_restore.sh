#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "usage: scripts/db_restore.sh <backup-file.dump>" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
BACKUP_FILE="$1"

if [ -n "${DOCKER_COMPOSE_CMD:-}" ]; then
  read -r -a COMPOSE <<< "$DOCKER_COMPOSE_CMD"
elif docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "docker compose or docker-compose is required" >&2
  exit 127
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "backup file not found: $BACKUP_FILE" >&2
  exit 2
fi

cat "$BACKUP_FILE" | "${COMPOSE[@]}" -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" sh -c '
  pg_restore --clean --if-exists --no-owner --no-privileges \
    -U "${POSTGRES_USER:-eduguard}" -d "${POSTGRES_DB:-eduguard}"
'

echo "restore completed: $BACKUP_FILE"
