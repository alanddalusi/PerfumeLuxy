# Read-only crawl audit of the public site. Run inside the web container:
#   docker exec -i <web> python manage.py shell -c "import sys; exec(sys.stdin.read())" < crawl_audit.py
# Checks every sitemap URL (200, self canonical, no noindex, allowed by robots.txt), every internal
# link found on those pages (status, noindex targets linked without nofollow) and third-party hosts.
import html as htmllib
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

BASE = os.environ.get("BASE", "https://perfumeriaelbuenolor.es").rstrip("/")
HOST = urlsplit(BASE).hostname
cache = {}


def fetch(url):
    if url not in cache:
        request = urllib.request.Request(url, headers={"User-Agent": "eo-crawl-audit"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                cache[url] = (response.status, response.read().decode("utf-8", "replace"), response.headers)
        except urllib.error.HTTPError as error:
            cache[url] = (error.code, "", error.headers)
    return cache[url]


robots = RobotFileParser()
robots.parse(fetch(BASE + "/robots.txt")[1].splitlines())
locs = re.findall(r"<loc>([^<]+)</loc>", fetch(BASE + "/sitemap.xml")[1])
problems, links, external = [], {}, {}
for url in locs:
    status, page, headers = fetch(url)
    canonical = re.search(r'<link rel="canonical" href="([^"]+)"', page)
    meta = re.search(r'<meta name="robots" content="([^"]+)"', page)
    if status != 200:
        problems.append(f"sitemap {url}: HTTP {status}")
        continue
    if not canonical or canonical.group(1) != url:
        problems.append(f"sitemap {url}: canonical {canonical.group(1) if canonical else 'missing'}")
    if (meta and "noindex" in meta.group(1)) or "noindex" in headers.get("X-Robots-Tag", ""):
        problems.append(f"sitemap {url}: noindex")
    if not robots.can_fetch("Googlebot", url):
        problems.append(f"sitemap {url}: blocked by robots.txt")
    for tag in re.findall(r"<a\s[^>]*>", page):
        href = re.search(r'href="([^"]+)"', tag)
        if not href or href.group(1).startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        target = urljoin(url, htmllib.unescape(href.group(1))).split("#")[0]
        if urlsplit(target).hostname == HOST:
            links.setdefault(target, set()).add(("nofollow" in tag, url))
    for src in re.findall(r'(?:src|href)="(https?://[^"]+)"', page):
        host = urlsplit(src).hostname
        if host and host != HOST and not src.startswith(("https://www.", "https://us.", "https://int.")) or (host and host != HOST and re.search(r"<(?:script|link)[^>]+" + re.escape(src), page)):
            if re.search(r"<(?:script|link|img|iframe)[^>]+" + re.escape(src), page):
                external.setdefault(host, set()).add(url)

followed_noindex = 0
for target, sources in sorted(links.items()):
    status, page, headers = fetch(target)
    if status >= 400 and urlsplit(target).path not in ("/checkout/",):
        problems.append(f"link {target}: HTTP {status} (from {next(iter(sources))[1]})")
    noindex = re.search(r'<meta name="robots" content="[^"]*noindex', page) or "noindex" in headers.get("X-Robots-Tag", "")
    if noindex and not robots.can_fetch("Googlebot", target):
        continue   # blocked area (account, bag...): not crawled anyway
    if noindex and any(not nofollow for nofollow, _ in sources):
        followed_noindex += 1
        if followed_noindex <= 8:
            problems.append(f"link to noindex page without nofollow: {target} (from {next(iter(sources))[1]})")
print(f"sitemap URLs: {len(locs)}; internal link targets: {len(links)}; problems: {len(problems)}")
for problem in problems:
    print("PROBLEM", problem)
print("third-party resources loaded:", {host: len(pages) for host, pages in external.items()} or "none")
