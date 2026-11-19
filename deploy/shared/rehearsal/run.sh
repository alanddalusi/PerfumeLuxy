#!/usr/bin/env bash
# Rehearsal of the shared-VPS deployment against an IMITATION of Foro IA al Día.
# For a disposable Ubuntu VM with Docker Engine + Compose v2 (see deploy/smoke/UBUNTU.md).
# It refuses to run if a real forum or a real perfumeria deployment is present.
#
#   cd deploy && ./shared/rehearsal/run.sh            # run, then remove everything it created
#   KEEP=1 ./shared/rehearsal/run.sh                  # keep both stacks for inspection
#   ./shared/rehearsal/run.sh --cleanup               # remove leftovers of a KEEP=1 run
#
# Uses the real scripts unchanged (preflight, caddy-check, caddy-backup, caddy-apply,
# caddy-rollback, verify-db-target, backup/restore) with two rehearsal-only settings:
# REQUIRE_DNS=0 (the real domain cannot point to a VM) and a forum Caddyfile with
# `local_certs`, so no ACME request is ever made for perfumeriaelbuenolor.es.
set -uo pipefail

cd "$(dirname "$0")/../.."                       # deploy/
SIM_PROJECT="foroia-production"
SIM_COMPOSE="shared/rehearsal/foro-compose.yaml"
LABEL="perfumeria.rehearsal"
ENV_PATH="shared/.env.production"
MARKER="# REHEARSAL-ONLY env file created by shared/rehearsal/run.sh"
export SIM_HTTP_PORT="${SIM_HTTP_PORT:-28080}" SIM_HTTPS_PORT="${SIM_HTTPS_PORT:-28443}"
WORK="$(mktemp -d "${REHEARSAL_WORK_ROOT:-$HOME}/perfumeria-rehearsal.XXXXXX")" || exit 2
chmod 700 "$WORK"
export FORO_SIM_DIR="$WORK/foro" FORO_SIM_DB_PASSWORD="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"
export CADDY_BACKUP_DIR="$WORK/caddy-backups"
REPORT="$WORK/report.txt"
passed=0; failed=0; sim_created=0; app_created=0

log() { printf '%s\n' "$*" | tee -a "$REPORT"; }
ok() { passed=$((passed + 1)); log "PASS  $*"; }
ko() { failed=$((failed + 1)); log "FAIL  $*"; }
die() { log "ABORT $*"; exit 2; }
check() { local name="$1"; shift; if "$@" >>"$WORK/checks.log" 2>&1; then ok "$name"; else ko "$name"; fi; }
sim() { docker compose -p "$SIM_PROJECT" -f "$SIM_COMPOSE" "$@"; }
pc() { docker compose -p perfumeria-production -f shared/compose.yaml --env-file "$ENV_PATH" "$@"; }
secret() { od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; }
forum_get() { curl -sk --max-time 10 --resolve "foro.localhost:$SIM_HTTPS_PORT:127.0.0.1" "https://foro.localhost:$SIM_HTTPS_PORT/"; }
perf() { curl -sk --max-time 15 --resolve "perfumeriaelbuenolor.es:$SIM_HTTPS_PORT:127.0.0.1" "$@"; }
perf_status() { perf -o /dev/null -w '%{http_code}' "https://perfumeriaelbuenolor.es:$SIM_HTTPS_PORT$1"; }
forum_state() { docker ps -a --filter "label=com.docker.compose.project=$SIM_PROJECT" --format '{{.Names}}' | sort | xargs -r docker inspect -f '{{.Name}} {{.Id}} {{.State.StartedAt}} {{.RestartCount}}'; }
caddyfile_state() { stat -c '%i' "$FORO_SIM_DIR/Caddyfile"; sha256sum "$FORO_SIM_DIR/Caddyfile" | cut -d' ' -f1; }

