# Catálogo de referencia heredado

Los 265 productos heredados se conservan como **catálogo de referencia** para desarrollar y para que el escaparate no parezca vacío. Están pensados para retirarse en bloque cuando llegue el catálogo real.

## Reglas

- **Origen.** Campo `catalog_origin`: `reference` (heredado) u `own` (catálogo propio, el valor por defecto para fichas nuevas). Es de solo lectura en el admin.
- **Nunca se aprueban solos.** Se importan como borradores con stock 0. Cada ficha se aprueba individualmente en el admin.
- **Aprobación más estricta.** Una ficha de referencia necesita concentración y formato rellenos, y referencias verificables en `verification_sources` para `name`, `brand`, `concentration` y `size`, más `description`, `family` y `notes` si se muestran.
- **Escaparate informativo.** Las fichas de referencia aprobadas se muestran sin precio, stock ni compra, con la etiqueta «Próximamente» y el aviso de disponibilidad. Nunca son vendibles, aunque `STORE_MODE` pase a `live`: quedan fuera del carrito, del checkout y del `Offer` en JSON-LD.
- **Fotografías.** Las 139 fotografías heredadas siguen en `media/` en el equipo local, sin versionar en Git y sin copiarse al servidor. No se publican sin derechos de uso confirmados. Mientras tanto se muestra un frasco ilustrado en blanco y dorado con la inicial de la marca, la familia olfativa y el texto «Fotografía en preparación».

## Procedimiento de revisión progresiva

1. **Cargar los borradores** (no publica nada; las SKU existentes no se modifican):
   ```bash
   python manage.py load_reference_catalog            # en seco: cuántos se añadirían
   python manage.py load_reference_catalog --apply
   ```
2. **Exportar la hoja de revisión:**
   ```bash
   python manage.py reference_catalog_report                      # resumen por origen y estado
   python manage.py reference_catalog_report --csv --pending > revision.csv
   ```
   La columna `missing` indica qué falta: valores (`concentration (valor)`, `size (valor)`) y referencias (`brand (referencia)`, etc.). Hoy ninguna ficha heredada trae concentración ni formato, así que las 265 necesitan revisión.
3. **Comprobar los datos reales** de cada perfume elegido con una fuente verificable (ficha oficial de la marca, documentación del distribuidor, etiqueta del producto físico): marca, nombre exacto, concentración (EDT, EDP, extrait…) y formato (ml). Corrige en el admin lo que no coincida. No copies descripciones de terceros; redacta una propia o déjala vacía.
4. **Registrar las referencias** en *Publicación → verification_sources*, por ejemplo:
   ```json
   {"name": "EXP-2026-014 ficha marca", "brand": "EXP-2026-014", "concentration": "EXP-2026-014 etiqueta", "size": "EXP-2026-014 etiqueta"}
   ```
   Guarda la documentación en el expediente interno; aquí solo va el identificador.
5. **Aprobar y publicar** con un usuario que tenga `products.publish_product`. Queda registrada la decisión, el revisor y las referencias. Cualquier cambio posterior devuelve la ficha a revisión.
6. **Imágenes**, solo con licencia o permiso escrito: crea un `CatalogImage` con la procedencia y la referencia del permiso y apruébalo. Hasta entonces se usa la presentación alternativa.

Empieza por un conjunto pequeño y representativo (por ejemplo, 3 o 4 perfumes por familia olfativa) para que el catálogo tenga variedad desde el principio.

## Sustitución por el catálogo real

1. Crea las fichas reales (origen `own`) y apruébalas con el mismo procedimiento.
2. Retira todas las fichas de referencia publicadas en un solo paso. Se conservan registros, slugs y una decisión por ficha:
   ```bash
   python manage.py retire_reference_catalog                               # en seco
   python manage.py retire_reference_catalog --apply --reviewer <usuario_staff>
   ```
3. Las URL retiradas devuelven 404 y salen del sitemap. Si un perfume de referencia pasa a venderse realmente, crea su ficha propia (`own`) con los datos y la evidencia del proveedor, en lugar de cambiar el origen.

## Migración

`products.0011_product_catalog_origin` añade el campo y marca como `reference` los productos existentes cuyo SKU está en `products/fixtures/products.json`. No cambia el estado de publicación, los precios, el stock ni las imágenes. Su reversión no hace nada con los datos.
