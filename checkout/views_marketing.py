"""
Vistas de Marketing para Checkout
Sistema de cupones, bundles y loyalty integrado
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone

from .marketing_models import Coupon, CouponUsage, Bundle, LoyaltyProgram, LoyaltyTransaction
from products.models import Product


@require_POST
def apply_coupon(request):
    """Aplicar cupón de descuento al carrito"""
    code = request.POST.get('coupon_code', '').strip().upper()
    
    if not code:
        messages.error(request, 'Por favor ingresa un código de cupón')
        return redirect('checkout:checkout')
    
    try:
        coupon = Coupon.objects.get(code=code)
        
        # Validar cupón
        is_valid, message = coupon.is_valid()
        if not is_valid:
            messages.error(request, f'Cupón inválido: {message}')
            return redirect('checkout:checkout')
        
        # Verificar si el usuario puede usarlo
        if request.user.is_authenticated:
            can_use, message = coupon.can_be_used_by(request.user)
            if not can_use:
                messages.error(request, message)
                return redirect('checkout:checkout')
        
        # Calcular descuento (necesitas implementar get_cart_total y get_cart_products)
        bag = request.session.get('bag', {})
        if not bag:
            messages.error(request, 'Tu carrito está vacío')
            return redirect('checkout:checkout')
        
        # Calcular total del carrito
        cart_total = 0
        products = []
        for item_id, item_data in bag.items():
            product = Product.objects.get(id=item_id)
            if isinstance(item_data, int):
                cart_total += product.price * item_data
                products.append(product)
            else:
                for size, quantity in item_data['items_by_size'].items():
                    cart_total += product.price * quantity
                    products.append(product)
        
        # Calcular descuento
        discount = coupon.calculate_discount(cart_total, products)
        
        if discount == 0 and coupon.discount_type != 'free_shipping':
            messages.error(request, 'Este cupón no es aplicable a tu carrito')
            return redirect('checkout:checkout')
        
        # Guardar en sesión
        request.session['coupon_id'] = coupon.id
        request.session['coupon_code'] = coupon.code
        request.session['discount'] = float(discount)
        request.session['free_shipping'] = coupon.discount_type == 'free_shipping'
        
        if coupon.discount_type == 'free_shipping':
            messages.success(request, f'¡Cupón {code} aplicado! Envío gratis activado')
        else:
            messages.success(request, f'¡Cupón {code} aplicado! Descuento: €{discount:.2f}')
        
    except Coupon.DoesNotExist:
        messages.error(request, 'Cupón no válido')
    
    return redirect('checkout:checkout')


@require_POST
def remove_coupon(request):
    """Eliminar cupón del carrito"""
    if 'coupon_id' in request.session:
        del request.session['coupon_id']
    if 'coupon_code' in request.session:
        del request.session['coupon_code']
    if 'discount' in request.session:
        del request.session['discount']
    if 'free_shipping' in request.session:
        del request.session['free_shipping']
    
    messages.info(request, 'Cupón eliminado')
    return redirect('checkout:checkout')


def register_coupon_usage(order, user):
    """
    Registrar uso de cupón después de completar orden
    Llamar desde checkout_success
    """
    from django.http import HttpRequest
    
    # Si es un HttpRequest, obtener sesión
    if isinstance(order, HttpRequest):
        request = order
        session = request.session
    else:
        # Asumir que order es el objeto Order y user tiene sesión
        return
    
    coupon_id = session.get('coupon_id')
    discount = session.get('discount', 0)
    
    if coupon_id and discount:
        try:
            coupon = Coupon.objects.get(id=coupon_id)
            
            # Registrar uso
            CouponUsage.objects.create(
                coupon=coupon,
                user=user,
                order_id=order.order_number if hasattr(order, 'order_number') else 'ORDER',
                discount_amount=discount
            )
            
            # Incrementar contador
            coupon.times_used += 1
            coupon.save()
            
            # Limpiar sesión
            del session['coupon_id']
            if 'coupon_code' in session:
                del session['coupon_code']
            if 'discount' in session:
                del session['discount']
            if 'free_shipping' in session:
                del session['free_shipping']
                
        except Coupon.DoesNotExist:
            pass


@login_required
def loyalty_dashboard(request):
    """Dashboard del programa de fidelización"""
    loyalty, created = LoyaltyProgram.objects.get_or_create(user=request.user)
    
    # Obtener transacciones recientes
    transactions = loyalty.transactions.all()[:20]
    
    # Calcular estadísticas
    total_earned = loyalty.transactions.filter(
        transaction_type='earn'
    ).aggregate(total=models.Sum('points'))['total'] or 0
    
    total_redeemed = loyalty.transactions.filter(
        transaction_type='redeem'
    ).aggregate(total=models.Sum('points'))['total'] or 0
    
    # Calcular puntos disponibles para canje
    available_to_redeem = (loyalty.points // 100) * 100  # Múltiplos de 100
    discount_value = (available_to_redeem / 100) * 5  # 100 puntos = 5€
    
    context = {
        'loyalty': loyalty,
        'transactions': transactions,
        'total_earned': total_earned,
        'total_redeemed': abs(total_redeemed),
        'available_to_redeem': available_to_redeem,
        'discount_value': discount_value,
        'tier_benefits': get_tier_benefits(loyalty.tier),
    }
    
    return render(request, 'checkout/loyalty_dashboard.html', context)


@login_required
@require_POST
def redeem_points(request):
    """Canjear puntos por descuento"""
    points_to_redeem = int(request.POST.get('points', 0))
    
    if points_to_redeem < 100:
        messages.error(request, 'Debes canjear mínimo 100 puntos')
        return redirect('loyalty_dashboard')
    
    if points_to_redeem % 100 != 0:
        messages.error(request, 'Los puntos deben ser múltiplos de 100')
        return redirect('loyalty_dashboard')
    
    try:
        loyalty = LoyaltyProgram.objects.get(user=request.user)
        success, result = loyalty.redeem_points(points_to_redeem)
        
        if success:
            discount = result
            
            # Registrar transacción
            LoyaltyTransaction.objects.create(
                loyalty_program=loyalty,
                transaction_type='redeem',
                points=points_to_redeem,
                description=f'Canje por €{discount:.2f} de descuento'
            )
            
            # Guardar descuento en sesión
            request.session['loyalty_discount'] = float(discount)
            request.session['loyalty_points_used'] = points_to_redeem
            
            messages.success(
                request,
                f'¡{points_to_redeem} puntos canjeados! Tienes €{discount:.2f} de descuento'
            )
            return redirect('checkout:checkout')
        else:
            messages.error(request, result)
            
    except LoyaltyProgram.DoesNotExist:
        messages.error(request, 'No tienes un programa de lealtad')
    
    return redirect('loyalty_dashboard')


@require_POST
def remove_loyalty_discount(request):
    """Eliminar descuento de loyalty del carrito"""
    points_used = request.session.get('loyalty_points_used', 0)
    
    if points_used:
        # Devolver puntos
        try:
            loyalty = LoyaltyProgram.objects.get(user=request.user)
            loyalty.points += points_used
            loyalty.save()
            
            # Registrar transacción
            LoyaltyTransaction.objects.create(
                loyalty_program=loyalty,
                transaction_type='earn',
                points=points_used,
                description='Puntos devueltos (descuento cancelado)'
            )
        except LoyaltyProgram.DoesNotExist:
            pass
    
    if 'loyalty_discount' in request.session:
        del request.session['loyalty_discount']
    if 'loyalty_points_used' in request.session:
        del request.session['loyalty_points_used']
    
    messages.info(request, 'Descuento de lealtad eliminado')
    return redirect('checkout:checkout')


def add_loyalty_points(user, amount_spent, order_number):
    """
    Añadir puntos después de completar orden
    Llamar desde checkout_success
    """
    if not user.is_authenticated:
        return
    
    loyalty, created = LoyaltyProgram.objects.get_or_create(user=user)
    points_earned = loyalty.add_points(amount_spent)
    
    # Registrar transacción
    LoyaltyTransaction.objects.create(
        loyalty_program=loyalty,
        transaction_type='earn',
        points=points_earned,
        description=f'Compra #{order_number}',
        order_id=order_number
    )
    
    return points_earned


def get_tier_benefits(tier):
    """Obtener beneficios según tier"""
    benefits = {
        'bronze': [
            'Acumula 1 punto por cada €1',
            'Acceso a ofertas exclusivas',
        ],
        'silver': [
            'Acumula 1 punto por cada €1',
            'Envío gratis en todos los pedidos',
            'Acceso prioritario a nuevos lanzamientos',
            '5% de descuento adicional en cumpleaños',
        ],
        'gold': [
            'Acumula 1.5 puntos por cada €1',
            'Envío express gratis',
            'Muestras gratis en cada pedido',
            '10% de descuento en cumpleaños',
            'Invitaciones a eventos exclusivos',
        ],
        'platinum': [
            'Acumula 2 puntos por cada €1',
            'Envío express gratis internacional',
            'Regalos exclusivos',
            '15% de descuento en cumpleaños',
            'Asesor personal de fragancias',
            'Acceso VIP a lanzamientos',
        ],
    }
    
    return benefits.get(tier, benefits['bronze'])


# API endpoints para AJAX
@require_POST
def validate_coupon_ajax(request):
    """Validar cupón vía AJAX sin aplicar"""
    code = request.POST.get('code', '').strip().upper()
    
    try:
        coupon = Coupon.objects.get(code=code)
        is_valid, message = coupon.is_valid()
        
        if is_valid and request.user.is_authenticated:
            can_use, message = coupon.can_be_used_by(request.user)
            if not can_use:
                is_valid = False
        
        return JsonResponse({
            'valid': is_valid,
            'message': message,
            'discount_type': coupon.discount_type if is_valid else None,
            'discount_value': float(coupon.discount_value) if is_valid else None,
        })
        
    except Coupon.DoesNotExist:
        return JsonResponse({
            'valid': False,
            'message': 'Cupón no encontrado'
        })
