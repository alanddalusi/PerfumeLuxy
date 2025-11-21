"""
Modelos adicionales para mejoras de perfumería
Tamaños, Videos, Muestras, Perfil Olfativo, etc.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class ProductSize(models.Model):
    """Variantes de tamaño para un producto"""
    product = models.ForeignKey(
        'Product', on_delete=models.CASCADE, related_name='sizes'
    )
    size_ml = models.IntegerField(help_text="Tamaño en ml")
    price = models.DecimalField(max_digits=6, decimal_places=2)
    stock = models.IntegerField(default=0)
    sku = models.CharField(max_length=50, unique=True)
    
    # Badges visuales
    is_popular = models.BooleanField(
        default=False, help_text="Marcar como 'Más popular'"
    )
    is_best_value = models.BooleanField(
        default=False, help_text="Marcar como 'Mejor valor'"
    )
    
    # Imagen específica del tamaño
    image = models.ImageField(
        upload_to='products/sizes/', null=True, blank=True
    )
    
    class Meta:
        ordering = ['size_ml']
        unique_together = ['product', 'size_ml']
    
    def __str__(self):
        return f"{self.product.name} - {self.size_ml}ml"
    
    @property
    def price_per_ml(self):
        """Precio por ml para comparación"""
        return round(float(self.price) / self.size_ml, 2)
    
    @property
    def in_stock(self):
        return self.stock > 0


class ProductVideo(models.Model):
    """Videos del producto (YouTube, Vimeo)"""
    product = models.ForeignKey(
        'Product', on_delete=models.CASCADE, related_name='videos'
    )
    title = models.CharField(max_length=200)
    video_url = models.URLField(help_text="URL de YouTube o Vimeo")
    thumbnail = models.ImageField(
        upload_to='products/videos/', null=True, blank=True
    )
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f"{self.product.name} - {self.title}"
    
    @property
    def embed_url(self):
        """Convertir URL a embed URL"""
        if 'youtube.com' in self.video_url or 'youtu.be' in self.video_url:
            video_id = self.video_url.split('v=')[-1].split('&')[0]
            if 'youtu.be' in self.video_url:
                video_id = self.video_url.split('/')[-1]
            return f"https://www.youtube.com/embed/{video_id}"
        elif 'vimeo.com' in self.video_url:
            video_id = self.video_url.split('/')[-1]
            return f"https://player.vimeo.com/video/{video_id}"
        return self.video_url


class SampleRequest(models.Model):
    """Solicitudes de muestras gratis"""
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobada'),
        ('sent', 'Enviada'),
        ('delivered', 'Entregada'),
        ('rejected', 'Rechazada'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    
    # Dirección de envío
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    postal_code = models.CharField(max_length=10)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='España')
    
    # Estado
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    # Tracking
    tracking_number = models.CharField(
        max_length=100, blank=True, null=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'product']  # Una muestra por producto
    
    def __str__(self):
        return f"Muestra de {self.product.name} para {self.user.username}"


class UserFragranceProfile(models.Model):
    """Perfil olfativo del usuario para recomendaciones"""
    INTENSITY_CHOICES = [
        ('light', 'Suave'),
        ('medium', 'Moderada'),
        ('strong', 'Fuerte'),
    ]
    
    PRICE_RANGE_CHOICES = [
        ('budget', 'Económico (<50€)'),
        ('mid', 'Medio (50-100€)'),
        ('premium', 'Premium (100-200€)'),
        ('luxury', 'Lujo (>200€)'),
    ]
    
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='fragrance_profile'
    )
    
    # Preferencias de familias y notas
    preferred_families = models.ManyToManyField(
        'FragranceFamily', blank=True, related_name='preferred_by_users'
    )
    preferred_notes = models.ManyToManyField(
        'FragranceNote', blank=True, related_name='preferred_by_users'
    )
    disliked_notes = models.ManyToManyField(
        'FragranceNote', blank=True, related_name='disliked_by_users'
    )
    
    # Preferencias de características
    preferred_intensity = models.CharField(
        max_length=20, choices=INTENSITY_CHOICES, default='medium'
    )
    preferred_duration = models.CharField(max_length=20, blank=True)
    preferred_price_range = models.CharField(
        max_length=20, choices=PRICE_RANGE_CHOICES, default='mid'
    )
    
    # Ocasiones favoritas
    favorite_occasions = models.CharField(
        max_length=200, blank=True,
        help_text="daily,night,formal (separados por comas)"
    )
    favorite_seasons = models.CharField(
        max_length=200, blank=True,
        help_text="spring,summer,autumn,winter"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Perfil de {self.user.username}"
    
    def get_recommendations(self, limit=6):
        """Obtener recomendaciones basadas en el perfil"""
        from .models import Product
        
        # Filtrar por familias preferidas
        products = Product.objects.filter(
            fragrance_family__in=self.preferred_families.all()
        )
        
        # Filtrar por rango de precio
        if self.preferred_price_range == 'budget':
            products = products.filter(price__lt=50)
        elif self.preferred_price_range == 'mid':
            products = products.filter(price__gte=50, price__lt=100)
        elif self.preferred_price_range == 'premium':
            products = products.filter(price__gte=100, price__lt=200)
        else:  # luxury
            products = products.filter(price__gte=200)
        
        # Filtrar por intensidad
        if self.preferred_intensity:
            products = products.filter(intensity=self.preferred_intensity)
        
        return products.distinct()[:limit]


class FragranceEvolution(models.Model):
    """Cronología de evolución del perfume"""
    product = models.OneToOneField(
        'Product', on_delete=models.CASCADE, related_name='evolution'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Notas de salida (0-15 minutos)
    top_notes = models.TextField()
    top_notes_duration = models.CharField(
        max_length=50, default="0-15 minutos"
    )
    top_notes_description = models.TextField(
        help_text="Descripción de las notas de salida"
    )
    
    # Notas de corazón (15 min - 4 horas)
    heart_notes = models.TextField()
    heart_notes_duration = models.CharField(
        max_length=50, default="15 min - 4 horas"
    )
    heart_notes_description = models.TextField(
        help_text="Descripción de las notas de corazón"
    )
    
    # Notas de fondo (4+ horas)
    base_notes = models.TextField()
    base_notes_duration = models.CharField(
        max_length=50, default="4+ horas"
    )
    base_notes_description = models.TextField(
        help_text="Descripción de las notas de fondo"
    )
    
    def __str__(self):
        return f"Evolución de {self.product.name}"


class ProductComparison(models.Model):
    """Guardar comparaciones de productos del usuario"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, default="Mi comparación")
    products = models.ManyToManyField('Product')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"
