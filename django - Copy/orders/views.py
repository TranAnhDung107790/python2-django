import base64
import os
import hmac
import hashlib
import json
from datetime import datetime, timedelta
from urllib import request as urllib_request

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .payment import build_vnpay_url, get_vnpay_cfg

from .models import Order
from cart.models import Cart, CartItem


def _get_tracking_context(order: Order) -> dict:
    """Generate tracking context for order tracking page."""
    status_map = {
        Order.Status.PLACED: {
            "title": "Đơn hàng đã được đặt",
            "description": "Xin cảm ơn, đơn hàng của bạn đã được ghi nhận.",
            "icon": "fa-solid fa-list",
            "state": "active",
        },
        Order.Status.CONFIRMED: {
            "title": "Đơn hàng được xác nhận",
            "description": "Đơn hàng của bạn đã được xác nhận và sẽ sớm được chuẩn bị.",
            "icon": "fa-solid fa-clipboard-check",
            "state": "active",
        },
        Order.Status.SHIPPED: {
            "title": "Đơn hàng đang được giao",
            "description": "Đơn hàng của bạn đang trên đường đến tay bạn.",
            "icon": "fa-solid fa-truck",
            "state": "active",
        },
        Order.Status.DONE: {
            "title": "Đơn hàng đã hoàn tất",
            "description": "Cảm ơn bạn đã mua hàng tại AD Sneaker.",
            "icon": "fa-solid fa-circle-check",
            "state": "completed",
        },
        Order.Status.CANCELED: {
            "title": "Đơn hàng đã bị hủy",
            "description": "Đơn hàng của bạn đã bị hủy.",
            "icon": "fa-solid fa-times-circle",
            "state": "pending",
        },
    }

    steps_timeline = [
        {
            "title": "Đã đặt",
            "description": "Đơn hàng được tạo",
            "icon": "fa-solid fa-bag-shopping",
            "state": "completed",
        },
        {
            "title": "Xác nhận",
            "description": "Shop xác nhận đơn hàng",
            "icon": "fa-solid fa-clipboard-check",
            "state": "completed" if order.status in [Order.Status.CONFIRMED, Order.Status.SHIPPED, Order.Status.DONE] else ("active" if order.status == Order.Status.PLACED else "pending"),
        },
        {
            "title": "Giao hàng",
            "description": "Bắt đầu giao hàng",
            "icon": "fa-solid fa-truck",
            "state": "completed" if order.status in [Order.Status.SHIPPED, Order.Status.DONE] else ("active" if order.status == Order.Status.CONFIRMED else "pending"),
        },
        {
            "title": "Hoàn tất",
            "description": "Bạn nhận được hàng",
            "icon": "fa-solid fa-circle-check",
            "state": "completed" if order.status == Order.Status.DONE else ("active" if order.status == Order.Status.SHIPPED else "pending"),
        },
    ]

    current_status_obj = status_map.get(order.status, status_map[Order.Status.PLACED])
    current_step_idx = {
        Order.Status.PLACED: 0,
        Order.Status.CONFIRMED: 1,
        Order.Status.SHIPPED: 2,
        Order.Status.DONE: 3,
        Order.Status.CANCELED: -1,
    }.get(order.status, 0)

    progress_percent = 0
    if order.status == Order.Status.PLACED:
        progress_percent = 25
    elif order.status == Order.Status.CONFIRMED:
        progress_percent = 50
    elif order.status == Order.Status.SHIPPED:
        progress_percent = 75
    elif order.status == Order.Status.DONE:
        progress_percent = 100
    elif order.status == Order.Status.CANCELED:
        progress_percent = 0

    return {
        "payment_status": "Đã thanh toán" if order.is_paid else "Chờ thanh toán",
        "current_status": order.get_status_display(),
        "current_step": current_status_obj if current_step_idx >= 0 else None,
        "next_step": None,  # Could be enhanced
        "steps": steps_timeline,
        "progress_percent": progress_percent,
        "is_canceled": order.status == Order.Status.CANCELED,
    }


