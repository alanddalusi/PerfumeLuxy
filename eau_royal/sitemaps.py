"""
Sistema de sitemaps avanzado para PerfumeLuxe
Divide el sitemap en múltiples archivos para mejor organización y SEO
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from products.models import Product, Category, Brand, Gender, FragranceFamily


class StaticViewSitemap(Sitemap):
    """High-priority static pages"""
    priority = 0.9
    changefreq = 'weekly'

    def items(self):
        return ['home:index', 'products:products']

    def location(self, item):
        return reverse(item)
    
    def lastmod(self, item):
        return timezone.now()


class ProductSitemap(Sitemap):
    """Individual product pages with SEO slugs"""
    changefreq = "daily"
    priority = 1.0
    
    def items(self):
        # Productos válidos con stock
        return Product.objects.filter(
            id__isnull=False,
            stock__gt=0
        ).select_related('brand', 'category', 'gender').order_by('-created_at')
    
    def lastmod(self, obj):
        return obj.updated_at if obj.updated_at else obj.created_at
    
    def location(self, obj):
        return f'/products/{obj.slug}/'


class CategorySitemap(Sitemap):
    """Category filter pages for better SEO"""
    changefreq = "weekly"
    priority = 0.8
    
    def items(self):
        categories = []
        
        # Categorías
        for category in Category.objects.all():
            categories.append({
                'type': 'category',
                'obj': category,
                'url': f'/products/?category={category.name}'
            })
        
        # Géneros
        for gender in Gender.objects.all():
            categories.append({
                'type': 'gender',
                'obj': gender,
                'url': f'/products/?gender={gender.db_name}'
            })
        
        # Marcas
        for brand in Brand.objects.all():
            categories.append({
                'type': 'brand',
                'obj': brand,
                'url': f'/products/?brand={brand.db_name}'
            })
        
        # Familias olfativas
        for family in FragranceFamily.objects.all():
            categories.append({
                'type': 'family',
                'obj': family,
                'url': f'/products/?fragrance_family={family.name}'
            })
        
        return categories
    
    def lastmod(self, obj):
        return timezone.now()
    
    def location(self, item):
        return item['url']


class LandingPageSitemap(Sitemap):
    """Landing pages SEO optimizadas"""
    changefreq = "weekly"
    priority = 0.9
    
    def items(self):
        return [
            {'url': '/products/?special_offers=true', 'name': 'ofertas'},
            {'url': '/products/?new_arrivals=true', 'name': 'novedades'},
            {'url': '/products/?best_sellers=true', 'name': 'mas-vendidos'},
            {'url': '/products/?gender=M', 'name': 'perfumes-hombre'},
            {'url': '/products/?gender=F', 'name': 'perfumes-mujer'},
            {'url': '/products/?gender=U', 'name': 'perfumes-unisex'},
            {'url': '/products/?has_discount=True', 'name': 'perfumes-descuento'},
            {'url': '/products/?intensity=strong', 'name': 'perfumes-intensos'},
            {'url': '/products/?concentration=edp', 'name': 'eau-de-parfum'},
            {'url': '/products/?concentration=edt', 'name': 'eau-de-toilette'},
        ]
    
    def lastmod(self, obj):
        return timezone.now()
    
    def location(self, item):
        return item['url']


# Dictionary of all sitemaps
sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'landing': LandingPageSitemap,
}

