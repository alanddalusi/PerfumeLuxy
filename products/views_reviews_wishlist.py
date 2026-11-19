"""
Views para Reviews y Wishlist
Funcionalidad estilo Shopify/Amazon
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Avg, Count
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import ReviewForm
from .models import Product, Review, Wishlist
from django.views.decorators.http import require_POST


# ========================================
# REVIEWS
# ========================================

@login_required
@require_POST
def add_review(request, product_id):
    """Añadir una reseña a un producto"""
    product = get_object_or_404(Product.objects.published(), id=product_id)
    
    # Verificar si ya tiene review
    if Review.objects.filter(product=product, user=request.user).exists():
        messages.warning(request, 'Ya has dejado una reseña para este producto.')
        return redirect('products:product_detail', slug=product.slug)
    
    form = ReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Completa la reseña con una valoración de 1 a 5.')
        return redirect('products:product_detail', slug=product.slug)

    review = form.save(commit=False)
    review.product = product
    review.user = request.user
    review.is_approved = False
    review.save()
    messages.success(request, 'Tu reseña se ha enviado para revisión.')
    return redirect('products:product_detail', slug=product.slug)


@login_required
@require_POST
def delete_review(request, review_id):
    """Eliminar una reseña propia"""
    review = get_object_or_404(Review, id=review_id, user=request.user)
    slug = review.product.slug
    review.delete()
    messages.success(request, 'Reseña eliminada correctamente.')
    return redirect('products:product_detail', slug=slug)


@login_required
@require_POST
def mark_review_helpful(request, review_id):
    """Marcar una reseña como útil"""
    review = get_object_or_404(Review, id=review_id, product__publication_status=Product.Publication.APPROVED)
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
@require_POST
def toggle_wishlist(request, product_id):
    """Añadir/quitar producto de wishlist"""
    product = get_object_or_404(Product.objects.published(), id=product_id)
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
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("products:products")


@login_required
def view_wishlist(request):
    """Ver lista de deseos completa"""
    products = Product.objects.published().filter(wishlisted_by__user=request.user).select_related("brand").prefetch_related("catalog_images")
    context = {'wishlist_products': products}
    
    return render(request, 'products/wishlist.html', context)


@login_required
@require_POST
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
    related = Product.objects.published().filter(
        fragrance_family=product.fragrance_family
    ).exclude(id=product.id)[:limit]
    
    # Si no hay suficientes de la misma familia, buscar por categoría
    if related.count() < limit:
        category_products = Product.objects.published().filter(
            category=product.category
        ).exclude(id=product.id).exclude(id__in=[p.id for p in related])
        
        remaining = limit - related.count()
        related = list(related) + list(category_products[:remaining])
    
    return related


def get_best_sellers(limit=8):
    """Obtener productos más vendidos (basado en número de reviews)"""
    return Product.objects.published().annotate(
        review_count=Count('reviews')
    ).order_by('-review_count')[:limit]


def get_top_rated(limit=8):
    """Obtener productos mejor valorados"""
    return Product.objects.published().annotate(
        avg_rating=Avg('reviews__rating')
    ).filter(
        avg_rating__gte=4
    ).order_by('-avg_rating')[:limit]
