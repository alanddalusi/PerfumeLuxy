from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count, Exists, OuterRef
from django.db.models.functions import Lower
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe

from checkout.store_mode import sales_enabled
from eau_royal.seo import SEOManager

from .models import (
    Brand, CatalogImage, Product, Category, Gender, FragranceFamily,
    FragranceNote, Review, ReviewImage, Wishlist,
    PriceAlert, StockAlert
)
from .catalog import catalog_filter_url, catalog_listing, normalize_search, search_products
from .forms import ProductForm
from .presentation import public_cover, public_gallery


def all_products(request):
    params = request.GET
    products, filter_context = catalog_listing(params)
    products = products.prefetch_related("catalog_images")
    if request.user.is_authenticated:
        products = products.annotate(
            saved_to_wishlist=Exists(Wishlist.objects.filter(user=request.user, products=OuterRef("pk")))
        )

    paginator = Paginator(products, 60)
    page = paginator.get_page(params.get("page"))
    for product in page:
        product.storefront_image = public_cover(product)

    seo = SEOManager(request)
    canonical_params = {"page": page.number} if page.number > 1 else {}
    catalog_url = catalog_filter_url(**canonical_params) if canonical_params else reverse("products:products")
    catalog_metadata = seo.get_meta_tags(
        title="Catálogo de perfumes | Perfumería El Buen Olor",
        description="Explora el catálogo de perfumes por marca, familia olfativa y concentración.",
        canonical=seo.get_canonical_url(catalog_url),
    )
    if filter_context["catalog_filtered"] or params.get("sort") or params.get("direction"):
        catalog_metadata["robots"] = "noindex, follow"

    page_params = params.copy()
    page_params.pop("page", None)

    def page_url(number):
        return f"?{page_params.urlencode()}&page={number}" if page_params else f"?page={number}"

    request.session["products_url"] = request.get_full_path()
    return render(request, "products/products.html", {
        "products": page,
        **filter_context,
        "seo_data": catalog_metadata,
        "total_products": paginator.count,
        "previous_page_url": page_url(page.previous_page_number()) if page.has_previous() else "",
        "next_page_url": page_url(page.next_page_number()) if page.has_next() else "",
    })


@require_safe
def catalog_image(request, image_id, variant):
    if variant not in {"web", "thumb"}:
        raise Http404
    image = get_object_or_404(
        CatalogImage, pk=image_id, approved_at__isnull=False, withdrawn_at__isnull=True,
        product__publication_status=Product.Publication.APPROVED,
    )
    asset = image.asset if variant == "web" else image.thumbnail
    if not asset:
        raise Http404
    try:
        response = FileResponse(asset.open("rb"), content_type="image/webp")
    except OSError:
        raise Http404 from None
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_safe
def search_suggestions(request):
    query = normalize_search(request.GET.get("q", ""))
    if len(query) < 2:
        return JsonResponse({"results": []})
    products = search_products(Product.objects.published().select_related("brand"), query)
    return JsonResponse({"results": [
        {
            "name": product.name,
            "brand": product.brand.name if product.brand else "",
            "url": product.get_absolute_url(),
        }
        for product in products.order_by(Lower("name"), "pk")[:8]
    ]})


def fragrance_families_guide(request):
    """Guía educativa de familias olfativas"""
    
    template = "products/fragrance_families.html"
    
    # Obtener todas las familias con conteo de productos
    fragrance_families = FragranceFamily.objects.annotate(
        product_count=Count('products', filter=Q(products__publication_status=Product.Publication.APPROVED))
    ).order_by('name')
    
    context = {
        "fragrance_families": fragrance_families,
        "seo_data": SEOManager(request).get_meta_tags(
            title="Guía de familias olfativas | Perfumería El Buen Olor",
            description="Aprende a leer las fichas y a comparar familias, notas, concentraciones y formatos.",
            canonical=request.build_absolute_uri(reverse("products:fragrance_families")),
        ),
    }
    
    return render(request, template, context)


