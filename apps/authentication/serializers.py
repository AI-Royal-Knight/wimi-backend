import re
from rest_framework import serializers
from apps.core.utils import normalize_email, normalize_phone
from apps.users.serializers import UserSerializer, MerchantStoreSerializer, RiderProfileSerializer


class SignupSerializer(serializers.Serializer):
    """
    Validates account registration data from frontend SignupPage.
    """
    full_name = serializers.CharField(max_length=150, min_length=3)
    email = serializers.EmailField(max_length=255)
    phone = serializers.CharField(max_length=30)
    password = serializers.CharField(min_length=8, write_only=True)
    terms_accepted = serializers.BooleanField(required=True)

    def validate_full_name(self, value):
        text = (value or "").strip()
        if len(text) < 3:
            raise serializers.ValidationError("Enter a valid full name (minimum 3 characters).")
        return text

    def validate_email(self, value):
        text = normalize_email(value)
        email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        if not email_regex.match(text):
            raise serializers.ValidationError("Enter a valid email address.")
        return text

    def validate_phone(self, value):
        text = (value or "").strip()
        normalized = normalize_phone(text)
        digits_only = "".join(filter(str.isdigit, normalized))
        if len(digits_only) < 8:
            raise serializers.ValidationError("Enter a valid phone number (at least 8 digits).")
        return normalized

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters.")
        return value

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError("Please agree to the terms of service and privacy policy.")
        return value


class VerifyOtpSerializer(serializers.Serializer):
    """
    Validates 4-digit numeric verification code for signup.
    """
    email = serializers.EmailField()
    otp_code = serializers.CharField(min_length=4, max_length=4)

    def validate_otp_code(self, value):
        code = value.strip()
        if not code.isdigit() or len(code) != 4:
            raise serializers.ValidationError("Enter a valid 4-digit OTP code.")
        return code


class ResendOtpSerializer(serializers.Serializer):
    """
    Validates email for resending signup OTP code.
    """
    email = serializers.EmailField()


class LoginSerializer(serializers.Serializer):
    """
    Accepts identifier (email or phone) and password.
    Directly supports both LoginPage toggle tabs.
    """
    identifier = serializers.CharField(required=False, help_text="Email address or phone number")
    email = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        # Resolve identifier from either identifier, email, or phone
        ident = attrs.get("identifier") or attrs.get("email") or attrs.get("phone")
        if not ident:
            raise serializers.ValidationError({"identifier": "Email address or phone number is required."})
        attrs["identifier"] = ident.strip()

        password = attrs.get("password")
        if not password:
            raise serializers.ValidationError({"password": "Password is required."})

        return attrs


class ForgotPasswordRequestSerializer(serializers.Serializer):
    """
    Request password reset OTP for email or phone.
    """
    destination = serializers.CharField()
    type = serializers.ChoiceField(choices=["email", "phone"], default="email")

    def validate_destination(self, value):
        dest = value.strip()
        if not dest:
            raise serializers.ValidationError("Destination is required.")
        return dest


class ForgotPasswordVerifySerializer(serializers.Serializer):
    """
    Verify 4-digit OTP code received for password recovery.
    """
    destination = serializers.CharField()
    type = serializers.ChoiceField(choices=["email", "phone"], default="email")
    otp_code = serializers.CharField(min_length=4, max_length=4)

    def validate_otp_code(self, value):
        code = value.strip()
        if not code.isdigit() or len(code) != 4:
            raise serializers.ValidationError("Please enter the complete 4-digit verification code.")
        return code


