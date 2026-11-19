# Shared helpers for the shared-VPS scripts. Sourced, never executed directly.
# Everything here only reads state (docker inspect, files); nothing is changed.

SHARED_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SHARED_DIR/.." && pwd)"
ENV_FILE="${PERFUMERIA_ENV_FILE:-$SHARED_DIR/.env.production}"
BLOCK_FILE="$SHARED_DIR/perfumeria.caddy"
BEGIN_MARK="# >>> BEGIN perfumeria-el-buen-olor"
END_MARK="# <<< END perfumeria-el-buen-olor"
PROJECT="perfumeria-production"

env_value() { [ -f "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true; }
CADDY="${SHARED_PROXY_CONTAINER:-$(env_value SHARED_PROXY_CONTAINER)}"; CADDY="${CADDY:-foroia-production-caddy-1}"
EDGE="${SHARED_EDGE_NETWORK:-$(env_value SHARED_EDGE_NETWORK)}"; EDGE="${EDGE:-foroia-production_edge}"
DOMAIN="perfumeriaelbuenolor.es"

pcompose() {
    docker compose -p "$PROJECT" -f "$SHARED_DIR/compose.yaml" --env-file "$ENV_FILE" "$@"
}

# Path of the Caddyfile inside the forum's Caddy container (from its --config argument).
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

# Validate a candidate Caddyfile with the forum's own Caddy image, in a throwaway
# container without network, with the forum's bind mounts read-only and empty /data.
# The running proxy is not touched.
validate_candidate() {
    local candidate="$1" inside image envfile mounts=() type source destination rw rc
    inside="$(caddy_config_path)"
    image="$(docker inspect -f '{{.Config.Image}}' "$CADDY")"
    envfile="$(mktemp)"; chmod 600 "$envfile"
    docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CADDY" | grep -v '^$' > "$envfile"
    while IFS='|' read -r type source destination rw; do
        [ "$type" = "bind" ] && mounts+=(--mount "type=bind,src=$source,dst=$destination,readonly")
    done < <(docker inspect -f '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.RW}}{{println}}{{end}}' "$CADDY")
    docker run --rm --network none --env-file "$envfile" "${mounts[@]}" \
        --mount "type=bind,src=$candidate,dst=$inside,readonly" \
        --tmpfs /data --tmpfs /config \
        --entrypoint caddy "$image" validate --config "$inside" --adapter caddyfile
    rc=$?
    rm -f -- "$envfile"
    return $rc
}

# Public addresses of this host, to compare with DNS answers.
host_addresses() { ip -o addr show scope global 2>/dev/null | awk '{split($4, a, "/"); print a[1]}'; }
dns_points_here() {
    local name="$1" answers
    answers="$(getent ahosts "$name" 2>/dev/null | awk '{print $1}' | sort -u)"
    [ -n "$answers" ] || return 1
    for address in $answers; do host_addresses | grep -qxF "$address" || return 1; done
}
