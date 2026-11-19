# Fase 6A: validación técnica del despliegue

Estado: **validación estática y de aplicación completada; arranque real con Docker pendiente** de un entorno con Docker Compose v2. Nada se ha desplegado ni publicado.

## 1. Fotografías heredadas en el historial de Git

- `media/` dejó de versionarse en `67c825f`. Los 140 archivos siguen en el disco local.
- El historial conserva **143 versiones de imagen (8,5 MB)** de `media/`, introducidas entre marzo y abril de 2022 por 6 commits, y ya publicadas en `origin/master` (GitHub). Cualquier `git clone` del repositorio las sigue descargando.
- Otras imágenes versionadas: `home/static/home/img/*.jpg` y `profiles/static/profile/img/profile-hero.jpg`, que proceden de Pexels con atribución en el README, y capturas y diagramas propios en `README/`. Los fondos de `home/static` ya no se usan en las plantillas actuales.

### Cómo dejar de distribuirlas (requiere tu autorización; no se ha hecho nada)

1. **Inmediato y reversible:** pon el repositorio de GitHub en privado y revisa quién tiene acceso, forks incluidos. Así se dejan de servir a terceros mientras se decide lo demás.
2. **Limpieza del historial** (reescribe todos los hashes; los 11 commits locales cambiarán):
   ```bash
   # En un clon espejo nuevo, nunca en el directorio de trabajo
   git clone --mirror https://github.com/<cuenta>/<repo>.git repo-limpio.git
   cd repo-limpio.git
   git filter-repo --invert-paths --path media/       # requiere git-filter-repo
   git push --force --mirror                           # solo con autorización expresa
   ```
   Después: cada colaborador vuelve a clonar (los clones antiguos conservan las imágenes), se cierran o rehacen las PR abiertas, y se pide a GitHub Support que purgue las referencias en caché y las vistas de commits antiguos. Los forks existentes no se limpian.
3. **Alternativa sin reescritura:** crear un repositorio nuevo a partir del estado actual (un único commit inicial) y archivar el antiguo como privado.
4. **Prevención:** `media/` está en `.gitignore`. Las fotografías aprobadas se gestionan como `CatalogImage` con licencia registrada y se guardan en el volumen privado, nunca en Git. Antes de cada push, revisa `git diff --stat origin/master` para comprobar que no aparecen imágenes nuevas fuera de `static/` y `README/`.

## 2. Docker

| Comprobación | Estado |
|---|---|
| Docker Compose v2 en este equipo | **No disponible**: Docker Toolbox 19.03 con `docker-compose` 1.24 y máquina VirtualBox detenida. No se ha instalado ni arrancado nada. |
| Construcción de imagen, arranque, salud, reinicios, persistencia, logs, copia y restauración | **No ejecutado.** Preparado en [deploy/smoke/run.sh](deploy/smoke/run.sh) |
| Validación estática | `compose.yaml` analizado como YAML (servicios, puertos, redes y volúmenes revisados); scripts comprobados con `bash -n` y `sh -n`. **No equivale a un arranque.** |
| Validación del `Caddyfile` | **No ejecutada** (no hay binario de Caddy). La cubre el paso de arranque de la prueba aislada. |

### Prueba de despliegue aislada

Requisitos: una máquina o VM Linux desechable (no el VPS en servicio) con Docker Engine y Compose v2 ≥ 2.20, `curl` y los puertos 127.0.0.1:18080 y 18443 libres.

```bash
git clone <repo> perfumeria && cd perfumeria && git checkout feature/prelaunch-security
cd deploy && ./smoke/run.sh          # KEEP=1 ./smoke/run.sh para inspeccionar después
```

El script crea el proyecto `perfumeria-smoke` con secretos aleatorios y el dominio `perfumeria.localhost` (certificado de la CA interna de Caddy). Solo escucha en 127.0.0.1, no contacta servicios reales y borra sus volúmenes al terminar. Comprueba:

