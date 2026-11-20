import csv
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageOps

from products.models import Product


class Command(BaseCommand):
    help = (
        "Read-only inventory of the image files in MEDIA_ROOT and the products that use them: "
        "real format, dimensions, proportion, background and approval state. Writes CSV to stdout."
    )

    def handle(self, *args, **options):
        root = Path(settings.MEDIA_ROOT)
        users = defaultdict(list)
        for product in Product.objects.select_related("brand").prefetch_related("catalog_images"):
            if product.image:
                users[product.image.name].append(product)
        writer = csv.writer(self.stdout)
        writer.writerow(["file", "real_format", "width", "height", "shape", "short_side_ok", "background",
                         "products", "product_status", "approved_image"])
        names = {p.name for p in root.iterdir() if p.is_file()} if root.is_dir() else set()
        for name in sorted(names | set(users)):
            path = root / name
            fmt = width = height = shape = background = ""
            if path.is_file():
                try:
                    with Image.open(path) as image:
                        fmt, (width, height) = image.format, image.size
                        rgb = ImageOps.exif_transpose(image).convert("RGB")
                        corners = [rgb.getpixel(xy) for xy in ((1, 1), (width - 2, 1), (1, height - 2), (width - 2, height - 2))]
                        background = "white" if min(sum(c) / 3 for c in corners) >= 245 else "coloured"
                        shape = "square" if abs(width - height) <= 2 else ("portrait" if height > width else "landscape")
                except OSError:
                    fmt = "unreadable"
            products = users.get(name, [])
            writer.writerow([
                name if path.is_file() else f"{name} (MISSING)", fmt, width, height, shape,
                "" if not width else ("yes" if min(width, height) >= 600 else "small"), background,
                "; ".join(f"{p.sku} {p.name}" for p in products) or "(none)",
                "; ".join(sorted({p.publication_status for p in products})),
                "yes" if any(i.is_public for p in products for i in p.catalog_images.all()) else "no",
            ])
