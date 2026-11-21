# Imágenes del catálogo

Estado (20/11/2026, 16:50 UTC): **desplegado en producción** (`perfumeria-web:bfe1268`, migración `products.0012` aplicada) tras una copia verificada (`/srv/perfumeria/backups/20261120T164907Z`). No se ha descargado ninguna imagen nueva.

- **Reversión:** `RELEASE=f02f4a8` en `deploy/shared/.env.production` y `pc up -d perfumeria-web`. La migración `0012` solo añade un campo, así que el código anterior funciona con ella.

## Regla de derechos (sin cambios)

Una fotografía solo se muestra en la web si tiene un `CatalogImage` **aprobado**, con procedencia y licencia registradas, y su ficha está publicada. Las fotos heredadas de `media/` siguen sin derechos verificados: ninguna es pública. Sin imagen aprobada se ve la presentación alternativa: el frasco ilustrado con la inicial de la marca.

## Inventario de `media/` (fotos heredadas)

| Aspecto | Resultado |
|---|---|
| Archivos | 140: 127 JPEG, **12 WebP con extensión `.jpeg`** y `noimage.png` |
| Dimensiones | de 224×224 a 4160×6240 (mediana 720×720) |
| Proporción | 116 cuadradas, 22 verticales (hasta 0,54) y 2 horizontales |
| Calidad | 3 con lado corto menor de 400 px y 30 menor de 600 px |
| Fondo | 119 blanco y 21 oscuro o de color |
| Orientación EXIF | ninguna rotada |
| Relación con los 265 productos de referencia | 138 tienen su foto; **127 apuntan a archivos que no existen**; 1 archivo sin producto; 15 solo con URL externa (no se descarga) |

Informe detallado por archivo (CSV de solo lectura), útil para la revisión de derechos:

```bash
python manage.py catalog_images_report > auditorias/imagenes.csv
```

## Cómo se procesan al aprobarlas

`decide_image` (aprobación en el admin):

1. Abre JPEG, PNG o WebP según el contenido real, no la extensión. Límite de 50 MP; los JPEG grandes se decodifican ya reducidos (`draft`).
2. Corrige la orientación EXIF, elimina metadatos y aplana la transparencia sobre blanco.
3. Genera **derivados que caben en un cuadrado** de 320, 640, 960 y 1280 px, en **AVIF y WebP**. Mantiene la proporción y nunca supera el tamaño original (una foto de 720 px genera 320, 640 y 720). Se guardan en `catalog_assets/r/` y quedan registrados en `CatalogImage.renditions`.
4. El original no se modifica ni se borra.

Para imágenes aprobadas antes de este cambio: `python manage.py rebuild_catalog_renditions` (en seco) y luego con `--apply`.

Se sirven en `/products/image/<id>/<caja>.<avif|webp>`, solo si la imagen está aprobada y no retirada y la ficha está publicada. Llevan `Cache-Control: public, max-age=600`: una retirada se refleja en 10 minutos.

## Presentación

- **Fragmento común** [`product_picture.html`](products/templates/products/includes/product_picture.html) en tarjetas del catálogo y resultados de búsqueda, «similares», imagen principal y miniaturas de la ficha, comparación y favoritos. El autocompletado usa una miniatura cuadrada con el mismo criterio.
- **`<picture>`** con `<source>` AVIF y WebP, `srcset` en anchos reales y `sizes` por contexto.
- **Dimensiones explícitas** (`width`/`height`) y marco con `aspect-ratio`: sin saltos de diseño al cargar.
- **Carga:** `loading="lazy"` fuera de pantalla; la imagen principal de la ficha y la primera tarjeta llevan `loading="eager"` y `fetchpriority="high"`.
- **Marco** `.sf-media`: cuadrado 1:1, fondo marfil de la tienda, margen interior y `object-fit: contain` centrado. La imagen tiene como tope su tamaño real en píxeles (`--img-max-w`/`--img-max-h`), así que **no se amplía**. `mix-blend-mode: multiply` funde los fondos blancos con el marfil; las fotos de fondo oscuro quedan enmarcadas.
- **Galería de la ficha:** al cambiar de miniatura se actualizan también los `<source>`, no solo `img.src`.

## Resultados medidos (demostración local con 21 fotos heredadas de 6 tipos)

- En móvil (390 px, viewport emulado), tableta (820 px) y escritorio (1440 px), en catálogo, búsqueda y fichas: todos los marcos cuadrados, **0 imágenes rotas, 0 ampliadas y 0 deformadas**, sin desplazamiento horizontal. 187 de 187 peticiones de imagen respondieron 200.
- El navegador eligió AVIF y el tamaño adecuado (320 px en tarjetas móviles y 640 px en tableta).
- **Peso medio por imagen:** original 113 KB; tarjeta 11 KB (AVIF) o 16 KB (WebP), un 90 % menos; imagen grande 20 KB (AVIF), un 82 % menos.
- Capturas en `auditorias/capturas-imagenes/` (local, sin versionar).

