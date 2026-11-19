#!/usr/bin/env bash
# REQUIRES AUTHORIZATION. Removes only the perfumeria block (between its markers) from the
# forum's Caddyfile and reloads Caddy gracefully. Any other change made to the file since
# the block was added is preserved. A copy of the current file is saved first.
#
#   cd deploy && ./shared/caddy-rollback.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

inside="$(caddy_config_path)"
host_file="$(caddy_config_host_path "$inside")"
grep -qF "$BEGIN_MARK" "$host_file" || { echo "No perfumeria block in $host_file; nothing to do."; exit 0; }
[ "$(grep -cF "$BEGIN_MARK" "$host_file")" = 1 ] && [ "$(grep -cF "$END_MARK" "$host_file")" = 1 ] \
    || { echo "Markers are not exactly one BEGIN and one END; fix by hand." >&2; exit 1; }

backups="/srv/perfumeria/caddy-backups"
mkdir -p "$backups"; chmod 700 "$backups"
backup="$backups/Caddyfile.before-rollback.$(date -u +%Y%m%dT%H%M%SZ)"
cp -p -- "$host_file" "$backup"

work="$(mktemp -d)"; chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT
# Drop the block and the single blank line caddy-apply.sh added in front of it.
awk -v begin="$BEGIN_MARK" -v end="$END_MARK" '
    index($0, begin) == 1 { skipping = 1; if (held && prev == "") held = 0; next }
    skipping { if (index($0, end) == 1) skipping = 0; next }
    { if (held) print prev; prev = $0; held = 1 }
    END { if (held) print prev }
' "$host_file" > "$work/stripped.Caddyfile"
grep -qF "$BEGIN_MARK" "$work/stripped.Caddyfile" && { echo "Block still present after filtering." >&2; exit 1; }
validate_candidate "$work/stripped.Caddyfile" >/dev/null

cat -- "$work/stripped.Caddyfile" > "$host_file"   # same inode
docker exec "$CADDY" caddy validate --config "$inside" --adapter caddyfile >/dev/null \
    || { echo "Validation failed; restoring the previous file." >&2; cat -- "$backup" > "$host_file"; exit 1; }
docker exec "$CADDY" caddy reload --config "$inside" --adapter caddyfile \
    || { echo "Reload rejected; restoring the previous file." >&2; cat -- "$backup" > "$host_file"; exit 1; }
echo "Perfumeria block removed and Caddy reloaded. Copy of the previous file: $backup"
