import hmac
import logging
from datetime import timedelta
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string
from rest_framework import exceptions
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions import (
    AccountAlreadyVerifiedError,
    CooldownActiveError,
    OTPAttemptsExceededError,
    OTPExpiredError,
    OTPInvalidError,
    UnverifiedAccountError,
)
from apps.core.utils import (
    generate_otp_code,
    generate_secure_token,
    normalize_email,
    normalize_phone,
)
from apps.notifications.email import EmailNotificationService
from .models import OTPCode, PasswordResetToken

logger = logging.getLogger(__name__)
User = get_user_model()


class OTPService:
    """Manages OTP generation, throttling/cooldown, delivery, and verification."""

    @staticmethod
    def _get_notification_backend(channel: str):
        if channel == OTPCode.CHANNEL_EMAIL:
            return EmailNotificationService()
        elif channel == OTPCode.CHANNEL_SMS:
            sms_backend_path = getattr(settings, "SMS_BACKEND", "apps.notifications.sms.ConsoleSMSBackend")
            backend_cls = import_string(sms_backend_path)
            return backend_cls()
        raise ValueError(f"Unsupported notification channel: {channel}")

    @classmethod
    def create_otp(
        cls,
        destination: str,
        purpose: str,
        channel: str,
        user: Optional[Any] = None,
    ) -> OTPCode:
        destination = normalize_email(destination) if channel == OTPCode.CHANNEL_EMAIL else normalize_phone(destination)

        # Check cooldown from latest OTP request
        cooldown_seconds = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)
        latest_otp = (
            OTPCode.objects.filter(destination=destination, purpose=purpose)
            .order_by("-created_at")
            .first()
        )

        if latest_otp:
            elapsed = (timezone.now() - latest_otp.created_at).total_seconds()
            if elapsed < cooldown_seconds:
                remaining = int(cooldown_seconds - elapsed)
                raise CooldownActiveError(
                    detail=f"Please wait {remaining} seconds before requesting a new code.",
                    details={"remaining_seconds": remaining},
                )

        # Generate 4-digit code
        code = generate_otp_code(4)
        expiration_seconds = getattr(settings, "OTP_EXPIRATION_SECONDS", 600)
        expires_at = timezone.now() + timedelta(seconds=expiration_seconds)

        otp = OTPCode.objects.create(
            user=user,
            destination=destination,
            code=code,
            purpose=purpose,
            channel=channel,
            expires_at=expires_at,
            max_attempts=getattr(settings, "OTP_MAX_ATTEMPTS", 5),
        )

        # Dispatch notification safely after transaction commits (or immediately in testing)
        def send_notification():
            backend = cls._get_notification_backend(channel)
            backend.send_verification_otp(destination=destination, code=code, purpose=purpose)

        if getattr(settings, "TESTING", False) or not transaction.get_connection().in_atomic_block:
            send_notification()
        else:
            transaction.on_commit(send_notification)

        return otp

    @classmethod
    def verify_otp(cls, destination: str, code: str, purpose: str) -> OTPCode:
        destination = destination.strip()
        # Find the latest unused OTP
        otp = (
            OTPCode.objects.filter(
                destination=destination,
                purpose=purpose,
                is_used=False,
            )
            .order_by("-created_at")
            .first()
        )

        if not otp:
            raise OTPInvalidError("Invalid verification code or code already used.")

        if otp.is_expired():
            raise OTPExpiredError("Verification code has expired. Please request a new one.")

        if otp.has_exceeded_attempts():
            otp.burn()
            raise OTPAttemptsExceededError("Maximum verification attempts exceeded. Please request a new code.")

        # Constant-time comparison
        is_match = hmac.compare_digest(str(otp.code), str(code).strip())

        if not is_match:
            otp.record_attempt()
            remaining = otp.max_attempts - otp.attempts
            if remaining <= 0:
                otp.burn()
                raise OTPAttemptsExceededError("Maximum verification attempts exceeded. Please request a new code.")
            raise OTPInvalidError(
                f"Invalid verification code. {remaining} attempt(s) remaining.",
                details={"remaining_attempts": remaining},
            )

        # Mark OTP as successfully used
        otp.mark_used()
        return otp


