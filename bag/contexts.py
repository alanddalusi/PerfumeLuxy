from decimal import Decimal
from django.conf import settings
from products.models import Product
from products.models import Brand


BAG_SIZES = ("30ML", "50ML", "100ML", "onesize")


def get_price(product, key):
    price_dictionary = {
        "30ML": product.price / 3,
        "50ML": product.price,
        "100ML": product.price * 2,
        "onesize": product.price,
    }
    return price_dictionary[key]


def bag_contents(request):
    bag_items = []
    sub_total = 0
    product_count = 0
    bag = request.session.get("bag", {})
    brands = Brand.objects.all()

    item_ids = {
        key: int(key) for key in bag
        if key.isascii() and key.isdigit() and len(key) <= 19 and int(key) <= 2**63 - 1
    }
    catalog = Product.objects.published().select_related("brand").prefetch_related("catalog_images").in_bulk(item_ids.values())
    for item_id, item_data in bag.items():
        product = catalog.get(item_ids.get(item_id))
        if product is None or product.price is None:
            continue
        if isinstance(item_data, int):
            lines = {"onesize": item_data}
        elif isinstance(item_data, dict):
            lines = item_data.get("items_by_size", {})
        else:
            continue
        for size, quantity in lines.items():
            if size not in BAG_SIZES or not isinstance(quantity, int) or quantity <= 0:
                continue
            price = get_price(product, size)
            sub_total += quantity * price
            product_count += quantity
            bag_items.append({
                "item_id": item_id,
                "quantity": quantity,
                "product": product,
                "item_price": price,
                "item_total": quantity * price,
                "size": size,
            })

    if sub_total >= settings.DISCOUNT_THRESHOLD:
        discount = sub_total * Decimal(settings.DISCOUNT_PERCENTAGE / 100)
        discount_delta = 0
    else:
        discount = 0
        discount_delta = settings.DISCOUNT_THRESHOLD - sub_total

    pre_delivery = sub_total - discount
    delivery_price = Decimal(5.99)
    if pre_delivery < settings.FREE_DELIVERY_THRESHOLD:
        delivery = delivery_price
    else:
        delivery = 0

    total = pre_delivery + delivery

    context = {
        "bag_items": bag_items,
        "product_count": product_count,
        "meta_brands": brands,
        "sub_total": sub_total,
        "total": total,
        "discount": discount,
        "discount_delta": discount_delta,
        "delivery": delivery,
        "delivery_price": delivery_price,
        "pre_delivery": pre_delivery,
        "delivery_threshold": settings.FREE_DELIVERY_THRESHOLD,
        "discount_threshold": settings.DISCOUNT_THRESHOLD,
        "discount_percentage": settings.DISCOUNT_PERCENTAGE,
    }

    return context