def _momo_order_id_for_api(order: Order) -> str:
    """MoMo từ chối nếu tái sử dụng cùng orderId; mỗi lần tạo link phải unique."""
    ms = int(datetime.now().timestamp() * 1000)
    return f"{order.id}M{ms}"


def _django_order_pk_from_momo_order_id(momo_order_id: str) -> int:
    s = (momo_order_id or "").strip()
    if not s:
        raise ValueError("empty orderId")
    if "M" in s:
        head = s.split("M", 1)[0]
        if head.isdigit():
            return int(head)
    return int(s)


@login_required
def success(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(request, "orders/success.html", {"order": order})


@login_required
def track(request, order_id: int):
    """Display order tracking page."""
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    tracking = _get_tracking_context(order)
    return render(request, "orders/track.html", {"order": order, "tracking": tracking})


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "orders/my_orders.html", {"orders": orders})


@login_required
def vnpay_start(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    cfg = get_vnpay_cfg()
    if not cfg:
        messages.error(request, "Chưa cấu hình VNPAY (.env).")
        return redirect("orders:success", order_id=order.id)

    # VNPAY amount is in VND * 100
    amount = int(order.total) * 100
    now = datetime.now()
    expire = now + timedelta(minutes=15)
    params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": cfg.tmn_code,
        "vnp_Amount": amount,
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": str(order.id),
        "vnp_OrderInfo": f"ORDER_{order.id}",
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": cfg.return_url,
        "vnp_IpAddr": request.META.get("REMOTE_ADDR", "127.0.0.1"),
        "vnp_CreateDate": now.strftime("%Y%m%d%H%M%S"),
        "vnp_ExpireDate": expire.strftime("%Y%m%d%H%M%S"),
    }
    url = build_vnpay_url(cfg=cfg, params=params)
    return redirect(url)


@login_required
def vnpay_return(request):
    # Minimal “runs and correct” flow: if ResponseCode == 00 mark paid
    code = request.GET.get("vnp_ResponseCode")
    txn_ref = request.GET.get("vnp_TxnRef")
    if not txn_ref:
        messages.error(request, "Thiếu mã đơn hàng.")
        return redirect("orders:my_orders")

    order = get_object_or_404(Order, pk=int(txn_ref), user=request.user)
    if code == "00":
        order.is_paid = True
        order.payment_method = Order.PaymentMethod.VNPAY
        order.save(update_fields=["is_paid", "payment_method"])
        messages.success(request, "Thanh toán VNPAY thành công.")
    else:
        messages.error(request, "Thanh toán VNPAY thất bại / bị hủy.")
    return redirect("orders:success", order_id=order.id)


