"""
Vistas para funcionalidades avanzadas de perfumería
Tamaños, Muestras, Comparador, Quiz, Perfil Olfativo
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Avg, Count, Min, Max
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Product, FragranceFamily, FragranceNote
from .models_extended import (
    ProductSize, SampleRequest, UserFragranceProfile,
    ProductComparison, FragranceEvolution
)


# ========================================
# SELECTOR DE TAMAÑOS
# ========================================

def get_product_sizes(request, product_id):
    """API para obtener tamaños disponibles de un producto"""
    product = get_object_or_404(Product, id=product_id)
    sizes = product.sizes.all()
    
    data = [{
        'id': size.id,
        'size_ml': size.size_ml,
        'price': str(size.price),
        'price_per_ml': size.price_per_ml,
        'stock': size.stock,
        'in_stock': size.in_stock,
        'is_popular': size.is_popular,
        'is_best_value': size.is_best_value,
        'image_url': size.image.url if size.image else product.image.url
    } for size in sizes]
    
    return JsonResponse({'sizes': data})


# ========================================
# SISTEMA DE MUESTRAS
# ========================================

@login_required
def request_sample(request, product_id):
    """Solicitar muestra de un producto"""
    product = get_object_or_404(Product, id=product_id)
    
    # Verificar si ya solicitó muestra
    existing = SampleRequest.objects.filter(
        user=request.user,
        product=product
    ).first()
    
    if existing:
        messages.warning(
            request,
            f'Ya has solicitado una muestra de {product.name}'
        )
        return redirect('products:product_detail', slug=product.slug)
    
    if request.method == 'POST':
        SampleRequest.objects.create(
            user=request.user,
            product=product,
            full_name=request.POST.get('full_name'),
            email=request.POST.get('email'),
            phone=request.POST.get('phone'),
            address=request.POST.get('address'),
            postal_code=request.POST.get('postal_code'),
            city=request.POST.get('city'),
            country=request.POST.get('country', 'España')
        )
        
        messages.success(
            request,
            '¡Muestra solicitada! Te enviaremos un email de confirmación.'
        )
        return redirect('products:product_detail', slug=product.slug)
    
    context = {
        'product': product
    }
    return render(request, 'products/request_sample.html', context)


@login_required
def my_sample_requests(request):
    """Ver mis solicitudes de muestras"""
    samples = SampleRequest.objects.filter(
        user=request.user
    ).select_related('product')
    
    context = {
        'samples': samples
    }
    return render(request, 'products/my_samples.html', context)


# ========================================
# COMPARADOR DE PERFUMES
# ========================================

def compare_products(request):
    """Comparar hasta 3 productos lado a lado"""
    product_ids = request.GET.getlist('products')
    
    if len(product_ids) < 2:
        messages.error(request, 'Selecciona al menos 2 productos para comparar')
        return redirect('products:products')
    
    if len(product_ids) > 3:
        product_ids = product_ids[:3]
        messages.warning(request, 'Solo puedes comparar hasta 3 productos')
    
    products = Product.objects.filter(id__in=product_ids).prefetch_related(
        'fragrance_notes',
        'reviews',
        'sizes'
    )
    
    # Calcular datos comparativos
    comparison_data = []
    for product in products:
        comparison_data.append({
            'product': product,
            'avg_rating': product.reviews.aggregate(
                Avg('rating')
            )['rating__avg'] or 0,
            'review_count': product.reviews.count(),
            'min_price': product.sizes.aggregate(
                models.Min('price')
            )['price__min'] if product.sizes.exists() else product.price,
            'max_price': product.sizes.aggregate(
                models.Max('price')
            )['price__max'] if product.sizes.exists() else product.price,
        })
    
    context = {
        'comparison_data': comparison_data
    }
    return render(request, 'products/compare.html', context)


@login_required
def add_to_comparison(request, product_id):
    """Añadir producto a lista de comparación (sesión)"""
    comparison_list = request.session.get('comparison_list', [])
    
    if product_id not in comparison_list:
        if len(comparison_list) >= 3:
            messages.warning(request, 'Solo puedes comparar hasta 3 productos')
        else:
            comparison_list.append(product_id)
            request.session['comparison_list'] = comparison_list
            messages.success(request, 'Producto añadido a comparación')
    
    return redirect(request.META.get('HTTP_REFERER', 'products:products'))


# ========================================
# PERFIL OLFATIVO
# ========================================

@login_required
def fragrance_profile(request):
    """Ver y editar perfil olfativo"""
    profile, created = UserFragranceProfile.objects.get_or_create(
        user=request.user
    )
    
    if request.method == 'POST':
        # Actualizar preferencias
        profile.preferred_intensity = request.POST.get('intensity')
        profile.preferred_price_range = request.POST.get('price_range')
        profile.favorite_occasions = request.POST.get('occasions', '')
        profile.favorite_seasons = request.POST.get('seasons', '')
        
        # Actualizar familias preferidas
        family_ids = request.POST.getlist('families')
        profile.preferred_families.set(family_ids)
        
        # Actualizar notas preferidas
        note_ids = request.POST.getlist('notes')
        profile.preferred_notes.set(note_ids)
        
        # Notas que no gustan
        dislike_ids = request.POST.getlist('disliked_notes')
        profile.disliked_notes.set(dislike_ids)
        
        profile.save()
        messages.success(request, 'Perfil actualizado correctamente')
        return redirect('products:fragrance_profile')
    
    # Obtener recomendaciones basadas en perfil
    recommendations = profile.get_recommendations(limit=8)
    
    context = {
        'profile': profile,
        'recommendations': recommendations,
        'families': FragranceFamily.objects.all(),
        'notes': FragranceNote.objects.all()
    }
    return render(request, 'products/fragrance_profile.html', context)


# ========================================
# QUIZ PERSONALIZADO
# ========================================

def fragrance_quiz_start(request):
    """Iniciar quiz de recomendación"""
    context = {
        'families': FragranceFamily.objects.all(),
        'notes': FragranceNote.objects.all()
    }
    return render(request, 'products/quiz_start.html', context)


def fragrance_quiz_results(request):
    """Resultados del quiz con recomendaciones"""
    if request.method != 'POST':
        return redirect('products:fragrance_quiz_start')
    
    # Procesar respuestas
    gender = request.POST.get('gender')
    intensity = request.POST.get('intensity')
    occasion = request.POST.get('occasion')
    price_range = request.POST.get('price_range')
    family_ids = request.POST.getlist('families')
    
    # Construir query de productos
    products = Product.objects.all()
    
    if gender:
        products = products.filter(gender__db_name=gender)
    
    if intensity:
        products = products.filter(intensity=intensity)
    
    if occasion:
        products = products.filter(occasion=occasion)
    
    if family_ids:
        products = products.filter(fragrance_family_id__in=family_ids)
    
    # Filtro de precio
    if price_range == 'budget':
        products = products.filter(price__lt=50)
    elif price_range == 'mid':
        products = products.filter(price__gte=50, price__lt=100)
    elif price_range == 'premium':
        products = products.filter(price__gte=100, price__lt=200)
    elif price_range == 'luxury':
        products = products.filter(price__gte=200)
    
    # Ordenar por rating
    products = products.annotate(
        avg_rating=Avg('reviews__rating')
    ).order_by('-avg_rating')[:6]
    
    context = {
        'products': products,
        'quiz_data': {
            'gender': gender,
            'intensity': intensity,
            'occasion': occasion,
            'price_range': price_range
        }
    }
    return render(request, 'products/quiz_results.html', context)


# ========================================
# TAMBIÉN COMPRARON (FREQUENTLY BOUGHT TOGETHER)
# ========================================

def get_frequently_bought_together(product, limit=3):
    """Obtener productos frecuentemente comprados juntos"""
    from checkout.models import Order, CartItem
    
    # Encontrar órdenes que incluyen este producto
    orders_with_product = Order.objects.filter(
        items__product=product
    ).values_list('id', flat=True)
    
    if not orders_with_product:
        # Si no hay órdenes, devolver productos relacionados
        return Product.objects.filter(
            fragrance_family=product.fragrance_family
        ).exclude(id=product.id)[:limit]
    
    # Productos en esas órdenes (excluyendo el actual)
    related_products = Product.objects.filter(
        cartitem__order_id__in=orders_with_product
    ).exclude(id=product.id).annotate(
        frequency=Count('id')
    ).order_by('-frequency')[:limit]
    
    return related_products


# ========================================
# NOTIFICACIONES DE STOCK
# ========================================

@login_required
def notify_when_available(request, product_id):
    """Notificar cuando el producto esté disponible"""
    from .models import StockAlert
    
    product = get_object_or_404(Product, id=product_id)
    
    alert, created = StockAlert.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'email': request.user.email}
    )
    
    if created:
        message = f'Te avisaremos cuando {product.name} esté disponible'
    else:
        message = f'Ya estás suscrito a las notificaciones de {product.name}'
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': message})
    
    messages.success(request, message)
    return redirect('products:product_detail', slug=product.slug)


# ============ FUNCIONES AUXILIARES PARA URLs ============

@require_POST
def remove_from_comparison(request, product_id):
    """Eliminar producto de la comparación"""
    comparison_list = request.session.get('comparison_list', [])
    if product_id in comparison_list:
        comparison_list.remove(product_id)
        request.session['comparison_list'] = comparison_list
    
    return JsonResponse({'success': True})


@require_POST
def clear_comparison(request):
    """Limpiar toda la comparación"""
    request.session['comparison_list'] = []
    return JsonResponse({'success': True})


@login_required
@require_POST
def save_comparison(request):
    """Guardar comparación actual del usuario"""
    from .models_extended import ProductComparison
    
    comparison_list = request.session.get('comparison_list', [])
    if not comparison_list:
        return JsonResponse({'success': False, 'message': 'No hay productos para guardar'})
    
    # Crear o actualizar comparación
    comparison, created = ProductComparison.objects.get_or_create(
        user=request.user,
        defaults={'name': f'Comparación {timezone.now().strftime("%d/%m/%Y")}'}
    )
    
    comparison.products.set(comparison_list)
    
    return JsonResponse({'success': True, 'message': 'Comparación guardada'})

