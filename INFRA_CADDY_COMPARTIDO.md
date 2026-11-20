# Preparación única del Caddy compartido (para ejecutar desde el proyecto Foro IA al Día)

Este documento describe **cambios genéricos de infraestructura** que gestiona el proyecto del foro con un despliegue específico: sin release completa y sin publicar otros cambios pendientes. No contiene nada de la perfumería. Después, cada proyecto publica sus sitios por su cuenta en `/srv/caddy/sites`.

Estado actual en producción (20/11/2026): `foroia-production-caddy-1` (Caddy 2.11.7) monta solo `./deploy/Caddyfile`, `caddydata` y `caddyconfig`. `/srv/caddy` no existe. El Caddyfile de producción (`325d2ff9…`) difiere del de `foroia-codex` (que añade `http://www.foroiaaldia.com`). Por eso el cambio se hace **sobre los archivos de producción**, no con una release.

## Qué cambia exactamente

| Elemento | Cambio |
|---|---|
| `/srv/caddy/sites`, `/srv/caddy/logs` | Se crean (root, 755). `sites/` queda **vacío**: el foro no cambia de comportamiento |
| `/opt/foroia/deploy/Caddyfile` | Se **añaden al final** 2 líneas: un comentario y `import /etc/caddy/sites/*.caddy` |
| `/opt/foroia/compose.production.yml`, servicio `caddy` | Se añaden 2 montajes: `/srv/caddy/sites:/etc/caddy/sites:ro` y `/srv/caddy/logs:/var/log/caddy-sites` |
| Contenedor `foroia-production-caddy-1` | Se recrea **solo él** (`--no-deps`): unos segundos de corte. Los certificados se conservan en `caddydata` |

Ningún otro servicio del foro se recrea. No se reconstruyen imágenes ni se aplican migraciones.

## Pasos (en el VPS, con autorización; ventana de pocos minutos)

```bash
set -euo pipefail
cd /opt/foroia
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

# 0. Copias de seguridad de los dos archivos (y de la configuración en ejecución)
sudo install -d -m 700 /srv/caddy-backups
sudo cp -p deploy/Caddyfile        "/srv/caddy-backups/Caddyfile.$STAMP"
sudo cp -p compose.production.yml  "/srv/caddy-backups/compose.production.yml.$STAMP"
sudo docker exec foroia-production-caddy-1 wget -q -O - http://127.0.0.1:2019/config/ \
  | sudo tee "/srv/caddy-backups/running-config.$STAMP.json" >/dev/null
sudo sh -c "cd /srv/caddy-backups && sha256sum *.$STAMP* > SHA256SUMS.$STAMP"

# 1. Directorio neutro de sitios y logs (vacío) y reglas de convivencia
sudo install -d -m 755 -o root -g root /srv/caddy /srv/caddy/sites /srv/caddy/logs
sudo tee /srv/caddy/README.md >/dev/null <<'EOF'
# Caddy compartido del VPS
- El Caddy de 80/443 importa /etc/caddy/sites/*.caddy (= /srv/caddy/sites, solo lectura).
- Un archivo por dominio, nombrado <dominio>.caddy; cada proyecto escribe SOLO el suyo.
- Sin bloque de opciones globales { }; snippets con prefijo del proyecto.
- Validar la configuración completa antes de activar; activar con mv atómico y `caddy reload`.
- Nunca dejar un archivo inválido con extensión .caddy (rompería el próximo arranque).
- Bloqueo compartido: flock /run/lock/caddy-sites.lock
- Logs por sitio en /srv/caddy/logs/<dominio>/ (= /var/log/caddy-sites).
EOF

# 2. Caddyfile: añadir el enganche al final (solo añadir; no se toca nada existente)
printf '\n# Sitios de otros proyectos alojados en este VPS (un archivo por dominio, gestionados fuera de este repositorio)\nimport /etc/caddy/sites/*.caddy\n' \
  | sudo tee -a deploy/Caddyfile >/dev/null

# 3. Compose: dos montajes justo después del montaje del Caddyfile (servicio caddy)
sudo awk '{print} /- \.\/deploy\/Caddyfile:\/etc\/caddy\/Caddyfile:ro/ && !done {ind=$0; sub(/-.*/, "", ind); print ind "- /srv/caddy/sites:/etc/caddy/sites:ro"; print ind "- /srv/caddy/logs:/var/log/caddy-sites"; done=1}' \
  compose.production.yml | sudo tee compose.production.yml.new >/dev/null
sudo mv compose.production.yml.new compose.production.yml

# 4. Comprobar que SOLO han cambiado esas líneas
sudo diff "/srv/caddy-backups/Caddyfile.$STAMP" deploy/Caddyfile || true                 # 3 líneas añadidas
sudo diff "/srv/caddy-backups/compose.production.yml.$STAMP" compose.production.yml || true  # 2 líneas añadidas
sudo docker compose --env-file production.env -f compose.production.yml config -q       # sin -q expande secretos
sudo docker run --rm --network none \
  -v /opt/foroia/deploy/Caddyfile:/etc/caddy/Caddyfile:ro -v /srv/caddy/sites:/etc/caddy/sites:ro \
  --tmpfs /var/log/caddy-sites --tmpfs /data --tmpfs /config \
  caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile         # "Valid configuration"
./shared-proxy-contract.sh --static compose.production.yml deploy/Caddyfile               # ver "Comprobaciones"

# 5. Recrear SOLO Caddy (unos segundos); el resto de servicios no se toca
sudo docker compose --env-file production.env -f compose.production.yml up -d --no-deps --force-recreate caddy

# 6. Verificar
sudo ./shared-proxy-contract.sh --live foroia-production-caddy-1                           # fails=0
curl -sI https://foroiaaldia.com/ | head -n1; curl -sI https://www.foroiaaldia.com/ | head -n1
sudo docker ps --filter label=com.docker.compose.project=foroia-production --format '{{.Names}} {{.Status}}'
```

