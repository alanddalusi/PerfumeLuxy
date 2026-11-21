from collections import Counter

from django.core.management.base import BaseCommand

from products.reference_evidence import EVIDENCE_FILE, apply_evidence, read_evidence


class Command(BaseCommand):
    help = (
        "Fill reference drafts from the verified evidence file (official name, concentration, size, "
        "gender, source URLs, meta description). Dry run unless --apply. Repeatable: rows already "
        "applied are reported as unchanged. Never changes publication status."
    )

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(EVIDENCE_FILE))
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--quiet", action="store_true", help="Only the summary line.")
        parser.add_argument("--sku", nargs="*", help="Only these SKUs (others are left untouched).")
        parser.add_argument("--published-only", action="store_true",
                            help="Only products already published (refresh their verified data, e.g. names or titles).")

    def handle(self, *args, **options):
        rows = read_evidence(options["file"])
        if options["sku"]:
            rows = [row for row in rows if row["sku"] in set(options["sku"])]
        if options["published_only"]:
            from products.models import Product
            published = set(Product.objects.published().values_list("sku", flat=True))
            rows = [row for row in rows if row["sku"] in published]
        results = apply_evidence(rows, apply=options["apply"])
        if not options["quiet"]:
            for sku, (outcome, detail) in results.items():
                if outcome in {"updated", "error"}:
                    self.stdout.write(f"{outcome:<9} {sku} {detail}")
        counts = Counter(outcome for outcome, _ in results.values())
        mode = "APPLIED" if options["apply"] else "DRY RUN (use --apply)"
        self.stdout.write(f"{mode}: " + ", ".join(f"{counts[k]} {k}" for k in ("updated", "unchanged", "skipped", "error")))
