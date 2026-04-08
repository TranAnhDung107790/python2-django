import secrets
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
import jwt
from pymongo import MongoClient

from accounts.models import PasswordResetToken
from cart.models import Cart, CartItem, Voucher
from catalog.models import Product
from chatbot.views import ask_chatbot
from orders.models import Order, OrderItem
from orders.views import momo_start, vnpay_start
from orders.notifier import send_order_confirmation

from .serializers import CartSerializer, OrderSerializer, ProductSerializer, RegisterSerializer, UserSerializer


def _mongo_db():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/shoe").strip()
    if not mongo_uri:
        return None
    try:
        return MongoClient(mongo_uri, serverSelectionTimeoutMS=1500).get_default_database()
    except Exception:
        return None


def _legacy_image_url(raw, request):
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return request.build_absolute_uri(f"/media/products/{raw}")


def _mongo_product_to_legacy(doc, request) -> dict:
    imgs = [_legacy_image_url(img, request) for img in (doc.get("img") or []) if img]
    if not imgs:
        imgs = [""]
    return {
        "_id": str(doc.get("_id")),
        "id": str(doc.get("_id")),
        "name": doc.get("name") or "",
        "slug": doc.get("slug") or "",
        "price": int(doc.get("price") or 0),
        "description": doc.get("description") or "",
        "type": int(doc.get("type") or 0),
        "img": imgs,
    }


def _mongo_legacy_products(request, *, query=None, product_id=None, similar_name=None):
    db = _mongo_db()
    if not db:
        return None

    collection = db.get_collection("products")
    if product_id is not None:
        docs = list(collection.find({"_id": product_id}))
        if not docs:
            docs = list(collection.find({"id": product_id}))
        if not docs:
            try:
                from bson import ObjectId

                docs = list(collection.find({"_id": ObjectId(str(product_id))}))
            except Exception:
                docs = []
        return [_mongo_product_to_legacy(doc, request) for doc in docs]

    criteria = {}
    if query:
        criteria["name"] = {"$regex": query, "$options": "i"}
    elif similar_name:
        criteria["name"] = {"$regex": similar_name[:80], "$options": "i"}

    docs = list(collection.find(criteria).limit(64))
    return [_mongo_product_to_legacy(doc, request) for doc in docs]


def _should_use_mongo_products():
    if os.getenv("REACT_USE_MONGO_PRODUCTS", "1").strip() == "1":
        return True
    return not Product.objects.exists()


def _order_to_legacy(order: Order, request) -> dict:
    products = []
    for item in order.items.select_related("product").prefetch_related("product__images"):
        first = item.product.images.first()
        img0 = request.build_absolute_uri(first.image.url) if first else ""
        products.append(
            {
                "_id": str(item.id),
                "nameProduct": item.product.name,
                "price": item.price,
                "quantity": item.quantity,
                "size": item.size or "39",
                "img": img0,
                "type": item.product.type,
            }
        )
    return {
        "_id": str(order.id),
        "id": order.id,
        "user": order.user.email or order.user.username,
        "username": order.full_name,
        "phone": order.phone,
        "address": order.address,
        "sumprice": order.total,
        "trangthai": order.is_paid,
        "tinhtrang": order.status == Order.Status.DONE,
        "products": products,
    }


class RegisterApiView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


def _issue_tokens(user: User):
    now = timezone.now()
    access_payload = {"sub": user.id, "username": user.username, "type": "access", "exp": now + timedelta(hours=2)}
    refresh_payload = {"sub": user.id, "username": user.username, "type": "refresh", "exp": now + timedelta(days=7)}
    access = jwt.encode(access_payload, settings.SECRET_KEY, algorithm="HS256")
    refresh = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm="HS256")
    return access, refresh


class LoginApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = (request.data.get("username") or request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({"message": "Invalid credentials"}, status=401)
        access, refresh = _issue_tokens(user)
        return Response({"access": access, "refresh": refresh, "user": UserSerializer(user).data})


class RefreshApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get("refresh", "")
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            if payload.get("type") != "refresh":
                return Response({"message": "Invalid token"}, status=400)
            user = User.objects.get(id=payload.get("sub"))
        except Exception:
            return Response({"message": "Invalid token"}, status=400)
        access, refresh = _issue_tokens(user)
        return Response({"access": access, "refresh": refresh})


class MeApiView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        old_password = request.data.get("old_password", "")
        new_password = request.data.get("new_password", "")
        user = request.user
        if not user.check_password(old_password):
            return Response({"message": "Mật khẩu cũ không đúng"}, status=400)
        if len(new_password) < 6:
            return Response({"message": "Mật khẩu mới phải >= 6 ký tự"}, status=400)
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"message": "Đổi mật khẩu thành công"})


class ForgotPasswordApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        user = User.objects.filter(Q(email=email) | Q(username=email)).first()
        if not user:
            return Response({"message": "Email không tồn tại"}, status=404)

        token = secrets.token_urlsafe(32)
        PasswordResetToken.objects.create(
            user=user,
            token=token,
            expires_at=PasswordResetToken.build_expiry(30),
        )
        reset_link = request.build_absolute_uri(reverse("api:auth_reset_password")) + f"?token={token}"
        send_mail(
            "AD Sneaker - Reset Password",
            f"Nhấn link để đặt lại mật khẩu (hết hạn 30 phút): {reset_link}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email or user.username],
            fail_silently=True,
        )
        return Response({"message": "Đã gửi email reset mật khẩu"})


class ResetPasswordApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get("token", "")
        new_password = request.data.get("new_password", "")
        prt = PasswordResetToken.objects.filter(token=token, is_used=False).first()
        if not prt or prt.expires_at < timezone.now():
            return Response({"message": "Token không hợp lệ hoặc đã hết hạn"}, status=400)
        if len(new_password) < 6:
            return Response({"message": "Mật khẩu mới phải >= 6 ký tự"}, status=400)
        user = prt.user
        user.set_password(new_password)
        user.save(update_fields=["password"])
        prt.is_used = True
        prt.save(update_fields=["is_used"])
        return Response({"message": "Đặt lại mật khẩu thành công"})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def products_api(request):
    q = (request.GET.get("q") or "").strip()
    type_id = request.GET.get("type")
    legacy = request.GET.get("legacy") in ("1", "true", "yes")
    if legacy and _should_use_mongo_products():
        data = _mongo_legacy_products(request, query=q) or []
        if type_id not in (None, ""):
            data = [item for item in data if int(item.get("type") or 0) == int(type_id)]
        return Response(data)
    qs = Product.objects.all().order_by("-created_at")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(slug__icontains=q))
    if type_id not in (None, ""):
        qs = qs.filter(type=int(type_id))
    if legacy:
        qs = qs.prefetch_related("images")
        return Response([_product_to_legacy(p, request) for p in qs])
    return Response(ProductSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def product_detail_api(request, pk):
    if _should_use_mongo_products() and not Product.objects.filter(pk=pk).exists():
        data = _mongo_legacy_products(request, product_id=pk) or []
        if data:
            return Response(data[0])
    product = Product.objects.filter(pk=pk).first()
    if not product:
        return Response({"message": "Not found"}, status=404)
    return Response(ProductSerializer(product).data)


def _get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _product_to_legacy(p: Product, request) -> dict:
    imgs = []
    for im in p.images.all():
        imgs.append(request.build_absolute_uri(im.image.url))
    if not imgs:
        imgs = [""]
    return {
        "_id": str(p.id),
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "price": p.price,
        "description": p.description,
        "type": p.type,
        "img": imgs,
    }


def _cart_legacy_bundle(request):
    cart = _get_cart(request.user)
    items = list(cart.items.select_related("product").prefetch_related("product__images"))
    code = (cart.voucher_code or "").strip()
    v = None
    if code:
        v = Voucher.objects.filter(code__iexact=code, is_active=True).first()
        if v and cart.total < v.min_order:
            v = None
    shipping_fee = 0 if (v and v.free_ship) else 50000
    discount = v.discount if (v and not v.free_ship) else 0
    grand_total = max(0, cart.total - discount + shipping_fee)
    if not items:
        return []
    products = []
    for item in items:
        p = item.product
        first = p.images.first()
        img0 = request.build_absolute_uri(first.image.url) if first else ""
        products.append(
            {
                "_id": str(item.id),
                "nameProduct": p.name,
                "price": p.price,
                "quantity": item.quantity,
                "size": item.size or "39",
                "img": img0,
                "type": p.type,
            }
        )
    row = {
        "sumprice": cart.total,
        "products": products,
        "shipping_fee": shipping_fee,
        "discount": discount,
        "grand_total": grand_total,
    }
    if v:
        row["voucher"] = {"code": v.code, "discount": v.discount, "free_ship": v.free_ship, "min_order": v.min_order}
    else:
        row["voucher"] = None
    return [row]


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def cart_api(request):
    if request.GET.get("legacy") in ("1", "true", "yes"):
        if not request.user.is_authenticated:
            return Response([])
        return Response(_cart_legacy_bundle(request))
    if not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=401)
    return Response(CartSerializer(_get_cart(request.user)).data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def cart_add_api(request):
    cart = _get_cart(request.user)
    product_id = int(request.data.get("product_id"))
    quantity = max(1, int(request.data.get("quantity", 1)))
    size = str(request.data.get("size", "")).strip()
    product = Product.objects.get(pk=product_id)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, size=size)
    item.quantity = quantity if created else item.quantity + quantity
    item.save()
    return Response({"message": "Added", "item_id": item.id})


