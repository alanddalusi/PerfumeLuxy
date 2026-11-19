#!/usr/bin/env bash
# Nightly backup of PostgreSQL and the private media volumes. Run on the VPS from cron:
#   15 3 * * * cd /srv/perfumeria/app/deploy && ./backup/backup.sh >> /var/log/perfumeria-backup.log 2>&1
# Produces, per run, a directory readable only by its owner:
#   db.dump (pg_dump custom format), media.tar.gz, catalog_assets.tar.gz, SHA256SUMS
set -euo pipefail
umask 077

cd "$(dirname "$0")/.."
# Override for the isolated smoke test; production uses deploy/.env.production.
ENV_FILE="${PERFUMERIA_ENV_FILE:-.env.production}"
[ -f "$ENV_FILE" ] || { echo "Missing deploy/$ENV_FILE" >&2; exit 1; }
# Stack layout comes from the env file: standalone (deploy/compose.yaml, services web/db,
# bundled caddy) or shared VPS (deploy/shared/compose.yaml, perfumeria-web/perfumeria-db,
# PROXY_SERVICE empty so the other project's Caddy is never touched).
setting() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true; }
for name in COMPOSE_FILE COMPOSE_PROJECT_NAME; do
    value="$(setting "$name")"
    if [ -n "$value" ]; then export "$name=$value"; fi
done
WEB="$(setting WEB_SERVICE)"; WEB="${WEB:-web}"
DB="$(setting DB_SERVICE)"; DB="${DB:-db}"
if grep -qE '^PROXY_SERVICE=' "$ENV_FILE"; then PROXY="$(setting PROXY_SERVICE)"; else PROXY=caddy; fi
compose() { docker compose --env-file "$ENV_FILE" "$@"; }
BACKUP_DIR="$(setting BACKUP_DIR)"; BACKUP_DIR="${BACKUP_DIR:-/srv/perfumeria/backups}"
KEEP_DAYS="$(setting BACKUP_KEEP_DAYS)"; KEEP_DAYS="${KEEP_DAYS:-14}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/$stamp"
mkdir -p "$target"
chmod 700 "$BACKUP_DIR" "$target"

# Consistent logical dump; credentials stay inside the db container.
compose exec -T "$DB" sh -c 'pg_dump --format=custom --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$target/db.dump"
compose exec -T "$WEB" tar -C /app -czf - media > "$target/media.tar.gz"
compose exec -T "$WEB" tar -C /srv -czf - catalog_assets > "$target/catalog_assets.tar.gz"

# A dump that pg_restore cannot list is not a backup.
compose exec -T "$DB" pg_restore --list < "$target/db.dump" > /dev/null
(cd "$target" && sha256sum db.dump media.tar.gz catalog_assets.tar.gz > SHA256SUMS)
chmod 600 "$target"/*

# Retention: delete only timestamped run directories older than KEEP_DAYS.
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*Z' -mtime +"$KEEP_DAYS" -print -exec rm -r -- {} +

echo "Backup completed: $target"
