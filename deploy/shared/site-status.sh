#!/usr/bin/env bash
# Read-only status of this project's site in the shared Caddy (safe at any time; use sudo for
# Docker access). Exit code 0 = healthy, 1 = something needs attention (usable from cron).
#
#   sudo ./shared/site-status.sh            # full report
#   sudo ./shared/site-status.sh --quiet    # one summary line
set -uo pipefail
source "$(dirname "$0")/lib.sh"

quiet=0; [ "${1:-}" = "--quiet" ] && quiet=1
fails=0; lines=()
say() { lines+=("$1"); case "$1" in FAIL*) fails=$((fails + 1)) ;; esac; }
ADDR="${STATUS_ADDR:-127.0.0.1:443}"
CURL=(curl -s ${STATUS_CURL_OPTS:-} --max-time 15 --resolve "$DOMAIN:${ADDR##*:}:${ADDR%:*}" --resolve "www.$DOMAIN:${ADDR##*:}:${ADDR%:*}")

while IFS= read -r line; do say "$line"; done < <(shared_proxy_ready)

if [ -f "$SITE_FILE" ]; then
    active="$(sha256sum < "$SITE_FILE" | cut -c1-16)"; repo="$(sha256sum < "$SITE_SOURCE" | cut -c1-16)"
    [ "$active" = "$repo" ] && say "PASS  site file deployed and identical to the repository ($active)" \
                            || say "WARN  site file deployed ($active) differs from the repository ($repo)"
else
    say "FAIL  site file $SITE_FILE not deployed"
fi
[ -e "$SITE_STAGED" ] && say "WARN  leftover staged file $SITE_STAGED (ignored by Caddy)"
served_hosts | grep -qxF "$DOMAIN" && say "PASS  $DOMAIN present in the running configuration" \
                                   || say "FAIL  $DOMAIN not in the running configuration"

cert="$(echo | timeout 10 openssl s_client -connect "$ADDR" -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -issuer -enddate 2>/dev/null)"
if [ -n "$cert" ]; then
    issuer="$(echo "$cert" | sed -n 's/^issuer=.*O *= *\([^,]*\).*/\1/p')"
    end="$(echo "$cert" | sed -n 's/^notAfter=//p')"
    days=$(( ( $(date -d "$end" +%s) - $(date +%s) ) / 86400 ))
    if [ "$days" -ge "${STATUS_MIN_DAYS:-14}" ]; then say "PASS  certificate for $DOMAIN from ${issuer:-?}, $days days left"
    else say "FAIL  certificate for $DOMAIN expires in $days days"; fi
else
    say "FAIL  no certificate served for $DOMAIN on $ADDR"
fi

code() { "${CURL[@]}" -o /dev/null -w '%{http_code}' "$1"; }
for check in "https://$DOMAIN/|200" "https://$DOMAIN/checkout/|403" "https://$DOMAIN/healthz/|404" "https://$DOMAIN/media/x.jpg|404"; do
    url="${check%|*}"; want="${check##*|}"; got="$(code "$url")"
    [ "$got" = "$want" ] && say "PASS  $url -> $got" || say "FAIL  $url -> $got (expected $want)"
done
redirect="$("${CURL[@]}" -o /dev/null -w '%{http_code} %{redirect_url}' "https://www.$DOMAIN/")"
case "$redirect" in 301\ https://$DOMAIN/*) say "PASS  www redirects to the apex ($redirect)" ;; *) say "FAIL  www redirect: $redirect" ;; esac

if [ "$quiet" = 1 ]; then
    [ "$fails" -eq 0 ] && echo "OK $DOMAIN" || { echo "PROBLEM $DOMAIN: $fails failing checks"; printf '%s\n' "${lines[@]}" | grep '^FAIL'; }
else
    printf '%s\n' "${lines[@]}"; echo "----"; echo "fails=$fails"
fi
[ "$fails" -eq 0 ]
