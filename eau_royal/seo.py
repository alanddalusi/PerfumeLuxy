"""
Sistema SEO dinámico completo para Perfumería El Buen Olor
Gestiona meta tags, OpenGraph, Twitter Cards, Schema.org y canonical URLs
"""
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from checkout.store_mode import sales_enabled
from products.presentation import seo_images
import json


def json_ld(schema):
    escaped = json.dumps(schema, cls=DjangoJSONEncoder, ensure_ascii=True, allow_nan=False).translate(
        {ord("&"): r"\u0026", ord("<"): r"\u003C", ord(">"): r"\u003E"}
    )
    return format_html('<script type="application/ld+json">{}</script>', mark_safe(escaped))


class SEOManager:
    """Gestor centralizado de SEO para todas las páginas"""
    
    def __init__(self, request):
        self.request = request
        self.site_name = "Perfumería El Buen Olor"
        self.default_image = ""
        self.default_description = "Descubre familias olfativas y perfumes en Perfumería El Buen Olor."
    
    def get_canonical_url(self, path=None):
        """Genera la URL canónica"""
        if path:
            return f"{self.request.scheme}://{self.request.get_host()}{path}"
        return self.request.build_absolute_uri()
    
    def generate_product_schema(self, product, avg_rating=0, review_count=0):
        """Genera Schema.org para productos"""
        schema = {
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": product.name,
            "description": (product.description or product.meta_description or "")[:500],
            "offers": {
                "@type": "Offer",
                "url": self.get_canonical_url(product.get_absolute_url()),
                "priceCurrency": "EUR",
                "price": str(product.price),
                "availability": "https://schema.org/InStock" if product.in_stock else "https://schema.org/OutOfStock",
                "seller": {
                    "@type": "Organization",
                    "name": "Perfumería El Buen Olor"
                }
            }
        }
        
        if not sales_enabled() or product.price is None or product.is_reference:
            schema.pop("offers")
        if not schema["description"]:
            schema.pop("description")

        if product.sku:
            schema["sku"] = product.sku
        if product.brand and product.brand.name:
            schema["brand"] = {"@type": "Brand", "name": product.brand.name}
        images = seo_images(product)
        if images:
            # Every approved photo, largest rendition first-class (Google accepts a URL list).
            schema["image"] = [self.request.build_absolute_uri(image["url"]) for image in images]

        # Añadir rating si existe
        if review_count > 0:
            schema["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": str(avg_rating),
                "reviewCount": str(review_count),
                "bestRating": "5",
                "worstRating": "1"
            }
        
        return json_ld(schema)
    
    def generate_breadcrumb_schema(self, items):
        """
        Genera Schema.org para breadcrumbs
        items: lista de diccionarios con 'name' y 'url'
        Ejemplo: [{'name': 'Inicio', 'url': '/'}, {'name': 'Productos', 'url': '/products/'}]
        """
        list_items = []
        for position, item in enumerate(items, start=1):
            list_items.append({
                "@type": "ListItem",
                "position": position,
                "name": item['name'],
                "item": self.get_canonical_url(item['url'])
            })
        
        schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": list_items
        }
        
        return json_ld(schema)
    
    def generate_organization_schema(self):
        """Genera Schema.org para la organización (para home/footer)"""
        schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Perfumería El Buen Olor",
            "url": self.get_canonical_url('/'),
            "description": self.default_description,
        }
        
        return json_ld(schema)
    
    def generate_website_schema(self):
        """Genera Schema.org para el sitio web"""
        schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Perfumería El Buen Olor",
            "url": self.get_canonical_url('/'),
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": self.get_canonical_url('/products/?q={search_term_string}')
                },
                "query-input": "required name=search_term_string"
            }
        }
        
        return json_ld(schema)
    
    def get_meta_tags(self, **kwargs):
        """
        Genera todos los meta tags necesarios
        
        Parámetros:
        - title: título de la página
        - description: descripción meta
        - keywords: palabras clave
        - image: URL de la imagen para OG/Twitter
        - type: tipo de contenido OG (website, product, article)
        - canonical: URL canónica (si es diferente de la actual)
        """
        title = kwargs.get('title', 'Perfumería El Buen Olor')
        description = kwargs.get('description', self.default_description)
        keywords = kwargs.get('keywords', 'perfumes auténticos, fragancias de lujo, perfume mujer, perfume hombre, eau de parfum, comprar perfume online')
        image = kwargs.get('image', self.default_image)
        og_type = kwargs.get('type', 'website')
        canonical = kwargs.get('canonical', self.get_canonical_url())
        
        return {
            'title': title,
            'meta_description': description,
            'meta_keywords': keywords,
            'canonical_url': canonical,
            'og_type': og_type,
            'og_title': title,
            'og_description': description,
            'og_image': image,
            'og_image_width': kwargs.get('image_width') if image else None,
            'og_image_height': kwargs.get('image_height') if image else None,
            'og_image_alt': kwargs.get('image_alt', '') if image else '',
            'og_url': canonical,
            'twitter_card': "summary_large_image" if image else "summary",
            'twitter_title': title,
            'twitter_description': description,
            'twitter_image': image,
        }
    
    def get_product_meta(self, product):
        """Genera meta tags específicos para productos"""
        # Construir título SEO optimizado
        title = f"{product.name}"
        if product.brand and product.brand.name:
            title = f"{product.brand.name} {product.name}"
        if product.concentration:
            title += f" {dict(product.CONCENTRATION_CHOICES).get(product.concentration, '').split(' (')[0]}"
        if product.size:
            title += f" {product.size.replace('ml', ' ml')}"
        title += " | Perfumería El Buen Olor"
        
        if product.meta_description:   # unique text written when the data was verified
            description = product.meta_description
        else:
            description = f"{product.brand.name} {product.name}" if product.brand and product.brand.name else product.name
            if product.fragrance_family:
                description += f" · {product.fragrance_family.name}"
            if product.description:
                description += f". {product.description}"

        # Keywords
        keywords = f"{product.name}, "
        if product.brand and product.brand.name:
            keywords += f"{product.brand.name}, "
        if product.fragrance_family:
            keywords += f"perfume {product.fragrance_family.name}, "
        if product.gender:
            keywords += f"perfume {product.gender.get_friendly_name()}, "
        keywords += "comprar perfume online, perfume auténtico, fragancia lujo"
        
        # Imagen principal (solo si está aprobada y la ficha publicada)
        images = seo_images(product)
        cover = images[0] if images else None

        return self.get_meta_tags(
            title=title,
            description=description[:160],
            keywords=keywords,
            image=self.request.build_absolute_uri(cover["url"]) if cover else self.default_image,
            image_width=cover["width"] if cover else None,
            image_height=cover["height"] if cover else None,
            image_alt=cover["alt"] if cover else "",
            type='product',
            canonical=self.get_canonical_url(product.get_absolute_url())
        )
    
    def get_category_meta(self, category_name, gender=None):
        """Genera meta tags para páginas de categorías"""
        title = f"Perfumes {category_name}"
        if gender:
            title = f"Perfumes {category_name} para {gender}"
        title += " | Perfumería El Buen Olor"
        
        description = f"Descubre nuestra colección de {category_name}"
        if gender:
            description += f" para {gender}"
        description += ". Explora las familias y notas olfativas del catálogo."
        
        keywords = f"perfumes {category_name}, fragancia {category_name}, comprar perfume {category_name}"
        if gender:
            keywords += f", perfume {gender}"
        
        return self.get_meta_tags(
            title=title,
            description=description,
            keywords=keywords
        )


# Context processor para hacer disponible el SEO manager en todos los templates
def seo_context(request):
    """Context processor que añade el SEO manager a todos los templates"""
    return {
        'seo': SEOManager(request)
    }
