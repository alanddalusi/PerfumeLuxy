"""Shared catalogue search, validation and query construction."""

from datetime import timedelta
from decimal import InvalidOperation
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q
from django.db.models.functions import Lower
from django.forms import DecimalField
from django.utils import timezone
from django.urls import reverse

from .models import Brand, Category, FragranceFamily, Gender, Product


SORT_FIELDS = {
    "name": Lower("name"),
    "price": "price",
    "rating": "rating",
    "created_at": "created_at",
}
PRICE_FILTER = DecimalField(required=False, min_value=0, max_digits=6, decimal_places=2)
CHOICE_FILTERS = {
    "concentration": Product.CONCENTRATION_CHOICES,
    "intensity": Product.INTENSITY_CHOICES,
    "duration": Product.DURATION_CHOICES,
    "occasion": Product.OCCASION_CHOICES,
    "season": Product.SEASON_CHOICES,
}


def normalize_search(term):
    return term.replace("\x00", "").strip()[:200]


def search_products(products, query):
    if not query:
        return products
    notes = Product.fragrance_notes.through.objects.filter(
        fragrancenote__name__icontains=query
    ).values("product_id")
    return products.filter(
        Q(name__icontains=query) | Q(description__icontains=query)
        | Q(brand__name__icontains=query) | Q(category__name__icontains=query)
        | Q(pk__in=notes)
    )


def catalog_listing(params):
    query = normalize_search(params.get("q", ""))
    products = search_products(
        Product.objects.published().select_related("brand", "category", "gender", "fragrance_family"), query
    ).annotate(
        catalog_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
        catalog_review_count=Count("reviews", filter=Q(reviews__is_approved=True)),
    )
    errors = []
    selected = {}
    taxonomies = {
        "brand": (Brand, "db_name"),
        "category": (Category, "db_name"),
        "gender": (Gender, "db_name"),
        "fragrance_family": (FragranceFamily, "name"),
    }
    labels = {
        "brand": "Marca", "category": "Categoría", "gender": "Género",
        "fragrance_family": "Familia olfativa", "concentration": "Concentración",
        "intensity": "Intensidad", "duration": "Duración", "occasion": "Ocasión",
        "season": "Temporada",
    }
    options = {}
    for field, (model, key) in taxonomies.items():
        entries = list(model.objects.order_by("name", "pk"))
        options[field] = [(getattr(entry, key), entry.name or getattr(entry, key)) for entry in entries]
        values = params.getlist(field)
        if not values:
            continue
        # Accept the old label/ID links while emitting stable taxonomy keys.
        lookup = {}
        for entry in entries:
            for alias in (entry.name, str(entry.pk)):
                if alias:
                    lookup.setdefault(alias.casefold(), entry)
        lookup.update((getattr(entry, key).casefold(), entry) for entry in entries)
        if field == "category":
            for alias, code in (("men", "m"), ("women", "f"), ("unisex", "u")):
                if alias in values:
                    products = products.filter(gender__db_name__iexact=code)
            values = [value for value in values if value not in {"men", "women", "unisex"}]
            if not values:
                continue
        matches = [lookup[value.casefold()] for value in values if value.casefold() in lookup]
        selected[field] = [getattr(entry, key) for entry in matches]
        products = products.filter(**{f"{field}_id__in": [entry.pk for entry in matches]})

    for field, choices in CHOICE_FILTERS.items():
        options[field] = choices
        values = params.getlist(field)
        if values:
            allowed = dict(choices)
            selected[field] = [value for value in values if value in allowed]
            products = products.filter(**{f"{field}__in": selected[field]})

    bounds = {}
    for name in ("price_from", "price_to"):
        try:
            bounds[name] = PRICE_FILTER.clean(params.get(name))
        except (InvalidOperation, ValidationError):
            bounds[name] = None
            errors.append("Introduce un precio válido.")
    minimum, maximum = bounds.values()
    if minimum is not None and maximum is not None and minimum > maximum:
        errors.append("El precio mínimo debe ser menor o igual que el máximo.")
    elif not errors:
        if minimum is not None:
            products = products.filter(price__gte=minimum)
        if maximum is not None:
            products = products.filter(price__lte=maximum)

    discount = params.get("has_discount", params.get("special_offers", "")).lower()
    if discount in {"true", "false"}:
        products = products.filter(has_discount=(discount == "true"))
    in_stock = params.get("in_stock", "").lower() == "true"
    if in_stock:
        products = products.filter(stock__gt=0)
    new_arrivals = params.get("new_arrivals", "").lower() == "true"
    if new_arrivals:
        products = products.filter(created_at__gte=timezone.now() - timedelta(days=30))

    sort = params.get("sort", "")
    if sort in SORT_FIELDS:
        field, direction = sort, params.get("direction", "asc")
    else:
        field, _, direction = sort.rpartition("_")
    if field in SORT_FIELDS and direction in {"asc", "desc"}:
        order_field = SORT_FIELDS[field]
        if isinstance(order_field, str):
            order_field = ("-" if direction == "desc" else "") + order_field
        else:
            order_field = order_field.desc() if direction == "desc" else order_field.asc()
        products = products.order_by(order_field, "pk")
        current_sorting = f"{field}_{direction}"
    else:
        products = products.order_by("-created_at", "-pk")
        current_sorting = ""

    return products, {
        "filter_options": [
            (field, labels[field], choices, selected.get(field, [])) for field, choices in options.items()
        ],
        "catalog_filtered": any(key not in {"page", "sort", "direction"} and value for key, value in params.items()),
        "search_term": query,
        "current_sorting": current_sorting,
        "price_from": params.get("price_from", ""),
        "price_to": params.get("price_to", ""),
        "in_stock_only": in_stock,
        "discount": discount,
        "new_arrivals": new_arrivals,
        "filter_errors": list(dict.fromkeys(errors)),
    }


def catalog_filter_url(**filters):
    return f"{reverse('products:products')}?{urlencode(filters)}"