- Construcción, usuario sin privilegios y ausencia de `env.py`, `.env`, SQLite o media en la imagen.
- Recuperación ante errores: `web` se niega a arrancar con migraciones pendientes o con `STORE_MODE=live`. Migraciones aplicadas y estado *healthy* de los tres servicios.
- Exposición: sin puertos en `db` ni en `web`, Caddy no alcanza PostgreSQL y Gunicorn no es accesible desde el host.
- TLS verificado, HSTS y cabeceras, sin cabecera `Server`, cookie CSRF `Secure; SameSite=Lax`, CSRF 403 sin token, redirecciones HTTP→HTTPS y `www`→dominio.
- `/checkout/` 403. `/healthz/` y `/media/` 404 a través de Caddy. Estáticos con caché.
- Correo: backend `dummy`, ningún formulario de aviso visible y ninguna clave de Stripe.
- Catálogo: 265 borradores cargados, 0 publicados; la ficha da 404 y no aparece en el listado, el sitemap ni la búsqueda.
- Tokens: un token marcado no aparece en el log de Caddy ni en los logs de los contenedores; las IP salen enmascaradas; la rotación de logs está activa.
- Reinicio automático tras la caída del proceso, `restart`, `down`/`up` con persistencia de datos.
- Copia: archivos con permisos 600 y sin la contraseña de la base; `restore.sh --verify` en una base temporal; restauración completa del stack de prueba con comprobación del estado restaurado.

El resultado queda en `report.txt` (ruta indicada al final). Repite la prueba tras cualquier cambio en `Dockerfile`, `compose.yaml`, `Caddyfile` o los scripts.

## 3. Seguridad revisada en esta fase

- **Formularios sin correo operativo.** Los formularios de aviso de lanzamiento y disponibilidad, el registro de cuentas y la recuperación de contraseña prometían correos que en producción se descartan. Ahora se ocultan y sus vistas rechazan el envío sin guardar datos mientras `NOTICE_SIGNUPS_OPEN` o `ACCOUNT_SIGNUPS_OPEN` estén desactivados. Estos indicadores dependen de `EMAIL_DELIVERY=smtp` y de `INTEREST_EMAIL_DELIVERY=1`. En su lugar aparece un aviso en blanco y dorado.
- **`restore.sh`.** Una ruta de copia relativa fallaba tras el `cd`. Corregido.
- **`docker compose run` y la IP fija de `web`.** La IP fija podía chocar con las ejecuciones puntuales (migraciones, restauración). Ahora `web` usa una IP dinámica del rango superior y solo Caddy tiene IP fija, que es la única de confianza para `X-Forwarded-For`.
- **Copias.** Los scripts no contienen contraseñas: `pg_dump` y `pg_restore` se ejecutan dentro del contenedor con el socket local, y las credenciales están en `.env.production` (600). El volcado no incluye contraseñas de roles, pero sí correos y hashes de contraseñas de usuarios, por eso se guarda con permisos 600.
- **Copia externa.** [deploy/backup/offsite.sh](deploy/backup/offsite.sh) cifra con `age` a claves públicas y sube con `rclone --immutable`. Se niega a funcionar si encuentra una clave privada en el servidor. Requiere que el operador instale `age` y `rclone` y elija proveedor.

## 4. Pruebas

- Suite Django: ver el informe de entrega (SQLite y PostgreSQL 17).
- Restauración de prueba: **no ejecutada en este equipo.** El PostgreSQL portátil local no incluye `pg_dump` ni `pg_restore`. La prueba aislada la ejecuta con la imagen oficial `postgres:17-alpine` sobre datos desechables.

## 5. Riesgos pendientes

- Arranque real con Docker y validación del `Caddyfile` sin verificar.
- Fotografías sin derechos en el historial público de GitHub.
- Copia externa cifrada sin proveedor ni claves definidos.
- Cortafuegos del VPS: Docker publica los puertos saltándose `ufw`. Solo Caddy publica puertos, pero revisa las reglas `DOCKER-USER` si se añaden servicios.
- Textos legales y datos del responsable pendientes ([PRIVACIDAD_BORRADOR.md](PRIVACIDAD_BORRADOR.md)).
- Ninguna ficha de referencia cumple hoy los requisitos de aprobación (faltan concentración, formato y fuentes), así que el escaparate se publicaría vacío hasta revisar las primeras.
