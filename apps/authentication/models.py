import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class OTPCode(models.Model):
    """
    Stores 4-digit numeric verification codes for account signup and password recovery.
    Includes brute-force attempt limits, expiration, and replay prevention.
    """
    PURPOSE_SIGNUP = "signup"
    PURPOSE_PASSWORD_RESET = "password_reset"
    PURPOSE_CHOICES = (
        (PURPOSE_SIGNUP, "Signup Verification"),
        (PURPOSE_PASSWORD_RESET, "Password Reset"),
    )

    CHANNEL_EMAIL = "email"
    CHANNEL_SMS = "sms"
    CHANNEL_CHOICES = (
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_SMS, "SMS"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="otps",
        null=True,
        blank=True,
    )
    destination = models.CharField(max_length=255, db_index=True)
    code = models.CharField(max_length=10)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default=PURPOSE_SIGNUP)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default=CHANNEL_EMAIL)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auth_otp_codes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["destination", "purpose", "is_used"], name="idx_otp_dest_purpose"),
            models.Index(fields=["created_at"], name="idx_otp_created_at"),
        ]

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def has_exceeded_attempts(self) -> bool:
        return self.attempts >= self.max_attempts

    def is_valid_state(self) -> bool:
        return not self.is_used and not self.is_expired() and not self.has_exceeded_attempts()

    def record_attempt(self):
        self.attempts += 1
        self.save(update_fields=["attempts"])

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=["is_used"])

    def burn(self):
        """Immediately burns the OTP so it cannot be attempted again."""
        self.is_used = True
        self.save(update_fields=["is_used"])

    def __str__(self):
        return f"OTP ({self.purpose}) for {self.destination} [Used: {self.is_used}]"


class PasswordResetToken(models.Model):
    """
    Temporary single-use cryptographic token issued after OTP verification to reset password.
    Valid for 10 minutes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token = models.CharField(max_length=128, unique=True, db_index=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auth_password_reset_tokens"
        ordering = ["-created_at"]

    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=["is_used"])

    def __str__(self):
        return f"ResetToken for {self.user.email} [Used: {self.is_used}]"
