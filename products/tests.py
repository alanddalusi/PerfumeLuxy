from io import BytesIO, StringIO
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from allauth.account.models import EmailAddress

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from PIL import Image

from home.models import Subscriber

from .models import Brand, CatalogImage, Category, FragranceFamily, FragranceNote, Product, ProductSize, PublicationDecision, Review, StockAlert, Wishlist


class CatalogImportTests(TestCase):
    def test_import_requires_review_settings(self):
        with self.assertRaises(CommandError):
            call_command("import_review_catalog", stdout=StringIO())
        self.assertFalse(Product.objects.exists())

    @override_settings(CATALOG_REVIEW=True)
    def test_import_twice_preserves_unique_stable_slugs_and_existing_records(self):
        output = StringIO()
        call_command("import_review_catalog", stdout=output)
        self.assertIn("265 added, 0 already present", output.getvalue())
        self.assertEqual(Product.objects.count(), 265)
        self.assertEqual(Product.objects.values("slug").distinct().count(), 265)
        self.assertFalse(Product.objects.filter(slug="").exists())
        self.assertFalse(Product.objects.exclude(stock=0).exists())
        self.assertFalse(Product.objects.published().exists())
        self.assertEqual(
            set(Product.objects.filter(slug__regex=r"^carolina-herrera-212-vip(-[0-9]+)?$")
                .values_list("slug", flat=True)),
            {"carolina-herrera-212-vip", "carolina-herrera-212-vip-1"},
        )
        previous = dict(Product.objects.values_list("sku", "slug"))
        product = Product.objects.get(sku="ER1173710781")
        product.name = "Nombre revisado"
        product.save(update_fields=["name"])
        call_command("import_review_catalog", stdout=output)
        self.assertIn("0 added, 265 already present", output.getvalue())
        self.assertEqual(dict(Product.objects.values_list("sku", "slug")), previous)
        product.refresh_from_db()
        self.assertEqual(product.name, "Nombre revisado")


