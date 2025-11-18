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
        active=True,
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

    context = {
        "form": form,
        "top_products": top_products,
    }

    return render(request, template, context)


def error_404(request, exception):
    return render(request, "errors/404.html")


def error_500(request, exception=None):
    return render(request, "errors/500.html")
