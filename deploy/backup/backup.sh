#!/usr/bin/env bash
# Nightly backup of PostgreSQL and the private media volumes. Run on the VPS from cron:
#   15 3 * * * cd /srv/perfumeria/app/deploy && ./backup/backup.sh >> /var/log/perfumeria-backup.log 2>&1
# Produces, per run, a directory readable only by its owner:
#   db.dump (pg_dump custom format), media.tar.gz, catalog_assets.tar.gz, SHA256SUMS
set -euo pipefail
umask 077

cd "$(dirname "$0")/.."
ENV_FILE=".env.production"
[ -f "$ENV_FILE" ] || { echo "Missing deploy/$ENV_FILE" >&2; exit 1; }
BACKUP_DIR="$(grep -E '^BACKUP_DIR=' "$ENV_FILE" | cut -d= -f2- || true)"
BACKUP_DIR="${BACKUP_DIR:-/srv/perfumeria/backups}"
KEEP_DAYS="$(grep -E '^BACKUP_KEEP_DAYS=' "$ENV_FILE" | cut -d= -f2- || true)"
KEEP_DAYS="${KEEP_DAYS:-14}"
compose() { docker compose --env-file "$ENV_FILE" "$@"; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/$stamp"
mkdir -p "$target"
chmod 700 "$BACKUP_DIR" "$target"

# Consistent logical dump; credentials stay inside the db container.
compose exec -T db sh -c 'pg_dump --format=custom --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$target/db.dump"
compose exec -T web tar -C /app -czf - media > "$target/media.tar.gz"
compose exec -T web tar -C /srv -czf - catalog_assets > "$target/catalog_assets.tar.gz"

# A dump that pg_restore cannot list is not a backup.
compose exec -T db pg_restore --list < "$target/db.dump" > /dev/null
(cd "$target" && sha256sum db.dump media.tar.gz catalog_assets.tar.gz > SHA256SUMS)
chmod 600 "$target"/*

# Retention: delete only timestamped run directories older than KEEP_DAYS.
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*Z' -mtime +"$KEEP_DAYS" -print -exec rm -r -- {} +

echo "Backup completed: $target"