def product_detail(request, slug):
    """View function that returns individual product details"""

    template = "products/product_detail_improved.html"
    products = Product.objects.published().select_related(
        "brand", "category", "gender", "fragrance_family"
    ).prefetch_related("fragrance_notes", "sizes", "catalog_images")
    product = products.filter(slug=slug).first()
    if product is None:
        if slug.isascii() and slug.isdigit() and len(slug) <= 19 and int(slug) <= 2**63 - 1:
            legacy_product = get_object_or_404(Product.objects.published(), pk=int(slug))
            return redirect(legacy_product.get_absolute_url(), permanent=True)
        raise Http404

    products_url = request.session.get('products_url', '/products/')

    # Obtener reviews del producto
    reviews = list(product.reviews.filter(is_approved=True).select_related("user"))
    review_count = len(reviews)
    avg_rating = sum(review.rating for review in reviews) / review_count if review_count else 0

    # Productos similares (misma familia olfativa o marca)
    related_filter = Q(pk__in=[])
    if product.fragrance_family_id:
        related_filter |= Q(fragrance_family_id=product.fragrance_family_id)
    if product.brand_id:
        related_filter |= Q(brand_id=product.brand_id)
    similar_products = list(Product.objects.published().filter(related_filter).exclude(
        id=product.id
    ).select_related("brand").prefetch_related("catalog_images").order_by("name", "pk")[:6])
    for related in similar_products:
        related.storefront_image = public_cover(related)


    # Verificar si está en la wishlist del usuario
    in_wishlist = False
    has_stock_alert = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, products=product).exists()
        has_stock_alert = StockAlert.objects.filter(user=request.user, product=product, confirmed_at__isnull=False, withdrawn_at__isnull=True).exists()

    # SEO: Generar meta tags optimizados
    seo = SEOManager(request)
    seo_data = seo.get_product_meta(product)
    
    # SEO: Breadcrumb
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Productos', 'url': '/products/'},
    ]
    if product.gender:
        breadcrumb_items.append({
            'name': product.gender.get_friendly_name(),
            'url': catalog_filter_url(gender=product.gender.db_name)
        })
    if product.brand:
        breadcrumb_items.append({
            'name': product.brand.name,
            'url': catalog_filter_url(brand=product.brand.db_name)
        })
    breadcrumb_items.append({'name': product.name, 'url': None})
    
    # SEO: Schema.org para producto
    product_schema = seo.generate_product_schema(product, avg_rating, review_count)
    breadcrumb_schema = seo.generate_breadcrumb_schema(breadcrumb_items)

    sizes = list(product.sizes.all())
    gallery = public_gallery(product)
    note_groups = [
        (label, [note for note in product.fragrance_notes.all() if note.note_type == kind])
        for kind, label in FragranceNote.NOTE_TYPES
    ]

    context = {
        "product": product,
        "gallery": gallery,
        "sizes": sizes,
        "cart_sizes": [size for size in sizes if size.size_ml in (30, 50, 100) and size.in_stock],
        "note_groups": note_groups,
        "has_notes": any(notes for _, notes in note_groups),
        "has_stock_alert": has_stock_alert,
        "products_url": products_url,
        "reviews": reviews,
        "avg_rating": round(avg_rating, 1),
        "review_count": review_count,
        "similar_products": similar_products,
        "in_wishlist": in_wishlist,
        "seo_data": seo_data,
        "breadcrumb_items": breadcrumb_items,
        "product_schema": product_schema,
        "brand_url": catalog_filter_url(brand=product.brand.db_name) if product.brand else "",
        "category_url": catalog_filter_url(category=product.category.db_name) if product.category else "",
        "breadcrumb_schema": breadcrumb_schema,
    }

    return render(request, template, context)


@login_required
def add_product(request):
    """Add a product to the store"""
    if not request.user.is_superuser:
        messages.error(request, "Sorry, only store owners can do that.")
        return redirect(reverse("home:index"))

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, "Successfully added product!")
            return redirect("admin:products_product_change", product.pk)
        else:
            messages.error(
                request,
                (
                    "Failed to add product. "
                    "Please ensure the form is valid."
                )
            )
    else:
        form = ProductForm()

    template = "products/add_product.html"
    context = {
        "form": form,
    }

    return render(request, template, context)


@login_required
def edit_product(request, product_id):
    """Edit a product in the store"""
    if not request.user.is_superuser:
        messages.error(request, "Sorry, only store owners can do that.")
        return redirect(reverse("home:index"))

    product = get_object_or_404(Product, pk=product_id)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Successfully updated product!")
            return redirect("admin:products_product_change", product.pk)
        else:
            messages.error(
                request,
                (
                    "Failed to update product. "
                    "Please ensure the form is valid."
                )
            )
    else:
        form = ProductForm(instance=product)
        messages.info(request, f"You are editing {product.name}")

    template = "products/edit_product.html"
    context = {
        "form": form,
        "product": product,
    }

    return render(request, template, context)


@login_required
@require_POST
def delete_product(request, product_id):
    """Delete a product from the store"""
    if not request.user.is_superuser:
        messages.error(request, "Sorry, only store owners can do that.")
        return redirect(reverse("home:index"))

    product = get_object_or_404(Product, pk=product_id)
    if product.publication_history.exists() or product.catalog_images.exists():
        return HttpResponseForbidden()
    if not sales_enabled() and product.cartitem_set.exists():
        return HttpResponseForbidden()
    product.delete()
    messages.success(request, "Product deleted!")
    return redirect(reverse("products:products"))


# Wishlist Views
@login_required
def wishlist(request):
    """Vista de la lista de deseos del usuario"""
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    products = wishlist.products.published()

    context = {
        'wishlist_products': products,
    }
    return render(request, 'products/wishlist.html', context)


@login_required
@require_POST
def toggle_wishlist(request, product_id):
    """Añadir o quitar producto de la wishlist"""
    product = get_object_or_404(Product.objects.published(), pk=product_id)
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)

    if wishlist.products.filter(id=product_id).exists():
        wishlist.products.remove(product)
        in_wishlist = False
        message = f'{product.name} eliminado de tu lista de deseos'
    else:
        wishlist.products.add(product)
        in_wishlist = True
        message = f'{product.name} añadido a tu lista de deseos'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'in_wishlist': in_wishlist,
            'message': message
        })
    else:
        messages.success(request, message)
        return redirect(request.META.get('HTTP_REFERER', 'products'))