@api_view(["PUT"])
@permission_classes([permissions.IsAuthenticated])
def cart_update_api(request, item_id):
    cart = _get_cart(request.user)
    item = CartItem.objects.filter(cart=cart, id=item_id).first()
    if not item:
        return Response({"message": "Not found"}, status=404)
    if "quantity" in request.data:
        item.quantity = max(1, int(request.data.get("quantity", 1)))
    if "size" in request.data:
        item.size = str(request.data.get("size", "")).strip()
    item.save()
    return Response({"message": "Updated"})


@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def cart_delete_api(request, item_id):
    cart = _get_cart(request.user)
    item = CartItem.objects.filter(cart=cart, id=item_id).first()
    if not item:
        return Response({"message": "Not found"}, status=404)
    item.delete()
    return Response({"message": "Deleted"})


@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def cart_clear_api(request):
    cart = _get_cart(request.user)
    cart.items.all().delete()
    return Response({"message": "Cleared"})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def order_create_api(request):
    cart = _get_cart(request.user)
    if not cart.items.exists():
        return Response({"message": "Cart empty"}, status=400)
    payment_method = str(request.data.get("payment_method", Order.PaymentMethod.COD))
    vcode = (cart.voucher_code or "").strip()
    v = Voucher.objects.filter(code__iexact=vcode, is_active=True).first() if vcode else None
    if v and cart.total < v.min_order:
        v = None
    shipping_fee = 0 if (v and v.free_ship) else 50000
    discount = v.discount if (v and not v.free_ship) else 0
    grand_total = max(0, cart.total - discount + shipping_fee)
    order = Order.objects.create(
        user=request.user,
        full_name=str(request.data.get("full_name") or cart.full_name),
        phone=str(request.data.get("phone") or cart.phone),
        province=str(request.data.get("province") or cart.province or "")[:120],
        district=str(request.data.get("district") or cart.district or "")[:120],
        ward=str(request.data.get("ward") or cart.ward or "")[:120],
        address=str(request.data.get("address") or cart.address),
        payment_method=payment_method,
        is_paid=(payment_method != Order.PaymentMethod.COD),
        status=Order.Status.PLACED,
        total=grand_total,
        note=str(request.data.get("note", "")),
    )
    for ci in cart.items.select_related("product"):
        OrderItem.objects.create(
            order=order,
            product=ci.product,
            quantity=ci.quantity,
            size=ci.size,
            price=ci.product.price,
        )
    send_order_confirmation(order)
    cart.voucher_code = ""
    cart.save(update_fields=["voucher_code"])
    if payment_method == Order.PaymentMethod.COD:
        cart.items.all().delete()
    return Response({"message": "Order created", "order_id": order.id})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def order_list_api(request):
    qs = Order.objects.filter(user=request.user).order_by("-created_at")
    return Response(OrderSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def order_detail_api(request, order_id):
    order = Order.objects.filter(user=request.user, id=order_id).first()
    if not order:
        return Response({"message": "Not found"}, status=404)
    return Response(OrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def order_cancel_api(request, order_id):
    order = Order.objects.filter(user=request.user, id=order_id).first()
    if not order:
        return Response({"message": "Không tìm thấy đơn hàng"}, status=404)
    if order.status == Order.Status.CANCELED:
        return Response({"message": "Đơn hàng đã được hủy trước đó"})
    if order.is_paid:
        return Response({"message": "Đơn đã thanh toán, không thể xóa trực tiếp"}, status=400)
    if order.status not in (Order.Status.PLACED, Order.Status.CONFIRMED):
        return Response({"message": "Không thể hủy đơn ở trạng thái hiện tại"}, status=400)
    order.status = Order.Status.CANCELED
    order.save(update_fields=["status"])
    return Response({"message": "Đã hủy đơn hàng"})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def payment_cod_api(request):
    request.data["payment_method"] = Order.PaymentMethod.COD
    return order_create_api(request)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def payment_vnpay_api(request):
    response = order_create_api(request)
    if response.status_code >= 400:
        return response
    order_id = response.data["order_id"]
    # trả redirect URL
    redirect_response = vnpay_start(request, order_id)
    return Response({"order_id": order_id, "redirect_url": redirect_response.url})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def payment_momo_api(request):
    response = order_create_api(request)
    if response.status_code >= 400:
        return response
    order_id = response.data["order_id"]
    redirect_response = momo_start(request, order_id)
    return Response({"order_id": order_id, "redirect_url": getattr(redirect_response, "url", "")})


@api_view(["GET", "POST"])
@permission_classes([permissions.AllowAny])
def payment_vnpay_callback_api(request):
    code = request.GET.get("vnp_ResponseCode") or request.data.get("vnp_ResponseCode")
    txn_ref = request.GET.get("vnp_TxnRef") or request.data.get("vnp_TxnRef")
    if not txn_ref:
        return Response({"message": "Missing vnp_TxnRef"}, status=400)
    order = Order.objects.filter(id=int(txn_ref)).first()
    if not order:
        return Response({"message": "Order not found"}, status=404)
    if code == "00":
        order.is_paid = True
        order.status = Order.Status.CONFIRMED
        order.payment_method = Order.PaymentMethod.VNPAY
        order.save(update_fields=["is_paid", "status", "payment_method"])
        return Response({"message": "Payment success"})
    return Response({"message": "Payment failed"}, status=400)


@api_view(["GET", "POST"])
@permission_classes([permissions.AllowAny])
def payment_momo_callback_api(request):
    result_code = request.GET.get("resultCode") or request.data.get("resultCode")
    order_id = request.GET.get("orderId") or request.data.get("orderId")
    if not order_id:
        return Response({"message": "Missing orderId"}, status=400)
    oid = str(order_id).strip()
    if "M" in oid:
        head = oid.split("M", 1)[0]
        pk = int(head) if head.isdigit() else None
    else:
        try:
            pk = int(oid)
        except ValueError:
            pk = None
    if pk is None:
        return Response({"message": "Invalid orderId"}, status=400)
    order = Order.objects.filter(id=pk).first()
    if not order:
        return Response({"message": "Order not found"}, status=404)
    if str(result_code) == "0":
        order.is_paid = True
        order.status = Order.Status.CONFIRMED
        order.payment_method = Order.PaymentMethod.MOMO
        order.save(update_fields=["is_paid", "status", "payment_method"])
        return Response({"message": "Payment success"})
    return Response({"message": "Payment failed"}, status=400)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def chat_api(request):
    question = str(request.data.get("question") or "").strip()
    if not question:
        return Response({"message": "question is required"}, status=400)
    return Response({"answer": ask_chatbot(question)})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_api(request):
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def recommendations_api(request):
    qs = Product.objects.all().order_by("-created_at")[:8]
    return Response(ProductSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def product_query_legacy_api(request):
    pk = request.GET.get("id")
    if not pk:
        return Response([])
    if _should_use_mongo_products():
        data = _mongo_legacy_products(request, product_id=pk) or []
        if data:
            return Response(data)
    product = Product.objects.prefetch_related("images").filter(pk=pk).first()
    if not product:
        return Response([])
    return Response([_product_to_legacy(product, request)])


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def search_legacy_api(request):
    name = (request.GET.get("nameProduct") or "").strip()
    if len(name) < 1:
        return Response([])
    words = [w.strip() for w in name.replace(",", " ").split() if w.strip()]
    if not words:
        return Response([])
    if _should_use_mongo_products():
        data = _mongo_legacy_products(request, query=name) or []
        if not data:
            return Response(
                [{"name": "Không Tìm Thấy Sản Phẩm !!!", "img": [""], "price": 0, "_id": "", "slug": "", "type": 0}]
            )
        return Response(data[:16])
    qs = Product.objects.all()
    for w in words:
        qs = qs.filter(Q(name__icontains=w) | Q(slug__icontains=w))
    qs = qs.prefetch_related("images").order_by("-created_at")[:16]
    data = [_product_to_legacy(p, request) for p in qs]
    if not data:
        return Response(
            [{"name": "Không Tìm Thấy Sản Phẩm !!!", "img": [""], "price": 0, "_id": "", "slug": "", "type": 0}]
        )
    return Response(data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def similar_product_legacy_api(request):
    name = (request.GET.get("nameProduct") or "").strip()
    if not name or name == "undefined":
        return Response([])
    if _should_use_mongo_products():
        return Response((_mongo_legacy_products(request, similar_name=name) or [])[:8])
    qs = Product.objects.filter(name__icontains=name[:80]).prefetch_related("images").order_by("-created_at")[:8]
    return Response([_product_to_legacy(p, request) for p in qs])


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def react_login_api(request):
    username = (request.data.get("username") or request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""
    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({"message": "Email Hoặc Mật Khẩu Không Chính Xác !!!"}, status=401)
    access, refresh = _issue_tokens(user)
    resp = Response(
        {
            "message": "Đăng Nhập Thành Công !!!",
            "access": access,
            "refresh": refresh,
        }
    )
    resp.set_cookie("logged", "1", max_age=7 * 24 * 3600, samesite="Lax", httponly=False)
    return resp


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def react_register_api(request):
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""
    fullname = (request.data.get("fullname") or "").strip()
    if not email or not password:
        return Response({"message": "Vui Lòng Xem Lại Thông Tin !!!"}, status=400)
    if User.objects.filter(username=email).exists():
        return Response({"message": "Người Dùng Đã Tồn Tại !!!"}, status=403)
    User.objects.create_user(username=email, email=email, password=password, first_name=fullname)
    return Response({"message": "Đăng Ký Thành Công !!!"})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def react_me_api(request):
    u = request.user
    return Response(
        {
            "_id": str(u.id),
            "email": u.email or u.username,
            "fullname": u.first_name or "",
            "phone": "",
            "surplus": 0,
            "isAdmin": u.is_staff,
        }
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def react_logout_api(request):
    resp = Response({"message": "Đăng xuất thành công"})
    resp.delete_cookie("logged", path="/")
    return resp


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def react_update_info_cart_api(request):
    cart = _get_cart(request.user)
    cart.full_name = str(request.data.get("name") or request.data.get("full_name") or cart.full_name)[:255]
    cart.phone = str(request.data.get("phone") or cart.phone)[:30]
    cart.address = str(request.data.get("address") or cart.address)[:500]
    cart.province = str(request.data.get("province") or cart.province)[:120]
    cart.district = str(request.data.get("district") or cart.district)[:120]
    cart.ward = str(request.data.get("ward") or cart.ward)[:120]
    cart.save()
    return Response({"message": "Đã cập nhật thông tin giỏ hàng"})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def react_payments_api(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items__product__images")
        .order_by("-created_at")
    )
    return Response([_order_to_legacy(order, request) for order in orders])


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def react_payment_api(request):
    if request.method == "GET":
        order = (
            Order.objects.filter(user=request.user)
            .prefetch_related("items__product__images")
            .order_by("-created_at")
            .first()
        )
        return Response([_order_to_legacy(order, request)] if order else [])

    request.data["payment_method"] = Order.PaymentMethod.MOMO
    return payment_momo_api(request)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def react_payment_cod_api(request):
    request.data["payment_method"] = Order.PaymentMethod.COD
    return payment_cod_api(request)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def react_payment_vnpay_api(request):
    request.data["payment_method"] = Order.PaymentMethod.VNPAY
    response = payment_vnpay_api(request)
    if response.status_code >= 400:
        return response
    redirect_url = response.data.get("redirect_url") or ""
    payload = dict(response.data)
    payload["vnpayResponse"] = redirect_url
    return Response(payload)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def react_apply_voucher_api(request):
    code = (request.data.get("code") or "").strip().upper()
    if not code:
        return Response({"message": "Vui lòng nhập mã voucher"}, status=400)
    cart = _get_cart(request.user)
    v = Voucher.objects.filter(code__iexact=code, is_active=True).first()
    if not v:
        cart.voucher_code = ""
        cart.save(update_fields=["voucher_code"])
        return Response({"message": "Mã voucher không hợp lệ"}, status=400)
    if cart.total < v.min_order:
        cart.voucher_code = ""
        cart.save(update_fields=["voucher_code"])
        return Response({"message": f"Đơn tối thiểu {v.min_order:,}đ để dùng voucher này"}, status=400)
    cart.voucher_code = v.code
    cart.save(update_fields=["voucher_code"])
    return Response(
        {
            "message": f"Áp dụng voucher {v.code} thành công",
            "voucher": {
                "code": v.code,
                "discount": v.discount,
                "freeShip": v.free_ship,
                "free_ship": v.free_ship,
                "minOrder": v.min_order,
            },
        }
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def react_remove_voucher_api(request):
    cart = _get_cart(request.user)
    cart.voucher_code = ""
    cart.save(update_fields=["voucher_code"])
    return Response({"message": "Đã xóa voucher"})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def react_addtocart_api(request):
    cart = _get_cart(request.user)
    raw_id = request.data.get("product_id")
    product = None
    if raw_id not in (None, ""):
        try:
            product = Product.objects.filter(pk=int(str(raw_id).strip())).first()
        except (TypeError, ValueError):
            product = None
    if product is None:
        name = (request.data.get("nameProduct") or "").strip()
        product = Product.objects.filter(name__iexact=name).first() if name else None
    if product is None:
        name = (request.data.get("nameProduct") or "").strip()
        if name:
            slug = str(request.data.get("slug") or name).strip().lower().replace(" ", "-")[:255]
            product = Product.objects.create(
                name=name,
                slug=f"{slug}-{Product.objects.count() + 1}",
                description=str(request.data.get("description") or ""),
                price=int(request.data.get("priceProduct") or 0),
                type=int(request.data.get("type") or 0),
            )
    if not product:
        return Response({"message": "Không tìm thấy sản phẩm"}, status=400)
    quantity = max(1, int(request.data.get("quantityProduct") or request.data.get("quantity") or 1))
    size = str(request.data.get("size") or "").strip()
    item, created = CartItem.objects.get_or_create(cart=cart, product=product, size=size)
    item.quantity = quantity if created else item.quantity + quantity
    item.save()
    return Response({"message": "Thêm Vào Giỏ Hàng Thành Công !!!"})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def react_deletecart_api(request):
    cart = _get_cart(request.user)
    try:
        cid = int(request.data.get("id"))
    except (TypeError, ValueError):
        return Response({"message": "Sai id"}, status=400)
    item = CartItem.objects.filter(cart=cart, id=cid).first()
    if not item:
        return Response({"message": "Không tìm thấy"}, status=404)
    item.delete()
    return Response({"message": "Xóa Sản Phẩm Thành Công !!!"})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def react_update_product_api(request):
    cart = _get_cart(request.user)
    try:
        item_id = int(request.data.get("productId"))
    except (TypeError, ValueError):
        return Response({"message": "Sai productId"}, status=400)
    item = CartItem.objects.filter(cart=cart, id=item_id).first()
    if not item:
        return Response({"message": "Không tìm thấy"}, status=404)
    if "quantity" in request.data:
        item.quantity = max(1, int(request.data.get("quantity", 1)))
    if "size" in request.data:
        item.size = str(request.data.get("size", "")).strip()
    item.save()
    return Response({"message": "Cập Nhật Thành Công !!!"})
