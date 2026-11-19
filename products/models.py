from django.conf import settings
from django.core.files.storage import storages
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.urls import reverse

from home.models import NoticeConsent


class Category(models.Model):
    class Meta:
        verbose_name_plural = "Categories"

    db_name = models.CharField(max_length=254)
    name = models.CharField(max_length=254, null=True, blank=True)

    def __str__(self):
        return self.db_name

    def get_friendly_name(self):
        return self.name


class Gender(models.Model):
    class Meta:
        verbose_name_plural = "Genders"

    db_name = models.CharField(max_length=2)
    name = models.CharField(max_length=254, null=True, blank=True)

    def __str__(self):
        return self.db_name

    def get_friendly_name(self):
        return self.name


class Brand(models.Model):
    class Meta:
        verbose_name_plural = "Brands"

    db_name = models.CharField(max_length=254)
    name = models.CharField(max_length=254, null=True, blank=True)
    logo = models.ImageField(upload_to='brands/', null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.db_name

    def get_friendly_name(self):
        return self.name


class FragranceFamily(models.Model):
    """Familia olfativa: Floral, Oriental, Amaderado, Cítrico, etc."""
    class Meta:
        verbose_name_plural = "Fragrance Families"

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name


class FragranceNote(models.Model):
    """Notas individuales de perfume"""
    NOTE_TYPES = [
        ('top', 'Nota de Salida'),
        ('heart', 'Nota de Corazón'),
        ('base', 'Nota de Fondo'),
    ]

    name = models.CharField(max_length=100)
    note_type = models.CharField(max_length=10, choices=NOTE_TYPES)
    description = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ['name', 'note_type']

    def __str__(self):
        return f"{self.name} ({self.get_note_type_display()})"


class ProductQuerySet(models.QuerySet):
    def published(self):
        return self.filter(publication_status="approved")

    def sellable(self):
        """Approved products that may enter a cart once sales are enabled."""
        return self.published().exclude(catalog_origin="reference")


def catalog_asset_storage():
    return storages["catalog_assets"]


class Product(models.Model):
    CONCENTRATION_CHOICES = [
        ('parfum', 'Parfum (20-30%)'),
        ('edp', 'Eau de Parfum (15-20%)'),
        ('edt', 'Eau de Toilette (5-15%)'),
        ('edc', 'Eau de Cologne (2-5%)'),
        ('splash', 'Splash/Body Mist (1-3%)'),
    ]
    
    SIZE_CHOICES = [
        ('2ml', '2ml - Muestra'),
        ('5ml', '5ml - Viaje'),
        ('10ml', '10ml - Viaje'),
        ('15ml', '15ml'),
        ('30ml', '30ml'),
        ('50ml', '50ml'),
        ('75ml', '75ml'),
        ('100ml', '100ml'),
        ('125ml', '125ml'),
        ('150ml', '150ml'),
        ('200ml', '200ml'),
    ]
    
    INTENSITY_CHOICES = [
        ('light', 'Suave'),
        ('moderate', 'Moderada'),
        ('strong', 'Fuerte'),
        ('very_strong', 'Muy Fuerte'),
    ]

    DURATION_CHOICES = [
        ('2-4', '2-4 horas'),
        ('4-6', '4-6 horas'),
        ('6-8', '6-8 horas'),
        ('8-12', '8-12 horas (Larga duración)'),
        ('12+', 'Más de 12 horas'),
    ]

    OCCASION_CHOICES = [
        ('daily', 'Diario'),
        ('night', 'Noche'),
        ('formal', 'Formal'),
        ('casual', 'Casual'),
        ('sport', 'Deportivo'),
    ]

    SEASON_CHOICES = [
        ('spring', 'Primavera'),
        ('summer', 'Verano'),
        ('autumn', 'Otoño'),
        ('winter', 'Invierno'),
        ('all', 'Todo el año'),
    ]

    class Meta:
        permissions = [("publish_product", "Can approve and withdraw products")]

    class Publication(models.TextChoices):
        DRAFT = "draft", "Pendiente de revisión"
        APPROVED = "approved", "Publicada"
        WITHDRAWN = "withdrawn", "Retirada"

    class Origin(models.TextChoices):
        OWN = "own", "Catálogo propio"
        REFERENCE = "reference", "Referencia heredada"

    objects = ProductQuerySet.as_manager()
    catalog_origin = models.CharField(
        "origen del catálogo", max_length=10, choices=Origin.choices, default=Origin.OWN, db_index=True,
        help_text="Las fichas de referencia heredadas son informativas y nunca se pueden vender.",
    )
    publication_status = models.CharField(
        max_length=10, choices=Publication.choices, default=Publication.DRAFT, db_index=True,
    )
    verification_sources = models.JSONField(
        default=dict, blank=True,
        help_text="Referencias por campo: name, brand, concentration, size, notes, family, description.",
    )

    # Campos básicos existentes
    name = models.CharField(max_length=254)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    brand = models.ForeignKey(
        "Brand", null=True, blank=True, on_delete=models.SET_NULL)
    sku = models.CharField(max_length=254, null=True, blank=True, unique=True)
    category = models.ForeignKey(
        "Category", null=True, blank=True, on_delete=models.SET_NULL
    )
    gender = models.ForeignKey(
        "Gender", null=True, blank=True, on_delete=models.SET_NULL
    )
    image_url = models.URLField(max_length=1024, null=True, blank=True)
    image = models.ImageField(null=True, blank=True)
    has_sizes = models.BooleanField(default=False, null=True, blank=True)
    has_discount = models.BooleanField(default=False, null=True, blank=True)
    has_subscription = models.BooleanField(
        default=False, null=True, blank=True)
    rating = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, default=0
    )
    price = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    scent = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField()

    # Nuevos campos para mejoras
    fragrance_family = models.ForeignKey(
        FragranceFamily, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='products'
    )
    fragrance_notes = models.ManyToManyField(
        FragranceNote, blank=True, related_name='products'
    )
    
    # Información esencial de perfumería
    concentration = models.CharField(
        max_length=20, choices=CONCENTRATION_CHOICES, null=True, blank=True,
        help_text="Concentración del perfume (EDT, EDP, Parfum)"
    )
    size = models.CharField(
        max_length=10, choices=SIZE_CHOICES, null=True, blank=True,
        help_text="Tamaño del frasco en ml"
    )
    
    # Características del perfume
    intensity = models.CharField(
        max_length=20, choices=INTENSITY_CHOICES, null=True, blank=True
    )
    duration = models.CharField(
        max_length=20, choices=DURATION_CHOICES, null=True, blank=True
    )
    projection = models.CharField(
        max_length=20, choices=INTENSITY_CHOICES, null=True, blank=True,
        help_text="Proyección del aroma"
    )
    
    # Uso recomendado
    occasion = models.CharField(
        max_length=20, choices=OCCASION_CHOICES, null=True, blank=True
    )
    season = models.CharField(
        max_length=20, choices=SEASON_CHOICES, null=True, blank=True
    )
    
    # Stock y disponibilidad
    stock = models.IntegerField(default=0)
    is_original = models.BooleanField(default=True, help_text="Es original (no tester)")
    is_tester = models.BooleanField(default=False)
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    # SEO
    meta_description = models.TextField(max_length=160, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.pk and self.publication_status == self.Publication.APPROVED:
            self.publication_status = self.Publication.DRAFT
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = {*kwargs["update_fields"], "publication_status"}
        if not self.slug:
            brand_name = self.brand.name if self.brand and self.brand.name else ""
            base_slug = slugify(f"{brand_name} {self.name}") or "producto"
            max_length = self._meta.get_field("slug").max_length
            slug = base_slug[:max_length].rstrip("-_") or "producto"
            existing = Product.objects.using(kwargs.get("using") or self._state.db)
            counter = 1
            while existing.filter(slug=slug).exclude(pk=self.pk).exists():
                suffix = f"-{counter}"
                slug = base_slug[:max_length - len(suffix)].rstrip("-_") + suffix
                counter += 1
            self.slug = slug
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = {*kwargs["update_fields"], "slug"}
        super().save(*args, **kwargs)

    @property
    def public_image_url(self):
        from .presentation import public_cover
        return public_cover(self) if self.publication_status == self.Publication.APPROVED else ""

    @property
    def is_reference(self):
        return self.catalog_origin == self.Origin.REFERENCE

    def get_absolute_url(self):
        return reverse("products:product_detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.name
    
    @property
    def in_stock(self):
        return self.stock > 0
    
    @property
    def average_rating(self):
        reviews = self.reviews.filter(is_approved=True)
        if reviews:
            return sum(r.rating for r in reviews) / len(reviews)
        return 0
    
    @property
    def review_count(self):
        return self.reviews.filter(is_approved=True).count()
    
    @property
    def discounted_price(self):
        if self.has_discount and hasattr(self, 'discount_percentage'):
            return self.price * (1 - self.discount_percentage / 100)
        return self.price
    
    @property
    def is_new(self):
        """Producto agregado en los últimos 30 días"""
        from datetime import timedelta
        from django.utils import timezone
        if self.created_at:
            return (timezone.now() - self.created_at).days <= 30
        return False


class PublicationDecision(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="publication_history")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=10, choices=Product.Publication.choices)
    evidence = models.JSONField(default=dict, blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-decided_at", "-pk"]


class CatalogImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="catalog_images")
    source_file = models.CharField(max_length=300, help_text="Nombre exacto del archivo de portada o de una variante.")
    source_reference = models.CharField(max_length=500, help_text="Referencia verificable al origen de la fotografía.")
    rights_reference = models.CharField(max_length=500, help_text="Referencia al permiso o licencia de publicación.")
    alt_text = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    asset = models.FileField(storage=catalog_asset_storage, upload_to="web/", blank=True, max_length=300)
    thumbnail = models.FileField(storage=catalog_asset_storage, upload_to="thumb/", blank=True, max_length=300)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["display_order", "pk"]
        permissions = [("approve_catalogimage", "Can approve catalog images")]

    @property
    def is_public(self):
        return bool(self.approved_at and not self.withdrawn_at and self.asset)


class Review(models.Model):
    """Reseñas y opiniones de productos"""
    SKIN_TYPE_CHOICES = [
        ('dry', 'Piel Seca'),
        ('oily', 'Piel Grasa'),
        ('normal', 'Piel Normal'),
        ('combination', 'Piel Mixta'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='reviews'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200)
    comment = models.TextField()
    
    # Información adicional
    skin_type = models.CharField(
        max_length=20, choices=SKIN_TYPE_CHOICES, null=True, blank=True
    )
    duration_experienced = models.CharField(
        max_length=50, null=True, blank=True,
        help_text="Duración experimentada por el usuario"
    )
    
    # Verificación y moderación
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Utilidad de la reseña
    helpful_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['product', 'user']  # Un usuario, una reseña por producto

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating}★)"


class ReviewImage(models.Model):
    """Imágenes adjuntas a reseñas"""
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name='images'
    )
    image = models.ImageField(upload_to='reviews/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Imagen de {self.review}"


class Wishlist(models.Model):
    """Lista de deseos del usuario"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    products = models.ManyToManyField(Product, blank=True, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wishlist de {self.user.username}"


class PriceAlert(models.Model):
    """Alertas de precio para productos"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    target_price = models.DecimalField(max_digits=6, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'product']

    def __str__(self):
        return f"Alerta de {self.user.username} para {self.product.name}"


class StockAlert(NoticeConsent):
    """Alertas de stock disponible"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    email = models.EmailField()
    is_notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'product']

    def __str__(self):
        return f"Alerta de stock: {self.user.username} - {self.product.name}"


# Importar modelos extendidos
from .models_extended import (
    ProductSize,
    ProductVideo,
    SampleRequest,
    UserFragranceProfile,
    FragranceEvolution,
    ProductComparison
)
