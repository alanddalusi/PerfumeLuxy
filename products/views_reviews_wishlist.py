"""
Views para Reviews y Wishlist
Funcionalidad estilo Shopify/Amazon
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Avg, Count
from .models import Product, Review, Wishlist
from django.views.decorators.http import require_POST


# ========================================
# REVIEWS
# ========================================

@login_required
@require_POST
def add_review(request, product_id):
    """Añadir una reseña a un producto"""
    product = get_object_or_404(Product, id=product_id)
    
    # Verificar si ya tiene review
    if Review.objects.filter(product=product, user=request.user).exists():
        messages.warning(request, 'Ya has dejado una reseña para este producto.')
        return redirect('products:product_detail', product_id=product.id)
    
    rating = request.POST.get('rating')
    title = request.POST.get('title')
    comment = request.POST.get('comment')
    
    if not rating or not title or not comment:
        messages.error(request, 'Por favor completa todos los campos.')
        return redirect('products:product_detail', product_id=product.id)
    
    Review.objects.create(
        product=product,
        user=request.user,
        rating=int(rating),
        title=title,
        comment=comment,
        is_approved=True  # Auto-aprobar o cambiar a False para moderación
    )
    
    messages.success(request, '¡Gracias por tu reseña!')
    return redirect('products:product_detail', product_id=product.id)


@login_required
def delete_review(request, review_id):
    """Eliminar una reseña propia"""
    review = get_object_or_404(Review, id=review_id, user=request.user)
    product_id = review.product.id
    review.delete()
    messages.success(request, 'Reseña eliminada correctamente.')
    return redirect('products:product_detail', product_id=product_id)


@login_required
@require_POST
def mark_review_helpful(request, review_id):
    """Marcar una reseña como útil"""
    review = get_object_or_404(Review, id=review_id)
    review.helpful_count += 1
    review.save()
    
    return JsonResponse({
        'success': True,
        'helpful_count': review.helpful_count
    })


# ========================================
# WISHLIST
# ========================================

@login_required
def toggle_wishlist(request, product_id):
    """Añadir/quitar producto de wishlist"""
    product = get_object_or_404(Product, id=product_id)
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    
    # Verificar si ya está en wishlist
    if product in wishlist.products.all():
        wishlist.products.remove(product)
        message = f'{product.name} eliminado de favoritos'
        action = 'removed'
    else:
        wishlist.products.add(product)
        message = f'{product.name} añadido a favoritos'
        action = 'added'
    
    # Si es AJAX, devolver JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'action': action
        })
    
    messages.success(request, message)
    return redirect(request.META.get('HTTP_REFERER', 'products:products'))


@login_required
def view_wishlist(request):
    """Ver lista de deseos completa"""
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    products = wishlist.products.all()
    
    context = {
        'wishlist_items': [{'product': p} for p in products],
        'total_items': products.count()
    }
    
    return render(request, 'products/wishlist.html', context)


@login_required
def clear_wishlist(request):
    """Vaciar toda la wishlist"""
    wishlist = Wishlist.objects.filter(user=request.user).first()
    if wishlist:
        wishlist.products.clear()
        messages.success(request, 'Lista de deseos vaciada.')
    
    return redirect('products:view_wishlist')


def is_in_wishlist(user, product):
    """Helper function para verificar si un producto está en wishlist"""
    if not user.is_authenticated:
        return False
    
    wishlist = Wishlist.objects.filter(user=user).first()
    if not wishlist:
        return False
    
    return product in wishlist.products.all()


# ========================================
# RECOMENDADOR DE PRODUCTOS
# ========================================

def get_related_products(product, limit=4):
    """
    Obtener productos relacionados basados en:
    - Misma familia olfativa
    - Misma categoría
    - Precio similar
    """
    related = Product.objects.filter(
        fragrance_family=product.fragrance_family
    ).exclude(id=product.id)[:limit]
    
    # Si no hay suficientes de la misma familia, buscar por categoría
    if related.count() < limit:
        category_products = Product.objects.filter(
            category=product.category
        ).exclude(id=product.id).exclude(id__in=[p.id for p in related])
        
        remaining = limit - related.count()
        related = list(related) + list(category_products[:remaining])
    
    return related


def get_best_sellers(limit=8):
    """Obtener productos más vendidos (basado en número de reviews)"""
    return Product.objects.annotate(
        review_count=Count('reviews')
    ).order_by('-review_count')[:limit]


def get_top_rated(limit=8):
    """Obtener productos mejor valorados"""
    return Product.objects.annotate(
        avg_rating=Avg('reviews__rating')
    ).filter(
        avg_rating__gte=4
    ).order_by('-avg_rating')[:limit]
