#!/usr/bin/env bash
# Isolated test of site-deploy.sh / site-rollback.sh / site-status.sh / shared-proxy-contract.sh
# against a SANDBOX copy of the shared-proxy layout. Safe on any Docker host:
#   - own containers perfumeria-sitetest-{proxy,foro,web} and network perfumeria-sitetest-net,
#     all labelled perfumeria.sitetest=true, no published ports;
#   - reuses an image already present (the shared proxy's image), never pulls;
#   - the scripts run with SITE_TEST_MODE=1, which makes them refuse any container that is
#     not perfumeria-sitetest-*; only resources with the sandbox label are ever removed.
#
#   cd deploy && sudo ./shared/sitetest/run.sh            # run all tests, then remove the sandbox
#   sudo KEEP=1 ./shared/sitetest/run.sh                  # keep it for inspection
#   sudo ./shared/sitetest/run.sh --cleanup               # remove leftovers of a KEEP=1 run
set -uo pipefail
cd "$(dirname "$0")/.."                               # deploy/shared
LABEL="perfumeria.sitetest=true"
P="perfumeria-sitetest"
NET="$P-net"
DOMAIN="perfumeriaelbuenolor.es"

sandbox_ids() { docker ps -aq --filter "label=$LABEL"; }
cleanup_sandbox() {
    local ids; ids="$(sandbox_ids)"
    [ -n "$ids" ] && docker rm -fv $ids >/dev/null   # -v: also their anonymous /data and /config volumes
    docker network ls -q --filter "label=$LABEL" | xargs -r docker network rm >/dev/null
}
[ "$(id -u)" = 0 ] || { echo "Run with sudo." >&2; exit 2; }
if [ "${1:-}" = "--cleanup" ]; then cleanup_sandbox; echo "Sandbox removed."; exit 0; fi
[ -z "$(sandbox_ids)$(docker network ls -q --filter "label=$LABEL")" ] || { echo "Sandbox leftovers exist; run with --cleanup first." >&2; exit 2; }
for n in "$P-proxy" "$P-foro" "$P-web"; do docker inspect "$n" >/dev/null 2>&1 && { echo "A container named $n exists without the sandbox label; refusing." >&2; exit 2; }; done

IMAGE="${PROXY_IMAGE:-$(docker inspect -f '{{.Config.Image}}' foroia-production-caddy-1 2>/dev/null || echo caddy:2-alpine)}"
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "Image $IMAGE not present locally (this test never pulls)." >&2; exit 2; }
WORK="$(mktemp -d "${SITETEST_ROOT:-/srv/perfumeria}/sitetest.XXXXXX")" || exit 2
chmod 700 "$WORK"; mkdir -p "$WORK/sites" "$WORK/logs" "$WORK/backups"; chmod 755 "$WORK/sites" "$WORK/logs"
REPORT="$WORK/report.txt"
passed=0; failed=0
log() { printf '%s\n' "$*" | tee -a "$REPORT"; }
ok() { passed=$((passed + 1)); log "PASS  $*"; }
ko() { failed=$((failed + 1)); log "FAIL  $*"; }
expect() { local want="$1" name="$2"; shift 2; "$@" >>"$WORK/commands.log" 2>&1; local rc=$?
    if { [ "$want" = 0 ] && [ $rc = 0 ]; } || { [ "$want" = fail ] && [ $rc != 0 ]; }; then ok "$name"; else ko "$name (rc=$rc)"; fi; }
finish() {
    log "RESULT: passed=$passed failed=$failed"
    if [ "${KEEP:-0}" = 1 ]; then log "Sandbox kept: $WORK (remove with --cleanup, then rm -r the directory)"
    else cleanup_sandbox; rm -rf -- "$WORK"; fi
}
trap finish EXIT

# ------------------------------------------------------------------ sandbox
cat > "$WORK/Caddyfile.unprepared" <<'EOF'
{
	local_certs
}

