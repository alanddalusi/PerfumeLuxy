"""
SEO Sitemaps for PerfumeLuxe
Generates dynamic XML sitemaps for products, categories, and static pages
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from products.models import Product, Category, Brand
from datetime import datetime


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages"""
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return ['home', 'products']

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    """Sitemap for individual products"""
    changefreq = "daily"
    priority = 1.0
    
    def items(self):
        return Product.objects.filter(active=True).order_by('-created_at')
    
    def lastmod(self, obj):
        return obj.updated_at if hasattr(obj, 'updated_at') else datetime.now()
    
    def location(self, obj):
        return reverse('product_detail', args=[obj.id])


class CategorySitemap(Sitemap):
    """Sitemap for product categories"""
    changefreq = "weekly"
    priority = 0.9
    
    def items(self):
        return Category.objects.all()
    
    def location(self, obj):
        return f"{reverse('products')}?category={obj.db_name}"


class BrandSitemap(Sitemap):
    """Sitemap for brands"""
    changefreq = "weekly"
    priority = 0.8
    
    def items(self):
        return Brand.objects.all().order_by('name')
    
    def location(self, obj):
        return f"{reverse('products')}?brand={obj.id}"


# Dictionary of all sitemaps
sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'brands': BrandSitemap,
}
