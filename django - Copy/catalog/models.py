from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Product(models.Model):
    TYPE_CHOICES = [
        (0, "Khác"),
        (1, "Giày Nam"),
        (2, "Giày Nữ"),
        (3, "Giày Trẻ Em"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.PositiveIntegerField(default=0)
    type = models.IntegerField(choices=TYPE_CHOICES, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="products/")

    def __str__(self) -> str:
        return f"{self.product_id}: {self.image.name}"


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="wishlist_items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="wishlisted_by", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")

    def __str__(self) -> str:
        return f"{self.user_id} ❤️ {self.product_id}"