foro.test {
	reverse_proxy web:80
}
EOF
{ cat "$WORK/Caddyfile.unprepared"; printf '\n# Sitios de otros proyectos alojados en este VPS\nimport /etc/caddy/sites/*.caddy\n'; } > "$WORK/Caddyfile"
docker network create --label "$LABEL" "$NET" >/dev/null
# Stand-ins: the forum app answers on "web"; the shop answers on "perfumeria-web" like Django
# (403 on /checkout/ during prelaunch, 200 elsewhere).
printf '{
	admin off
	auto_https off
}
:80 {
	respond "foro-ok"
}
' > "$WORK/foro-upstream.Caddyfile"
printf '{
	admin off
	auto_https off
}
:8000 {
	respond /checkout/* "forbidden" 403
	respond "perfumeria-ok"
}
' > "$WORK/web-upstream.Caddyfile"
docker run -d --name "$P-foro" --label "$LABEL" --network "$NET" --network-alias web -v "$WORK/foro-upstream.Caddyfile:/etc/caddy/Caddyfile:ro" "$IMAGE" >/dev/null
docker run -d --name "$P-web" --label "$LABEL" --network "$NET" --network-alias perfumeria-web -v "$WORK/web-upstream.Caddyfile:/etc/caddy/Caddyfile:ro" "$IMAGE" >/dev/null

start_proxy() {   # $1 = prepared|unprepared
    docker rm -fv "$P-proxy" >/dev/null 2>&1
    if [ "$1" = prepared ]; then
        docker run -d --name "$P-proxy" --label "$LABEL" --network "$NET" \
            -v "$WORK/Caddyfile:/etc/caddy/Caddyfile:ro" -v "$WORK/sites:/etc/caddy/sites:ro" -v "$WORK/logs:/var/log/caddy-sites" \
            "$IMAGE" >/dev/null
    else
        docker run -d --name "$P-proxy" --label "$LABEL" --network "$NET" -v "$WORK/Caddyfile.unprepared:/etc/caddy/Caddyfile:ro" "$IMAGE" >/dev/null
    fi
    for _ in $(seq 30); do docker exec "$P-proxy" wget -q -O /dev/null http://127.0.0.1:2019/config/ 2>/dev/null && break; sleep 1; done
    IP="$(docker inspect -f "{{(index .NetworkSettings.Networks \"$NET\").IPAddress}}" "$P-proxy")"
}

export SITE_TEST_MODE=1 SHARED_PROXY_CONTAINER="$P-proxy" SITES_DIR="$WORK/sites" LOGS_DIR="$WORK/logs" \
       CADDY_BACKUP_DIR="$WORK/backups" LOCK_FILE="$WORK/lock" REQUIRE_DNS=0 SETTLE_SECONDS=2 \
       PERFUMERIA_ENV_FILE=/dev/null STATUS_MIN_DAYS=0 STATUS_CURL_OPTS=-k \
       CONTRACT_SITES_DIR="$WORK/sites" CONTRACT_LOGS_DIR="$WORK/logs"
env_for_ip() { export FORO_URLS="https://foro.test/" FORO_CURL_OPTS="-k --resolve foro.test:443:$IP" STATUS_ADDR="$IP:443"; }
body() { curl -sk --max-time 10 --resolve "$1:443:$IP" "https://$1${2:-/}"; }
active_sha() { [ -f "$WORK/sites/$DOMAIN.caddy" ] && sha256sum < "$WORK/sites/$DOMAIN.caddy" | cut -c1-16 || echo none; }
sha_of() { sha256sum < "$1" | cut -c1-16; }

log "Sandbox image: $IMAGE ($(docker run --rm --network none --entrypoint caddy "$IMAGE" version | cut -d' ' -f1)); work dir $WORK"

# Versions of the site file used by the tests (v1 = the real file in the repository).
V1="site/$DOMAIN.caddy"
sed 's/^\t\t-Via$/\t\t-Via\n\t\tX-Site-Version "v2"/' "$V1" > "$WORK/v2.caddy"
sed 's/^\t\t-Via$/\t\t-Via\n\t\tX-Site-Version "v3"/' "$V1" > "$WORK/v3.caddy"
printf '%s {\n\tthis_directive_does_not_exist\n}\n' "$DOMAIN" > "$WORK/broken.caddy"
printf 'foro.test {\n\trespond "hijacked"\n}\n' > "$WORK/hijack.caddy"

# ------------------------------------------------------------------ A. proxy NOT prepared
start_proxy unprepared; env_for_ip
expect fail "A1 site-deploy refuses when the shared proxy lacks the mounts and the import line" ./site-deploy.sh
[ "$(active_sha)" = none ] && ok "A2 nothing written to the sites directory" || ko "A2 a site file was written"
expect fail "A3 site-status reports the missing preparation" ./site-status.sh
expect fail "A4 contract --live detects the unprepared proxy" ./shared-proxy-contract.sh --live "$P-proxy"

# ------------------------------------------------------------------ B. one-time preparation
start_proxy prepared; env_for_ip
IDENTITY="$(docker inspect -f '{{.Id}} {{.State.StartedAt}} {{.RestartCount}}' "$P-proxy")"
expect 0 "B1 contract --live passes with an empty sites directory" ./shared-proxy-contract.sh --live "$P-proxy"
[ "$(body foro.test)" = "foro-ok" ] && ok "B2 forum site answers through the prepared proxy" || ko "B2 forum site"
cp /opt/foroia/compose.production.yml "$WORK/compose.yml" 2>/dev/null || printf 'services:\n  caddy:\n    image: caddy\n    volumes:\n      - ./deploy/Caddyfile:/etc/caddy/Caddyfile:ro\n  web:\n    image: x\n' > "$WORK/compose.yml"
expect fail "B3 contract --static rejects a compose file without the mounts" ./shared-proxy-contract.sh --static "$WORK/compose.yml" "$WORK/Caddyfile"
awk '{print} /\.\/deploy\/Caddyfile:\/etc\/caddy\/Caddyfile:ro/ {sub(/-.*/, ""); print $0 "- /srv/caddy/sites:/etc/caddy/sites:ro"; print $0 "- /srv/caddy/logs:/var/log/caddy-sites"}' "$WORK/compose.yml" > "$WORK/compose.prepared.yml"
expect 0 "B4 contract --static accepts the compose file with the two mounts" ./shared-proxy-contract.sh --static "$WORK/compose.prepared.yml" "$WORK/Caddyfile"
expect fail "B5 contract --static rejects a Caddyfile without the import line" ./shared-proxy-contract.sh --static "$WORK/compose.prepared.yml" "$WORK/Caddyfile.unprepared"

