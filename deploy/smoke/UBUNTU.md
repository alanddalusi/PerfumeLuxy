# Prueba del stack Docker en una VM Ubuntu Server

Procedimiento para ejecutar `deploy/smoke/run.sh` en una máquina virtual desechable. **No es el VPS de producción.** Docker solo se considera validado cuando el informe termina en `RESULT: ALL n CHECKS PASSED` y el script devuelve código 0.

## 0. Máquina virtual

| Requisito | Valor |
|---|---|
| Sistema | Ubuntu Server 24.04 LTS (o una LTS posterior que figure en la [lista de Docker](https://docs.docker.com/engine/install/ubuntu/#os-requirements)), amd64 o arm64 |
| Recursos | 2 vCPU, 4 GB de RAM y 20 GB de disco libres |
| Red | Salida a Internet hacia `download.docker.com`, Docker Hub (`registry-1.docker.io`, `production.cloudflare.docker.com`) y PyPI (`pypi.org`, `files.pythonhosted.org`). No hace falta ningún puerto de entrada salvo SSH. |
| Aislamiento | VM nueva o con instantánea previa, sin otros proyectos Docker. El script se niega a funcionar si encuentra un proyecto Compose llamado `perfumeria`. |

Durante la instalación de Ubuntu Server, activa *OpenSSH server* y **no marques `docker` en "Featured server snaps"**: el snap no es compatible con este procedimiento y el script lo rechaza.

## 1. Paquetes base

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git gnupg
# Ya incluidos en Ubuntu Server: bash, coreutils (od, sha256sum, mktemp), findutils, iproute2 (ss, ip), hostname, tar, gzip
```

## 2. Docker Engine y Compose v2 desde el repositorio oficial

Comprueba los pasos en <https://docs.docker.com/engine/install/ubuntu/> por si han cambiado.

```bash
# Paquetes que entran en conflicto (en una VM nueva no suele haber ninguno)
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt-get remove -y "$pkg" 2>/dev/null
done

# Clave de firma de Docker
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
gpg --show-keys /etc/apt/keyrings/docker.asc     # huella esperada: 9DC8 5822 9FC7 DD38 854A  E2D8 8D81 803C 0EBF CD88

# Repositorio
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verificación
docker --version
docker compose version          # debe ser v2.20 o superior
sudo docker run --rm hello-world
```

Permiso para usar Docker sin `sudo` (en una VM de pruebas; pertenecer al grupo `docker` equivale a ser root):

```bash
sudo usermod -aG docker "$USER"
newgrp docker                   # o cerrar sesión y volver a entrar
docker info >/dev/null && echo "acceso OK"
```

## 3. Copiar la rama `feature/prelaunch-security` sin hacer push

La rama solo existe en el equipo Windows. Se transfiere como *bundle* de Git, que conserva los commits y no publica nada. Contiene el historial completo, incluidas las fotografías heredadas del historial, así que debe quedarse en la VM privada.

**En Windows (PowerShell), en la carpeta del proyecto:**

```powershell
git status --short                                    # debe estar vacío
git bundle create "$env:USERPROFILE\perfumeria-6a.bundle" feature/prelaunch-security
git bundle verify "$env:USERPROFILE\perfumeria-6a.bundle"
(Get-FileHash "$env:USERPROFILE\perfumeria-6a.bundle" -Algorithm SHA256).Hash
git rev-parse --short feature/prelaunch-security      # anota el commit
scp "$env:USERPROFILE\perfumeria-6a.bundle" <usuario>@<ip-de-la-vm>:~/
```

**En la VM:**

```bash
sha256sum ~/perfumeria-6a.bundle                     # debe coincidir con el hash de Windows
git clone --branch feature/prelaunch-security ~/perfumeria-6a.bundle ~/perfumeria
cd ~/perfumeria
git log --oneline -1                                  # el mismo commit anotado en Windows
grep -c $'\r' deploy/smoke/run.sh deploy/entrypoint.sh   # 0 en ambos (finales de línea LF)
ls -l deploy/smoke/run.sh                             # debe ser ejecutable (-rwx)
```

No copies `env.py`, `db.sqlite3`, `media/` ni ningún `.env` a la VM: la prueba no los necesita y genera sus propios secretos.

## 4. Ejecutar la prueba

```bash
cd ~/perfumeria/deploy
./smoke/run.sh; echo "exit=$?"
```

- Duración aproximada: entre 5 y 15 minutos (la primera vez descarga imágenes y paquetes).
- Código de salida: `0` si todo pasa, `1` si alguna comprobación falla, `2` si una comprobación previa aborta sin crear nada.
- Para inspeccionar el stack al terminar: `KEEP=1 ./smoke/run.sh`. El informe indica la orden exacta para eliminarlo.
- Puertos o subred alternativos: `SMOKE_HTTPS_PORT=28443 SMOKE_HTTP_PORT=28080 SMOKE_SUBNET_PREFIX=172.31.77 ./smoke/run.sh`.

### Qué hace y qué no hace

- Crea solo el proyecto Compose `perfumeria-smoke`: contenedores, la red `perfumeria-smoke_edge`/`_backend` y los volúmenes `perfumeria-smoke_*`. Antes de crear nada comprueba que Compose resuelve ese nombre. Al terminar ejecuta `docker compose down -v` **solo de ese proyecto**.
- No ejecuta `docker system prune`, `docker volume rm` ni nada sobre otros proyectos. La imagen `perfumeria-web:smoke` y las imágenes base descargadas se conservan para acelerar la siguiente ejecución.
- Los secretos (`SECRET_KEY`, contraseña de PostgreSQL) se generan al azar en `~/perfumeria-smoke.XXXXXX/.env.smoke` (permisos 600, directorio 700). Los datos son desechables: 265 borradores de referencia y direcciones `@example.invalid`.
- Caddy escucha solo en `127.0.0.1` con su CA interna para `perfumeria.localhost`. No hay ACME, DNS, SMTP ni Stripe. El script comprueba también que nada responde en la IP de red de la VM.

## 5. Consultar el resultado

La última línea del terminal indica el directorio de trabajo, por ejemplo `~/perfumeria-smoke.Ab12Cd`.

```bash
W=$(ls -dt ~/perfumeria-smoke.* | head -n1)
tail -n 3 "$W/report.txt"                      # RESULT: ...
grep -E '^(FAIL|ABORT)' "$W/report.txt"        # vacío si todo ha pasado
less "$W/report.txt"
```

| Archivo en `$W` | Contenido |
|---|---|
| `report.txt` | Versiones, commit y una línea `PASS`/`FAIL` por comprobación |
| `build.log`, `migrate.log`, `catalog.log` | Construcción de la imagen, migraciones y carga del catálogo |
| `compose.log` | Logs de los tres servicios (sin tokens si la prueba pasa) |
| `caddy-access.log` | Log de acceso de Caddy (tokens redactados, IP enmascaradas) |
| `login-headers.txt` | Cabeceras HTTPS de `/accounts/login/` |
| `backup.log`, `restore-verify.log`, `restore.log`, `backups/` | Copia, verificación y restauración sobre los datos desechables |

Para entregar el resultado, copia **solo** `report.txt` (y, si hay fallos, los logs correspondientes) a Windows: `scp <usuario>@<ip>:~/perfumeria-smoke.*/report.txt .`. No compartas `.env.smoke` ni `backups/`, aunque sean desechables.

### Comprobaciones críticas

Docker se considera validado solo si pasan todas. Estas son imprescindibles:

- Construcción, imagen sin privilegios y sin `env.py`, `.env`, SQLite ni media.
- `db`, `web` y `caddy` en estado *healthy*. `web` se niega a arrancar con migraciones pendientes o con `STORE_MODE=live`.
- `db` y `web` sin puertos publicados, red `backend` interna, Caddy fuera de ella y nada escuchando en la IP de la VM.
- TLS verificado, HSTS, `X-Frame-Options`, `nosniff`, cookie CSRF `Secure` y `SameSite=Lax`, y POST sin token rechazado (403).
- `/checkout/` 403. `/healthz/` y `/media/` 404 a través de Caddy.
- Correo `dummy`, sin formularios de aviso ni de registro, sin claves de Stripe.
- 265 borradores sin publicar, sin aparecer en el listado, el sitemap ni la búsqueda; la ficha devuelve 404.
- Token ausente de todos los logs.
- Persistencia tras `down`/`up`, copia con permisos 600 y restauración verificada.

## 6. Si algo falla

| Síntoma en `report.txt` | Causa probable | Qué hacer |
|---|---|---|
| `ABORT Docker is installed as a snap` | Docker instalado desde el instalador de Ubuntu | `sudo snap remove docker` y repetir el paso 2 |
| `ABORT cannot talk to the Docker daemon` | Usuario fuera del grupo `docker` | Paso 2 (`usermod`, `newgrp`) o ejecutar con `sudo` |
| `ABORT port … is already in use` / `subnet …` | Otro servicio usa el puerto o la subred | `SMOKE_HTTPS_PORT`, `SMOKE_HTTP_PORT`, `SMOKE_SUBNET_PREFIX` |
| `FAIL image builds` | Sin acceso a Docker Hub o PyPI, o una dependencia sin rueda para la arquitectura | Revisar `build.log` y la salida a Internet de la VM |
| `FAIL web becomes healthy` | Error de arranque de Django o Gunicorn | `KEEP=1 ./smoke/run.sh` y después `docker logs perfumeria-smoke-web-1` |
| `FAIL caddy becomes healthy` o CA no disponible | `Caddyfile` no válido | `docker logs perfumeria-smoke-caddy-1` (muestra la línea del error) |
| Fallo en cabeceras, tokens o catálogo | Defecto real de configuración o de código | No lo corrijas en la VM: corrígelo en Windows (paso 7) |

Para inspeccionar un stack conservado con `KEEP=1`, exporta antes las dos variables que indica el informe (`COMPOSE_PROJECT_NAME` y `PERFUMERIA_ENV_FILE`) y usa siempre `docker compose --env-file "$PERFUMERIA_ENV_FILE" …` desde `~/perfumeria/deploy`.

## 7. Corregir y repetir sin tocar producción

1. Corrige en Windows, ejecuta la suite Django y crea un commit local (sin push).
2. Genera un bundle nuevo y cópialo a la VM, como en el paso 3.
3. En la VM, actualiza el clon y repite la prueba:
   ```bash
   cd ~/perfumeria && git pull --ff-only ~/perfumeria-6a.bundle feature/prelaunch-security
   git log --oneline -1
   cd deploy && ./smoke/run.sh; echo "exit=$?"
   ```
   Cada ejecución elimina primero los restos del proyecto `perfumeria-smoke` y crea secretos y datos nuevos.
4. Limpieza al terminar la campaña de pruebas:
   ```bash
   rm -rf ~/perfumeria-smoke.*            # informes, secretos temporales y copias desechables
   docker image rm perfumeria-web:smoke   # opcional
   ```
   O, más sencillo, restaurar la instantánea de la VM o eliminar la VM.

Nada de este procedimiento usa el dominio real, el DNS, el VPS, `deploy/.env.production` ni datos de producción.
