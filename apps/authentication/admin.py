from django.contrib import admin
from .models import OTPCode, PasswordResetToken


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = (
        "destination",
        "purpose",
        "channel",
        "attempts",
        "max_attempts",
        "is_used",
        "expires_at",
        "created_at",
    )
    list_filter = ("purpose", "channel", "is_used", "created_at")
    search_fields = ("destination", "code")
    readonly_fields = ("created_at",)


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "is_used", "expires_at", "created_at")
    list_filter = ("is_used", "created_at")
    search_fields = ("user__email", "user__phone", "token")
    readonly_fields = ("created_at",)
