"""Public storefront derivatives (only approved images of published products reach here)."""

from django.urls import reverse

FORMAT_ORDER = ("avif", "webp")   # <source> order: best compression first, WebP as fallback


def _rendition_url(image, entry):
    return reverse("products:catalog_rendition", args=[image.pk, entry["box"], entry["fmt"]])


def picture_data(image, alt):
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
                "srcset": ", ".join(f"{_rendition_url(image, r)} {r['w']}w" for r in same),
            })
    webp = [r for r in entries if r["fmt"] == "webp"] or entries
    largest, smallest = webp[-1], webp[0]
    return {
        "alt": alt,
        "sources": sources,
        "srcset": next((s["srcset"] for s in sources if s["type"] == "image/webp"), ""),
        "src": _rendition_url(image, largest),
        "width": largest["w"], "height": largest["h"],   # real pixels: also the CSS upscaling cap
        "thumb": _rendition_url(image, smallest), "thumb_width": smallest["w"], "thumb_height": smallest["h"],
    }


def public_pictures(product):
    alt_default = " ".join(part for part in ((product.brand.name if product.brand_id and product.brand else ""), product.name) if part)
    return [picture_data(image, image.alt_text or alt_default) for image in product.catalog_images.all() if image.is_public]


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
