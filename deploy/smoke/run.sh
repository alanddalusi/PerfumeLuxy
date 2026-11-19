#!/usr/bin/env bash
# Isolated end-to-end test of the production stack (Phase 6A).
#
# Run on a disposable Linux machine or VM with Docker Engine + Compose v2 (>= 2.20), curl
# and a free 127.0.0.1:18080/18443. Never on the production VPS while it serves traffic.
#
#   cd deploy && ./smoke/run.sh            # run and remove everything afterwards
#   KEEP=1 ./smoke/run.sh                  # keep the stack for inspection
#
# It creates the Compose project "perfumeria-smoke" with random secrets, binds Caddy to
# 127.0.0.1 only, uses Caddy's internal CA for perfumeria.localhost, and never contacts
# real mail, payment or DNS services. Results are written to $WORK/report.txt.
set -uo pipefail

cd "$(dirname "$0")/.."
DOMAIN="perfumeria.localhost"
HTTPS_PORT=18443
HTTP_PORT=18080
WORK="$(mktemp -d)"
REPORT="$WORK/report.txt"
export COMPOSE_PROJECT_NAME="perfumeria-smoke"
export PERFUMERIA_ENV_FILE="$WORK/.env.smoke"
TOKEN="SMOKE6A$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')"
passed=0
failed=0

log() { printf '%s\n' "$*" | tee -a "$REPORT"; }
ok() { passed=$((passed + 1)); log "PASS  $*"; }
ko() { failed=$((failed + 1)); log "FAIL  $*"; }
check() { local name="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$name"; else ko "$name"; fi; }
compose() { docker compose --env-file "$PERFUMERIA_ENV_FILE" "$@"; }
manage() { compose exec -T web python manage.py "$@"; }
secret() { od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; }
https() { curl -sS --max-time 15 --cacert "$WORK/root.crt" --resolve "$DOMAIN:$HTTPS_PORT:127.0.0.1" --resolve "www.$DOMAIN:$HTTPS_PORT:127.0.0.1" "$@"; }
status() { https -o /dev/null -w '%{http_code}' "$@"; }

wait_healthy() {
    local service="$1" seconds="${2:-180}" id
    for _ in $(seq "$seconds"); do
        id="$(compose ps -q "$service")"
        [ -n "$id" ] && [ "$(docker inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null)" = "healthy" ] && return 0
        sleep 1
    done
    return 1
}

cleanup() {
    if [ "${KEEP:-0}" = "1" ]; then
        log "Stack kept. Remove with: COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME PERFUMERIA_ENV_FILE=$PERFUMERIA_ENV_FILE docker compose --env-file $PERFUMERIA_ENV_FILE down -v"
    else
        compose down -v --remove-orphans >/dev/null 2>&1
    fi
    log "Report: $REPORT  (passed=$passed failed=$failed)"
}
trap cleanup EXIT

# ---------------------------------------------------------------- prerequisites
version="$(docker compose version --short 2>/dev/null || true)"
[ -n "$version" ] || { echo "Docker Compose v2 is required." >&2; exit 2; }
command -v curl >/dev/null || { echo "curl is required." >&2; exit 2; }
log "Docker $(docker version -f '{{.Server.Version}}' 2>/dev/null), Compose $version, commit $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

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
EDGE_SUBNET=172.30.99.0/24
EDGE_IP_RANGE=172.30.99.128/25
EDGE_CADDY_IP=172.30.99.2
BACKUP_DIR=$WORK/backups
BACKUP_KEEP_DAYS=14
EOF
chmod 600 "$PERFUMERIA_ENV_FILE"

# ---------------------------------------------------------------- build and start
check "compose config is valid" compose config -q
compose build --pull >"$WORK/build.log" 2>&1 && ok "image builds" || { ko "image builds (see $WORK/build.log)"; exit 1; }
check "image runs as non-root" test "$(docker run --rm --entrypoint id perfumeria-web:smoke -u)" != "0"
check "image contains no env.py, .env, sqlite or media" \
    docker run --rm --entrypoint sh perfumeria-web:smoke -c '! ls env.py .env db.sqlite3 media/* catalog_assets 2>/dev/null | grep -q .'

