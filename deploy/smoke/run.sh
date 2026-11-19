#!/usr/bin/env bash
# Isolated end-to-end test of the production stack (Phase 6A).
#
# Target: a disposable Ubuntu Server VM (24.04 LTS or later) with Docker Engine and the
# Compose v2 plugin from Docker's apt repository (not the snap). Never the production VPS.
#
#   cd deploy && ./smoke/run.sh            # run, then remove the smoke stack and its volumes
#   KEEP=1 ./smoke/run.sh                  # keep the stack running for inspection
#
# Optional overrides: SMOKE_HTTP_PORT (18080), SMOKE_HTTPS_PORT (18443),
# SMOKE_SUBNET_PREFIX (172.30.99), SMOKE_WORK_ROOT ($HOME).
#
# Scope: everything happens in the Compose project "perfumeria-smoke" (containers,
# network and volumes prefixed perfumeria-smoke_). Secrets are random and live only in
# the work directory. Caddy listens on 127.0.0.1 with its internal CA; no mail, payment
# or DNS service is contacted. Images are pulled from Docker Hub and packages from PyPI.
set -uo pipefail

cd "$(dirname "$0")/.."
DOMAIN="perfumeria.localhost"
HTTP_PORT="${SMOKE_HTTP_PORT:-18080}"
HTTPS_PORT="${SMOKE_HTTPS_PORT:-18443}"
NET="${SMOKE_SUBNET_PREFIX:-172.30.99}"
WORK="$(mktemp -d "${SMOKE_WORK_ROOT:-$HOME}/perfumeria-smoke.XXXXXX")" || exit 2
REPORT="$WORK/report.txt"
export COMPOSE_PROJECT_NAME="perfumeria-smoke"
export PERFUMERIA_ENV_FILE="$WORK/.env.smoke"
TOKEN="SMOKE6A$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
passed=0
failed=0
started=0

log() { printf '%s\n' "$*" | tee -a "$REPORT"; }
ok() { passed=$((passed + 1)); log "PASS  $*"; }
ko() { failed=$((failed + 1)); log "FAIL  $*"; }
die() { log "ABORT $*"; exit 2; }
check() { local name="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$name"; else ko "$name"; fi; }
compose() { docker compose --env-file "$PERFUMERIA_ENV_FILE" "$@"; }
manage() { compose exec -T web python manage.py "$@"; }
pyshell() { compose exec -T web python manage.py shell --no-imports -c "$1"; }
secret() { od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; }
https() { curl -sS --max-time 15 --cacert "$WORK/root.crt" --resolve "$DOMAIN:$HTTPS_PORT:127.0.0.1" --resolve "www.$DOMAIN:$HTTPS_PORT:127.0.0.1" "$@"; }
status() { https -o /dev/null -w '%{http_code}' "$@"; }
page() { https "https://$DOMAIN:$HTTPS_PORT$1"; }
container() { compose ps -q "$1"; }

wait_healthy() {
    local service="$1" seconds="${2:-180}" id
    for _ in $(seq "$seconds"); do
        id="$(container "$service")"
        [ -n "$id" ] && [ "$(docker inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null)" = "healthy" ] && return 0
        sleep 1
    done
    return 1
}

cleanup() {
    if [ "$started" = "1" ]; then
        if [ "${KEEP:-0}" = "1" ]; then
            log "Stack kept. Remove it with:"
            log "  cd $(pwd) && COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME PERFUMERIA_ENV_FILE=$PERFUMERIA_ENV_FILE docker compose --env-file $PERFUMERIA_ENV_FILE down -v --remove-orphans"
        else
            # Only the perfumeria-smoke project: its containers, network and volumes.
            compose down -v --remove-orphans >/dev/null 2>&1
        fi
    fi
    log "Work directory (report, logs, disposable secrets and backups): $WORK"
    log "Report: $REPORT  (passed=$passed failed=$failed)"
}
trap cleanup EXIT
chmod 700 "$WORK"

