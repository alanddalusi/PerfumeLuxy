"""Display names: brand + product name without repeating the brand ("Hugo Boss" + "Boss Bottled
Night" -> "Boss Bottled Night", not "Hugo Boss Boss Bottled Night")."""


def full_name(brand_name, name):
    brand_name, name = (brand_name or "").strip(), (name or "").strip()
    if not brand_name or not name:
        return brand_name or name
    first_word = name.split()[0].lower()
    if first_word in {word.lower() for word in brand_name.split()}:
        return name
    return f"{brand_name} {name}"


def product_full_name(product):
    return full_name(product.brand.name if product.brand_id and product.brand else "", product.name)
