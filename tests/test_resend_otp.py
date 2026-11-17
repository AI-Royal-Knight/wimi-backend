from datetime import timedelta
import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status
from apps.authentication.models import OTPCode
from apps.authentication.services import OTPService


@pytest.mark.django_db
class TestResendOtp:
    url = "/api/v1/auth/signup/resend-otp/"

    def test_resend_otp_success_after_cooldown(self, api_client, unverified_user):
        # Create an initial OTP from 70 seconds ago (cooldown expired)
        otp = OTPService.create_otp(
            destination=unverified_user.email,
            purpose=OTPCode.PURPOSE_SIGNUP,
            channel=OTPCode.CHANNEL_EMAIL,
            user=unverified_user,
        )
        otp.created_at = timezone.now() - timedelta(seconds=70)
        otp.save()

        mail.outbox.clear()

        response = api_client.post(self.url, data={"email": unverified_user.email}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert len(mail.outbox) == 1

    def test_resend_otp_cooldown_enforced_within_60_seconds(self, api_client, unverified_user):
        # Create an initial OTP just created now
        OTPService.create_otp(
            destination=unverified_user.email,
            purpose=OTPCode.PURPOSE_SIGNUP,
            channel=OTPCode.CHANNEL_EMAIL,
            user=unverified_user,
        )

        response = api_client.post(self.url, data={"email": unverified_user.email}, format="json")

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "COOLDOWN_ACTIVE"
        assert "remaining_seconds" in response.data["error"]["details"]

    def test_resend_otp_already_verified_account_fails(self, api_client, active_user):
        response = api_client.post(self.url, data={"email": active_user.email}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "ACCOUNT_ALREADY_VERIFIED"
