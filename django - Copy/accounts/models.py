from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class PasswordResetToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reset_tokens")
    token = models.CharField(max_length=128, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    @staticmethod
    def build_expiry(minutes: int = 30):
        return timezone.now() + timedelta(minutes=minutes)
