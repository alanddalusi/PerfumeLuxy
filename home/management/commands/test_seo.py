"""
Management command to test and verify SEO sitemap functionality
"""
from django.core.management.base import BaseCommand
from django.test import Client
from products.models import Product


class Command(BaseCommand):
    help = 'Test sitemap and SEO functionality'

    def handle(self, *args, **options):
        client = Client()
        
        self.stdout.write("=== SEO Sitemap & Robots.txt Test ===\n")
        
        # Test sitemap.xml
        self.stdout.write("Testing sitemap.xml...")
        try:
            response = client.get('/sitemap.xml', HTTP_HOST='127.0.0.1:8000')
            if response.status_code == 200:
                content = response.content.decode('utf-8')
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Sitemap working! {len(content)} characters generated"
                    )
                )
                # Count URLs
                url_count = content.count('<url>')
                self.stdout.write(f"  └─ Found {url_count} URLs in sitemap")
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Sitemap failed with status {response.status_code}"
                    )
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Sitemap error: {e}"))

        # Test robots.txt
        self.stdout.write("\nTesting robots.txt...")
        try:
            response = client.get('/robots.txt', HTTP_HOST='127.0.0.1:8000')
            if response.status_code == 200:
                content = response.content.decode('utf-8')
                self.stdout.write(
                    self.style.SUCCESS("✓ Robots.txt working!")
                )
                self.stdout.write("  Content preview:")
                for i, line in enumerate(content.split('\n')[:10]):
                    self.stdout.write(f"    {line}")
                if content.count('\n') > 10:
                    self.stdout.write("    ...")
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Robots.txt failed with status {response.status_code}"
                    )
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Robots.txt error: {e}"))

        # Test product URLs with slugs
        self.stdout.write("\nTesting product URLs with slugs...")
        products_with_slugs = Product.objects.exclude(slug='')[:5]
        
        for product in products_with_slugs:
            url = f'/products/{product.slug}/'
            try:
                response = client.get(url, HTTP_HOST='127.0.0.1:8000')
                status_icon = "✓" if response.status_code == 200 else "✗"
                status_color = self.style.SUCCESS if response.status_code == 200 else self.style.ERROR
                
                self.stdout.write(
                    status_color(f"  {status_icon} {product.name}: {url} -> {response.status_code}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ {product.name}: {url} -> Error: {e}")
                )

        self.stdout.write(f"\n=== Test completed ===")