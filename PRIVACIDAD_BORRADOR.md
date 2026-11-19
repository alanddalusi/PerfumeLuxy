# Borrador interno de privacidad y cookies

Documento para revisión del responsable. La pantalla pública explica el uso de los avisos y las cookies técnicas. Este borrador requiere completar los datos reales antes de abrir la recogida de correos al público.

| Punto | Texto o decisión por confirmar |
|---|---|
| Responsable y contacto | Identidad de la entidad o persona responsable, domicilio y contacto para privacidad. Pendiente de facilitar por el negocio. |
| Aviso general | Recoger correo, fecha, finalidad, versión del consentimiento y estado de confirmación o baja para avisar del lanzamiento. La ficha de alta pide una acción afirmativa y el correo incluye un enlace para retirar el consentimiento. |
| Aviso de producto | Asociar una solicitud al perfume, la cuenta y el correo verificado. La suscripción de lanzamiento, el aviso de producto y cualquier promoción son finalidades distintas. |
| Seguridad y registros | Describir cookies de sesión y CSRF y contadores antiabuso con huellas seudonimizadas de la dirección de conexión. Revisar también cookies de Allauth y cómo se registran las rutas de token en el proxy. |
| Conservación | Fijar plazos para altas pendientes, avisos confirmados, bajas, registros de consentimiento, contadores, logs y copias. Documentar qué se elimina y qué registro mínimo se conserva tras una retirada. |
| Proveedores y destinatarios | Identificar alojamiento, SMTP, almacenamiento, asistencia y posibles transferencias. Verificar contratos y regiones reales. |
| Derechos y baja | Establecer un canal verificable. Explicar cómo ejercer los derechos aplicables, retirar cada consentimiento y reclamar ante la autoridad competente. Probar la baja en los correos de confirmación y de notificación. |
| Cookies y terceros | Inventariar con un navegador limpio las cookies, almacenamiento y solicitudes a terceros en producción. Revisar finalidades, duración, proveedores y mecanismos de consentimiento antes de incorporar analítica o publicidad. |

La información definitiva debe ser accesible desde ambos formularios. Antes de publicar, cierra el aviso legal y las capas informativas con datos del responsable y revisa los textos de la tienda y los contactos. La revisión debe tener en cuenta el funcionamiento real del sitio y las condiciones del despliegue.

## Datos a completar manualmente (Fase 5B)

Ninguno de estos datos se ha inventado. Deben facilitarlos el responsable del negocio o su asesor antes de publicar los textos definitivos.

| Dato | Dónde se usará | Estado |
|---|---|---|
| Titular (persona física o sociedad), NIF/CIF, domicilio, datos registrales si los hay | Aviso legal, política de privacidad, pie de página | Pendiente |
| Correo de contacto para privacidad y, si procede, delegado de protección de datos | Política de privacidad, correos de aviso | Pendiente |
| Proveedor del VPS: entidad, país y región del centro de datos, contrato de encargo | Política de privacidad (destinatarios), registro de actividades | Pendiente |
| Proveedor de copias externas cifradas: entidad, región, contrato | Política de privacidad, procedimiento de copias | Pendiente |
| Proveedor SMTP (solo cuando se active): entidad, región, transferencias internacionales | Política de privacidad, `EMAIL_*` | Pendiente; SMTP desactivado |
| Let's Encrypt (emisión de certificados; recibe el correo `ACME_EMAIL` del operador, no datos de visitantes) | Documentación interna | Informativo |
| Plazos de conservación: altas sin confirmar (propuesta técnica: 30 días tras caducar el enlace), contadores antiabuso (48 h), bajas, cuentas, copias (14 días), logs de Caddy (30 días, IP enmascarada) y de Docker (≈50 MB por servicio) | Política de privacidad, `purge_notice_data`, `BACKUP_KEEP_DAYS`, `Caddyfile` | Propuesta técnica pendiente de aprobación |
| Base jurídica de cada finalidad (aviso de lanzamiento, aviso de disponibilidad, cuenta de cliente, seguridad y antiabuso) | Política de privacidad | Pendiente de revisión jurídica |
| Inventario real de cookies en producción (sesión, CSRF, mensajes de Django y allauth; sin analítica ni terceros en esta versión) | Política de cookies | Comprobar en el dominio real con un navegador limpio |
| Enlaces sociales del pie (hoy apuntan a las portadas genéricas de cada red) | Pie de página | Sustituir por perfiles reales o eliminar |

Mientras el SMTP esté desactivado, el formulario guarda solicitudes pendientes, pero no se envía el correo de confirmación. Valora ocultar los formularios públicos hasta activar el correo, o explicar en la página que la confirmación llegará más adelante.
