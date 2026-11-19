"""Legacy reference catalog: import as drafts, report review gaps, retire in one step.

The 265 legacy fixture records are development reference material. They enter the
database as drafts tagged ``catalog_origin=reference``; publication still needs an
individual decision in the admin, and reference products are never sellable.
"""

import json
from pathlib import Path

from django.db import transaction

from .models import Brand, Category, Gender, Product


FIXTURES = Path(__file__).resolve().parent / "fixtures"
REFERENCE_REQUIRED_EVIDENCE = ("name", "brand", "concentration", "size")


def records(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def import_reference_catalog(apply=True):
    """Create missing legacy products as unpublished reference drafts.

    Existing SKUs are never modified. Returns ``(created, skipped)``.
    """
    rows = sorted(records("products"), key=lambda row: row["pk"])
    existing = set(Product.objects.filter(sku__in=[row["fields"]["sku"] for row in rows]).values_list("sku", flat=True))
    if not apply:
        return len(rows) - len(existing), len(existing)

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
        for row in rows:
            fields = row["fields"].copy()
            sku = fields.pop("sku")
            if sku in existing:
                continue
            for field, entries in relations.items():
                original_id = fields[field]
                fields[field] = entries[original_id] if original_id is not None else None
            for field in ("has_sizes", "has_subscription", "has_discount"):
                fields[field] = Product._meta.get_field(field).to_python(fields[field])
            Product.objects.create(
                sku=sku, stock=0, catalog_origin=Product.Origin.REFERENCE,
                publication_status=Product.Publication.DRAFT, **fields,
            )
            created += 1
    return created, len(existing)


def missing_reference_data(product):
    """Fields a reviewer still has to confirm before a reference product can be approved."""
    sources = product.verification_sources if isinstance(product.verification_sources, dict) else {}
    missing = []
    if not product.concentration:
        missing.append("concentration (valor)")
    if not (product.size or product.sizes.exists()):
        missing.append("size (valor)")
    for key in REFERENCE_REQUIRED_EVIDENCE:
        value = sources.get(key)
        if not isinstance(value, str) or not value.strip():
            missing.append(f"{key} (referencia)")
    return missing


def review_rows(queryset=None):
    queryset = queryset if queryset is not None else Product.objects.filter(catalog_origin=Product.Origin.REFERENCE)
    for product in queryset.select_related("brand").prefetch_related("sizes", "catalog_images").order_by("brand__name", "name"):
        yield {
            "sku": product.sku or "",
            "brand": product.brand.name if product.brand and product.brand.name else "",
            "name": product.name,
            "status": product.publication_status,
            "concentration": product.concentration or "",
            "size": product.size or ", ".join(f"{size.size_ml} ml" for size in product.sizes.all()),
            "approved_images": sum(1 for image in product.catalog_images.all() if image.is_public),
            "missing": "; ".join(missing_reference_data(product)),
        }


def retire_reference_catalog(reviewer):
    """Withdraw every approved reference product, recording one decision per product."""
    from .publication import decide_product

    retired = 0
    for product in Product.objects.published().filter(catalog_origin=Product.Origin.REFERENCE):
        decide_product(product, Product.Publication.WITHDRAWN, reviewer)
        retired += 1
    return retired
