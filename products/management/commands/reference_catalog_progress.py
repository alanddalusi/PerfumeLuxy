import csv
from collections import Counter
from contextlib import nullcontext

from django.core.management.base import BaseCommand

from products.models import Product
from products.reference_catalog import missing_reference_data
from products.reference_evidence import EVIDENCE_FILE, STATUSES, read_evidence


class Command(BaseCommand):
    help = (
        "Progress report of the reference catalog: data complete / incomplete (and why), "
        "ready to publish, and photo state (none, pending rights, approved). CSV with --output."
    )

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(EVIDENCE_FILE))
        parser.add_argument("--output", help="CSV file (UTF-8 with BOM).")

    def handle(self, *args, **options):
        evidence = {row["sku"]: row for row in read_evidence(options["file"])}
        products = (Product.objects.filter(catalog_origin=Product.Origin.REFERENCE)
                    .select_related("brand").prefetch_related("sizes", "catalog_images").order_by("brand__name", "name"))
        totals, photos = Counter(), Counter()
        target = open(options["output"], "w", encoding="utf-8-sig", newline="") if options["output"] else nullcontext(None)
        with target as out:
            writer = csv.writer(out) if out else None
            if writer:
                writer.writerow(["sku", "brand", "name", "concentration", "size", "evidence_status", "evidence_note",
                                 "data", "missing", "publication", "photo", "source_url"])
            for product in products:
                row = evidence.get(product.sku, {})
                status = row.get("status") or "pending"
                missing = missing_reference_data(product)
                images = list(product.catalog_images.all())
                if any(i.is_public for i in images):
                    photo = "approved"
                elif product.image and product.image.storage.exists(product.image.name):
                    photo = "pending_rights"      # file present, no recorded permission yet
                else:
                    photo = "none"                # no file (the legacy record points to a missing one)
                if product.publication_status == Product.Publication.APPROVED:
                    group = "published"
                elif not missing:
                    group = "ready_to_publish"
                else:
                    group = f"incomplete:{status}"
                totals[group] += 1
                photos[photo] += 1
                if writer:
                    writer.writerow([
                        product.sku, product.brand.name if product.brand else "", product.name,
                        product.concentration or "", product.size or "", status,
                        row.get("notes") or STATUSES.get(status, ""), "complete" if not missing else "incomplete",
                        "; ".join(missing), product.publication_status, photo, row.get("source_url", ""),
                    ])
        self.stdout.write("Reference catalog:")
        for group, total in sorted(totals.items()):
            self.stdout.write(f"  {group:<28} {total}")
        self.stdout.write("Photos: " + ", ".join(f"{k} {v}" for k, v in sorted(photos.items())))