compose up -d db >/dev/null 2>&1
check "postgres becomes healthy" wait_healthy db 90

# Recovery: web must refuse to start before migrations and with a non-prelaunch mode.
compose up -d web >/dev/null 2>&1
sleep 15
check "web refuses to serve with pending migrations" sh -c "docker compose --env-file '$PERFUMERIA_ENV_FILE' logs web 2>&1 | grep -q 'Unapplied migrations'"
compose stop web >/dev/null 2>&1
check "web refuses STORE_MODE=live" sh -c "! docker compose --env-file '$PERFUMERIA_ENV_FILE' run --rm --no-deps -e STORE_MODE=live web serve"
compose run --rm web python manage.py migrate --noinput >"$WORK/migrate.log" 2>&1 && ok "migrations apply" || ko "migrations apply"

compose up -d >/dev/null 2>&1
check "web becomes healthy" wait_healthy web 180
check "caddy becomes healthy" wait_healthy caddy 120
for _ in $(seq 60); do compose cp caddy:/data/caddy/pki/authorities/local/root.crt "$WORK/root.crt" >/dev/null 2>&1 && break; sleep 2; done
check "internal CA certificate available" test -s "$WORK/root.crt"
check "migrations fully applied" manage migrate --check

# ---------------------------------------------------------------- exposure
check "db publishes no ports" test -z "$(compose port db 5432 2>/dev/null)"
check "web publishes no ports" test -z "$(compose port web 8000 2>/dev/null)"
check "caddy bound to 127.0.0.1 only in this test" sh -c "docker compose --env-file '$PERFUMERIA_ENV_FILE' port caddy 443 | grep -q '^127.0.0.1:'"
check "caddy cannot reach postgres (separate network)" sh -c "! docker compose --env-file '$PERFUMERIA_ENV_FILE' exec -T caddy nc -z -w 3 db 5432"
check "gunicorn not reachable from host" sh -c "! curl -s --max-time 3 http://127.0.0.1:8000/"

# ---------------------------------------------------------------- HTTPS, headers, cookies
headers="$(https -sI "https://$DOMAIN:$HTTPS_PORT/accounts/login/")"
printf '%s\n' "$headers" > "$WORK/login-headers.txt"
check "TLS verifies against Caddy CA and login returns 200" sh -c "printf '%s' \"\$1\" | head -1 | grep -q ' 200'" _ "$headers"
for header in "strict-transport-security: max-age=31536000" "x-frame-options: DENY" "x-content-type-options: nosniff" "referrer-policy: strict-origin-when-cross-origin" "cross-origin-opener-policy: same-origin"; do
    check "header $header" sh -c "printf '%s' \"\$1\" | tr -d '\r' | grep -qi \"^\$2\"" _ "$headers" "$header"
done
check "no Server header" sh -c "! printf '%s' \"\$1\" | grep -qi '^server:'" _ "$headers"
check "csrftoken cookie is Secure and SameSite=Lax" sh -c "printf '%s' \"\$1\" | grep -i '^set-cookie: csrftoken' | grep -qi 'secure' && printf '%s' \"\$1\" | grep -i '^set-cookie: csrftoken' | grep -qi 'samesite=lax'" _ "$headers"
redirect="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' --resolve "$DOMAIN:$HTTP_PORT:127.0.0.1" "http://$DOMAIN:$HTTP_PORT/")"
check "HTTP redirects to HTTPS ($redirect)" sh -c "echo '$redirect' | grep -qE '^30[18] https://$DOMAIN'"
check "www redirects to apex" sh -c "[ \"\$(curl -s -o /dev/null -w '%{redirect_url}' --cacert '$WORK/root.crt' --resolve 'www.$DOMAIN:$HTTPS_PORT:127.0.0.1' 'https://www.$DOMAIN:$HTTPS_PORT/')\" = 'https://$DOMAIN/' ]"
check "CSRF rejects POST without token (403)" test "$(status -X POST -d 'email=a@example.invalid' "https://$DOMAIN:$HTTPS_PORT/accounts/login/")" = "403"