## Pruebas automáticas

[`products/test_catalog_images.py`](products/test_catalog_images.py):
- tamaños sin ampliación;
- proporción conservada en fotos cuadradas, verticales, horizontales, diminutas, grandes y WebP con extensión `.jpeg`;
- metadatos eliminados y transparencia aplanada;
- formatos y tipos MIME correctos;
- control de derechos (borrador, retirada, foto sin aprobar);
- `<picture>` en todas las superficies, con cada URL comprobada (sin imágenes rotas);
- carga diferida o prioritaria según la posición;
- reglas CSS (1:1, `contain`, sin `cover`, tope de tamaño);
- galería, autocompletado y los dos comandos.

## Asignación progresiva de fotos (por SKU)

La relación foto ↔ perfume ya existe: cada ficha de referencia apunta a `media/<SKU>.jpeg`. Hay **138 fotos emparejadas** con su marca y nombre; las 127 restantes apuntan a archivos que no existen.

1. **Hoja de revisión** (solo lectura). Se abre en Excel:

   ```bash
   python manage.py catalog_photo_manifest --output auditorias/fotos-catalogo.csv        --source "Parfumo (vía proyecto Eau Royal) - pendiente de permiso"
   ```

   Contiene SKU, marca, nombre, concentración, tamaño, archivo, dimensiones, fondo, el `alt_text` sugerido, la procedencia y el estado actual. Se rellena por filas:
   - `mapping_confirmed`: `sí` cuando la foto corresponde de verdad a ese perfume. El README advierte de que algunas no coinciden.
   - `rights_reference`: el permiso o la licencia (contrato, correo de autorización, kit de prensa de la marca…).
   - `alt_text`: se puede afinar, por ejemplo con el color del frasco.

2. **Asignación.** Sin `--apply` es una simulación.

   ```bash
   python manage.py assign_catalog_photos auditorias/fotos-catalogo.csv            # simulación
   python manage.py assign_catalog_photos auditorias/fotos-catalogo.csv --apply    # registra pendientes
   python manage.py assign_catalog_photos auditorias/fotos-catalogo.csv --apply        --approve --reviewer <usuario>                                             # aprueba las que tienen permiso
   ```

   - Solo usa las filas confirmadas y comprueba que el archivo sea la portada o una variante de ese SKU.
   - Crea un `CatalogImage` **pendiente** con el texto alternativo, la procedencia y los derechos.
   - Con `--approve`, aprueba y genera los derivados únicamente de las filas que tienen procedencia **y** referencia de derechos. El revisor necesita `products.approve_catalogimage`.
   - Se puede repetir a medida que se añaden filas, sin duplicar registros.
   - Una foto retirada no se reactiva: vuelve a quedar pendiente en un registro nuevo.
   - **Nunca publica fichas.** La foto solo se ve cuando su ficha también está aprobada, con la concentración y el formato verificados.

Prueba local con todo el catálogo de referencia (copia de la base en el scratchpad): 138 filas, 0 errores de emparejamiento, 138 pendientes sin derechos y 0 aprobadas.

## SEO de imágenes

Solo intervienen las fotos aprobadas de fichas publicadas:

- **Texto alternativo** descriptivo por defecto: «Frasco de *Marca Nombre Concentración Tamaño*» (por ejemplo, «Frasco de Dior Sauvage Eau de Parfum 100 ml»), o el `alt_text` propio de la imagen.
- **URL con nombre descriptivo**: `/products/image/<id>/<marca-nombre>-<caja>.<avif|webp>`. El nombre es decorativo; el `id` decide qué se sirve. La ruta anterior sigue funcionando.
- **Open Graph / Twitter**: `og:image` con `og:image:width`, `og:image:height` y `og:image:alt`, y `twitter:image:alt`.
- **JSON-LD `Product`**: `image` con la lista de todas las fotos aprobadas, en URL absolutas.
- **Sitemap de imágenes**: `/sitemap.xml` añade `<image:image>` a cada ficha con foto aprobada. Plantilla en `templates/seo/sitemap.xml`.

## Subir a producción (cuando se decida)

1. Desplegar el código.
2. Copiar al volumen `media` del VPS **solo los originales autorizados**. Hoy los originales no están en el servidor.
3. Ejecutar allí `assign_catalog_photos ... --apply --approve`.
4. Aprobar las fichas verificadas.
