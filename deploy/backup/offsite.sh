#!/usr/bin/env bash
# Encrypt the newest local backup and copy it to an off-site remote.
#
#   ./backup/offsite.sh            # newest run directory under BACKUP_DIR
#   ./backup/offsite.sh <run-dir>  # a specific run
#
# Requirements on the VPS (installed by the operator, not by this script):
#   - age      https://age-encryption.org  (encryption to public keys)
#   - rclone   https://rclone.org          (remote configured as OFFSITE_REMOTE)
# Configuration in deploy/.env.production:
#   OFFSITE_RECIPIENTS=/srv/perfumeria/offsite-recipients.txt   # age public keys, one per line
#   OFFSITE_REMOTE=offsite:perfumeria-backups                    # rclone remote:path
#
# Only public keys live on the server, so a compromised VPS cannot decrypt old copies.
# Keep the matching private keys offline (password manager + paper copy), held by at
# least two named people. Decrypt with: age -d -i key.txt run.tar.age > run.tar
set -euo pipefail
umask 077

cd "$(dirname "$0")/.."
ENV_FILE="${PERFUMERIA_ENV_FILE:-.env.production}"
setting() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true; }

BACKUP_DIR="$(setting BACKUP_DIR)"; BACKUP_DIR="${BACKUP_DIR:-/srv/perfumeria/backups}"
RECIPIENTS="$(setting OFFSITE_RECIPIENTS)"
REMOTE="$(setting OFFSITE_REMOTE)"
[ -n "$RECIPIENTS" ] && [ -s "$RECIPIENTS" ] || { echo "Set OFFSITE_RECIPIENTS to a file of age public keys." >&2; exit 1; }
[ -n "$REMOTE" ] || { echo "Set OFFSITE_REMOTE (rclone remote:path)." >&2; exit 1; }
command -v age >/dev/null && command -v rclone >/dev/null || { echo "age and rclone are required." >&2; exit 1; }
if grep -qE 'AGE-SECRET-KEY' "$RECIPIENTS"; then
    echo "OFFSITE_RECIPIENTS contains a private key. Keep private keys off the server." >&2
    exit 1
fi

run="${1:-$(find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*Z' | sort | tail -n1)}"
[ -d "$run" ] || { echo "No backup run found." >&2; exit 1; }
(cd "$run" && sha256sum --check --quiet SHA256SUMS)

name="$(basename "$run")"
encrypted="$BACKUP_DIR/$name.tar.age"
tar -C "$BACKUP_DIR" -cf - "$name" | age --encrypt --recipients-file "$RECIPIENTS" > "$encrypted"
sha256sum "$encrypted" > "$encrypted.sha256"
rclone copy --immutable "$encrypted" "$REMOTE/"
rclone copy --immutable "$encrypted.sha256" "$REMOTE/"
rclone check --one-way "$BACKUP_DIR" "$REMOTE" --include "$name.tar.age" --include "$name.tar.age.sha256"
rm -f -- "$encrypted" "$encrypted.sha256"
echo "Off-site copy stored: $REMOTE/$name.tar.age"
