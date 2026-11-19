from django.contrib.sites.requests import RequestSite
from django.core.paginator import InvalidPage
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_safe

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
    response = render(request, "sitemap.xml", {"urlset": urls}, content_type="application/xml")
    response["X-Robots-Tag"] = "noindex, follow"
    return response
