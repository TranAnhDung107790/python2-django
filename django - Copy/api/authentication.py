from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication, exceptions
import jwt


class BearerJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        token = header.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            if payload.get("type") != "access":
                raise exceptions.AuthenticationFailed("Invalid token type")
            user = User.objects.get(id=payload.get("sub"))
            return user, token
        except Exception:
            raise exceptions.AuthenticationFailed("Invalid token")
