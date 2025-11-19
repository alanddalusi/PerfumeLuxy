# 📚 EJEMPLOS DE USO - PERFUMELUXE

Guía práctica con ejemplos de código para usar todas las funcionalidades implementadas.

---

## 🔍 SEO SYSTEM

### Ejemplo 1: Vista Simple con SEO

```python
# En tu views.py
from django.shortcuts import render
from eau_royal.seo import SEOManager

def mi_pagina(request):
    # Crear instancia del SEO Manager
    seo = SEOManager(request)
    
    # Generar meta tags
    seo_data = seo.get_meta_tags(
        title="Perfumes de Nicho | PerfumeLuxe",
        description="Descubre nuestra exclusiva colección de perfumes nicho. Fragancias únicas de las mejores casas perfumistas.",
        keywords="perfumes nicho, fragancias exclusivas, perfume artesanal"
    )
    
    return render(request, 'mi_template.html', {
        'seo_data': seo_data
    })
```

### Ejemplo 2: Producto con Schema.org Completo

```python
# En products/views.py
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    seo = SEOManager(request)
    
    # Meta tags optimizados para producto
    seo_data = seo.get_product_meta(product)
    
    # Breadcrumb
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Productos', 'url': '/products/'},
        {'name': product.brand.name, 'url': f'/products/?brand={product.brand.db_name}'},
        {'name': product.name, 'url': None}  # None = ítem actual
    ]
    
    # Schemas
    product_schema = seo.generate_product_schema(product)
    breadcrumb_schema = seo.generate_breadcrumb_schema(breadcrumb_items)
    
    return render(request, 'product.html', {
        'product': product,
        'seo_data': seo_data,
        'breadcrumb_items': breadcrumb_items,
        'product_schema': product_schema,
        'breadcrumb_schema': breadcrumb_schema,
    })
```

### Ejemplo 3: Template con SEO

```html
<!-- En tu template.html -->
{% extends "base.html" %}
{% load static %}

<!-- El base.html ya incluye los meta tags si pasa seo_data -->

{% block content %}
  <!-- Breadcrumb SEO -->
  {% if breadcrumb_items %}
    {% include 'seo/breadcrumb.html' with breadcrumb_items=breadcrumb_items %}
  {% endif %}
  
  <div class="container">
    <h1>{{ title }}</h1>
    <!-- Tu contenido -->
  </div>
{% endblock %}
```

---

## 🎟️ SISTEMA DE CUPONES

### Ejemplo 1: Crear Cupón en Admin Shell

```python
# python manage.py shell

from checkout.marketing_models import Coupon
from django.utils import timezone
from datetime import timedelta

# Cupón de 20% de descuento
coupon = Coupon.objects.create(
    code="VERANO2025",
    discount_type="percentage",
    discount_value=20,
    min_purchase_amount=50,
    max_discount_amount=30,  # Máximo 30€ de descuento
    valid_from=timezone.now(),
    valid_to=timezone.now() + timedelta(days=60),
    usage_limit=100,  # Máximo 100 usos totales
    usage_limit_per_user=1,  # 1 uso por usuario
    is_active=True
)

print(f"Cupón creado: {coupon.code}")
```

### Ejemplo 2: Cupón con Restricciones

```python
from checkout.marketing_models import Coupon
from products.models import Brand, Category

# Cupón solo para perfumes de una marca específica
coupon = Coupon.objects.create(
    code="DIOR15",
    discount_type="fixed",
    discount_value=15,  # 15€ de descuento
    min_purchase_amount=80,
    valid_from=timezone.now(),
    valid_to=timezone.now() + timedelta(days=30),
    is_active=True
)

# Aplicar solo a productos de Dior
dior = Brand.objects.get(db_name="dior")
coupon.applicable_to_brands.add(dior)

print("Cupón DIOR15 creado (solo productos Dior)")
```

### Ejemplo 3: Validar y Aplicar Cupón

```python
# En checkout/views.py
from checkout.marketing_models import Coupon, CouponUsage

def apply_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('coupon_code', '').strip().upper()
        
        try:
            coupon = Coupon.objects.get(code=code)
            
            # Validar cupón
            is_valid, message = coupon.is_valid()
            if not is_valid:
                messages.error(request, f"Cupón inválido: {message}")
                return redirect('checkout')
            
            # Verificar si el usuario puede usarlo
            can_use, message = coupon.can_be_used_by(request.user)
            if not can_use:
                messages.error(request, message)
                return redirect('checkout')
            
            # Calcular descuento
            cart_total = get_cart_total(request)  # Tu función
            products = get_cart_products(request)  # Tu función
            discount = coupon.calculate_discount(cart_total, products)
            
            # Guardar en sesión
            request.session['coupon_id'] = coupon.id
            request.session['discount'] = float(discount)
            
            messages.success(request, f'¡Cupón {code} aplicado! Descuento: {discount}€')
            
        except Coupon.DoesNotExist:
            messages.error(request, 'Cupón no válido')
    
    return redirect('checkout')
```