# ---------------------------------------------------------------- preflight (nothing changed yet)
for tool in docker curl git sha256sum od ss hostname; do
    command -v "$tool" >/dev/null || die "missing command: $tool"
done
if command -v snap >/dev/null && snap list docker >/dev/null 2>&1; then
    die "Docker is installed as a snap. Use Docker Engine from download.docker.com (see deploy/smoke/UBUNTU.md)."
fi
docker info >/dev/null 2>&1 || die "cannot talk to the Docker daemon (add the user to the docker group or run with sudo)"
version="$(docker compose version --short 2>/dev/null | sed 's/^v//')"
[ -n "$version" ] || die "Docker Compose v2 plugin not found (package docker-compose-plugin)"
[ "$(printf '%s\n2.20.0\n' "$version" | sort -V | head -n1)" = "2.20.0" ] || die "Compose $version is older than 2.20"
if [ -n "$(docker ps -aq --filter label=com.docker.compose.project=perfumeria)$(docker volume ls -q --filter label=com.docker.compose.project=perfumeria)" ]; then
    die "a 'perfumeria' (production) Compose project exists on this host; run the smoke test on a separate VM"
fi
for port in "$HTTP_PORT" "$HTTPS_PORT"; do
    ss -Hltn "sport = :$port" | grep -q . && die "port $port is already in use"
done
if docker network inspect $(docker network ls -q) -f '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null | grep -q "$NET\." \
   && ! docker network inspect perfumeria-smoke_edge >/dev/null 2>&1; then
    die "subnet $NET.0/24 is used by another Docker network; set SMOKE_SUBNET_PREFIX"
fi
ip route 2>/dev/null | grep -q "^$NET\." && ! docker network inspect perfumeria-smoke_edge >/dev/null 2>&1 \
    && die "subnet $NET.0/24 overlaps a host route; set SMOKE_SUBNET_PREFIX"

log "Ubuntu: $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"), Docker $(docker version -f '{{.Server.Version}}'), Compose $version"
log "Commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown) on $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown); token marker $TOKEN"

cat > "$PERFUMERIA_ENV_FILE" <<EOF
COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME
SITE_DOMAIN=$DOMAIN
ACME_EMAIL=smoke@example.invalid
RELEASE=smoke
DJANGO_ALLOWED_HOSTS=$DOMAIN
DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMAIN:$HTTPS_PORT
SECRET_KEY=$(secret)$(secret)
POSTGRES_DB=perfumeria
POSTGRES_USER=perfumeria
POSTGRES_PASSWORD=$(secret)
STORE_MODE=prelaunch
EMAIL_DELIVERY=disabled
INTEREST_EMAIL_DELIVERY=0
HTTP_BIND=127.0.0.1:$HTTP_PORT
HTTPS_BIND=127.0.0.1:$HTTPS_PORT
EDGE_SUBNET=$NET.0/24
EDGE_IP_RANGE=$NET.128/25
EDGE_CADDY_IP=$NET.2
BACKUP_DIR=$WORK/backups
BACKUP_KEEP_DAYS=14
EOF
chmod 600 "$PERFUMERIA_ENV_FILE"

# Refuse to continue unless Compose really resolves to the smoke project.
resolved="$(compose config 2>/dev/null | sed -n 's/^name: //p' | head -n1)"
[ "$resolved" = "perfumeria-smoke" ] || die "Compose resolved project '$resolved' instead of perfumeria-smoke"
started=1
compose down -v --remove-orphans >/dev/null 2>&1   # leftovers of an earlier KEEP=1 run, smoke project only

# ---------------------------------------------------------------- build and start
check "compose config is valid" compose config -q
compose build --pull >"$WORK/build.log" 2>&1 && ok "image builds" || { ko "image builds (see $WORK/build.log)"; exit 1; }
check "image runs as non-root" test "$(docker run --rm --entrypoint id perfumeria-web:smoke -u)" != "0"
check "image contains no env.py, .env, sqlite or media" \
    docker run --rm --entrypoint sh perfumeria-web:smoke -c '! ls env.py .env db.sqlite3 media/* 2>/dev/null | grep -q .'

