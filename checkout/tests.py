import os
import runpy
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from products.models import Brand, Category, Product, Review, Wishlist
from products.models_extended import SampleRequest

from .marketing_models import CouponUsage, LoyaltyProgram, LoyaltyTransaction
from .models import CartItem, Order
from .store_mode import sales_enabled
from .webhook_handler import payment_charge


class StoreModeTests(SimpleTestCase):
    def test_defaults_to_prelaunch_without_environment_variable(self):
        settings_file = Path(settings.BASE_DIR) / "eau_royal" / "settings.py"
        with patch.dict(os.environ):
            os.environ.pop("STORE_MODE", None)
            self.assertEqual(runpy.run_path(str(settings_file))["STORE_MODE"], "prelaunch")

    @override_settings(STORE_MODE="unexpected")
    def test_unknown_mode_fails_closed(self):
        self.assertFalse(sales_enabled())

    @override_settings(STORE_MODE="live")
    def test_live_requires_explicit_mode(self):
        self.assertTrue(sales_enabled())

    @patch("stripe.Charge.retrieve")
    def test_stripe_payment_charge_accepts_legacy_and_current_event_shapes(self, retrieve):
        def intent(fields):
            return stripe.StripeObject.construct_from(fields, None)

        self.assertEqual(payment_charge(intent({"charges": {"data": [{"id": "ch_old"}]}})).id, "ch_old")
        self.assertEqual(payment_charge(intent({"latest_charge": {"id": "ch_expanded"}})).id, "ch_expanded")
        retrieve.assert_not_called()
        self.assertEqual(payment_charge(intent({"latest_charge": "ch_ref"})), retrieve.return_value)
        retrieve.assert_called_once_with("ch_ref")


