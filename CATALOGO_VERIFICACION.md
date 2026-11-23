# Verificación del catálogo de referencia

Los 265 perfumes heredados están en producción como **borradores**. Una ficha solo se publica cuando su marca, nombre, concentración, tamaño y género están comprobados en la **web oficial de la marca**. La URL de esa página queda guardada como evidencia de cada dato. Nada se inventa ni se aproxima: si un dato no se puede comprobar, la ficha sigue pendiente.

## Archivo de evidencias

[`products/verification/reference_evidence.csv`](products/verification/reference_evidence.csv) tiene una fila por SKU (las 265) y está versionado.

| Columna | Contenido |
|---|---|
| `status` | `verified`, `ambiguous`, `duplicate`, `not_found`, `not_applicable` o `pending` |
| `official_name`, `concentration`, `size`, `gender` | Datos tal como aparecen en la web oficial (códigos del modelo: `edp`, `edt`…, `80ml`…, `M`/`F`/`U`) |
| `source_url` | Página oficial que respalda todos los datos de la fila |
| `sizes_seen` | Formatos que ofrece la marca; se elige uno de ellos |
| `notes` | Versión elegida y versiones que no hay que confundir |

### Criterios

- **Solo fuentes oficiales.** Se acepta únicamente `https` en el dominio de la propia marca, en cualquier país (lista `OFFICIAL_DOMAINS` en [`products/reference_evidence.py`](products/reference_evidence.py)). Las tiendas y los agregadores se rechazan.
- **Versión original.** Si las otras versiones tienen un nombre propio («Le Parfum», «Intense», «Elixir», «Essence»…), se toma la versión original y se anota.
- **Ambigüedad.** Si el mismo nombre existe en EDT y en EDP, o en versión de hombre y de mujer, la fila queda `ambiguous` hasta que alguien elija la versión. La foto puede ayudar.
- **Duplicados.** Los SKU repetidos se marcan como `duplicate` y no se publican nunca dos veces.
- **Descripción.** La descripción heredada, en inglés y sin fuente, se elimina al aplicar los datos.
- **Meta descripción.** Se genera una propia, única, con los datos verificados.

## Proceso por lotes (repetible y reanudable)

```bash
python manage.py apply_reference_evidence                # simulación
python manage.py apply_reference_evidence --apply        # aplica; repetirlo no cambia nada
python manage.py reference_catalog_progress --output auditorias/catalogo-progreso.csv
python manage.py publish_reference_batch --reviewer <usuario>           # simulación
python manage.py publish_reference_batch --reviewer <usuario> --apply   # publica (requiere autorización)
```

- **`apply_reference_evidence`.** Cada fila va en su propia transacción, así que una ejecución interrumpida se puede repetir sin más.
  - No cambia el estado de publicación.
  - Genera una URL descriptiva (`/products/carolina-herrera-good-girl-eau-de-parfum/`) solo en fichas que nunca se han publicado.
- **`publish_reference_batch`.** Usa `decide_product`, que vuelve a exigir todas las evidencias y deja registrada la decisión.
  - Salta las fichas que tengan la misma marca, nombre, concentración y tamaño que otra ya publicada.
  - Las fichas de referencia nunca se pueden comprar: aparecen como «Próximamente» y sin precio, también en el comparador y en el test olfativo.
- **`reference_catalog_progress`.** Para cada producto indica si está completo, incompleto (y por qué) o listo para publicar. También el estado de la foto: `none` (sin archivo), `pending_rights` (archivo sin permiso registrado) o `approved`.

## Publicación inicial (21/11/2026, 20:30 UTC)

Publicadas las **30 fichas verificadas** en producción (`perfumeria-web:910bdcd`, revisor `app`), como «Próximamente», sin precios, compras ni fotos.

- **Copias previas verificadas** con `restore.sh --verify`: `20261121T201234Z` y `20261121T202409Z`.
- **Borradores intactos:** los otros 235 tienen la misma huella antes y después (`d67e7492961f1b7e`).
- **Comprobación en el sitio real** con [`deploy/checks/check_published.py`](deploy/checks/check_published.py) por HTTPS: 30/30 sin problemas.
  - Títulos y meta descripciones únicos, canonical y JSON-LD válido sin `offers`.
  - Unos 100 palabras de contenido propio por ficha.
  - Sin precio, compra ni foto.
  - En el sitemap y permitidas por `robots.txt`.
