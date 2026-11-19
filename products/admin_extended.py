"""
Admin para modelos extendidos de perfumería
ProductSize, ProductVideo, SampleRequest, UserFragranceProfile, etc.
"""
from django.contrib import admin
from checkout.store_mode import CommercialAdminMixin
from django.utils.html import format_html
from .models_extended import (
    ProductSize,
    ProductVideo,
    SampleRequest,
    UserFragranceProfile,
    FragranceEvolution,
    ProductComparison
)


# ============================================
# INLINES (para usar en ProductAdmin)
# ============================================

class ProductSizeInline(admin.TabularInline):
    model = ProductSize
    extra = 1
    fields = (
        'size_ml', 'price', 'stock', 'sku',
        'is_popular', 'is_best_value', 'image'
    )
    readonly_fields = ('price_per_ml_display',)
    
    def price_per_ml_display(self, obj):
        if obj.pk:
            return f"€{obj.price_per_ml}/ml"
        return "-"
    price_per_ml_display.short_description = 'Precio/ml'


class ProductVideoInline(admin.TabularInline):
    model = ProductVideo
    extra = 1
    fields = ('title', 'video_url', 'thumbnail', 'order', 'is_active')
    

class FragranceEvolutionInline(admin.StackedInline):
    model = FragranceEvolution
    extra = 0
    max_num = 1
    fields = (
        ('top_notes', 'top_notes_duration'),
        'top_notes_description',
        ('heart_notes', 'heart_notes_duration'),
        'heart_notes_description',
        ('base_notes', 'base_notes_duration'),
        'base_notes_description',
    )


# ============================================
# ADMIN MODELS
# ============================================

@admin.register(ProductSize)
class ProductSizeAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'size_ml', 'price', 'price_per_ml_display',
        'stock', 'stock_badge', 'badges_display'
    ]
    list_filter = ['is_popular', 'is_best_value', 'size_ml']
    search_fields = ['product__name', 'sku']
    list_editable = ['price', 'stock']
    readonly_fields = ['price_per_ml_display']
    
    def price_per_ml_display(self, obj):
        return f"€{obj.price_per_ml}/ml"
    price_per_ml_display.short_description = 'Precio/ml'
    price_per_ml_display.admin_order_field = 'price'
    
    def stock_badge(self, obj):
        if obj.stock > 10:
            color = 'green'
            text = 'En stock'
        elif obj.stock > 0:
            color = 'orange'
            text = 'Bajo stock'
        else:
            color = 'red'
            text = 'Agotado'
        
        return format_html(
            '<span style="padding:3px 10px;border-radius:3px;'
            'background:{};color:white;font-weight:600">{}</span>',
            color, text
        )
    stock_badge.short_description = 'Estado'
    
    def badges_display(self, obj):
        badges = []
        if obj.is_popular:
            badges.append('⭐ Popular')
        if obj.is_best_value:
            badges.append('💎 Mejor valor')
        return ' '.join(badges) if badges else '-'
    badges_display.short_description = 'Badges'


@admin.register(ProductVideo)
class ProductVideoAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'title', 'video_type',
        'order', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['product__name', 'title']
    list_editable = ['order', 'is_active']
    readonly_fields = ['embed_preview', 'created_at']
    
    def video_type(self, obj):
        url = obj.video_url.lower()
        if 'youtube' in url or 'youtu.be' in url:
            return '📺 YouTube'
        elif 'vimeo' in url:
            return '🎬 Vimeo'
        return '🔗 Otro'
    video_type.short_description = 'Tipo'
    
    def embed_preview(self, obj):
        if obj.pk:
            embed = obj.embed_url
            return format_html(
                '<iframe width="560" height="315" src="{}" '
                'frameborder="0" allowfullscreen></iframe>',
                embed
            )
        return "Guarda primero para ver preview"
    embed_preview.short_description = 'Preview'


