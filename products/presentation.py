"""Public storefront derivatives."""

from django.urls import reverse


def public_gallery(product):
    return [
        {
            "url": reverse("products:catalog_image", args=[image.pk, "web"]),
            "thumbnail": reverse("products:catalog_image", args=[image.pk, "thumb"]),
            "alt": image.alt_text or product.name,
        }
        for image in product.catalog_images.all()
        if image.is_public
    ]


def public_cover(product):
    gallery = public_gallery(product)
    return gallery[0]["thumbnail"] if gallery else ""
