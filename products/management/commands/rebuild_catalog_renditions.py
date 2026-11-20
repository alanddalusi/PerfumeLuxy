from io import BytesIO
from uuid import uuid4

from django.core.management.base import BaseCommand
from PIL import Image

from products.models import CatalogImage
from products.publication import flatten, save_renditions


class Command(BaseCommand):
    help = (
        "Create the responsive AVIF/WebP renditions of APPROVED catalog images that lack them. "
        "Approval state, sources and rights are not changed. Dry run unless --apply."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--all", action="store_true", help="Also rebuild images that already have renditions.")

    def handle(self, *args, apply=False, all=False, **options):
        images = CatalogImage.objects.filter(approved_at__isnull=False, withdrawn_at__isnull=True).select_related("product")
        pending = [image for image in images if all or not image.renditions]
        self.stdout.write(f"{len(pending)} approved images {'will be' if apply else 'would be'} processed.")
        if not apply:
            return
        done = 0
        for image in pending:
            files = [image.product.image, *(size.image for size in image.product.sizes.all())]
            source = next((f for f in files if f and f.name == image.source_file), None)
            if source is None:
                self.stderr.write(f"image {image.pk}: source file {image.source_file} not found; skipped")
                continue
            with source.open("rb") as handle, Image.open(BytesIO(handle.read()), formats=("JPEG", "PNG", "WEBP")) as original:
                clean = flatten(original)
            image.renditions = save_renditions(image, clean, uuid4().hex)
            image.save(update_fields=["renditions"])
            done += 1
        self.stdout.write(f"{done} images now have renditions.")
