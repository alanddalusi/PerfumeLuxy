#!/usr/bin/env bash
# Read-only audit of the shared VPS. Needs nothing from this repository on the server and
# writes nothing there: no files, containers, networks or volumes are created or changed.
# Prints to stdout; the Caddyfile content itself is not printed (only its site addresses).
#
#   ssh <user>@<vps> 'bash -s' < deploy/shared/audit-readonly.sh > audit-vps.txt
#   (if the Caddyfile is only readable by root: ssh -t <user>@<vps> 'sudo bash -s' < ...)
set -uo pipefail
export LC_ALL=C

CADDY="${SHARED_PROXY_CONTAINER:-foroia-production-caddy-1}"
EDGE="${SHARED_EDGE_NETWORK:-foroia-production_edge}"
DOMAIN="perfumeriaelbuenolor.es"
fails=0; warns=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() { fails=$((fails + 1)); printf 'FAIL  %s\n' "$*"; }
warn() { warns=$((warns + 1)); printf 'WARN  %s\n' "$*"; }
info() { printf 'INFO  %s\n' "$*"; }
section() { printf '\n== %s\n' "$*"; }

section "Host"
info "$(. /etc/os-release && echo "$PRETTY_NAME"), kernel $(uname -r), uptime: $(uptime -p 2>/dev/null)"
info "user $(id -un), groups: $(id -Gn)"
docker info >/dev/null 2>&1 && pass "Docker daemon reachable ($(docker version -f '{{.Server.Version}}'))" || { fail "Docker daemon not reachable"; exit 1; }
info "Docker Compose $(docker compose version --short 2>/dev/null || echo 'not found')"
free -m | awk '/^Mem:/ {printf "INFO  memory MiB: total %s, used %s, available %s\n", $2, $3, $7} /^Swap:/ {printf "INFO  swap MiB: total %s, used %s\n", $2, $3}'
available_mb="$(free -m | awk '/^Mem:/ {print $7}')"
[ "${available_mb:-0}" -ge 2048 ] && pass "available RAM ${available_mb} MiB (minimum 2048)" || fail "available RAM ${available_mb:-?} MiB < 2048"
docker_root="$(docker info -f '{{.DockerRootDir}}')"
df -h / "$docker_root" 2>/dev/null | sed 's/^/INFO  /'
free_gb="$(df -BG --output=avail "$docker_root" | tail -n1 | tr -dc '0-9')"
[ "${free_gb:-0}" -ge 10 ] && pass "free disk ${free_gb} GB on $docker_root" || fail "free disk ${free_gb:-?} GB on $docker_root"
info "load average: $(cut -d' ' -f1-3 /proc/loadavg), CPUs: $(nproc)"
docker system df 2>/dev/null | sed 's/^/INFO  /'

section "Containers"
docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Label "com.docker.compose.project"}}' \
    | awk -F'|' '{printf "INFO  %-40s %-35s %-28s project=%s\n", $1, $2, $3, $4}'
unhealthy="$(docker ps --filter health=unhealthy --format '{{.Names}}' | tr '\n' ' ')"
[ -z "$unhealthy" ] && pass "no unhealthy containers" || warn "unhealthy: $unhealthy"
for c in $(docker ps --format '{{.Names}}'); do
    info "$(docker inspect -f '{{.Name}} restarts={{.RestartCount}} started={{.State.StartedAt}} mem_limit={{.HostConfig.Memory}} cpus={{.HostConfig.NanoCpus}}' "$c" | sed 's#^/##')"
done
docker stats --no-stream --format 'INFO  stats {{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}' 2>/dev/null

section "Forum proxy $CADDY"
if [ "$(docker inspect -f '{{.State.Running}}' "$CADDY" 2>/dev/null)" != "true" ]; then
    fail "$CADDY not running"; echo "fails=$fails warns=$warns"; exit 1
