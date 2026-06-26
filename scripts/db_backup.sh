#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.prod.yml}"
DB_SERVICE="${DB_SERVICE:-db}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
BACKUP_KEEP="${BACKUP_KEEP:-14}"

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

mkdir -p "$BACKUP_DIR"

timestamp="$(date +%Y%m%d_%H%M)"
output="$BACKUP_DIR/eduguard_${timestamp}.dump"

"${COMPOSE[@]}" -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" sh -c '
  pg_dump -U "${POSTGRES_USER:-eduguard}" -d "${POSTGRES_DB:-eduguard}" -Fc
' > "$output"

count=0
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'eduguard_*.dump' | sort -r | while IFS= read -r file; do
  count=$((count + 1))
  if [ "$count" -gt "$BACKUP_KEEP" ]; then
    rm -f "$file"
  fi
done

echo "backup created: $output"
