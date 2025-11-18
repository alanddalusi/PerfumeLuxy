from django.urls import path
from . import views

urlpatterns = [
    path("", views.all_products, name="products"),
    path("families/", views.fragrance_families_guide, name="fragrance_families"),
    path("<slug:slug>/", views.product_detail, name="product_detail"),
    path("add/", views.add_product, name="add_product"),
    path("edit/<int:product_id>/", views.edit_product, name="edit_product"),
    path(
        "delete/<int:product_id>/",
        views.delete_product,
        name="delete_product"),
    
    # Wishlist
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/toggle/<int:product_id>/", views.toggle_wishlist, name="toggle_wishlist"),
    
    # Comparación
    path("compare/", views.compare_products, name="compare_products"),
    
    # Reviews
    path("<int:product_id>/review/add/", views.add_review, name="add_review"),
    
    # Alertas
    path("<int:product_id>/alert/price/", views.create_price_alert, name="create_price_alert"),
    path("<int:product_id>/alert/stock/", views.create_stock_alert, name="create_stock_alert"),
    
    # Quiz
    path("quiz/", views.perfume_quiz, name="perfume_quiz"),
    path("quiz/results/", views.quiz_results, name="quiz_results"),
]
