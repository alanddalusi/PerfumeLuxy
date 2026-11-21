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

    def handle(self, *args, **options):
        results = apply_evidence(read_evidence(options["file"]), apply=options["apply"])
        if not options["quiet"]:
            for sku, (outcome, detail) in results.items():
                if outcome in {"updated", "error"}:
                    self.stdout.write(f"{outcome:<9} {sku} {detail}")
        counts = Counter(outcome for outcome, _ in results.values())
        mode = "APPLIED" if options["apply"] else "DRY RUN (use --apply)"
        self.stdout.write(f"{mode}: " + ", ".join(f"{counts[k]} {k}" for k in ("updated", "unchanged", "skipped", "error")))
