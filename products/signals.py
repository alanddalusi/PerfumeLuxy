from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import Brand, CatalogImage, FragranceFamily, FragranceNote, Product, ProductSize


def invalidate(queryset):
    queryset.published().update(publication_status=Product.Publication.DRAFT)


def retire_detached_images(product_id, using):
    product = Product.objects.using(using).filter(pk=product_id).first()
    if product is None:
        return
    files = [product.image.name, *product.sizes.values_list("image", flat=True)]
    CatalogImage.objects.using(using).filter(
        product_id=product_id, approved_at__isnull=False, withdrawn_at__isnull=True,
    ).exclude(source_file__in=[file for file in files if file]).update(withdrawn_at=timezone.now())


@receiver(post_save, sender=Product)
def product_media_changed(sender, instance, created, using, **kwargs):
    if not created and not kwargs.get("raw"):
        retire_detached_images(instance.pk, using)


@receiver(post_save, sender=ProductSize)
@receiver(post_delete, sender=ProductSize)
def product_size_changed(sender, instance, using, **kwargs):
    if not kwargs.get("raw"):
        invalidate(Product.objects.using(using).filter(pk=instance.product_id))
        retire_detached_images(instance.product_id, using)


@receiver(m2m_changed, sender=Product.fragrance_notes.through)
def product_notes_changed(sender, instance, action, reverse, pk_set, using, **kwargs):
    if action not in {"pre_add", "pre_remove", "pre_clear"}:
        return
    queryset = Product.objects.using(using)
    if reverse:
        queryset = queryset.filter(pk__in=pk_set) if pk_set is not None else queryset.filter(fragrance_notes=instance)
    else:
        queryset = queryset.filter(pk=instance.pk)
    invalidate(queryset)


@receiver(post_save, sender=Brand)
@receiver(pre_delete, sender=Brand)
@receiver(post_save, sender=FragranceFamily)
@receiver(pre_delete, sender=FragranceFamily)
@receiver(post_save, sender=FragranceNote)
@receiver(pre_delete, sender=FragranceNote)
def reference_changed(sender, instance, using, **kwargs):
    if not kwargs.get("created") and not kwargs.get("raw"):
        lookup = {Brand: "brand", FragranceFamily: "fragrance_family", FragranceNote: "fragrance_notes"}
        invalidate(Product.objects.using(using).filter(**{lookup[sender]: instance}))
