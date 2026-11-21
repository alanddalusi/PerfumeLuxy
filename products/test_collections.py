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


@override_settings(STORE_MODE="prelaunch")
class SiteSeoTests(TestCase):
    def test_home_title_keyword_default_share_image_and_faq(self):
        html = self.client.get("/").content.decode()
        self.assertIn("<title>Perfumes y fragancias verificadas | Perfumería El Buen Olor</title>", html)
        self.assertIn('<meta property="og:image" content="http://testserver/static/img/og-default.png">', html)
        self.assertIn('<meta property="og:image:width" content="1200">', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
        self.assertIn("Preguntas frecuentes sobre perfumes.", html)
        self.assertIn('href="/sobre-nosotros/"', html)

    def test_about_page_is_indexable_and_in_sitemap(self):
        response = self.client.get("/sobre-nosotros/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("<h1>Sobre nosotros.</h1>", html)
        self.assertNotIn("noindex", html)
        self.assertIn('<link rel="canonical" href="http://testserver/sobre-nosotros/">', html)

    def test_product_page_links_its_official_source(self):
        brand = Brand.objects.create(db_name="ch", name="Carolina Herrera")
        product = Product.objects.create(
            name="Good Girl", brand=brand, concentration="edp", catalog_origin=Product.Origin.REFERENCE,
            publication_status="approved",
            verification_sources={"concentration": "https://www.carolinaherrera.com/x", "name": "https://www.carolinaherrera.com/x"})
        html = self.client.get(product.get_absolute_url()).content.decode()
        self.assertIn('href="https://www.carolinaherrera.com/x" rel="nofollow noopener" target="_blank">web oficial de Carolina Herrera</a>', html)
        Product.objects.filter(pk=product.pk).update(verification_sources={"concentration": "javascript:alert(1)"})
        self.assertNotIn("javascript:", self.client.get(product.get_absolute_url()).content.decode())



class LegalPagesTests(TestCase):
    OWNER = {"name": "Titular de prueba", "tax_id": "00000000T", "address": "Calle de prueba 1, Ciudad",
             "email": "contacto@example.test", "phone": "", "registry": ""}

    def test_hidden_without_real_owner_data(self):
        with self.settings(LEGAL_OWNER={"name": "", "tax_id": "", "address": "", "email": ""}):
            for url in ("/aviso-legal/", "/politica-de-privacidad/", "/contacto/"):
                self.assertEqual(self.client.get(url).status_code, 404, url)
            home = self.client.get("/").content.decode()
            self.assertNotIn("/aviso-legal/", home)
            self.assertNotIn("/aviso-legal/", self.client.get("/sitemap.xml").content.decode())
        with self.settings(LEGAL_OWNER={**self.OWNER, "tax_id": ""}):   # one required field missing
            self.assertEqual(self.client.get("/aviso-legal/").status_code, 404)

    def test_published_with_complete_owner_data(self):
        with self.settings(LEGAL_OWNER=self.OWNER):
            notice = self.client.get("/aviso-legal/").content.decode()
            self.assertIn("Titular de prueba", notice)
            self.assertIn("00000000T", notice)
            self.assertIn("contacto@example.test", self.client.get("/contacto/").content.decode())
            self.assertIn("Agencia Española de Protección de Datos", self.client.get("/politica-de-privacidad/").content.decode())
            self.assertIn('href="/aviso-legal/"', self.client.get("/").content.decode())
            self.assertIn("/politica-de-privacidad/", self.client.get("/sitemap.xml").content.decode())
