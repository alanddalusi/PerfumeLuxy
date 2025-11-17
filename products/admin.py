from django.contrib import admin
from .models import (
    Brand, Category, Product, Gender, FragranceFamily,
    FragranceNote, Review, ReviewImage, Wishlist,
    PriceAlert, StockAlert
)


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "brand",
        "category",
        "price",
        "rating",
        "stock",
        "intensity",
        "duration",
        "gender",
    )
    list_filter = (
        "brand",
        "category",
        "gender",
        "fragrance_family",
        "intensity",
        "duration",
        "occasion",
        "season",
        "is_original",
        "is_tester",
    )
    search_fields = ("name", "sku", "description")
    filter_horizontal = ("fragrance_notes",)
    ordering = ("sku",)
    fieldsets = (
        ("Información Básica", {
            "fields": ("name", "sku", "brand", "category", "gender", "description")
        }),
        ("Precio y Stock", {
            "fields": ("price", "stock", "has_discount", "has_subscription")
        }),
        ("Características del Perfume", {
            "fields": (
                "fragrance_family", "fragrance_notes", "intensity",
                "duration", "projection", "scent"
            )
        }),
        ("Uso Recomendado", {
            "fields": ("occasion", "season")
        }),
        ("Imágenes", {
            "fields": ("image", "image_url")
        }),
        ("Otros", {
            "fields": (
                "has_sizes", "is_original", "is_tester",
                "rating", "meta_description"
            )
        }),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "user",
        "rating",
        "is_verified_purchase",
        "is_approved",
        "created_at",
    )
    list_filter = (
        "rating",
        "is_verified_purchase",
        "is_approved",
        "skin_type",
        "created_at",
    )
    search_fields = ("product__name", "user__username", "comment")
    inlines = [ReviewImageInline]
    actions = ["approve_reviews", "disapprove_reviews"]

    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
    approve_reviews.short_description = "Aprobar reseñas seleccionadas"

    def disapprove_reviews(self, request, queryset):
        queryset.update(is_approved=False)
    disapprove_reviews.short_description = "Desaprobar reseñas seleccionadas"


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "product_count")
    search_fields = ("user__username",)
    filter_horizontal = ("products",)

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = "Productos"


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "product",
        "target_price",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("user__username", "product__name")


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "product",
        "email",
        "is_notified",
        "created_at",
    )
    list_filter = ("is_notified", "created_at")
    search_fields = ("user__username", "product__name", "email")


@admin.register(FragranceFamily)
class FragranceFamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(FragranceNote)
class FragranceNoteAdmin(admin.ModelAdmin):
    list_display = ("name", "note_type")
    list_filter = ("note_type",)
    search_fields = ("name",)


@admin.register(Brand, Category, Gender)
class DatabaseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "db_name",
    )

    ordering = ("id",)