@login_required
def momo_start(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    partner = os.getenv("MOMO_PARTNER_CODE", "MOMO").strip()
    access = os.getenv("MOMO_ACCESS_KEY", "F8BBA842ECF85").strip()
    secret = os.getenv("MOMO_SECRET_KEY", "K951B6PE1waDMi640xX08PD3vg6EkVlz").strip()
    endpoint = os.getenv("MOMO_ENDPOINT", "https://test-payment.momo.vn/v2/gateway/api/create").strip()
    request_id = f"{partner}{order.id}{int(datetime.now().timestamp())}"
    order_id_str = _momo_order_id_for_api(order)
    return_url = request.build_absolute_uri(reverse("orders:momo_return"))
    notify_url = return_url
    amount = str(int(order.total))
    order_info = f"ORDER_{order.id}"
    extra_data = ""
    request_type = "captureWallet"
    raw = (
        f"accessKey={access}&amount={amount}&extraData={extra_data}&ipnUrl={notify_url}"
        f"&orderId={order_id_str}&orderInfo={order_info}&partnerCode={partner}"
        f"&redirectUrl={return_url}&requestId={request_id}&requestType={request_type}"
    )
    signature = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    body = {
        "partnerCode": partner,
        "accessKey": access,
        "requestId": request_id,
        "amount": amount,
        "orderId": order_id_str,
        "orderInfo": order_info,
        "redirectUrl": return_url,
        "ipnUrl": notify_url,
        "lang": "vi",
        "extraData": extra_data,
        "requestType": request_type,
        "signature": signature,
    }
    try:
        req = urllib_request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("resultCode") not in (0, "0"):
            messages.error(request, payload.get("message") or "Không tạo được thanh toán MOMO.")
            return redirect("orders:success", order_id=order.id)
        qr_url = (payload.get("qrCodeUrl") or payload.get("qrCodeURL") or "").strip()
        qr_data_uri = ""
        if qr_url:
            try:
                rimg = urllib_request.Request(
                    qr_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101"},
                )
                with urllib_request.urlopen(rimg, timeout=20) as r:
                    raw = r.read()
                    ct = (r.headers.get("Content-Type") or "image/png").split(";")[0].strip() or "image/png"
                if raw:
                    qr_data_uri = f"data:{ct};base64,{base64.b64encode(raw).decode('ascii')}"
            except Exception:
                qr_data_uri = ""
        return render(
            request,
            "orders/momo_pay.html",
            {
                "order": order,
                "pay_url": payload.get("payUrl") or "",
                "embedded_pay_url": payload.get("payUrl") or "",
                "deeplink": payload.get("deeplink") or "",
                "qr_code_url": qr_url,
                "qr_data_uri": qr_data_uri,
                "request_id": payload.get("requestId") or request_id,
                "trans_id": payload.get("transId") or "",
            },
        )
    except Exception as exc:
        print(f"MOMO error: {exc}")
        messages.error(request, "MOMO demo tạm thời lỗi, vui lòng thử lại.")
        return redirect("orders:success", order_id=order.id)


@login_required
def momo_return(request):
    order_id_raw = request.GET.get("orderId")
    result_code = str(request.GET.get("resultCode") or "")
    if not order_id_raw:
        messages.error(request, "Thiếu mã đơn hàng từ MOMO.")
        return redirect("orders:my_orders")

    try:
        order_pk = _django_order_pk_from_momo_order_id(order_id_raw)
    except (ValueError, TypeError):
        messages.error(request, "Mã đơn MOMO không hợp lệ.")
        return redirect("orders:my_orders")

    order = get_object_or_404(Order, pk=order_pk, user=request.user)
    if result_code == "0":
        order.is_paid = True
        order.payment_method = Order.PaymentMethod.MOMO
        order.save(update_fields=["is_paid", "payment_method"])
        messages.success(request, "Thanh toán MOMO thành công.")
    else:
        messages.error(request, "Thanh toán MOMO thất bại hoặc bị hủy.")
    return redirect("orders:success", order_id=order.id)


@login_required
def order_cancel(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if request.method != "POST":
        return redirect("orders:success", order_id=order.id)
    if order.status == Order.Status.CANCELED:
        messages.info(request, "Đơn hàng đã được hủy trước đó.")
        return redirect("cart:detail")
    elif order.is_paid:
        messages.error(request, "Đơn đã thanh toán — vui lòng liên hệ shop để xử lý.")
        return redirect("orders:my_orders")
    elif order.status in (Order.Status.PLACED, Order.Status.CONFIRMED):
        order.status = Order.Status.CANCELED
        order.save(update_fields=["status"])
        
        # Restore items back to cart
        cart, _ = Cart.objects.get_or_create(user=request.user)
        for target_item in order.items.all():
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=target_item.product,
                size=target_item.size,
                defaults={"quantity": target_item.quantity}
            )
            if not created:
                cart_item.quantity += target_item.quantity
                cart_item.save()

        messages.success(request, "Đã hủy đơn hàng! Các sản phẩm đã được tự động thêm lại vào giỏ hàng.")
        return redirect("cart:detail")
    else:
        messages.error(request, "Không thể hủy đơn ở trạng thái hiện tại.")
        return redirect("cart:detail")
