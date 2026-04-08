from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("trang/<slug:slug>/", views.site_page, name="site_page"),
    path("", views.home, name="home"),
    path("category/", views.category, name="category"),
    path("category/<slug:category_slug>/", views.category, name="category_slug"),
    # dùng <path:slug> để chấp nhận slug có dấu chấm/ký tự lạ từ dữ liệu import
    path("product/<int:pk>/<path:slug>/", views.product_detail, name="product_detail"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/toggle/<int:product_id>/", views.wishlist_toggle, name="wishlist_toggle"),
]

