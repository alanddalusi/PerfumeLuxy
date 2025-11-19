from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from .forms import SubscribeForm
from products.models import Product


def index(request):
    """View to return homepage"""

    template = "home/index.html"

    # Get featured/top selling products (valid products only)
    top_products = Product.objects.filter(
        id__isnull=False,
        stock__gt=0
    ).order_by('-rating')[:8]  # Top 8 rated products

    if request.method == "POST":
        form = SubscribeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Subscription created successfully!")
            return redirect(reverse("home"))
        else:
            messages.error(
                request,
                (
                    "Something went wrong during subscription creation"
                    "Please try again later."
                ),
            )
    else:
        form = SubscribeForm()

    # SEO: Generar meta tags para home
    from eau_royal.seo import SEOManager
    seo = SEOManager(request)
    seo_data = seo.get_meta_tags(
        title="PerfumeLuxe - Perfumes Auténticos de Lujo | Envío Gratis +50€",
        description="Descubre PerfumeLuxe: fragancias 100% auténticas de las mejores marcas. Chanel, Dior, Tom Ford, Gucci y más. Envío gratis +50€, devolución 30 días. Compra con garantía total.",
        keywords="perfumes auténticos, fragancias de lujo, perfume mujer, perfume hombre, eau de parfum, comprar perfume online, tienda perfumes españa"
    )
    
    # Schema.org para organización y sitio web
    organization_schema = seo.generate_organization_schema()
    website_schema = seo.generate_website_schema()

    context = {
        "form": form,
        "top_products": top_products,
        "seo_data": seo_data,
        "organization_schema": organization_schema,
        "website_schema": website_schema,
    }

    return render(request, template, context)


def error_404(request, exception):
    return render(request, "errors/404.html")


def error_500(request, exception=None):
    return render(request, "errors/500.html")
