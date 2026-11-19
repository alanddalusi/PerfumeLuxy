# Sistema de diseño de Perfumería El Buen Olor

## Auditoría de las vistas activas

- La plantilla base cargaba Bootstrap CSS y JS, jQuery, Font Awesome, cuatro familias web, ocho hojas CSS propias y el JavaScript de ecommerce en todas las páginas. Portada y ficha añaden CSS y scripts específicos. El listado tenía CSS y JavaScript de antiguos filtros y paginación sin uso, incluida una llamada a una función de filtros que había dejado de existir.
- `base.css`, `luxury-premium.css`, `luxury-white-gold.css` y `products-enhancements-2025.css` definen botones, colores, tipografías y tarjetas con selectores que se solapan. En particular, los estilos globales de `span` reemplazaban la tipografía heredada del logotipo. El sistema nuevo usa clases `eo-` para delimitar su alcance.
- Las cabeceras móvil y de escritorio repetían marca, cuenta y enlaces. Usaban menús de Bootstrap, un desplazamiento para la navegación fija y un buscador duplicado. Las acciones de tarjeta dependían de pasar el ratón. El pie tenía enlaces sin destino, contactos de ejemplo y una suscripción sin conexión a la vista.
- Los formularios del carrito y de cuentas y algunas pantallas heredadas todavía usan jQuery. Los modales de portada y ficha usan Bootstrap. Las hojas antiguas sobreviven donde el contenido actual las necesita. La Fase 4B puede eliminar reglas, fuentes e iconos por pantalla después de comprobar sus dependencias.

## Identidad y componentes

El blanco es la superficie principal. Marfil y arena se usan para superficies secundarias y separadores. El dorado se reserva para acentos y acciones seleccionadas.

| Color | Uso |
|---|---|
| `#FFFFFF` | Fondo principal, cabecera y campos |
| `#FAF8F3` | Avisos, estados vacíos y pie |
| `#EEE6D9` | Arena para separadores y etiquetas |
| `#C5A46D` | Dorado para rellenos con texto oscuro y detalles |
| `#98743A` | Bordes de controles y detalles secundarios |
| `#73521F` | Dorado oscuro para texto, foco y acciones sobre fondos claros |
| `#28221C` | Negro cálido para texto e iconos |

La cabecera y el pie usan Georgia y la tipografía del sistema. La escala de espaciado parte de 4 px con valores de 4, 8, 12, 16, 24, 32 y 48 px al tamaño de raíz habitual. Los controles principales tienen una altura mínima de 44 px, un foco claramente visible y estados hover, disabled y error. El menú y la cuenta usan `details` y `summary`. Los enlaces siguen disponibles sin JavaScript. Escape cierra el menú y devuelve el foco al control que lo abrió.

- `templates/includes/design/` contiene cabecera, enlaces de navegación, pie, migas, botones, campos, estados vacíos y aviso.
- `products/templates/products/includes/perfume_card.html` contiene la tarjeta actual extraída del listado. Las acciones son visibles con foco y en dispositivos sin hover.
- `static/css/design-system.css` contiene tokens y estilos. `static/js/design-shell.js` gestiona el cierre de los menús.

Los contrastes calculados incluyen **6,67:1** para texto negro cálido sobre dorado, **7,10:1** para texto dorado oscuro sobre blanco y **6,69:1** sobre marfil. El dorado profundo sobre blanco da **4,29:1**, por lo que se usa en bordes. El dorado elegante sobre blanco da **2,36:1** y se reserva a decoración cuando se usa sobre ese fondo.

## Alcance de la siguiente fase

La cabecera y el pie nuevos conservan los destinos existentes. Los marcadores sin ruta quedan fuera de la navegación. Las redes sociales conservan sus enlaces genéricos hasta disponer de perfiles oficiales. La Fase 4B debe revisar el contenido comercial heredado, las fotografías, las promesas de entrega y la legibilidad de los componentes específicos de portada, catálogo y ficha.

## Fase 4B

- La portada usa una ilustración original de CSS y carga familias y categorías desde la base. La ilustración representa la marca y no se asocia a un producto. La portada, el catálogo y la ficha usan la plantilla ligera `includes/design/storefront.html`, sin fuentes web ni Bootstrap, jQuery o Font Awesome.
- Los listados y fichas solo muestran un archivo de imagen si su nombre de almacenamiento figura en `CATALOG_APPROVED_IMAGE_NAMES`. La variable acepta nombres exactos separados por coma. Confirmar los derechos y preparar versiones web antes de incorporarlas. Configurar la lista no altera los ficheros ni publica los registros de la base de revisión.
- La ficha usa variantes, notas y familias cuando existen en la base. Los avisos por producto usan el correo verificado de la cuenta y guardan una solicitud. La captura de avisos de lanzamiento exige una casilla sin premarcar y registra la fecha y versión de consentimiento. La migración de `home` es aditiva y mantiene los registros anteriores con versión vacía.
- Los resultados filtrados llevan `noindex, follow`. El sitemap publica rutas estables de portada, catálogo, guía y fichas del catálogo servido. En producción debe verificarse que el dominio de Django Sites coincide con el dominio público. Antes de enviar avisos reales hacen falta la información de privacidad, la baja y el proceso de envío.
