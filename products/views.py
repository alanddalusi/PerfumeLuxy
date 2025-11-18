from django.forms import ValidationError
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, Min, Avg, Count
from django.db.models.functions import Lower
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import (
    Brand, Product, Category, Gender, FragranceFamily,
    FragranceNote, Review, ReviewImage, Wishlist,
    PriceAlert, StockAlert
)
from .forms import ProductForm


def all_products(request):
    """
    View function that returns all products,
    including search and sorting queries
    """

    def get_dict_value(dictionary):
        """Function that returns a value given a dictionary key"""
        for key, value in dictionary.items():
            return value

    template = "products/products.html"

    # Filter valid products and order by creation date (newest first)
    products = Product.objects.filter(
        id__isnull=False
    ).order_by('-created_at')
    
    total_products = products.count()

    brand_list = Brand.objects.all()
    gender_list = Gender.objects.all()
    category_list = Category.objects.all()
    fragrance_family_list = FragranceFamily.objects.all()

    min_price_dict = Product.objects.aggregate(Min("price"))
    max_price_dict = Product.objects.aggregate(Max("price"))
    min_price = round(get_dict_value(min_price_dict))
    max_price = round(get_dict_value(max_price_dict))

    query = None
    categories = None
    genders = None
    brands = None
    discounts = None
    fragrance_families = None
    intensities = None
    durations = None
    occasions = None
    seasons = None
    in_stock_only = False
    sort = None
    direction = None
    price_from = min_price
    price_to = max_price

    if request.GET:
        if "products_url" in request.GET:
            url = request.GET.get("products_url")
            request.session['products_url'] = url
        if "price_from" and "price_to" in request.GET:
            price_from = request.GET.get("price_from")
            price_to = request.GET.get("price_to")
            products = products.filter(price__range=[price_from, price_to])
            total_products = products.count()

        if "sort" in request.GET:
            sortkey = request.GET["sort"]
            sort = sortkey
            if sortkey == "name":
                sortkey = "lower_name"
                products = products.annotate(lower_name=Lower("name"))
            if "direction" in request.GET:
                direction = request.GET["direction"]
                if direction == "desc":
                    sortkey = f"-{sortkey}"
            products = products.order_by(sortkey)
            total_products = products.count()

        if "category" in request.GET:
            categories = request.GET.getlist("category")
            products = products.filter(category__name__in=categories)
            categories = Category.objects.filter(name__in=categories)
            total_products = products.count()
            if not categories:
                messages.error(
                    request,
                    (f"'{categories}' does not exist in Categories table")
                )
                return redirect(reverse("products"))

        if "gender" in request.GET:
            genders = request.GET["gender"].split(",")
            products = products.filter(gender__db_name__in=genders)
            genders = Gender.objects.filter(db_name__in=genders)
            total_products = products.count()
            if not genders:
                messages.error(
                    request,
                    (f"'{genders}' does not exist in Gender table")
                )
                return redirect(reverse("products"))

        if "brand" in request.GET:
            brands = request.GET.getlist("brand")
            products = products.filter(brand__db_name__in=brands)
            brands = Brand.objects.filter(db_name__in=brands)
            total_products = products.count()
            if not brands:
                messages.error(
                    request, (f"'{brands}' does not exist in Brand table"))
                return redirect(reverse("products"))

        if "has_discount" in request.GET:
            try:
                discounts = request.GET["has_discount"]
                products = products.filter(has_discount=discounts)
                discounts = Product.objects.filter(has_discount=discounts)
                total_products = products.count()
            except (ValidationError) as e:
                if isinstance(e, ValidationError):
                    messages.error(
                        request,
                        (
                            f"'{discounts}' is not a boolean value. "
                            f"Please enter either 'True' or 'False'"
                        ),
                    )
                    return redirect(reverse("products"))

        if "fragrance_family" in request.GET:
            fragrance_families = request.GET.getlist("fragrance_family")
            products = products.filter(fragrance_family__name__in=fragrance_families)
            total_products = products.count()

        if "intensity" in request.GET:
            intensities = request.GET.getlist("intensity")
            products = products.filter(intensity__in=intensities)
            total_products = products.count()

        if "duration" in request.GET:
            durations = request.GET.getlist("duration")
            products = products.filter(duration__in=durations)
            total_products = products.count()

        if "occasion" in request.GET:
            occasions = request.GET.getlist("occasion")
            products = products.filter(occasion__in=occasions)
            total_products = products.count()

        if "season" in request.GET:
            seasons = request.GET.getlist("season")
            products = products.filter(season__in=seasons)
            total_products = products.count()

        if "in_stock" in request.GET:
            in_stock_only = request.GET.get("in_stock") == "true"
            if in_stock_only:
                products = products.filter(stock__gt=0)
                total_products = products.count()

        if "q" in request.GET:
            query = request.GET["q"]
            if not query:
                messages.error(
                    request, ("You didn't enter any search criteria!"))
                return redirect(reverse("products"))

            queries = (
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(brand__name__icontains=query)
                | Q(category__name__icontains=query)
            )
            products = products.filter(queries)
            total_products = products.count()

    current_sorting = f"{sort}_{direction}"

    page_number = request.GET.get("page", 1)
    paginator = Paginator(products, 60)

    try:
        products = paginator.page(page_number)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    request.session['products_url'] = request.get_full_path()

    context = {
        "products": products,
        "brand_list": brand_list,
        "category_list": category_list,
        "gender_list": gender_list,
        "fragrance_family_list": fragrance_family_list,
        "total_products": total_products,
        "search_term": query,
        "current_categories": categories,
        "current_genders": genders,
        "current_brands": brands,
        "current_discounts": discounts,
        "current_fragrance_families": fragrance_families,
        "current_intensities": intensities,
        "current_durations": durations,
        "current_occasions": occasions,
        "current_seasons": seasons,
        "in_stock_only": in_stock_only,
        "current_sorting": current_sorting,
        "min_price": min_price,
        "max_price": max_price,
        "price_from": price_from,
        "price_to": price_to,
    }

    return render(request, template, context)


