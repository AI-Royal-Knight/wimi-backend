from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, MerchantStore, RiderProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "full_name",
        "phone",
        "role",
        "is_active",
        "is_verified",
        "is_staff",
        "date_joined",
    )
    list_filter = ("role", "is_active", "is_verified", "is_staff", "terms_accepted")
    search_fields = ("email", "full_name", "phone")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "phone", "role", "avatar")}),
        (
            "Permissions & Status",
            {
                "fields": (
                    "is_active",
                    "is_verified",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Verification & Compliance",
            {"fields": ("email_verified_at", "phone_verified_at", "terms_accepted", "terms_accepted_at")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )

    readonly_fields = ("date_joined", "updated_at", "email_verified_at", "phone_verified_at", "terms_accepted_at")

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "phone", "role", "password", "is_active", "is_verified"),
            },
        ),
    )


@admin.register(MerchantStore)
class MerchantStoreAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "owner",
        "is_verified",
        "is_open",
        "rating",
        "reviews_count",
        "created_at",
    )
    list_filter = ("category", "is_verified", "is_open")
    search_fields = ("name", "owner__email", "owner__full_name", "phone", "address")
    readonly_fields = ("created_at", "updated_at")


@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "vehicle_type",
        "zone",
        "status",
        "deliveries_count",
        "total_earnings",
        "created_at",
    )
    list_filter = ("status", "vehicle_type", "zone")
    search_fields = ("user__email", "user__full_name", "user__phone", "number_plate", "zone")
    readonly_fields = ("created_at", "updated_at")
