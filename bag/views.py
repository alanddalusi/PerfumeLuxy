from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from products.models import Product

from .contexts import BAG_SIZES


def view_bag(request):
    return render(request, "bag/bag.html")


def update_bag(request, item_id, operation):
    if not item_id.isascii() or not item_id.isdigit() or len(item_id) > 19 or int(item_id) > 2**63 - 1:
        raise Http404
    item_id = str(int(item_id))
    product = get_object_or_404(Product.objects.sellable() if operation != "remove" else Product, pk=item_id)
    size = request.POST.get("product_size") or "onesize"
    if size not in BAG_SIZES or (size != "onesize" and not product.has_sizes):
        return HttpResponseBadRequest("Formato no válido.")

    bag = request.session.get("bag", {})
    entry = bag.get(item_id, 0)
    sizes = entry.get("items_by_size", {}) if isinstance(entry, dict) else {"onesize": entry}
    if operation == "remove":
        quantity = 0
    else:
        try:
            quantity = int(request.POST.get("quantity", ""))
        except ValueError:
            return HttpResponseBadRequest("Cantidad no válida.")
        if product.price is None or quantity < (1 if operation == "add" else 0):
            return HttpResponseBadRequest("Cantidad o producto no válido.")
        if operation == "add":
            quantity += sizes.get(size, 0)
        if quantity > 6:
            return HttpResponseBadRequest("La cantidad máxima por formato es 6.")

    if quantity:
        sizes[size] = quantity
    else:
        sizes.pop(size, None)
    sizes = {key: value for key, value in sizes.items() if value}
    if not sizes:
        bag.pop(item_id, None)
    elif set(sizes) == {"onesize"}:
        bag[item_id] = sizes["onesize"]
    else:
        bag[item_id] = {"items_by_size": sizes}

    request.session["bag"] = bag
    messages.success(request, f"Carrito actualizado: {product.name}")
    if operation == "remove":
        return HttpResponse()
    target = request.POST.get("redirect_url") if operation == "add" else None
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect("bag:view_bag")


@require_POST
def add_to_bag(request, item_id):
    return update_bag(request, item_id, "add")


@require_POST
def adjust_bag(request, item_id):
    return update_bag(request, item_id, "adjust")


@require_POST
def remove_from_bag(request, item_id):
    return update_bag(request, item_id, "remove")