### Ejemplo 4: Registrar Uso de Cupón

```python
# Después de completar el pedido
from checkout.marketing_models import CouponUsage

def complete_order(request, order):
    coupon_id = request.session.get('coupon_id')
    discount = request.session.get('discount', 0)
    
    if coupon_id and discount:
        coupon = Coupon.objects.get(id=coupon_id)
        
        # Registrar uso
        CouponUsage.objects.create(
            coupon=coupon,
            user=request.user,
            order_id=order.order_number,
            discount_amount=discount
        )
        
        # Incrementar contador
        coupon.times_used += 1
        coupon.save()
        
        # Limpiar sesión
        del request.session['coupon_id']
        del request.session['discount']
```

---

## 🎁 BUNDLES Y OFERTAS

### Ejemplo 1: Crear Pack 3x2

```python
from checkout.marketing_models import Bundle
from products.models import Product

# Seleccionar productos para el pack
products = Product.objects.filter(
    brand__db_name='dior',
    concentration='edt'
)[:3]

bundle = Bundle.objects.create(
    name="Pack 3x2 Dior",
    bundle_type="3x2",
    valid_from=timezone.now(),
    valid_to=timezone.now() + timedelta(days=30),
    is_active=True
)

# Añadir productos
bundle.products.set(products)

print(f"Bundle creado: {bundle.name}")
print(f"Precio original: {sum(p.price for p in products)}€")
print(f"Precio con 3x2: {bundle.calculate_price()}€")
```

### Ejemplo 2: Pack con Descuento Fijo

```python
# Pack "Descubre Nicho" con 3 perfumes y 25% descuento
niche_products = Product.objects.filter(
    category__db_name='niche'
)[:3]

bundle = Bundle.objects.create(
    name="Pack Descubre Nicho",
    bundle_type="pack",
    discount_percentage=25,  # 25% de descuento
    valid_from=timezone.now(),
    valid_to=timezone.now() + timedelta(days=60),
    is_active=True
)

bundle.products.set(niche_products)
```

---

## 💎 PROGRAMA DE FIDELIZACIÓN

### Ejemplo 1: Crear Programa para Usuario

```python
from checkout.marketing_models import LoyaltyProgram
from django.contrib.auth.models import User

# Obtener o crear programa
user = User.objects.get(username='cliente@example.com')
loyalty, created = LoyaltyProgram.objects.get_or_create(user=user)

if created:
    print(f"Programa creado para {user.username}")
else:
    print(f"Puntos actuales: {loyalty.points} | Tier: {loyalty.tier}")
```

### Ejemplo 2: Añadir Puntos por Compra

```python
# Después de completar un pedido
def complete_order(request, order):
    # ... código de orden ...
    
    # Añadir puntos
    if request.user.is_authenticated:
        loyalty = LoyaltyProgram.objects.get_or_create(user=request.user)[0]
        points_earned = loyalty.add_points(amount_spent=order.total)
        
        # Registrar transacción
        from checkout.marketing_models import LoyaltyTransaction
        LoyaltyTransaction.objects.create(
            loyalty_program=loyalty,
            transaction_type='earn',
            points=points_earned,
            description=f'Compra #{order.order_number}',
            order_id=order.order_number
        )
        
        messages.success(
            request,
            f'¡Has ganado {points_earned} puntos! Total: {loyalty.points}'
        )
```

### Ejemplo 3: Canjear Puntos

```python
def redeem_points(request):
    if request.method == 'POST':
        points_to_redeem = int(request.POST.get('points', 0))
        
        loyalty = LoyaltyProgram.objects.get(user=request.user)
        success, result = loyalty.redeem_points(points_to_redeem)
        
        if success:
            discount = result
            
            # Registrar transacción
            LoyaltyTransaction.objects.create(
                loyalty_program=loyalty,
                transaction_type='redeem',
                points=points_to_redeem,
                description=f'Canje por {discount}€ de descuento'
            )
            
            # Guardar descuento en sesión
            request.session['loyalty_discount'] = float(discount)
            
            messages.success(
                request,
                f'¡{points_to_redeem} puntos canjeados! Descuento: {discount}€'
            )
        else:
            messages.error(request, result)
    
    return redirect('checkout')
```

### Ejemplo 4: Mostrar Tier en Template

```html
<!-- En perfil de usuario -->
{% if request.user.is_authenticated %}
  {% with loyalty=request.user.loyaltyprogram %}
    <div class="loyalty-card">
      <h3>Programa de Lealtad</h3>
      <div class="points-display">
        <span class="points">{{ loyalty.points }}</span>
        <span class="label">puntos</span>
      </div>
      <div class="tier-badge tier-{{ loyalty.tier }}">
        {{ loyalty.get_tier_display }}
      </div>
      
      {% if loyalty.points >= 100 %}
        <p>Tienes {{ loyalty.points }} puntos</p>
        <p>Puedes canjear hasta {{ loyalty.points|floatformat:0 }} puntos por 
           {{ loyalty.points|floatformat:0|mul:0.05 }}€ de descuento</p>
        <form method="post" action="{% url 'redeem_points' %}">
          {% csrf_token %}
          <input type="number" name="points" max="{{ loyalty.points }}" step="100">
          <button type="submit">Canjear</button>
        </form>
      {% endif %}
    </div>
  {% endwith %}
{% endif %}
```

