from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from products.reference_catalog import import_reference_catalog


class Command(BaseCommand):
    help = "Import the unverified legacy catalog into the offline review database."
    requires_migrations_checks = True

    def handle(self, *args, **options):
        if not getattr(settings, "CATALOG_REVIEW", False):
            raise CommandError("Use --settings=eau_royal.catalog_review_settings.")
        created, skipped = import_reference_catalog()
        self.stdout.write(f"{created} added, {skipped} already present. Source records are unverified.")
