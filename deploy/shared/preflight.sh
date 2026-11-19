#!/usr/bin/env bash
# Read-only checks before deploying Perfumería El Buen Olor on the VPS shared with
# Foro IA al Día. Starts, stops, writes and deletes nothing.
#
#   cd deploy && ./shared/preflight.sh               # DNS mismatch is a warning
#   REQUIRE_DNS=1 ./shared/preflight.sh              # DNS must already point here (before the Caddy step)
#
# Exit code: 0 = no blocking issue, 1 = at least one FAIL.
set -uo pipefail
source "$(dirname "$0")/lib.sh"

fails=0
warns=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() { fails=$((fails + 1)); printf 'FAIL  %s\n' "$*"; }
warn() { warns=$((warns + 1)); printf 'WARN  %s\n' "$*"; }
info() { printf 'INFO  %s\n' "$*"; }

echo "== Host"
info "$(. /etc/os-release && echo "$PRETTY_NAME"), kernel $(uname -r)"
for tool in docker curl getent ip awk sha256sum; do
    command -v "$tool" >/dev/null || fail "missing command: $tool"
done
docker info >/dev/null 2>&1 && pass "Docker daemon reachable" || fail "Docker daemon not reachable (docker group or sudo)"
version="$(docker compose version --short 2>/dev/null | sed 's/^v//')"
if [ -n "$version" ] && [ "$(printf '%s\n2.20.0\n' "$version" | sort -V | head -n1)" = "2.20.0" ]; then
    pass "Docker Compose $version"
else
    fail "Docker Compose v2.20+ required (found '${version:-none}')"
fi
available_mb="$(free -m | awk '/^Mem:/ {print $7}')"
[ "${available_mb:-0}" -ge 2048 ] && pass "available RAM ${available_mb} MiB (stack limit ~1.8 GiB)" || fail "available RAM ${available_mb:-?} MiB < 2048 MiB"
docker_root="$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)"
free_gb="$(df -BG --output=avail "$docker_root" 2>/dev/null | tail -n1 | tr -dc '0-9')"
[ "${free_gb:-0}" -ge 10 ] && pass "free disk ${free_gb} GB on $docker_root" || fail "free disk ${free_gb:-?} GB < 10 GB on $docker_root"

echo "== Forum proxy (read-only)"
if [ "$(docker inspect -f '{{.State.Running}}' "$CADDY" 2>/dev/null)" = "true" ]; then
    pass "$CADDY is running ($(docker inspect -f '{{.Config.Image}}' "$CADDY"))"
else
    fail "$CADDY is not running or does not exist"
fi
if docker inspect -f '{{range $name, $net := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$CADDY" 2>/dev/null | grep -qxF "$EDGE"; then
    pass "$CADDY is attached to $EDGE"
else
    fail "$CADDY is not attached to $EDGE"
fi
ports="$(docker port "$CADDY" 2>/dev/null | tr '\n' ' ')"
info "$CADDY published ports: ${ports:-none}"
echo "$ports" | grep -q '443/tcp' && pass "$CADDY serves 443" || warn "443/tcp not seen on $CADDY"
inside="$(caddy_config_path)"
info "Caddy config inside container: $inside"
if host_file="$(caddy_config_host_path "$inside")"; then
    pass "config comes from bind mount: $host_file"
    if [ -r "$host_file" ]; then
        pass "config readable on host"
        grep -qF "$BEGIN_MARK" "$host_file" && warn "perfumeria block already present in $host_file" || pass "perfumeria block not present yet"
        grep -qE '^\s*admin\s+off' "$host_file" && fail "admin API disabled ('admin off'): reload impossible without restarting Caddy" || pass "admin API not disabled"
        grep -qE "(^|[[:space:]])(www\.)?perfumeriaelbuenolor\.es([[:space:],{]|$)" "$host_file" && ! grep -qF "$BEGIN_MARK" "$host_file" \
            && fail "the forum Caddyfile already mentions perfumeriaelbuenolor.es outside the managed block"
        [ -w "$host_file" ] && info "config writable by $(id -un)" || info "config not writable by $(id -un): the Caddy step will need sudo"
    else
        fail "cannot read $host_file (try with sudo)"
    fi
else
    fail "Caddyfile is not on a bind mount; adding a site would require changing the forum's compose (stop and decide)"
fi

