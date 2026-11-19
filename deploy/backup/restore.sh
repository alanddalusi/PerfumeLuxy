#!/usr/bin/env bash
# Restore a backup directory produced by backup.sh.
#
#   ./backup/restore.sh --verify <backup-dir>
#       Checks the checksums and restores the dump into a throwaway database
#       (perfumeria_restore_check) inside the db container, then drops it.
#       Production data is not touched. Run it after every new backup policy and monthly.
#
#   ./backup/restore.sh --replace-production <backup-dir>
#       Stops web (and the bundled proxy, never a shared one), replaces the production database and media volumes with the backup,
#       and starts web again. Take a fresh backup first; this cannot be undone.
set -euo pipefail

mode="${1:-}"
source_dir="${2:-}"
[ -n "$mode" ] && [ -d "$source_dir" ] || { sed -n '2,13p' "$0"; exit 2; }
# Resolve before changing directory so relative backup paths keep working.
source_dir="$(cd "$source_dir" && pwd)"

cd "$(dirname "$0")/.."
# Override for the isolated smoke test; production uses deploy/.env.production.
ENV_FILE="${PERFUMERIA_ENV_FILE:-.env.production}"
[ -f "$ENV_FILE" ] || { echo "Missing env file $ENV_FILE" >&2; exit 1; }
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

(cd "$source_dir" && sha256sum --check --quiet SHA256SUMS)
echo "Checksums verified."

case "$mode" in
  --verify)
    compose exec -T "$DB" sh -c 'dropdb --if-exists -U "$POSTGRES_USER" perfumeria_restore_check && createdb -U "$POSTGRES_USER" perfumeria_restore_check'
    compose exec -T "$DB" sh -c 'pg_restore --no-owner --no-privileges --exit-on-error -U "$POSTGRES_USER" -d perfumeria_restore_check' < "$source_dir/db.dump"
    compose exec -T "$DB" sh -c 'psql -U "$POSTGRES_USER" -d perfumeria_restore_check -tAc "select '"'"'products'"'"', count(*) from products_product union all select '"'"'migrations'"'"', count(*) from django_migrations"'
    compose exec -T "$DB" sh -c 'dropdb -U "$POSTGRES_USER" perfumeria_restore_check'
    tar -tzf "$source_dir/media.tar.gz" > /dev/null
    tar -tzf "$source_dir/catalog_assets.tar.gz" > /dev/null
    echo "Restore check passed. Production was not modified."
    ;;
  --replace-production)
    read -r -p "Type the site domain to replace PRODUCTION data from $source_dir: " answer
    expected="$(grep -E '^SITE_DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
    [ "$answer" = "$expected" ] || { echo "Aborted." >&2; exit 1; }
    compose stop "$WEB" $PROXY
    compose exec -T "$DB" sh -c 'pg_restore --clean --if-exists --no-owner --no-privileges --single-transaction --exit-on-error -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$source_dir/db.dump"
    compose run --rm --no-deps -T --entrypoint sh "$WEB" -c 'find /app/media -mindepth 1 -delete && tar -C /app -xzf -' < "$source_dir/media.tar.gz"
    compose run --rm --no-deps -T --entrypoint sh "$WEB" -c 'find /srv/catalog_assets -mindepth 1 -delete && tar -C /srv -xzf -' < "$source_dir/catalog_assets.tar.gz"
    compose up -d "$WEB" $PROXY
    echo "Production restored from $source_dir. Check /healthz/ through Caddy and the admin."
    ;;
  *)
    sed -n '2,13p' "$0"; exit 2 ;;
esac
