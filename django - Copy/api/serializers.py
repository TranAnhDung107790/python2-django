from django.contrib.auth.models import User
from rest_framework import serializers

from cart.models import Cart, CartItem
from catalog.models import Product, ProductImage
from orders.models import Order, OrderItem


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "password"]

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
        )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "is_staff", "is_superuser"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image"]


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "description", "price", "type", "images", "created_at"]


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True, required=False)
    subtotal = serializers.IntegerField(read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_id", "quantity", "size", "subtotal"]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "full_name", "phone", "address", "updated_at", "items", "total"]


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "quantity", "size", "price", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "full_name",
            "phone",
            "province",
            "district",
            "ward",
            "address",
            "payment_method",
            "is_paid",
            "status",
            "total",
            "note",
            "created_at",
            "items",
        ]