`shared-proxy-contract.sh` es un script autónomo de solo lectura (en `deploy/shared/` del repositorio de la perfumería). Se puede copiar al VPS o al proyecto del foro; no depende de ningún otro archivo. Si se prefiere no copiarlo, los pasos 4 y 6 ya incluyen comprobaciones equivalentes (`diff`, `config -q`, `caddy validate`, `curl`).

### Rollback

```bash
cd /opt/foroia
sudo cp -p "/srv/caddy-backups/Caddyfile.$STAMP" deploy/Caddyfile
sudo cp -p "/srv/caddy-backups/compose.production.yml.$STAMP" compose.production.yml
sudo docker compose --env-file production.env -f compose.production.yml up -d --no-deps --force-recreate caddy
```

`/srv/caddy` puede quedarse: vacío no afecta a nada.

## Conservar el cambio en las releases futuras del foro

1. **En el repositorio del foro**, desde el propio proyecto del foro: incorporar los mismos dos cambios genéricos a su `deploy/Caddyfile` y a su `compose.production.yml` (las 2 líneas del enganche y los 2 montajes). No contienen nada de otros proyectos.
2. **Antes de cada release** (sobre el árbol que se va a empaquetar):
   ```bash
   ./shared-proxy-contract.sh --static compose.production.yml deploy/Caddyfile   # debe dar fails=0
   ```
   Si falla, la release eliminaría el enganche o los montajes: no desplegar.
3. **Después de cada release o recreación de Caddy:**
   ```bash
   sudo ./shared-proxy-contract.sh --live foroia-production-caddy-1             # fails=0; cada sitio de /srv/caddy/sites cargado
   ```
4. **Nunca** `docker compose down -v` ni borrar `/srv/caddy`. Las releases extraen en `/opt/foroia` y no tocan `/srv/caddy`.
5. Recomendado: fijar la imagen (`caddy:2.11.7-alpine`) en lugar de `caddy:2-alpine`, y probar cada actualización de Caddy con `--live`.

Además, por parte de la perfumería, `site-status.sh --quiet` (de solo lectura) puede ejecutarse a diario para detectar si una release del foro ha perdido el enganche: el foro no se ve afectado, pero la perfumería dejaría de servirse.

## Después de la preparación (flujo de la perfumería, con su propia autorización)

1. DNS de `perfumeriaelbuenolor.es`: quitar la redirección web de OVH y poner los A de `@` y `www` hacia `146.59.35.127`, sin tocar MX ni SPF.
2. `cd /srv/perfumeria/app/deploy && sudo -E FORO_URLS="https://foroiaaldia.com/ https://www.foroiaaldia.com/" ./shared/site-deploy.sh`: recarga en caliente, sin recrear Caddy.
3. `sudo ./shared/site-status.sh`: certificado de Let's Encrypt, HTTPS, redirecciones, `/checkout/` 403, `/healthz/` y `/media/` 404.
