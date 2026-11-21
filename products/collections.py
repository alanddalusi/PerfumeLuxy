"""Indexable collection pages (brand and gender) built only from published products.

A collection is indexable and listed in the sitemap when it has at least MIN_INDEXABLE published
products; smaller ones still work for visitors but carry ``noindex`` (no thin pages in Google),
and a brand with no published product does not exist (404). Text is generated from the verified
data of the products it lists, so each page is different.
"""

from django.db.models import Count, Q
from django.urls import reverse
from django.utils.text import slugify

from .models import Brand, Product
from .naming import product_full_name
from .reference_evidence import CONCENTRATION_LABELS

MIN_INDEXABLE = 3
GENDERS = {"mujer": ("F", "para mujer"), "hombre": ("M", "para hombre"), "unisex": ("U", "unisex")}


def brand_slug(brand):
    return slugify(brand.name) or brand.db_name


def brand_url(brand):
    return reverse("products:brand_collection", args=[brand_slug(brand)])


def published_brands():
    """[(brand, published_count)] for brands with at least one published product."""
    brands = Brand.objects.annotate(
        published=Count("product", filter=Q(product__publication_status=Product.Publication.APPROVED))
    ).filter(published__gt=0).order_by("name")
    return [(brand, brand.published) for brand in brands]


def find_brand(slug):
    return next((brand for brand, _ in published_brands() if brand_slug(brand) == slug), None)


def _join(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def describe(products, subject):
    """Intro and meta description from the listed products' verified data."""
    concentrations = sorted({CONCENTRATION_LABELS[p.concentration] for p in products if p.concentration})
    names = [product_full_name(p) for p in products][:6]
    count = len(products)
    intro = (
        f"{count} perfume{'s' if count != 1 else ''} {subject} con ficha verificada en la web oficial de cada marca: "
        f"concentración, formato y notas olfativas."
        + (f" Formatos: {_join(concentrations)}." if concentrations else "")
        + (f" Incluye {_join(names)}{' y más' if count > len(names) else ''}." if names else "")
        + " Próximamente disponibles en Perfumería El Buen Olor."
    )
    meta = (f"Perfumes {subject}: {_join(names[:3])}. Fichas verificadas con concentración y formato oficiales."
            if names else f"Perfumes {subject} en Perfumería El Buen Olor.")
    return intro, meta[:160]


def collection_products(**filters):
    return list(Product.objects.published().filter(**filters)
                .select_related("brand", "fragrance_family").prefetch_related("catalog_images").order_by("name"))


def sitemap_locations():
    """URLs of the indexable collections."""
    urls = [brand_url(brand) for brand, count in published_brands() if count >= MIN_INDEXABLE]
    for slug, (code, _) in GENDERS.items():
        if Product.objects.published().filter(gender__db_name=code).count() >= MIN_INDEXABLE:
            urls.append(reverse("products:gender_collection", args=[slug]))
    return urls
