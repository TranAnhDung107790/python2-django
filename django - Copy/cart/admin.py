from django.contrib import admin

from .models import Cart, CartItem, Voucher


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "full_name", "phone", "updated_at")
    search_fields = ("user__username", "user__email", "full_name", "phone")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "quantity", "size")
    search_fields = ("cart__user__username", "cart__user__email", "product__name")


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("code", "discount", "min_order", "free_ship", "is_active")
    list_filter = ("free_ship", "is_active")
    search_fields = ("code",)