class ResetPasswordSerializer(serializers.Serializer):
    """
    Reset password using single-use reset token from NewPasswordPage.
    """
    reset_token = serializers.CharField()
    new_password = serializers.CharField(min_length=6, write_only=True)
    confirm_password = serializers.CharField(min_length=6, write_only=True, required=False)

    def validate(self, attrs):
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")

        if len(new_password) < 6:
            raise serializers.ValidationError({"new_password": "Password must be at least 6 characters long."})

        if confirm_password and new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """
    Change password for authenticated user (ChangePasswordPage checklist rules).
    """
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        new_pw = attrs.get("new_password")
        confirm_pw = attrs.get("confirm_password")

        if len(new_pw) < 8:
            raise serializers.ValidationError({"new_password": "Password must be at least 8 characters long."})

        if not any(c.isupper() for c in new_pw):
            raise serializers.ValidationError({"new_password": "Password must contain at least one uppercase letter."})

        if not any(c.isdigit() for c in new_pw):
            raise serializers.ValidationError({"new_password": "Password must contain at least one number."})

        if new_pw != confirm_pw:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        return attrs


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, help_text="Refresh token to blacklist")


class TokenRefreshSerializer(serializers.Serializer):
    """
    Refresh access token using valid refresh token.
    """
    refresh = serializers.CharField()


class AuthResponseDataSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()
    store = MerchantStoreSerializer(required=False)
    rider_profile = RiderProfileSerializer(required=False)


class MerchantRegisterSerializer(serializers.Serializer):
    """
    Validates complete merchant owner and store business registration.
    """
    full_name = serializers.CharField(max_length=150, min_length=3)
    email = serializers.EmailField(max_length=255)
    phone = serializers.CharField(max_length=30)
    password = serializers.CharField(min_length=8, write_only=True)
    store_name = serializers.CharField(max_length=200, min_length=2)
    category = serializers.CharField(max_length=100, default="Grocery")
    store_address = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    store_description = serializers.CharField(required=False, allow_blank=True, default="")
    terms_accepted = serializers.BooleanField(required=True)

    def validate_full_name(self, value):
        text = (value or "").strip()
        if len(text) < 3:
            raise serializers.ValidationError("Enter a valid full name (minimum 3 characters).")
        return text

    def validate_email(self, value):
        text = normalize_email(value)
        email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        if not email_regex.match(text):
            raise serializers.ValidationError("Enter a valid email address.")
        return text

    def validate_phone(self, value):
        text = (value or "").strip()
        normalized = normalize_phone(text)
        digits_only = "".join(filter(str.isdigit, normalized))
        if len(digits_only) < 8:
            raise serializers.ValidationError("Enter a valid phone number (at least 8 digits).")
        return normalized

    def validate_store_name(self, value):
        text = (value or "").strip()
        if len(text) < 2:
            raise serializers.ValidationError("Store name must be at least 2 characters long.")
        return text

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        return value

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError("Please agree to the merchant terms of service and privacy policy.")
        return value


class MerchantAuthResponseDataSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()
    store = MerchantStoreSerializer()


class RiderRegisterSerializer(serializers.Serializer):
    """
    Validates delivery partner / rider registration.
    """
    full_name = serializers.CharField(max_length=150, min_length=3)
    email = serializers.EmailField(max_length=255)
    phone = serializers.CharField(max_length=30)
    password = serializers.CharField(min_length=8, write_only=True)
    vehicle_type = serializers.ChoiceField(
        choices=["Motorcycle", "Bicycle"],
        default="Motorcycle",
    )
    number_plate = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default="",
    )
    zone = serializers.CharField(
        max_length=100,
        required=False,
        default="Port-au-Prince Centre",
    )
    terms_accepted = serializers.BooleanField(required=True)

    def validate_full_name(self, value):
        text = (value or "").strip()
        if len(text) < 3:
            raise serializers.ValidationError("Enter a valid full name (minimum 3 characters).")
        return text

    def validate_email(self, value):
        text = normalize_email(value)
        email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        if not email_regex.match(text):
            raise serializers.ValidationError("Enter a valid email address.")
        return text

    def validate_phone(self, value):
        text = (value or "").strip()
        normalized = normalize_phone(text)
        digits_only = "".join(filter(str.isdigit, normalized))
        if len(digits_only) < 8:
            raise serializers.ValidationError("Enter a valid phone number (at least 8 digits).")
        return normalized

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        return value

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError("Please agree to the delivery fleet partner terms and safety policies.")
        return value


class RiderAuthResponseDataSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()

