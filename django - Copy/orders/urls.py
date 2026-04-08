from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("success/<int:order_id>/", views.success, name="success"),
    path("track/<int:order_id>/", views.track, name="track"),
    path("cancel/<int:order_id>/", views.order_cancel, name="order_cancel"),
    path("my/", views.my_orders, name="my_orders"),
    path("vnpay/start/<int:order_id>/", views.vnpay_start, name="vnpay_start"),
    path("vnpay/return/", views.vnpay_return, name="vnpay_return"),
    path("momo/start/<int:order_id>/", views.momo_start, name="momo_start"),
    path("momo/return/", views.momo_return, name="momo_return"),
]

