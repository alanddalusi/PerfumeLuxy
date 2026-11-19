#!/usr/bin/env bash
# REQUIRES AUTHORIZATION. Appends the perfumeria site block to the forum's Caddyfile
# and reloads Caddy gracefully (no container restart). Forum site blocks are left as
# they are; only the delimited block is added.
#
#   cd deploy && FORO_URLS="https://<foro-domain>/" ./shared/caddy-apply.sh
#
# Safety: DNS must point here, a timestamped copy of the Caddyfile is saved first, the
# candidate is validated in a throwaway container, the file is appended in place (same
# inode, so the container's bind mount sees it), and if validation or reload fails the
# original content is written back. Forum URLs in FORO_URLS must answer with the same
# HTTP status before and after.
set -euo pipefail
source "$(dirname "$0")/lib.sh"

[ -n "${FORO_URLS:-}" ] || { echo "Set FORO_URLS to one or more forum URLs to compare before/after." >&2; exit 1; }
# REQUIRE_DNS=0 is only for the rehearsal VM, where the real domain cannot point to the host.
REQUIRE_DNS="${REQUIRE_DNS:-1}" "$SHARED_DIR/preflight.sh" >/dev/null \
    || { echo "Preflight failed. Run: REQUIRE_DNS=${REQUIRE_DNS:-1} ./shared/preflight.sh" >&2; exit 1; }

inside="$(caddy_config_path)"
host_file="$(caddy_config_host_path "$inside")"
if grep -qF "$BEGIN_MARK" "$host_file"; then echo "Block already present; nothing to do."; exit 0; fi

backups="$CADDY_BACKUP_DIR"
mkdir -p "$backups"; chmod 700 "$backups"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$backups/Caddyfile.$stamp"
cp -p -- "$host_file" "$backup"
sha256sum "$backup" > "$backup.sha256"
echo "Saved copy: $backup"

work="$(mktemp -d)"; chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT
{ cat -- "$backup"; printf '\n'; cat -- "$BLOCK_FILE"; } > "$work/candidate.Caddyfile"
validate_candidate "$work/candidate.Caddyfile" >/dev/null

# FORO_CURL_OPTS: extra curl options (--resolve/-k in the rehearsal); empty in production.
statuses() { for url in $FORO_URLS; do printf '%s %s\n' "$url" "$(curl -s ${FORO_CURL_OPTS:-} -o /dev/null --max-time 15 -w '%{http_code}' "$url")"; done; }
before="$(statuses)"
echo "Forum before:"; printf '  %s\n' "$before"

restore() {
    echo "Restoring the original Caddyfile content." >&2
    cat -- "$backup" > "$host_file"     # same inode
}

{ printf '\n'; cat -- "$BLOCK_FILE"; } >> "$host_file"
if ! docker exec "$CADDY" grep -qF "$BEGIN_MARK" "$inside"; then
    echo "The container does not see the change (bind mount points to another inode)." >&2
    restore; exit 1
fi
if ! docker exec "$CADDY" caddy validate --config "$inside" --adapter caddyfile >/dev/null; then
    restore; exit 1
fi
if ! docker exec "$CADDY" caddy reload --config "$inside" --adapter caddyfile; then
    echo "Reload rejected; Caddy keeps running the previous configuration." >&2
    restore; exit 1
fi

sleep 5
after="$(statuses)"
echo "Forum after:"; printf '  %s\n' "$after"
if [ "$before" != "$after" ]; then
    echo "Forum responses changed. Rolling back now." >&2
    restore
    docker exec "$CADDY" caddy reload --config "$inside" --adapter caddyfile
    exit 1
fi
echo "Perfumeria block active. Certificate issuance for $DOMAIN starts now (see: docker logs --since 5m $CADDY)."
echo "Rollback: ./shared/caddy-rollback.sh"
