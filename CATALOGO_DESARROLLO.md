# Revisión del catálogo heredado

La configuración de revisión usa `catalog-review.sqlite3` y deshabilita las rutas públicas. El comando rechaza la configuración habitual de la tienda.

```powershell
.\.venv\Scripts\python.exe manage.py migrate --settings=eau_royal.catalog_review_settings
.\.venv\Scripts\python.exe manage.py import_review_catalog --settings=eau_royal.catalog_review_settings
```

La primera ejecución en una base limpia importa 265 registros. Si se repite, encuentra los 265 SKU y conserva los registros existentes, incluidos sus slugs. Importa las referencias de marca, categoría y género y fija el stock en cero. La carga está pensada para revisar datos en local.

## Procedencia y calidad

El fixture contiene 265 SKU distintos y 265 nombres de archivo de imagen. Hay 138 archivos en las rutas locales declaradas y faltan 127. Solo 15 registros incluyen `image_url`. Hay cinco repeticiones de descripciones más allá de su primera aparición. El fixture carece de concentración, volumen, stock y procedencia verificable para los precios, valoraciones e imágenes. **265 registros importables para revisión y 0 verificados para publicación.**

`loaddata` guarda las filas en bruto y omite `Product.save()`. El archivo heredado carece de `slug` en los 265 registros, de modo que la restricción única falla al guardar el segundo valor vacío. El importador usa el guardado normal y procesa el archivo por ID de origen. En una base limpia, el primer registro conserva el slug base y el segundo añade `-1` en los seis grupos siguientes.

| Slug base | IDs del fixture |
|---|---|
| `carolina-herrera-212-vip` | 48, 49 |
| `carolina-herrera-212-sexy` | 50, 54 |
| `giorgio-armani-code` | 99, 100 |
| `gucci-guilty-intense` | 112, 125 |
| `lacoste-eau-de-lacoste` | 177, 180 |
| `paco-rabanne-olympea` | 197, 198 |

Los productos ya guardados conservan su slug al cambiar el nombre. Las URLs numéricas heredadas redirigen con 301 a la ficha cuando el ID existe y la ruta numérica no es un slug vigente.

## Consultas del catálogo

Medición con el cliente Django anónimo y SQLite en memoria, para `/products/?brand=auditoria` y un carrito vacío. Los datos sintéticos solo se usaron en la base de medición.

| Escenario | Antes de Fase 2 | Después |
|---|---:|---:|
| 1 producto de la marca | 15 | 9 |
| Primera página de 60 tarjetas, con 62 productos coincidentes | 133 | 9 |

Se eliminaron recuentos intermedios y consultas de marca, familia y reseñas por tarjeta. La prueba de regresión incluye reseñas aprobadas y exige el mismo número de consultas para una o 60 tarjetas, con un máximo de 12.
