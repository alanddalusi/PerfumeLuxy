"""
SEO Views for Eau Royal
Dynamic robots.txt and sitemap management
"""
from django.http import HttpResponse
from django.template import loader
from django.contrib.sites.models import Site


def robots_txt(request):
    """
    Generate dynamic robots.txt with current domain
    """
    template = loader.get_template('seo/robots.txt')
    
    # Get current site domain
    try:
        current_site = Site.objects.get_current()
        domain = f"https://{current_site.domain}"
    except Site.DoesNotExist:
        domain = request.build_absolute_uri('/')[:-1]  # Remove trailing slash
    
    context = {
        'domain': domain,
        'sitemap_url': f"{domain}/sitemap.xml"
    }
    
    return HttpResponse(
        template.render(context, request),
        content_type='text/plain'
    )