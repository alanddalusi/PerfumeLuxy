from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from products.models import Product
from products.publication import decide_product
from products.reference_catalog import missing_reference_data


class Command(BaseCommand):
    help = (
        "Approve reference drafts whose data and evidence are complete (informative pages, never "
        "sellable). Dry run unless --apply. Optionally limited to --sku values. A product with the "
        "same brand, name, concentration and size as one already selected or published is skipped."
    )

    def add_arguments(self, parser):
        parser.add_argument("--reviewer", required=True, help="Username with products.change_product.")
        parser.add_argument("--sku", nargs="*", help="Only these SKUs.")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        reviewer = get_user_model().objects.filter(username=options["reviewer"], is_active=True).first()
        if reviewer is None or not reviewer.has_perm("products.change_product"):
            raise CommandError("The reviewer must exist, be active and have products.change_product.")
        queryset = (Product.objects.filter(catalog_origin=Product.Origin.REFERENCE)
                    .exclude(publication_status=Product.Publication.APPROVED)
                    .select_related("brand").prefetch_related("sizes").order_by("pk"))
        if options["sku"]:
            queryset = queryset.filter(sku__in=options["sku"])
        seen = {(p.brand_id, p.name.lower(), p.concentration, p.size)
                for p in Product.objects.published().filter(catalog_origin=Product.Origin.REFERENCE)}
        done = skipped = 0
        verb = "published" if options["apply"] else "ready"
        for product in queryset:
            if missing_reference_data(product):
                continue
            key = (product.brand_id, product.name.lower(), product.concentration, product.size)
            if key in seen:
                skipped += 1
                self.stdout.write(f"duplicate {product.sku} {product.brand.name} {product.name}")
                continue
            seen.add(key)
            if options["apply"]:
                try:
                    decide_product(product, Product.Publication.APPROVED, reviewer)
                except ValidationError as exc:
                    self.stdout.write(f"error     {product.sku}: {'; '.join(exc.messages)}")
                    continue
            done += 1
            self.stdout.write(f"{verb:<9} {product.sku} {product.brand.name} {product.name}")
        mode = "APPLIED" if options["apply"] else "DRY RUN (use --apply)"
        self.stdout.write(f"{mode}: {done} {verb}, {skipped} duplicates skipped.")
