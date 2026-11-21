import csv
from contextlib import nullcontext

from django.core.management.base import BaseCommand
from PIL import Image, ImageOps

from products.models import Product
from products.presentation import product_alt

COLUMNS = [
    "sku", "brand", "name", "concentration", "size", "file", "file_status", "width", "height",
    "background", "alt_text", "source_reference", "rights_reference", "mapping_confirmed",
    "image_state", "product_status",
]


def image_state(product, file_name):
    records = [i for i in product.catalog_images.all() if i.source_file == file_name]
    if not records:
        return "", None
    record = records[-1]
    if record.is_public:
        return "approved", record
    return ("withdrawn" if record.withdrawn_at else "pending"), record


def describe_file(field):
    """(status, width, height, background) of a stored photo, read-only."""
    try:
        with field.open("rb") as handle, Image.open(handle) as image:
            rgb = ImageOps.exif_transpose(image).convert("RGB")
            w, h = rgb.size
            corners = [rgb.getpixel(xy) for xy in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2))]
            background = "white" if min(sum(c) / 3 for c in corners) >= 245 else "coloured"
            return "ok", w, h, background
    except FileNotFoundError:
        return "missing", "", "", ""
    except OSError:
        return "unreadable", "", "", ""


class Command(BaseCommand):
    help = (
        "Read-only review sheet of the product <-> photo mapping (by SKU): brand, name, suggested "
        "alt text and the rights columns to fill in. Edit it and feed it to assign_catalog_photos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--output", help="CSV file to write (UTF-8 with BOM, opens in Excel). Default: stdout.")
        parser.add_argument("--source", default="",
                            help="Pre-fill source_reference for rows that have none (e.g. where the photo comes from).")
        parser.add_argument("--all", action="store_true", help="Include products whose photo file is missing.")

    def handle(self, *args, **options):
        products = (Product.objects.exclude(image="").exclude(image__isnull=True)
                    .select_related("brand").prefetch_related("catalog_images").order_by("sku", "pk"))
        target = open(options["output"], "w", encoding="utf-8-sig", newline="") if options["output"] else nullcontext(self.stdout)
        written = missing = 0
        with target as out:
            writer = csv.writer(out)
            writer.writerow(COLUMNS)
            for product in products:
                status, width, height, background = describe_file(product.image)
                if status != "ok":
                    missing += 1
                    if not options["all"]:
                        continue
                state, record = image_state(product, product.image.name)
                writer.writerow([
                    product.sku, product.brand.name if product.brand else "", product.name,
                    product.get_concentration_display() if product.concentration else "",
                    product.size or "", product.image.name, status, width, height, background,
                    (record.alt_text if record and record.alt_text else product_alt(product)),
                    (record.source_reference if record else "") or options["source"],
                    record.rights_reference if record else "",
                    "yes" if record else "",
                    state, product.publication_status,
                ])
                written += 1
        self.stderr.write(f"{written} rows written; {missing} products point to a missing or unreadable file.\n")
