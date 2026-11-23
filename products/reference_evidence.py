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

from .models import FragranceFamily, FragranceNote, Gender, Product, PublicationDecision
from .naming import full_name

EVIDENCE_FILE = Path(__file__).resolve().parent / "verification" / "reference_evidence.csv"
COLUMNS = ["sku", "status", "brand", "official_name", "concentration", "size", "gender",
           "source_url", "sizes_seen", "notes", "checked_on", "description_es", "description_source",
           "field_sources", "notes_pyramid", "family"]
FAMILY_DESCRIPTIONS = {'Floral': 'Las fragancias florales giran en torno a flores como la rosa, el jazmín, el nardo o la peonía. Es la familia más amplia: va de los florales frescos y luminosos a los más empolvados o sensuales.', 'Amaderada': 'Las fragancias amaderadas se construyen sobre maderas como el cedro, el sándalo, el vetiver o el guayaco. Suelen ser cálidas y secas, y a menudo se combinan con notas aromáticas o especiadas.', 'Ambarada': 'La familia ambarada, antes llamada oriental, reúne fragancias cálidas y envolventes, con notas como la vainilla, las resinas, el haba tonka o las especias.', 'Aromática': 'Las fragancias aromáticas se basan en hierbas como la lavanda, la salvia, el romero o la menta, a menudo acompañadas de cítricos y maderas. Son muy habituales en la perfumería masculina.', 'Fougère': 'Fougère, «helecho» en francés, es una estructura clásica que combina lavanda, notas herbales y un fondo de musgo o haba tonka. Muchas fragancias masculinas modernas parten de ella.', 'Cítrica': 'Las fragancias cítricas destacan notas de bergamota, limón, mandarina o pomelo. Son frescas y ligeras, y muy apreciadas en verano.', 'Chipre': 'La estructura chipre contrasta notas frescas de salida con un fondo de musgo y pachulí.', 'Gourmand': 'Las fragancias gourmand evocan notas comestibles como la vainilla, el praliné, el caramelo o el cacao.', 'Afrutada': 'Las fragancias afrutadas destacan frutas como la frambuesa, la pera o el melocotón.'}
NOTE_LEVELS = ("top", "heart", "base")
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
    "Estée Lauder": {"esteelauder"}, "Givenchy": {"givenchybeauty", "givenchy"}, "Gucci": {"gucci"},
    "Guerlain": {"guerlain"}, "Guess": {"guess"}, "Hugo Boss": {"hugoboss"},
    "Jean Paul Gaultier": {"jeanpaulgaultier"}, "Lacoste": {"lacoste"}, "Lancôme": {"lancome", "lancome-usa"},
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


def field_sources(row):
    """Optional per-field official sources: "gender=https://...|size=https://..."."""
    out = {}
    for part in filter(None, (row.get("field_sources") or "").split("|")):
        key, _, url = part.partition("=")
        out[key.strip()] = url.strip()
    return out


def note_pyramid(row):
    """"top=Bergamota,Pera;heart=Rosa;base=Vainilla" -> [("top", "Bergamota"), ...]."""
    pairs = []
    for part in filter(None, (row.get("notes_pyramid") or "").split(";")):
        level, _, names = part.partition("=")
        for name in filter(None, (n.strip() for n in names.split(","))):
            pairs.append((level.strip(), name))
    return pairs


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
    for key, url in field_sources(row).items():
        if key not in {"name", "brand", "concentration", "size", "gender"} or not is_official(url, brand):
            problems.append(f"field_sources {key} must be a known field with an official https URL")
    if row.get("description_es") and not is_official(row.get("description_source", ""), brand):
        problems.append("description_source must be https on the brand's official site")
    pyramid = note_pyramid(row)
    if pyramid and (any(level not in NOTE_LEVELS for level, _ in pyramid)
                    or not is_official(row.get("description_source", ""), brand)):
        problems.append("notes_pyramid needs top/heart/base levels and an official description_source")
    if row.get("family") and (row["family"] not in FAMILY_DESCRIPTIONS
                              or not is_official(row.get("description_source", ""), brand)):
        problems.append("family must be a known family classified on the official description_source")
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
    text = (f"{full_name(brand, name)} {CONCENTRATION_LABELS[concentration]} {size.replace('ml', ' ml')}, "
            f"perfume {audience}. Ficha informativa en Perfumería El Buen Olor: próximamente disponible.")
    return text[:160]


def apply_row(row, product, apply):
    """Returns the list of changed fields (empty when the product already matches)."""
    url = row["source_url"]
    gender = Gender.objects.filter(db_name=row["gender"]).first()
    description = row.get("description_es", "")
    sources = {"name": url, "brand": url, "concentration": url, "size": url, "gender": url}
    sources.update(field_sources(row))
    if description:
        sources["description"] = row["description_source"]
    values = {
        "name": row["official_name"][:254],
        "concentration": row["concentration"],
        "size": row["size"],
        "gender": gender,
        # Our own Spanish text written from the notes on the official page (sourced), or nothing:
        # the legacy English text has no verifiable source.
        "description": description,
        "verification_sources": sources,
        "meta_description": meta_description(row["brand"], row["official_name"], row["concentration"],
                                             row["size"], row["gender"]),
    }
    pyramid = note_pyramid(row)
    if pyramid:
        sources["notes"] = row["description_source"]   # the same official page lists the notes
    family = None
    if row.get("family"):
        sources["family"] = row["description_source"]  # classification published on that page
        family = FragranceFamily.objects.filter(name=row["family"]).first()
        if family is None and apply:
            family = FragranceFamily.objects.create(name=row["family"], description=FAMILY_DESCRIPTIONS[row["family"]])
    values_family = family.pk if family else None
    changed = [field for field, value in values.items() if getattr(product, field) != value]
    if product.fragrance_family_id != values_family and (row.get("family") or product.fragrance_family_id):
        changed.append("family")
    current_notes = {(n.note_type, n.name) for n in product.fragrance_notes.all()}
    if current_notes != set(pyramid):
        changed.append("notes")
    never_published = not PublicationDecision.objects.filter(product=product).exists()
    slug = seo_slug(product, values["name"], values["concentration"]) if never_published else product.slug
    if slug != product.slug:
        changed.append("slug")
    if changed and apply:
        values["slug"] = slug
        values["fragrance_family_id"] = values_family
        # queryset update: keeps publication_status untouched (Product.save would demote it)
        Product.objects.filter(pk=product.pk).update(**values)
        if "notes" in changed:
            # M2M only: no Product.save(), so the publication status is untouched
            product.fragrance_notes.set([FragranceNote.objects.get_or_create(name=name, note_type=level)[0]
                                         for level, name in pyramid])
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
