from rest_framework import serializers
from apps.core.utils import normalize_phone
from .models import User, MerchantStore, RiderProfile


class RiderProfileSerializer(serializers.ModelSerializer):
    """Public representation of Rider Profile."""
    is_approved = serializers.SerializerMethodField()

    class Meta:
        model = RiderProfile
        fields = [
            "id",
            "vehicle_type",
            "number_plate",
            "zone",
            "status",
            "is_approved",
            "deliveries_count",
            "total_earnings",
            "wallet_balance",
            "nid_front",
            "nid_back",
            "license_front",
            "license_back",
            "submission_date",
            "submission_id",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "is_approved",
            "deliveries_count",
            "total_earnings",
            "wallet_balance",
            "submission_date",
            "submission_id",
            "created_at",
        ]

    def get_is_approved(self, obj):
        return obj.status in [RiderProfile.STATUS_ACTIVE, RiderProfile.STATUS_ON_DELIVERY, RiderProfile.STATUS_OFFLINE]


class MerchantStoreSerializer(serializers.ModelSerializer):
    """Public representation of Merchant Store."""

    class Meta:
        model = MerchantStore
        fields = [
            "id",
            "name",
            "category",
            "address",
            "description",
            "phone",
            "logo",
            "banner",
            "is_verified",
            "is_open",
            "rating",
            "reviews_count",
            "bank_name",
            "account_number",
            "account_holder",
            "routing_number",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "is_verified",
            "rating",
            "reviews_count",
            "created_at",
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get("request")
        if request:
            if instance.logo:
                ret["logo"] = request.build_absolute_uri(instance.logo.url)
            if instance.banner:
                ret["banner"] = request.build_absolute_uri(instance.banner.url)
        return ret


class UserSerializer(serializers.ModelSerializer):
    """Public representation of User profile."""
    store = MerchantStoreSerializer(source="merchant_store", read_only=True)
    rider_profile = RiderProfileSerializer(read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "full_name",
            "role",
            "avatar",
            "is_verified",
            "is_staff",
            "is_superuser",
            "terms_accepted",
            "date_joined",
            "store",
            "rider_profile",
        ]
        read_only_fields = [
            "id",
            "email",
            "role",
            "is_verified",
            "is_staff",
            "is_superuser",
            "terms_accepted",
            "date_joined",
            "store",
            "rider_profile",
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Ensure staff and superusers always expose role 'admin'
        if instance.is_superuser or instance.is_staff:
            if ret.get("role") == "customer":
                ret["role"] = "admin"
        return ret

    def get_avatar(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.avatar.url)
        return obj.avatar.url


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile attributes."""
    full_name = serializers.CharField(required=False, max_length=150)
    phone = serializers.CharField(required=False, max_length=30)
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["full_name", "phone", "avatar"]

    def validate_full_name(self, value):
        text = (value or "").strip()
        if len(text) < 2:
            raise serializers.ValidationError("Full name must be at least 2 characters long.")
        return text

    def validate_phone(self, value):
        if not value:
            return value
        normalized = normalize_phone(value)
        digits_only = "".join(filter(str.isdigit, normalized))
        if len(digits_only) < 8:
            raise serializers.ValidationError("Enter a valid phone number (at least 8 digits).")

        # Ensure uniqueness across other users
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            if User.objects.exclude(id=user.id).filter(phone=normalized).exists():
                raise serializers.ValidationError("A user with this phone number already exists.")

        return normalized
