"""
Sistema de Cupones, Descuentos y Marketing para PerfumeLuxe
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from products.models import Product, Category, Brand
import string
import random


class Coupon(models.Model):
    """Cupones de descuento"""
    DISCOUNT_TYPES = [
        ('percentage', 'Porcentaje'),
        ('fixed', 'Cantidad Fija'),
        ('free_shipping', 'Envío Gratis'),
    ]
    
    code = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Código del cupón (ej: VERANO2025, BIENVENIDO10)"
    )
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Porcentaje (10 = 10%) o cantidad fija (15 = 15€)"
    )
    
    # Condiciones
    min_purchase_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Monto mínimo de compra para aplicar el cupón"
    )
    max_discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Descuento máximo (solo para porcentaje)"
    )
    
    # Validez
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    
    # Límites de uso
    usage_limit = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Número máximo de usos totales (vacío = ilimitado)"
    )
    usage_limit_per_user = models.IntegerField(
        default=1,
        help_text="Usos máximos por usuario"
    )
    times_used = models.IntegerField(default=0)
    
    # Restricciones
    applicable_to_products = models.ManyToManyField(
        Product, 
        blank=True,
        help_text="Dejar vacío para aplicar a todos"
    )
    applicable_to_categories = models.ManyToManyField(
        Category, 
        blank=True
    )
    applicable_to_brands = models.ManyToManyField(
        Brand, 
        blank=True
    )
    
    # Control
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_coupons'
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.get_discount_display()}"
    
    def get_discount_display(self):
        if self.discount_type == 'percentage':
            return f"{self.discount_value}%"
        elif self.discount_type == 'fixed':
            return f"{self.discount_value}€"
        else:
            return "Envío Gratis"
    
    def is_valid(self):
        """Verifica si el cupón es válido"""
        now = timezone.now()
        if not self.is_active:
            return False, "Cupón desactivado"
        if now < self.valid_from:
            return False, "Cupón aún no válido"
        if now > self.valid_to:
            return False, "Cupón expirado"
        if self.usage_limit and self.times_used >= self.usage_limit:
            return False, "Límite de uso alcanzado"
        return True, "Válido"
    
    def can_be_used_by(self, user):
        """Verifica si un usuario puede usar este cupón"""
        if not user.is_authenticated:
            return False, "Debes iniciar sesión"
        
        usage_count = CouponUsage.objects.filter(
            coupon=self,
            user=user
        ).count()
        
        if usage_count >= self.usage_limit_per_user:
            return False, f"Ya has usado este cupón {usage_count} veces"
        
        return True, "Disponible"
    
    def calculate_discount(self, cart_total, products):
        """Calcula el descuento aplicable"""
        # Verificar productos aplicables
        if self.applicable_to_products.exists():
            applicable_products = self.applicable_to_products.all()
            applicable_total = sum(
                p.price for p in products if p in applicable_products
            )
        elif self.applicable_to_categories.exists():
            applicable_categories = self.applicable_to_categories.all()
            applicable_total = sum(
                p.price for p in products 
                if p.category in applicable_categories
            )
        elif self.applicable_to_brands.exists():
            applicable_brands = self.applicable_to_brands.all()
            applicable_total = sum(
                p.price for p in products 
                if p.brand in applicable_brands
            )
        else:
            applicable_total = cart_total
        
        if self.discount_type == 'percentage':
            discount = applicable_total * (self.discount_value / 100)
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        elif self.discount_type == 'fixed':
            discount = min(self.discount_value, applicable_total)
        else:  # free_shipping
            discount = 0  # El envío se manejará aparte
        
        return round(discount, 2)
    
    @staticmethod
    def generate_code(prefix="LUXE", length=8):
        """Genera un código de cupón aleatorio"""
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(random.choice(chars) for _ in range(length))
        return f"{prefix}{random_part}"


class CouponUsage(models.Model):
    """Registro de uso de cupones"""
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=100)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-used_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.coupon.code}"


class Bundle(models.Model):
    """Packs y ofertas 3x2, 2x1"""
    BUNDLE_TYPES = [
        ('3x2', 'Paga 2 Lleva 3'),
        ('2x1', 'Paga 1 Lleva 2'),
        ('pack', 'Pack con Descuento'),
    ]
    
    name = models.CharField(max_length=200)
    bundle_type = models.CharField(max_length=10, choices=BUNDLE_TYPES)
    products = models.ManyToManyField(Product, related_name='in_bundles')
    
    # Para packs con descuento
    discount_percentage = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0
    )
    fixed_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Precio fijo del pack (alternativa al descuento %)"
    )
    
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_bundle_type_display()})"
    
    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and 
            self.valid_from <= now <= self.valid_to
        )
    
    def calculate_price(self):
        """Calcula el precio del bundle"""
        products = self.products.all()
        total = sum(p.price for p in products)
        
        if self.fixed_price:
            return self.fixed_price
        elif self.discount_percentage:
            return total * (1 - self.discount_percentage / 100)
        elif self.bundle_type == '3x2':
            # Paga los 2 más caros
            prices = sorted([p.price for p in products], reverse=True)
            return sum(prices[:2]) if len(prices) >= 3 else total
        elif self.bundle_type == '2x1':
            # Paga el más caro
            prices = sorted([p.price for p in products], reverse=True)
            return prices[0] if len(prices) >= 2 else total
        
        return total


class LoyaltyProgram(models.Model):
    """Programa de puntos y fidelización"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    points = models.IntegerField(default=0)
    tier = models.CharField(
        max_length=20,
        choices=[
            ('bronze', 'Bronce'),
            ('silver', 'Plata'),
            ('gold', 'Oro'),
            ('platinum', 'Platino'),
        ],
        default='bronze'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.points} puntos ({self.tier})"
    
    def add_points(self, amount_spent):
        """Añade puntos por compra (1€ = 1 punto)"""
        points_earned = int(amount_spent)
        self.points += points_earned
        self.update_tier()
        self.save()
        return points_earned
    
    def redeem_points(self, points_to_redeem):
        """Canjea puntos por descuento (100 puntos = 5€)"""
        if points_to_redeem > self.points:
            return False, "Puntos insuficientes"
        
        discount = (points_to_redeem / 100) * 5
        self.points -= points_to_redeem
        self.save()
        return True, discount
    
    def update_tier(self):
        """Actualiza el tier según puntos acumulados"""
        if self.points >= 5000:
            self.tier = 'platinum'
        elif self.points >= 2000:
            self.tier = 'gold'
        elif self.points >= 500:
            self.tier = 'silver'
        else:
            self.tier = 'bronze'


class LoyaltyTransaction(models.Model):
    """Historial de transacciones de puntos"""
    TRANSACTION_TYPES = [
        ('earn', 'Ganados'),
        ('redeem', 'Canjeados'),
        ('expire', 'Expirados'),
        ('bonus', 'Bonus'),
    ]
    
    loyalty_program = models.ForeignKey(
        LoyaltyProgram, 
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    points = models.IntegerField()
    description = models.CharField(max_length=200)
    order_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.loyalty_program.user.username} - {self.points} pts ({self.transaction_type})"
