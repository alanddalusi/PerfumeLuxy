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
        from home.legal import legal_ready
        pages = ['home:index', 'products:products', 'products:fragrance_families', 'home:about']
        from home.legal import shop_pages_ready
        pages += ['home:contact', 'home:legal_notice', 'home:privacy_policy'] if legal_ready() else []
        return pages + (['home:shipping_returns', 'home:authenticity'] if shop_pages_ready() else [])

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


class CollectionSitemap(Sitemap):
    """Brand and gender pages with enough published products to be indexable."""
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        from products.collections import sitemap_locations
        return sitemap_locations()

    def location(self, item):
        return item


sitemaps = {"static": StaticViewSitemap, "collections": CollectionSitemap, "products": ProductSitemap}
