# Shared helpers for the shared-VPS scripts. Sourced, never executed directly.
#
# Model (ARQUITECTURA_CADDY_COMPARTIDO.md): the Caddy that owns 80/443 imports
# /etc/caddy/sites/*.caddy from a neutral host directory (/srv/caddy/sites). This project
# only ever writes its own file there and asks Caddy for a graceful reload. It never edits
# another project's files, never recreates or stops containers and never runs
# `docker compose` on another project.

SHARED_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SHARED_DIR/.." && pwd)"
ENV_FILE="${PERFUMERIA_ENV_FILE:-$SHARED_DIR/.env.production}"
PROJECT="perfumeria-production"
DOMAIN="perfumeriaelbuenolor.es"

env_value() { [ -f "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true; }
CADDY="${SHARED_PROXY_CONTAINER:-$(env_value SHARED_PROXY_CONTAINER)}"; CADDY="${CADDY:-foroia-production-caddy-1}"
EDGE="${SHARED_EDGE_NETWORK:-$(env_value SHARED_EDGE_NETWORK)}"; EDGE="${EDGE:-foroia-production_edge}"

# --- Modular site layout (host paths can be overridden only by the sandbox test) ---------
SITES_DIR="${SITES_DIR:-/srv/caddy/sites}"          # host directory, mounted read-only in Caddy
SITES_MOUNT="/etc/caddy/sites"                       # path inside the shared Caddy
LOGS_DIR="${LOGS_DIR:-/srv/caddy/logs}"             # host directory for per-site access logs
LOGS_MOUNT="/var/log/caddy-sites"                    # path inside the shared Caddy
IMPORT_LINE="import $SITES_MOUNT/*.caddy"
SITE_SOURCE="${SITE_SOURCE:-$SHARED_DIR/site/$DOMAIN.caddy}"   # version-controlled site block
SITE_FILE="$SITES_DIR/$DOMAIN.caddy"                 # the only file this project may write
SITE_STAGED="$SITE_FILE.new"                         # not matched by *.caddy: safe to validate
CADDY_BACKUP_DIR="${CADDY_BACKUP_DIR:-/srv/perfumeria/caddy-backups}"
LOCK_FILE="${LOCK_FILE:-/run/lock/caddy-sites.lock}" # shared by every project that edits sites/

pcompose() {
    docker compose -p "$PROJECT" -f "$SHARED_DIR/compose.yaml" --env-file "$ENV_FILE" "$@"
}

# Sandbox runs must never reach a real proxy: in test mode only perfumeria-sitetest-* containers.
guard_target() {
    if [ "${SITE_TEST_MODE:-0}" = "1" ]; then
        case "$CADDY" in perfumeria-sitetest-*) ;; *) echo "test mode refuses container $CADDY" >&2; return 1 ;; esac
    fi
    case "$(realpath -m "$SITES_DIR")/" in /opt/*|/etc/*|/var/lib/docker/*) echo "refusing sites directory $SITES_DIR" >&2; return 1 ;; esac
    [ -L "$SITE_FILE" ] && { echo "refusing: $SITE_FILE is a symlink" >&2; return 1; }
    [ "$(dirname "$(realpath -m "$SITE_FILE")")" = "$(realpath -m "$SITES_DIR")" ] || { echo "refusing site path $SITE_FILE" >&2; return 1; }
    return 0
}

# Path of the Caddyfile inside the shared Caddy (from its --config argument).
caddy_config_path() {
    docker inspect -f '{{range .Args}}{{println .}}{{end}}' "$CADDY" 2>/dev/null \
        | awk 'prev == "--config" { print; found = 1; exit } { prev = $0 } END { if (!found) print "/etc/caddy/Caddyfile" }'
}

# Host path of that Caddyfile, only if it comes from a bind mount (file or directory).
caddy_config_host_path() {
    local inside="$1" type source destination rw
    while IFS='|' read -r type source destination rw; do
        [ "$type" = "bind" ] || continue
        if [ "$inside" = "$destination" ]; then echo "$source"; return 0; fi
        case "$inside" in "$destination"/*) echo "$source${inside#"$destination"}"; return 0 ;; esac
    done < <(docker inspect -f '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.RW}}{{println}}{{end}}' "$CADDY")
    return 1
}

mount_line() {  # "<type>|<source>|<rw>" of the mount at destination $1, empty if none
    docker inspect -f '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.RW}}{{println}}{{end}}' "$CADDY" \
        | awk -F'|' -v d="$1" '$3 == d {print $1 "|" $2 "|" $4; exit}'
}

# Is the shared Caddy prepared for modular sites? Prints one line per check.
shared_proxy_ready() {
    local ok=0 inside host_file line
    if [ "$(docker inspect -f '{{.State.Running}}' "$CADDY" 2>/dev/null)" = "true" ]; then
        echo "PASS  $CADDY is running"
    else
        echo "FAIL  $CADDY is not running"; return 1
    fi
    line="$(mount_line "$SITES_MOUNT")"
    if [ "$line" = "bind|$(realpath -m "$SITES_DIR")|false" ] || [ "$line" = "bind|$SITES_DIR|false" ]; then
        echo "PASS  $SITES_DIR mounted read-only at $SITES_MOUNT"
    else
        echo "FAIL  $SITES_MOUNT is not a read-only bind mount of $SITES_DIR (found: ${line:-none})"; ok=1
    fi
    line="$(mount_line "$LOGS_MOUNT")"
    if [ "$line" = "bind|$(realpath -m "$LOGS_DIR")|true" ] || [ "$line" = "bind|$LOGS_DIR|true" ]; then
        echo "PASS  $LOGS_DIR mounted read-write at $LOGS_MOUNT"
    else
        echo "FAIL  $LOGS_MOUNT is not a read-write bind mount of $LOGS_DIR (found: ${line:-none})"; ok=1
    fi
    inside="$(caddy_config_path)"
    if host_file="$(caddy_config_host_path "$inside")" && grep -qxE "[[:space:]]*import[[:space:]]+$SITES_MOUNT/\*\.caddy[[:space:]]*" "$host_file"; then
        echo "PASS  shared Caddyfile contains '$IMPORT_LINE'"
    elif docker exec "$CADDY" grep -qxE "[[:space:]]*import[[:space:]]+$SITES_MOUNT/\*\.caddy[[:space:]]*" "$inside" 2>/dev/null; then
        echo "PASS  shared Caddyfile contains '$IMPORT_LINE' (checked inside the container)"
    else
        echo "FAIL  shared Caddyfile lacks '$IMPORT_LINE'"; ok=1
    fi
    if docker exec "$CADDY" wget -q -O /dev/null http://127.0.0.1:2019/config/ 2>/dev/null; then
        echo "PASS  admin API reachable (graceful reload possible)"
    else
        echo "FAIL  admin API not reachable at 127.0.0.1:2019"; ok=1
    fi
    return $ok
}

# Hosts served by the running configuration (from the admin API).
served_hosts() {
    docker exec "$CADDY" wget -q -O - http://127.0.0.1:2019/config/apps/http/servers 2>/dev/null | python3 -c '
import json, sys
try:
    servers = json.load(sys.stdin) or {}
except Exception:
    sys.exit()
hosts = set()
for srv in servers.values():
    for route in srv.get("routes", []):
        for m in route.get("match", []):
            hosts.update(m.get("host", []))
print("\n".join(sorted(hosts)))'
}

proxy_identity() { docker inspect -f '{{.Id}} {{.State.StartedAt}} {{.RestartCount}}' "$CADDY"; }

# Validate the whole shared configuration as it would be with $1 as this project's site
# file (empty $1 = without it), using the same image in a throwaway, network-less
# container. Other projects' site files are included read-only as they are.
validate_site_candidate() {
    local candidate="$1" inside image envfile work mounts=() type source destination rw rc
    inside="$(caddy_config_path)"
    image="$(docker inspect -f '{{.Config.Image}}' "$CADDY")"
    work="$(mktemp -d)"; chmod 700 "$work"; mkdir "$work/sites"
    envfile="$work/env"; docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CADDY" | grep -v '^$' > "$envfile"
    for f in "$SITES_DIR"/*.caddy; do
        [ -f "$f" ] || continue
        [ "$f" = "$SITE_FILE" ] && continue
        cp -- "$f" "$work/sites/"
    done
    [ -n "$candidate" ] && cp -- "$candidate" "$work/sites/$DOMAIN.caddy"
    chmod -R a+rX "$work/sites"
    while IFS='|' read -r type source destination rw; do
        [ "$type" = "bind" ] || continue
        case "$destination" in "$SITES_MOUNT"|"$LOGS_MOUNT") continue ;; esac
        mounts+=(--mount "type=bind,src=$source,dst=$destination,readonly")
    done < <(docker inspect -f '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.RW}}{{println}}{{end}}' "$CADDY")
    docker run --rm --network none --env-file "$envfile" "${mounts[@]}" \
        --mount "type=bind,src=$work/sites,dst=$SITES_MOUNT,readonly" \
        --tmpfs "$LOGS_MOUNT" --tmpfs /data --tmpfs /config \
        --entrypoint caddy "$image" validate --config "$inside" --adapter caddyfile >"$work/validate.log" 2>&1
    rc=$?
    [ $rc -ne 0 ] && grep -E '"level":"error"|Error' "$work/validate.log" | tail -n 3 >&2
    rm -rf -- "$work"
    return $rc
}

# Validate a whole candidate Caddyfile (used by caddy-backup.sh --verify).
validate_candidate() {
    local candidate="$1" inside image envfile mounts=() type source destination rw rc
    inside="$(caddy_config_path)"
    image="$(docker inspect -f '{{.Config.Image}}' "$CADDY")"
    envfile="$(mktemp)"; chmod 600 "$envfile"
    docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CADDY" | grep -v '^$' > "$envfile"
    while IFS='|' read -r type source destination rw; do
        # The Caddyfile's own mount is replaced by the candidate (duplicate destinations are rejected).
        [ "$type" = "bind" ] && [ "$destination" != "$inside" ] && [ "$destination" != "$LOGS_MOUNT" ] \
            && mounts+=(--mount "type=bind,src=$source,dst=$destination,readonly")
    done < <(docker inspect -f '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.RW}}{{println}}{{end}}' "$CADDY")
    docker run --rm --network none --env-file "$envfile" "${mounts[@]}" \
        --mount "type=bind,src=$candidate,dst=$inside,readonly" \
        --tmpfs "$LOGS_MOUNT" --tmpfs /data --tmpfs /config \
        --entrypoint caddy "$image" validate --config "$inside" --adapter caddyfile
    rc=$?
    rm -f -- "$envfile"
    return $rc
}

caddy_reload() { docker exec "$CADDY" caddy reload --config "$(caddy_config_path)" --adapter caddyfile; }

# HTTP status of each forum URL (FORO_URLS), to prove other sites are unaffected.
forum_statuses() {
    local url
    for url in ${FORO_URLS:-}; do
        printf '%s %s\n' "$url" "$(curl -s ${FORO_CURL_OPTS:-} -o /dev/null --max-time 15 -w '%{http_code}' "$url")"
    done
}

# Public addresses of this host, to compare with DNS answers.
host_addresses() { ip -o addr show scope global 2>/dev/null | awk '{split($4, a, "/"); print a[1]}'; }
dns_points_here() {
    local name="$1" answers
    answers="$(getent ahosts "$name" 2>/dev/null | awk '{print $1}' | sort -u)"
    [ -n "$answers" ] || return 1
    for address in $answers; do host_addresses | grep -qxF "$address" || return 1; done
}
