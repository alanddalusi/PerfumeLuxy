"""Verified data for the legacy reference catalog, loaded from a reviewed evidence file.

``products/verification/reference_evidence.csv`` holds one row per SKU, researched on the
official site of each brand. Only rows with ``status=verified`` and an https URL on the
brand's own domain are applied. Applying fills the official name, concentration, size and
gender, records the URL as evidence for each field, drops the unverified legacy
description and writes a unique meta description. It never publishes anything; publication
stays an explicit decision (``publish_reference_batch``).
"""

import csv
from pathlib import Path
from urllib.parse import urlsplit

from django.db import transaction
from django.utils.text import slugify

from .models import Gender, Product, PublicationDecision

EVIDENCE_FILE = Path(__file__).resolve().parent / "verification" / "reference_evidence.csv"
COLUMNS = ["sku", "status", "brand", "official_name", "concentration", "size", "gender",
           "source_url", "sizes_seen", "notes", "checked_on"]
STATUSES = {
    "verified": "datos comprobados en la web oficial",
    "ambiguous": "existe en varias concentraciones o versiones: hace falta elegir cuál es",
    "discontinued": "no figura en la web oficial (posiblemente descatalogado)",
    "not_found": "sin página oficial localizable",
    "duplicate": "repite otro SKU del catálogo",
    "not_applicable": "producto propio del proyecto anterior: no hay fabricante que lo verifique",
    "pending": "sin investigar todavía",
}

# Registrable names of each brand's official sites (any country TLD is accepted).
OFFICIAL_DOMAINS = {
    "Burberry": {"burberry"}, "Bvlgari": {"bulgari"}, "Calvin Klein": {"calvinklein"},
    "Carolina Herrera": {"carolinaherrera"}, "Cartier": {"cartier"}, "Chanel": {"chanel"},
    "Diesel": {"diesel"}, "Dior": {"dior"}, "Dkny": {"dkny"}, "Dolce & Gabbana": {"dolcegabbana"},
    "Emporio Armani": {"armanibeauty", "armani"}, "Giorgio Armani": {"armanibeauty", "armani"},
    "Estee Lauder": {"esteelauder"}, "Givenchy": {"givenchybeauty", "givenchy"}, "Gucci": {"gucci"},
    "Guerlain": {"guerlain"}, "Guess": {"guess"}, "Hugo Boss": {"hugoboss"},
    "Jean Paul Gaultier": {"jeanpaulgaultier"}, "Lacoste": {"lacoste"}, "Lancome": {"lancome", "lancome-usa"},
    "Montblanc": {"montblanc"}, "Paco Rabanne": {"rabanne", "pacorabanne"},
    "Roberto Cavalli": {"robertocavalli"}, "Tom Ford": {"tomfordbeauty", "tomford"},
    "Tommy Hilfiger": {"tommy"}, "Versace": {"versace"}, "Yves Saint Laurent": {"yslbeauty", "yslbeautyus", "ysl"},
    "Adidas": {"adidas"}, "Jaguar": {"jaguar"},
}
CONCENTRATION_LABELS = {code: label.split(" (")[0] for code, label in Product.CONCENTRATION_CHOICES}


def is_official(url, brand):
    """True for an https URL whose registrable name is one of the brand's official sites."""
    parts = urlsplit(url or "")
    if parts.scheme != "https" or not parts.hostname:
        return False
    labels = parts.hostname.lower().split(".")
    allowed = OFFICIAL_DOMAINS.get(brand, set())
    # name.tld, name.co.uk, www.name.com.br ...: the brand label followed only by a short suffix
    for index, label in enumerate(labels[:-1]):
        suffix = labels[index + 1:]
        if label in allowed and len(suffix) <= 2 and all(len(part) <= 3 for part in suffix):
            return True
    return False


def read_evidence(path=EVIDENCE_FILE):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def row_problems(row, product):
    """Reasons a verified row cannot be applied (empty list when it can)."""
    problems = []
    brand = product.brand.name if product.brand else ""
    if row["brand"] != brand:
        problems.append(f"brand {row['brand']!r} does not match the product ({brand!r})")
    if not row["official_name"]:
        problems.append("official_name is empty")
    if row["concentration"] not in CONCENTRATION_LABELS:
        problems.append(f"concentration {row['concentration']!r} is not a valid choice")
    if row["size"] not in dict(Product.SIZE_CHOICES):
        problems.append(f"size {row['size']!r} is not a valid choice")
    if row["gender"] not in {"M", "F", "U"}:
        problems.append("gender must be M, F or U")
    if not is_official(row["source_url"], brand):
        problems.append("source_url must be https on the brand's official site")
    return problems


def seo_slug(product, name, concentration):
    """brand-name-concentration, unique ("carolina-herrera-good-girl-eau-de-parfum")."""
    brand = product.brand.name if product.brand else ""
    base = slugify(f"{brand} {name} {CONCENTRATION_LABELS[concentration]}")[:240].rstrip("-") or "producto"
    slug, counter = base, 1
    while Product.objects.filter(slug=slug).exclude(pk=product.pk).exists():
        counter += 1
        slug = f"{base}-{counter}"
    return slug


def meta_description(brand, name, concentration, size, gender):
    audience = {"M": "para hombre", "F": "para mujer", "U": "unisex"}[gender]
    text = (f"{brand} {name} {CONCENTRATION_LABELS[concentration]} {size.replace('ml', ' ml')}, "
            f"perfume {audience}. Ficha informativa en Perfumería El Buen Olor: próximamente disponible.")
    return text[:160]


def apply_row(row, product, apply):
    """Returns the list of changed fields (empty when the product already matches)."""
    url = row["source_url"]
    gender = Gender.objects.filter(db_name=row["gender"]).first()
    values = {
        "name": row["official_name"][:254],
        "concentration": row["concentration"],
        "size": row["size"],
        "gender": gender,
        "description": "",   # legacy text has no verifiable source; it would also block approval
        "verification_sources": {"name": url, "brand": url, "concentration": url, "size": url, "gender": url},
        "meta_description": meta_description(row["brand"], row["official_name"], row["concentration"],
                                             row["size"], row["gender"]),
    }
    changed = [field for field, value in values.items() if getattr(product, field) != value]
    never_published = not PublicationDecision.objects.filter(product=product).exists()
    slug = seo_slug(product, values["name"], values["concentration"]) if never_published else product.slug
    if slug != product.slug:
        changed.append("slug")
    if changed and apply:
        values["slug"] = slug
        # queryset update: keeps publication_status untouched (Product.save would demote it)
        Product.objects.filter(pk=product.pk).update(**values)
    return changed


def apply_evidence(rows, apply=False):
    """Apply verified rows. Returns {sku: (outcome, detail)}; each row is its own transaction,
    so an interrupted run can simply be repeated."""
    results = {}
    products = {p.sku: p for p in Product.objects.filter(
        catalog_origin=Product.Origin.REFERENCE, sku__in=[r["sku"] for r in rows]).select_related("brand", "gender")}
    for row in rows:
        product = products.get(row["sku"])
        if product is None:
            results[row["sku"]] = ("error", "no reference product with this SKU")
            continue
        if row["status"] != "verified":
            results[row["sku"]] = ("skipped", row["status"] or "pending")
            continue
        problems = row_problems(row, product)
        if problems:
            results[row["sku"]] = ("error", "; ".join(problems))
            continue
        with transaction.atomic():
            changed = apply_row(row, product, apply)
        results[row["sku"]] = ("updated" if changed else "unchanged", ", ".join(changed))
    return results
