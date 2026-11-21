# Datos legales del titular: cómo introducirlos de forma segura

Las páginas `/aviso-legal/`, `/politica-de-privacidad/` y `/contacto/` solo existen cuando el servidor tiene los datos reales del titular. Mientras falte alguno obligatorio responden 404, no se enlazan y no están en el sitemap. Los datos **no se guardan en el repositorio**.

## Datos

| Variable | Contenido | Obligatoria |
|---|---|---|
| `LEGAL_OWNER_NAME` | Nombre completo o razón social | Sí |
| `LEGAL_OWNER_TAX_ID` | NIF o CIF | Sí |
| `LEGAL_OWNER_ADDRESS` | Domicilio completo | Sí |
| `LEGAL_OWNER_EMAIL` | Correo de contacto (mejor uno del dominio) | Sí |
| `LEGAL_OWNER_PHONE` | Teléfono | No |
| `LEGAL_OWNER_REGISTRY` | Datos del Registro Mercantil, si es sociedad | No |
| `LEGAL_EMAIL_PROVIDER` | Proveedor de envío de correo, cuando se active | No |

## Procedimiento

Hazlo tú, en una terminal interactiva. Nadie más necesita ver los datos.

1. Conéctate al servidor: `ssh ubuntu@146.59.35.127`
2. Comprueba el estado sin mostrar valores:
   `cd /srv/perfumeria/app/deploy && sudo bash shared/set-legal-data.sh --check`
3. Introduce los datos: `sudo bash shared/set-legal-data.sh`
   - Pide cada dato por teclado y no lo muestra en pantalla (como una contraseña), así que escribe con cuidado.
   - Los datos no quedan en el historial del shell ni en la lista de procesos, y el script nunca los imprime.
   - No se admiten comillas simples.
   - Guarda una copia del archivo anterior (`.env.production.<fecha>.bak`, permisos 600).
4. Vuelve a ejecutar el paso 2: los obligatorios deben aparecer como «definido».
5. **No reinicies nada.** Avísame; con tu autorización:
   - se recrea solo el contenedor web, que es cuando lee los datos;
   - se comprueba que las tres páginas se ven bien;
   - se despliega el código de las páginas legales, que aún no está en producción.

Los datos quedan en `/srv/perfumeria/app/deploy/shared/.env.production` (propiedad de root, permisos 600) y en las variables del contenedor, visibles solo para administradores del servidor. Django no los escribe en los registros.

## Antes de publicar las páginas

- [ ] Datos obligatorios introducidos y comprobados con `--check`.
- [ ] **Purga programada** de los datos de avisos (`purge_notice_data --apply`, a diario). La política dice que las solicitudes sin confirmar se borran a los 30 días y los contadores a las 48 horas. Hoy no hay ninguna tarea programada en el servidor; tampoco copias automáticas.
- [ ] Revisión de los textos por un profesional:
  - qué se hace con los datos al cerrar una cuenta;
  - el compromiso de no ceder datos;
  - la ubicación exacta del centro de datos de OVH.
- [ ] Licencia del código heredado (proyecto anterior de otro autor, sin archivo `LICENSE`): conviene confirmar los derechos de uso.