- **Sitemap:** las 33 URL que declara responden 200.
- **Tienda:** el catálogo muestra 30 productos, `/checkout/` responde 403, hay 0 imágenes aprobadas y 0 productos vendibles. `site-status` da 0 fallos y el foro sigue sin cambios.
- **Reversión:** `publish_reference_batch` no retira fichas. Para retirarlas: `python manage.py retire_reference_catalog --reviewer app --apply` (o una a una en el admin). Para volver al código anterior: `RELEASE=fbfea75`.

## Segunda ronda (21/11/2026, 21:00 UTC), desplegada `9beff7a`

- **Marcas y títulos:** «Lancôme» y «Estée Lauder» (migración `0014`, reversible). Los títulos ya no repiten la marca («Boss Bottled Night Eau de Toilette 100 ml»). Se actualizaron solo las 30 publicadas (`--published-only`, 5 cambios); los 235 borradores siguen intactos (misma huella).
- **Páginas de colección:** `/products/marca/<marca>/` y `/products/genero/<mujer|hombre|unisex>/`.
  - Cada una tiene H1, texto y meta descripción propios, generados a partir de los datos verificados.
  - Son indexables y entran en el sitemap solo con 3 o más fichas publicadas (hoy Versace, Paco Rabanne, Mujer y Hombre).
  - Por debajo de 3 llevan `noindex`; una marca sin fichas publicadas devuelve 404.
  - El menú y las fichas enlazan a estas páginas.
- **Comprobación en el sitio real:** 30/30 fichas correctas, 37 URL del sitemap con respuesta 200 y `site-status` sin fallos. El foro sigue sin cambios.
- **17 perfumes nuevos verificados**, listos para la segunda publicación. Están verificados solo en el archivo de evidencias; los borradores de producción no se han tocado.

## Segunda publicación (21/11/2026, 21:10 UTC)

Publicados los **17 perfumes nuevos** (revisor `app`, misma versión `9beff7a`, sin despliegue de código).

- **Copia previa verificada:** `20261121T205349Z`.
- **Borradores intactos:** los 218 restantes tienen la misma huella antes y después (`1927164fcc31f50c`).
- **Comprobación en el sitio real:** 47/47 fichas sin problemas.
  - El catálogo muestra 47 productos y las 60 URL del sitemap responden 200.
  - Colecciones indexables: Bvlgari, Carolina Herrera, Emporio Armani, Guerlain, Hugo Boss, Lancôme, Paco Rabanne, Versace, Mujer y Hombre.
  - 0 precios, 0 fotos, 0 productos vendibles y `/checkout/` responde 403.
- **Rendimiento móvil** ([`deploy/checks/mobile_perf.py`](deploy/checks/mobile_perf.py): Edge instalado y protocolo DevTools, sin paquetes nuevos). Condiciones: 390×844 a 3×, CPU 4× más lenta y red de 1,6 Mbps con 150 ms de latencia.
  - LCP entre 0,5 y 1,1 s, CLS 0 y unos 17 KB por página, sin desplazamiento horizontal.
  - El servidor responde en 0,07–0,13 s.

**Después de publicar** se han verificado 4 más gracias a la foto heredada, que identifica la versión, y a la web oficial: Bleu de Chanel EDP, Obsession for Men EDT, 212 Men Sexy EDT y 212 VIP Men EDT. No están publicados y su evidencia solo está en el repositorio local.

## Tercera publicación y SEO de la portada (21/11/2026, 21:10 UTC), versión `f63d5c8`

- **Publicadas 4 fichas más**, en total 51: Bleu de Chanel EDP, Obsession for Men EDT, 212 VIP Men EDT y 212 Men Sexy EDT.
  - Copia previa verificada: `20261121T210550Z`.
  - Los 214 borradores restantes tienen la misma huella antes y después (`b859b746e81d741e`).
- **Portada** (informe de Seobility):
  - Unas 550 palabras de texto propio (antes 227), que repiten las palabras del título y del H1.
  - Escaparate de perfumes recientes y enlaces limpios a géneros y marcas indexables.
  - Ningún enlace interno con parámetros sin `nofollow`.
  - Eliminados las secciones vacías (Velas, Más valorados) y los enlaces sociales de relleno.
  - Anclas más variadas y tarjetas cuyo enlace lleva el nombre del perfume.
