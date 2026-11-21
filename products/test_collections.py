"""Brand and gender collection pages: indexable only with enough published products."""

from django.test import TestCase, override_settings

from .models import Brand, Gender, Product


@override_settings(STORE_MODE="prelaunch")
class CollectionPageTests(TestCase):
    def setUp(self):
        self.versace = Brand.objects.create(db_name="versace", name="Versace")
        self.boss = Brand.objects.create(db_name="hugo_boss", name="Hugo Boss")
        self.f = Gender.objects.create(db_name="F", name="Mujer")
        self.m = Gender.objects.create(db_name="M", name="Hombre")
        for name, conc in (("Bright Crystal", "edt"), ("Yellow Diamond", "edt"), ("Eros", "edp")):
            Product.objects.create(name=name, brand=self.versace, gender=self.f, concentration=conc, price=50,
                                   catalog_origin=Product.Origin.REFERENCE, publication_status="approved")
        Product.objects.create(name="Boss Bottled Night", brand=self.boss, gender=self.m, concentration="edt",
                               catalog_origin=Product.Origin.REFERENCE, publication_status="approved")
        Product.objects.create(name="Draft only", brand=self.versace, gender=self.m, catalog_origin=Product.Origin.REFERENCE)

    def test_indexable_brand_page_with_unique_text(self):
        html = self.client.get("/products/marca/versace/").content.decode()
        self.assertIn("<h1>Perfumes de Versace</h1>", html)
        self.assertIn("<title>Perfumes de Versace | Perfumería El Buen Olor</title>", html)
        self.assertIn('<link rel="canonical" href="http://testserver/products/marca/versace/">', html)
        self.assertNotIn("noindex", html)
        self.assertIn("3 perfumes de Versace con ficha verificada", html)
        self.assertIn("Eau de Parfum y Eau de Toilette", html)
        self.assertNotIn("Draft only", html)
        self.assertNotIn("€", html.split("<main", 1)[-1])

    def test_small_or_empty_collections_are_not_indexed(self):
        html = self.client.get("/products/marca/hugo-boss/").content.decode()
        self.assertIn('content="noindex, follow"', html)
        self.assertIn("Boss Bottled Night", html)
        self.assertNotIn("Hugo Boss Boss", html)
        self.assertEqual(self.client.get("/products/marca/no-existe/").status_code, 404)
        self.assertIn('content="noindex, follow"', self.client.get("/products/genero/unisex/").content.decode())
        self.assertEqual(self.client.get("/products/genero/otro/").status_code, 404)

    def test_sitemap_lists_only_indexable_collections(self):
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/products/marca/versace/", xml)
        self.assertIn("/products/genero/mujer/", xml)
        self.assertNotIn("/products/marca/hugo-boss/", xml)
        self.assertNotIn("/products/genero/hombre/", xml)

    def test_product_page_links_to_its_brand_page(self):
        product = Product.objects.get(name="Bright Crystal")
        html = self.client.get(product.get_absolute_url()).content.decode()
        self.assertIn('href="/products/marca/versace/"', html)