# ---------------------------------------------------------------- public surface
check "home 200" test "$(status "https://$DOMAIN:$HTTPS_PORT/")" = "200"
check "/checkout/ is 403" test "$(status "https://$DOMAIN:$HTTPS_PORT/checkout/")" = "403"
check "/healthz/ hidden by Caddy (404)" test "$(status "https://$DOMAIN:$HTTPS_PORT/healthz/")" = "404"
check "/media/ hidden by Caddy (404)" test "$(status "https://$DOMAIN:$HTTPS_PORT/media/ER1173710781.jpeg")" = "404"
check "static served by Caddy" sh -c "curl -sS --cacert '$WORK/root.crt' --resolve '$DOMAIN:$HTTPS_PORT:127.0.0.1' -I 'https://$DOMAIN:$HTTPS_PORT/static/css/storefront.css' | tr -d '\r' | grep -qi '^cache-control: public'"
check "no launch form while mail is disabled" sh -c "! curl -sS --cacert '$WORK/root.crt' --resolve '$DOMAIN:$HTTPS_PORT:127.0.0.1' 'https://$DOMAIN:$HTTPS_PORT/' | grep -q 'name=\"consent\"'"
check "outgoing mail backend is dummy" sh -c "docker compose --env-file '$PERFUMERIA_ENV_FILE' exec -T web python manage.py shell -c 'from django.conf import settings as s; assert s.EMAIL_BACKEND.endswith(\"dummy.EmailBackend\") and not s.NOTICE_SIGNUPS_OPEN and not s.INTEREST_EMAIL_DELIVERY'"
check "no Stripe keys in the container" sh -c "! docker compose --env-file '$PERFUMERIA_ENV_FILE' exec -T web env | grep -q '^STRIPE_'"

# ---------------------------------------------------------------- unapproved catalog stays hidden
manage load_reference_catalog --apply >"$WORK/catalog.log" 2>&1 && ok "reference catalog loaded as drafts" || ko "reference catalog loaded as drafts"
slug="$(manage shell -c 'from products.models import Product; print(Product.objects.order_by("pk").values_list("slug", flat=True).first())' 2>/dev/null | tail -n1 | tr -d '\r')"
check "published count is 0" sh -c "docker compose --env-file '$PERFUMERIA_ENV_FILE' exec -T web python manage.py shell -c 'from products.models import Product; assert Product.objects.count() == 265 and not Product.objects.published().exists()'"
check "draft product page is 404" test "$(status "https://$DOMAIN:$HTTPS_PORT/products/$slug/")" = "404"
check "catalog lists no drafts" sh -c "! curl -sS --cacert '$WORK/root.crt' --resolve '$DOMAIN:$HTTPS_PORT:127.0.0.1' 'https://$DOMAIN:$HTTPS_PORT/products/' | grep -q 'eo-perfume-card'"
check "sitemap lists no drafts" sh -c "! curl -sS --cacert '$WORK/root.crt' --resolve '$DOMAIN:$HTTPS_PORT:127.0.0.1' 'https://$DOMAIN:$HTTPS_PORT/sitemap.xml' | grep -q '/products/$slug/'"
check "search API returns no drafts" sh -c "curl -sS --cacert '$WORK/root.crt' --resolve '$DOMAIN:$HTTPS_PORT:127.0.0.1' 'https://$DOMAIN:$HTTPS_PORT/products/api/search/?q=ad' | grep -q '\"results\": *\[\]'"

