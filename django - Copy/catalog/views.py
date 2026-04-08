import html
import random

from django.contrib import messages
from django.utils.html import strip_tags
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .models import Product, WishlistItem

_INFO_TEMPLATES: dict[str, str] = {
    "gioi-thieu": "pages/gioi-thieu.html",
    "chinh-sach-thanh-toan": "pages/chinh-sach-thanh-toan.html",
    "chinh-sach-van-chuyen": "pages/chinh-sach-van-chuyen.html",
    "chinh-sach-doi-tra": "pages/chinh-sach-doi-tra.html",
    "chinh-sach-bao-hanh": "pages/chinh-sach-bao-hanh.html",
}


def site_page(request, slug: str):
    tpl = _INFO_TEMPLATES.get(slug)
    if not tpl:
        raise Http404()
    return render(request, tpl)


def _filter_products_by_search(qs, q: str):
    q = (q or "").strip()
    if not q:
        return qs
    words = [w.strip() for w in q.replace(",", " ").split() if w.strip()]
    if not words:
        return qs
    for w in words:
        qs = qs.filter(Q(name__icontains=w) | Q(slug__icontains=w))
    return qs


def _category_slug_to_type(category_slug: str | None):
    if category_slug in (None, "", "all"):
        return None
    if category_slug == "giay-nam":
        return 1
    if category_slug == "giay-nu":
        return 2
    if category_slug == "giay-tre-em":
        return 3
    return None


def home(request):
    q = (request.GET.get("q") or "").strip()
    qs = Product.objects.all()
    qs = _filter_products_by_search(qs, q)
    qs = qs.order_by("-created_at")

    featured_men = Product.objects.filter(type=1).order_by("-created_at")[:8]
    featured_women = Product.objects.filter(type=2).order_by("-created_at")[:8]
    featured_kids = Product.objects.filter(type=3).order_by("-created_at")[:8]
    new_drops = Product.objects.order_by("-created_at")[:8]
    editor_picks = Product.objects.order_by("-created_at")[:4]

    wishlist_ids = set()
    if request.user.is_authenticated:
        wishlist_ids = set(
            WishlistItem.objects.filter(user=request.user).values_list("product_id", flat=True),
        )

    return render(
        request,
        "catalog/home.html",
        {
            "products": qs,
            "q": q,
            "wishlist_ids": wishlist_ids,
            "featured_men": featured_men,
            "featured_women": featured_women,
            "featured_kids": featured_kids,
            "new_drops": new_drops,
            "editor_picks": editor_picks,
        },
    )


def category(request, category_slug: str | None = None):
    q = (request.GET.get("q") or "").strip()
    sort = (request.GET.get("sort") or "newest").strip()  # asc|desc|newest
    price_range = request.GET.get("price")
    page = int(request.GET.get("page") or 1)

    type_id = _category_slug_to_type(category_slug)
    qs = Product.objects.all()
    if type_id is not None:
        qs = qs.filter(type=type_id)
    qs = _filter_products_by_search(qs, q)

    # Filter by price
    if price_range == "under_1m":
        qs = qs.filter(price__lt=1000000)
    elif price_range == "1m_to_2m":
        qs = qs.filter(price__gte=1000000, price__lte=2000000)
    elif price_range == "above_2m":
        qs = qs.filter(price__gt=2000000)

    # Sort
    if sort == "asc":
        qs = qs.order_by("price", "-created_at")
    elif sort == "desc":
        qs = qs.order_by("-price", "-created_at")
    else:
        qs = qs.order_by("-created_at")

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(page)

    wishlist_ids = set()
    if request.user.is_authenticated:
        wishlist_ids = set(
            WishlistItem.objects.filter(user=request.user).values_list("product_id", flat=True),
        )

    return render(
        request,
        "catalog/category.html",
        {
            "category_slug": category_slug or "",
            "type_id": type_id,
            "q": q,
            "sort": sort,
            "price_range": price_range,
            "page_obj": page_obj,
            "wishlist_ids": wishlist_ids,
        },
    )


def product_detail(request, pk: int, slug: str):
    # slug chỉ để SEO/đẹp URL; dữ liệu import có thể chứa ký tự không hợp lệ.
    # Lấy theo pk để luôn hoạt động.
    product = get_object_or_404(Product, pk=pk)

    similar_qs = Product.objects.filter(type=product.type).exclude(id=product.id).order_by("-created_at")[:8]

    is_wishlisted = False
    if request.user.is_authenticated:
        is_wishlisted = WishlistItem.objects.filter(user=request.user, product=product).exists()

    desc_html = html.unescape(product.description or "")
    desc_plain = strip_tags(desc_html).strip()

    # Tạo 3 đánh giá giả lập ngẫu nhiên cho mỗi sản phẩm mỗi khi refresh
    vietnamese_names = [
        "Trần Hữu Nam", "Lê Hương Trà", "Phạm Quốc Bảo", 
        "Nguyễn Thu Trang", "Đặng Minh Tâm", "Vũ Hoàng Long", 
        "Hoàng Thanh Nga", "Đinh Gia Hân", "Bùi Đức Anh"
    ]
    reviews_content = [
        "Sản phẩm quá tuyệt vời so với giá tiền. Đi rất êm chân nha mọi người.",
        "Thiết kế đẹp, đóng gói rất cẩn thận, hộp không bị móp. Shipper thân thiện.",
        "Màu sắc bên ngoài y hệt như hình trên web, mình canh sale nên mua được giá hời.",
        "Form giày hơi ôm nên bạn nào chân bè nhớ tăng thêm 1 size nhé, nhưng đi rất sướng.",
        "Tuyệt phẩm! Bạn gái mình rất thích đôi này, sẽ tiếp tục ủng hộ shop lâu dài.",
        "Ship hỏa tốc cực nhanh, mới đặt tối qua mà sáng nay đã có giày đi chơi rồi."
    ]
    
    random_reviewers = random.sample(vietnamese_names, 3)
    random_comments = random.sample(reviews_content, 3)
    
    mock_reviews = [
        {
            "name": random_reviewers[0], 
            "content": random_comments[0], 
            "stars": 5, 
            "avatar_color": "1fa24f",
            "date": "2 ngày trước"
        },
        {
            "name": random_reviewers[1], 
            "content": random_comments[1], 
            "stars": 5, 
            "avatar_color": "d63384",
            "date": "1 tuần trước"
        },
        {
            "name": random_reviewers[2], 
            "content": random_comments[2], 
            "stars": 4, 
            "avatar_color": "0d6efd",
            "date": "2 tuần trước"
        }
    ]

    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "similar_products": similar_qs,     
            "is_wishlisted": is_wishlisted,     
            "product_description_html": desc_html,
            "product_description_plain": desc_plain,
            "mock_reviews": mock_reviews,
        },
    )

@login_required
def wishlist(request):
    items = WishlistItem.objects.filter(user=request.user).select_related("product").order_by("-created_at")
    return render(request, "catalog/wishlist.html", {"items": items})


@login_required
def wishlist_toggle(request, product_id: int):
    product = get_object_or_404(Product, pk=product_id)
    existing = WishlistItem.objects.filter(user=request.user, product=product)
    if existing.exists():
        existing.delete()
        messages.success(request, "Đã xóa khỏi yêu thích.")
    else:
        WishlistItem.objects.create(user=request.user, product=product)
        messages.success(request, "Đã thêm vào yêu thích.")
    return redirect(request.META.get("HTTP_REFERER") or "catalog:home")
