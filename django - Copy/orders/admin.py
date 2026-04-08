from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total", "payment_method", "is_paid", "status", "created_at")
    list_filter = ("payment_method", "is_paid", "status")
    search_fields = ("id", "user__email", "user__username", "full_name", "phone")
    inlines = [OrderItemInline]

# Register your models here.
