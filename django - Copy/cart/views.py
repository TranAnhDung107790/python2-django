from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from catalog.models import Product
from orders.models import Order, OrderItem
from orders.notifier import send_order_confirmation

from .models import Cart, CartItem, Voucher, Voucher

SHIPPING_FEE_DEFAULT = 50000


def _voucher_code_for_cart(request, cart: Cart) -> str | None:
    sc = request.session.get("voucher_code")
    if sc:
        return str(sc)
    c = (cart.voucher_code or "").strip()
    return c or None


def _get_voucher(request, cart: Cart) -> Voucher | None:
    code = _voucher_code_for_cart(request, cart)
    if not code:
        return None
    v = Voucher.objects.filter(code__iexact=code, is_active=True).first()
    if not v:
        return None
    if cart.total < v.min_order:
        return None
    return v


def _calc_totals(cart_total: int, voucher: Voucher | None):
    shipping_fee = 0 if (voucher and voucher.free_ship) else SHIPPING_FEE_DEFAULT
    discount = voucher.discount if (voucher and not voucher.free_ship) else 0
    grand_total = max(0, cart_total - discount + shipping_fee)
    return shipping_fee, discount, grand_total


def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@login_required
def cart_detail(request):
    cart = _get_or_create_cart(request.user)
    voucher = _get_voucher(request, cart)
    shipping_fee, discount, grand_total = _calc_totals(cart.total, voucher)
    last_order = None
    last_order_id = request.session.get("last_order_id")
    if last_order_id:
        last_order = Order.objects.filter(pk=last_order_id, user=request.user).first()
        
    random_vouchers = list(Voucher.objects.filter(is_active=True).order_by('?')[:4])
    
    return render(
        request,
        "cart/detail.html",
        {
            "cart": cart,
            "shipping_fee": shipping_fee,
            "discount": discount,
            "grand_total": grand_total,
            "voucher": voucher,
            "voucher_code": _voucher_code_for_cart(request, cart) or "",
            "last_order": last_order,
            "SHIPPING_FEE_DEFAULT": SHIPPING_FEE_DEFAULT,
            "random_vouchers": random_vouchers,
        },
    )


@login_required
def add_to_cart(request, product_id: int):
    product = get_object_or_404(Product, pk=product_id)
    cart = _get_or_create_cart(request.user)

    size = (request.POST.get("size") or "").strip()
    try:
        quantity = int(request.POST.get("quantity") or 1)
    except ValueError:
        quantity = 1
    if quantity < 1:
        quantity = 1

    item, created = CartItem.objects.get_or_create(cart=cart, product=product, size=size)
    if created:
        item.quantity = quantity
    else:
        item.quantity += quantity
    item.save()

    messages.success(request, "Thêm vào giỏ hàng thành công !!!")
    referer = request.META.get("HTTP_REFERER") or ""
    if url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(referer)
    return redirect("catalog:product_detail", pk=product.id, slug=product.slug)


@login_required
def update_item(request, item_id: int):
    cart = _get_or_create_cart(request.user)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    try:
        quantity = int(request.POST.get("quantity") or item.quantity)
    except ValueError:
        quantity = item.quantity
    if quantity < 1:
        quantity = 1
    item.quantity = quantity
    size = request.POST.get("size")
    if size is not None:
        item.size = size.strip()
    item.save()
    messages.success(request, "Đã cập nhật giỏ hàng.")
    return redirect("cart:detail")


@login_required
def remove_item(request, item_id: int):
    cart = _get_or_create_cart(request.user)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()
    messages.success(request, "Đã xóa sản phẩm khỏi giỏ.")
    return redirect("cart:detail")


