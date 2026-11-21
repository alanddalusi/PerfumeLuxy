# Revisión de la indexación en Google Search Console

La propiedad `perfumeriaelbuenolor.es` ya está verificada; no hay que tocar ni la propiedad ni el DNS. No tengo acceso a Search Console: esta guía indica qué mirar y qué datos enviarme.

## Estado de partida (auditoría del 21/11/2026, `deploy/checks/crawl_audit.py`)

| Comprobación | Resultado |
|---|---|
| URL del sitemap | 66: portada, catálogo, guía de familias, «Sobre nosotros», 10 colecciones indexables y 51 fichas |
| Respuesta | 66/66 con HTTP 200 |
| Canonical | 66/66 apuntan a sí mismas |
| `noindex` | Ninguna página del sitemap lo lleva |
| `robots.txt` | No bloquea ninguna; solo `/admin/`, `/accounts/`, `/bag/`, `/checkout/` y `/profile/` |
| Enlaces internos | 161 destinos, ninguno roto. La miga de pan de las fichas enlazaba filtros `?brand=` con `noindex`; se ha corregido para enlazar a la página de la marca (falta desplegar) |
| Recursos de terceros | Ninguno |

## Qué revisar en Search Console

1. **Sitemaps** (Indexación › Sitemaps). Debe figurar `https://perfumeriaelbuenolor.es/sitemap.xml` con estado «Correcto» y unas 66 URL descubiertas. Si no está, añádelo ahí; no hace falta nada más.
2. **Páginas** (Indexación › Páginas). Exporta el informe (botón «Exportar», CSV o Google Sheets) y fíjate en:
   - «Indexadas»: con el tiempo deberían acercarse a 66.
   - «Descubierta: actualmente sin indexar» y «Rastreada: actualmente sin indexar»: son normales en un sitio nuevo durante unas semanas.
   - «Excluida por la etiqueta noindex» y «Página alternativa con etiqueta canónica adecuada»: son esperables en filtros (`?brand=`, `?gender=`, `?sort=`), búsquedas y colecciones pequeñas. Es correcto.
   - «Bloqueada por robots.txt»: solo deberían aparecer las zonas privadas.
   - Cualquier 404, 5xx o «Duplicada sin canónica seleccionada»: esto sí lo quiero ver.
3. **Inspección de URLs**. Inspecciona estas tres y pide la indexación de las que no lo estén:
   - `https://perfumeriaelbuenolor.es/`
   - `https://perfumeriaelbuenolor.es/products/chanel-bleu-de-chanel-eau-de-parfum/`
   - `https://perfumeriaelbuenolor.es/products/marca/versace/`

   En cada una, «Ver página rastreada» debe mostrar el contenido completo y el canonical elegido por Google debe coincidir con el declarado.
4. **Mejoras** (Fragmentos de productos, Rutas de exploración). Las fichas declaran `Product` sin `offers` porque no hay venta. Google puede marcar «Falta el campo offers, review o aggregateRating»; es esperable mientras la tienda no venda y no impide indexar.
5. **Rendimiento** (Resultados de búsqueda). Durante las primeras semanas habrá pocas impresiones. Exporta las consultas y páginas de los últimos 28 días cuando haya datos.

## Qué necesito para el informe

- La exportación de **Páginas** (los motivos y la lista de ejemplos de cada motivo).
- Una captura o exportación de **Sitemaps**.
- El resultado de inspeccionar las 3 URL anteriores: indexada o no, canonical elegido y fecha del último rastreo.
- Más adelante, la exportación de **Rendimiento** (consultas y páginas).

Alternativa: añadir mi acceso como usuario de solo lectura no es posible desde aquí; basta con las exportaciones.
