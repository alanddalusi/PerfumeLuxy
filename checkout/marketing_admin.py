"""
Admin interface para sistema de Marketing
Cupones, Bundles y Programa de Lealtad
"""
from django.contrib import admin
from checkout.store_mode import CommercialAdminMixin
from django.utils.html import format_html
from django.utils import timezone
from .marketing_models import (
    Coupon, CouponUsage, Bundle, 
    LoyaltyProgram, LoyaltyTransaction
)


@admin.register(Coupon)
class CouponAdmin(CommercialAdminMixin, admin.ModelAdmin):
    list_display = [
        'code', 
        'discount_display', 
        'status_badge',
        'times_used',
        'usage_limit',
        'valid_from',
        'valid_to'
    ]
    list_filter = [
        'discount_type', 
        'is_active',
        'valid_from',
        'valid_to'
    ]
    search_fields = ['code', 'created_by__username']
    readonly_fields = ['times_used', 'created_at', 'created_by']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('code', 'discount_type', 'discount_value', 'is_active')
        }),
        ('Condiciones de Uso', {
            'fields': (
                'min_purchase_amount', 
                'max_discount_amount',
                'valid_from',
                'valid_to'
            )
        }),
        ('Límites de Uso', {
            'fields': (
                'usage_limit',
                'usage_limit_per_user',
                'times_used'
            )
        }),
        ('Restricciones (Dejar vacío para aplicar a todo)', {
            'fields': (
                'applicable_to_products',
                'applicable_to_categories',
                'applicable_to_brands'
            ),
            'classes': ('collapse',)
        }),
        ('Información de Creación', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    def discount_display(self, obj):
        """Muestra el descuento de forma visual"""
        return obj.get_discount_display()
    discount_display.short_description = 'Descuento'
    
    def status_badge(self, obj):
        """Badge colorido para el estado"""
        is_valid, message = obj.is_valid()
        if is_valid:
            color = 'green'
            icon = '✓'
            text = 'Activo'
        else:
            color = 'red'
            icon = '✗'
            text = message
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, text
        )
    status_badge.short_description = 'Estado'
    
    def save_model(self, request, obj, form, change):
        """Guarda el usuario que creó el cupón"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['activate_coupons', 'deactivate_coupons', 'generate_coupon_code']
    
    def activate_coupons(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} cupones activados.')
    activate_coupons.short_description = 'Activar cupones seleccionados'
    
    def deactivate_coupons(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} cupones desactivados.')
    deactivate_coupons.short_description = 'Desactivar cupones seleccionados'


@admin.register(CouponUsage)
class CouponUsageAdmin(CommercialAdminMixin, admin.ModelAdmin):
    list_display = [
        'coupon',
        'user',
        'order_id',
        'discount_amount',
        'used_at'
    ]
    list_filter = ['used_at', 'coupon']
    search_fields = ['user__username', 'coupon__code', 'order_id']
    readonly_fields = ['coupon', 'user', 'order_id', 'discount_amount', 'used_at']
    
    def has_add_permission(self, request):
        """No permitir creación manual"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """No permitir edición"""
        return False


@admin.register(Bundle)
class BundleAdmin(CommercialAdminMixin, admin.ModelAdmin):
    list_display = [
        'name',
        'bundle_type',
        'discount_percentage',
        'is_active',
        'valid_from',
        'valid_to',
        'status_badge'
    ]
    list_filter = ['bundle_type', 'is_active', 'valid_from']
    search_fields = ['name']
    filter_horizontal = ['products']
    
    fieldsets = (
        ('Información del Pack', {
            'fields': ('name', 'bundle_type', 'is_active')
        }),
        ('Productos Incluidos', {
            'fields': ('products',)
        }),
        ('Descuento (para tipo "Pack con Descuento")', {
            'fields': ('discount_percentage', 'fixed_price'),
            'description': 'Usa discount_percentage O fixed_price, no ambos'
        }),
        ('Validez', {
            'fields': ('valid_from', 'valid_to')
        })
    )
    
    def status_badge(self, obj):
        """Badge de estado del bundle"""
        if obj.is_valid():
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Activo</span>'
            )
        else:
            return format_html(
                '<span style="color: gray; font-weight: bold;">○ Inactivo</span>'
            )
    status_badge.short_description = 'Estado'


@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(CommercialAdminMixin, admin.ModelAdmin):
    list_display = [
        'user',
        'points_display',
        'tier_badge',
        'created_at',
        'updated_at'
    ]
    list_filter = ['tier', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Usuario', {
            'fields': ('user',)
        }),
        ('Información del Programa', {
            'fields': ('points', 'tier')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def points_display(self, obj):
        """Muestra puntos con formato"""
        return format_html(
            '<strong style="color: #d4af37; font-size: 1.1em;">{} pts</strong>',
            obj.points
        )
    points_display.short_description = 'Puntos'
    
    def tier_badge(self, obj):
        """Badge colorido según tier"""
        colors = {
            'bronze': '#CD7F32',
            'silver': '#C0C0C0',
            'gold': '#FFD700',
            'platinum': '#E5E4E2'
        }
        color = colors.get(obj.tier, '#999')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 3px; font-weight: bold; text-transform: uppercase;">{}</span>',
            color, obj.get_tier_display()
        )
    tier_badge.short_description = 'Nivel'
    
    actions = ['reset_points']
    
    def reset_points(self, request, queryset):
        """Resetear puntos (usar con cuidado)"""
        for loyalty in queryset:
            loyalty.points = 0
            loyalty.tier = 'bronze'
            loyalty.save()
        self.message_user(request, f'{queryset.count()} programas reseteados.')
    reset_points.short_description = '⚠️ Resetear puntos (CUIDADO)'


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(CommercialAdminMixin, admin.ModelAdmin):
    list_display = [
        'loyalty_program',
        'transaction_type',
        'points_display',
        'description',
        'order_id',
        'created_at'
    ]
    list_filter = ['transaction_type', 'created_at']
    search_fields = [
        'loyalty_program__user__username',
        'order_id',
        'description'
    ]
    readonly_fields = [
        'loyalty_program',
        'transaction_type',
        'points',
        'description',
        'order_id',
        'created_at'
    ]
    
    def points_display(self, obj):
        """Muestra puntos con + o -"""
        color = 'green' if obj.transaction_type in ['earn', 'bonus'] else 'red'
        sign = '+' if obj.transaction_type in ['earn', 'bonus'] else '-'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{}</span>',
            color, sign, abs(obj.points)
        )
    points_display.short_description = 'Puntos'
    
    def has_add_permission(self, request):
        """No permitir creación manual"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """No permitir edición"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminación (mantener historial)"""
        return False


# Personalización del sitio admin
admin.site.site_header = "PerfumeLuxe - Administración"
admin.site.site_title = "PerfumeLuxe Admin"
admin.site.index_title = "Panel de Control"