wait_healthy() {
    local id
    for _ in $(seq "${2:-180}"); do
        id="$(pc ps -q "$1" 2>/dev/null)"
        [ -n "$id" ] && [ "$(docker inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null)" = healthy ] && return 0
        sleep 1
    done
    return 1
}

# Every resource of the imitation must carry the rehearsal label; otherwise it may be the real forum.
sim_is_ours() {
    local ids
    ids="$(docker ps -aq --filter "label=com.docker.compose.project=$SIM_PROJECT")"
    for id in $ids; do [ "$(docker inspect -f "{{index .Config.Labels \"$LABEL\"}}" "$id")" = true ] || return 1; done
    for n in "${SIM_PROJECT}_edge" "${SIM_PROJECT}_backend" $(docker network ls -q --filter "label=com.docker.compose.project=$SIM_PROJECT"); do
        docker network inspect "$n" >/dev/null 2>&1 || continue
        [ "$(docker network inspect -f "{{index .Labels \"$LABEL\"}}" "$n")" = true ] || return 1
    done
    for v in $(docker volume ls -q --filter "label=com.docker.compose.project=$SIM_PROJECT"); do
        [ "$(docker volume inspect -f "{{index .Labels \"$LABEL\"}}" "$v")" = true ] || return 1
    done
}
sim_exists() {
    [ -n "$(docker ps -aq --filter "label=com.docker.compose.project=$SIM_PROJECT")$(docker volume ls -q --filter "label=com.docker.compose.project=$SIM_PROJECT")" ] \
        || docker network inspect "${SIM_PROJECT}_edge" >/dev/null 2>&1 || docker network inspect "${SIM_PROJECT}_backend" >/dev/null 2>&1
}
app_exists() { [ -n "$(docker ps -aq --filter label=com.docker.compose.project=perfumeria-production)$(docker volume ls -q --filter label=com.docker.compose.project=perfumeria-production)" ]; }
env_is_ours() { [ -f "$ENV_PATH" ] && head -n1 "$ENV_PATH" | grep -qxF "$MARKER"; }

teardown() {
    if env_is_ours && { [ "$app_created" = 1 ] || [ "${CLEANUP:-0}" = 1 ]; }; then
        pc down -v --remove-orphans >/dev/null 2>&1
    fi
    if sim_exists; then
        if sim_is_ours; then
            FORO_SIM_DIR="${FORO_SIM_DIR}" sim down -v --remove-orphans >/dev/null 2>&1
        else
            log "NOT removing $SIM_PROJECT: some resources lack the $LABEL label (real forum?)"
        fi
    fi
    env_is_ours && rm -f -- "$ENV_PATH"
}

if [ "${1:-}" = "--cleanup" ]; then
    CLEANUP=1
    [ -f "$ENV_PATH" ] && ! env_is_ours && die "$ENV_PATH is not a rehearsal file; refusing to clean up"
    export FORO_SIM_DIR=/nonexistent
    teardown; log "Cleanup finished."; exit 0
fi

finish() {
    if [ "${KEEP:-0}" = 1 ]; then
        log "Stacks kept. Remove them with: ./shared/rehearsal/run.sh --cleanup"
    elif [ "$sim_created" = 1 ] || [ "$app_created" = 1 ]; then
        teardown
    fi
    log "Work directory: $WORK"
    log "Report: $REPORT  (passed=$passed failed=$failed)"
}
trap finish EXIT

# ------------------------------------------------------------ guards (nothing created yet)
version="$(docker compose version --short 2>/dev/null | sed 's/^v//')"
[ -n "$version" ] && [ "$(printf '%s\n2.20.0\n' "$version" | sort -V | head -n1)" = 2.20.0 ] || die "Docker Compose v2.20+ required"
for tool in curl sha256sum stat od; do command -v "$tool" >/dev/null || die "missing $tool"; done
if sim_exists; then
    sim_is_ours && die "leftover rehearsal forum found; run ./shared/rehearsal/run.sh --cleanup" \
        || die "a real '$SIM_PROJECT' project exists on this host: this is not a rehearsal machine"
fi
app_exists && die "perfumeria-production resources exist on this host: never rehearse next to a real deployment"
[ -e "$ENV_PATH" ] && die "$ENV_PATH exists; the rehearsal will not overwrite it"
for port in "$SIM_HTTP_PORT" "$SIM_HTTPS_PORT"; do ss -Hltn "sport = :$port" | grep -q . && die "port $port in use"; done
log "Rehearsal on $(. /etc/os-release && echo "$PRETTY_NAME"), Docker $(docker version -f '{{.Server.Version}}'), Compose $version, commit $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

# ------------------------------------------------------------ 1. imitation of the forum
mkdir -p "$FORO_SIM_DIR"
cat > "$FORO_SIM_DIR/Caddyfile" <<'EOF'
{
	local_certs
}

foro.localhost {
	reverse_proxy web:80
}
EOF
sim_created=1
sim up -d >"$WORK/sim-up.log" 2>&1 || die "imitation forum did not start (see $WORK/sim-up.log)"
for _ in $(seq 60); do forum_get | grep -q 'Name: foro-sim-web' && break; sleep 2; done
check "imitation forum answers through its Caddy" sh -c "curl -sk --resolve foro.localhost:$SIM_HTTPS_PORT:127.0.0.1 https://foro.localhost:$SIM_HTTPS_PORT/ | grep -q 'Name: foro-sim-web'"
sim exec -T db psql -U foro -d foro -qc "create table foro_marker (note text); insert into foro_marker values ('untouched');" >/dev/null
forum_before="$(forum_state)"
read -r inode0 sha0 <<< "$(caddyfile_state | tr '\n' ' ')"

# ------------------------------------------------------------ 2. perfumeria env (rehearsal values)
umask 077
cat > "$ENV_PATH" <<EOF
$MARKER
COMPOSE_FILE=shared/compose.yaml
COMPOSE_PROJECT_NAME=perfumeria-production
WEB_SERVICE=perfumeria-web
DB_SERVICE=perfumeria-db
PROXY_SERVICE=
RELEASE=rehearsal
SITE_DOMAIN=perfumeriaelbuenolor.es
DJANGO_ALLOWED_HOSTS=perfumeriaelbuenolor.es
DJANGO_CSRF_TRUSTED_ORIGINS=https://perfumeriaelbuenolor.es
SECRET_KEY=$(secret)$(secret)
POSTGRES_DB=perfumeria
POSTGRES_USER=perfumeria
POSTGRES_PASSWORD=$(secret)
SHARED_EDGE_NETWORK=foroia-production_edge
SHARED_PROXY_CONTAINER=foroia-production-caddy-1
GUNICORN_WORKERS=2
GUNICORN_THREADS=2
BACKUP_DIR=$WORK/backups
BACKUP_KEEP_DAYS=14
EOF
umask 022
chmod 600 "$ENV_PATH"

# ------------------------------------------------------------ 3. read-only audit and Caddy checks
REQUIRE_DNS=0 ./shared/preflight.sh >"$WORK/preflight.log" 2>&1 && ok "preflight.sh: no FAIL" || ko "preflight.sh (see $WORK/preflight.log)"
bash ./shared/audit-readonly.sh >"$WORK/audit.log" 2>&1 && ok "audit-readonly.sh: no FAIL" || ko "audit-readonly.sh (see $WORK/audit.log)"
./shared/caddy-check.sh >"$WORK/caddy-check.log" 2>&1 && ok "caddy-check.sh validates current and candidate" || ko "caddy-check.sh (see $WORK/caddy-check.log)"
./shared/caddy-backup.sh >"$WORK/caddy-backup.log" 2>&1 && ok "caddy-backup.sh creates a verified copy" || ko "caddy-backup.sh (see $WORK/caddy-backup.log)"
copy="$(find "$CADDY_BACKUP_DIR" -maxdepth 1 -type d -name 'config-*' | sort | tail -n1)"
check "caddy-backup.sh --verify on the copy" ./shared/caddy-backup.sh --verify "$copy"
check "copy files are owner-only" sh -c "[ -n '$copy' ] && [ -z \"\$(find '$copy' -type f ! -perm 600)\" ]"
check "Caddyfile untouched by read-only steps" test "$(caddyfile_state | tr '\n' ' ')" = "$inode0 $sha0 "

# ------------------------------------------------------------ 4. perfumeria stack on the shared network
app_created=1
pc build >"$WORK/build.log" 2>&1 && ok "image builds" || { ko "image builds (see $WORK/build.log)"; exit 1; }
pc up -d perfumeria-db >/dev/null 2>&1
check "perfumeria-db healthy" wait_healthy perfumeria-db 90
check "perfumeria-db only on its internal network" test "$(docker inspect -f '{{range $n, $v := .NetworkSettings.Networks}}{{$n}} {{end}}' "$(pc ps -q perfumeria-db)")" = "perfumeria-production_backend "
check "perfumeria backend network is internal" test "$(docker network inspect -f '{{.Internal}}' perfumeria-production_backend)" = true
./shared/verify-db-target.sh >"$WORK/verify-db.log" 2>&1 && ok "verify-db-target.sh: Django targets perfumeria-db only" || ko "verify-db-target.sh (see $WORK/verify-db.log)"
pc run --rm -T perfumeria-web python manage.py migrate --noinput >"$WORK/migrate.log" 2>&1 && ok "migrations apply" || ko "migrations (see $WORK/migrate.log)"
pc up -d perfumeria-web >/dev/null 2>&1
check "perfumeria-web healthy" wait_healthy perfumeria-web 180
check "forum database untouched (marker intact, no Django tables)" sh -c \
    "docker compose -p $SIM_PROJECT -f $SIM_COMPOSE exec -T db psql -U foro -d foro -tAc \"select (select note from foro_marker) || ':' || (select count(*) from information_schema.tables where table_name like 'django_%')\" | grep -qx 'untouched:0'"
check "perfumeria-web cannot resolve the forum database alias 'db'" sh -c \
    "! docker compose -p perfumeria-production -f shared/compose.yaml --env-file $ENV_PATH exec -T perfumeria-web python -c \"import socket; socket.gethostbyname('db')\""
collisions=0
for _ in $(seq 30); do forum_get | grep -q 'Name: foro-sim-web' || collisions=$((collisions + 1)); done
check "forum 'web' still resolves only to the forum (30/30 requests)" test "$collisions" = 0
check "no published ports in perfumeria-production" test -z "$(docker ps --filter label=com.docker.compose.project=perfumeria-production --format '{{.Ports}}' | tr -d ' \n')"
check "forum containers not restarted after joining the network" test "$(forum_state)" = "$forum_before"

# ------------------------------------------------------------ 5. negative test: invalid block is never applied
printf '# >>> BEGIN perfumeria-el-buen-olor\nperfumeriaelbuenolor.es {\n\tthis_directive_does_not_exist\n}\n# <<< END perfumeria-el-buen-olor\n' > "$WORK/broken.caddy"
PERFUMERIA_CADDY_BLOCK="$WORK/broken.caddy" REQUIRE_DNS=0 FORO_URLS="https://foro.localhost:$SIM_HTTPS_PORT/" \
    FORO_CURL_OPTS="-k --resolve foro.localhost:$SIM_HTTPS_PORT:127.0.0.1" ./shared/caddy-apply.sh >"$WORK/apply-broken.log" 2>&1 \
    && ko "caddy-apply.sh accepted an invalid block" || ok "caddy-apply.sh rejects an invalid block"
check "Caddyfile unchanged after the rejected apply" test "$(caddyfile_state | tr '\n' ' ')" = "$inode0 $sha0 "
check "forum unaffected by the rejected apply" sh -c "curl -sk --resolve foro.localhost:$SIM_HTTPS_PORT:127.0.0.1 https://foro.localhost:$SIM_HTTPS_PORT/ | grep -q 'Name: foro-sim-web'"

# ------------------------------------------------------------ 6. apply
REQUIRE_DNS=0 FORO_URLS="https://foro.localhost:$SIM_HTTPS_PORT/" FORO_CURL_OPTS="-k --resolve foro.localhost:$SIM_HTTPS_PORT:127.0.0.1" \
    ./shared/caddy-apply.sh >"$WORK/apply.log" 2>&1 && ok "caddy-apply.sh" || ko "caddy-apply.sh (see $WORK/apply.log)"
read -r inode1 sha1 <<< "$(caddyfile_state | tr '\n' ' ')"
check "same inode after apply (bind mount still sees the file)" test "$inode1" = "$inode0"
check "only the delimited block was added" sh -c "head -c \$(stat -c %s '$copy/Caddyfile') '$FORO_SIM_DIR/Caddyfile' | cmp -s - '$copy/Caddyfile'"
for _ in $(seq 30); do [ "$(perf_status /)" = 200 ] && break; sleep 2; done
check "perfumeria home 200 through the forum's Caddy" test "$(perf_status /)" = 200
check "perfumeria /checkout/ 403" test "$(perf_status /checkout/)" = 403
check "perfumeria /healthz/ 404 (hidden by Caddy)" test "$(perf_status /healthz/)" = 404
check "perfumeria /media/ 404 (hidden by Caddy)" test "$(perf_status /media/ER1173710781.jpeg)" = 404
check "static served by WhiteNoise with cache headers" sh -c "curl -skI --resolve perfumeriaelbuenolor.es:$SIM_HTTPS_PORT:127.0.0.1 https://perfumeriaelbuenolor.es:$SIM_HTTPS_PORT/static/css/storefront.css | tr -d '\r' | grep -qi '^cache-control: max-age=86400, public'"
check "HSTS and X-Frame-Options present" sh -c "curl -skI --resolve perfumeriaelbuenolor.es:$SIM_HTTPS_PORT:127.0.0.1 https://perfumeriaelbuenolor.es:$SIM_HTTPS_PORT/ | tr -d '\r' | grep -qi '^strict-transport-security' && curl -skI --resolve perfumeriaelbuenolor.es:$SIM_HTTPS_PORT:127.0.0.1 https://perfumeriaelbuenolor.es:$SIM_HTTPS_PORT/ | tr -d '\r' | grep -qi '^x-frame-options: deny'"
check "no e-mail forms (prelaunch without SMTP)" sh -c "! curl -sk --resolve perfumeriaelbuenolor.es:$SIM_HTTPS_PORT:127.0.0.1 https://perfumeriaelbuenolor.es:$SIM_HTTPS_PORT/ | grep -q 'name=\"consent\"'"
token="REHEARSAL$(od -An -N6 -tx1 /dev/urandom | tr -d ' \n')"
perf -o /dev/null "https://perfumeriaelbuenolor.es:$SIM_HTTPS_PORT/avisos/lanzamiento/confirmar/$token/"; sleep 2
sim exec -T caddy cat /data/perfumeria/access.log > "$WORK/perfumeria-access.log" 2>/dev/null
check "perfumeria access log written in the forum Caddy volume" test -s "$WORK/perfumeria-access.log"
check "token redacted in the access log" sh -c "! grep -q '$token' '$WORK/perfumeria-access.log' && grep -q redacted '$WORK/perfumeria-access.log'"
check "forum still answers after apply" sh -c "curl -sk --resolve foro.localhost:$SIM_HTTPS_PORT:127.0.0.1 https://foro.localhost:$SIM_HTTPS_PORT/ | grep -q 'Name: foro-sim-web'"
check "forum containers not restarted by apply (graceful reload)" test "$(forum_state)" = "$forum_before"
REQUIRE_DNS=0 FORO_URLS="https://foro.localhost:$SIM_HTTPS_PORT/" FORO_CURL_OPTS="-k --resolve foro.localhost:$SIM_HTTPS_PORT:127.0.0.1" \
    ./shared/caddy-apply.sh >"$WORK/apply-again.log" 2>&1 && grep -q 'already present' "$WORK/apply-again.log" && ok "second apply is a no-op" || ko "second apply is a no-op"
check "Caddyfile unchanged by the second apply" test "$(caddyfile_state | tr '\n' ' ')" = "$inode1 $sha1 "

# ------------------------------------------------------------ 7. backups in shared mode
PERFUMERIA_ENV_FILE="$ENV_PATH" ./backup/backup.sh >"$WORK/backup.log" 2>&1 && ok "backup.sh in shared mode" || ko "backup.sh (see $WORK/backup.log)"
run_dir="$(find "$WORK/backups" -mindepth 1 -maxdepth 1 -type d -name '20*Z' 2>/dev/null | sort | tail -n1)"
PERFUMERIA_ENV_FILE="$ENV_PATH" ./backup/restore.sh --verify "$run_dir" >"$WORK/restore-verify.log" 2>&1 && ok "restore.sh --verify in shared mode" || ko "restore.sh --verify (see $WORK/restore-verify.log)"
printf 'perfumeriaelbuenolor.es\n' | PERFUMERIA_ENV_FILE="$ENV_PATH" ./backup/restore.sh --replace-production "$run_dir" >"$WORK/restore.log" 2>&1 \
    && ok "restore.sh --replace-production in shared mode" || ko "restore.sh --replace-production (see $WORK/restore.log)"
check "forum Caddy not stopped by the restore" test "$(forum_state)" = "$forum_before"
check "perfumeria-web healthy after restore" wait_healthy perfumeria-web 180

# ------------------------------------------------------------ 8. rollback
./shared/caddy-rollback.sh >"$WORK/rollback.log" 2>&1 && ok "caddy-rollback.sh" || ko "caddy-rollback.sh (see $WORK/rollback.log)"
check "Caddyfile identical to the original (inode and SHA-256)" test "$(caddyfile_state | tr '\n' ' ')" = "$inode0 $sha0 "
check "perfumeria no longer served by the forum Caddy" sh -c "[ \"\$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 --resolve perfumeriaelbuenolor.es:$SIM_HTTPS_PORT:127.0.0.1 https://perfumeriaelbuenolor.es:$SIM_HTTPS_PORT/)\" != 200 ]"
check "forum still answers after rollback" sh -c "curl -sk --resolve foro.localhost:$SIM_HTTPS_PORT:127.0.0.1 https://foro.localhost:$SIM_HTTPS_PORT/ | grep -q 'Name: foro-sim-web'"
check "forum containers not restarted by rollback" test "$(forum_state)" = "$forum_before"

# ------------------------------------------------------------ 9. R2: stop the perfumeria (keeps data)
pc down >/dev/null 2>&1 && ok "pc down (without -v)" || ko "pc down"
check "forum edge network still exists" docker network inspect foroia-production_edge
check "perfumeria volumes kept" test -n "$(docker volume ls -q --filter label=com.docker.compose.project=perfumeria-production)"
check "forum unaffected by pc down" sh -c "curl -sk --resolve foro.localhost:$SIM_HTTPS_PORT:127.0.0.1 https://foro.localhost:$SIM_HTTPS_PORT/ | grep -q 'Name: foro-sim-web'"
check "forum containers unchanged at the end" test "$(forum_state)" = "$forum_before"

log "----"
[ "$failed" -eq 0 ] && log "RESULT: ALL $passed CHECKS PASSED" || log "RESULT: $failed OF $((passed + failed)) CHECKS FAILED"
[ "$failed" -eq 0 ]