@override_settings(
    STORE_MODE="prelaunch",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    STRIPE_SECRET_KEY="sk_test_mocked",
)
class PrelaunchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.owner = users.create_user(username="owner")
        cls.other = users.create_user(username="other")
        cls.staff = users.create_superuser(username="staff", email="staff@example.test")
        cls.product = Product.objects.create(
            name="Producto de prueba",
            publication_status=Product.Publication.APPROVED,
            description="Descripción de prueba",
            price=50,
            stock=2,
            brand=Brand.objects.create(name="Marca de prueba", db_name="marca"),
            category=Category.objects.create(name="Perfumes"),
        )
        cls.order = cls.create_order(cls.owner.userprofile)
        cls.unassigned_order = cls.create_order(None)
        cls.item = CartItem.objects.create(
            order=cls.order, product=cls.product, quantity=1, product_size=""
        )

    @staticmethod
    def create_order(profile):
        return Order.objects.create(
            user_profile=profile, full_name="Pedido privado",
            email="private@example.test", phone_number="000000000",
            town_or_city="Madrid", street_address1="Calle privada",
        )

    def put_product_in_cart(self):
        session = self.client.session
        session["bag"] = {str(self.product.pk): 1}
        session.save()

    def test_commercial_routes_stop_before_stripe_mail_and_database_writes(self):
        self.client.force_login(self.owner)
        self.put_product_in_cart()
        routes = {
            "checkout:checkout": ("get", "post", "head"),
            "checkout:cache_checkout_data": ("post",),
            "checkout:webhook": ("post",),
            "checkout:apply_coupon": ("post",),
            "checkout:remove_coupon": ("post",),
            "checkout:validate_coupon": ("post",),
            "checkout:loyalty_dashboard": ("get",),
            "checkout:redeem_points": ("post",),
            "products:request_sample": ("get", "post"),
        }
        data = {
            "full_name": "Cliente de prueba", "email": "sale@example.test",
            "phone_number": "000000000", "street_address1": "Calle prueba",
            "street_address2": "", "town_or_city": "Madrid", "county": "Madrid",
            "postcode": "28001", "country": "ES", "client_secret": "pi_fake_secret_test",
            "save_info": "true",
        }
        with ExitStack() as stack:
            mocks = [
                stack.enter_context(patch(target))
                for target in (
                    "stripe.PaymentIntent.create",
                    "stripe.PaymentIntent.modify",
                    "stripe.Webhook.construct_event",
                    "checkout.webhooks.StripeWH_Handler",
                    "checkout.webhook_handler.send_mail",
                )
            ]
            for name, methods in routes.items():
                args = [self.product.pk] if name == "products:request_sample" else []
                for method in methods:
                    with self.subTest(route=name, method=method):
                        url = reverse(name, args=args)
                        if name == "checkout:webhook":
                            response = self.client.post(
                                url, '{"type":"payment_intent.succeeded"}',
                                content_type="application/json", HTTP_STRIPE_SIGNATURE="mock",
                            )
                        else:
                            response = getattr(self.client, method)(url, data)
                        self.assertEqual(response.status_code, 403)
            for mock in mocks:
                mock.assert_not_called()

        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(CartItem.objects.count(), 1)
        self.assertFalse(CouponUsage.objects.exists())
        self.assertFalse(LoyaltyProgram.objects.exists())
        self.assertFalse(LoyaltyTransaction.objects.exists())
        self.assertFalse(SampleRequest.objects.exists())
        self.assertEqual(self.client.session["bag"], {str(self.product.pk): 1})

    def test_admin_commercial_records_are_read_only(self):
        self.client.force_login(self.staff)
        change = reverse("admin:checkout_order_change", args=[self.order.pk])
        self.assertEqual(self.client.get(change).status_code, 200)
        self.assertEqual(self.client.post(change, {"full_name": "Modificado"}).status_code, 403)
        for name, args in (
            ("admin:checkout_order_add", []),
            ("admin:checkout_order_delete", [self.order.pk]),
            ("admin:checkout_coupon_add", []),
            ("admin:checkout_loyaltyprogram_add", []),
            ("admin:products_samplerequest_add", []),
            ("admin:products_product_delete", [self.product.pk]),
            ("products:delete_product", [self.product.pk]),
        ):
            with self.subTest(route=name):
                self.assertEqual(self.client.post(reverse(name, args=args)).status_code, 403)
        self.assertEqual(self.client.post(reverse("admin:products_product_changelist"), {
            "action": "delete_selected",
            "_selected_action": [self.product.pk],
            "post": "yes",
            "index": "0",
        }).status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.full_name, "Pedido privado")
        self.assertTrue(CartItem.objects.filter(pk=self.item.pk).exists())

    def test_private_order_pages_require_existing_ownership(self):
        for name in ("checkout:checkout_success", "profiles:order_history"):
            with self.subTest(route=name):
                url = reverse(name, args=[self.order.order_number])
                self.client.logout()
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertNotIn(b"private@example.test", response.content)
                self.client.force_login(self.other)
                response = self.client.get(url)
                self.assertNotContains(response, "private@example.test", status_code=404)
                guest_url = reverse(name, args=[self.unassigned_order.order_number])
                self.assertEqual(self.client.get(guest_url).status_code, 404)

                self.client.force_login(self.owner)
                self.put_product_in_cart()
                response = self.client.get(url)
                self.assertContains(response, "private@example.test")
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertEqual(self.client.post(url).status_code, 405)
                self.assertEqual(self.client.session["bag"], {str(self.product.pk): 1})

        self.unassigned_order.refresh_from_db()
        self.order.refresh_from_db()
        self.assertIsNone(self.unassigned_order.user_profile_id)
        self.assertEqual(self.order.user_profile_id, self.owner.userprofile.pk)
        self.assertFalse(LoyaltyProgram.objects.exists())

    def test_mutations_require_post_and_csrf(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.staff)
        self.put_product_in_cart()
        review = Review.objects.create(
            product=self.product, user=self.staff, rating=5, title="Prueba", comment="Prueba"
        )
        wishlist = Wishlist.objects.create(user=self.staff)
        wishlist.products.add(self.product)
        routes = {
            "products:delete_product": [self.product.pk],
            "products:delete_review": [review.pk],
            "products:toggle_wishlist": [self.product.pk],
            "products:clear_wishlist": [],
            "products:add_to_comparison": [self.product.pk],
            "products:notify_when_available": [self.product.pk],
            "bag:add_to_bag": [self.product.pk],
            "bag:adjust_bag": [self.product.pk],
            "bag:remove_from_bag": [self.product.pk],
        }
        for name, args in routes.items():
            with self.subTest(route=name):
                url = reverse(name, args=args)
                self.assertEqual(self.client.get(url).status_code, 405)
                self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertTrue(Review.objects.filter(pk=review.pk).exists())
        self.assertTrue(wishlist.products.filter(pk=self.product.pk).exists())
        self.assertEqual(self.client.session["bag"], {str(self.product.pk): 1})

    def test_authenticated_favorites_and_reviews_accept_valid_csrf_post(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.owner)
        self.client.get(reverse("home:index"))
        headers = {"HTTP_X_CSRFTOKEN": self.client.cookies["csrftoken"].value}
        product = [self.product.pk]
        detail = reverse("products:product_detail", args=[self.product.slug])
        wishlist = reverse("products:view_wishlist")

        self.assertEqual(self.client.get(wishlist).status_code, 200)
        self.assertFalse(Wishlist.objects.filter(user=self.owner).exists())
        self.assertRedirects(
            self.client.post(reverse("products:toggle_wishlist", args=product), **headers),
            reverse("products:products"),
        )
        self.assertContains(self.client.get(wishlist), self.product.name)
        self.assertRedirects(self.client.post(
            reverse("products:clear_wishlist"), **headers,
        ), wishlist)
        self.assertFalse(Wishlist.objects.get(user=self.owner).products.exists())

        self.assertRedirects(self.client.post(
            reverse("products:add_review", args=product),
            {"rating": 5, "title": "Reseña de prueba", "comment": "Comentario"},
            **headers,
        ), detail)
        review = Review.objects.get(product=self.product, user=self.owner)
        self.assertRedirects(self.client.post(
            reverse("products:delete_review", args=[review.pk]), **headers,
        ), detail)
        self.assertFalse(Review.objects.filter(pk=review.pk).exists())

    def test_public_pages_and_cart_remain_available_without_purchase_controls(self):
        detail = reverse("products:product_detail", args=[self.product.slug])
        for url in (reverse("home:index"), reverse("products:products"), detail):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "Todavía no aceptamos pedidos ni pagos")
                self.assertNotContains(response, "https://js.stripe.com")
                self.assertNotContains(response, reverse("bag:add_to_bag", args=[self.product.pk]))

        bag = reverse("bag:view_bag")
        self.assertRedirects(self.client.post(
            reverse("bag:add_to_bag", args=[self.product.pk]),
            {"quantity": 1, "redirect_url": bag},
        ), bag)
        self.assertRedirects(self.client.post(
            reverse("bag:adjust_bag", args=[self.product.pk]), {"quantity": 2},
        ), bag)
        response = self.client.get(bag)
        self.assertContains(response, self.product.name)
        self.assertNotContains(response, reverse("checkout:checkout"))
        self.assertNotContains(response, "https://js.stripe.com")
        self.assertEqual(self.client.session["bag"][str(self.product.pk)], 2)
        self.assertEqual(self.client.post(
            reverse("bag:remove_from_bag", args=[self.product.pk]),
        ).status_code, 200)
        self.assertEqual(self.client.session["bag"], {})

    def test_empty_catalog_is_available(self):
        Product.objects.all().delete()
        self.assertContains(self.client.get(reverse("products:products")), "Todos los Productos")