compose up -d db >/dev/null 2>&1
check "postgres becomes healthy" wait_healthy db 90

# Recovery: web must refuse to start before migrations and with a non-prelaunch mode.
compose up -d web >/dev/null 2>&1
sleep 20
check "web refuses to serve with pending migrations" sh -c "docker compose --env-file '$PERFUMERIA_ENV_FILE' logs web 2>&1 | grep -q 'Unapplied migrations'"
compose stop web >/dev/null 2>&1
check "web refuses STORE_MODE=live" sh -c "! docker compose --env-file '$PERFUMERIA_ENV_FILE' run --rm --no-deps -T -e STORE_MODE=live web serve"
compose run --rm -T web python manage.py migrate --noinput >"$WORK/migrate.log" 2>&1 && ok "migrations apply" || ko "migrations apply (see $WORK/migrate.log)"

compose up -d >/dev/null 2>&1
check "web becomes healthy" wait_healthy web 180
check "caddy becomes healthy" wait_healthy caddy 120
for _ in $(seq 60); do compose cp caddy:/data/caddy/pki/authorities/local/root.crt "$WORK/root.crt" >/dev/null 2>&1 && break; sleep 2; done
check "internal CA certificate available" test -s "$WORK/root.crt"
check "migrations fully applied" manage migrate --check

# ---------------------------------------------------------------- exposure
networks() { docker inspect -f '{{range $name, $net := .NetworkSettings.Networks}}{{$name}} {{end}}' "$(container "$1")"; }
check "db publishes no ports" test -z "$(compose port db 5432 2>/dev/null)"
check "web publishes no ports" test -z "$(compose port web 8000 2>/dev/null)"
check "db only on the internal backend network" test "$(networks db)" = "perfumeria-smoke_backend "
check "backend network is internal" test "$(docker network inspect -f '{{.Internal}}' perfumeria-smoke_backend)" = "true"
check "caddy not attached to the backend network" sh -c "! echo '$(networks caddy)' | grep -q backend"
check "caddy bound to 127.0.0.1 only in this test" sh -c "docker compose --env-file '$PERFUMERIA_ENV_FILE' port caddy 443 | grep -q '^127.0.0.1:'"
lan_ip="$(hostname -I | awk '{print $1}')"
check "nothing answers on the VM address $lan_ip:$HTTPS_PORT" sh -c "[ -n '$lan_ip' ] && ! curl -sk --max-time 3 -o /dev/null 'https://$lan_ip:$HTTPS_PORT/'"
check "gunicorn not reachable from the host loopback" sh -c "! curl -s --max-time 3 -o /dev/null http://127.0.0.1:8000/"

# ---------------------------------------------------------------- HTTPS, headers, cookies
headers="$(https -I "https://$DOMAIN:$HTTPS_PORT/accounts/login/" | tr -d '\r')"
printf '%s\n' "$headers" > "$WORK/login-headers.txt"
has_header() { printf '%s\n' "$headers" | grep -qi "^$1"; }
check "TLS verifies against Caddy CA and login returns 200" sh -c "printf '%s\n' \"\$1\" | head -n1 | grep -q ' 200'" _ "$headers"
for header in "strict-transport-security: max-age=31536000" "x-frame-options: DENY" "x-content-type-options: nosniff" "referrer-policy: strict-origin-when-cross-origin" "cross-origin-opener-policy: same-origin"; do
    check "header $header" has_header "$header"
done
check "no Server header" sh -c "! printf '%s\n' \"\$1\" | grep -qi '^server:'" _ "$headers"
csrf_cookie="$(printf '%s\n' "$headers" | grep -i '^set-cookie: csrftoken' || true)"
check "csrftoken cookie is Secure" sh -c "echo \"\$1\" | grep -qi '; *secure'" _ "$csrf_cookie"
check "csrftoken cookie is SameSite=Lax" sh -c "echo \"\$1\" | grep -qi 'samesite=lax'" _ "$csrf_cookie"
redirect="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' --resolve "$DOMAIN:$HTTP_PORT:127.0.0.1" "http://$DOMAIN:$HTTP_PORT/")"
check "HTTP redirects to HTTPS ($redirect)" sh -c "echo '$redirect' | grep -qE '^30[18] https://$DOMAIN'"
check "www redirects to apex" test "$(https -o /dev/null -w '%{redirect_url}' "https://www.$DOMAIN:$HTTPS_PORT/")" = "https://$DOMAIN/"
check "CSRF rejects POST without token (403)" test "$(status -X POST -d 'login=a&password=b' "https://$DOMAIN:$HTTPS_PORT/accounts/login/")" = "403"

