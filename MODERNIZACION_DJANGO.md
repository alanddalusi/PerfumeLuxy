# Ejecutar Perfumería El Buen Olor con Django 5.2

El proyecto usa Python 3.13 y Django 5.2 LTS. Usa el último parche de Python 3.13 disponible para el entorno. `runtime.txt` fija la versión de producción.

## Desarrollo

En Windows, crea un entorno virtual nuevo para conservar el entorno de Django 3.2.

```powershell
py -3.13 -m venv .venv-django52
.\.venv-django52\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-django52\Scripts\python.exe manage.py test
.\.venv-django52\Scripts\python.exe manage.py check
```

Si `DATABASE_URL` está vacía, desarrollo usa `db.sqlite3`. Para probar una base existente, trabaja primero con una copia. Las migraciones nuevas de Django y Allauth vienen de sus paquetes.

```powershell
$env:DJANGO_ENV = 'development'
$env:STORE_MODE = 'prelaunch'
# Usa una ruta SQLite desechable y verificada antes de migrar.
$env:DATABASE_URL = 'sqlite:///preview.sqlite3'
.\.venv-django52\Scripts\python.exe manage.py migrate
.\.venv-django52\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Las pruebas Selenium heredadas apuntan a un sitio externo. Usa la suite de Django para verificar localmente.

## Producción

- Exporta las variables del proceso a partir de [.env.example](.env.example). Configura `DJANGO_ENV=production`, `STORE_MODE=prelaunch`, una clave propia, los hosts explícitos y la URL PostgreSQL. Conserva la clave del despliegue actual si es válida y necesitas mantener sus sesiones.
- Usa PostgreSQL 14 o superior, en una versión con soporte del proveedor. Configura `sslmode=verify-full` y la CA del proveedor para verificar la identidad del servidor. La configuración exige TLS y usa `require` cuando el DSN no especifica un modo.
- Termina TLS en el proxy. Si activas `DJANGO_TRUST_HTTPS_PROXY`, haz que el proxy sobrescriba `X-Forwarded-Proto` y limita el acceso directo al origen. Sirve estáticos y medios desde el proxy o el almacenamiento configurado.
- HSTS está activo en el host HTTPS. Activa `DJANGO_HSTS_INCLUDE_SUBDOMAINS` y `DJANGO_HSTS_PRELOAD` solo cuando el dominio esté preparado. Django avisa sobre ambas decisiones en `check --deploy`.
- `build.sh` instala las dependencias y recopila estáticos. En la fase de release, revisa `python manage.py migrate --plan`, ensaya la actualización con una copia y ejecuta `migrate` de forma explícita. Arranca el proceso WSGI después de aplicar las migraciones.

Para repetir la suite con PostgreSQL, exporta la URL de una instancia **desechable** en modo desarrollo. El rol de pruebas debe poder crear una base temporal. Nunca ejecutes la suite contra la instancia de producción.
