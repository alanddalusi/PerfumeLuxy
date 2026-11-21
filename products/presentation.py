"""Public storefront derivatives (only approved images of published products reach here)."""

from django.urls import reverse

FORMAT_ORDER = ("avif", "webp")   # <source> order: best compression first, WebP as fallback


def _rendition_url(image, entry, slug=""):
    # Descriptive file name for image search ("/products/image/7/dior-sauvage-640.avif"); the
    # slug is cosmetic, the id decides what is served.
    if slug:
        return reverse("products:catalog_rendition_named", args=[image.pk, slug, entry["box"], entry["fmt"]])
    return reverse("products:catalog_rendition", args=[image.pk, entry["box"], entry["fmt"]])


def product_alt(product):
    """Descriptive alt text: brand, name, concentration and size ("Frasco de Dior Sauvage
    Eau de Parfum 100 ml"). Used when the image has no alt of its own."""
    parts = [product.brand.name if product.brand_id and product.brand else "", product.name]
    if product.concentration:
        label = dict(product.CONCENTRATION_CHOICES).get(product.concentration, "")
        parts.append(label.split(" (")[0])
    if product.size:
        parts.append(product.size.replace("ml", " ml"))
    text = " ".join(part.strip() for part in parts if part and part.strip())
    return f"Frasco de {text}"[:200] if text else ""


def picture_data(image, alt, slug=""):
    """Everything a <picture> needs: per-format srcset, fallback src, true pixel size."""
    entries = sorted(image.renditions or [], key=lambda r: (r["box"], r["fmt"]))
    if not entries:   # approved before renditions existed: single WebP pair
        return {
            "alt": alt, "sources": [], "src": reverse("products:catalog_image", args=[image.pk, "web"]),
            "srcset": "", "width": None, "height": None,
            "thumb": reverse("products:catalog_image", args=[image.pk, "thumb"]), "thumb_width": None, "thumb_height": None,
        }
    sources = []
    for fmt in FORMAT_ORDER:
        same = [r for r in entries if r["fmt"] == fmt]
        if same:
            sources.append({
                "type": f"image/{fmt}",
                "srcset": ", ".join(f"{_rendition_url(image, r, slug)} {r['w']}w" for r in same),
            })
    webp = [r for r in entries if r["fmt"] == "webp"] or entries
    largest, smallest = webp[-1], webp[0]
    return {
        "alt": alt,
        "sources": sources,
        "srcset": next((s["srcset"] for s in sources if s["type"] == "image/webp"), ""),
        "src": _rendition_url(image, largest, slug),
        "width": largest["w"], "height": largest["h"],   # real pixels: also the CSS upscaling cap
        "thumb": _rendition_url(image, smallest, slug), "thumb_width": smallest["w"], "thumb_height": smallest["h"],
    }


def public_pictures(product):
    alt_default = product_alt(product)
    return [picture_data(image, image.alt_text or alt_default, product.slug)
            for image in product.catalog_images.all() if image.is_public]


def public_picture(product):
    pictures = public_pictures(product)
    return pictures[0] if pictures else None


def public_gallery(product):
    """Gallery entries for the product page: picture data plus the URLs the switcher uses."""
    return [{**picture, "url": picture["src"], "thumbnail": picture["thumb"]} for picture in public_pictures(product)]


def public_cover(product):
    """Single URL of the main image (structured data, size API)."""
    picture = public_picture(product)
    return picture["src"] if picture else ""


def seo_images(product):
    """Largest public WebP of every approved image, for Open Graph, JSON-LD and the image
    sitemap: [{"url": relative URL, "width", "height", "alt"}]. Empty when nothing is public."""
    return [{"url": p["src"], "width": p["width"], "height": p["height"], "alt": p["alt"]}
            for p in public_pictures(product)]