# ---------------------------------------------------------------- public surface
check "home 200" test "$(status "https://$DOMAIN:$HTTPS_PORT/")" = "200"
check "/checkout/ is 403" test "$(status "https://$DOMAIN:$HTTPS_PORT/checkout/")" = "403"
check "/healthz/ hidden by Caddy (404)" test "$(status "https://$DOMAIN:$HTTPS_PORT/healthz/")" = "404"
check "/media/ hidden by Caddy (404)" test "$(status "https://$DOMAIN:$HTTPS_PORT/media/ER1173710781.jpeg")" = "404"
check "static served by Caddy with cache headers" sh -c "printf '%s' \"\$1\" | tr -d '\r' | grep -qi '^cache-control: public'" _ "$(https -I "https://$DOMAIN:$HTTPS_PORT/static/css/storefront.css")"
check "no launch form while mail is disabled" sh -c "! printf '%s' \"\$1\" | grep -q 'name=\"consent\"'" _ "$(page /)"
check "no sign-up link while mail is disabled" sh -c "! printf '%s' \"\$1\" | grep -q '/accounts/signup/'" _ "$(page /)"
check "outgoing mail backend is dummy" pyshell 'from django.conf import settings as s; assert s.EMAIL_BACKEND.endswith("dummy.EmailBackend") and not s.NOTICE_SIGNUPS_OPEN and not s.ACCOUNT_SIGNUPS_OPEN and not s.INTEREST_EMAIL_DELIVERY'
check "no Stripe keys in the container" sh -c "! docker compose --env-file '$PERFUMERIA_ENV_FILE' exec -T web env | grep -q '^STRIPE_'"

# ---------------------------------------------------------------- unapproved catalog stays hidden
manage load_reference_catalog --apply >"$WORK/catalog.log" 2>&1 && ok "reference catalog loaded as drafts" || ko "reference catalog loaded as drafts"
slug="$(pyshell 'from products.models import Product; print(Product.objects.order_by("pk").values_list("slug", flat=True).first())' 2>/dev/null | tail -n1 | tr -d '\r')"
check "265 drafts, none published" pyshell 'from products.models import Product; assert Product.objects.count() == 265 and not Product.objects.published().exists()'
check "draft product page is 404 ($slug)" sh -c "[ -n '$slug' ] && [ \"\$1\" = 404 ]" _ "$(status "https://$DOMAIN:$HTTPS_PORT/products/$slug/")"
check "catalog lists no drafts" sh -c "! printf '%s' \"\$1\" | grep -q 'eo-perfume-card'" _ "$(page /products/)"
check "sitemap lists no drafts" sh -c "! printf '%s' \"\$1\" | grep -q '/products/$slug/'" _ "$(page /sitemap.xml)"
check "search API returns no drafts" sh -c "printf '%s' \"\$1\" | grep -q '\"results\": *\[\]'" _ "$(page '/products/api/search/?q=ad')"

