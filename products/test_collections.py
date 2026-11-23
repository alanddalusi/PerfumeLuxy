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
        self.assertIn("<h1>Perfumes y colonias de Versace</h1>", html)
        self.assertIn("<title>Perfumes y colonias de Versace | Perfumería El Buen Olor</title>", html)
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
            policy = self.client.get("/politica-de-privacidad/").content.decode()
            self.assertIn("Agencia Española de Protección de Datos", policy)
            self.assertIn("hash", policy)                                  # not "cifrada"
            self.assertNotIn("cifrada", policy)
            self.assertIn("un máximo de 30 días", policy)                  # server logs retention (Caddy roll_keep_for)
            self.assertIn('href="/aviso-legal/"', self.client.get("/").content.decode())
            self.assertIn("/politica-de-privacidad/", self.client.get("/sitemap.xml").content.decode())


@override_settings(STORE_MODE="prelaunch")
class NotesAndTrustTests(TestCase):
    URL = "https://www.versace.com/x"

    def setUp(self):
        from .models import Gender
        Gender.objects.create(db_name="F", name="Mujer")
        self.brand = Brand.objects.create(db_name="versace", name="Versace")
        self.products = []
        for i, name in enumerate(("Bright Crystal", "Yellow Diamond", "Eros Pour Femme")):
            self.products.append(Product.objects.create(
                name=name, brand=self.brand, sku=f"V{i}", catalog_origin=Product.Origin.REFERENCE,
                publication_status="approved"))

    def apply(self, sku, name, pyramid):
        from .reference_evidence import apply_evidence
        row = {"sku": sku, "status": "verified", "brand": "Versace", "official_name": name, "concentration": "edt",
               "size": "90ml", "gender": "F", "source_url": self.URL, "description_es": "Texto propio " * 12,
               "description_source": self.URL, "notes_pyramid": pyramid, "field_sources": ""}
        return apply_evidence([row], apply=True)

    def test_notes_are_applied_with_evidence_and_keep_publication(self):
        self.assertEqual(self.apply("V0", "Bright Crystal", "top=Yuzu,Granada;heart=Peonía;base=Almizcle")["V0"][0], "updated")
        product = Product.objects.get(sku="V0")
        self.assertEqual(sorted((n.note_type, n.name) for n in product.fragrance_notes.all()),
                         [("base", "Almizcle"), ("heart", "Peonía"), ("top", "Granada"), ("top", "Yuzu")])
        self.assertEqual(product.verification_sources["notes"], self.URL)
        # Changing the notes of a published product sends it back to review (signals.py) ...
        self.assertEqual(product.publication_status, "draft")
        # ... and re-approval checks the evidence again, notes included.
        from django.contrib.auth import get_user_model
        from .publication import decide_product
        decide_product(product, "approved", get_user_model().objects.create_superuser(username="r"))
        product.refresh_from_db()
        self.assertEqual(product.publication_status, "approved")
        self.assertEqual(self.apply("V0", "Bright Crystal", "top=Yuzu,Granada;heart=Peonía;base=Almizcle")["V0"][0], "unchanged")
        bad = self.apply("V1", "Yellow Diamond", "middle=Rosa")
        self.assertEqual(bad["V1"][0], "error")

    def republish(self):
        Product.objects.filter(sku__startswith="V").update(publication_status="approved")

    def test_note_pages_indexable_from_three_products(self):
        self.apply("V0", "Bright Crystal", "base=Almizcle")
        self.apply("V1", "Yellow Diamond", "base=Almizcle;heart=Fresia")
        self.republish()
        html = self.client.get("/products/nota/almizcle/").content.decode()
        self.assertIn("<h1>Perfumes con notas de almizcle</h1>", html)
        self.assertIn('content="noindex, follow"', html)          # only 2 products
        self.apply("V2", "Eros Pour Femme", "base=Almizcle")
        self.republish()
        html = self.client.get("/products/nota/almizcle/").content.decode()
        self.assertNotIn("noindex", html)
        self.assertIn("/products/nota/almizcle/", self.client.get("/sitemap.xml").content.decode())
        self.assertEqual(self.client.get("/products/nota/no-existe/").status_code, 404)
        detail = self.client.get(Product.objects.get(sku="V1").get_absolute_url()).content.decode()
        self.assertIn('href="/products/nota/fresia/"', detail)
        self.assertIn("Versión exacta: Eau de Toilette · 90ml, comprobada en la web oficial de Versace.", detail)

    def test_shop_pages_hidden_without_real_policy(self):
        owner = {"name": "T", "tax_id": "1", "address": "A", "email": "a@example.test"}
        policy = {"supplier_authorized": True, "goods_origin": "Unión Europea", "delivery_days": "2-4",
                  "shipping_cost": "4,95 €", "return_days": "14", "carrier": "", "free_shipping_from": "",
                  "samples_included": False}
        for url in ("/garantia-de-autenticidad/", "/envios-y-devoluciones/"):
            self.assertEqual(self.client.get(url).status_code, 404)
            with self.settings(LEGAL_OWNER=owner, SHOP_POLICY={**policy, "return_days": "7"}):   # below legal minimum
                self.assertEqual(self.client.get(url).status_code, 404)
            with self.settings(LEGAL_OWNER=owner, SHOP_POLICY={**policy, "supplier_authorized": False}):
                self.assertEqual(self.client.get(url).status_code, 404)
        with self.settings(LEGAL_OWNER=owner, SHOP_POLICY=policy):
            page = self.client.get("/envios-y-devoluciones/").content.decode()
            self.assertIn("2-4 días laborables", page)
            self.assertNotIn("muestras de regalo", page)
            self.assertIn("Unión Europea", self.client.get("/garantia-de-autenticidad/").content.decode())
            self.assertIn('href="/envios-y-devoluciones/"', self.client.get("/").content.decode())


