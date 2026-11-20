# Propuesta: Caddy compartido con configuración modular por proyecto

Estado: **propuesta para decidir; no aplicada.** No se ha modificado el DNS, el Caddy de producción ni el repositorio de Foro IA al Día.

## Requisitos

1. Foro IA al Día y Perfumería El Buen Olor son proyectos independientes: sin código, ramas, releases ni despliegues mezclados.
2. Toda la configuración y automatización de la perfumería vive en su propio repositorio.
3. Se comparten el VPS y el Caddy que ya publica 80/443.
4. Un despliegue de la perfumería no publica cambios pendientes del foro ni recrea sus contenedores.
5. Las releases del foro no eliminan ni sobrescriben la configuración de la perfumería.

## Solución propuesta: directorio neutro de sitios + `import`

```
/srv/caddy/                         infraestructura compartida (no pertenece a ningún proyecto)
├── README.md                       reglas de convivencia
├── sites/                          un archivo por dominio, montado en solo lectura en Caddy
│   └── perfumeriaelbuenolor.es.caddy   ← lo escribe SOLO el despliegue de la perfumería
└── logs/                           logs de acceso por sitio (escribe Caddy)
    └── perfumeriaelbuenolor.es/

foroia-production-caddy-1 (Caddy del foro, sigue siendo el único en 80/443)
  /etc/caddy/Caddyfile   ← del foro: sus sitios + UNA línea genérica:  import /etc/caddy/sites/*.caddy
  /etc/caddy/sites       ← /srv/caddy/sites (solo lectura)
  /var/log/caddy-sites   ← /srv/caddy/logs
```

- **El foro** solo contiene un enganche genérico (`import` de un directorio). No menciona la perfumería ni ningún otro proyecto. Su Caddyfile y su Compose siguen en su repositorio y en sus releases.
- **La perfumería** solo escribe `/srv/caddy/sites/perfumeriaelbuenolor.es.caddy`, que está fuera de `/opt/foroia`. Ninguna release del foro lo toca, porque extrae su paquete en `/opt/foroia`.
- **Persistencia:** cada recarga o recreación del Caddy del foro vuelve a leer el directorio, así que la perfumería se conserva sin intervención.
- **Separación de despliegues:**
  - el de la perfumería = validar, mover el archivo de forma atómica y `caddy reload`. Es una recarga en caliente, sin recrear el contenedor, sin publicar nada del foro y sin tocar sus archivos;
  - el del foro = su release habitual, que no conoce el contenido de `sites/`.

### Comprobado con la imagen real del foro (Caddy 2.11.7, contenedores desechables sin red)

| Prueba | Resultado |
|---|---|
| Enganche con `sites/` vacío | Válido; el foro funciona igual y solo aparece un aviso «No files matching import glob pattern» |
| Enganche + archivo de la perfumería | Válido; sirve `foroiaaldia.com`, `www.foroiaaldia.com`, `perfumeriaelbuenolor.es` y `www.perfumeriaelbuenolor.es` |
| Solo `*.caddy.new` (preparación) | Ignorado: se puede validar un candidato antes de activarlo |
| Archivo de sitio roto | Rechazado (`rc=1`) |
| Archivo que redefine `foroiaaldia.com` | Rechazado (`rc=1`): un proyecto no puede apropiarse del dominio de otro |

## Cambios mínimos en la infraestructura compartida (una sola vez)

Son cambios **genéricos** del foro (no contienen nada de la perfumería). Los decide y despliega el responsable del foro, en su repositorio y con su proceso de release:

1. **Directorio neutro** en el VPS:
   ```bash
   sudo install -d -m 755 -o root -g root /srv/caddy /srv/caddy/sites /srv/caddy/logs
   ```
2. **`deploy/Caddyfile` del foro**: añadir al final
   ```caddyfile
   # Sitios de otros proyectos alojados en este VPS (un archivo por dominio, gestionados fuera de este repositorio)
   import /etc/caddy/sites/*.caddy
   ```
3. **`compose.production.yml` del foro**, servicio `caddy`, dos montajes más:
   ```yaml
       volumes:
         - ./deploy/Caddyfile:/etc/caddy/Caddyfile:ro
         - /srv/caddy/sites:/etc/caddy/sites:ro
         - /srv/caddy/logs:/var/log/caddy-sites
         - caddydata:/data
         - caddyconfig:/config
   ```
4. **Aplicarlo** con una release del foro que contenga solo esos cambios genéricos y recree Caddy, como ya hace su procedimiento (`up -d --force-recreate caddy`). Es **el único reinicio de Caddy** de todo el proceso: unos segundos, en una ventana elegida, con `sites/` todavía vacío, así que el foro no cambia de comportamiento. A partir de ahí, ningún despliegue de la perfumería vuelve a recrear Caddy.

Recomendación adicional para el foro, a su criterio: fijar la versión de la imagen (por ejemplo `caddy:2.11.7-alpine`) en lugar de `caddy:2-alpine`. Afecta a los dos proyectos y conviene controlarla.

## Automatización de la perfumería (en este repositorio)

Sustituye a los scripts actuales `caddy-apply.sh` y `caddy-rollback.sh`, que editaban el Caddyfile del foro y quedarían retirados.

