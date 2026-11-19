#!/usr/bin/env bash
# Read-only: build "current forum Caddyfile + perfumeria block" in a temporary file and
# validate it with the forum's own Caddy image in a throwaway, network-less container.
# The forum's Caddyfile and running proxy are not modified.
#
#   cd deploy && ./shared/caddy-check.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

inside="$(caddy_config_path)"
host_file="$(caddy_config_host_path "$inside")" || { echo "Caddyfile is not on a bind mount." >&2; exit 1; }
[ -r "$host_file" ] || { echo "Cannot read $host_file (run with sudo)." >&2; exit 1; }

work="$(mktemp -d)"; chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT
cp -- "$host_file" "$work/current.Caddyfile"

echo "== 1/2 Current forum configuration (baseline, must already be valid)"
validate_candidate "$work/current.Caddyfile"

echo "== 2/2 Forum configuration + perfumeria block"
if grep -qF "$BEGIN_MARK" "$work/current.Caddyfile"; then
    echo "Block already present; validating the file as it is."
    cp -- "$work/current.Caddyfile" "$work/candidate.Caddyfile"
else
    { cat -- "$work/current.Caddyfile"; printf '\n'; cat -- "$BLOCK_FILE"; } > "$work/candidate.Caddyfile"
fi
validate_candidate "$work/candidate.Caddyfile"
echo "Candidate is valid. Forum Caddyfile unchanged: $host_file"