@override_settings(STORE_MODE="prelaunch")
class PublicCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.brand = Brand.objects.create(db_name="marca-test", name="Marca & Test")
        cls.category = Category.objects.create(db_name="perfumes", name="Perfumes")
        cls.product = Product.objects.create(
            brand=cls.brand, category=cls.category, name="Ámbar & Té",
            publication_status=Product.Publication.APPROVED,
            description="Fragancia de prueba", price="39.50", has_sizes=True,
        )
        cls.other = Product.objects.create(name="Especias", publication_status=Product.Publication.APPROVED, description="Distinto", price=60)
        cls.list_url = reverse("products:products")
        cls.suggest_url = reverse("products:search_suggestions")

    def results(self, **params):
        response = self.client.get(self.list_url, params)
        self.assertEqual(response.status_code, 200)
        return list(response.context["products"])

    def test_search_and_suggestions_use_database_products(self):
        self.assertEqual(self.results(q="  & Té "), [self.product])
        self.assertEqual(self.results(q="Fragancia"), [self.product])
        self.assertCountEqual(self.results(q="  "), [self.product, self.other])
        self.assertEqual(self.results(q="%_"), [])
        response = self.client.get(self.suggest_url, {"q": "& Té"})
        self.assertEqual(response.json()["results"], [{
            "name": self.product.name,
            "brand": self.brand.name,
            "url": self.product.get_absolute_url(),
        }])
        self.assertEqual(self.client.get(self.suggest_url, {"q": "  "}).json(), {"results": []})
        self.assertEqual(self.client.post(self.suggest_url).status_code, 405)

    def test_taxonomies_prices_sort_and_invalid_parameters(self):
        self.assertEqual(self.results(brand=self.brand.db_name, category=self.category.db_name), [self.product])
        self.assertEqual(self.results(brand=self.brand.name, category=self.category.pk), [self.product])
        self.assertEqual(self.results(brand="missing"), [])
        self.assertEqual(self.results(category="missing"), [])
        self.assertEqual(self.results(price_to="40"), [self.product])
        self.assertEqual(self.results(price_from="50"), [self.other])
        self.assertEqual(self.results(sort="price_asc"), [self.product, self.other])
        self.assertEqual(self.results(sort="price", direction="desc"), [self.other, self.product])
        self.assertEqual(self.results(sort="name_desc"), [self.product, self.other])
        for key, value in (
            ("price_from", "abc"), ("price_to", "NaN"), ("price_from", "-1"),
            ("price_to", "1e999999"), ("sort", "not_a_field"),
            ("direction", "invalid"), ("has_discount", "invalid"),
        ):
            with self.subTest(key=key, value=value):
                self.assertCountEqual(self.results(**{key: value}), [self.product, self.other])
        self.assertContains(
            self.client.get(self.list_url, {"price_from": "51", "price_to": "40"}),
            "El precio mínimo debe ser menor",
        )

    def test_pagination_retains_repeated_filters_and_query_budget(self):
        user = get_user_model().objects.create_user(username="reviewer")
        params = {
            "brand": [self.brand.db_name, "missing"],
            "category": self.category.db_name, "q": "Fragancia", "sort": "price_asc",
            "price_from": "20", "price_to": "50",
        }
        Review.objects.create(
            user=user, product=self.product, title="Prueba", comment="Prueba",
            is_approved=True, rating=4,
        )
        with CaptureQueriesContext(connection) as single:
            response = Client().get(self.list_url, params)
        self.assertEqual(response.status_code, 200)
        for i in range(61):
            product = Product.objects.create(
                brand=self.brand, category=self.category, name=f"Producto {i}",
                publication_status=Product.Publication.APPROVED,
                description="Fragancia de prueba", price=40,
            )
            Review.objects.create(
                user=user, product=product, title="Prueba", comment="Prueba",
                is_approved=True, rating=4,
            )
        with CaptureQueriesContext(connection) as many:
            page = Client().get(self.list_url, params)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(many), len(single))
        self.assertLessEqual(len(many), 12)
        self.assertEqual(len(page.context["products"]), 60)
        next_page = page.context["next_page_url"]
        expected = {key: value if isinstance(value, list) else [value] for key, value in params.items()}
        self.assertEqual(parse_qs(urlsplit(next_page).query), {**expected, "page": ["2"]})
        final = self.client.get(self.list_url + next_page)
        self.assertEqual(len(final.context["products"]), 2)
        self.assertEqual(parse_qs(urlsplit(final.context["previous_page_url"]).query)["page"], ["1"])

    def test_detail_and_legacy_url_keep_published_slug(self):
        url = self.product.get_absolute_url()
        self.product.name = "Nuevo nombre"
        self.product.save()
        self.assertEqual(self.product.get_absolute_url(), url)
        self.assertEqual(self.client.get(url).status_code, 404)
        Product.objects.filter(pk=self.product.pk).update(publication_status=Product.Publication.APPROVED)
        response = self.client.get(url)
        self.assertContains(response, "Nuevo nombre")
        self.assertContains(response, "?brand=marca-test")
        self.assertContains(response, "?category=perfumes")
        self.assertNotContains(response, '"offers":')
        self.assertRedirects(
            self.client.get(f"/products/{self.product.pk}/"), url, status_code=301
        )
        self.assertEqual(self.client.get("/products/no-existe/").status_code, 404)

    def test_navigation_subscription_profile_favorites_and_cart(self):
        detail = self.product.get_absolute_url()
        home = reverse("home:index")
        self.assertContains(self.client.get(home), self.suggest_url)
        self.assertRedirects(self.client.post(home, {"email": "visitor@example.test", "consent": "on"}), home)
        self.assertEqual(Subscriber.objects.count(), 1)
        self.assertContains(self.client.post(home, {"email": "incorrecto"}), "correo electrónico válido")
        self.assertEqual(Subscriber.objects.count(), 1)

        user = get_user_model().objects.create_user(username="visitor")
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("profiles:profile")), "Historial de Pedidos")
        self.assertRedirects(self.client.post(
            reverse("products:toggle_wishlist", args=[self.product.pk]), {"next": detail},
        ), detail)
        self.assertContains(self.client.get(reverse("products:view_wishlist")), escape(self.product.name))

        bag = reverse("bag:view_bag")
        add = reverse("bag:add_to_bag", args=[self.product.pk])
        self.assertRedirects(self.client.post(
            add, {"quantity": "2", "product_size": "30ML", "redirect_url": "//example.test"}
        ), bag)
        for invalid in ("abc", "0", "-1", "7"):
            self.assertEqual(self.client.post(add, {"quantity": invalid}).status_code, 400)
        adjust = reverse("bag:adjust_bag", args=[self.product.pk])
        self.assertRedirects(self.client.post(adjust, {"quantity": "3", "product_size": "30ML"}), bag)
        self.assertEqual(self.client.session["bag"][str(self.product.pk)], {"items_by_size": {"30ML": 3}})
        self.assertContains(self.client.get(bag), escape(self.product.name))
        self.assertEqual(self.client.get(reverse("checkout:checkout")).status_code, 403)

    def test_empty_catalog_has_a_message(self):
        Product.objects.all().delete()
        self.assertContains(self.client.get(self.list_url), "Aún no hay productos disponibles")

    def test_error_handlers_keep_http_status(self):
        client = Client(raise_request_exception=False)
        self.assertEqual(client.get("/url-que-no-existe/").status_code, 404)
        with patch("home.views.SEOManager", side_effect=RuntimeError("Fallo de prueba")):
            self.assertEqual(client.get(reverse("home:index")).status_code, 500)

    def test_comparison_accepts_legacy_and_repeated_product_ids(self):
        url = reverse("products:compare_products")
        for ids in ([self.product.pk, self.other.pk], f"{self.product.pk},{self.other.pk}"):
            with self.subTest(ids=ids):
                response = self.client.get(url, {"products": ids})
                self.assertEqual(response.status_code, 200)
                self.assertCountEqual(response.context["products"], [self.product, self.other])
        self.assertRedirects(self.client.get(url, {"products": "invalid"}), self.list_url)


