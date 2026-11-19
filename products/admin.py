from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import path
from django.views.decorators.http import require_POST
from checkout.store_mode import sales_enabled
from .models import (
    Brand, Category, Product, Gender, FragranceFamily,
    FragranceNote, Review, ReviewImage, Wishlist,
    PriceAlert, StockAlert, CatalogImage, PublicationDecision
)
from .publication import decide_image, decide_product
from .admin_extended import (
    ProductSizeInline, ProductVideoInline, FragranceEvolutionInline
)


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    change_form_template = "admin/products/publication_change.html"
    readonly_fields = ("publication_status",)

    def get_urls(self):
        return [
            path("<int:object_id>/decision/<str:decision>/",
                 self.admin_site.admin_view(require_POST(self.publication_decision)),
                 name="products_product_decision"),
        ] + super().get_urls()

    def publication_decision(self, request, object_id, decision):
        product = get_object_or_404(Product, pk=object_id)
        if not self.has_change_permission(request, product) or not request.user.has_perm("products.publish_product"):
            raise PermissionDenied
        try:
            decide_product(product, decision, request.user)
        except ValidationError as exc:
            self.message_user(request, " ".join(exc.messages), level="error")
        else:
            self.message_user(request, "Decisión de publicación registrada.")
        return redirect("admin:products_product_change", object_id)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and (obj.publication_history.exists() or obj.catalog_images.exists()):
            return False
        if not sales_enabled() and obj is not None and obj.cartitem_set.exists():
            return False
        return super().has_delete_permission(request, obj)

    list_display = (
        "sku",
        "name",
        "publication_status",
        "brand",
        "category",
        "concentration",
        "size",
        "price",
        "rating",
        "stock",
        "gender",
    )
    list_filter = (
        "publication_status",
        "brand",
        "category",
        "gender",
        "concentration",
        "size",
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
    inlines = [ProductSizeInline, ProductVideoInline, FragranceEvolutionInline]
    fieldsets = (
        ("Publicación", {"fields": ("publication_status", "verification_sources")}),
        ("Información Básica", {
            "fields": (
                "name", "sku", "brand", "category",
                "gender", "description"
            )
        }),
        ("Información Esencial de Perfumería", {
            "fields": ("concentration", "size"),
            "description": (
                "Concentración (EDT/EDP/Parfum) y tamaño son "
                "información CRÍTICA para clientes"
            )
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


@admin.register(CatalogImage)
class CatalogImageAdmin(admin.ModelAdmin):
    change_form_template = "admin/products/image_change.html"
    list_display = ("product", "source_file", "approved_at", "approved_by", "withdrawn_at")
    search_fields = ("product__name", "source_file")
    autocomplete_fields = ("product",)
    readonly_fields = ("asset", "thumbnail", "approved_at", "approved_by", "withdrawn_at")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_public:
            return (*self.readonly_fields, "product", "source_file", "source_reference", "rights_reference")
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        return [
            path("<int:object_id>/decision/<str:decision>/",
                 self.admin_site.admin_view(require_POST(self.publication_decision)),
                 name="products_catalogimage_decision"),
        ] + super().get_urls()

    def publication_decision(self, request, object_id, decision):
        image = get_object_or_404(CatalogImage, pk=object_id)
        if not self.has_change_permission(request, image) or not request.user.has_perm("products.approve_catalogimage"):
            raise PermissionDenied
        if decision not in {"approve", "withdraw"}:
            raise PermissionDenied
        try:
            decide_image(image, decision == "approve", request.user)
        except ValidationError as exc:
            self.message_user(request, " ".join(exc.messages), level="error")
        else:
            self.message_user(request, "Decisión sobre la imagen registrada.")
        return redirect("admin:products_catalogimage_change", object_id)


@admin.register(PublicationDecision)
class PublicationDecisionAdmin(admin.ModelAdmin):
    list_display = ("product", "status", "reviewer", "decided_at")
    readonly_fields = ("product", "status", "reviewer", "decided_at", "evidence")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
    fields = ("user", "product", "email", "consent_version", "consent_requested_at",
              "confirmed_at", "withdrawn_at", "is_notified", "notified_at", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

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