echo "== Shared edge network $EDGE"
if docker network inspect "$EDGE" >/dev/null 2>&1; then
    pass "$EDGE exists (internal=$(docker network inspect -f '{{.Internal}}' "$EDGE"))"
    info "containers on $EDGE:"
    docker network inspect -f '{{range $id, $c := .Containers}}{{println $c.Name}}{{end}}' "$EDGE" | grep -v '^$' | sed 's/^/        /'
    collision=0
    for container in $(docker network inspect -f '{{range $id, $c := .Containers}}{{println $c.Name}}{{end}}' "$EDGE"); do
        case "$container" in "$PROJECT"-*) continue ;; esac
        aliases="$(docker inspect -f "{{with index .NetworkSettings.Networks \"$EDGE\"}}{{range .Aliases}}{{println .}}{{end}}{{range .DNSNames}}{{println .}}{{end}}{{end}}" "$container" 2>/dev/null)"
        if printf '%s\n%s\n' "$container" "$aliases" | grep -qxE 'perfumeria-web|perfumeria-db'; then
            fail "$container already answers to perfumeria-web/perfumeria-db on $EDGE"; collision=1
        fi
    done
    [ "$collision" = 0 ] && pass "no DNS name collision for perfumeria-web on $EDGE"
else
    fail "network $EDGE not found"
fi

echo "== Perfumería project"
if [ -f "$ENV_FILE" ]; then
    pass "env file $ENV_FILE"
    [ "$(stat -c %a "$ENV_FILE")" = "600" ] && pass "env file mode 600" || fail "env file mode $(stat -c %a "$ENV_FILE"), expected 600"
    grep -vE '^[[:space:]]*#' "$ENV_FILE" | grep -q '<' && fail "env file still has <placeholders>"
    for key in RELEASE SECRET_KEY POSTGRES_PASSWORD DJANGO_ALLOWED_HOSTS DJANGO_CSRF_TRUSTED_ORIGINS; do
        [ -n "$(env_value "$key")" ] || fail "env file: $key is empty"
    done
    [ "$(env_value SITE_DOMAIN)" = "$DOMAIN" ] && pass "SITE_DOMAIN=$DOMAIN" || fail "SITE_DOMAIN must be $DOMAIN"
    [ -z "$(env_value PROXY_SERVICE)" ] && grep -q '^PROXY_SERVICE=' "$ENV_FILE" && pass "PROXY_SERVICE empty (scripts never stop the forum proxy)" || fail "PROXY_SERVICE= must be present and empty"
    grep -qE '^(STRIPE_[A-Z_]+|STORE_MODE|EMAIL_DELIVERY|INTEREST_EMAIL_DELIVERY)=.' "$ENV_FILE" \
        && warn "env file sets commerce/mail variables; compose.yaml pins them anyway (prelaunch, disabled)"
    if config="$(pcompose config 2>/dev/null)"; then
        pass "compose configuration resolves"
        [ "$(printf '%s\n' "$config" | sed -n 's/^name: //p' | head -n1)" = "$PROJECT" ] && pass "project name $PROJECT" || fail "project name is not $PROJECT"
        services="$(pcompose config --services 2>/dev/null | sort | tr '\n' ' ')"
        [ "$services" = "perfumeria-db perfumeria-web " ] && pass "services: $services" || fail "unexpected services: $services"
        printf '%s\n' "$config" | grep -qE '^\s+(published|ports):' && fail "compose publishes ports" || pass "no published ports"
        printf '%s\n' "$config" | grep -q 'STORE_MODE: prelaunch' && pass "STORE_MODE pinned to prelaunch" || fail "STORE_MODE is not prelaunch"
        printf '%s\n' "$config" | grep -q 'EMAIL_DELIVERY: disabled' && pass "EMAIL_DELIVERY pinned to disabled" || fail "EMAIL_DELIVERY not disabled"
    else
        fail "docker compose config failed (run: ./shared/preflight.sh after filling the env file)"
    fi
else
    fail "missing $ENV_FILE (copy shared/env.production.example and chmod 600)"
fi
existing="$(docker ps -a --filter "label=com.docker.compose.project=$PROJECT" --format '{{.Names}} ({{.Status}})' | tr '\n' ' ')"
info "existing $PROJECT containers: ${existing:-none}"
volumes="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | tr '\n' ' ')"
info "existing $PROJECT volumes: ${volumes:-none}"
foro_projects="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | sort -u | grep -v '^$' | tr '\n' ' ')"
info "running Compose projects: $foro_projects"

echo "== DNS"
info "host addresses: $(host_addresses | tr '\n' ' ')"
for name in "$DOMAIN" "www.$DOMAIN"; do
    answers="$(getent ahosts "$name" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ')"
    if dns_points_here "$name"; then
        pass "$name -> $answers"
    elif [ "${REQUIRE_DNS:-0}" = "1" ]; then
        fail "$name -> ${answers:-no answer}; must point to this host before the Caddy step"
    else
        warn "$name -> ${answers:-no answer} (not this host yet)"
    fi
done

echo "----"
echo "fails=$fails warns=$warns"
[ "$fails" -eq 0 ]