class AuthService:
    """Core domain service for user onboarding, authentication, and password management."""

    @classmethod
    @transaction.atomic
    def signup(
        cls,
        full_name: str,
        email: str,
        phone: str,
        password: str,
        terms_accepted: bool,
    ) -> Tuple[Any, OTPCode]:
        email = normalize_email(email)
        phone = normalize_phone(phone)

        if not terms_accepted:
            raise exceptions.ValidationError({"terms_accepted": ["You must agree to the Terms of Service and Privacy Policy."]})

        # Check existing accounts
        existing_by_email = User.objects.filter(email=email).first()
        existing_by_phone = User.objects.filter(phone=phone).first()

        if existing_by_email and existing_by_email.is_verified:
            raise exceptions.ValidationError({"email": ["An account with this email already exists."]})
        if existing_by_phone and existing_by_phone.is_verified:
            raise exceptions.ValidationError({"phone": ["An account with this phone number already exists."]})

        if existing_by_email and existing_by_phone and existing_by_email.id != existing_by_phone.id:
            raise exceptions.ValidationError({
                "email": ["This email is associated with a different pending account than this phone number."]
            })

        user = existing_by_email or existing_by_phone
        if user:
            # User previously started registration but did not verify: update details and resend OTP
            user.full_name = full_name
            user.email = email
            user.phone = phone
            user.terms_accepted = True
            user.terms_accepted_at = timezone.now()
            user.set_password(password)
            user.save()
        else:
            user = User.objects.create_user(
                email=email,
                phone=phone,
                full_name=full_name,
                password=password,
                terms_accepted=True,
                terms_accepted_at=timezone.now(),
                is_active=False,
                is_verified=False,
            )

        # Issue 4-digit verification code to user email (as required by OtpVerifyPage)
        otp = OTPService.create_otp(
            destination=user.email,
            purpose=OTPCode.PURPOSE_SIGNUP,
            channel=OTPCode.CHANNEL_EMAIL,
            user=user,
        )

        return user, otp

    @classmethod
    def verify_signup_otp(cls, email: str, otp_code: str) -> Dict[str, Any]:
        email = normalize_email(email)
        user = User.objects.filter(email=email).first()
        if not user:
            raise exceptions.NotFound("Account not found.")

        if user.is_verified:
            raise AccountAlreadyVerifiedError("Account is already verified. Please sign in.")

        # Verify OTP first (independent of user transaction so failed attempts persist)
        OTPService.verify_otp(destination=email, code=otp_code, purpose=OTPCode.PURPOSE_SIGNUP)

        # Activate user in atomic block
        with transaction.atomic():
            user.mark_verified("email")

        # Generate JWT Tokens
        refresh = RefreshToken.for_user(user)

        from apps.users.serializers import UserSerializer

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        }

    @classmethod
    def resend_signup_otp(cls, email: str) -> OTPCode:
        email = normalize_email(email)
        user = User.objects.filter(email=email).first()
        if not user:
            raise exceptions.NotFound("Account not found.")

        if user.is_verified:
            raise AccountAlreadyVerifiedError("Account is already verified. Please sign in.")

        return OTPService.create_otp(
            destination=email,
            purpose=OTPCode.PURPOSE_SIGNUP,
            channel=OTPCode.CHANNEL_EMAIL,
            user=user,
        )

    @classmethod
    def login(cls, identifier: str, password: str) -> Dict[str, Any]:
        identifier = identifier.strip()
        # Check if identifier is email or phone
        if "@" in identifier:
            email = normalize_email(identifier)
            user = User.objects.filter(email=email).first()
        else:
            phone = normalize_phone(identifier)
            # Match exact phone, or with + prefix, or matching Haiti (+509) variations
            user = (
                User.objects.filter(phone=phone).first()
                or (not phone.startswith("+") and User.objects.filter(phone=f"+{phone}").first())
                or (len(phone) == 8 and User.objects.filter(phone=f"+509{phone}").first())
                or (phone.startswith("509") and User.objects.filter(phone=f"+{phone}").first())
            )

        if not user or not user.check_password(password):
            raise exceptions.AuthenticationFailed("Invalid email/phone or password.")

        if getattr(user, "is_banned", False):
            reason = getattr(user, "ban_reason", "")
            msg = f"Your account has been suspended: {reason}" if reason else "Your account has been suspended by an administrator."
            raise exceptions.AuthenticationFailed(msg)

        # Ensure platform administrators are never blocked by verification states
        if (user.is_superuser or user.is_staff or user.role == User.ROLE_ADMIN) and not (user.is_verified and user.is_active):
            user.is_active = True
            user.is_verified = True
            user.save(update_fields=["is_active", "is_verified", "updated_at"])

        if not user.is_verified or not user.is_active:
            raise UnverifiedAccountError(
                "Your account is not verified yet. Please verify your account with OTP.",
                details={"email": user.email},
            )

        refresh = RefreshToken.for_user(user)
        from apps.users.serializers import UserSerializer

        user_data = UserSerializer(user).data
        result: Dict[str, Any] = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user_data,
        }

        # Include store if user is a merchant
        if hasattr(user, "merchant_store") and user.merchant_store:
            from apps.users.serializers import MerchantStoreSerializer
            result["store"] = MerchantStoreSerializer(user.merchant_store).data

        # Include rider_profile if user is a rider
        if hasattr(user, "rider_profile") and user.rider_profile:
            from apps.users.serializers import RiderProfileSerializer
            result["rider_profile"] = RiderProfileSerializer(user.rider_profile).data

        return result

    @classmethod
    def request_password_reset(cls, destination: str, dest_type: str = "email") -> bool:
        if dest_type == "email":
            dest_normalized = normalize_email(destination)
            user = User.objects.filter(email=dest_normalized).first()
            channel = OTPCode.CHANNEL_EMAIL
        else:
            dest_normalized = normalize_phone(destination)
            user = User.objects.filter(phone=dest_normalized).first()
            channel = OTPCode.CHANNEL_SMS

        # Anti-enumeration: if user doesn't exist, return True without generating OTP
        if not user:
            logger.info("Password reset requested for non-existent destination: %s", dest_normalized)
            return True

        OTPService.create_otp(
            destination=dest_normalized,
            purpose=OTPCode.PURPOSE_PASSWORD_RESET,
            channel=channel,
            user=user,
        )
        return True

    @classmethod
    def verify_password_reset_otp(cls, destination: str, otp_code: str, dest_type: str = "email") -> str:
        dest_normalized = normalize_email(destination) if dest_type == "email" else normalize_phone(destination)
        user = User.objects.filter(email=dest_normalized).first() if dest_type == "email" else User.objects.filter(phone=dest_normalized).first()
        if not user:
            raise exceptions.NotFound("Account not found.")

        # Verify OTP
        OTPService.verify_otp(
            destination=dest_normalized,
            code=otp_code,
            purpose=OTPCode.PURPOSE_PASSWORD_RESET,
        )

        # Issue single-use reset token
        reset_token_str = generate_secure_token(48)
        expiration_seconds = getattr(settings, "OTP_EXPIRATION_SECONDS", 600)
        PasswordResetToken.objects.create(
            user=user,
            token=reset_token_str,
            expires_at=timezone.now() + timedelta(seconds=expiration_seconds),
        )

        return reset_token_str

    @classmethod
    @transaction.atomic
    def reset_password(cls, reset_token: str, new_password: str) -> Any:
        token_obj = (
            PasswordResetToken.objects.filter(token=reset_token, is_used=False)
            .select_related("user")
            .first()
        )

        if not token_obj or not token_obj.is_valid():
            raise exceptions.ValidationError({"reset_token": ["Reset token is invalid or has expired."]})

        user = token_obj.user
        user.set_password(new_password)
        user.save()

        token_obj.mark_used()
        return user

    @classmethod
    @transaction.atomic
    def change_password(cls, user: Any, current_password: str, new_password: str) -> None:
        if not user.check_password(current_password):
            raise exceptions.ValidationError({"current_password": ["Current password is incorrect."]})

        user.set_password(new_password)
        user.save()

    @classmethod
    @transaction.atomic
    def register_merchant(
        cls,
        full_name: str,
        email: str,
        phone: str,
        password: str,
        store_name: str,
        category: str = "Grocery",
        store_address: str = "",
        store_description: str = "",
        terms_accepted: bool = True,
    ) -> Dict[str, Any]:
        from apps.users.models import MerchantStore
        from apps.users.serializers import UserSerializer, MerchantStoreSerializer

        email = normalize_email(email)
        phone = normalize_phone(phone)

        if not terms_accepted:
            raise exceptions.ValidationError({"terms_accepted": ["You must agree to the Merchant Terms of Service."]})

        if User.objects.filter(email=email).exists():
            raise exceptions.ValidationError({"email": ["An account with this email address already exists."]})
        if User.objects.filter(phone=phone).exists():
            raise exceptions.ValidationError({"phone": ["An account with this phone number already exists."]})

        # Create Merchant User
        user = User.objects.create_user(
            email=email,
            phone=phone,
            full_name=full_name,
            password=password,
            role=User.ROLE_MERCHANT,
            is_active=True,
            is_verified=True,
            terms_accepted=True,
            terms_accepted_at=timezone.now(),
        )

        # Create Associated Merchant Store
        store = MerchantStore.objects.create(
            owner=user,
            name=store_name,
            category=category or MerchantStore.CATEGORY_GROCERY,
            address=store_address,
            description=store_description,
            phone=phone,
            is_verified=True,
            is_open=True,
        )

        refresh = RefreshToken.for_user(user)

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
            "store": MerchantStoreSerializer(store).data,
        }

    @classmethod
    @transaction.atomic
    def register_rider(
        cls,
        full_name: str,
        email: str,
        phone: str,
        password: str,
        vehicle_type: str = "Motorcycle",
        number_plate: str = "",
        zone: str = "Port-au-Prince Centre",
        terms_accepted: bool = True,
    ) -> Dict[str, Any]:
        from apps.users.models import RiderProfile
        from apps.users.serializers import UserSerializer

        email = normalize_email(email)
        phone = normalize_phone(phone)

        if not terms_accepted:
            raise exceptions.ValidationError({"terms_accepted": ["You must agree to the Fleet Partner Terms of Service."]})

        if User.objects.filter(email=email).exists():
            raise exceptions.ValidationError({"email": ["An account with this email address already exists."]})
        if User.objects.filter(phone=phone).exists():
            raise exceptions.ValidationError({"phone": ["An account with this phone number already exists."]})

        # Create Rider User
        user = User.objects.create_user(
            email=email,
            phone=phone,
            full_name=full_name,
            password=password,
            role=User.ROLE_RIDER,
            is_active=True,
            is_verified=True,
            terms_accepted=True,
            terms_accepted_at=timezone.now(),
        )

        # Create Rider Fleet Profile in Pending Verification status
        rider_profile = RiderProfile.objects.create(
            user=user,
            vehicle_type=vehicle_type or RiderProfile.VEHICLE_MOTORCYCLE,
            number_plate=(number_plate or "").strip().upper(),
            zone=zone or "Port-au-Prince Centre",
            status=RiderProfile.STATUS_PENDING,
        )

        refresh = RefreshToken.for_user(user)
        from apps.users.serializers import RiderProfileSerializer

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
            "rider_profile": RiderProfileSerializer(rider_profile).data,
        }

