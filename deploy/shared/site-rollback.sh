#!/usr/bin/env bash
# REQUIRES AUTHORIZATION in production. Rolls back this project's site in the shared Caddy.
#
#   sudo -E FORO_URLS="https://foroiaaldia.com/" ./shared/site-rollback.sh            # previous version
#   sudo -E FORO_URLS="https://foroiaaldia.com/" ./shared/site-rollback.sh --remove   # take the site offline
#
# The current file is saved first; the target state is validated in a throwaway container;
# Caddy is reloaded gracefully; other sites must answer the same. On any failure the saved
# current file is put back and Caddy reloaded again. Only this project's file is touched.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

mode="${1:-previous}"
case "$mode" in previous|--previous) mode=previous ;; --remove) mode=remove ;; *) sed -n '2,9p' "$0"; exit 2 ;; esac
[ "$(id -u)" = 0 ] || { echo "Run with sudo." >&2; exit 2; }
guard_target
[ -n "${FORO_URLS:-}" ] || { echo "Set FORO_URLS (other sites to compare before/after)." >&2; exit 2; }
fail_at() { [ "${SITE_TEST_MODE:-0}" = 1 ] && [ "${SITE_TEST_FAIL_AT:-}" = "$1" ]; }

exec 9>"$LOCK_FILE"
flock -w 60 9 || { echo "Another site deployment holds $LOCK_FILE." >&2; exit 2; }
shared_proxy_ready >/dev/null || { echo "Shared proxy not prepared; nothing to roll back here." >&2; exit 1; }

target=""
if [ "$mode" = previous ]; then
    # Newest saved version that differs from the active file (failed deployments also leave
    # copies of the active file behind; those are not a "previous version").
    current_sha="$( { [ -f "$SITE_FILE" ] && sha256sum < "$SITE_FILE" | cut -d' ' -f1; } || true )"
    target=""
    while IFS= read -r candidate; do
        [ "$(sha256sum < "$candidate" | cut -d' ' -f1)" != "$current_sha" ] && { target="$candidate"; break; }
    done < <(find "$CADDY_BACKUP_DIR" -maxdepth 1 -type f -name "site-$DOMAIN-2*.caddy" 2>/dev/null | sort -r)
    if [ -z "$target" ]; then
        echo "No previous version saved; use --remove to take the site offline." >&2; exit 1
    fi
    (cd "$(dirname "$target")" && sha256sum --check --quiet "$(basename "$target").sha256") \
        || { echo "Checksum mismatch for $target" >&2; exit 1; }
    echo "Target: previous version $target"
else
    echo "Target: remove $SITE_FILE"
fi

umask 077
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$CADDY_BACKUP_DIR"; chmod 700 "$CADDY_BACKUP_DIR"
saved=""
if [ -f "$SITE_FILE" ]; then
    saved="$CADDY_BACKUP_DIR/before-rollback-$DOMAIN-$stamp.caddy"
    cp -p -- "$SITE_FILE" "$saved"; sha256sum "$saved" > "$saved.sha256"
    echo "Current site file saved: $saved"
elif [ "$mode" = remove ]; then
    echo "Site file not present; nothing to remove."; exit 0
fi

echo "== Validate the target state (throwaway container)"
validate_site_candidate "$target" || { echo "Target state rejected; nothing changed." >&2; exit 1; }

before="$(forum_statuses)"
put_back() {
    echo "Putting the saved site file back." >&2
    if [ -n "$saved" ]; then cp -p -- "$saved" "$SITE_FILE.restore" && mv -f -- "$SITE_FILE.restore" "$SITE_FILE"; else rm -f -- "$SITE_FILE"; fi
    caddy_reload >/dev/null 2>&1 || echo "WARNING: reload after put-back failed; check $CADDY now." >&2
}

umask 022
if [ -n "$target" ]; then
    cp -- "$target" "$SITE_STAGED" && chmod 644 "$SITE_STAGED" && mv -f -- "$SITE_STAGED" "$SITE_FILE"
else
    rm -f -- "$SITE_FILE"
fi
if fail_at reload || ! caddy_reload; then echo "Reload rejected." >&2; put_back; exit 1; fi

sleep "${SETTLE_SECONDS:-3}"
after="$(forum_statuses)"
if [ "$before" != "$after" ] || fail_at compare; then echo "Other sites answer differently." >&2; put_back; exit 1; fi
if [ -n "$target" ]; then
    served_hosts | grep -qxF "$DOMAIN" || { echo "$DOMAIN missing after restore." >&2; put_back; exit 1; }
    echo "PASS  previous version active (sha256 $(sha256sum < "$SITE_FILE" | cut -c1-16))."
else
    served_hosts | grep -qxF "$DOMAIN" && { echo "$DOMAIN still served after removal." >&2; put_back; exit 1; }
    echo "PASS  $DOMAIN removed from the shared Caddy; other sites unchanged."
fi
