from django.contrib import admin

from .models import Product, ProductImage, WishlistItem


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "type", "slug", "created_at")
    list_filter = ("type",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline]


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "created_at")
    search_fields = ("user__username", "user__email", "product__name", "product__slug")

# Register your models here.
