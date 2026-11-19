from django.core.management.base import BaseCommand

from products.reference_catalog import import_reference_catalog


class Command(BaseCommand):
    help = (
        "Load the legacy reference catalog into this database as unpublished drafts. "
        "Dry run unless --apply is given. Existing SKUs are never modified."
    )
    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the drafts. Without it nothing changes.")

    def handle(self, *args, apply=False, **options):
        created, skipped = import_reference_catalog(apply=apply)
        verb = "added" if apply else "would be added"
        self.stdout.write(
            f"{created} reference drafts {verb}, {skipped} already present. "
            "Nothing is published; approve products one by one in the admin."
        )
