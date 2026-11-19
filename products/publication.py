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


def webp_variant(image, dimensions):
    variant = image.copy()
    variant.thumbnail(dimensions, Image.Resampling.LANCZOS)
    output = BytesIO()
    variant.save(output, format="WEBP", quality=83, method=4)
    return ContentFile(output.getvalue())


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
            if original.width * original.height > 25_000_000 or getattr(original, "is_animated", False):
                raise ValidationError("La imagen debe ser fija y tener hasta 25 megapíxeles.")
            photo = ImageOps.exif_transpose(original).convert("RGB")
            clean = Image.new("RGB", photo.size)
            clean.paste(photo)
            asset = webp_variant(clean, (1200, 1440))
            thumbnail = webp_variant(clean, (420, 504))
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("No se pudo abrir una imagen JPEG, PNG o WebP válida.") from exc
    filename = f"{uuid4().hex}.webp"
    image_record.asset.save(filename, asset, save=False)
    image_record.thumbnail.save(filename, thumbnail, save=False)
    image_record.approved_at = timezone.now()
    image_record.approved_by = reviewer
    image_record.withdrawn_at = None
    image_record.save()