# ---------------------------------------------------------------- tokens never logged
https -o /dev/null "https://$DOMAIN:$HTTPS_PORT/avisos/lanzamiento/confirmar/$TOKEN/"
https -o /dev/null "https://$DOMAIN:$HTTPS_PORT/avisos/lanzamiento/baja/$TOKEN/"
https -o /dev/null "https://$DOMAIN:$HTTPS_PORT/accounts/confirm-email/$TOKEN/"
sleep 2
compose exec -T caddy cat /var/log/caddy/access.log > "$WORK/caddy-access.log" 2>/dev/null
compose logs --no-color > "$WORK/compose.log" 2>&1
check "access log written" test -s "$WORK/caddy-access.log"
check "token absent from Caddy access log" sh -c "! grep -q '$TOKEN' '$WORK/caddy-access.log'"
check "token absent from container logs" sh -c "! grep -q '$TOKEN' '$WORK/compose.log'"
check "redaction marker present" grep -q 'redacted' "$WORK/caddy-access.log"
check "client IPs masked in access log" sh -c "! grep -q '\"remote_ip\":\"127.0.0.1\"' '$WORK/caddy-access.log'"
check "docker log rotation configured" sh -c "docker inspect -f '{{json .HostConfig.LogConfig}}' \$(docker compose --env-file '$PERFUMERIA_ENV_FILE' ps -q web) | grep -q '\"max-size\":\"10m\"'"

# ---------------------------------------------------------------- restart and persistence
manage shell -c 'from home.models import Subscriber; Subscriber.objects.create(email="persist@example.invalid")' >/dev/null 2>&1
web_id="$(compose ps -q web)"
before="$(docker inspect -f '{{.RestartCount}}' "$web_id")"
compose exec -T web sh -c 'kill -TERM 1' >/dev/null 2>&1
sleep 5
check "web restarts automatically after its process exits" wait_healthy web 120
check "restart counter increased" test "$(docker inspect -f '{{.RestartCount}}' "$web_id")" -gt "$before"
compose restart web >/dev/null 2>&1
check "web healthy after compose restart" wait_healthy web 120
compose down >/dev/null 2>&1
compose up -d >/dev/null 2>&1
check "stack healthy after down/up" wait_healthy caddy 180
check "data persisted across down/up" sh -c "docker compose --env-file '$PERFUMERIA_ENV_FILE' exec -T web python manage.py shell -c 'from home.models import Subscriber; from products.models import Product; assert Subscriber.objects.filter(email=\"persist@example.invalid\").exists() and Product.objects.count() == 265'"

# ---------------------------------------------------------------- backup and restore (disposable data only)
./backup/backup.sh >"$WORK/backup.log" 2>&1 && ok "backup completes" || ko "backup completes (see $WORK/backup.log)"
run_dir="$(find "$WORK/backups" -mindepth 1 -maxdepth 1 -type d -name '20*Z' | sort | tail -n1)"
check "backup files are owner-only (600)" sh -c "[ -n '$run_dir' ] && [ -z \"\$(find '$run_dir' -type f ! -perm 600)\" ]"
check "backup contains no plaintext DB password" sh -c "! grep -rqF \"\$(grep '^POSTGRES_PASSWORD=' '$PERFUMERIA_ENV_FILE' | cut -d= -f2-)\" '$run_dir'"
./backup/restore.sh --verify "$run_dir" >"$WORK/restore-verify.log" 2>&1 && ok "restore --verify into throwaway database" || ko "restore --verify (see $WORK/restore-verify.log)"
manage shell -c 'from home.models import Subscriber; Subscriber.objects.create(email="after-backup@example.invalid")' >/dev/null 2>&1
printf '%s\n' "$DOMAIN" | ./backup/restore.sh --replace-production "$run_dir" >"$WORK/restore.log" 2>&1 && ok "full restore on the smoke stack" || ko "full restore (see $WORK/restore.log)"
check "web healthy after restore" wait_healthy web 180
check "restored state matches the backup" sh -c "docker compose --env-file '$PERFUMERIA_ENV_FILE' exec -T web python manage.py shell -c 'from home.models import Subscriber; from products.models import Product; assert Subscriber.objects.filter(email=\"persist@example.invalid\").exists() and not Subscriber.objects.filter(email=\"after-backup@example.invalid\").exists() and Product.objects.count() == 265'"

log "----"
log "passed=$passed failed=$failed"
[ "$failed" -eq 0 ]
