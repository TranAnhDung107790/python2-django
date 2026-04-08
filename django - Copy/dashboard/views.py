from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.shortcuts import render

from catalog.models import Product
from orders.models import Order


@staff_member_required
def dashboard_home(request):
    totals = Order.objects.aggregate(
        total_orders=Count("id"),
        total_revenue=Sum("total"),
    )
    recent_orders = Order.objects.select_related("user").order_by("-created_at")[:10]
    product_count = Product.objects.count()
    return render(
        request,
        "dashboard/home.html",
        {
            "totals": totals,
            "recent_orders": recent_orders,
            "product_count": product_count,
        },
    )
