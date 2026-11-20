# Despliegue en el VPS compartido con Foro IA al Día

Estado: **preparado, no desplegado.** Nada de lo descrito aquí se ha ejecutado en el VPS.

VPS OVHcloud con Ubuntu 26.04, 4 vCores, 8 GB de RAM (6,2 GiB libres) y 61 GB de disco libres. Foro IA al Día ya funciona con 7 contenedores; su Caddy (`foroia-production-caddy-1`) ocupa 80/443 en las redes `foroia-production_backend` y `foroia-production_edge`. Dominio nuevo: `perfumeriaelbuenolor.es`.

## Estado del despliegue (19/11/2026, UTC)

**Instalación aislada hecha; web no publicada.** No se ha cambiado ni el Caddy del foro ni el DNS.

- **Código.** `/srv/perfumeria/app` (rama `feature/prelaunch-security`, commit `f02f4a8`). Secretos generados en el VPS en `deploy/shared/.env.production` (600, nunca mostrados).
- **Contenedores.**
  - `perfumeria-production-perfumeria-db-1`: sano; solo en `perfumeria-production_backend` (interna, 172.21.0.0/16).
  - `perfumeria-production-perfumeria-web-1`: sano; en `perfumeria-production_backend` y en `foroia-production_edge` con el nombre `perfumeria-web`. Sin puertos, sistema de archivos de solo lectura, usuario `app`.
- **Imágenes.** `perfumeria-web:f02f4a8` en uso; `perfumeria-web:ec7d69b` se conserva para volver atrás.
- **Base de datos.** 58 migraciones aplicadas en `perfumeria`; `verify-db-target.sh` confirmó el destino (172.21.0.2). Hay 0 productos: el catálogo de referencia no se ha cargado.
- **Pruebas internas superadas.**
  - Portada 200; `/checkout/` 403; HTTP redirige a HTTPS (301).
  - HSTS, `X-Frame-Options`, `nosniff`, `Referrer-Policy` y cookie CSRF `Secure; SameSite=Lax`.
  - Estáticos servidos por WhiteNoise con caché de un día; el sitemap solo lista la portada, el catálogo y la guía de familias.
  - Sin formularios de correo ni registro; un token inválido devuelve 410 y no aparece en los logs.
  - Correo `dummy`, sin claves de Stripe, ventas desactivadas.
  - Desde el Caddy del foro: `perfumeria-web` resuelve a 172.19.0.4 y `web` sigue resolviendo solo a 172.19.0.2 (la web del foro); el Caddy del foro llega a `/healthz/` con 200.
- **Consumo en reposo.** Web unos 128 MiB de 1 GiB; base de datos unos 36 MiB de 768 MiB. La RAM disponible del VPS pasó de 6,34 a 6,14 GiB.
- **Foro.** Mismas horas de arranque, sin reinicios, mismo estado de salud y mismo Caddyfile (inodo y SHA-256) antes y después.
- **Permisos del foro.** 79 archivos `666 root:root` de `/opt/foroia` pasados a 644 (`chmod go-w`). Contenido, propietarios y fechas sin cambios. Copia y `ROLLBACK.sh` en `/srv/perfumeria/foro-permisos-20261119T235315Z/`.
- **Caddy en el código fuente del foro (preparado, no aplicado).** Rama local `perfumeria-caddy` (commit `13cff12`) en un *worktree* aparte (`Desktop/Mi Blog/foroia-codex-perfumeria-caddy`). El parche está en [deploy/shared/foroia/0001-perfumeria-caddy.patch](deploy/shared/foroia/0001-perfumeria-caddy.patch). Validado con Caddy 2.11.7 sobre el fuente del foro y sobre el Caddyfile de producción, sin avisos nuevos.
  - Ojo: el fuente del foro ya incluye un bloque `http://www.foroiaaldia.com` que todavía no está en producción, así que su próxima release lo desplegará también.

## Plan: dominio y HTTPS conservando el correo de OVHcloud (preparado, no aplicado)

### Diagnóstico del dominio (20/11/2026, 00:58 CET)