# ------------------------------------------------------------------ C. deploy
expect 0 "C1 first deployment (v1)" ./site-deploy.sh
[ "$(active_sha)" = "$(sha_of "$V1")" ] && ok "C2 active file is v1" || ko "C2 active file"
[ "$(body "$DOMAIN")" = "perfumeria-ok" ] && ok "C3 $DOMAIN proxied to perfumeria-web" || ko "C3 perfumeria response"
[ "$(curl -sk -o /dev/null -w '%{http_code} %{redirect_url}' --resolve "www.$DOMAIN:443:$IP" "https://www.$DOMAIN/")" = "301 https://$DOMAIN/" ] && ok "C4 www redirects to the apex" || ko "C4 www redirect"
[ "$(body "$DOMAIN" /healthz/)" != "perfumeria-ok" ] && ok "C5 /healthz/ hidden by the site block" || ko "C5 healthz"
[ "$(body foro.test)" = "foro-ok" ] && ok "C6 forum still answers (web alias not taken over)" || ko "C6 forum"
[ -s "$WORK/logs/$DOMAIN/access.log" ] && ok "C7 access log written to the neutral logs directory" || ko "C7 access log"
expect 0 "C8 site-status passes" ./site-status.sh
expect 0 "C9 contract --live: the site file is loaded" ./shared-proxy-contract.sh --live "$P-proxy"
expect 0 "C10 identical redeployment is a no-op" ./site-deploy.sh
grep -q "nothing to do" "$WORK/commands.log" && ok "C11 no-op reported" || ko "C11 no-op message"

# ------------------------------------------------------------------ D. update and failure recovery
expect 0 "D1 deploy v2" env SITE_SOURCE="$WORK/v2.caddy" ./site-deploy.sh
[ "$(active_sha)" = "$(sha_of "$WORK/v2.caddy")" ] && ok "D2 active file is v2" || ko "D2 active file"
curl -skI --resolve "$DOMAIN:443:$IP" "https://$DOMAIN/" | tr -d '\r' | grep -qi '^x-site-version: v2' && ok "D3 v2 served" || ko "D3 v2 header"
expect fail "D4 broken candidate rejected before activation" env SITE_SOURCE="$WORK/broken.caddy" ./site-deploy.sh
expect fail "D5 candidate that redefines the forum domain rejected" env SITE_SOURCE="$WORK/hijack.caddy" ./site-deploy.sh
for fault in live-validate reload compare; do
    expect fail "D6 failure at '$fault' is detected" env SITE_SOURCE="$WORK/v3.caddy" SITE_TEST_FAIL_AT="$fault" ./site-deploy.sh
    [ "$(active_sha)" = "$(sha_of "$WORK/v2.caddy")" ] && ok "D7 after '$fault' the previous version (v2) is active again" || ko "D7 state after $fault: $(active_sha)"
done
curl -skI --resolve "$DOMAIN:443:$IP" "https://$DOMAIN/" | tr -d '\r' | grep -qi '^x-site-version: v2' && ok "D8 v2 still served after all failures" || ko "D8 served version"
[ "$(body foro.test)" = "foro-ok" ] && ok "D9 forum unaffected by the failures" || ko "D9 forum"
ls "$WORK/sites" | grep -vqxE "$DOMAIN\.caddy" && ko "D10 stray files left in sites/: $(ls "$WORK/sites" | tr '\n' ' ')" || ok "D10 no staged or temporary files left in sites/"

# ------------------------------------------------------------------ E. rollback
expect 0 "E1 rollback to the previous version" ./site-rollback.sh
[ "$(active_sha)" = "$(sha_of "$V1")" ] && ok "E2 v1 active after rollback (skipping copies identical to v2)" || ko "E2 active after rollback: $(active_sha)"
[ "$(body "$DOMAIN")" = "perfumeria-ok" ] && ok "E3 site still served" || ko "E3 site"
expect fail "E4 rollback failure at reload puts the current file back" env SITE_TEST_FAIL_AT=reload ./site-rollback.sh --remove
[ "$(active_sha)" = "$(sha_of "$V1")" ] && ok "E5 v1 still active after the failed rollback" || ko "E5 state: $(active_sha)"
expect 0 "E6 rollback --remove takes the site offline" ./site-rollback.sh --remove
[ "$(active_sha)" = none ] && ok "E7 site file removed" || ko "E7 site file"
[ "$(curl -sk -o /dev/null -w '%{http_code}' --resolve "$DOMAIN:443:$IP" "https://$DOMAIN/")" != 200 ] && ok "E8 $DOMAIN no longer served" || ko "E8 still served"
[ "$(body foro.test)" = "foro-ok" ] && ok "E9 forum unaffected by the removal" || ko "E9 forum"
expect fail "E10 site-status reports the removed site" ./site-status.sh
expect 0 "E11 contract --live still passes without the site" ./shared-proxy-contract.sh --live "$P-proxy"
expect 0 "E12 redeploy after removal (first-deployment path)" ./site-deploy.sh

# ------------------------------------------------------------------ F. guards
expect fail "F1 test mode refuses the real shared proxy" env SHARED_PROXY_CONTAINER=foroia-production-caddy-1 ./site-deploy.sh
expect fail "F2 a sites directory under /opt is refused" env SITES_DIR=/opt/foroia/deploy ./site-deploy.sh
expect fail "F3 a missing FORO_URLS is refused" env -u FORO_URLS ./site-deploy.sh
[ "$(docker inspect -f '{{.Id}} {{.State.StartedAt}} {{.RestartCount}}' "$P-proxy")" = "$IDENTITY" ] \
    && ok "F4 sandbox proxy never restarted or recreated during sections C-F" || ko "F4 proxy identity changed"