@admin.register(SampleRequest)
class SampleRequestAdmin(CommercialAdminMixin, admin.ModelAdmin):
    list_display = [
        'id', 'product', 'user_email', 'status_badge',
        'created_at', 'city', 'country'
    ]
    list_filter = ['status', 'country', 'created_at', 'approved_at']
    search_fields = [
        'user__email', 'email', 'full_name',
        'product__name', 'tracking_number'
    ]
    readonly_fields = [
        'created_at', 'approved_at', 'sent_at', 'delivered_at'
    ]
    
    fieldsets = (
        ('Producto y Usuario', {
            'fields': ('product', 'user')
        }),
        ('Información Personal', {
            'fields': ('full_name', 'email', 'phone')
        }),
        ('Dirección de Envío', {
            'fields': (
                'address', 'postal_code', 'city', 'country'
            )
        }),
        ('Estado', {
            'fields': (
                'status', 'tracking_number', 'admin_notes'
            )
        }),
        ('Fechas', {
            'fields': (
                'created_at', 'approved_at', 'sent_at', 'delivered_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_approved', 'mark_sent', 'mark_delivered', 'mark_rejected']
    
    def user_email(self, obj):
        return obj.user.email if obj.user else obj.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'email'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'approved': '#17a2b8',
            'sent': '#007bff',
            'delivered': '#28a745',
            'rejected': '#dc3545',
        }
        labels = {
            'pending': '⏳ Pendiente',
            'approved': '✅ Aprobada',
            'sent': '📦 Enviada',
            'delivered': '🎁 Entregada',
            'rejected': '❌ Rechazada',
        }
        
        return format_html(
            '<span style="padding:5px 12px;border-radius:15px;'
            'background:{};color:white;font-weight:600">{}</span>',
            colors[obj.status], labels[obj.status]
        )
    status_badge.short_description = 'Estado'
    status_badge.admin_order_field = 'status'
    
    def mark_approved(self, request, queryset):
        queryset.update(status='approved', approved_at=timezone.now())
        self.message_user(request, f'{queryset.count()} muestras aprobadas')
    mark_approved.short_description = '✅ Marcar como aprobadas'
    
    def mark_sent(self, request, queryset):
        queryset.update(status='sent', sent_at=timezone.now())
        self.message_user(request, f'{queryset.count()} muestras marcadas como enviadas')
    mark_sent.short_description = '📦 Marcar como enviadas'
    
    def mark_delivered(self, request, queryset):
        queryset.update(status='delivered', delivered_at=timezone.now())
        self.message_user(request, f'{queryset.count()} muestras entregadas')
    mark_delivered.short_description = '🎁 Marcar como entregadas'
    
    def mark_rejected(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f'{queryset.count()} muestras rechazadas')
    mark_rejected.short_description = '❌ Marcar como rechazadas'


@admin.register(UserFragranceProfile)
class UserFragranceProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'preferred_intensity', 'preferred_duration',
        'price_range_display', 'profile_completeness'
    ]
    list_filter = [
        'preferred_intensity', 'preferred_duration', 'preferred_price_range'
    ]
    search_fields = ['user__email', 'user__username']
    filter_horizontal = [
        'preferred_families', 'preferred_notes', 'disliked_notes'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Usuario', {
            'fields': ('user',)
        }),
        ('Preferencias Olfativas', {
            'fields': (
                'preferred_families',
                'preferred_notes',
                'disliked_notes',
            )
        }),
        ('Preferencias de Perfume', {
            'fields': (
                'preferred_intensity',
                'preferred_duration',
                'preferred_price_range',
            )
        }),
        ('Ocasiones y Temporadas', {
            'fields': (
                'favorite_occasions',
                'favorite_seasons',
            )
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def price_range_display(self, obj):
        ranges = {
            'budget': '💵 Económico',
            'mid': '💰 Medio',
            'premium': '💎 Premium',
            'luxury': '👑 Lujo',
        }
        return ranges.get(obj.preferred_price_range, '-')
    price_range_display.short_description = 'Presupuesto'
    
    def profile_completeness(self, obj):
        score = 0
        if obj.preferred_families.exists():
            score += 25
        if obj.preferred_notes.exists():
            score += 25
        if obj.preferred_intensity:
            score += 15
        if obj.preferred_duration:
            score += 15
        if obj.favorite_occasions:
            score += 10
        if obj.favorite_seasons:
            score += 10
        
        if score >= 80:
            color = 'green'
        elif score >= 50:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color:{};font-weight:600">{} %</span>',
            color, score
        )
    profile_completeness.short_description = 'Completado'


@admin.register(FragranceEvolution)
class FragranceEvolutionAdmin(admin.ModelAdmin):
    list_display = ['product', 'duration_summary', 'created_at']
    search_fields = ['product__name', 'top_notes', 'heart_notes', 'base_notes']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Producto', {
            'fields': ('product',)
        }),
        ('Notas de Salida (Top)', {
            'fields': (
                'top_notes', 'top_notes_duration', 'top_notes_description'
            )
        }),
        ('Notas de Corazón (Heart)', {
            'fields': (
                'heart_notes', 'heart_notes_duration', 'heart_notes_description'
            )
        }),
        ('Notas de Fondo (Base)', {
            'fields': (
                'base_notes', 'base_notes_duration', 'base_notes_description'
            )
        }),
    )
    
    def duration_summary(self, obj):
        return f"{obj.get_top_notes_duration_display()} → " \
               f"{obj.get_heart_notes_duration_display()} → " \
               f"{obj.get_base_notes_duration_display()}"
    duration_summary.short_description = 'Duración'


@admin.register(ProductComparison)
class ProductComparisonAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'product_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'name']
    filter_horizontal = ['products']
    readonly_fields = ['created_at']
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Nº Productos'
