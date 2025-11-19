from django.urls import path
from . import views
from . import views_marketing
from .webhooks import webhook

app_name = 'checkout'
urlpatterns = [
    path("", views.checkout, name="checkout"),
    path(
        "checkout_success/<order_number>",
        views.checkout_success,
        name="checkout_success",
    ),
    path(
        "cache_checkout_data/",
        views.cache_checkout_data,
        name="cache_checkout_data",
    ),
    path("wh/", webhook, name="webhook"),
    
    # Marketing URLs
    path("apply-coupon/", views_marketing.apply_coupon, name="apply_coupon"),
    path("remove-coupon/", views_marketing.remove_coupon, name="remove_coupon"),
    path("validate-coupon/", views_marketing.validate_coupon_ajax, name="validate_coupon"),
    path("loyalty/", views_marketing.loyalty_dashboard, name="loyalty_dashboard"),
    path("redeem-points/", views_marketing.redeem_points, name="redeem_points"),
]
