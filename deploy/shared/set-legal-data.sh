#!/usr/bin/env bash
# Store the site owner's legal data (LSSI-CE / RGPD) in the production env file, on the server.
#
#   sudo bash deploy/shared/set-legal-data.sh            # asks each value, writes nothing to the screen
#   sudo bash deploy/shared/set-legal-data.sh --check    # says which values are set (never prints them)
#
# - Values are typed interactively (read from the terminal): they do not appear in shell history,
#   command lines, process lists or this script's output.
# - The env file stays root-owned with mode 600; a timestamped copy (also 600) is kept beside it.
# - Nothing is published: the web container must be recreated afterwards (separate, authorised step):
#     docker compose -p perfumeria-production -f shared/compose.yaml --env-file shared/.env.production up -d perfumeria-web
set -euo pipefail
set +x   # never trace: the values would be printed

ENV_FILE="${PERFUMERIA_ENV_FILE:-$(dirname "$0")/.env.production}"
[ "$(id -u)" = 0 ] || { echo "Run with sudo." >&2; exit 1; }
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE" >&2; exit 1; }

FIELDS=(
  "LEGAL_OWNER_NAME|Titular: nombre completo o razón social|required"
  "LEGAL_OWNER_TAX_ID|NIF o CIF|required"
  "LEGAL_OWNER_ADDRESS|Domicilio completo|required"
  "LEGAL_OWNER_EMAIL|Correo electrónico de contacto|required"
  "LEGAL_OWNER_PHONE|Teléfono (opcional, Enter para omitir)|optional"
  "LEGAL_OWNER_REGISTRY|Datos del Registro Mercantil (opcional)|optional"
  "LEGAL_EMAIL_PROVIDER|Proveedor de envío de correo (opcional)|optional"
)

if [ "${1:-}" = "--check" ]; then
  for entry in "${FIELDS[@]}"; do
    key="${entry%%|*}"; kind="${entry##*|}"
    if grep -qE "^${key}=.+" "$ENV_FILE"; then state="definido"; else state="vacío"; fi
    printf '%-22s %-9s (%s)\n' "$key" "$state" "$kind"
  done
  exit 0
fi

[ -t 0 ] || { echo "Run it from an interactive terminal (values are typed, not piped)." >&2; exit 1; }
umask 077
declare -A VALUES
for entry in "${FIELDS[@]}"; do
  IFS='|' read -r key label kind <<< "$entry"
  while true; do
    # -s: not echoed to the screen either (shoulder-surfing, terminal recordings)
    IFS= read -r -s -p "$label: " value < /dev/tty; echo
    value="${value#"${value%%[![:space:]]*}"}"; value="${value%"${value##*[![:space:]]}"}"
    if [ -z "$value" ] && [ "$kind" = required ]; then echo "  Obligatorio."; continue; fi
    # Single-quoted in the env file (no variable expansion): reject what would break that format.
    if [[ "$value" == *"'"* || "$value" == *$'\n'* || "$value" =~ [[:cntrl:]] ]]; then
      echo "  No se admiten comillas simples ni caracteres de control. Vuelve a escribirlo."; continue
    fi
    if [ "$key" = LEGAL_OWNER_EMAIL ] && ! [[ "$value" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; then
      echo "  No parece un correo válido."; continue
    fi
    VALUES[$key]="$value"; break
  done
done

backup="${ENV_FILE}.$(date -u +%Y%m%dT%H%M%SZ).bak"
cp -p "$ENV_FILE" "$backup"; chmod 600 "$backup"
tmp="$(mktemp "${ENV_FILE}.XXXXXX")"
grep -vE "^(LEGAL_OWNER_[A-Z_]+|LEGAL_EMAIL_PROVIDER)=" "$ENV_FILE" > "$tmp" || true
for entry in "${FIELDS[@]}"; do
  key="${entry%%|*}"
  printf "%s='%s'\n" "$key" "${VALUES[$key]}" >> "$tmp"
done
chmod 600 "$tmp"; chown --reference="$ENV_FILE" "$tmp"; mv "$tmp" "$ENV_FILE"
unset VALUES value
echo "Datos guardados en $ENV_FILE (copia previa: $backup). No se ha mostrado ningún valor."
echo "Siguiente paso (con autorización): recrear el contenedor web y comprobar con --check."
