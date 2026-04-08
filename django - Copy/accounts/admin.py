from django.contrib import admin
from .models import PasswordResetToken


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "is_used", "created_at", "expires_at")
    search_fields = ("user__username", "user__email", "token")
