import csv
import importlib
from io import StringIO

from django.apps import apps as global_apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Brand, Product, PublicationDecision
from .publication import decide_product


EVIDENCE = {key: "Expediente REF-001" for key in ("name", "brand", "concentration", "size", "description")}


class ReferenceCatalogTests(TestCase):
    def setUp(self):
        self.reviewer = get_user_model().objects.create_superuser(username="revisor")

    def load(self, *args):
        output = StringIO()
        call_command("load_reference_catalog", *args, stdout=output)
        return output.getvalue()

    def test_load_is_a_dry_run_by_default_and_never_publishes(self):
        self.assertIn("265 reference drafts would be added", self.load())
        self.assertFalse(Product.objects.exists())

        self.assertIn("265 reference drafts added", self.load("--apply"))
        legacy = Product.objects.filter(catalog_origin=Product.Origin.REFERENCE)
        self.assertEqual(legacy.count(), 265)
        self.assertFalse(Product.objects.published().exists())
        self.assertFalse(legacy.exclude(stock=0).exists())
        self.assertFalse(PublicationDecision.objects.exists())

        edited = legacy.first()
        Product.objects.filter(pk=edited.pk).update(name="Nombre revisado")
        self.assertIn("0 reference drafts added, 265 already present", self.load("--apply"))
        edited.refresh_from_db()
        self.assertEqual(edited.name, "Nombre revisado")
        self.assertFalse(self.client.get(reverse("products:products")).content.count(b"sf-card eo-perfume-card"))

    def reference_product(self, **fields):
        values = {
            "name": "Referencia de prueba", "brand": Brand.objects.create(db_name="ref", name="Marca Ref"),
            "description": "Descripción comprobada.", "catalog_origin": Product.Origin.REFERENCE,
            "price": 80, "stock": 5, "verification_sources": EVIDENCE,
        }
        values.update(fields)
        return Product.objects.create(**values)

    def test_reference_approval_requires_checked_concentration_and_format(self):
        product = self.reference_product()
        with self.assertRaisesMessage(ValidationError, "concentración y formato"):
            decide_product(product, Product.Publication.APPROVED, self.reviewer)
        Product.objects.filter(pk=product.pk).update(concentration="EDP", size="100ml")
        Product.objects.filter(pk=product.pk).update(verification_sources={"name": "x", "brand": "x"})
        with self.assertRaisesMessage(ValidationError, "concentration"):
            decide_product(product, Product.Publication.APPROVED, self.reviewer)
        Product.objects.filter(pk=product.pk).update(verification_sources=EVIDENCE)
        decide_product(product, Product.Publication.APPROVED, self.reviewer)
        self.assertTrue(Product.objects.published().filter(pk=product.pk).exists())

    def test_approved_reference_is_informative_only_and_never_sellable(self):
        product = self.reference_product(concentration="EDP", size="100ml")
        decide_product(product, Product.Publication.APPROVED, self.reviewer)
        response = self.client.get(product.get_absolute_url())
        self.assertContains(response, "Próximamente")
        self.assertContains(response, "Fotografía en preparación")
        self.assertContains(response, "Aviso de disponibilidad")
        for hidden in ("Añadir al carrito", "80,00", "80.00", '"offers":'):
            self.assertNotContains(response, hidden)
        self.assertContains(self.client.get(reverse("products:products")), "Próximamente")

        self.assertFalse(Product.objects.sellable().filter(pk=product.pk).exists())
        with override_settings(STORE_MODE="live"):
            response = self.client.post(reverse("bag:add_to_bag", args=[product.pk]), {"quantity": 1, "redirect_url": "/"})
            self.assertEqual(response.status_code, 404)
            live = self.client.get(product.get_absolute_url())
            self.assertNotContains(live, "Añadir al carrito")
            self.assertNotContains(live, '"offers":')
            self.assertContains(live, "Aviso de disponibilidad")
        self.assertFalse(self.client.session.get("bag"))

    def test_retire_reference_catalog_withdraws_in_one_traceable_step(self):
        approved = self.reference_product(concentration="EDP", size="100ml")
        decide_product(approved, Product.Publication.APPROVED, self.reviewer)
        own = Product.objects.create(name="Propio", brand=approved.brand, description="x",
                                     verification_sources={"name": "x", "brand": "x", "description": "x"})
        decide_product(own, Product.Publication.APPROVED, self.reviewer)

        output = StringIO()
        call_command("retire_reference_catalog", stdout=output)
        self.assertIn("1 approved reference products would be withdrawn", output.getvalue())
        with self.assertRaises(CommandError):
            call_command("retire_reference_catalog", "--apply", stdout=StringIO())
        call_command("retire_reference_catalog", "--apply", "--reviewer", "revisor", stdout=output)

        approved.refresh_from_db()
        self.assertEqual(approved.publication_status, Product.Publication.WITHDRAWN)
        self.assertEqual(self.client.get(approved.get_absolute_url()).status_code, 404)
        self.assertTrue(Product.objects.published().filter(pk=own.pk).exists())
        self.assertEqual(approved.publication_history.order_by("pk").last().status, Product.Publication.WITHDRAWN)

    def test_report_lists_what_each_reference_product_still_needs(self):
        self.reference_product(verification_sources={"name": "x"})
        output = StringIO()
        call_command("reference_catalog_report", "--csv", stdout=output)
        rows = list(csv.DictReader(StringIO(output.getvalue())))
        self.assertEqual(len(rows), 1)
        self.assertIn("concentration (valor)", rows[0]["missing"])
        self.assertIn("brand (referencia)", rows[0]["missing"])
        summary = StringIO()
        call_command("reference_catalog_report", stdout=summary)
        self.assertIn("reference  draft      1", summary.getvalue())

    def test_migration_tags_existing_legacy_skus_without_publishing(self):
        migration = importlib.import_module("products.migrations.0011_product_catalog_origin")
        legacy = Product.objects.create(name="Heredado", sku="ER1173710781", description="x")
        other = Product.objects.create(name="Nuevo", sku="OWN-1", description="x")
        migration.tag_legacy_products(global_apps, None)
        legacy.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(legacy.catalog_origin, Product.Origin.REFERENCE)
        self.assertEqual(legacy.publication_status, Product.Publication.DRAFT)
        self.assertEqual(other.catalog_origin, Product.Origin.OWN)
