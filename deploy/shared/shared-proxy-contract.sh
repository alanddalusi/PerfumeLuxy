#!/usr/bin/env bash
# Contract of the shared Caddy on the VPS (standalone, read-only, no project dependencies).
# Any project that owns or uses the shared Caddy can run it; the forum project may copy it
# into its own release checklist. It never modifies anything.
#
#   ./shared-proxy-contract.sh --static compose.production.yml deploy/Caddyfile   # before a release
#   sudo ./shared-proxy-contract.sh --live [container]                            # after a release
#
# Contract:
#   1. The Caddyfile imports per-project site files:   import /etc/caddy/sites/*.caddy
#   2. The caddy service mounts /srv/caddy/sites read-only at /etc/caddy/sites
#   3. The caddy service mounts /srv/caddy/logs read-write at /var/log/caddy-sites
#   4. (live) the running configuration validates and the admin API allows graceful reloads
#   5. (live) every *.caddy file in /srv/caddy/sites is loaded (its hosts are served)
set -uo pipefail

fails=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() { fails=$((fails + 1)); printf 'FAIL  %s\n' "$*"; }
IMPORT_RE='^[[:space:]]*import[[:space:]]+/etc/caddy/sites/\*\.caddy[[:space:]]*$'
SITES_HOST="${CONTRACT_SITES_DIR:-/srv/caddy/sites}"   # overridable only for sandbox tests
LOGS_HOST="${CONTRACT_LOGS_DIR:-/srv/caddy/logs}"

case "${1:-}" in
--static)
    compose="${2:?compose file}"; caddyfile="${3:?Caddyfile}"
    grep -qE "$IMPORT_RE" "$caddyfile" && pass "$caddyfile imports /etc/caddy/sites/*.caddy" \
                                      || fail "$caddyfile lacks 'import /etc/caddy/sites/*.caddy'"
    # Only look inside the caddy service block of the compose file.
    block="$(awk '/^  caddy:/{f=1; print; next} f && /^  [A-Za-z0-9_-]+:/{f=0} f' "$compose")"
    [ -n "$block" ] || fail "no 'caddy' service found in $compose"
    printf '%s\n' "$block" | grep -qE -- '-[[:space:]]*"?/srv/caddy/sites:/etc/caddy/sites:ro"?[[:space:]]*$' \
        && pass "caddy mounts /srv/caddy/sites:/etc/caddy/sites:ro" || fail "caddy lacks the mount /srv/caddy/sites:/etc/caddy/sites:ro"
    printf '%s\n' "$block" | grep -qE -- '-[[:space:]]*"?/srv/caddy/logs:/var/log/caddy-sites"?[[:space:]]*$' \
        && pass "caddy mounts /srv/caddy/logs:/var/log/caddy-sites" || fail "caddy lacks the mount /srv/caddy/logs:/var/log/caddy-sites"
    ;;
--live)
    c="${2:-foroia-production-caddy-1}"
    [ "$(docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null)" = true ] && pass "$c running" || { fail "$c not running"; echo "fails=$fails"; exit 1; }
    mounts="$(docker inspect -f '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.RW}}{{println}}{{end}}' "$c")"
    printf '%s\n' "$mounts" | grep -qxF "bind|$SITES_HOST|/etc/caddy/sites|false" && pass "sites mount read-only" || fail "sites mount missing or writable"
    printf '%s\n' "$mounts" | grep -qxF "bind|$LOGS_HOST|/var/log/caddy-sites|true" && pass "logs mount read-write" || fail "logs mount missing"
    config="$(docker inspect -f '{{range .Args}}{{println .}}{{end}}' "$c" | awk 'p == "--config" {print; f = 1; exit} {p = $0} END {if (!f) print "/etc/caddy/Caddyfile"}')"
    docker exec "$c" grep -qE "$IMPORT_RE" "$config" && pass "running Caddyfile has the import line" || fail "running Caddyfile lacks the import line"
    docker exec "$c" caddy validate --config "$config" --adapter caddyfile >/dev/null 2>&1 && pass "configuration validates" || fail "configuration does not validate"
    docker exec "$c" wget -q -O /dev/null http://127.0.0.1:2019/config/ 2>/dev/null && pass "admin API reachable" || fail "admin API not reachable"
    hosts="$(docker exec "$c" wget -q -O - http://127.0.0.1:2019/config/apps/http/servers 2>/dev/null | grep -oE '"host":\[[^]]*\]' | grep -oE '"[^"]+"' | tr -d '"' | grep -v '^host$' | sort -u)"
    for f in "$SITES_HOST"/*.caddy; do
        [ -f "$f" ] || continue
        site="$(basename "$f" .caddy)"
        printf '%s\n' "$hosts" | grep -qxF "$site" && pass "$site loaded" || fail "$site file present but not loaded (reload pending or invalid)"
    done
    ;;
*) sed -n '2,15p' "$0"; exit 2 ;;
esac
echo "----"; echo "fails=$fails"
[ "$fails" -eq 0 ]