| Pieza | Función |
|---|---|
| `deploy/shared/site/perfumeriaelbuenolor.es.caddy` | El bloque del sitio (contenido actual, con el log en `/var/log/caddy-sites/perfumeriaelbuenolor.es/access.log`) |
| `deploy/shared/site-deploy.sh` | 1. Comprueba que el Caddy compartido tiene el enganche y los montajes (si no, se detiene). 2. Exige que el DNS apunte al VPS. 3. Copia el archivo actual (si existe) a `/srv/perfumeria/caddy-backups/`. 4. Escribe el candidato como `*.caddy.new`. 5. Valida la configuración completa (Caddyfile del foro + `sites/` con el candidato) en un contenedor desechable sin red con la misma imagen. 6. `mv` atómico. 7. `caddy reload`. 8. Compara las respuestas del foro antes y después. Si cualquier paso falla, restaura el archivo anterior (o lo retira) y vuelve a recargar |
| `deploy/shared/site-rollback.sh` | Restaura la copia anterior del archivo del sitio o lo retira; valida y recarga |
| `deploy/shared/site-status.sh` | Solo lectura: enganche presente, archivo desplegado (SHA-256), dominios activos en la configuración en ejecución y certificados |
| Guardas | Los scripts solo pueden escribir `/srv/caddy/sites/perfumeriaelbuenolor.es.caddy` (y su `.new`). Nunca editan `/opt/foroia`, nunca recrean ni detienen contenedores del foro y nunca usan `docker compose` sobre el proyecto del foro |

Reglas de convivencia en `/srv/caddy/README.md`:
- un archivo por dominio, con el nombre del dominio;
- sin opciones globales `{ }`;
- fragmentos reutilizables (snippets) con prefijo del proyecto;
- validar siempre antes de recargar;
- cada proyecto solo toca su archivo.

## Riesgos y cómo se cubren

| Riesgo | Mitigación |
|---|---|
| Un archivo roto en `sites/` impediría arrancar el Caddy compartido en su próxima recarga o recreación | Solo se activa un archivo tras validar la configuración completa; el `mv` es atómico; nunca quedan archivos inválidos con extensión `.caddy` |
| Un proyecto declara el dominio de otro | Caddy rechaza la configuración (prueba T5) |
| Una release futura del foro quita el enganche o los montajes | La perfumería dejaría de servirse, pero el foro no se vería afectado. `site-status.sh` y la comprobación externa de salud lo detectan. Volver a añadirlo es el mismo cambio genérico |
| La recarga del Caddy compartido | `caddy reload` es en caliente y atómica; si la nueva configuración falla, Caddy mantiene la anterior. Es la única acción de la perfumería sobre el contenedor del foro |
| Actualización de la imagen de Caddy por la etiqueta flotante | Fijar la versión (recomendación al foro) |

## Alternativas valoradas

| Opción | Cambio en el foro | Por qué no es la recomendada |
|---|---|---|
| **B. `import /config/sites/*.caddy`** (dentro del volumen `caddyconfig` que ya existe) | Solo una línea en el Caddyfile; se aplica con recarga, sin recrear | La configuración de la perfumería quedaría dentro de un volumen del foro; es un acoplamiento que no cumple la separación pedida. Sirve como transición si no se acepta ningún reinicio |
| **C. Proxy de borde independiente** (`/srv/edge`, dueño de 80/443, enruta a cada proyecto) | El Caddy del foro deja de publicar 80/443 | Separación total, pero exige migrar los puertos y certificados del foro. Tiene sentido si se añaden más proyectos |
| API de administración de Caddy (rutas dinámicas) | Ninguno | Se pierde en cada recarga o recreación del foro: no es persistente |
| caddy-docker-proxy (rutas por etiquetas) | Sustituir el Caddy del foro | Cambio grande en el foro |
| Añadir el bloque al Caddyfile del foro (plan anterior) | Contenido de la perfumería en el foro | Mezcla proyectos; descartado |

## Limpieza del enfoque anterior (pendiente de autorización)

- **En el repositorio del foro:** eliminar la rama local `perfumeria-caddy` y su *worktree* (`Desktop/Mi Blog/foroia-codex-perfumeria-caddy`), que creé antes. No se ha publicado ni fusionado nada.
- **En este repositorio:** retirar `deploy/shared/foroia/0001-perfumeria-caddy.patch` y, cuando la nueva automatización esté lista, `caddy-apply.sh` y `caddy-rollback.sh`.

## Secuencia propuesta

1. Aprobar esta arquitectura y hacer la limpieza.
2. **Perfumería:** implementar `site-deploy.sh`, `site-rollback.sh` y `site-status.sh` con pruebas, más el ensayo en una VM con un Caddy imitado.
3. **Foro (su responsable):** release con el enganche genérico y los montajes, más la recreación de Caddy en una ventana elegida; antes, crear `/srv/caddy` (🔴, con autorización).
4. **DNS** (🔴): quitar la redirección de OVH y poner los A de `@` y `www` hacia el VPS, sin tocar el correo.
5. **Perfumería:** `site-deploy.sh` (🔴, con autorización): recarga en caliente; el certificado de Let's Encrypt se emite automáticamente.
6. Verificación pública y de que el foro no ha cambiado.
