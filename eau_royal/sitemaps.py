"""
Sistema de sitemaps avanzado para PerfumeLuxe
Divide el sitemap en múltiples archivos para mejor organización y SEO
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from products.models import Product


class StaticViewSitemap(Sitemap):
    """High-priority static pages"""
    priority = 0.9
    changefreq = 'weekly'

    def items(self):
        return ['home:index', 'products:products', 'products:fragrance_families']

    def location(self, item):
        return reverse(item)
    


class ProductSitemap(Sitemap):
    """Individual product pages with SEO slugs"""
    changefreq = "daily"
    priority = 1.0
    
    def items(self):
        return (Product.objects.published().exclude(slug="").order_by("pk")
                .select_related("brand").prefetch_related("catalog_images"))   # image entries
    
    def lastmod(self, obj):
        return obj.updated_at if obj.updated_at else obj.created_at
    
    def location(self, obj):
        return obj.get_absolute_url()


sitemaps = {"static": StaticViewSitemap, "products": ProductSitemap}
