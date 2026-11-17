import logging
from django.conf import settings
from django.core.mail import send_mail
from .base import BaseNotificationBackend

logger = logging.getLogger(__name__)


class EmailNotificationService(BaseNotificationBackend):
    """Email delivery service using configured Django EMAIL_BACKEND."""

    def send_verification_otp(self, destination: str, code: str, purpose: str = "signup") -> bool:
        if purpose == "signup":
            subject = "TiBoutik - Verify your account"
            message = (
                f"Welcome to TiBoutik!\n\n"
                f"Your 4-digit verification code is: {code}\n\n"
                f"This code will expire in 10 minutes. If you did not create an account, please ignore this email.\n"
            )
            html_message = (
                f"<div style='font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;'>"
                f"<h2 style='color: #FF7449;'>Welcome to TiBoutik</h2>"
                f"<p>Use the 4-digit code below to verify your account:</p>"
                f"<div style='font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #1E293B; background: #F8FAFC; padding: 16px; border-radius: 8px; text-align: center; margin: 24px 0;'>"
                f"{code}"
                f"</div>"
                f"<p style='color: #64748B; font-size: 14px;'>This code is valid for 10 minutes. Never share this code with anyone.</p>"
                f"</div>"
            )
        else:  # password reset
            subject = "TiBoutik - Reset your password"
            message = (
                f"You requested to reset your TiBoutik account password.\n\n"
                f"Your 4-digit recovery code is: {code}\n\n"
                f"This code will expire in 10 minutes. If you did not request this, please secure your account immediately.\n"
            )
            html_message = (
                f"<div style='font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;'>"
                f"<h2 style='color: #FF7449;'>TiBoutik Password Reset</h2>"
                f"<p>Your password recovery code is:</p>"
                f"<div style='font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #1E293B; background: #F8FAFC; padding: 16px; border-radius: 8px; text-align: center; margin: 24px 0;'>"
                f"{code}"
                f"</div>"
                f"<p style='color: #64748B; font-size: 14px;'>This code is valid for 10 minutes. Never share this code with anyone.</p>"
                f"</div>"
            )

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destination],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info("Verification email dispatched successfully to recipient")
            return True
        except Exception as e:
            logger.error("Failed to send verification email: %s", str(e))
            return False
