from django.shortcuts import (
    render, redirect, reverse, get_object_or_404, HttpResponse,)
from django.views.decorators.http import require_POST, require_safe
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages


from .forms import OrderForm
from .store_mode import require_live_store
from .models import Order, CartItem

from bag.contexts import bag_contents
from products.models import Product
from profiles.models import UserProfile

import stripe
import json


@require_live_store
@require_POST
def cache_checkout_data(request):
    try:
        pid = request.POST.get("client_secret").split("_secret")[0]
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.PaymentIntent.modify(
            pid,
            metadata={
                "bag": json.dumps(request.session.get("bag", {})),
                "save_info": request.POST.get("save_info"),
                "username": request.user,
            },
        )
        return HttpResponse(status=200)
    except Exception as e:
        messages.error(
            request,
            (
                "Sorry, your payment cannot be "
                "processed right now. Please try "
                "again later."
            )
        )
        return HttpResponse(content=e, status=400)


@require_live_store
def checkout(request):
    """
    View to return user input when filling forms and handle stripe
    payments
    """

    stripe_public_key = settings.STRIPE_PUBLIC_KEY
    stripe_secret_key = settings.STRIPE_SECRET_KEY

    intent = None
    if request.method == "POST":
        bag = request.session.get("bag", {})
        form_data = {
            "full_name": request.POST["full_name"],
            "email": request.POST["email"],
            "phone_number": request.POST["phone_number"],
            "street_address1": request.POST["street_address1"],
            "street_address2": request.POST["street_address2"],
            "town_or_city": request.POST["town_or_city"],
            "county": request.POST["county"],
            "postcode": request.POST["postcode"],
            "country": request.POST["country"],
        }

        order_form = OrderForm(form_data)
        if order_form.is_valid():
            order = order_form.save(commit=False)
            pid = request.POST.get("client_secret").split("_secret")[0]
            order.stripe_pid = pid
            order.original_bag = json.dumps(bag)
            if request.user.is_authenticated:
                order.user_profile = UserProfile.objects.filter(user=request.user).first()
            order.save()
            for item_id, item_data in bag.items():
                try:
                    product = Product.objects.get(id=item_id)
                    if isinstance(item_data, int):
                        order_cart_item = CartItem(
                            order=order,
                            product=product,
                            quantity=item_data,
                            product_size="",
                        )
                        order_cart_item.save()
                    else:
                        item_data_items = item_data["items_by_size"].items()
                        for size, quantity in item_data_items:
                            order_cart_item = CartItem(
                                order=order,
                                product=product,
                                quantity=quantity,
                                product_size=size,
                            )
                            order_cart_item.save()
                except Product.DoesNotExist:
                    messages.error(
                        request,
                        (
                            "One of the products in your bag wasn't "
                            "found in our database. "
                            "Please call us for assistance!"
                        )
                    )
                    order.delete()
                    return redirect(reverse("bag:view_bag"))

            for key in (
                "bag", "save_info", "coupon_id", "coupon_code", "discount",
                "free_shipping", "loyalty_discount", "loyalty_points_used",
            ):
                request.session.pop(key, None)

            if order.user_profile_id:
                return redirect("checkout:checkout_success", order_number=order.order_number)
            return redirect("home:index")
        else:
            messages.error(request, "There was an error with form")
    else:
        bag = request.session.get("bag", {})
        if not bag:
            messages.error(
                request,
                "There's nothing in your bag at the moment"
            )
            return redirect(reverse("products:products"))

        current_bag = bag_contents(request)
        total = current_bag["total"]
        stripe_total = round(total * 100)
        
        # Verificar que las claves de Stripe estén configuradas
        intent = None
        mock_key = "sk_test_51234567890abcdef"
        if not stripe_secret_key or stripe_secret_key == mock_key:
            # Crear un intent mock para desarrollo sin Stripe válido
            class MockIntent:
                client_secret = "pi_mock_secret_for_development"
            intent = MockIntent()
            messages.warning(
                request,
                "Demo mode: Using mock payment processing. "
                "Configure Stripe for real payments."
            )
        else:
            stripe.api_key = stripe_secret_key
            try:
                intent = stripe.PaymentIntent.create(
                    amount=stripe_total,
                    currency=settings.STRIPE_CURRENCY,
                )
            except Exception:
                messages.error(
                    request,
                    (
                        "Error processing your payment. "
                        "You have not been charged. "
                        "Please try again later"
                    )
                )
                return redirect(reverse("bag:view_bag"))

        if request.user.is_authenticated:
            try:
                profile = UserProfile.objects.get(user=request.user)
                order_form = OrderForm(
                    initial={
                        "full_name": profile.user.get_full_name(),
                        "email": profile.user.email,
                        "phone_number": profile.default_phone_number,
                        "street_address1": profile.default_street_address1,
                        "street_address2": profile.default_street_address2,
                        "town_or_city": profile.default_town_or_city,
                        "county": profile.default_county,
                        "postcode": profile.default_postcode,
                        "country": profile.default_country,
                    }
                )
            except UserProfile.DoesNotExist:
                order_form = OrderForm()
        else:
            order_form = OrderForm()

    if not stripe_public_key:
        messages.warning(
            request,
            (
                "Stripe public key is missing. "
                "Did you forget to set it in your environment?"
            )
        )

    template = "checkout/checkout_luxury.html"

    context = {
        "order_form": order_form,
        "stripe_public_key": stripe_public_key,
        "client_secret": intent.client_secret if intent else "",
    }

    return render(request, template, context)


@never_cache
@login_required
@require_safe
def checkout_success(request, order_number):
    order = get_object_or_404(
        Order, order_number=order_number, user_profile__user=request.user
    )
    return render(request, "checkout/checkout_success_luxury.html", {
        "order": order,
        "on_checkout_success": True,
    })
