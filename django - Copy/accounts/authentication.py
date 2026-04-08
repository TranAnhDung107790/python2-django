from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailOrUsernameBackend(ModelBackend):
    """Cho phép đăng nhập bằng email/username không phân biệt hoa thường."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        login_value = (username or kwargs.get("email") or "").strip()
        if not login_value or not password:
            return None

        user = (
            User.objects.filter(username__iexact=login_value).first()
            or User.objects.filter(email__iexact=login_value).first()
        )
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
