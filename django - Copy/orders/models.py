from django.conf import settings
from django.db import models

from catalog.models import Product


class Order(models.Model):
    class Status(models.TextChoices):
        PLACED = "PLACED", "Đã đặt"
        CONFIRMED = "CONFIRMED", "Đã xác nhận"
        SHIPPED = "SHIPPED", "Đang giao"
        DONE = "DONE", "Hoàn tất"
        CANCELED = "CANCELED", "Đã hủy"

    class PaymentMethod(models.TextChoices):
        COD = "COD", "Thanh toán khi nhận hàng"
        VNPAY = "VNPAY", "VNPAY"
        MOMO = "MOMO", "Momo"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)
    province = models.CharField(max_length=120, blank=True)
    district = models.CharField(max_length=120, blank=True)
    ward = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=500)

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    is_paid = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLACED)
    total = models.PositiveIntegerField(default=0)
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Order({self.id}) {self.user_id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=10, blank=True)
    price = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.order_id} - {self.product_id}"

    @property
    def subtotal(self) -> int:
        return int(self.price) * int(self.quantity)
