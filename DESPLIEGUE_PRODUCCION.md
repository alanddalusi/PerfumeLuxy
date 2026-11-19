# Despliegue de producción (prelanzamiento)

Estado: preparado, **no desplegado**. La tienda arranca siempre con `STORE_MODE=prelaunch`, sin pagos, y con el correo saliente desactivado.

## Arquitectura

| Servicio | Imagen | Red | Puertos publicados | Datos |
|---|---|---|---|---|
| `caddy` | `caddy:2.8-alpine` | `edge` (IP fija 172.30.10.2) | 80, 443 TCP/UDP | certificados (`caddy_data`), logs de acceso (`caddy_logs`), estáticos en solo lectura |
| `web` | `Dockerfile` (Python 3.13, Gunicorn) | `edge` (IP dinámica del rango .128/25) + `backend` | ninguno | `static`, `media` (originales privados), `catalog_assets` (WebP aprobados) |
| `db` | `postgres:17-alpine` | `backend` (`internal: true`) | ninguno | `pgdata` |

- Solo Caddy es accesible desde Internet. PostgreSQL no tiene puerto publicado y la red `backend` no tiene salida.
- `web` se ejecuta como usuario sin privilegios, con sistema de archivos de solo lectura, sin capacidades y con `no-new-privileges`. El código pertenece a root.
- Caddy sirve únicamente `/static/`. Devuelve 404 para `/media/`, `/healthz`, `/.env*` y `/.git*`. Las imágenes aprobadas salen por Django desde `catalog_assets`; los originales nunca se exponen.
- Las migraciones **no** se aplican solas. El contenedor no arranca si hay migraciones pendientes o si `STORE_MODE` no es `prelaunch`.

### Archivos

| Archivo | Función |
|---|---|
| [Dockerfile](Dockerfile), [.dockerignore](.dockerignore) | Imagen de la aplicación sin secretos, bases de datos, `media/` ni `catalog_assets/` |
| [deploy/compose.yaml](deploy/compose.yaml) | Servicios, redes, volúmenes, comprobaciones de salud y rotación de logs de Docker (10 MB × 5) |
| [deploy/Caddyfile](deploy/Caddyfile) | HTTPS automático, redirección `www`, cabeceras, log de acceso filtrado y rotado (20 MiB × 10, 30 días) |
| [deploy/entrypoint.sh](deploy/entrypoint.sh) | `check --deploy`, `migrate --check`, `collectstatic` y Gunicorn |
| [deploy/gunicorn.conf.py](deploy/gunicorn.conf.py) | Workers, tiempos y log de errores; sin log de acceso (contendría tokens) |
| [deploy/healthcheck.py](deploy/healthcheck.py) | Comprobación de `/healthz/` (estado de la base, sin detalles) |
| [deploy/env.production.example](deploy/env.production.example) | Plantilla de variables. El archivo real `deploy/.env.production` está ignorado por Git |
| [deploy/backup/backup.sh](deploy/backup/backup.sh), [deploy/backup/restore.sh](deploy/backup/restore.sh) | Copias y restauración |

## Seguridad aplicada en esta fase

