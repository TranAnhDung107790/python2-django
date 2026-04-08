from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from orders.models import Order


def register(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm_password") or ""
        full_name = (request.POST.get("full_name") or "").strip()

        if not email or not password:
            messages.error(request, "Vui lòng nhập email và mật khẩu.")
            return redirect("accounts:register")
            
        if password != confirm_password:
            messages.error(request, "Mật khẩu xác nhận không khớp.")
            return redirect("accounts:register")

        if User.objects.filter(username=email).exists():
            messages.error(request, "Người dùng đã tồn tại.")
            return redirect("accounts:register")

        user = User.objects.create_user(username=email, email=email, password=password, first_name=full_name)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, "Đăng ký thành công.")
        return redirect("catalog:home")

    return render(request, "accounts/register.html")


def login_view(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=email, password=password)
        if user is None:
            messages.error(request, "Email hoặc mật khẩu không chính xác.")
            return redirect("accounts:login")
        login(request, user)
        
        remember_me = request.POST.get("remember_me")
        if remember_me:
            request.session.set_expiry(1209600)  # Ghi nhớ trong 2 tuần (14 ngày)
        else:
            request.session.set_expiry(0)  # Đóng trình duyệt sẽ đăng xuất
            
        messages.success(request, "Đăng nhập thành công.")
        return redirect("catalog:home")

    return render(request, "accounts/login.html")


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "Đã đăng xuất.")
    return redirect("catalog:home")


@login_required
def profile(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items", "items__product").order_by("-created_at")
    return render(request, "accounts/profile.html", {"orders": orders})
