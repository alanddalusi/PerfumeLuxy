"""Verified data for the reference catalog: evidence file, batch apply, report and publication."""

import csv
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from .models import Brand, Gender, Product, PublicationDecision
from .reference_evidence import COLUMNS, EVIDENCE_FILE, STATUSES, is_official, read_evidence, row_problems

URL = "https://www.carolinaherrera.com/cl/en/p-fragrance/good-girl-eau-de-parfum"


class EvidenceFileTests(TestCase):
    """The committed evidence file itself."""

    def test_covers_every_reference_sku_once_with_known_statuses(self):
        rows = read_evidence()
        self.assertEqual(list(rows[0]), COLUMNS)
        fixture = json.loads((Path(EVIDENCE_FILE).parents[1] / "fixtures" / "products.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(r["sku"] for r in rows), sorted(p["fields"]["sku"] for p in fixture))
        self.assertTrue({r["status"] for r in rows} <= set(STATUSES))

    def test_every_verified_row_is_complete_and_official(self):
        brands = {b["pk"]: b["fields"]["name"] for b in json.loads(
            (Path(EVIDENCE_FILE).parents[1] / "fixtures" / "brands.json").read_text(encoding="utf-8"))}
        fixture = {p["fields"]["sku"]: brands[p["fields"]["brand"]] for p in json.loads(
            (Path(EVIDENCE_FILE).parents[1] / "fixtures" / "products.json").read_text(encoding="utf-8"))}
        verified = [r for r in read_evidence() if r["status"] == "verified"]
        self.assertGreater(len(verified), 0)
        for row in verified:
            product = SimpleNamespace(brand=SimpleNamespace(name=fixture[row["sku"]]))
            self.assertEqual(row_problems(row, product), [], row["sku"])
        # one page per perfume: no two verified rows describe the same product
        keys = [(r["brand"], r["official_name"].lower(), r["concentration"], r["size"]) for r in verified]
        self.assertEqual(len(keys), len(set(keys)))

    def test_official_domain_check(self):
        self.assertTrue(is_official("https://www.dior.com/en_int/beauty/products/joy.html", "Dior"))
        self.assertTrue(is_official("https://www.lancome.co.uk/perfume/x.html", "Lancome"))
        self.assertTrue(is_official("https://yslbeautyus.com/fragrance/x.html", "Yves Saint Laurent"))
        self.assertFalse(is_official("http://www.dior.com/x", "Dior"))                 # not https
        self.assertFalse(is_official("https://dior.example.com/x", "Dior"))            # not the brand's domain
        self.assertFalse(is_official("https://www.notino.es/dior/sauvage/", "Dior"))  # retailer
        self.assertFalse(is_official("https://www.chanel.com/x", "Dior"))              # another brand


@override_settings(STORE_MODE="prelaunch")
class ApplyAndPublishTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brand = Brand.objects.create(db_name="ch", name="Carolina Herrera")
        Gender.objects.create(db_name="F", name="Mujer")
        self.product = Product.objects.create(
            name="Good girl", brand=self.brand, sku="ER1", description="Unverified legacy text.", price=89,
            catalog_origin=Product.Origin.REFERENCE)
        self.twin = Product.objects.create(
            name="Good Girl", brand=self.brand, sku="ER2", catalog_origin=Product.Origin.REFERENCE)
        self.reviewer = get_user_model().objects.create_superuser(username="reviewer")

    def evidence(self, rows):
        path = Path(self.tmp.name) / "evidence.csv"
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row.get(column, "") for column in COLUMNS})
        return str(path)

    def good_row(self, sku="ER1", **extra):
        return {"sku": sku, "status": "verified", "brand": "Carolina Herrera", "official_name": "Good Girl",
                "concentration": "edp", "size": "80ml", "gender": "F", "source_url": URL, **extra}

    def run_apply(self, path, *flags):
        out = StringIO()
        call_command("apply_reference_evidence", "--file", path, *flags, stdout=out)
        return out.getvalue()

    def test_dry_run_then_apply_is_idempotent_and_never_publishes(self):
        path = self.evidence([
            self.good_row(),
            {"sku": "ER2", "status": "duplicate", "brand": "Carolina Herrera"},
        ])
        self.assertIn("DRY RUN", self.run_apply(path))
        self.product.refresh_from_db()
        self.assertIsNone(self.product.concentration)

        self.assertIn("1 updated, 0 unchanged, 1 skipped, 0 error", self.run_apply(path, "--apply"))
        self.product.refresh_from_db()
        self.assertEqual((self.product.name, self.product.concentration, self.product.size, self.product.gender.db_name),
                         ("Good Girl", "edp", "80ml", "F"))
        self.assertEqual(self.product.description, "")              # unverified legacy text removed
        self.assertEqual(self.product.verification_sources["concentration"], URL)
        self.assertEqual(self.product.slug, "carolina-herrera-good-girl-eau-de-parfum")
        self.assertIn("Carolina Herrera Good Girl Eau de Parfum 80 ml, perfume para mujer", self.product.meta_description)
        self.assertLessEqual(len(self.product.meta_description), 160)
        self.assertEqual(self.product.publication_status, Product.Publication.DRAFT)
        self.assertIn("0 updated, 1 unchanged", self.run_apply(path, "--apply"))   # resumable / repeatable

    def test_rows_that_are_not_official_or_valid_are_rejected(self):
        path = self.evidence([self.good_row(source_url="https://www.notino.es/carolina-herrera/good-girl/"),
                              self.good_row(sku="ER2", size="85ml")])
        output = self.run_apply(path, "--apply")
        self.assertIn("source_url must be https on the brand's official site", output)
        self.assertIn("size '85ml' is not a valid choice", output)
        self.product.refresh_from_db()
        self.assertIsNone(self.product.concentration)

    def test_report_and_batch_publication(self):
        call_command("apply_reference_evidence", "--file", self.evidence([self.good_row()]), "--apply", stdout=StringIO())
        report = StringIO()
        out_csv = Path(self.tmp.name) / "report.csv"
        call_command("reference_catalog_progress", "--file", self.evidence([self.good_row()]),
                     "--output", str(out_csv), stdout=report)
        self.assertIn("ready_to_publish", report.getvalue())
        self.assertIn("incomplete:pending", report.getvalue())
        self.assertIn("ER1,Carolina Herrera,Good Girl,edp,80ml,verified", out_csv.read_text(encoding="utf-8-sig"))

        clerk = get_user_model().objects.create_user(username="clerk")
        with self.assertRaises(Exception):
            call_command("publish_reference_batch", "--reviewer", clerk.username, stdout=StringIO())
        dry = StringIO()
        call_command("publish_reference_batch", "--reviewer", "reviewer", stdout=dry)
        self.assertIn("1 ready", dry.getvalue())
        self.product.refresh_from_db()
        self.assertEqual(self.product.publication_status, Product.Publication.DRAFT)

        call_command("publish_reference_batch", "--reviewer", "reviewer", "--apply", stdout=StringIO())
        self.product.refresh_from_db()
        self.assertEqual(self.product.publication_status, Product.Publication.APPROVED)
        self.assertEqual(PublicationDecision.objects.filter(product=self.product).count(), 1)
        self.assertFalse(Product.objects.sellable().filter(pk=self.product.pk).exists())   # reference: never for sale

        # A second SKU with identical verified data is not published twice (duplicate content).
        Product.objects.filter(pk=self.twin.pk).update(
            concentration="edp", size="80ml", verification_sources=self.product.verification_sources)
        out = StringIO()
        call_command("publish_reference_batch", "--reviewer", "reviewer", "--apply", stdout=out)
        self.assertIn("1 duplicates skipped", out.getvalue())

        # Public page: verified title and description, no legacy price, no sale.
        html = self.client.get(self.product.get_absolute_url()).content.decode()
        self.assertIn("<title>Carolina Herrera Good Girl Eau de Parfum 80 ml | Perfumería El Buen Olor</title>", html)
        self.assertIn('<meta name="description" content="Carolina Herrera Good Girl Eau de Parfum 80 ml, perfume para mujer.', html)
        self.assertIn('<link rel="canonical" href="http://testserver/products/carolina-herrera-good-girl-eau-de-parfum/">', html)
        self.assertIn('"description": "Carolina Herrera Good Girl Eau de Parfum 80 ml, perfume para mujer.', html)  # JSON-LD
        self.assertNotIn('"offers"', html)
        self.assertNotIn("Unverified legacy text", html)
        self.assertNotIn("89", html.split("<main", 1)[-1].split("</main>")[0])
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("carolina-herrera-good-girl-eau-de-parfum", sitemap)
        self.assertNotIn(self.twin.slug, sitemap)

    def test_compare_page_hides_reference_prices(self):
        other = Product.objects.create(name="Bad Boy", brand=self.brand, sku="ER3", price=77,
                                       catalog_origin=Product.Origin.REFERENCE)
        Product.objects.filter(pk__in=[self.product.pk, other.pk]).update(publication_status=Product.Publication.APPROVED)
        html = self.client.get(f"/products/compare/?products={self.product.pk},{other.pk}").content.decode()
        self.assertIn("Bad Boy", html)
        self.assertNotIn("€89", html)
        self.assertNotIn("€77", html)
