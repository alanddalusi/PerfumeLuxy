from io import BytesIO
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps

from .models import CatalogImage, Product, PublicationDecision


@transaction.atomic
def decide_product(product, status, reviewer):
    product = Product.objects.select_for_update().get(pk=product.pk)
    evidence = product.verification_sources
    if status == Product.Publication.APPROVED:
        if not product.name.strip() or not product.brand or not product.brand.name:
            raise ValidationError("Hace falta un nombre y una marca identificada.")
        required = ["name", "brand"]
        if product.is_reference:
            if not product.concentration or not (product.size or product.sizes.exists()):
                raise ValidationError(
                    "Las fichas de referencia necesitan concentración y formato comprobados."
                )
        for key, present in (
            ("concentration", product.concentration),
            ("size", product.size or product.sizes.exists()),
            ("notes", product.fragrance_notes.exists()),
            ("family", product.fragrance_family_id),
            ("description", product.description.strip()),
        ):
            if present:
                required.append(key)
        sources = evidence if isinstance(evidence, dict) else {}
        missing = [key for key in required if not isinstance(sources.get(key), str) or not sources[key].strip()]
        if missing:
            raise ValidationError("Incluye una referencia verificable para: " + ", ".join(missing))
    elif status != Product.Publication.WITHDRAWN:
        raise ValidationError("Decisión de publicación no válida.")
    if product.publication_status != status:
        Product.objects.filter(pk=product.pk).update(publication_status=status)
        PublicationDecision.objects.create(product=product, reviewer=reviewer, status=status, evidence=evidence)


# Square boxes for responsive derivatives. Each rendition fits inside box x box keeping its
# proportions (no cropping, no padding baked in); the frame and background are CSS.
RENDITION_BOXES = (320, 640, 960, 1280)
MAX_PIXELS = 50_000_000   # decompression-bomb guard; the largest legacy photo has 26 MP
RENDITION_FORMATS = {
    "avif": {"format": "AVIF", "quality": 55},
    "webp": {"format": "WEBP", "quality": 80, "method": 6},
}


def webp_variant(image, dimensions):
    variant = image.copy()
    variant.thumbnail(dimensions, Image.Resampling.LANCZOS)
    output = BytesIO()
    variant.save(output, format="WEBP", quality=83, method=4)
    return ContentFile(output.getvalue())


def rendition_boxes(width, height):
    """Boxes to generate for an original: never larger than its long side (no upscaling)."""
    longest = max(width, height)
    top = min(longest, RENDITION_BOXES[-1])          # the original size is the last step, capped
    return [box for box in RENDITION_BOXES if box < top] + [top]


def build_renditions(clean, stem):
    """Encode every box/format. Returns [(metadata, ContentFile)] without saving anything."""
    out = []
    for box in rendition_boxes(*clean.size):
        variant = clean.copy()
        variant.thumbnail((box, box), Image.Resampling.LANCZOS)
        for fmt, options in RENDITION_FORMATS.items():
            buffer = BytesIO()
            variant.save(buffer, **options)
            out.append(({"box": box, "w": variant.width, "h": variant.height, "fmt": fmt,
                         "name": f"r/{stem}-{box}.{fmt}"}, ContentFile(buffer.getvalue())))
    return out


def flatten(photo):
    """RGB without metadata; transparent areas become white (the CSS blends white away)."""
    photo = ImageOps.exif_transpose(photo)
    if photo.mode in ("RGBA", "LA") or (photo.mode == "P" and "transparency" in photo.info):
        photo = photo.convert("RGBA")
        base = Image.new("RGB", photo.size, (255, 255, 255))
        base.paste(photo, mask=photo.getchannel("A"))
        return base
    photo = photo.convert("RGB")
    clean = Image.new("RGB", photo.size)
    clean.paste(photo)
    return clean


def save_renditions(image_record, clean, stem):
    storage = image_record.asset.storage
    saved = []
    for meta, content in build_renditions(clean, stem):
        meta["name"] = storage.save(meta["name"], content)
        saved.append(meta)
    return saved


@transaction.atomic
def decide_image(image_record, approve, reviewer):
    image_record = CatalogImage.objects.select_for_update().select_related("product").get(pk=image_record.pk)
    if not approve:
        CatalogImage.objects.filter(pk=image_record.pk, withdrawn_at__isnull=True).update(withdrawn_at=timezone.now())
        return
    if image_record.is_public:
        return
    if not image_record.source_reference.strip() or not image_record.rights_reference.strip():
        raise ValidationError("Indica el origen y la referencia del permiso de publicación.")
    files = [image_record.product.image, *(size.image for size in image_record.product.sizes.all())]
    source = next((file for file in files if file and file.name == image_record.source_file), None)
    if source is None:
        raise ValidationError("El archivo debe pertenecer a la portada o a una variante de este producto.")
    limit = 12 * 1024 * 1024
    try:
        with source.open("rb") as file:
            data = file.read(limit + 1)
        if len(data) > limit:
            raise ValidationError("El archivo supera 12 MB.")
        with Image.open(BytesIO(data), formats=("JPEG", "PNG", "WEBP")) as original:
            if original.width * original.height > MAX_PIXELS or getattr(original, "is_animated", False):
                raise ValidationError("La imagen debe ser fija y tener hasta 50 megapíxeles.")
            # JPEG can be decoded already reduced (1/2, 1/4, 1/8) when it is far larger than the
            # biggest rendition: less memory and time, same result after the final resize.
            original.draft("RGB", (RENDITION_BOXES[-1], RENDITION_BOXES[-1]))
            clean = flatten(original)
            asset = webp_variant(clean, (1280, 1280))
            thumbnail = webp_variant(clean, (480, 480))
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("No se pudo abrir una imagen JPEG, PNG o WebP válida.") from exc
    stem = uuid4().hex
    filename = f"{stem}.webp"
    image_record.asset.save(filename, asset, save=False)
    image_record.thumbnail.save(filename, thumbnail, save=False)
    image_record.renditions = save_renditions(image_record, clean, stem)
    image_record.approved_at = timezone.now()
    image_record.approved_by = reviewer
    image_record.withdrawn_at = None
    image_record.save()