- **En OVHcloud el dominio está bien.** `dns103.ovh.net` sirve la zona: SOA, NS `dns103`/`ns103.ovh.net`, A `@` y `www` = `213.186.33.5`, MX `mx1`/`mx2`/`mx3.mail.ovh.net`, SPF `v=spf1 include:mx.ovh.com -all`, TXT `1|www.perfumeriaelbuenolor.es`, y `ftp` como CNAME de `@`. No hay AAAA ni DMARC.
- **El registro `.es` aún no publica la delegación.** `a`/`c`/`g`/`h.nic.es` responden NXDOMAIN para el dominio, con la zona `.es` en el serial `2026112001` (versión 01 del 20/11). La delegación hacia `dns103`/`ns103.ovh.net` no está todavía en la zona publicada de Red.es.
- **Por qué devolvía NXDOMAIN.** No era un error de nombre: no existe ninguna variante con tilde, con guiones ni `.com.es`. Tampoco un fallo de la zona de OVH, que ya responde correctamente. Que el panel diga «activo» y que el dominio esté publicado en la zona `.es` son dos pasos distintos: el segundo depende de Red.es y se refleja en una versión posterior de su zona.
- **Caché negativa.** La zona `.es` tiene un TTL negativo de 86 400 s. Los resolvedores que ya respondieron NXDOMAIN (1.1.1.1, 8.8.8.8, el del VPS) pueden repetirlo hasta 24 h después de la publicación. La comprobación fiable es preguntar directamente a `a.nic.es`. Si en 24–48 h sigue sin aparecer allí, conviene abrir una incidencia con OVHcloud para revisar el estado en Red.es.

### Requisitos antes de tocar nada público

1. `a.nic.es` devuelve los NS `dns103`/`ns103.ovh.net` para `perfumeriaelbuenolor.es`.
2. La instalación aislada sigue sana (`preflight.sh` y las pruebas internas del paso 5).
3. Hay una decisión tomada sobre Caddy: una release del foro con la rama `perfumeria-caddy`, o `caddy-apply.sh` en caliente.
4. Copia de la zona: en el panel, *Zona DNS → Cambiar en modo texto*; copia todo el texto y guárdalo en `auditorias/zona-perfumeriaelbuenolor.es-<fecha>.txt`.

### Cambios DNS propuestos 🔴 (zona en `dns103.ovh.net`)

