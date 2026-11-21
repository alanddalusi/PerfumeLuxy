# Read-only checks of the published reference pages. Run with: python manage.py shell < check_published.py
# BASE env var = public site (e.g. https://perfumeriaelbuenolor.es); without it, Django's test client.
import html as htmllib
import json
import os
import re
import urllib.request
from urllib.robotparser import RobotFileParser

from products.models import Product

BASE = os.environ.get("BASE", "").rstrip("/")


def get(path):
    if BASE:
        request = urllib.request.Request(BASE + path, headers={"User-Agent": "eo-publication-check"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8")
    from django.test import Client
    from django.test.utils import override_settings
    with override_settings(ALLOWED_HOSTS=["*"]):
        response = Client().get(path)
    return response.status_code, response.content.decode("utf-8")


def text_of(fragment):
    return htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


problems, titles, descriptions, rows = [], {}, {}, []
products = list(Product.objects.published().filter(catalog_origin="reference").select_related("brand").order_by("pk"))
status, sitemap = get("/sitemap.xml")
_, robots_txt = get("/robots.txt")
robots = RobotFileParser()
robots.parse(robots_txt.splitlines())
for product in products:
    path = product.get_absolute_url()
    code, page = get(path)
    if code != 200:
        problems.append(f"{path}: HTTP {code}")
        continue
    title = text_of(re.search(r"<title>(.*?)</title>", page, re.S).group(1))
    meta = re.search(r'<meta name="description" content="([^"]*)"', page)
    canonical = re.search(r'<link rel="canonical" href="([^"]*)"', page)
    robots_meta = re.search(r'<meta name="robots" content="([^"]*)"', page)
    blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)]
    schema = next((b for b in blocks if b.get("@type") == "Product"), None)
    main = page.split("<main", 1)[-1].split("</main>", 1)[0]
    body = text_of(main)
    checks = {
        "title": bool(title) and product.name in title and title not in titles,
        "meta_description": bool(meta) and 70 <= len(meta.group(1)) <= 160 and meta.group(1) not in descriptions,
        "canonical": bool(canonical) and canonical.group(1).endswith(path),
        "indexable": not robots_meta or "noindex" not in robots_meta.group(1),
        "json_ld": bool(schema) and schema.get("name") and schema.get("brand", {}).get("name") and "offers" not in schema,
        "content": len(product.description) >= 120 and product.description[:60] in htmllib.unescape(main),
        "proximamente": "Próximamente" in body or "próximamente" in body,
        "no_price": not re.search(r"€\s?\d|\d\s?€", body),
        "no_purchase": "add_to_bag" not in main and 'action="/bag/' not in main,
        "no_photo": "/products/image/" not in main,
        "sitemap": path in sitemap,
        "robots_allows": robots.can_fetch("Googlebot", (BASE or "http://testserver") + path),
    }
    titles[title] = path
    if meta:
        descriptions[meta.group(1)] = path
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        problems.append(f"{path}: {', '.join(failed)}")
    rows.append((path, title, len(body.split())))
print(f"published reference pages: {len(products)}; sitemap HTTP {status}; problems: {len(problems)}")
for problem in problems:
    print("PROBLEM", problem)
for path, title, words in rows:
    print(f"OK {path} | {title} | {words} palabras")