@override_settings(STORE_MODE="prelaunch")
class PremiumStorefrontTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        brand = Brand.objects.create(name="Marca de prueba", db_name="marca-prueba")
        cls.family = FragranceFamily.objects.create(name="Amaderada")
        cls.category = Category.objects.create(name="Perfumes", db_name="perfumes")
        cls.product = Product.objects.create(
            name="Perfume de prueba", description="Descripción de prueba.",
            brand=brand, fragrance_family=cls.family, category=cls.category,
            concentration="edp", price=900, stock=3, image="approved/front.webp",
        )
        cls.product.fragrance_notes.add(FragranceNote.objects.create(name="Cedro", note_type="base"))
        ProductSize.objects.create(
            product=cls.product, size_ml=50, price=900, sku="test-50", image="approved/side.webp",
        )
        ProductSize.objects.create(
            product=cls.product, size_ml=75, price=900, sku="test-75", image="uncleared.webp",
        )

        cls.image = CatalogImage.objects.create(
            product=cls.product, source_file="approved/front.webp", asset="web/test.webp",
            thumbnail="thumb/test.webp", approved_at=timezone.now(),
        )
        cls.second_image = CatalogImage.objects.create(
            product=cls.product, source_file="approved/side.webp", asset="web/test2.webp",
            thumbnail="thumb/test2.webp", approved_at=timezone.now(),
        )
        Product.objects.filter(pk=cls.product.pk).update(publication_status=Product.Publication.APPROVED)

    def test_home_discovery_and_explicit_idempotent_consent(self):
        home = reverse("home:index")
        form = self.client.get(home)
        self.assertContains(form, "?fragrance_family=Amaderada")
        self.assertContains(form, "?category=perfumes")
        self.assertContains(form, 'name="consent" required')
        self.assertNotContains(form, "Env\u00edo gratis")
        Subscriber.objects.create(email="legacy@example.test")
        data = {"email": "Legacy@example.test"}
        self.assertContains(self.client.post(home, data), "Confirma que quieres recibir avisos")
        self.assertEqual(Subscriber.objects.count(), 1)
        data["consent"] = "on"
        self.assertRedirects(self.client.post(home, data), home)
        self.assertRedirects(self.client.post(home, data), home)
        self.assertEqual(Subscriber.objects.filter(consent_version="launch-email-v2").count(), 1)
        self.assertEqual(Subscriber.objects.filter(consent_version="").count(), 1)

    def test_gallery_uses_only_approved_files_and_real_product_details(self):
        response = self.client.get(self.product.get_absolute_url())
        for text in (reverse("products:catalog_image", args=[self.image.pk, "web"]), reverse("products:catalog_image", args=[self.second_image.pk, "web"]), "50 ml", "75 ml", "Cedro", "Amaderada"):
            self.assertContains(response, text)
        for text in ("uncleared.webp", "Añadir al carrito", "/checkout/", "900", '"offers":', "js.stripe.com"):
            self.assertNotContains(response, text)
        self.assertContains(response, "<title>", count=1)
        self.assertContains(response, 'rel="canonical" href="http://testserver' + self.product.get_absolute_url())
        self.assertContains(response, "Aviso de disponibilidad")

    def test_catalog_filters_canonical_and_comparison_controls(self):
        url = reverse("products:products")
        response = self.client.get(url, {"brand": "marca-prueba"})
        self.assertContains(response, 'value="marca-prueba" checked')
        self.assertContains(response, 'form="sf-compare"')
        self.assertContains(response, 'name="products"')
        self.assertContains(response, 'content="noindex, follow"')
        self.assertNotContains(response, "Solo en stock")
        self.assertNotContains(response, "Sin stock")
        self.assertNotContains(response, "900")

    def test_stock_alert_requires_verified_email_and_is_idempotent(self):
        url = reverse("products:notify_when_available", args=[self.product.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        user = get_user_model().objects.create_user(username="testwatcher", email="watcher@example.test")
        self.client.force_login(user)
        detail = self.product.get_absolute_url()
        self.assertRedirects(self.client.post(url, {"consent": "on"}), detail)
        self.assertFalse(StockAlert.objects.exists())
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        self.assertRedirects(self.client.post(url, {"consent": "on"}), detail)
        self.assertRedirects(self.client.post(url, {"consent": "on"}), detail)
        self.assertEqual(StockAlert.objects.get().email, user.email)
        self.assertIsNone(StockAlert.objects.get().confirmed_at)



@override_settings(STORE_MODE="prelaunch")
class PublicationTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(db_name="test", name="Marca de prueba")
        self.family = FragranceFamily.objects.create(name="Familia de prueba")
        self.product = Product.objects.create(
            name="Candidato secreto", brand=self.brand, fragrance_family=self.family,
            description="Información de prueba.", verification_sources={
                "name": "Ficha de prueba", "brand": "Ficha de prueba",
                "family": "Ficha de prueba", "description": "Ficha de prueba",
            },
        )
        self.reviewer = get_user_model().objects.create_superuser(username="reviewer")
        self.approve = reverse("admin:products_product_decision", args=[self.product.pk, "approved"])
        self.withdraw = reverse("admin:products_product_decision", args=[self.product.pk, "withdrawn"])

    def test_draft_and_withdrawn_product_are_excluded_across_public_surfaces(self):
        user = get_user_model().objects.create_user(username="visitor")
        wishlist = Wishlist.objects.create(user=user)
        wishlist.products.add(self.product)
        self.client.force_login(user)

        def excluded():
            detail = self.product.get_absolute_url()
            self.assertEqual(self.client.get(detail).status_code, 404)
            self.assertEqual(self.client.get(f"/products/{self.product.pk}/").status_code, 404)
            for path in (reverse("products:products"), reverse("products:view_wishlist"),
                         reverse("products:fragrance_families"), "/sitemap.xml"):
                self.assertNotContains(self.client.get(path), self.product.name)
            self.assertNotContains(self.client.get("/sitemap.xml"), detail)
            self.assertEqual(self.client.get(reverse("products:search_suggestions"), {"q": "Candidato"}).json()["results"], [])
            self.assertEqual(self.client.get(reverse("products:get_product_sizes", args=[self.product.pk])).status_code, 404)
            self.assertEqual(self.client.get(reverse("products:compare_products"), {"products": self.product.pk}).status_code, 302)
            self.assertEqual(self.client.post(reverse("products:add_to_comparison", args=[self.product.pk])).status_code, 404)
            from .views_reviews_wishlist import get_related_products, get_top_rated
            self.assertNotIn(self.product, get_related_products(self.product))
            self.assertNotIn(self.product, get_top_rated())

        excluded()
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(self.approve).status_code, 302)
        self.assertEqual(self.client.get(self.product.get_absolute_url()).status_code, 200)
        self.assertContains(self.client.get("/sitemap.xml"), self.product.get_absolute_url())
        self.assertContains(self.client.get("/robots.txt"), "http://testserver/sitemap.xml")
        self.assertEqual(self.client.post(self.withdraw).status_code, 302)
        delete = reverse("products:delete_product", args=[self.product.pk])
        self.assertEqual(self.client.post(delete).status_code, 403)
        self.client.force_login(user)
        excluded()
        self.assertEqual(PublicationDecision.objects.filter(product=self.product).count(), 2)

    def test_admin_requires_permissions_post_and_csrf_and_validates_sources(self):
        self.assertEqual(self.client.post(self.approve).status_code, 302)
        limited = get_user_model().objects.create_user(username="editor", is_staff=True)
        limited.user_permissions.add(Permission.objects.get(codename="change_product"))
        self.client.force_login(limited)
        self.assertEqual(self.client.post(self.approve).status_code, 403)

        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.reviewer)
        change = reverse("admin:products_product_change", args=[self.product.pk])
        self.assertContains(strict.get(change), "Aprobar y publicar")
        self.assertEqual(strict.get(self.approve).status_code, 405)
        self.assertEqual(strict.post(self.approve).status_code, 403)
        csrf = {"HTTP_X_CSRFTOKEN": strict.cookies["csrftoken"].value}
        Product.objects.filter(pk=self.product.pk).update(verification_sources={})
        self.assertEqual(strict.post(self.approve, **csrf).status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.publication_status, Product.Publication.DRAFT)
        self.assertFalse(PublicationDecision.objects.exists())

    def test_new_products_default_to_draft_and_admin_rejects_non_staff(self):
        self.assertEqual(Product.objects.create(name="Sin revisar").publication_status, Product.Publication.DRAFT)
        self.assertFalse(Product.objects.published().exists())
        paths = [reverse("admin:index"), self.approve, self.withdraw] + [
            reverse(f"admin:{name}_changelist") for name in (
                "products_product", "products_catalogimage", "products_publicationdecision",
                "products_stockalert", "home_subscriber",
            )
        ]
        customer = get_user_model().objects.create_user(username="customer")
        for user in (None, customer):
            if user:
                self.client.force_login(user)
            for path in paths:
                response = self.client.post(path) if path in (self.approve, self.withdraw) else self.client.get(path)
                self.assertEqual(response.status_code, 302, path)
                self.assertIn(reverse("admin:login"), response["Location"])
        self.assertFalse(PublicationDecision.objects.exists())
        self.assertFalse(Product.objects.published().exists())

    def test_related_product_edit_requires_new_review(self):
        self.client.force_login(self.reviewer)
        self.client.post(self.approve)
        self.assertTrue(Product.objects.published().filter(pk=self.product.pk).exists())
        self.brand.name = "Marca editada"
        self.brand.save()
        self.assertFalse(Product.objects.published().filter(pk=self.product.pk).exists())

    def test_image_approval_creates_private_webp_derivatives_and_withdrawal_gates_urls(self):
        with TemporaryDirectory() as root, self.settings(STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"location": root + "/originals"}},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            "catalog_assets": {"BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"location": root + "/derivatives"}},
        }):
            raw = BytesIO()
            Image.new("RGB", (560, 700), (220, 210, 200)).save(raw, "PNG")
            self.product.image.save("source.png", ContentFile(raw.getvalue()))
            image = CatalogImage.objects.create(
                product=self.product, source_file=self.product.image.name,
                source_reference="Origen de prueba", rights_reference="Licencia de prueba",
            )
            url = reverse("products:catalog_image", args=[image.pk, "thumb"])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_login(self.reviewer)
            approve = reverse("admin:products_catalogimage_decision", args=[image.pk, "approve"])
            self.assertEqual(self.client.post(approve).status_code, 302)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.post(self.approve)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Content-Type"], "image/webp")
            with Image.open(BytesIO(b"".join(response.streaming_content))) as derivative:
                self.assertEqual(derivative.format, "WEBP")
                self.assertLessEqual(derivative.width, 420)
            withdraw = reverse("admin:products_catalogimage_decision", args=[image.pk, "withdraw"])
            self.assertEqual(self.client.post(withdraw).status_code, 302)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertContains(self.client.get(self.product.get_absolute_url()), "Fotografía en preparación")