| Registro | Ahora | Propuesto | Motivo |
|---|---|---|---|
| Redirección web de OVH (`@` y `www`) | activa: A `213.186.33.5` + TXT `1\|www…` | **eliminar en el panel** (pestaña *Redirección*) | Gestiona por sí sola el A y el TXT; si se edita el A con ella activa, el panel lo revierte o entra en conflicto |
| A `@` | `213.186.33.5` | `146.59.35.127`, TTL 300 | Apuntar al VPS (al Caddy del foro) |
| A `www` | `213.186.33.5` | `146.59.35.127`, TTL 300 (o CNAME a `perfumeriaelbuenolor.es.`) | Caddy redirige `www` al dominio principal |
| AAAA `@`/`www` | ninguno | **ninguno por ahora** | El foro no publica AAAA; el camino IPv6 del VPS no está probado. Se añade más adelante, tras probar IPv6 |
| MX `mx1`–`mx3.mail.ovh.net` | — | **sin cambios** | El correo de OVHcloud no depende del A |
| SPF `v=spf1 include:mx.ovh.com -all` | — | **sin cambios** | También cubre el SMTP de OVH (`ssl0.ovh.net`) si Django lo usa más adelante |
| Otros TXT y NS | — | **sin cambios** | |
| `ftp` CNAME → `@` | apunta a `213.186.33.5` | quedará apuntando al VPS | Revisa si se usa; si no, se puede borrar más adelante |
| CAA | ninguno | opcional: `0 issue "letsencrypt.org"` y `0 issue "sectigo.com"` | Limita la emisión a las CA que usa Caddy (Let's Encrypt y ZeroSSL) |
| DMARC `_dmarc` | ninguno | recomendado más adelante: `v=DMARC1; p=none; rua=mailto:<buzón>` | Protección del correo; decisión del titular |

### Orden de ejecución (cada paso con autorización)

1. Exportar la zona (requisito 4).
2. En el panel, eliminar la redirección web y crear los A de `@` y `www` hacia `146.59.35.127` con TTL 300.
3. Verificar en el servidor autoritativo y en el público:
   ```powershell
   Resolve-DnsName perfumeriaelbuenolor.es -Type A -Server dns103.ovh.net -DnsOnly
   Resolve-DnsName perfumeriaelbuenolor.es -Type MX -Server dns103.ovh.net -DnsOnly   # MX intactos
   Resolve-DnsName perfumeriaelbuenolor.es -Type A -Server 1.1.1.1 -DnsOnly           # puede tardar por la caché negativa
   ```
4. Esperar a que los resolvedores públicos (y los de Let's Encrypt) respondan el A nuevo, hasta 1 h tras la publicación, para no desperdiciar intentos de validación. En el VPS, `REQUIRE_DNS=1 ./shared/preflight.sh` debe dar el DNS en PASS. Si el resolvedor del VPS conserva el NXDOMAIN en caché, `sudo resolvectl flush-caches` lo limpia (operación local, con autorización).
5. Publicar en Caddy: release del foro con la rama `perfumeria-caddy` (recomendado), o `sudo -E FORO_URLS="https://foroiaaldia.com/ https://www.foroiaaldia.com/" ./shared/caddy-apply.sh`. El Caddy del foro obtiene el certificado por HTTP-01/TLS-ALPN en los puertos 80/443, que ya están publicados.
6. Verificación pública (paso 8 de esta guía), comprobando que el foro responde igual y que el correo sigue funcionando: MX intactos, envío y recepción de prueba en la cuenta de OVH y webmail.
7. Pasadas 24–48 h estables, subir el TTL de A y `www` a 3600.

### Reversión DNS

Restaurar el texto de zona exportado, o en el panel volver a poner A `@`/`www` = `213.186.33.5` y recrear la redirección web (eso recrea el TXT `1|…`). Combinar con `caddy-rollback.sh` o con retirar el bloque de la release del foro. Los MX y el SPF nunca se tocan, así que el correo no se ve afectado en ningún paso.

## Auditoría real del VPS (19/11/2026)

Resultado de `audit-readonly.sh` ejecutado por SSH, sin escribir en el VPS: **0 fallos y 2 avisos (DNS)**. Los informes completos están en `auditorias/`, carpeta local ignorada por Git.

- **Host.** Ubuntu 26.04 LTS, Docker 29.9.2, Compose 5.6.1. 6,3 GiB de RAM disponibles, sin swap. 61 GB libres.
- **Contenedores del foro.** Los 7 contenedores de `foroia-production` están en marcha y sanos, sin límites de memoria. El proyecto `foroia-seo-review` está detenido.
- **Caddy del foro.** Imagen `caddy:2-alpine`, versión 2.11.7. El Caddyfile está montado como archivo suelto desde `/opt/foroia/deploy/Caddyfile` (root, 644); el inodo coincide dentro y fuera del contenedor. La configuración actual es válida. El API de administración responde en `127.0.0.1:2019`, así que se puede recargar sin reiniciar. Publica 80/443 por IPv4 e IPv6.
- **Validación del bloque.** El bloque de la perfumería, añadido al Caddyfile actual, valida con esa misma versión (`caddy adapt --validate` por entrada estándar dentro del contenedor, sin escribir nada).
- **`foroia-production_edge`.** Solo están `foroia-production-caddy-1` (alias `caddy`) y `foroia-production-web-1` (alias **`web`**). Confirma que un servicio llamado `web` habría colisionado; `perfumeria-web` no colisiona.
- **Base de datos del foro.** `foroia-production-db-1` solo está en `foroia-production_backend`: no es alcanzable desde `perfumeria-web`.
- **Puertos en escucha.** 22, 80 y 443, más la resolución DNS local.
- **Riesgo: el Caddyfile pertenece a las releases del foro.** `/opt/foroia` no es un repositorio Git: el foro se despliega con releases (`make-release.py`, `receipts/`). Una release futura del foro puede sobrescribir `deploy/Caddyfile` y eliminar el bloque de la perfumería. El foro seguiría funcionando, pero la perfumería quedaría fuera de línea. Ver «Decisión pendiente sobre Caddy».
- **Hallazgo del foro (no de la perfumería).** Varios archivos de `/opt/foroia/deploy` tienen permisos 666 (escribibles por cualquier usuario): `backup.sh`, `foroia-backup.service`/`.timer`, `foroia-health.service`/`.timer`, `install-docker.sh`, `prepare-docker.sh`, `restore-check.sh` y `production.env.example`. Algunos los ejecutan temporizadores de systemd, previsiblemente como root. Se recomienda corregirlos a 644 dentro del proceso del foro.
- **IPv6.** El VPS tiene IPv6 (`2001:41d0:601:1100::8fe2`) y Caddy escucha en `[::]`, así que conviene un registro AAAA.

### Decisión pendiente sobre Caddy

1. **Recomendada.** Incorporar el bloque de `deploy/shared/perfumeria.caddy` al Caddyfile **fuente** del foro, para que cada release del foro lo conserve. Para la primera publicación se puede aplicar en caliente con `caddy-apply.sh`, siempre que la siguiente release del foro ya lo incluya.
2. Solo `caddy-apply.sh`. Funciona, pero se pierde con la próxima release del foro y habría que volver a aplicarlo cada vez.
3. A largo plazo: que el Compose del foro monte un directorio de sitios con `import`. Requiere recrear una vez el Caddy del foro (breve reinicio en una ventana de mantenimiento).


| Marca | Significado |
|---|---|
| 🟢 | Solo lectura. No cambia nada en el VPS. |
| 🟡 | Crea recursos **nuevos y exclusivos** de la perfumería (archivos en `/srv/perfumeria`, imagen, contenedores y volúmenes `perfumeria-production_*`). No toca el foro. **Requiere tu autorización para empezar a ejecutar en el VPS.** |
| 🔴 | Toca algo compartido o público: la red del foro, el Caddyfile del foro, la recarga de Caddy, el DNS o datos de producción. **Requiere tu autorización expresa en cada paso.** |

## Arquitectura

```
Internet ──443──▶ foroia-production-caddy-1 (del foro, sin reiniciar)
                     │  foro: rutas existentes, sin cambios
                     │  perfumeriaelbuenolor.es ──▶ perfumeria-web:8000
                     ▼
        red foroia-production_edge (del foro, external)
                     │
              perfumeria-web (Gunicorn + Django + WhiteNoise)
                     │
        red perfumeria-production_backend (internal: true, exclusiva)
                     │
              perfumeria-db (PostgreSQL 17, volumen propio)
```

- **Proyecto Compose `perfumeria-production`**, en [deploy/shared/compose.yaml](deploy/shared/compose.yaml). No incluye Caddy ni publica puertos. Volúmenes propios `perfumeria-production_{pgdata,static,media,catalog_assets}`.
- **Nombres únicos.** Compose registra el nombre de cada servicio como alias DNS en todas sus redes. Un servicio `web` en `foroia-production_edge` respondería también a `web`, y el Caddy del foro podría repartir el tráfico del foro hacia la perfumería. Por eso los servicios se llaman `perfumeria-web` y `perfumeria-db`, y `preflight.sh` comprueba que ningún contenedor del foro use esos nombres.
- **Solo `perfumeria-web`** se une a `foroia-production_edge`. `perfumeria-db` solo está en la red interna exclusiva, separado del PostgreSQL del foro (otra red, otro volumen y otras credenciales).
- **Estáticos con WhiteNoise** (`DJANGO_SERVE_STATIC=1`). El Caddy del foro no puede montar nuestro volumen sin recrearse. `/media/` y `/healthz/` no se publican; las imágenes aprobadas salen por Django.
- **IP del visitante.** Django solo acepta `X-Forwarded-For` del contenedor `foroia-production-caddy-1`, resuelto por nombre cada 30 s, de modo que si el foro recrea su Caddy y cambia de IP sigue funcionando. Si el nombre no resuelve, no confía en nadie.
- **Fijado en el Compose**, sin que el archivo de entorno pueda cambiarlo: `STORE_MODE=prelaunch`, `EMAIL_DELIVERY=disabled`, `INTEREST_EMAIL_DELIVERY=0` y claves de Stripe vacías. Los formularios de aviso, registro y recuperación de contraseña siguen ocultos (Fase 6A).
- **Logs.** El log de acceso de la perfumería lo escribe el Caddy del foro en su volumen `/data`, en `/data/perfumeria/access.log` (20 MiB × 10, 30 días, tokens redactados e IP enmascaradas). Los logs de nuestros contenedores rotan en Docker.
- **Límites:** `perfumeria-db` 1 CPU y 768 MiB; `perfumeria-web` 1,5 CPU y 1 GiB (2 workers × 2 hilos). Total máximo: 2,5 CPU y unos 1,8 GiB. Ambos con `pids_limit` y logs rotados a 10 MB × 5.

### Riesgo aceptado al compartir `foroia-production_edge`

Cualquier contenedor del foro conectado a esa red puede alcanzar `perfumeria-web:8000` sin pasar por Caddy, y la perfumería puede alcanzar los servicios del foro en esa red. `preflight.sh` lista los contenedores conectados. La mitigación actual: Gunicorn no confía en cabeceras salvo las del Caddy, no hay datos sensibles en abierto, y la base de datos está en una red aparte. **Mejora posible (requiere cambiar el Compose del foro):** una red `perfumeria_edge` exclusiva a la que se conecte solo el Caddy del foro.

## Archivos

| Archivo | Uso | Autorización |
|---|---|---|
| [deploy/shared/compose.yaml](deploy/shared/compose.yaml) | Stack de la perfumería para el VPS compartido | 🟡 / 🔴 (unirse a la red del foro) |
| [deploy/shared/env.production.example](deploy/shared/env.production.example) | Plantilla de `deploy/shared/.env.production` (600, ignorado por Git) | 🟡 |
| [deploy/shared/perfumeria.caddy](deploy/shared/perfumeria.caddy) | Bloque delimitado para el Caddyfile del foro | 🔴 al aplicarlo |
| [deploy/shared/audit-readonly.sh](deploy/shared/audit-readonly.sh) | Auditoría del VPS por SSH sin copiar nada al servidor (`ssh … 'bash -s' < …`); no escribe, no crea contenedores | 🟢 |
| [deploy/shared/preflight.sh](deploy/shared/preflight.sh) | Validación previa completa | 🟢 |
| [deploy/shared/caddy-backup.sh](deploy/shared/caddy-backup.sh) | Copia verificable de la configuración actual de Caddy (Caddyfile, JSON en ejecución, metadatos, SHA256SUMS, validación); `--verify` la comprueba de nuevo | 🟡 |
| [deploy/shared/verify-db-target.sh](deploy/shared/verify-db-target.sh) | Demuestra antes de migrar que Django solo llega a `perfumeria-db` | 🔴 (contenedor temporal en la red del foro) |
| [deploy/shared/rehearsal/](deploy/shared/rehearsal/) | Ensayo completo contra una imitación del foro en una VM desechable | Solo VM |
| [deploy/shared/caddy-check.sh](deploy/shared/caddy-check.sh) | Valida «Caddyfile actual + bloque» con la imagen del Caddy del foro en un contenedor desechable sin red | 🟡 (no toca el foro, pero crea un contenedor y un directorio temporales que se borran al terminar) |
| [deploy/shared/caddy-apply.sh](deploy/shared/caddy-apply.sh) | Copia, añade el bloque, valida y recarga sin reiniciar; compara las respuestas del foro antes y después | 🔴 |
| [deploy/shared/caddy-rollback.sh](deploy/shared/caddy-rollback.sh) | Retira solo el bloque y recarga | 🔴 |
| [deploy/backup/backup.sh](deploy/backup/backup.sh), [restore.sh](deploy/backup/restore.sh) | Ya admiten el modo compartido (servicios `perfumeria-*`, nunca detienen el Caddy del foro) | 🟡 / 🔴 restaurar |

En el VPS conviene un alias para no olvidar ninguna opción:

```bash
cd /srv/perfumeria/app/deploy
pc() { docker compose -p perfumeria-production -f shared/compose.yaml --env-file shared/.env.production "$@"; }
```

## Procedimiento

### 0a. Auditoría remota sin escribir en el VPS 🟢

```bash
# Desde el equipo con el repositorio; en el VPS no se copia ni se crea nada
ssh <usuario>@<vps> 'bash -s' < deploy/shared/audit-readonly.sh > audit-vps.txt
# Si el Caddyfile solo lo lee root:
ssh -t <usuario>@<vps> 'sudo bash -s' < deploy/shared/audit-readonly.sh > audit-vps.txt
```

Revisa en `audit-vps.txt`:
- la memoria, el disco y el estado de los 7 contenedores;
- cómo está montado el Caddyfile (archivo o directorio, y si el inodo coincide dentro y fuera del contenedor);
- que el API de administración responde (necesario para recargar sin reiniciar);
- que la configuración actual valida;
- los contenedores y nombres DNS de `foroia-production_edge`, avisando si alguna base de datos está en esa red;
- dónde están las bases del foro;
- el DNS.

Ejecuta `caddy-check.sh` y `preflight.sh` (paso 2) cuando el código ya esté en el VPS.

### 0b. Ensayo en la VM (recomendado antes de tocar el VPS)

```bash
cd ~/perfumeria/deploy && ./shared/rehearsal/run.sh; echo "exit=$?"
```

El ensayo levanta una **imitación** del foro con los mismos nombres: proyecto `foroia-production`, `foroia-production-caddy-1` con el Caddyfile montado como archivo suelto, un servicio `web` y una base `db` con una tabla de control. Después:
1. Ejecuta los scripts reales.
2. Comprueba que `caddy-apply.sh` rechaza un bloque inválido.
3. Aplica el bloque y comprueba la perfumería a través del Caddy del «foro».
4. Verifica que `web` sigue resolviendo solo al foro y que la base del foro no cambia.
5. Prueba copia y restauración en modo compartido.
6. Hace el rollback y comprueba que el Caddyfile vuelve a ser idéntico (mismo inodo y SHA-256).
7. Comprueba que ningún contenedor del foro se reinicia en ningún momento.

Usa `local_certs`, así que no pide certificados reales. Se niega a funcionar si encuentra un foro o una perfumería reales en la máquina.

### 0c. Antes de empezar (en Windows) 🟢

```powershell
git status --short                       # vacío
.\.venv-django52\Scripts\python.exe manage.py test --noinput
git bundle create "$env:USERPROFILE\perfumeria-vps.bundle" feature/prelaunch-security
git bundle verify "$env:USERPROFILE\perfumeria-vps.bundle"
(Get-FileHash "$env:USERPROFILE\perfumeria-vps.bundle" -Algorithm SHA256).Hash
git rev-parse --short feature/prelaunch-security      # = RELEASE
scp "$env:USERPROFILE\perfumeria-vps.bundle" <usuario>@<vps>:~/
```

Prueba primero `deploy/smoke/run.sh` en la VM Ubuntu ([deploy/smoke/UBUNTU.md](deploy/smoke/UBUNTU.md)). Esa prueba valida la imagen y el stack autónomo; este modo compartido tiene su propia verificación en el paso 5.

### 1. Código y secretos en el VPS 🟡

```bash
sha256sum ~/perfumeria-vps.bundle                          # comparar con Windows
sudo install -d -m 750 -o "$USER" -g "$USER" /srv/perfumeria
git clone --branch feature/prelaunch-security ~/perfumeria-vps.bundle /srv/perfumeria/app
cd /srv/perfumeria/app/deploy
cp shared/env.production.example shared/.env.production && chmod 600 shared/.env.production
nano shared/.env.production       # RELEASE, SECRET_KEY, POSTGRES_PASSWORD (ver comentarios)
```

### 2. Validación previa 🟢

```bash
./shared/preflight.sh             # fails=0; los avisos de DNS son normales hasta el paso 6
./shared/caddy-check.sh           # 🟡 contenedor temporal sin red: Caddyfile actual válido y válido con el bloque añadido
sudo -E ./shared/caddy-backup.sh  # 🟡 copia verificable en /srv/perfumeria/caddy-backups/config-<fecha>/
```

`preflight.sh` comprueba, entre otras cosas:
- versiones de Compose, RAM y disco;
- que `foroia-production-caddy-1` está en marcha, conectado a `foroia-production_edge` y sirviendo el 443;
- que su Caddyfile viene de un *bind mount* legible y que el API de administración no está desactivado (necesario para recargar sin reiniciar);
- que no hay colisiones de nombres en la red;
- el archivo de entorno: permisos 600, sin marcadores pendientes y `PROXY_SERVICE` vacío;
- que el Compose resuelve con el proyecto y los servicios esperados, sin puertos y con prelanzamiento y correo fijados;
- el DNS.

`caddy-check.sh` lanza un contenedor temporal con la imagen del Caddy del foro: sin red, con los montajes del foro en solo lectura y con `/data` vacío. El Caddy en marcha no se toca. Si el Caddyfile del foro no está en un *bind mount* o tiene `admin off`, **para aquí**: añadir el sitio exigiría cambiar el Compose del foro.

### 3. Imagen y base de datos 🟡 (y 🔴 para `pc run`, ver nota)

```bash
pc build                                  # compila en el VPS; mejor en horas de poco tráfico (no tiene límite de CPU)
pc up -d perfumeria-db
pc ps                                      # perfumeria-db healthy
./shared/verify-db-target.sh              # Django debe conectar a perfumeria-db (base 'perfumeria'); si no, NO migrar
pc run --rm -T perfumeria-web python manage.py migrate --noinput
pc run --rm -T perfumeria-web python manage.py migrate --check && echo "migraciones al día"
pc run --rm perfumeria-web python manage.py createsuperuser
```

**Nota:** `pc run … perfumeria-web` crea contenedores temporales que también se conectan a `foroia-production_edge` mientras duran, así que la migración y `createsuperuser` entran en la autorización 2. Para no compilar en el VPS, puedes construir en la VM de pruebas y transferir la imagen con `docker save perfumeria-web:<RELEASE> | gzip | ssh <vps> 'gunzip | docker load'`.

### 4. Arrancar la web y unirla a la red del foro 🔴

```bash
pc up -d perfumeria-web
pc ps                                      # perfumeria-web healthy (unos 40-60 s)
docker network inspect -f '{{range .Containers}}{{println .Name}}{{end}}' foroia-production_edge   # aparece perfumeria-production-perfumeria-web-1
```

### 5. Verificación interna, sin público 🟢

```bash
pc exec -T perfumeria-web python deploy/healthcheck.py && echo "salud OK"
# Desde el Caddy del foro (solo lectura: wget dentro del contenedor, sin cambiar nada)
docker exec foroia-production-caddy-1 wget -q -S -O /dev/null \
  --header 'Host: perfumeriaelbuenolor.es' --header 'X-Forwarded-Proto: https' http://perfumeria-web:8000/ 2>&1 | head -n1   # HTTP/1.1 200
docker exec foroia-production-caddy-1 wget -q -O - \
  --header 'Host: perfumeriaelbuenolor.es' --header 'X-Forwarded-Proto: https' http://perfumeria-web:8000/checkout/ 2>&1 | head -n1  # 403
pc exec -T perfumeria-web python manage.py shell --no-imports -c \
  "from products.models import Product; print('publicados', Product.objects.published().count())"   # 0
pc logs --tail 50 perfumeria-web
```

### 6. DNS 🔴 (en el registrador; no se ha modificado nada)

> Estado y plan detallado en «Plan: dominio y HTTPS conservando el correo de OVHcloud». No uses aquí el MX nulo ni `v=spf1 -all`: el dominio tiene correo de OVHcloud y sus MX y SPF se conservan.

Obtén las IP del VPS con `ip -o addr show scope global` (o en el panel de OVHcloud). Antes de cambiar nada, revisa los registros actuales del dominio (por ejemplo, una página de aparcamiento) y anótalos para poder revertir.

| Tipo | Nombre | Valor | TTL | Nota |
|---|---|---|---|---|
| A | `@` | `<IPv4 del VPS>` | 300 (3600 cuando esté estable) | Sustituye cualquier A de aparcamiento |
| AAAA | `@` | `<IPv6 del VPS>` | 300 | Solo si el foro ya sirve por IPv6 (`docker port foroia-production-caddy-1` muestra `[::]:443`); si no, ninguno |
| CNAME | `www` | `perfumeriaelbuenolor.es.` | 300 | Caddy redirige `www` al dominio principal |
| CAA | `@` | `0 issue "letsencrypt.org"` | 3600 | Añade `0 issue "sectigo.com"` si el Caddy del foro usa ZeroSSL como respaldo (es el comportamiento por defecto de Caddy) |
| MX | `@` | `0 .` (MX nulo) | 3600 | Mientras el dominio no reciba correo |
| TXT | `@` | `v=spf1 -all` | 3600 | El dominio no envía correo; se cambiará al configurar SMTP |
| TXT | `_dmarc` | `v=DMARC1; p=reject` | 3600 | Ídem |

Comprueba la propagación antes del paso 7: `REQUIRE_DNS=1 ./shared/preflight.sh` (DNS en PASS) y `resolvectl query perfumeriaelbuenolor.es`. Si Caddy recibe el dominio antes de que el DNS apunte al VPS, reintentará la emisión de certificados y puede acercarse a los límites de Let's Encrypt.

### 7. Publicar en el Caddy del foro 🔴

```bash
sudo -E FORO_URLS="https://<dominio-del-foro>/ https://<dominio-del-foro>/<otra-ruta>" ./shared/caddy-apply.sh
```

Pasos que da el script:
1. Repite la validación previa exigiendo que el DNS ya apunte al VPS.
2. Guarda una copia del Caddyfile en `/srv/perfumeria/caddy-backups/` (con su `sha256`).
3. Valida el candidato en un contenedor desechable.
4. Anota el estado HTTP de las URL del foro.
5. **Añade** el bloque al final del Caddyfile, sin sobrescribirlo y conservando el mismo archivo (inodo), y comprueba que el contenedor ve el cambio.
6. Valida dentro del contenedor y ejecuta `caddy reload`, que es una recarga en caliente: sin reinicio y sin cortar conexiones.
7. Si algo falla, o si las URL del foro responden distinto que antes, restaura el contenido original y vuelve a recargar.

Después: `docker logs --since 5m foroia-production-caddy-1 | grep -i perfumeria` (emisión del certificado).

### 8. Verificación pública 🟢

```bash
D=https://perfumeriaelbuenolor.es
curl -sI $D/ | head -n1                                     # 200
curl -sI $D/ | grep -iE 'strict-transport|x-frame|x-content-type|referrer-policy'
curl -s -o /dev/null -w '%{http_code}\n' $D/checkout/       # 403
curl -s -o /dev/null -w '%{http_code}\n' $D/healthz/        # 404
curl -s -o /dev/null -w '%{http_code}\n' $D/media/x.jpg     # 404
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' http://perfumeriaelbuenolor.es/      # 308 -> https
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://www.perfumeriaelbuenolor.es/ # 301 -> apex
curl -sI $D/static/css/storefront.css | grep -i cache-control                                # max-age=86400
curl -sI $D/accounts/login/ | grep -i 'set-cookie: csrftoken'                              # Secure; SameSite=Lax
curl -s $D/sitemap.xml | grep -c '<loc>'                    # sin fichas no aprobadas
curl -s $D/ | grep -c 'name="consent"'                      # 0 (formularios de correo ocultos)
curl -s -o /dev/null -w '%{http_code}\n' "$D/avisos/lanzamiento/confirmar/PRUEBA-TOKEN-$RANDOM/"   # 410
docker exec foroia-production-caddy-1 tail -n 5 /data/perfumeria/access.log | grep -c 'PRUEBA-TOKEN'  # 0
nc -zv -w 3 <IPv4 del VPS> 5432 ; nc -zv -w 3 <IPv4 del VPS> 8000       # desde fuera del VPS: ambos cerrados
```

Comprueba además que el foro responde igual que antes, en el navegador y con `curl`.

### 9. Copias y mantenimiento 🟡

```bash
crontab -e
# 15 3 * * * cd /srv/perfumeria/app/deploy && PERFUMERIA_ENV_FILE=shared/.env.production ./backup/backup.sh >> /srv/perfumeria/backup.log 2>&1
# 40 3 * * * cd /srv/perfumeria/app/deploy && docker compose -p perfumeria-production -f shared/compose.yaml --env-file shared/.env.production exec -T perfumeria-web python manage.py purge_notice_data --apply >> /srv/perfumeria/maintenance.log 2>&1
PERFUMERIA_ENV_FILE=shared/.env.production ./backup/backup.sh
PERFUMERIA_ENV_FILE=shared/.env.production ./backup/restore.sh --verify /srv/perfumeria/backups/<run>    # base temporal, no toca producción
```

Las copias van a `/srv/perfumeria/backups` (700/600) y solo incluyen la base y los volúmenes de la perfumería; las del foro siguen su propio proceso. Copia externa: [deploy/backup/offsite.sh](deploy/backup/offsite.sh), pendiente de proveedor. El catálogo de referencia se puede cargar como borradores con `pc exec -T perfumeria-web python manage.py load_reference_catalog --apply` (🟡). No publica nada; las fichas se aprueban una a una en el admin.

## Reversión

Ordenada de menor a mayor impacto. Ningún nivel detiene ni modifica contenedores del foro.

| Nivel | Acción | Órdenes | Autorización |
|---|---|---|---|
| R1 | Retirar el sitio del Caddy del foro | `sudo -E ./shared/caddy-rollback.sh`: solo quita el bloque entre marcadores, guarda copia, valida y recarga | 🔴 |
| R2 | Parar la perfumería conservando datos | `pc stop perfumeria-web`, o `pc down` (quita nuestros contenedores y la red `perfumeria-production_backend`; la red del foro y los volúmenes se conservan). **Nunca `down -v`.** | 🟡 |
| R3 | Volver a la versión anterior | `RELEASE=<commit anterior>` en `shared/.env.production` y después `pc up -d perfumeria-web`. Si la nueva versión aplicó migraciones, restaura la copia previa con `PERFUMERIA_ENV_FILE=shared/.env.production ./backup/restore.sh --replace-production <run>` (🔴, datos) | 🟡 / 🔴 |
| R4 | DNS | Restaurar los registros anotados en el paso 6 | 🔴 |
| R5 | Eliminar datos de la perfumería | Borrar volúmenes `perfumeria-production_*`: solo con autorización expresa y tras una copia verificada | 🔴 |

Haz siempre una copia (`backup.sh`) antes de cualquier migración y antes de R3.

## Resumen de autorizaciones necesarias

1. 🟡 Empezar a trabajar en el VPS: crear `/srv/perfumeria`, copiar el bundle, crear `.env.production`, compilar la imagen y arrancar `perfumeria-db` (solo red interna propia).
2. 🔴 Conectar contenedores `perfumeria-web` a `foroia-production_edge`: la migración y `createsuperuser` con `pc run` (temporales) y `pc up -d perfumeria-web` (permanente).
3. 🔴 Cambiar el DNS de `perfumeriaelbuenolor.es` en el registrador.
4. 🔴 `caddy-apply.sh`: añade el bloque al Caddyfile del foro y recarga Caddy en caliente.
5. 🟡 Instalar las tareas de cron de copia y limpieza.
6. 🔴 Cualquier restauración sobre la base de producción, rollback de Caddy o eliminación de volúmenes.

Las órdenes 🟢 (`preflight.sh`, `caddy-check.sh` y las verificaciones con `curl`, `docker inspect`, `docker logs` y `wget` dentro del Caddy) no cambian nada y se pueden ejecutar en cualquier momento.