@login_required
def apply_voucher(request):
    code = (request.POST.get("code") or "").strip().upper()
    if not code:
        messages.error(request, "Vui lòng nhập mã voucher.")
        return redirect("cart:detail")

    cart = _get_or_create_cart(request.user)
    v = Voucher.objects.filter(code__iexact=code, is_active=True).first()
    if not v:
        messages.error(request, "Mã voucher không hợp lệ.")
        request.session.pop("voucher_code", None)
        cart.voucher_code = ""
        cart.save(update_fields=["voucher_code"])
        return redirect("cart:detail")

    if cart.total < v.min_order:
        messages.error(request, f"Đơn tối thiểu {v.min_order:,}đ để dùng voucher này.")
        request.session.pop("voucher_code", None)
        cart.voucher_code = ""
        cart.save(update_fields=["voucher_code"])
        return redirect("cart:detail")

    request.session["voucher_code"] = v.code
    cart.voucher_code = v.code
    cart.save(update_fields=["voucher_code"])
    messages.success(request, f"Áp dụng voucher {v.code} thành công.")
    return redirect("cart:detail")


@login_required
def remove_voucher(request):
    request.session.pop("voucher_code", None)
    cart = _get_or_create_cart(request.user)
    cart.voucher_code = ""
    cart.save(update_fields=["voucher_code"])
    messages.success(request, "Đã xóa voucher.")
    return redirect("cart:detail")


@login_required
def checkout(request):
    cart = _get_or_create_cart(request.user)
    cart = Cart.objects.prefetch_related("items__product__images").get(pk=cart.pk)
    if not cart.items.exists():
        messages.error(request, "Giỏ hàng đang trống.")
        return redirect("cart:detail")

    voucher = _get_voucher(request, cart)
    shipping_fee, discount, grand_total = _calc_totals(cart.total, voucher)

    if request.method == "POST":
        cart.full_name = (request.POST.get("full_name") or "").strip()
        cart.phone = (request.POST.get("phone") or "").strip()
        cart.province = (request.POST.get("province") or "").strip()
        cart.district = (request.POST.get("district") or "").strip()
        cart.ward = (request.POST.get("ward") or "").strip()
        cart.address = (request.POST.get("address") or "").strip()
        note = (request.POST.get("note") or "").strip()
        payment_method = (request.POST.get("payment_method") or Order.PaymentMethod.COD).strip()
        cart.save()

        if not cart.full_name or not cart.phone or not cart.address:
            messages.error(request, "Vui lòng nhập đầy đủ Họ tên / SĐT / Địa chỉ.")
            return redirect("cart:checkout")
        if not cart.province or not cart.district or not cart.ward:
            messages.error(request, "Vui lòng chọn/nhập Tỉnh, Quận/Huyện và Phường/Xã.")
            return redirect("cart:checkout")

        phone_digits = "".join(ch for ch in cart.phone if ch.isdigit())
        if len(phone_digits) < 9:
            messages.error(request, "Số điện thoại không hợp lệ.")
            return redirect("cart:checkout")

        order = Order.objects.create(
            user=request.user,
            full_name=cart.full_name,
            phone=cart.phone,
            province=cart.province,
            district=cart.district,
            ward=cart.ward,
            address=cart.address,
            payment_method=payment_method,
            is_paid=False,
            status=Order.Status.PLACED,
            total=grand_total,
            note=note,
        )
        for it in cart.items.select_related("product"):
            OrderItem.objects.create(
                order=order,
                product=it.product,
                quantity=it.quantity,
                size=it.size,
                price=it.product.price,
            )
        send_order_confirmation(order)
        cart.items.all().delete()
        request.session.pop("voucher_code", None)
        cart.voucher_code = ""
        cart.save(update_fields=["voucher_code"])
        request.session["last_order_id"] = order.id
        if payment_method == Order.PaymentMethod.COD:
            messages.success(request, f"Đặt hàng COD thành công. Mã đơn #{order.id}.")
            return redirect("orders:success", order_id=order.id)

        if payment_method == Order.PaymentMethod.VNPAY:
            return redirect("orders:vnpay_start", order_id=order.id)
        if payment_method == Order.PaymentMethod.MOMO:
            return redirect("orders:momo_start", order_id=order.id)

        messages.success(request, "Đặt hàng thành công.")
        return redirect("orders:success", order_id=order.id)

    return render(
        request,
        "cart/checkout.html",
        {"cart": cart, "shipping_fee": shipping_fee, "discount": discount, "grand_total": grand_total, "voucher": voucher},
    )
