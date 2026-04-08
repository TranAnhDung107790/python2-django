from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="detail"),
    path("add/<int:product_id>/", views.add_to_cart, name="add"),
    path("update/<int:item_id>/", views.update_item, name="update_item"),
    path("remove/<int:item_id>/", views.remove_item, name="remove_item"),
    path("voucher/apply/", views.apply_voucher, name="apply_voucher"),
    path("voucher/remove/", views.remove_voucher, name="remove_voucher"),
    path("checkout/", views.checkout, name="checkout"),
]

