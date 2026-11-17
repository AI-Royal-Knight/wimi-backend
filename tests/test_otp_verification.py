from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework import status
from apps.authentication.models import OTPCode
from apps.authentication.services import OTPService


@pytest.mark.django_db
class TestOtpVerification:
    url = "/api/v1/auth/signup/verify/"

    def test_verify_otp_success_activates_user_and_returns_jwt_tokens(self, api_client, unverified_user):
        otp = OTPService.create_otp(
            destination=unverified_user.email,
            purpose=OTPCode.PURPOSE_SIGNUP,
            channel=OTPCode.CHANNEL_EMAIL,
            user=unverified_user,
        )

        payload = {
            "email": unverified_user.email,
            "otp_code": otp.code,
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert "access" in response.data["data"]
        assert "refresh" in response.data["data"]
        assert response.data["data"]["user"]["email"] == unverified_user.email
        assert response.data["data"]["user"]["is_verified"] is True

        # Check DB state
        unverified_user.refresh_from_db()
        assert unverified_user.is_active is True
        assert unverified_user.is_verified is True
        assert unverified_user.email_verified_at is not None

        otp.refresh_from_db()
        assert otp.is_used is True

    def test_verify_otp_invalid_code_records_attempt(self, api_client, unverified_user):
        otp = OTPService.create_otp(
            destination=unverified_user.email,
            purpose=OTPCode.PURPOSE_SIGNUP,
            channel=OTPCode.CHANNEL_EMAIL,
            user=unverified_user,
        )

        payload = {
            "email": unverified_user.email,
            "otp_code": "0000" if otp.code != "0000" else "9999",
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "OTP_INVALID"

        otp.refresh_from_db()
        assert otp.attempts == 1
        assert otp.is_used is False

    def test_verify_otp_exceeding_max_attempts_burns_code(self, api_client, unverified_user):
        otp = OTPService.create_otp(
            destination=unverified_user.email,
            purpose=OTPCode.PURPOSE_SIGNUP,
            channel=OTPCode.CHANNEL_EMAIL,
            user=unverified_user,
        )
        otp.attempts = 4
        otp.save()

        payload = {
            "email": unverified_user.email,
            "otp_code": "0000" if otp.code != "0000" else "9999",
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.data["error"]["code"] == "OTP_MAX_ATTEMPTS_EXCEEDED"

        otp.refresh_from_db()
        assert otp.is_used is True  # burned

    def test_verify_otp_expired_code(self, api_client, unverified_user):
        otp = OTPService.create_otp(
            destination=unverified_user.email,
            purpose=OTPCode.PURPOSE_SIGNUP,
            channel=OTPCode.CHANNEL_EMAIL,
            user=unverified_user,
        )
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()

        payload = {
            "email": unverified_user.email,
            "otp_code": otp.code,
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "OTP_EXPIRED"

    def test_verify_otp_replay_protection_used_code_fails(self, api_client, unverified_user):
        otp = OTPService.create_otp(
            destination=unverified_user.email,
            purpose=OTPCode.PURPOSE_SIGNUP,
            channel=OTPCode.CHANNEL_EMAIL,
            user=unverified_user,
        )
        # Mark as used
        otp.mark_used()

        payload = {
            "email": unverified_user.email,
            "otp_code": otp.code,
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "OTP_INVALID"
