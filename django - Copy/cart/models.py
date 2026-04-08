from django.conf import settings
from django.db import models

from catalog.models import Product


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    province = models.CharField("Tỉnh/Thành", max_length=120, blank=True)
    district = models.CharField("Quận/Huyện", max_length=120, blank=True)
    ward = models.CharField("Phường/Xã", max_length=120, blank=True)
    address = models.CharField("Địa chỉ (số nhà, đường)", max_length=500, blank=True)
    voucher_code = models.CharField(max_length=50, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Cart({self.user_id})"

    @property
    def total(self) -> int:
        return sum(i.subtotal for i in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=10, blank=True)

    class Meta:
        unique_together = ("cart", "product", "size")

    def __str__(self) -> str:
        return f"{self.product_id} x{self.quantity} ({self.size})"

    @property
    def subtotal(self) -> int:
        return int(self.product.price) * int(self.quantity)


class Voucher(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount = models.PositiveIntegerField(default=0)
    min_order = models.PositiveIntegerField(default=0)
    free_ship = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.code