---

## 🔄 WISHLIST (Ya Implementada)

### Ejemplo: Añadir/Quitar de Wishlist

```python
# En template de producto
<button 
  class="wishlist-btn {% if in_wishlist %}active{% endif %}"
  data-product-id="{{ product.id }}"
  onclick="toggleWishlist({{ product.id }})">
  <i class="fas fa-heart"></i>
  {% if in_wishlist %}En Favoritos{% else %}Añadir a Favoritos{% endif %}
</button>

<script>
function toggleWishlist(productId) {
  fetch(`/products/wishlist/toggle/${productId}/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': '{{ csrf_token }}',
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      location.reload();
    }
  });
}
</script>
```

---

## 📝 REVIEWS (Ya Implementadas)

### Ejemplo: Formulario de Review

```html
<!-- En product_detail.html -->
<div class="review-form">
  <h4>Deja tu opinión</h4>
  <form method="post" action="{% url 'products:add_review' product.id %}" enctype="multipart/form-data">
    {% csrf_token %}
    
    <!-- Rating -->
    <div class="rating-input">
      <label>Calificación:</label>
      <div class="stars">
        {% for i in "12345" %}
          <input type="radio" name="rating" value="{{ i }}" id="star{{ i }}" required>
          <label for="star{{ i }}">★</label>
        {% endfor %}
      </div>
    </div>
    
    <!-- Título -->
    <input type="text" name="title" placeholder="Título de tu reseña" required>
    
    <!-- Comentario -->
    <textarea name="comment" placeholder="Cuéntanos tu experiencia..." required></textarea>
    
    <!-- Tipo de piel (opcional) -->
    <select name="skin_type">
      <option value="">Tipo de piel (opcional)</option>
      <option value="dry">Piel Seca</option>
      <option value="oily">Piel Grasa</option>
      <option value="normal">Piel Normal</option>
      <option value="combination">Piel Mixta</option>
    </select>
    
    <!-- Duración experimentada -->
    <input type="text" name="duration_experienced" placeholder="Duración que experimentaste">
    
    <!-- Imágenes (opcional) -->
    <input type="file" name="images" multiple accept="image/*">
    <small>Puedes subir hasta 5 imágenes</small>
    
    <button type="submit">Publicar Reseña</button>
  </form>
</div>
```

---

## 🎨 ESTILOS CSS LUXURY

### Ejemplo: Botón Premium

```html
<!-- Botón dorado luxury -->
<button class="btn-luxury-gold">
  <i class="fas fa-shopping-bag me-2"></i>
  Añadir al Carrito
</button>

<style>
.btn-luxury-gold {
  background: linear-gradient(135deg, #d4af37 0%, #f8e896 100%);
  color: #1a1a1a;
  padding: 12px 30px;
  border: none;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3);
}

.btn-luxury-gold:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(212, 175, 55, 0.4);
}
</style>
```

---

## 🔗 URLs ÚTILES

```python
# En tus URLpatterns
from checkout.marketing_admin import *  # Importar admin de marketing

urlpatterns = [
    # Cupones
    path('checkout/apply-coupon/', apply_coupon, name='apply_coupon'),
    path('checkout/remove-coupon/', remove_coupon, name='remove_coupon'),
    
    # Loyalty
    path('profile/loyalty/', loyalty_dashboard, name='loyalty_dashboard'),
    path('profile/redeem-points/', redeem_points, name='redeem_points'),
    
    # Ya existentes
    path('products/wishlist/toggle/<int:product_id>/', toggle_wishlist, name='toggle_wishlist'),
    path('products/<int:product_id>/review/add/', add_review, name='add_review'),
]
```

---

## ✅ TESTING

### Test del Sistema SEO

```python
# python manage.py shell

from eau_royal.seo import SEOManager
from django.test import RequestFactory
from products.models import Product

# Crear request falso
factory = RequestFactory()
request = factory.get('/')

# Test SEOManager
seo = SEOManager(request)

# Test meta tags generales
meta = seo.get_meta_tags(title="Test", description="Test description")
print(meta)

# Test meta tags de producto
product = Product.objects.first()
product_meta = seo.get_product_meta(product)
print(product_meta)

# Test schemas
schema = seo.generate_product_schema(product)
print(schema)
```

---

**¿Necesitas más ejemplos?** Consulta `IMPLEMENTACION_COMPLETA.md` para la documentación completa.
