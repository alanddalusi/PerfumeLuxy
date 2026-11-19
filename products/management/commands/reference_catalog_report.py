
from django.core.management.base import BaseCommand
from django.db.models import Count

from products.models import Product
from products.reference_catalog import review_rows


class Command(BaseCommand):
    help = "Summarise publication status and list what each reference product still needs."

    def add_arguments(self, parser):
        parser.add_argument("--csv", action="store_true", help="Write one CSV row per reference product.")
        parser.add_argument("--pending", action="store_true", help="Only products that are not approved.")

    def handle(self, *args, csv=False, pending=False, **options):
        queryset = Product.objects.filter(catalog_origin=Product.Origin.REFERENCE)
        if pending:
            queryset = queryset.exclude(publication_status=Product.Publication.APPROVED)
        if csv:
            return self.write_csv(queryset)
        totals = Product.objects.values_list("catalog_origin", "publication_status").annotate(total=Count("id"))
        for origin, status, total in sorted(totals):
            self.stdout.write(f"{origin:<10} {status:<10} {total}")
        ready = sum(1 for row in review_rows(queryset) if not row["missing"])
        self.stdout.write(f"Reference products with complete data and evidence: {ready}")

    def write_csv(self, queryset):
        import csv as csv_module

        writer = csv_module.DictWriter(self.stdout, fieldnames=[
            "sku", "brand", "name", "status", "concentration", "size", "approved_images", "missing",
        ])
        writer.writeheader()
        for row in review_rows(queryset):
            writer.writerow(row)
