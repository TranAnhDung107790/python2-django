from django.conf import settings
from django.core.mail import send_mail


def send_order_confirmation(order):
    email = order.user.email or order.user.username
    subject = f"AD Sneaker - Xác nhận đơn hàng #{order.id}"
    addr_parts = [p for p in (order.address, order.ward, order.district, order.province) if p]
    addr_line = ", ".join(addr_parts) if addr_parts else order.address
    lines = [
        f"Xin chào {order.full_name or order.user.username},",
        f"Đơn hàng #{order.id} đã được tạo thành công.",
        f"Tổng tiền: {order.total} đ",
        f"Phương thức: {order.payment_method}",
        f"Trạng thái: {order.status}",
        f"Giao hàng: {addr_line}",
        f"SĐT: {order.phone}",
    ]
    send_mail(
        subject,
        "\n".join(lines),
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=True,
    )