fi
pass "$CADDY running, image $(docker inspect -f '{{.Config.Image}}' "$CADDY"), $(docker exec "$CADDY" caddy version 2>/dev/null | head -n1)"
info "entrypoint/args: $(docker inspect -f '{{.Path}} {{join .Args " "}}' "$CADDY")"
info "restart policy: $(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$CADDY")"
info "published ports: $(docker port "$CADDY" | tr '\n' ' ')"
docker port "$CADDY" | grep -q '^443/tcp -> \[::\]' && info "443 also published on IPv6" || info "443 not published on IPv6 (no AAAA record needed)"
info "networks: $(docker inspect -f '{{range $n, $v := .NetworkSettings.Networks}}{{$n}}={{$v.IPAddress}} {{end}}' "$CADDY")"
docker inspect -f '{{range $n, $v := .NetworkSettings.Networks}}{{println $n}}{{end}}' "$CADDY" | grep -qxF "$EDGE" \
    && pass "$CADDY attached to $EDGE" || fail "$CADDY not attached to $EDGE"
echo "INFO  mounts:"
docker inspect -f '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} rw={{.RW}}{{println}}{{end}}' "$CADDY" | grep -v '^$' | sed 's/^/        /'

config="$(docker inspect -f '{{range .Args}}{{println .}}{{end}}' "$CADDY" | awk 'p == "--config" {print; f = 1; exit} {p = $0} END {if (!f) print "/etc/caddy/Caddyfile"}')"
info "config in container: $config"
host_file=""
while IFS='|' read -r type source destination; do
    [ "$type" = bind ] || continue
    if [ "$config" = "$destination" ]; then host_file="$source"; mount_kind="file"; break; fi
    case "$config" in "$destination"/*) host_file="$source${config#"$destination"}"; mount_kind="directory"; break ;; esac
done < <(docker inspect -f '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}{{println}}{{end}}' "$CADDY")
if [ -n "$host_file" ]; then
    pass "Caddyfile from a $mount_kind bind mount: $host_file"
    if [ -r "$host_file" ]; then
        info "host file: $(stat -c 'inode=%i mode=%a owner=%U:%G size=%s modified=%y' "$host_file")"
        info "sha256: $(sha256sum "$host_file" | cut -d' ' -f1)"
        inode_in="$(docker exec "$CADDY" stat -c %i "$config" 2>/dev/null)"
        inode_host="$(stat -c %i "$host_file")"
        if [ "$mount_kind" = file ]; then
            [ "$inode_in" = "$inode_host" ] && pass "container sees the same inode ($inode_host): in-place appends are visible" \
                || fail "inode differs (host $inode_host, container $inode_in): the file was replaced after the container started; appends would not be visible"
        else
            pass "directory mount: changes to the file are visible in the container"
        fi
        echo "INFO  site addresses in the Caddyfile:"
        grep -nE '^[^#[:space:]][^{]*\{[[:space:]]*$' "$host_file" | sed 's/[[:space:]]*{[[:space:]]*$//; s/^/        /'
        grep -nE '^[[:space:]]*import[[:space:]]' "$host_file" | sed 's/^/INFO  import: /'
        grep -qE '^[[:space:]]*admin[[:space:]]+off' "$host_file" && fail "admin API disabled (admin off)" || pass "admin API not disabled in the Caddyfile"
        grep -nE '^[[:space:]]*admin[[:space:]]' "$host_file" | sed 's/^/INFO  admin directive: /'
        grep -qE 'perfumeriaelbuenolor' "$host_file" && warn "Caddyfile already mentions perfumeriaelbuenolor" || pass "no perfumeriaelbuenolor entries yet"
        grep -qE '^[[:space:]]*(local_certs|acme_ca|cert_issuer)' "$host_file" && info "custom certificate issuer settings present: $(grep -E '^[[:space:]]*(local_certs|acme_ca|cert_issuer)' "$host_file" | tr -s ' ' | tr '\n' ';')"
        [ -w "$host_file" ] && info "writable by $(id -un)" || info "not writable by $(id -un) (the apply step needs sudo)"
    else
        warn "cannot read $host_file as $(id -un); rerun with sudo for the file checks"
    fi
else
    fail "Caddyfile is not on a bind mount (baked into the image or in a volume)"
fi
docker exec "$CADDY" caddy validate --config "$config" --adapter caddyfile >/dev/null 2>&1 \
    && pass "current configuration validates inside $CADDY" || fail "current configuration does not validate inside $CADDY"
# Caddy's default admin address localhost:2019 is bound to 127.0.0.1. BusyBox wget may try ::1
# first for "localhost", so probe the IPv4 loopback explicitly (the caddy CLI tries both).
admin_addr="$(docker exec "$CADDY" sh -c 'echo ${CADDY_ADMIN:-127.0.0.1:2019}' 2>/dev/null | sed 's/^localhost:/127.0.0.1:/')"
docker exec "$CADDY" wget -q -O /dev/null "http://${admin_addr:-127.0.0.1:2019}/config/" 2>/dev/null \
    && pass "admin API answers at ${admin_addr:-127.0.0.1:2019} inside the container: graceful reload without restart is possible" \
    || fail "admin API not reachable at ${admin_addr:-127.0.0.1:2019}: reload would fail (check the admin directive)"

section "Shared network $EDGE"
if docker network inspect "$EDGE" >/dev/null 2>&1; then
    info "$(docker network inspect -f 'driver={{.Driver}} internal={{.Internal}} subnet={{range .IPAM.Config}}{{.Subnet}} {{end}} labels={{json .Labels}}' "$EDGE")"
    echo "INFO  containers and DNS names on $EDGE:"
    for c in $(docker network inspect -f '{{range .Containers}}{{println .Name}}{{end}}' "$EDGE"); do
        names="$(docker inspect -f "{{with index .NetworkSettings.Networks \"$EDGE\"}}{{join .Aliases \",\"}} {{join .DNSNames \",\"}}{{end}}" "$c" 2>/dev/null)"
        image="$(docker inspect -f '{{.Config.Image}}' "$c")"
        printf '        %-40s image=%-30s names=%s\n' "$c" "$image" "$names"
        case "$image" in *postgres*|*mysql*|*mariadb*|*redis*|*mongo*) warn "$c ($image) is on the shared edge network: reachable from perfumeria-web" ;; esac
        printf '%s %s\n' "$c" "$names" | tr ', ' '\n\n' | grep -qxE 'perfumeria-web|perfumeria-db' && fail "$c already answers to perfumeria-web/perfumeria-db"
    done
else
    fail "network $EDGE not found"
fi

section "Perfumería names and existing resources"
left="$(docker ps -a --format '{{.Names}}' | grep -i perfumeria | tr '\n' ' ')"; [ -z "$left" ] && pass "no perfumeria containers yet" || info "perfumeria containers: $left"
left="$(docker volume ls -q | grep -i perfumeria | tr '\n' ' ')"; [ -z "$left" ] && pass "no perfumeria volumes yet" || info "perfumeria volumes: $left"
left="$(docker network ls --format '{{.Name}}' | grep -i perfumeria | tr '\n' ' ')"; [ -z "$left" ] && pass "no perfumeria networks yet" || info "perfumeria networks: $left"
left="$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -i perfumeria | tr '\n' ' ')"; info "perfumeria images: ${left:-none}"
echo "INFO  networks and subnets:"
for n in $(docker network ls -q); do docker network inspect -f '        {{.Name}} {{range .IPAM.Config}}{{.Subnet}} {{end}}internal={{.Internal}}' "$n"; done
[ -d /srv/perfumeria ] && info "/srv/perfumeria exists: $(ls -ld /srv/perfumeria)" || info "/srv/perfumeria does not exist yet"
info "listening TCP ports: $(ss -Hltn | awk '{print $4}' | sort -u | tr '\n' ' ')"

section "Forum databases (read-only)"
for c in $(docker ps --format '{{.Names}}'); do
    case "$(docker inspect -f '{{.Config.Image}}' "$c")" in
        *postgres*|*mysql*|*mariadb*)
            info "$c networks: $(docker inspect -f '{{range $n, $v := .NetworkSettings.Networks}}{{$n}} {{end}}' "$c") ports: $(docker port "$c" | tr '\n' ' ')" ;;
    esac
done

section "DNS"
info "host addresses: $(ip -o addr show scope global | awk '{split($4, a, "/"); print a[1]}' | tr '\n' ' ')"
for name in "$DOMAIN" "www.$DOMAIN"; do
    answer="$(getent ahosts "$name" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ')"
    [ -n "$answer" ] && info "$name -> $answer" || warn "$name does not resolve"
done
command -v resolvectl >/dev/null && resolvectl query "$DOMAIN" 2>&1 | head -n3 | sed 's/^/INFO  resolvectl: /'

printf '\n----\nfails=%s warns=%s\n' "$fails" "$warns"
[ "$fails" -eq 0 ]
