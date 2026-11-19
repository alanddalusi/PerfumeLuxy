import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import Brand, Category, Gender, Product


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def records(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class Command(BaseCommand):
    help = "Import the unverified legacy catalog into the offline review database."
    requires_migrations_checks = True

    def handle(self, *args, **options):
        if not getattr(settings, "CATALOG_REVIEW", False):
            raise CommandError("Use --settings=eau_royal.catalog_review_settings.")

        with transaction.atomic():
            relations = {}
            for field, model, fixture in (
                ("brand", Brand, "brands"),
                ("category", Category, "categories"),
                ("gender", Gender, "gender"),
            ):
                relations[field] = {}
                for row in records(fixture):
                    values = row["fields"].copy()
                    code = values.pop("db_name")
                    entry, _ = model.objects.get_or_create(db_name=code, defaults=values)
                    relations[field][row["pk"]] = entry

            created = 0
            skipped = 0
            for row in sorted(records("products"), key=lambda row: row["pk"]):
                fields = row["fields"].copy()
                sku = fields.pop("sku")
                if Product.objects.filter(sku=sku).exists():
                    skipped += 1
                    continue
                for field, entries in relations.items():
                    original_id = fields[field]
                    fields[field] = entries[original_id] if original_id is not None else None
                for field in ("has_sizes", "has_subscription", "has_discount"):
                    fields[field] = Product._meta.get_field(field).to_python(fields[field])
                Product.objects.create(sku=sku, stock=0, **fields)
                created += 1

        self.stdout.write(
            f"{created} added, {skipped} already present. Source records are unverified."
        )
