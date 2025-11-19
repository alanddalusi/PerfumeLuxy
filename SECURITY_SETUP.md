"""
🔒 GUÍA DE SEGURIDAD - PERFUMELUXE
=====================================

PASOS CRÍTICOS PARA PRODUCCIÓN:

1. ELIMINAR env.py del repositorio
   - Este archivo NUNCA debe estar en Git
   - Ya está en .gitignore, pero elimínalo si está visible
   - Comando: git rm --cached env.py

2. CREAR .env con variables de entorno
   - Copia .env.example a .env
   - Completa con credenciales REALES
   - El .env ya está en .gitignore

3. CAMBIAR SECRET_KEY
   - Genera una nueva: python manage.py shell
   - from django.core.management.utils import get_random_secret_key
   - print(get_random_secret_key())
   - Copia la clave generada a tu .env

4. MIGRAR DE SQLITE A POSTGRESQL
   
   a) Instalar PostgreSQL:
      - Windows: https://www.postgresql.org/download/windows/
      - Mac: brew install postgresql
      - Linux: sudo apt install postgresql
   
   b) Crear base de datos:
      psql -U postgres
      CREATE DATABASE eau_royal;
      CREATE USER eau_royal_user WITH PASSWORD 'tu_password_seguro';
      GRANT ALL PRIVILEGES ON DATABASE eau_royal TO eau_royal_user;
      \q
   
   c) Actualizar .env:
      DATABASE_URL=postgresql://eau_royal_user:tu_password@localhost:5432/eau_royal
   
   d) Instalar adaptador:
      pip install psycopg2-binary
   
   e) Migrar datos:
      python manage.py migrate
      python manage.py createsuperuser

5. CONFIGURAR AWS S3 PARA MEDIA
   
   a) Crear bucket en AWS S3:
      - https://s3.console.aws.amazon.com/s3/
      - Nombre: eau-royal o perfumeluxe
      - Región: eu-west-1 (Irlanda) o más cercana
   
   b) Crear usuario IAM con permisos S3:
      - https://console.aws.amazon.com/iam/
      - Crear usuario con acceso programático
      - Adjuntar política: AmazonS3FullAccess
      - Guardar Access Key ID y Secret Access Key
   
   c) Actualizar .env:
      USE_AWS=True
      AWS_ACCESS_KEY_ID=tu_access_key_id
      AWS_SECRET_ACCESS_KEY=tu_secret_key
      AWS_STORAGE_BUCKET_NAME=tu-bucket-name

6. CONFIGURAR CORS Y CSRF
   - ALLOWED_HOSTS debe incluir tu dominio real
   - Configurar CORS_ALLOWED_ORIGINS si usas frontend separado

7. ACTIVAR HTTPS EN PRODUCCIÓN
   - Configurar certificado SSL (Let's Encrypt gratis)
   - SECURE_SSL_REDIRECT = True
   - SESSION_COOKIE_SECURE = True
   - CSRF_COOKIE_SECURE = True

8. VARIABLES DE ENTORNO EN RENDER/HEROKU
   - No uses .env en producción cloud
   - Configura las variables en el panel:
     * Render: Settings > Environment > Add Environment Variable
     * Heroku: Settings > Config Vars

9. STRIPE EN PRODUCCIÓN
   - Cambiar de test keys a live keys
   - Configurar webhooks en producción:
     https://dashboard.stripe.com/webhooks

10. MONITOREO (OPCIONAL)
    - Sentry para errores: sentry.io
    - New Relic para performance
    - CloudWatch si usas AWS

=====================================
CHECKLIST DE SEGURIDAD:
=====================================
[ ] env.py eliminado del repositorio
[ ] .env creado con credenciales reales
[ ] SECRET_KEY nueva generada y configurada
[ ] PostgreSQL instalado y configurado
[ ] Datos migrados de SQLite a PostgreSQL
[ ] AWS S3 configurado para media files
[ ] ALLOWED_HOSTS actualizado con dominio real
[ ] DEBUG=False en producción
[ ] HTTPS activado
[ ] Stripe keys de producción configuradas
[ ] Webhooks de Stripe actualizados
[ ] Backup de base de datos configurado
[ ] Logs de error monitoreados

=====================================
DESARROLLO LOCAL:
=====================================
Para desarrollo local puedes seguir usando:
- SQLite (más simple)
- DEBUG=True
- Stripe test keys
- Media files locales

Pero en PRODUCCIÓN es OBLIGATORIO:
- PostgreSQL o MySQL
- DEBUG=False
- S3 o almacenamiento cloud
- HTTPS
- Variables de entorno seguras
"""
