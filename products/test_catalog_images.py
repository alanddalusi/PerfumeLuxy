"""Catalog image pipeline and presentation: no broken images, no distortion, no upscaling."""

import re
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.signals import request_finished
from django.db import close_old_connections
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Brand, CatalogImage, Product, Wishlist
from .publication import RENDITION_BOXES, decide_image, rendition_boxes


def close_response(response):
    """Release the file of a FileResponse without closing the test's database connection
    (response.close() fires request_finished, like the test client avoids doing)."""
    request_finished.disconnect(close_old_connections)
    try:
        response.close()
    finally:
        request_finished.connect(close_old_connections)


def photo_bytes(size, fmt="JPEG", background=(255, 255, 255), mode="RGB", exif=False):
    """Bottle-like test photo: dark rectangle on a background, optionally with EXIF."""
    image = Image.new(mode, size, background if mode == "RGB" else (0, 0, 0, 0))
    w, h = size
    bottle = Image.new(mode, (max(1, w // 3), max(1, h * 2 // 3)), (60, 40, 30) if mode == "RGB" else (60, 40, 30, 255))
    image.paste(bottle, (w // 3, h // 6))
    out = BytesIO()
    kwargs = {}
    if exif:
        data = Image.Exif(); data[0x010F] = "SecretCameraMaker"; kwargs["exif"] = data.tobytes()
    image.save(out, fmt, **kwargs)
    return out.getvalue()


@override_settings(STORE_MODE="prelaunch")
class CatalogImageTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = self.tmp.name
        storages = {
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"location": root + "/originals"}},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            "catalog_assets": {"BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"location": root + "/derivatives"}},
        }
        override = self.settings(STORAGES=storages)
        override.enable(); self.addCleanup(override.disable)
        self.brand = Brand.objects.create(db_name="b", name="Maison Test")
        self.reviewer = get_user_model().objects.create_superuser(username="reviewer")
        self.addCleanup(self.remove_derivatives)

    def remove_derivatives(self):
        # The catalog_assets storage is bound when the model loads, so derivatives land in the
        # configured directory even under override_settings: delete what this test created.
        for image in CatalogImage.objects.all():
            storage = image.asset.storage
            for name in [image.asset.name, image.thumbnail.name, *(r["name"] for r in image.renditions)]:
                if name and storage.exists(name):
                    storage.delete(name)

    def product_with_photo(self, name, data, filename, publish=True):
        product = Product.objects.create(name=name, brand=self.brand, description="x")
        product.image.save(filename, ContentFile(data))
        image = CatalogImage.objects.create(product=product, source_file=product.image.name,
                                            source_reference="Fuente de prueba", rights_reference="Licencia de prueba")
        decide_image(image, True, self.reviewer)
        if publish:
            Product.objects.filter(pk=product.pk).update(publication_status=Product.Publication.APPROVED)
        product.refresh_from_db(); image.refresh_from_db()
        return product, image

    def status_of(self, url):
        response = self.client.get(url)
        close_response(response)  # FileResponse keeps the file open until closed (matters on Windows)
        return response.status_code

    def open_rendition(self, image, entry):
        with image.asset.storage.open(entry["name"], "rb") as handle:
            return Image.open(BytesIO(handle.read()))

    # ------------------------------------------------------------------ derivatives
    def test_rendition_boxes_never_exceed_the_original(self):
        self.assertEqual(rendition_boxes(224, 224), [224])
        self.assertEqual(rendition_boxes(350, 350), [320, 350])
        self.assertEqual(rendition_boxes(720, 720), [320, 640, 720])
        self.assertEqual(rendition_boxes(4160, 6240), list(RENDITION_BOXES))
        self.assertEqual(rendition_boxes(348, 645), [320, 640, 645])

    def test_renditions_keep_proportion_never_upscale_and_strip_metadata(self):
        cases = {
            "square": ((900, 900), "JPEG", "a.jpeg"),
            "portrait": ((400, 800), "JPEG", "b.jpeg"),
            "landscape": ((1600, 900), "JPEG", "c.jpeg"),
            "tiny": ((224, 224), "JPEG", "d.jpeg"),
            "webp-named-jpeg": ((700, 1050), "WEBP", "e.jpeg"),   # 12 legacy files are like this
            "large-jpeg": ((3000, 2000), "JPEG", "l.jpeg"),       # decoded reduced (draft), capped at 1280
        }
        for label, (size, fmt, filename) in cases.items():
            with self.subTest(case=label):
                _, image = self.product_with_photo(label, photo_bytes(size, fmt, exif=True), filename)
                boxes = sorted({r["box"] for r in image.renditions})
                self.assertEqual(boxes, rendition_boxes(*size))
                self.assertEqual({r["fmt"] for r in image.renditions}, {"avif", "webp"})
                for entry in image.renditions:
                    rendered = self.open_rendition(image, entry)
                    self.assertEqual(rendered.format, entry["fmt"].upper())
                    self.assertEqual((rendered.width, rendered.height), (entry["w"], entry["h"]))
                    self.assertLessEqual(max(rendered.size), entry["box"])          # fits the square box
                    self.assertLessEqual(rendered.width, size[0])                    # never upscaled
                    self.assertLessEqual(rendered.height, size[1])
                    self.assertAlmostEqual(rendered.width / rendered.height, size[0] / size[1], delta=0.02)  # no distortion
                    self.assertNotIn(b"SecretCameraMaker", rendered.info.get("exif", b""))
                self.assertEqual(max(max(r["w"], r["h"]) for r in image.renditions), min(max(size), RENDITION_BOXES[-1]))

    def test_transparent_png_is_flattened_on_white(self):
        _, image = self.product_with_photo("png", photo_bytes((500, 500), "PNG", mode="RGBA"), "f.png")
        entry = next(r for r in image.renditions if r["fmt"] == "webp")
        corner = self.open_rendition(image, entry).convert("RGB").getpixel((2, 2))
        self.assertGreaterEqual(min(corner), 245)

    # ------------------------------------------------------------------ serving and rights gating
    def test_every_rendition_is_served_with_its_type_and_gated_by_rights(self):
        product, image = self.product_with_photo("served", photo_bytes((800, 800)), "g.jpeg")
        for entry in image.renditions:
            url = reverse("products:catalog_rendition", args=[image.pk, entry["box"], entry["fmt"]])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertEqual(response["Content-Type"], f"image/{entry['fmt']}")
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            body = b"".join(response.streaming_content)
            close_response(response)
            Image.open(BytesIO(body)).verify()   # not broken
        self.assertEqual(self.client.get(reverse("products:catalog_rendition", args=[image.pk, 123, "webp"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("products:catalog_rendition", args=[image.pk, 320, "png"])).status_code, 404)
        url = reverse("products:catalog_rendition", args=[image.pk, 320, "avif"])
        Product.objects.filter(pk=product.pk).update(publication_status=Product.Publication.DRAFT)
        self.assertEqual(self.client.get(url).status_code, 404)                 # unpublished product
        Product.objects.filter(pk=product.pk).update(publication_status=Product.Publication.APPROVED)
        decide_image(image, False, self.reviewer)
        self.assertEqual(self.client.get(url).status_code, 404)                 # withdrawn image

    def test_unapproved_legacy_photo_is_never_rendered(self):
        product = Product.objects.create(name="Sin derechos", brand=self.brand, description="x")
        product.image.save("legacy.jpeg", ContentFile(photo_bytes((600, 600))))   # a file, but no approved CatalogImage
        Product.objects.filter(pk=product.pk).update(publication_status=Product.Publication.APPROVED)
        product.refresh_from_db()
        page = self.client.get(product.get_absolute_url()).content.decode()
        self.assertNotIn("<picture", page)
        self.assertNotIn("legacy", page)
        self.assertIn("Fotografía en preparación", page)
        self.assertIsNone(product.storefront_picture)

    # ------------------------------------------------------------------ markup on every surface
    def assert_picture_markup(self, html, image, priority):
        picture = re.search(r"<picture class=\"sf-picture\">.*?</picture>", html, re.S)
        self.assertIsNotNone(picture, "no <picture> rendered")
        block = picture.group(0)
        largest = max((r for r in image.renditions if r["fmt"] == "webp"), key=lambda r: r["box"])
        self.assertIn('<source type="image/avif" srcset="', block)
        self.assertIn('<source type="image/webp" srcset="', block)
        self.assertIn(f'width="{largest["w"]}" height="{largest["h"]}"', block)
        self.assertIn(f'--img-max-w: {largest["w"]}px; --img-max-h: {largest["h"]}px', block)
        self.assertIn('decoding="async"', block)
        if priority:
            self.assertIn('loading="eager" fetchpriority="high"', block)
        else:
            self.assertIn('loading="lazy"', block)
            self.assertNotIn("fetchpriority", block)
        urls = set(re.findall(r'(/products/image/\d+/[a-z0-9-]+-\d+\.(?:avif|webp))', block))
        self.assertGreaterEqual(len(urls), 2)
        for url in urls:                                                         # no broken image
            self.assertEqual(self.status_of(url), 200, url)
        return block

    def test_catalog_search_detail_compare_and_wishlist_share_the_square_picture(self):
        first, first_image = self.product_with_photo("Alpha", photo_bytes((400, 800)), "h.jpeg")
        second, second_image = self.product_with_photo("Beta", photo_bytes((224, 224)), "i.jpeg")
        no_photo = Product.objects.create(name="Gamma", brand=self.brand, description="x",
                                          publication_status=Product.Publication.APPROVED)

        catalog = self.client.get(reverse("products:products")).content.decode()
        cards = re.findall(r'<article class="sf-card eo-perfume-card">.*?</article>', catalog, re.S)
        self.assertEqual(len(cards), 3)
        by_name = {name: next(card for card in cards if f">{name}</a>" in card) for name in ("Alpha", "Beta", "Gamma")}
        images = {"Alpha": first_image, "Beta": second_image}
        for position, card in enumerate(cards):              # only the first card is prioritised
            name = next(n for n, c in by_name.items() if c is card)
            if name in images:
                self.assert_picture_markup(card, images[name], priority=position == 0)
                self.assertIn('alt=""', card)                 # the surrounding link already names it
            else:
                self.assertNotIn("<picture", card)
                self.assertIn('class="sf-placeholder"', card)       # placeholder in the same frame
                self.assertIn('<span class="eo-sr-only">Ver ficha de', card)   # link text = product
        self.assertIn("--img-max-w: 224px", by_name["Beta"])        # small photo never enlarged

        results = self.client.get(reverse("products:products"), {"q": "Beta"}).content.decode()
        self.assert_picture_markup(results, second_image, priority=True)

        detail = self.client.get(first.get_absolute_url()).content.decode()
        main = self.assert_picture_markup(detail, first_image, priority=True)
        self.assertIn("data-gallery-main", main)
        self.assertIn('sizes="(min-width: 64rem) 36rem, 92vw"', main)

        compare = self.client.get(reverse("products:compare_products"), {"products": [first.pk, no_photo.pk]}).content.decode()
        self.assert_picture_markup(compare, first_image, priority=False)
        self.assertIn("Fotografía en preparación", compare)

        user = get_user_model().objects.create_user(username="fan")
        Wishlist.objects.create(user=user).products.add(second)
        self.client.force_login(user)
        wishlist = self.client.get(reverse("products:view_wishlist")).content.decode()
        self.assert_picture_markup(wishlist, second_image, priority=False)
        self.client.logout()

        suggestion = self.client.get(reverse("products:search_suggestions"), {"q": "Alp"}).json()["results"][0]["image"]
        smallest = min((r for r in first_image.renditions if r["fmt"] == "webp"), key=lambda r: r["box"])
        self.assertEqual((suggestion["width"], suggestion["height"]), (smallest["w"], smallest["h"]))
        self.assertEqual(self.status_of(suggestion["src"]), 200)

    def test_gallery_thumbnails_carry_every_source_for_switching(self):
        product, image = self.product_with_photo("Delta", photo_bytes((900, 900)), "j.jpeg")
        extra = CatalogImage.objects.create(product=product, source_file=product.image.name, display_order=1,
                                            source_reference="Fuente", rights_reference="Licencia")
        decide_image(extra, True, self.reviewer)
        page = self.client.get(product.get_absolute_url()).content.decode()
        thumbs = re.findall(r"<li><a [^>]*data-gallery-image[^>]*>", page)
        self.assertEqual(len(thumbs), 2)
        for thumb in thumbs:
            self.assertIn('data-srcset0="', thumb)
            self.assertIn('data-srcset1="', thumb)
            self.assertRegex(thumb, r'data-width="\d+" data-height="\d+"')

    # ------------------------------------------------------------------ stylesheet contract
    def test_frame_css_contains_never_crops_or_stretches(self):
        css = (Path(settings.BASE_DIR) / "static/css/storefront.css").read_text(encoding="utf-8")
        self.assertIn(".sf-media { aspect-ratio: 1 / 1;", css)
        rule = re.search(r"\.sf-media img \{([^}]*)\}", css).group(1)
        self.assertIn("object-fit: contain", rule)
        self.assertIn("max-width: min(100%, var(--img-max-w, 100%))", rule)
        self.assertIn("max-height: min(100%, var(--img-max-h, 100%))", rule)
        self.assertIn("width: auto", rule)
        self.assertNotIn("object-fit: cover", css)
        self.assertNotRegex(css, r"\.sf-media img \{[^}]*width: 100%")       # would stretch small photos
        search = (Path(settings.BASE_DIR) / "static/css/search-autocomplete.css").read_text(encoding="utf-8")
        thumb = re.search(r"\.search-result-image img \{([^}]*)\}", search).group(1)
        self.assertIn("object-fit: contain", thumb)
        self.assertNotIn("cover", thumb)

    # ------------------------------------------------------------------ commands
    def test_rebuild_and_report_commands(self):
        _, image = self.product_with_photo("Epsilon", photo_bytes((700, 700)), "k.jpeg")
        orphans = [r["name"] for r in image.renditions]   # unlinked below; delete them at the end
        self.addCleanup(lambda: [image.asset.storage.delete(n) for n in orphans if image.asset.storage.exists(n)])
        CatalogImage.objects.filter(pk=image.pk).update(renditions=[])
        out = StringIO(); call_command("rebuild_catalog_renditions", stdout=out)
        self.assertIn("1 approved images would be processed", out.getvalue())
        image.refresh_from_db(); self.assertEqual(image.renditions, [])
        call_command("rebuild_catalog_renditions", "--apply", stdout=StringIO())
        image.refresh_from_db()
        self.assertEqual(sorted({r["box"] for r in image.renditions}), [320, 640, 700])
        with self.settings(MEDIA_ROOT=self.tmp.name + "/originals"):
            report = StringIO(); call_command("catalog_images_report", stdout=report)
        self.assertIn("square", report.getvalue())
        self.assertIn("Epsilon", report.getvalue())

    # ------------------------------------------------------------------ SEO
    def test_alt_text_and_descriptive_image_urls(self):
        product, image = self.product_with_photo("Zeta", photo_bytes((700, 700)), "z.jpeg")
        Product.objects.filter(pk=product.pk).update(concentration="edp", size="100ml")
        product.refresh_from_db()
        from .presentation import product_alt, public_picture
        self.assertEqual(product_alt(product), "Frasco de Maison Test Zeta Eau de Parfum 100 ml")
        picture = public_picture(product)
        self.assertEqual(picture["alt"], "Frasco de Maison Test Zeta Eau de Parfum 100 ml")
        self.assertIn(f"/products/image/{image.pk}/{product.slug}-700.webp", picture["src"])
        for source in picture["sources"]:
            for candidate in source["srcset"].split(", "):
                url = candidate.split(" ")[0]
                self.assertIn(product.slug, url)
                self.assertEqual(self.status_of(url), 200, url)
        CatalogImage.objects.filter(pk=image.pk).update(alt_text="Frasco azul de Zeta")
        self.assertEqual(public_picture(product)["alt"], "Frasco azul de Zeta")

    def test_product_page_and_sitemap_expose_only_approved_images(self):
        product, image = self.product_with_photo("Eta", photo_bytes((900, 600)), "e.jpeg")
        hidden, _ = self.product_with_photo("Theta", photo_bytes((600, 600)), "t.jpeg", publish=False)
        html = self.client.get(product.get_absolute_url()).content.decode()
        self.assertIn('<meta property="og:image" content="http://testserver/products/image/', html)
        self.assertIn('<meta property="og:image:width" content="900">', html)
        self.assertIn('<meta property="og:image:height" content="600">', html)
        self.assertIn('<meta property="og:image:alt" content="Frasco de Maison Test Eta">', html)
        self.assertIn('<meta name="twitter:image:alt"', html)
        self.assertRegex(html, r'"image": \["http://testserver/products/image/\d+/maison-test-eta-900\.webp"\]')
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertIn('xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"', xml)
        self.assertIn(f"<image:loc>http://testserver/products/image/{image.pk}/maison-test-eta-900.webp</image:loc>", xml)
        self.assertNotIn(hidden.slug, xml)
        self.assertEqual(xml.count("<image:image>"), 1)
        CatalogImage.objects.filter(pk=image.pk).update(withdrawn_at="2026-01-01T00:00:00Z")
        self.assertNotIn("<image:image>", self.client.get("/sitemap.xml").content.decode())
        html = self.client.get(product.get_absolute_url()).content.decode()
        self.assertNotIn("/products/image/", html)          # no product photo once withdrawn
        self.assertIn('<meta property="og:image" content="http://testserver/static/img/og-default.png">', html)

    # ------------------------------------------------------------------ progressive assignment
    def legacy_product(self, name, sku, filename, size=(640, 640)):
        product = Product.objects.create(name=name, brand=self.brand, description="x")
        product.image.save(filename, ContentFile(photo_bytes(size)))
        Product.objects.filter(pk=product.pk).update(sku=sku)
        product.refresh_from_db()
        return product

    def manifest(self, rows):
        path = Path(self.tmp.name) / "manifest.csv"
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            import csv
            writer = csv.writer(handle, delimiter=";")   # as Excel in Spanish saves it
            writer.writerow(["sku", "file", "alt_text", "source_reference", "rights_reference", "mapping_confirmed"])
            writer.writerows(rows)
        return str(path)

    def test_manifest_lists_mapping_with_brand_name_and_suggested_alt(self):
        a = self.legacy_product("Iota", "SKU-A", "a.jpeg")
        b = self.legacy_product("Kappa", "SKU-B", "b.jpeg")
        Product.objects.filter(pk=b.pk).update(image="gone.jpeg")
        out = Path(self.tmp.name) / "m.csv"
        call_command("catalog_photo_manifest", "--output", str(out), "--source", "Origen X", stderr=StringIO())
        text = out.read_text(encoding="utf-8-sig")
        self.assertIn(f"SKU-A,Maison Test,Iota,,,{a.image.name},ok,640,640,white,Frasco de Maison Test Iota,Origen X,,,,", text)
        self.assertNotIn("SKU-B", text)
        call_command("catalog_photo_manifest", "--output", str(out), "--all", stderr=StringIO())
        self.assertIn("SKU-B", out.read_text(encoding="utf-8-sig"))
        self.assertIn("missing", out.read_text(encoding="utf-8-sig"))

    def test_assignment_is_dry_run_by_default_and_never_publishes_without_rights(self):
        a = self.legacy_product("Lambda", "SKU-L", "l.jpeg")
        b = self.legacy_product("Mu", "SKU-M", "m.jpeg")
        c = self.legacy_product("Nu", "SKU-N", "n.jpeg")
        path = self.manifest([
            ["SKU-L", a.image.name, "", "Origen", "", "sí"],                 # no rights -> pending
            ["SKU-M", b.image.name, "Frasco de Mu", "Origen", "Licencia 7", "yes"],
            ["SKU-N", c.image.name, "", "Origen", "Licencia 8", ""],          # not confirmed
            ["SKU-L", b.image.name, "", "Origen", "Licencia", "yes"],         # wrong product photo
            ["SKU-Z", "z.jpeg", "", "", "", "yes"],                           # unknown SKU
        ])
        out = StringIO(); call_command("assign_catalog_photos", path, stdout=out)
        self.assertIn("DRY RUN", out.getvalue())
        self.assertIn("2 created", out.getvalue())
        self.assertIn("2 errors", out.getvalue())
        self.assertFalse(CatalogImage.objects.exists())

        out = StringIO(); call_command("assign_catalog_photos", path, "--apply", stdout=out)
        self.assertIn("0 approved", out.getvalue())
        pending = CatalogImage.objects.get(product=a)
        self.assertEqual(pending.alt_text, "Frasco de Maison Test Lambda")
        self.assertFalse(pending.is_public)
        self.assertFalse(CatalogImage.objects.filter(product=c).exists())
        self.assertFalse(any(i.is_public for i in CatalogImage.objects.all()))

        clerk = get_user_model().objects.create_user(username="clerk")
        with self.assertRaises(Exception):
            call_command("assign_catalog_photos", path, "--apply", "--approve", "--reviewer", "clerk", stdout=StringIO())
        out = StringIO()
        call_command("assign_catalog_photos", path, "--apply", "--approve", "--reviewer", "reviewer", stdout=out)
        self.assertIn("1 approved", out.getvalue())
        approved = CatalogImage.objects.get(product=b)
        self.assertTrue(approved.is_public)
        self.assertEqual(approved.alt_text, "Frasco de Mu")
        self.assertTrue(approved.renditions)
        self.assertFalse(CatalogImage.objects.get(product=a).is_public)   # still no rights
        b.refresh_from_db()
        self.assertNotEqual(b.publication_status, Product.Publication.APPROVED)   # products untouched
        self.assertIsNone(clerk.last_login)

        # Re-running is idempotent; a withdrawn photo is not revived but re-opened for review.
        out = StringIO(); call_command("assign_catalog_photos", path, "--apply", stdout=out)
        self.assertIn("0 created", out.getvalue())
        decide_image(approved, False, self.reviewer)
        call_command("assign_catalog_photos", path, "--apply", stdout=StringIO())
        records = list(CatalogImage.objects.filter(product=b).order_by("pk"))
        self.assertEqual(len(records), 2)
        self.assertIsNotNone(records[0].withdrawn_at)
        self.assertFalse(records[1].is_public)
