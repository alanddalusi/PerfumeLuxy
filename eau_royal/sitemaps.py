"""
SEO Sitemaps for Eau Royal Perfumery - Luxury E-commerce
Generates dynamic XML sitemaps with SEO-optimized slugs and priorities
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from products.models import Product, Category, Brand


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
    changefreq = "weekly"
    priority = 0.8
    
    def items(self):
        # Only active products with valid slugs
        return Product.objects.filter(
            is_active=True
        ).exclude(
            slug=''
        ).select_related('brand', 'category').order_by('-created_at')
    
    def lastmod(self, obj):
        return obj.created_at
    
    def location(self, obj):
        # Use new slug-based URLs
        return f'/products/{obj.slug}/'


class CategorySitemap(Sitemap):
    """Category filter pages for better SEO"""
    changefreq = "monthly"
    priority = 0.7
    
    def items(self):
        # Only categories that have products
        return Category.objects.filter(
            product__isnull=False
        ).distinct().order_by('name')
    
    def lastmod(self, obj):
        return timezone.now()
    
    def location(self, obj):
        return f"/products/?category={obj.db_name}"


class BrandSitemap(Sitemap):
    """Luxury brand pages for enhanced discovery"""
    changefreq = "monthly"
    priority = 0.6
    
    def items(self):
        # Only brands with available products
        return Brand.objects.filter(
            product__isnull=False
        ).distinct().order_by('name')
    
    def lastmod(self, obj):
        return timezone.now()
    
    def location(self, obj):
        return f"/products/?brand={obj.id}"


# Dictionary of all sitemaps
sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'brands': BrandSitemap,
}
