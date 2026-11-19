from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from products.models import Product
from products.reference_catalog import retire_reference_catalog


class Command(BaseCommand):
    help = (
        "Withdraw every approved reference product in one step, keeping records, slugs "
        "and a decision per product. Dry run unless --apply is given."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--reviewer", help="Username recorded on each withdrawal decision.")

    def handle(self, *args, apply=False, reviewer=None, **options):
        approved = Product.objects.published().filter(catalog_origin=Product.Origin.REFERENCE)
        if not apply:
            self.stdout.write(f"{approved.count()} approved reference products would be withdrawn.")
            return
        if not reviewer:
            raise CommandError("--reviewer is required with --apply.")
        try:
            user = get_user_model().objects.get(username=reviewer, is_staff=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError("The reviewer must be an existing staff user.") from exc
        self.stdout.write(f"{retire_reference_catalog(user)} reference products withdrawn.")
