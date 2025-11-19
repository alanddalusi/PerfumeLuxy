"""
Sistema SEO dinámico completo para PerfumeLuxe
Gestiona meta tags, OpenGraph, Twitter Cards, Schema.org y canonical URLs
"""
from django.conf import settings
from django.utils.html import format_html
from django.utils.safestring import mark_safe
import json


class SEOManager:
    """Gestor centralizado de SEO para todas las páginas"""
    
    def __init__(self, request):
        self.request = request
        self.site_name = "PerfumeLuxe"
        self.default_image = f"{request.scheme}://{request.get_host()}/static/img/og-default.jpg"
        self.default_description = "Descubre PerfumeLuxe - Fragancias 100% auténticas de las mejores marcas. Envío gratis +50€, devolución 30 días. Compra perfumes de lujo con garantía total."
    
    def get_canonical_url(self, path=None):
        """Genera la URL canónica"""
        if path:
            return f"{self.request.scheme}://{self.request.get_host()}{path}"
        return self.request.build_absolute_uri()
    
    def generate_product_schema(self, product):
        """Genera Schema.org para productos"""
        schema = {
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": product.name,
            "description": product.description[:500] if product.description else "",
            "sku": product.sku or f"PROD-{product.id}",
            "brand": {
                "@type": "Brand",
                "name": product.brand.name if product.brand else "PerfumeLuxe"
            },
            "offers": {
                "@type": "Offer",
                "url": self.get_canonical_url(f"/products/{product.slug}/"),
                "priceCurrency": "EUR",
                "price": str(product.price),
                "availability": "https://schema.org/InStock" if product.in_stock else "https://schema.org/OutOfStock",
                "seller": {
                    "@type": "Organization",
                    "name": "PerfumeLuxe"
                }
            }
        }
        
        # Añadir imagen si existe
        if product.image:
            schema["image"] = self.request.build_absolute_uri(product.image.url)
        
        # Añadir rating si existe
        if product.review_count > 0:
            schema["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": str(product.average_rating),
                "reviewCount": str(product.review_count),
                "bestRating": "5",
                "worstRating": "1"
            }
        
        return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>')
    
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
        
        return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>')
    
    def generate_organization_schema(self):
        """Genera Schema.org para la organización (para home/footer)"""
        schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "PerfumeLuxe",
            "url": self.get_canonical_url('/'),
            "logo": f"{self.request.scheme}://{self.request.get_host()}/static/img/logo.png",
            "description": self.default_description,
            "contactPoint": {
                "@type": "ContactPoint",
                "telephone": "+34-91-123-4567",
                "contactType": "customer service",
                "email": "info@perfumeluxe.com",
                "availableLanguage": ["Spanish", "English"]
            },
            "sameAs": [
                "https://www.facebook.com/perfumeluxe",
                "https://www.instagram.com/perfumeluxe",
                "https://www.twitter.com/perfumeluxe"
            ]
        }
        
        return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>')
    
    def generate_website_schema(self):
        """Genera Schema.org para el sitio web"""
        schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "PerfumeLuxe",
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
        
        return mark_safe(f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>')
    
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
        title = kwargs.get('title', 'PerfumeLuxe - Perfumes Auténticos de Lujo | Envío Gratis +50€')
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
            'og_url': canonical,
            'twitter_card': 'summary_large_image',
            'twitter_title': title,
            'twitter_description': description,
            'twitter_image': image,
        }
    
    def get_product_meta(self, product):
        """Genera meta tags específicos para productos"""
        # Construir título SEO optimizado
        title = f"{product.name}"
        if product.brand:
            title = f"{product.brand.name} {product.name}"
        if product.concentration:
            title += f" - {dict(product.CONCENTRATION_CHOICES).get(product.concentration, '')}"
        title += " | PerfumeLuxe"
        
        # Descripción optimizada
        description = f"{product.name}"
        if product.brand:
            description = f"Compra {product.brand.name} {product.name}"
        if product.fragrance_family:
            description += f" - {product.fragrance_family.name}"
        if product.description:
            description += f". {product.description[:100]}"
        description += f". Envío gratis +50€. Precio: {product.price}€"
        
        # Keywords
        keywords = f"{product.name}, "
        if product.brand:
            keywords += f"{product.brand.name}, "
        if product.fragrance_family:
            keywords += f"perfume {product.fragrance_family.name}, "
        if product.gender:
            keywords += f"perfume {product.gender.get_friendly_name()}, "
        keywords += "comprar perfume online, perfume auténtico, fragancia lujo"
        
        # Imagen
        image = self.request.build_absolute_uri(product.image.url) if product.image else self.default_image
        
        return self.get_meta_tags(
            title=title,
            description=description[:160],
            keywords=keywords,
            image=image,
            type='product',
            canonical=self.get_canonical_url(f"/products/{product.slug}/")
        )
    
    def get_category_meta(self, category_name, gender=None):
        """Genera meta tags para páginas de categorías"""
        title = f"Perfumes {category_name}"
        if gender:
            title = f"Perfumes {category_name} para {gender}"
        title += " | PerfumeLuxe"
        
        description = f"Descubre nuestra colección de {category_name}"
        if gender:
            description += f" para {gender}"
        description += ". Fragancias auténticas con envío gratis +50€. Los mejores precios en perfumes de lujo."
        
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