class ErrorPageTests(TestCase):
    def test_404_is_spanish_and_has_no_third_party_resources(self):
        response = self.client.get("/no-existe-esta-pagina/")
        self.assertEqual(response.status_code, 404)
        html = response.content.decode()
        self.assertIn("No encontramos esta página.", html)
        self.assertNotIn("instaud", html)
        self.assertNotIn("<iframe", html)
        self.assertIsNone(__import__("re").search(r'(?:src|href)="https?://(?!testserver)', html))


@override_settings(STORE_MODE="prelaunch")
class FamiliesGuidesKeywordsTests(TestCase):
    URL = "https://www.versace.com/x"

    def setUp(self):
        from .models import Gender
        Gender.objects.create(db_name="M", name="Hombre")
        self.brand = Brand.objects.create(db_name="versace", name="Versace")
        for i, name in enumerate(("Pour Homme", "Eau Fraîche", "Dylan Blue")):
            Product.objects.create(name=name, brand=self.brand, sku=f"F{i}", catalog_origin=Product.Origin.REFERENCE,
                                   publication_status="approved")

    def apply(self, sku, name, family):
        from .reference_evidence import apply_evidence
        row = {"sku": sku, "status": "verified", "brand": "Versace", "official_name": name, "concentration": "edt",
               "size": "100ml", "gender": "M", "source_url": self.URL, "description_es": "Texto propio " * 12,
               "description_source": self.URL, "notes_pyramid": "", "field_sources": "", "family": family}
        return apply_evidence([row], apply=True)

    def test_family_applied_with_evidence_and_family_pages(self):
        self.assertEqual(self.apply("F0", "Pour Homme", "Aromática")["F0"][0], "updated")
        product = Product.objects.get(sku="F0")
        self.assertEqual(product.fragrance_family.name, "Aromática")
        self.assertEqual(product.verification_sources["family"], self.URL)
        self.assertIn("hierbas", product.fragrance_family.description)
        self.assertEqual(self.apply("F1", "Eau Fraîche", "Inventada")["F1"][0], "error")   # unknown family
        html = self.client.get("/products/familia/aromatica/").content.decode()
        self.assertIn("<h1>Perfumes de la familia aromática</h1>", html)
        self.assertIn("Las fragancias aromáticas se basan en hierbas", html)
        self.assertIn('content="noindex, follow"', html)                 # 1 product only
        for sku, name in (("F1", "Eau Fraîche"), ("F2", "Dylan Blue")):
            self.apply(sku, name, "Aromática")
        self.assertNotIn("noindex", self.client.get("/products/familia/aromatica/").content.decode())
        self.assertIn("/products/familia/aromatica/", self.client.get("/sitemap.xml").content.decode())
        self.assertIn('href="/products/familia/aromatica/"', self.client.get("/products/families/").content.decode())

    def test_guides_are_indexable_linked_and_structured(self):
        from home.guides import GUIDES
        index = self.client.get("/guias/").content.decode()
        sitemap = self.client.get("/sitemap.xml").content.decode()
        for guide in GUIDES:
            url = f"/guias/{guide['slug']}/"
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            html = response.content.decode()
            self.assertIn(f"<h1>{guide['title']}</h1>", html)
            self.assertIn('"@type": "Article"', html)
            self.assertIn(f'<link rel="canonical" href="http://testserver{url}">', html)
            self.assertIn(url, index)
            self.assertIn(url, sitemap)
        self.assertIn("/guias/", sitemap)
        self.assertEqual(self.client.get("/guias/no-existe/").status_code, 404)
        self.assertIn('href="/guias/"', self.client.get("/").content.decode())

    def test_colonias_keyword_on_collection_and_catalog_pages(self):
        self.assertIn("<h1>Perfumes y colonias para hombre</h1>", self.client.get("/products/genero/hombre/").content.decode())
        self.assertIn("<title>Catálogo de perfumes y colonias | Perfumería El Buen Olor</title>",
                      self.client.get("/products/").content.decode())
        self.assertIn("perfumes y colonias", self.client.get("/").content.decode())
