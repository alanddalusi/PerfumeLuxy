from django.contrib.sites.requests import RequestSite
from django.core.paginator import InvalidPage
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_safe

from products.models import Product
from products.presentation import seo_images

from .sitemaps import sitemaps


@require_safe
def robots_txt(request):
    return render(request, "seo/robots.txt", {
        "sitemap_url": request.build_absolute_uri(reverse("django.contrib.sitemaps.views.sitemap")),
    }, content_type="text/plain")


@require_safe
def public_sitemap(request):
    site = RequestSite(request)
    try:
        page = int(request.GET.get("p", 1))
    except ValueError:
        raise Http404 from None
    urls = []
    for factory in sitemaps.values():
        try:
            urls.extend(factory().get_urls(page=page, site=site, protocol=request.scheme))
        except InvalidPage:
            continue
    if not urls:
        raise Http404
    for url in urls:   # image sitemap entries: only approved photos of published products
        item = url.get("item")
        url["images"] = (
            [request.build_absolute_uri(image["url"]) for image in seo_images(item)]
            if isinstance(item, Product) else []
        )
    response = render(request, "seo/sitemap.xml", {"urlset": urls}, content_type="application/xml")
    response["X-Robots-Tag"] = "noindex, follow"
    return response