# ---------------------------------------------------------------- tokens never logged
https -o /dev/null "https://$DOMAIN:$HTTPS_PORT/avisos/lanzamiento/confirmar/$TOKEN/"
https -o /dev/null "https://$DOMAIN:$HTTPS_PORT/avisos/lanzamiento/baja/$TOKEN/"
https -o /dev/null "https://$DOMAIN:$HTTPS_PORT/accounts/confirm-email/$TOKEN/"
sleep 3
compose exec -T caddy cat /var/log/caddy/access.log > "$WORK/caddy-access.log" 2>/dev/null
compose logs --no-color > "$WORK/compose.log" 2>&1
check "access log written" test -s "$WORK/caddy-access.log"
check "token absent from Caddy access log" sh -c "! grep -q '$TOKEN' '$WORK/caddy-access.log'"
check "token absent from container logs" sh -c "! grep -q '$TOKEN' '$WORK/compose.log'"
check "redaction marker present" grep -q 'redacted' "$WORK/caddy-access.log"
check "client IPs masked in access log (all end in .0)" sh -c "grep -oE '\"remote_ip\":\"[0-9.]+\"' '$WORK/caddy-access.log' | grep -q . && ! grep -oE '\"remote_ip\":\"[0-9.]+\"' '$WORK/caddy-access.log' | grep -vqE '\\.0\"$'"
check "docker log rotation configured" sh -c "docker inspect -f '{{json .HostConfig.LogConfig}}' '$(container web)' | grep -q '\"max-size\":\"10m\"'"

# ---------------------------------------------------------------- restart and persistence
pyshell 'from home.models import Subscriber; Subscriber.objects.create(email="persist@example.invalid")' >/dev/null 2>&1
web_id="$(container web)"
before="$(docker inspect -f '{{.RestartCount}}' "$web_id")"
compose exec -T web sh -c 'kill -TERM 1' >/dev/null 2>&1
sleep 8
check "web restarts automatically after its process exits" wait_healthy web 150
check "restart counter increased" test "$(docker inspect -f '{{.RestartCount}}' "$web_id")" -gt "$before"
compose restart web >/dev/null 2>&1
check "web healthy after compose restart" wait_healthy web 150
compose down >/dev/null 2>&1
compose up -d >/dev/null 2>&1
check "stack healthy after down/up" wait_healthy caddy 180
check "data persisted across down/up" pyshell 'from home.models import Subscriber; from products.models import Product; assert Subscriber.objects.filter(email="persist@example.invalid").exists() and Product.objects.count() == 265'

# ---------------------------------------------------------------- backup and restore (disposable data only)
./backup/backup.sh >"$WORK/backup.log" 2>&1 && ok "backup completes" || ko "backup completes (see $WORK/backup.log)"
run_dir="$(find "$WORK/backups" -mindepth 1 -maxdepth 1 -type d -name '20*Z' 2>/dev/null | sort | tail -n1)"
check "backup run directory created" test -n "$run_dir"
check "backup files are owner-only (600)" sh -c "[ -n '$run_dir' ] && [ -z \"\$(find '$run_dir' -type f ! -perm 600)\" ]"
check "backup contains no plaintext DB password" sh -c "[ -n '$run_dir' ] && ! grep -rqF \"\$(grep '^POSTGRES_PASSWORD=' '$PERFUMERIA_ENV_FILE' | cut -d= -f2-)\" '$run_dir'"
./backup/restore.sh --verify "$run_dir" >"$WORK/restore-verify.log" 2>&1 && ok "restore --verify into throwaway database" || ko "restore --verify (see $WORK/restore-verify.log)"
pyshell 'from home.models import Subscriber; Subscriber.objects.create(email="after-backup@example.invalid")' >/dev/null 2>&1
printf '%s\n' "$DOMAIN" | ./backup/restore.sh --replace-production "$run_dir" >"$WORK/restore.log" 2>&1 && ok "full restore on the smoke stack" || ko "full restore (see $WORK/restore.log)"
check "web healthy after restore" wait_healthy web 180
check "restored state matches the backup" pyshell 'from home.models import Subscriber; from products.models import Product; assert Subscriber.objects.filter(email="persist@example.invalid").exists() and not Subscriber.objects.filter(email="after-backup@example.invalid").exists() and Product.objects.count() == 265'

log "----"
if [ "$failed" -eq 0 ]; then
    log "RESULT: ALL $passed CHECKS PASSED"
else
    log "RESULT: $failed OF $((passed + failed)) CHECKS FAILED"
fi
[ "$failed" -eq 0 ]