- **HTTPS y cabeceras.** Django: redirección a HTTPS, HSTS de un año, cookies `Secure` + `HttpOnly` (sesión) + `SameSite=Lax`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, COOP. Caddy añade las mismas cabeceras a los estáticos. `SECURE_PROXY_SSL_HEADER` solo se activa con `DJANGO_TRUST_HTTPS_PROXY=1`, y Caddy sobrescribe `X-Forwarded-Proto`.
- **Hosts y CSRF.** `DJANGO_ALLOWED_HOSTS` explícito (se rechaza `*`) y `DJANGO_CSRF_TRUSTED_ORIGINS` con el dominio HTTPS.
- **IP del visitante.** `eau_royal.proxy.TrustedProxyMiddleware` solo acepta `X-Forwarded-For` si la conexión procede de `DJANGO_TRUSTED_PROXY_NETWORKS` (la IP fija de Caddy), y entonces usa la última entrada, la que escribe Caddy. Caddy reemplaza la cabecera enviada por el cliente. Sin esa variable, `REMOTE_ADDR` es siempre el par TCP.
- **Tokens fuera de los logs.** Filtro `RedactTokensFilter` en el log de Django, Gunicorn sin log de acceso y filtro en Caddy para `/confirmar/`, `/baja/`, `/confirm-email/` y `/password/reset/key/`. Caddy borra además cookies, `Authorization` y `Referer`, y enmascara las IP (/24 en IPv4 y /48 en IPv6).
- **Correo.** En producción todo correo se descarta (`dummy`) salvo `EMAIL_DELIVERY=smtp`, que exige `EMAIL_HOST` y `DEFAULT_FROM_EMAIL`. Los avisos además requieren `INTEREST_EMAIL_DELIVERY=1`. Desarrollo usa siempre la consola. Consecuencia: mientras el SMTP esté desactivado, los visitantes no reciben la verificación de cuenta ni las confirmaciones de aviso.
- **Base de datos.** TLS obligatorio salvo `sslmode=disable` hacia un nombre de servicio sin puntos listado en `DJANGO_DB_PLAINTEXT_HOSTS` (`db`), que solo existe en la red interna.
- **Pagos.** Sin claves de Stripe. El checkout devuelve 403 en prelanzamiento, y fuera de `DEBUG` ya no se simula un pago si faltan claves (antes había un `MockIntent` heredado).
- **Catálogo de referencia.** Las fichas heredadas no se pueden vender aunque se cambie el modo de tienda (`Product.objects.sellable()`).

## Primer despliegue en el VPS (pendiente de autorización)

Requisitos: Docker Engine con el plugin `docker compose` v2, el DNS del dominio apuntando al VPS, y los puertos 80 y 443 abiertos. En el cortafuegos, solo 22 (restringido), 80 y 443.

```bash
git clone <repositorio> /srv/perfumeria/app && cd /srv/perfumeria/app/deploy
cp env.production.example .env.production && chmod 600 .env.production   # completar valores
docker compose --env-file .env.production build
docker compose --env-file .env.production up -d db
docker compose --env-file .env.production run --rm web python manage.py migrate
docker compose --env-file .env.production run --rm web python manage.py createsuperuser
docker compose --env-file .env.production up -d
docker compose --env-file .env.production ps        # los tres servicios "healthy"
```

Catálogo de referencia (opcional, solo borradores): `docker compose --env-file .env.production run --rm web python manage.py load_reference_catalog` (en seco) y después con `--apply`. Ver [CATALOGO_REFERENCIA.md](CATALOGO_REFERENCIA.md). Las fotografías heredadas no se copian al servidor.

Actualizaciones: `git pull`, copia de seguridad, `build`, `run --rm web python manage.py migrate` si hay migraciones, y `up -d`.

Base existente (Render u otra): restaura primero una copia en un entorno de ensayo, aplica `products.0010` y `0011` y `home.0003` y `0004`, y revisa el resultado antes de migrar la base real. `0011` solo marca como referencia los SKU del fixture heredado; no publica nada.

## Copias de seguridad y restauración

- **Qué se copia.** `pg_dump` en formato personalizado y los volúmenes `media` y `catalog_assets` (tar.gz), con `SHA256SUMS`.
- **Dónde.** En `BACKUP_DIR` (por defecto `/srv/perfumeria/backups`), con `umask 077`: directorios 700 y archivos 600. El volcado se valida con `pg_restore --list`. La retención es `BACKUP_KEEP_DAYS` (14).
- **Programación.** Con cron en el VPS, por ejemplo: `15 3 * * * cd /srv/perfumeria/app/deploy && ./backup/backup.sh >> /var/log/perfumeria-backup.log 2>&1`.
- **Copia externa (pendiente).** Las copias contienen correos de suscriptores, cuentas y la base completa. Envíalas cifradas (por ejemplo restic, age o gpg) a otro proveedor y región. Guarda la clave fuera del VPS y documenta quién tiene acceso. Esta parte depende del proveedor elegido y no está automatizada.
- **Prueba de restauración (mensual y tras cada cambio).** `./backup/restore.sh --verify <dir>` verifica las sumas, restaura en la base temporal `perfumeria_restore_check`, cuenta productos y migraciones, la elimina y comprueba los tar. No toca producción.
- **Restauración real.** `./backup/restore.sh --replace-production <dir>` pide escribir el dominio, detiene `web` y `caddy`, restaura la base en una sola transacción (`--clean --if-exists`), reemplaza los volúmenes de media y arranca de nuevo. Haz antes una copia del estado actual.

