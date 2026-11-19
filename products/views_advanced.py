from django.conf import settings
"""
Vistas para funcionalidades avanzadas de perfumería
Tamaños, Muestras, Comparador, Quiz, Perfil Olfativo
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from allauth.account.models import EmailAddress
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Avg, Count, Min, Max
from django.views.decorators.http import require_POST
from django.utils import timezone
from checkout.store_mode import require_live_store, sales_enabled
from home.notices import AVAILABILITY_CONSENT_VERSION, rate_allowed, request_confirmation

from .models import Product, FragranceFamily, FragranceNote
from .presentation import public_cover
from .models_extended import (
    ProductSize, SampleRequest, UserFragranceProfile,
    ProductComparison, FragranceEvolution
)


# ========================================
# SELECTOR DE TAMAÑOS
# ========================================

def get_product_sizes(request, product_id):
    """API para obtener tamaños disponibles de un producto"""
    product = get_object_or_404(Product.objects.published().prefetch_related("catalog_images"), id=product_id)
    sizes = product.sizes.all()
    
    cover = public_cover(product)
    commerce = sales_enabled()
    data = [{
        'id': size.id,
        'size_ml': size.size_ml,
        'price': str(size.price) if commerce else None,
        'price_per_ml': size.price_per_ml if commerce else None,
        'stock': size.stock if commerce else None,
        'in_stock': size.in_stock if commerce else None,
        'is_popular': size.is_popular if commerce else False,
        'is_best_value': size.is_best_value if commerce else False,
        'image_url': cover
    } for size in sizes]
    
    return JsonResponse({'sizes': data})


# ========================================
# SISTEMA DE MUESTRAS
# ========================================

@require_live_store
@login_required
def request_sample(request, product_id):
    """Solicitar muestra de un producto"""
    product = get_object_or_404(Product.objects.published(), id=product_id)
    
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
        user=request.user, product__publication_status=Product.Publication.APPROVED,
    ).select_related("product").prefetch_related("product__catalog_images")
    
    context = {
        'samples': samples
    }
    return render(request, 'products/my_samples.html', context)


# ========================================
# COMPARADOR DE PERFUMES
# ========================================

def compare_products(request):
    """Comparar hasta 3 productos lado a lado"""
    product_ids = []
    for value in request.GET.getlist("products"):
        for item in value.split(","):
            if item.isascii() and item.isdigit() and len(item) <= 19 and int(item) <= 2**63 - 1:
                product_ids.append(int(item))
    products = list(Product.objects.published().filter(
        pk__in=list(dict.fromkeys(product_ids))[:3]
    ).select_related("brand", "fragrance_family").prefetch_related("fragrance_notes", "catalog_images"))
    if len(products) < 2:
        messages.error(request, "Selecciona al menos 2 productos para comparar.")
        return redirect("products:products")

    return render(request, "products/compare.html", {"products": products})

@login_required
@require_POST
def add_to_comparison(request, product_id):
    """Añadir producto a lista de comparación (sesión)"""
    get_object_or_404(Product.objects.published(), pk=product_id)
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
    if request.method == 'POST':
        profile, _ = UserFragranceProfile.objects.get_or_create(user=request.user)
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
    profile = UserFragranceProfile.objects.filter(user=request.user).first()
    recommendations = profile.get_recommendations(limit=8) if profile else []
    
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
    products = Product.objects.published().all()
    
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
        return Product.objects.published().filter(
            fragrance_family=product.fragrance_family
        ).exclude(id=product.id)[:limit]
    
    # Productos en esas órdenes (excluyendo el actual)
    related_products = Product.objects.published().filter(
        cartitem__order_id__in=orders_with_product
    ).exclude(id=product.id).annotate(
        frequency=Count('id')
    ).order_by('-frequency')[:limit]
    
    return related_products


# ========================================
# NOTIFICACIONES DE STOCK
# ========================================

@login_required
@require_POST
def notify_when_available(request, product_id):
    """Notificar cuando el producto esté disponible"""
    from .models import StockAlert
    
    product = get_object_or_404(Product.objects.published(), id=product_id)
    if not settings.NOTICE_SIGNUPS_OPEN:
        message = "Los avisos de disponibilidad se activarán muy pronto."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": message}, status=503)
        messages.info(request, message)
        return redirect("products:product_detail", slug=product.slug)

    verified_email = EmailAddress.objects.filter(
        user=request.user, email__iexact=request.user.email, verified=True
    ).first()
    if verified_email is None:
        message = "Verifica el correo de tu cuenta para solicitar avisos."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": message}, status=400)
        messages.error(request, message)
        return redirect("products:product_detail", slug=product.slug)

    if request.POST.get("consent") != "on":
        messages.error(request, "Confirma que quieres recibir el aviso de disponibilidad.")
        return redirect("products:product_detail", slug=product.slug)
    if not rate_allowed(request):
        return JsonResponse({"success": False, "message": "Inténtalo más tarde."}, status=429)
    alert, _ = StockAlert.objects.get_or_create(
        user=request.user, product=product, defaults={"email": verified_email.email},
    )
    request_confirmation(
        request, alert, "disponibilidad", email=verified_email.email,
        version=AVAILABILITY_CONSENT_VERSION, product_name=product.name,
    )
    message = "Si el aviso está pendiente, recibirás un correo para confirmarlo."

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
    
    comparison.products.set(Product.objects.published().filter(pk__in=comparison_list))
    
    return JsonResponse({'success': True, 'message': 'Comparación guardada'})

