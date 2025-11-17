from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


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


class Product(models.Model):
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

    # Campos básicos existentes
    name = models.CharField(max_length=254)
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


class StockAlert(models.Model):
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

