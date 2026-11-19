# Procedimiento de revisión y publicación

El modo de despliegue sigue siendo `STORE_MODE=prelaunch`. Las fichas del escaparate requieren aprobación explícita.

## Productos e imágenes

1. Introduce los datos en administración. Una ficha nueva queda pendiente. En **Publicación**, guarda referencias verificables en `verification_sources`, mediante un objeto JSON. Las claves son `name`, `brand`, `concentration`, `size`, `notes`, `family` y `description`. El nombre y la marca son obligatorios. Si se muestra un dato opcional, su referencia también es obligatoria. Usa referencias o identificadores del expediente y conserva la documentación en un repositorio interno.
2. Con los permisos de cambio y `products.publish_product`, abre esa ficha y pulsa **Aprobar y publicar**. El sistema registra la decisión, el revisor, la fecha y las referencias. Los cambios de producto, variantes, marca, familia o notas devuelven la ficha a revisión. Tras revisar las novedades, aprueba de nuevo. **Retirar publicación** conserva el registro y el slug y hace que la URL pública devuelva 404. Si se vuelve a aprobar la misma ficha, reutiliza la URL.
3. Crea una entrada en **Catalog images** para cada original de portada o variante. Registra el nombre exacto de almacenamiento, un identificador de procedencia y el permiso o la licencia. Revisa el alcance de la licencia antes de decidir. Con los permisos de cambio y `products.approve_catalogimage`, pulsa **Confirmar derechos y aprobar imagen**. Se crean dos WebP de hasta 1200×1440 y 420×504, con los metadatos del original eliminados. La ficha y la imagen deben estar aprobadas para servir los WebP. Una ficha sin imágenes aprobadas usa el estado visual alternativo.
4. Conserva los originales y `CATALOG_ASSET_ROOT` fuera de las rutas estáticas públicas, incluso si el proveedor de almacenamiento usa un dominio propio. El proxy debe enviar las rutas de WebP a Django y evitar cachearlas. Si hay varias instancias, deben compartir los derivados. No expongas el directorio de originales como `/media/` público.

El fixture heredado conserva 265 registros revisables en la base de revisión aislada. El valor inicial de publicación es pendiente y la migración no aprueba registros. Esta fase no aporta evidencias comerciales ni permisos reales de terceros.

## Base y avisos

- `home.0004` añade estado de confirmación, baja y datos técnicos de limitación. `products.0010` añade publicación, decisiones, imágenes y el estado de avisos por producto. Son migraciones aditivas. Revisa el plan, haz copia y ensaya la migración antes de aplicarla a producción.
- La solicitud de lanzamiento y la de disponibilidad son registros separados. La disponibilidad requiere una cuenta con correo verificado y un consentimiento específico. Las altas heredadas quedan sin confirmar y el flujo de lanzamiento actual usa la versión `launch-email-v2`.
- Los enlaces de confirmación caducan en 24 horas. GET presenta una pantalla informativa. POST con CSRF consume el enlace y cambia el estado. La baja también requiere POST, se aplica al aviso específico e invalida la confirmación pendiente. Si una solicitud se repite seguidamente, el correo se limita a uno cada diez minutos por aviso. Además, se admiten hasta diez solicitudes por hora y dirección de conexión seudonimizada. La dirección se toma de `REMOTE_ADDR`, evitando aceptar cabeceras de cliente como prueba de origen.
- Antes de abrir el formulario público, valida qué dirección entrega el proxy a Django. Si todas las peticiones parecen proceder del proxy, el límite se compartirá entre ellas. Define la limpieza periódica de los contadores antiguos y evita registrar URLs de confirmación y baja en los logs. Si un envío falla, el aviso queda pendiente y se puede pedir otro al pasar el intervalo de reintento.
- Desarrollo usa correo de consola. Producción mantiene `INTEREST_EMAIL_DELIVERY=0` hasta autorizar y probar SMTP. Este flujo envía confirmaciones cuando se habilita. Las comunicaciones de lanzamiento y stock requieren un proceso de envío posterior. Ese proceso debe seleccionar solo la finalidad y versión vigentes, con confirmación y sin baja, y debe incluir el enlace de baja. Las promociones requieren un consentimiento propio y quedan fuera de este flujo.

## Verificación de despliegue

Usa un único dominio HTTPS y redirige los alias. Comprueba `robots.txt`, sitemap, canonicals, ficha retirada, imágenes retiradas, cookies y cabeceras en el proxy. Mantén las credenciales de Stripe fuera del despliegue de prelanzamiento. Haz una prueba de confirmación y baja con el receptor de pruebas acordado antes de habilitar SMTP para visitantes.

## Pruebas y entorno local

- `env.py` heredado solo se lee para recuperar la clave local de firma; `settings.py` restaura después el entorno original. Un `DATABASE_URL` explícito tiene prioridad y nunca se descarta en silencio (prueba `test_legacy_development_settings_cannot_override_explicit_database`).
- Antes de ejecutar la suite, confirma el motor activo: `python -c "import os,django;os.environ['DJANGO_SETTINGS_MODULE']='eau_royal.settings';django.setup();from django.db import connection;print(connection.vendor)"`.
- SQLite: `python manage.py test --noinput`. PostgreSQL: exporta `DATABASE_URL=postgres://<rol>@127.0.0.1:<puerto>/<base>` hacia un servidor de pruebas local y repite el comando. Django crea y destruye una base `test_*` y no toca los datos de la base nombrada.
- Resultado de la Fase 5A: 40 pruebas superadas en SQLite y en PostgreSQL 17.
