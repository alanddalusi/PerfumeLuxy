#!/usr/bin/env bash
# REQUIRES AUTHORIZATION in production. Publishes this project's site file in the shared
# Caddy and reloads it gracefully. Never edits other projects' files or containers.
#
#   cd deploy && sudo -E FORO_URLS="https://foroiaaldia.com/ https://www.foroiaaldia.com/" ./shared/site-deploy.sh
#
# Steps: lock -> shared proxy prepared? -> DNS points here -> back up the active site file
# -> stage <domain>.caddy.new -> validate the whole configuration in a throwaway container
# -> atomic rename -> validate inside the proxy -> graceful reload -> other sites answer the
# same -> domain present in the running config. Any failure after the rename restores the
# previous state (previous file or no file) and reloads again.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

[ "$(id -u)" = 0 ] || { echo "Run with sudo (writes $SITES_DIR and talks to Docker)." >&2; exit 2; }
guard_target
[ -f "$SITE_SOURCE" ] || { echo "Missing site source $SITE_SOURCE" >&2; exit 2; }
[ -n "${FORO_URLS:-}" ] || { echo "Set FORO_URLS (other sites to compare before/after)." >&2; exit 2; }
fail_at() { [ "${SITE_TEST_MODE:-0}" = 1 ] && [ "${SITE_TEST_FAIL_AT:-}" = "$1" ]; }

exec 9>"$LOCK_FILE"
flock -w 60 9 || { echo "Another site deployment holds $LOCK_FILE." >&2; exit 2; }

echo "== Shared proxy"
shared_proxy_ready || { echo "Shared proxy not prepared: apply the one-time setup (ARQUITECTURA_CADDY_COMPARTIDO.md)." >&2; exit 1; }

if [ "${REQUIRE_DNS:-1}" = 1 ]; then   # REQUIRE_DNS=0 only in the sandbox test
    for name in "$DOMAIN" "www.$DOMAIN"; do
        dns_points_here "$name" || { echo "DNS for $name does not point to this host yet." >&2; exit 1; }
    done
    echo "PASS  DNS for $DOMAIN and www points here"
fi

new_sha="$(sha256sum < "$SITE_SOURCE" | cut -d' ' -f1)"
if [ -f "$SITE_FILE" ] && [ "$(sha256sum < "$SITE_FILE" | cut -d' ' -f1)" = "$new_sha" ] && served_hosts | grep -qxF "$DOMAIN"; then
    echo "Site file already active and identical (sha256 ${new_sha:0:16}); nothing to do."
    exit 0
fi

umask 077
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$CADDY_BACKUP_DIR"; chmod 700 "$CADDY_BACKUP_DIR"
backup=""
if [ -f "$SITE_FILE" ]; then
    backup="$CADDY_BACKUP_DIR/site-$DOMAIN-$stamp.caddy"
    cp -p -- "$SITE_FILE" "$backup"
    sha256sum "$backup" > "$backup.sha256"
    echo "Previous site file saved: $backup"
else
    echo "No previous site file (first deployment)."
fi
docker exec "$CADDY" wget -q -O - http://127.0.0.1:2019/config/ > "$CADDY_BACKUP_DIR/running-config-$stamp.json" 2>/dev/null || true
before_identity="$(proxy_identity)"

umask 022
cp -- "$SITE_SOURCE" "$SITE_STAGED"
chmod 644 "$SITE_STAGED"
trap 'rm -f -- "$SITE_STAGED"' EXIT

echo "== Validate the whole configuration with the candidate (throwaway container)"
if ! validate_site_candidate "$SITE_STAGED" || fail_at validate; then
    echo "Candidate rejected; nothing was activated." >&2
    exit 1
fi
echo "PASS  candidate valid"

before="$(forum_statuses)"
printf 'Other sites before: %s\n' "$(echo "$before" | tr '\n' ' ')"

restore() {
    echo "Restoring the previous state." >&2
    if [ -n "$backup" ]; then
        cp -p -- "$backup" "$SITE_FILE.restore" && mv -f -- "$SITE_FILE.restore" "$SITE_FILE"
    else
        rm -f -- "$SITE_FILE"
    fi
    caddy_reload >/dev/null 2>&1 || echo "WARNING: reload after restore failed; check $CADDY now." >&2
}

mv -f -- "$SITE_STAGED" "$SITE_FILE"            # atomic on the same filesystem
if ! docker exec "$CADDY" caddy validate --config "$(caddy_config_path)" --adapter caddyfile >/dev/null 2>&1 || fail_at live-validate; then
    echo "Validation inside the proxy failed." >&2; restore; exit 1
fi
if fail_at reload || ! caddy_reload; then
    echo "Reload rejected; Caddy keeps the previous configuration." >&2; restore; exit 1
fi

sleep "${SETTLE_SECONDS:-3}"
after="$(forum_statuses)"
printf 'Other sites after:  %s\n' "$(echo "$after" | tr '\n' ' ')"
if [ "$before" != "$after" ] || fail_at compare; then
    echo "Other sites answer differently after the reload." >&2; restore; exit 1
fi
if ! served_hosts | grep -qxF "$DOMAIN"; then
    echo "$DOMAIN is not in the running configuration." >&2; restore; exit 1
fi
[ "$(proxy_identity)" = "$before_identity" ] || echo "WARNING: the proxy container identity changed during the deployment." >&2

echo "PASS  $DOMAIN active (site sha256 ${new_sha:0:16}); proxy not restarted."
echo "Certificates are obtained automatically once DNS points here. Status: ./shared/site-status.sh"
echo "Rollback: sudo -E ./shared/site-rollback.sh"