def product_detail(request, product_id):
    """View function that returns individual product details"""

    template = "products/product_detail_improved.html"
    product = get_object_or_404(Product, pk=product_id)

    products_url = request.session.get('products_url', '/products/')

    # Obtener reviews del producto
    reviews = product.reviews.filter(is_approved=True).order_by('-created_at')
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    review_count = reviews.count()

    # Productos similares (misma familia olfativa o marca)
    similar_products = Product.objects.filter(
        Q(fragrance_family=product.fragrance_family) |
        Q(brand=product.brand)
    ).exclude(id=product.id)[:6]

    # Verificar si está en la wishlist del usuario
    in_wishlist = False
    if request.user.is_authenticated:
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        in_wishlist = wishlist.products.filter(id=product.id).exists()

    context = {
        "product": product,
        "products_url": products_url,
        "reviews": reviews,
        "avg_rating": round(avg_rating, 1),
        "review_count": review_count,
        "similar_products": similar_products,
        "in_wishlist": in_wishlist,
    }

    return render(request, template, context)


@login_required
def add_product(request):
    """Add a product to the store"""
    if not request.user.is_superuser:
        messages.error(request, "Sorry, only store owners can do that.")
        return redirect(reverse("home"))

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, "Successfully added product!")
            return redirect(reverse("product_detail", args=[product.id]))
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
        return redirect(reverse("home"))

    product = get_object_or_404(Product, pk=product_id)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Successfully updated product!")
            return redirect(reverse("product_detail", args=[product.id]))
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
def delete_product(request, product_id):
    """Delete a product from the store"""
    if not request.user.is_superuser:
        messages.error(request, "Sorry, only store owners can do that.")
        return redirect(reverse("home"))

    product = get_object_or_404(Product, pk=product_id)
    product.delete()
    messages.success(request, "Product deleted!")
    return redirect(reverse("products"))


# Wishlist Views
@login_required
def wishlist(request):
    """Vista de la lista de deseos del usuario"""
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    products = wishlist.products.all()

    context = {
        'wishlist_products': products,
    }
    return render(request, 'products/wishlist.html', context)


@login_required
@require_POST
def toggle_wishlist(request, product_id):
    """Añadir o quitar producto de la wishlist"""
    product = get_object_or_404(Product, pk=product_id)
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
    
    products = Product.objects.filter(id__in=product_ids)
    
    context = {
        'products': products,
    }
    return render(request, 'products/compare.html', context)


# Reviews
@login_required
@require_POST
def add_review(request, product_id):
    """Añadir una review a un producto"""
    product = get_object_or_404(Product, pk=product_id)
    
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
    product = get_object_or_404(Product, pk=product_id)
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
    product = get_object_or_404(Product, pk=product_id)
    
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
    products = Product.objects.filter(stock__gt=0)
    
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
