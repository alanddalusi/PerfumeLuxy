#!/usr/bin/env bash
# REQUIRES AUTHORIZATION (writes under CADDY_BACKUP_DIR, default /srv/perfumeria/caddy-backups).
# Verifiable copy of the forum's current Caddy configuration. The forum's files and the
# running proxy are only read; validation runs in a throwaway, network-less container.
#
#   cd deploy && sudo -E ./shared/caddy-backup.sh
#   ./shared/caddy-backup.sh --verify <dir>     # re-check an existing copy
#
# Each copy contains: the bind-mounted Caddyfile (or its whole directory), the running JSON
# configuration from the admin API, container metadata and SHA256SUMS. Mode 700/600: the
# configuration may contain credentials (for example DNS provider tokens).
set -euo pipefail
source "$(dirname "$0")/lib.sh"

verify() {
    local dir="$1"
    (cd "$dir" && sha256sum --check --quiet SHA256SUMS) && echo "Checksums OK: $dir"
    validate_candidate "$dir/Caddyfile" >/dev/null && echo "Caddyfile in the copy validates with $(cat "$dir/image.txt")"
}

if [ "${1:-}" = "--verify" ]; then
    [ -d "${2:-}" ] || { echo "usage: $0 --verify <dir>" >&2; exit 2; }
    verify "$(cd "$2" && pwd)"; exit 0
fi

umask 077
inside="$(caddy_config_path)"
host_file="$(caddy_config_host_path "$inside")" || { echo "Caddyfile is not on a bind mount." >&2; exit 1; }
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dir="$CADDY_BACKUP_DIR/config-$stamp"
mkdir -p "$dir"; chmod 700 "$CADDY_BACKUP_DIR" "$dir"

cp -p -- "$host_file" "$dir/Caddyfile"
mount_source="$(docker inspect -f '{{range .Mounts}}{{if eq .Type "bind"}}{{.Source}}|{{.Destination}}{{println}}{{end}}{{end}}' "$CADDY" \
    | awk -F'|' -v cfg="$inside" '$2 != cfg && index(cfg, $2 "/") == 1 {print $1; exit}')"
if [ -n "$mount_source" ]; then
    tar -C "$(dirname "$mount_source")" -czf "$dir/config-dir.tar.gz" "$(basename "$mount_source")"
fi
docker exec "$CADDY" wget -q -O - http://localhost:2019/config/ > "$dir/running-config.json" 2>/dev/null \
    || echo "admin API not readable; running-config.json skipped" > "$dir/running-config.unavailable"
docker inspect -f '{{.Config.Image}}' "$CADDY" > "$dir/image.txt"
docker inspect -f '{{.Image}}' "$CADDY" > "$dir/image-id.txt"
docker inspect -f '{{.Path}} {{join .Args " "}}' "$CADDY" > "$dir/command.txt"
docker inspect -f '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} rw={{.RW}}{{println}}{{end}}' "$CADDY" > "$dir/mounts.txt"
printf 'host_file=%s\ninside=%s\ninode=%s\ncontainer=%s\n' "$host_file" "$inside" "$(stat -c %i "$host_file")" "$CADDY" > "$dir/source.txt"
cat > "$dir/RESTORE.txt" <<EOF
Restore the forum Caddyfile exactly as it was at $stamp (keeps the inode seen by the container):
  sudo tee "$host_file" < "$dir/Caddyfile" > /dev/null
  docker exec $CADDY caddy validate --config $inside --adapter caddyfile
  docker exec $CADDY caddy reload --config $inside --adapter caddyfile      # graceful, no restart
EOF
(cd "$dir" && sha256sum -- * > SHA256SUMS)
chmod 600 "$dir"/*
verify "$dir"
echo "Copy stored in $dir"
