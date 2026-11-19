#!/usr/bin/env bash
# Proves which PostgreSQL server Django connects to before running migrations: the server
# address seen by Django must be the perfumeria-db container on the project's own
# internal network, and the database must be the perfumería one. Read-only (SELECT only),
# but it starts a temporary perfumeria-web container, which joins the forum's edge network
# while it runs: covered by authorization 2 (see DESPLIEGUE_VPS_COMPARTIDO.md).
#
#   cd deploy && ./shared/verify-db-target.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

db_container="$(pcompose ps -q perfumeria-db)"
[ -n "$db_container" ] || { echo "perfumeria-db is not running (pc up -d perfumeria-db)." >&2; exit 1; }
expected_ip="$(docker inspect -f "{{with index .NetworkSettings.Networks \"${PROJECT}_backend\"}}{{.IPAddress}}{{end}}" "$db_container")"
networks="$(docker inspect -f '{{range $n, $v := .NetworkSettings.Networks}}{{$n}} {{end}}' "$db_container")"
[ "$networks" = "${PROJECT}_backend " ] || { echo "perfumeria-db is attached to unexpected networks: $networks" >&2; exit 1; }

seen="$(pcompose run --rm --no-deps -T perfumeria-web python manage.py shell --no-imports -c \
    'from django.db import connection as c
c.ensure_connection()
cur = c.cursor()
cur.execute("select current_database(), host(inet_server_addr()), current_user")
print("|".join(str(v) for v in cur.fetchone()))' 2>/dev/null | tail -n1 | tr -d '\r')"
IFS='|' read -r database server user <<< "$seen"
expected_db="$(env_value POSTGRES_DB)"; expected_db="${expected_db:-perfumeria}"
echo "Django connects to: database=$database server=$server user=$user"
echo "Expected:           database=$expected_db server=$expected_ip (perfumeria-db on ${PROJECT}_backend)"
[ "$server" = "$expected_ip" ] && [ "$database" = "$expected_db" ] || { echo "MISMATCH: do not run migrations." >&2; exit 1; }
echo "OK: migrations can only reach the perfumería database."
