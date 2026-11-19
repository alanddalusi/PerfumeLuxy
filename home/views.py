from django.conf import settings
from django.shortcuts import render, redirect, reverse
from django.http import Http404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from .forms import LAUNCH_CONSENT_VERSION, SubscribeForm
from .models import Subscriber
from .notices import confirmation_queryset, rate_allowed, request_confirmation, withdrawal_queryset
from products.models import Category, FragranceFamily, Product, StockAlert
from products.catalog import catalog_filter_url
from eau_royal.seo import SEOManager


NOTICE_CLOSED_MESSAGE = "Los avisos por correo se activarán muy pronto. Todavía no guardamos ninguna dirección."


def index(request):
    if request.method == "POST" and not settings.NOTICE_SIGNUPS_OPEN:
        # Nothing is stored while the confirmation e-mail cannot be delivered.
        messages.info(request, NOTICE_CLOSED_MESSAGE)
        return redirect("home:index")
    if request.method == "POST":
        form = SubscribeForm(request.POST)
        if form.is_valid():
            if not rate_allowed(request):
                return notice_response(request, "limited", status=429)
            notice = form.save()
            request_confirmation(
                request, notice, "lanzamiento", email=notice.email, version=LAUNCH_CONSENT_VERSION,
            )
            messages.success(request, "Si el aviso está pendiente, recibirás un correo para confirmarlo.")
            return redirect("home:index")
        if "email" in form.errors:
            messages.error(request, "Introduce un correo electrónico válido.")
    else:
        form = SubscribeForm()

    seo = SEOManager(request)
    return render(request, "home/index.html", {
        "form": form,
        "has_products": Product.objects.published().exists(),
        "families": [
            (family, catalog_filter_url(fragrance_family=family.name))
            for family in FragranceFamily.objects.order_by("name")[:6]
        ],
        "categories": [
            (category.name or category.db_name, catalog_filter_url(category=category.db_name))
            for category in Category.objects.order_by("name", "pk")[:6]
        ],
        "seo_data": seo.get_meta_tags(
            title="Perfumería El Buen Olor | Descubre tu próxima fragancia",
            description="Explora perfumes por familias olfativas y conoce las notas que definen cada fragancia. Apúntate para recibir el aviso de lanzamiento.",
            canonical=seo.get_canonical_url(reverse("home:index")),
        ),
        "organization_schema": seo.generate_organization_schema(),
        "website_schema": seo.generate_website_schema(),
    })


def error_404(request, exception):
    return render(request, "errors/404.html", status=404)


def error_500(request, exception=None):
    return render(request, "errors/500.html", status=500)


def notice_model(kind):
    if kind == "lanzamiento":
        return Subscriber
    if kind == "disponibilidad":
        return StockAlert
    raise Http404


def notice_response(request, state, *, status=200):
    response = render(request, "home/notice_action.html", {"state": state}, status=status)
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def confirm_notice(request, kind, token):
    pending = confirmation_queryset(notice_model(kind), token)
    if kind == "disponibilidad":
        pending = pending.filter(product__publication_status=Product.Publication.APPROVED)
    if request.method == "POST":
        consumed = pending.update(confirmed_at=timezone.now(), confirmation_digest="", confirmation_expires_at=None)
        return notice_response(request, "confirmed" if consumed else "invalid", status=200 if consumed else 410)
    if pending.exists():
        return notice_response(request, "confirm")
    return notice_response(request, "invalid", status=410)


@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def unsubscribe_notice(request, kind, token):
    pending = withdrawal_queryset(notice_model(kind), kind, token)
    if request.method == "POST":
        consumed = pending.update(
            withdrawn_at=timezone.now(), unsubscribe_nonce="", confirmation_digest="", confirmation_expires_at=None,
        )
        return notice_response(request, "withdrawn" if consumed else "invalid", status=200 if consumed else 410)
    if pending.exists():
        return notice_response(request, "unsubscribe")
    return notice_response(request, "invalid", status=410)


def privacy(request):
    response = render(request, "home/privacy.html")
    response["X-Robots-Tag"] = "noindex"
    return response
