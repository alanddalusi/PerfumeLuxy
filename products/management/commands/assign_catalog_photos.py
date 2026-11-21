import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import CatalogImage, Product
from products.presentation import product_alt
from products.publication import decide_image

YES = {"yes", "y", "si", "sí", "s", "x", "1", "true", "ok"}


def read_rows(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text.split("\n", 1)[0], delimiters=",;\t")   # Excel ES saves with ;
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(text.splitlines(), dialect=dialect))
    if rows and not {"sku", "file"} <= set(rows[0]):
        raise CommandError("The CSV needs at least the columns sku and file (see catalog_photo_manifest).")
    return rows


class Command(BaseCommand):
    help = (
        "Assign legacy photos to their products from a reviewed manifest. Dry run unless --apply. "
        "Only rows with mapping_confirmed=yes are used. Rows become pending CatalogImage records "
        "(brand/name alt text, source, rights). With --approve, rows that also carry source and "
        "rights references are approved and their renditions generated. Product publication is never changed."
    )

    def add_arguments(self, parser):
        parser.add_argument("manifest")
        parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run).")
        parser.add_argument("--approve", action="store_true",
                            help="Approve rows that have source_reference and rights_reference.")
        parser.add_argument("--reviewer", help="Username recorded as approver (needs products.approve_catalogimage).")

    def handle(self, *args, **options):
        reviewer = None
        if options["approve"]:
            if not options["reviewer"]:
                raise CommandError("--approve needs --reviewer <username>.")
            reviewer = get_user_model().objects.filter(username=options["reviewer"], is_active=True).first()
            if reviewer is None or not reviewer.has_perm("products.approve_catalogimage"):
                raise CommandError("The reviewer must exist, be active and have products.approve_catalogimage.")
        apply = options["apply"]
        counts = {"created": 0, "updated": 0, "unchanged": 0, "approved": 0, "unconfirmed": 0,
                  "no_rights": 0, "errors": 0, "hidden_product": 0}
        for line, row in enumerate(read_rows(options["manifest"]), start=2):
            row = {k: (v or "").strip() for k, v in row.items() if k}
            label = f"line {line} {row.get('sku', '')}"
            if row.get("mapping_confirmed", "").lower() not in YES:
                counts["unconfirmed"] += 1
                continue
            try:
                with transaction.atomic():
                    outcome = self.assign(row, apply, reviewer)
            except (ValidationError, CommandError) as exc:
                counts["errors"] += 1
                message = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                self.stdout.write(f"ERROR {label}: {message}")
                continue
            action, approved, rights, product = outcome
            counts[action] += 1
            counts["approved"] += approved
            counts["no_rights"] += not rights
            counts["hidden_product"] += product.publication_status != Product.Publication.APPROVED
            self.stdout.write(f"{label}: {action}{' + approved' if approved else ''}"
                              f"{'' if rights else ' (pending: no source/rights reference)'}")
        mode = "APPLIED" if apply else "DRY RUN (nothing written; use --apply)"
        self.stdout.write(
            f"{mode}: {counts['created']} created, {counts['updated']} updated, {counts['unchanged']} unchanged, "
            f"{counts['approved']} approved{'' if apply else ' (would be)'}, {counts['no_rights']} without rights, "
            f"{counts['unconfirmed']} unconfirmed rows skipped, {counts['errors']} errors. "
            f"{counts['hidden_product']} assigned photos belong to unpublished products (not visible yet)."
        )

    def assign(self, row, apply, reviewer):
        product = (Product.objects.select_related("brand").prefetch_related("sizes")
                   .filter(sku=row["sku"]).first() if row.get("sku") else None)
        if product is None:
            raise CommandError("no product with that SKU")
        files = [product.image, *(size.image for size in product.sizes.all())]
        source = next((f for f in files if f and f.name == row["file"]), None)
        if source is None:
            raise CommandError(f"{row['file']!r} is not the cover or a variant photo of {product.sku}")
        if not source.storage.exists(source.name):
            raise CommandError(f"{row['file']!r} does not exist in media storage")
        values = {
            "alt_text": (row.get("alt_text") or product_alt(product))[:200],
            "source_reference": row.get("source_reference", "")[:500],
            "rights_reference": row.get("rights_reference", "")[:500],
        }
        rights = bool(values["source_reference"] and values["rights_reference"])
        record = CatalogImage.objects.filter(product=product, source_file=source.name).order_by("-pk").first()
        if record is not None and record.is_public:
            # Approved photos keep their recorded provenance; only the alt text can be refined.
            changed = record.alt_text != values["alt_text"]
            if changed and apply:
                CatalogImage.objects.filter(pk=record.pk).update(alt_text=values["alt_text"])
            return ("updated" if changed else "unchanged"), False, True, product
        if record is None or record.withdrawn_at:
            # A withdrawn photo is never revived in place (it still has its approval and files):
            # assigning it again opens a new pending record that must be approved afresh.
            action = "created"
            record = CatalogImage(product=product, source_file=source.name,
                                  display_order=0 if source.name == product.image.name else 1)
        else:
            action = "updated" if any(getattr(record, k) != v for k, v in values.items()) else "unchanged"
        approve = bool(reviewer and rights)
        if apply:
            for key, value in values.items():
                setattr(record, key, value)
            record.save()
            if approve:
                decide_image(record, True, reviewer)
        return action, approve, rights, product
