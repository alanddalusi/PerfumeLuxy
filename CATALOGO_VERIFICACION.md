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

## Estado (21/11/2026)

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