- **Comprobación en el sitio real:** 51/51 fichas correctas, 65 URL del sitemap con respuesta 200, `site-status` sin fallos y el foro sin cambios.
- **Rendimiento móvil:** LCP de 0,5 a 1,1 s y CLS 0.
- **Fuera del alcance del código:**
  - La redirección HTTP→HTTPS es un 308 del Caddy compartido, que no se modifica. Es una redirección permanente válida.
  - La longitud del dominio y los backlinks dependen de acciones externas.

## SEO, segunda ronda (21/11/2026, 22:25 UTC), versión `17dc5ee`

- **Copia previa verificada:** `20261121T222419Z`. Los 214 borradores tienen la misma huella y siguen publicadas 51 fichas.
- **Portada:**
  - título «Perfumes y fragancias verificadas | Perfumería El Buen Olor»;
  - `og:image` propia de 1200×630 (`static/img/og-default.png`) y `summary_large_image`;
  - 4 preguntas frecuentes.
- **Nueva página `/sobre-nosotros/`:** indexable, con canonical y en el sitemap.
- **Fichas:** enlace a la web oficial usada para verificarlas (`nofollow noopener`).
- **Comprobaciones:**
  - 51/51 fichas correctas y 66 URL del sitemap con respuesta 200;
  - `robots.txt` sin cambios;
  - el pago responde 403 y no se muestra ningún precio;
  - `site-status` sin fallos y el foro sin cambios;
  - en el registro solo aparecen los 403 intencionados del pago.
- **Rendimiento móvil:** LCP de 0,6 a 1,2 s y CLS 0.

**Páginas legales preparadas, sin publicar:** `/aviso-legal/`, `/politica-de-privacidad/` y `/contacto/`. Responden 404 y no se enlazan mientras falten en el servidor `LEGAL_OWNER_NAME`, `LEGAL_OWNER_TAX_ID`, `LEGAL_OWNER_ADDRESS` y `LEGAL_OWNER_EMAIL`. Los textos están pendientes de revisión legal.

## Cuarta publicación y mantenimiento (23/11/2026, 07:15 UTC), versión `8b841bd`

- **Copia previa verificada:** `20261123T071217Z`. Los 211 borradores restantes tienen la misma huella antes y después (`a0d5a9337eb82b0b`).
- **Publicadas 3 fichas más**, en total 54: My Burberry Blush, Goldea The Roman Night Absolute y L.12.12 Rouge.
- **Miga de pan:** enlaza a las páginas de marca y de género, ya sin filtros `?brand=`.
- **Páginas legales:** el código está desplegado, pero sin datos del titular responden 404 y no se enlazan.
- **Tareas programadas** en `/etc/cron.d/perfumeria` (copia en [`deploy/shared/cron.perfumeria`](deploy/shared/cron.perfumeria)), en UTC y después de la copia del foro (03:15):
  - 04:10, copia de seguridad (retención de 14 días);
  - 04:35, `purge_notice_data --apply`.
- **Comprobaciones:**
  - 54/54 fichas correctas;
  - las 70 URL del sitemap responden 200, con canonical propio y sin `noindex`;
  - ningún enlace roto; `site-status` sin fallos;
  - el pago responde 403 y no se muestra ningún precio.

## Estado de la verificación (21/11/2026)

| Estado | Fichas |
|---|---|
| Verificadas, **listas para publicar** | **30** |
| Pendientes de investigar | 153 (3 de ellas casi listas: falta el género o el tamaño) |
| Ambiguas (elegir versión) | 39 |
| Duplicadas | 14 |
| Sin fuente oficial accesible | 14 (13 de Gucci, cuya web bloquea la verificación automática, y 1 de DKNY) |
| No aplicable (velas propias del proyecto anterior) | 15 |

Prueba en una copia local con las 265 fichas: 30 actualizadas y una segunda ejecución sin cambios. 30 publicables, sin duplicados; los títulos, las meta descripciones, los canonical, el JSON-LD y el sitemap salen correctos. 12 de las 30 tienen foto, pero sin permiso registrado, así que se muestran con la ilustración del frasco.

## SEO incluido

- **Título:** «Marca Nombre Concentración Tamaño | Perfumería El Buen Olor».
- **Meta descripción:** única para cada ficha.
- **Canonical, URL y robots:** canonical absoluto y URL descriptiva. `robots.txt` bloquea admin, cuenta, cesta y pago.
- **JSON-LD `Product`:** nombre, marca, SKU y descripción, sin `offers` porque no hay venta.
- **Sitemap:** solo las fichas publicadas, con sus imágenes cuando haya fotos autorizadas.