# Product Comparison
def compare_products(request):
    """Comparar hasta 4 productos"""
    product_ids = request.GET.getlist('products')
    
    if len(product_ids) < 2:
        messages.warning(request, 'Selecciona al menos 2 productos para comparar')
        return redirect('products')
    
    if len(product_ids) > 4:
        messages.warning(request, 'Puedes comparar un máximo de 4 productos')
        product_ids = product_ids[:4]
    
    products = Product.objects.published().filter(id__in=product_ids)
    
    context = {
        'products': products,
    }
    return render(request, 'products/compare.html', context)


# Reviews
@login_required
@require_POST
def add_review(request, product_id):
    """Añadir una review a un producto"""
    product = get_object_or_404(Product.objects.published(), pk=product_id)
    
    # Verificar si el usuario ya ha dejado una review
    if Review.objects.filter(product=product, user=request.user).exists():
        messages.error(request, 'Ya has dejado una reseña para este producto')
        return redirect('product_detail', product_id=product_id)
    
    rating = request.POST.get('rating')
    title = request.POST.get('title')
    comment = request.POST.get('comment')
    skin_type = request.POST.get('skin_type', '')
    duration_experienced = request.POST.get('duration_experienced', '')
    
    if not all([rating, title, comment]):
        messages.error(request, 'Por favor completa todos los campos requeridos')
        return redirect('product_detail', product_id=product_id)
    
    try:
        review = Review.objects.create(
            product=product,
            user=request.user,
            rating=int(rating),
            title=title,
            comment=comment,
            skin_type=skin_type if skin_type else None,
            duration_experienced=duration_experienced if duration_experienced else None,
        )
        
        # Manejar imágenes subidas
        images = request.FILES.getlist('images')
        for image in images[:5]:  # Máximo 5 imágenes
            ReviewImage.objects.create(review=review, image=image)
        
        messages.success(request, '¡Gracias por tu reseña!')
    except Exception as e:
        messages.error(request, f'Error al guardar la reseña: {str(e)}')
    
    return redirect('product_detail', product_id=product_id)


# Price Alerts
@login_required
@require_POST
def create_price_alert(request, product_id):
    """Crear alerta de precio"""
    product = get_object_or_404(Product.objects.published(), pk=product_id)
    target_price = request.POST.get('target_price')
    
    if not target_price:
        messages.error(request, 'Por favor indica el precio objetivo')
        return redirect('product_detail', product_id=product_id)
    
    try:
        alert, created = PriceAlert.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'target_price': target_price}
        )
        
        if not created:
            alert.target_price = target_price
            alert.is_active = True
            alert.save()
            messages.success(request, 'Alerta de precio actualizada')
        else:
            messages.success(request, 'Te avisaremos cuando baje el precio')
    except Exception as e:
        messages.error(request, f'Error al crear la alerta: {str(e)}')
    
    return redirect('product_detail', product_id=product_id)


# Stock Alerts
@login_required
@require_POST
def create_stock_alert(request, product_id):
    """Crear alerta de stock"""
    product = get_object_or_404(Product.objects.published(), pk=product_id)
    
    if product.in_stock:
        messages.info(request, 'Este producto está disponible')
        return redirect('product_detail', product_id=product_id)
    
    try:
        alert, created = StockAlert.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'email': request.user.email}
        )
        
        if created:
            messages.success(request, 'Te avisaremos cuando vuelva a estar disponible')
        else:
            messages.info(request, 'Ya tienes una alerta activa para este producto')
    except Exception as e:
        messages.error(request, f'Error al crear la alerta: {str(e)}')
    
    return redirect('product_detail', product_id=product_id)


# Recommendation Quiz
def perfume_quiz(request):
    """Quiz de recomendación de perfumes"""
    return render(request, 'products/quiz.html')


@require_POST
def quiz_results(request):
    """Procesar resultados del quiz y mostrar recomendaciones"""
    # Obtener respuestas del quiz
    intensity_pref = request.POST.get('intensity')
    occasion_pref = request.POST.get('occasion')
    season_pref = request.POST.get('season')
    family_pref = request.POST.get('family')
    
    # Filtrar productos basándose en las preferencias
    products = Product.objects.published().filter(stock__gt=0)
    
    if intensity_pref:
        products = products.filter(intensity=intensity_pref)
    if occasion_pref:
        products = products.filter(occasion=occasion_pref)
    if season_pref:
        products = products.filter(season__in=[season_pref, 'all'])
    if family_pref:
        products = products.filter(fragrance_family__name=family_pref)
    
    # Ordenar por rating
    products = products.annotate(
        avg_rating=Avg('reviews__rating')
    ).order_by('-avg_rating')[:12]
    
    context = {
        'recommended_products': products,
        'preferences': {
            'intensity': intensity_pref,
            'occasion': occasion_pref,
            'season': season_pref,
            'family': family_pref,
        }
    }
    
    return render(request, 'products/quiz_results.html', context)