## Mantenimiento programado

```bash
# Diario: contadores antiabuso (>48 h) y solicitudes nunca confirmadas cuyo enlace caducó hace >30 días.
docker compose --env-file .env.production run --rm web python manage.py purge_notice_data            # en seco
docker compose --env-file .env.production run --rm web python manage.py purge_notice_data --apply
```

Los plazos (`--counter-hours`, `--unconfirmed-days`) deben coincidir con la política de conservación que apruebe el responsable. El comando no toca altas confirmadas, bajas ni registros heredados sin fecha de caducidad.

## Lista de comprobación antes de publicar

**Infraestructura**
- [ ] DNS del dominio y de `www` apuntando al VPS. Certificado emitido por Caddy (`docker compose logs caddy`).
- [ ] `docker compose ps`: `db`, `web` y `caddy` en estado *healthy*. `curl -I https://<dominio>/` devuelve 200 con HSTS.
- [ ] Desde fuera: `nmap -p 5432,8000 <ip>` muestra puertos cerrados. `https://<dominio>/media/<archivo>` y `/healthz/` devuelven 404.
- [ ] `http://` y `www` redirigen a `https://<dominio>/`.
- [ ] Copia ejecutada y `restore.sh --verify` superado. Copia externa cifrada configurada.

**Aplicación**
- [ ] `deploy/.env.production` con 600, `SECRET_KEY` y contraseña de base únicas, sin claves de Stripe.
- [ ] `STORE_MODE=prelaunch`, `EMAIL_DELIVERY=disabled`, `INTEREST_EMAIL_DELIVERY=0`.
- [ ] `/checkout/` devuelve 403. En las fichas no aparecen precio, stock ni «Añadir al carrito».
- [ ] `robots.txt` y `sitemap.xml` solo enlazan fichas aprobadas. Una ficha retirada devuelve 404.
- [ ] Ninguna fotografía heredada publicada. `CatalogImage` aprobadas solo con licencia registrada.
- [ ] Superusuario con contraseña robusta. Revisores con el permiso `publish_product` asignado individualmente.
- [ ] Log de acceso de Caddy revisado tras abrir un enlace de confirmación: el token aparece como `[redacted]`.
- [ ] Varias peticiones desde IP distintas: el limitador cuenta por visitante y no por la IP del proxy.

**Privacidad y negocio** (ver [PRIVACIDAD_BORRADOR.md](PRIVACIDAD_BORRADOR.md))
- [ ] Datos del responsable, aviso legal, política de privacidad y de cookies revisados y publicados.
- [ ] Contratos de encargo con el proveedor del VPS, el de copias y, en su momento, el de SMTP.
- [ ] Plazos de conservación aprobados y reflejados en `purge_notice_data` y en `BACKUP_KEEP_DAYS`.
- [ ] Antes de activar SMTP: prueba de confirmación y baja con un buzón de pruebas acordado.

## Verificación local realizada

- Suite completa (62 pruebas) en SQLite y en PostgreSQL 17 local.
- Ensayo de producción contra PostgreSQL: `check --deploy` (solo avisan W005/W021 sobre HSTS de subdominios y preload, opcionales), `migrate --check` detecta pendientes, `migrate`, `collectstatic` (3 MB), carga de 265 borradores de referencia, informe y purga en seco.
- `compose.yaml` validado como YAML. Scripts comprobados con `bash -n` y `sh -n`.
- **No verificado:** construcción de la imagen y arranque con Docker. El equipo de desarrollo solo tiene Docker Toolbox 2019, sin `docker compose` v2. Hazlo en el VPS o en un equipo con Docker actual antes de publicar, y valida el `Caddyfile` con `docker run --rm -v ./Caddyfile:/etc/caddy/Caddyfile caddy:2.8-alpine caddy validate --config /etc/caddy/Caddyfile` (con `SITE_DOMAIN` y `ACME_EMAIL` definidos).
