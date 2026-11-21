from django.urls import path
from . import views
from . import views_reviews_wishlist
from . import views_advanced

app_name = 'products'

urlpatterns = [
    path("", views.all_products, name="products"),
    # Numeric renditions first: "320.webp" would otherwise match the legacy web/thumb route.
    path("image/<int:image_id>/<int:box>.<str:fmt>", views.catalog_rendition, name="catalog_rendition"),
    path("image/<int:image_id>/<slug:name>-<int:box>.<str:fmt>", views.catalog_rendition_named,
         name="catalog_rendition_named"),   # before <variant>.webp, which would swallow it
    path("image/<int:image_id>/<str:variant>.webp", views.catalog_image, name="catalog_image"),
    path("api/search/", views.search_suggestions, name="search_suggestions"),
    path("families/", views.fragrance_families_guide, name="fragrance_families"),
    
    # Wishlist (mejorado)
    path("wishlist/", views_reviews_wishlist.view_wishlist, name="view_wishlist"),
    path("wishlist/toggle/<int:product_id>/", views_reviews_wishlist.toggle_wishlist, name="toggle_wishlist"),
    path("wishlist/clear/", views_reviews_wishlist.clear_wishlist, name="clear_wishlist"),
    
    # Comparación (avanzado)
    path("compare/", views_advanced.compare_products, name="compare_products"),
    path("comparison/add/<int:product_id>/", views_advanced.add_to_comparison, name="add_to_comparison"),
    path("comparison/remove/<int:product_id>/", views_advanced.remove_from_comparison, name="remove_from_comparison"),
    path("comparison/clear/", views_advanced.clear_comparison, name="clear_comparison"),
    path("comparison/save/", views_advanced.save_comparison, name="save_comparison"),
    
    # Muestras gratis
    path("samples/request/<int:product_id>/", views_advanced.request_sample, name="request_sample"),
    path("samples/my-samples/", views_advanced.my_sample_requests, name="my_samples"),
    
    # Quiz de fragancias
    path("quiz/", views_advanced.fragrance_quiz_start, name="fragrance_quiz"),
    path("quiz/results/", views_advanced.fragrance_quiz_results, name="quiz_results"),
    
    # Perfil olfativo
    path("profile/fragrance/", views_advanced.fragrance_profile, name="fragrance_profile"),
    
    # Notificaciones de stock
    path("notify/<int:product_id>/", views_advanced.notify_when_available, name="notify_when_available"),
    
    # API para selector de tamaños
    path("api/sizes/<int:product_id>/", views_advanced.get_product_sizes, name="get_product_sizes"),
    
    # Reviews (mejorado)
    path("review/add/<int:product_id>/", views_reviews_wishlist.add_review, name="add_review"),
    path("review/delete/<int:review_id>/", views_reviews_wishlist.delete_review, name="delete_review"),
    path("review/helpful/<int:review_id>/", views_reviews_wishlist.mark_review_helpful, name="mark_review_helpful"),
    
    # Product detail debe ir al final para no capturar otras URLs
    path("add/", views.add_product, name="add_product"),
    path("edit/<int:product_id>/", views.edit_product, name="edit_product"),
    path("delete/<int:product_id>/", views.delete_product, name="delete_product"),
    path("<slug:slug>/", views.product_detail, name="product_detail"),
]
