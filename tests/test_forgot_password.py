import pytest
from django.core import mail
from rest_framework import status
from apps.authentication.models import OTPCode, PasswordResetToken
from apps.authentication.services import OTPService
from apps.notifications.sms import LocMemSMSBackend


@pytest.mark.django_db
class TestForgotPassword:
    request_url = "/api/v1/auth/forgot-password/request/"
    verify_url = "/api/v1/auth/forgot-password/verify/"
    reset_url = "/api/v1/auth/forgot-password/reset/"

    def test_forgot_password_request_email_sends_otp(self, api_client, active_user):
        payload = {"destination": active_user.email, "type": "email"}
        response = api_client.post(self.request_url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert len(mail.outbox) == 1
        assert "TiBoutik - Reset your password" in mail.outbox[0].subject

    def test_forgot_password_request_phone_sends_otp(self, api_client, active_user):
        payload = {"destination": active_user.phone, "type": "phone"}
        response = api_client.post(self.request_url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert len(LocMemSMSBackend.outbox) == 1
        assert LocMemSMSBackend.outbox[0]["destination"] == active_user.phone

    def test_forgot_password_request_nonexistent_returns_safe_success(self, api_client):
        payload = {"destination": "nonexistent@tiboutik.com", "type": "email"}
        response = api_client.post(self.request_url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        # No email sent
        assert len(mail.outbox) == 0

    def test_forgot_password_verify_otp_returns_reset_token(self, api_client, active_user):
        otp = OTPService.create_otp(
            destination=active_user.email,
            purpose=OTPCode.PURPOSE_PASSWORD_RESET,
            channel=OTPCode.CHANNEL_EMAIL,
            user=active_user,
        )

        payload = {
            "destination": active_user.email,
            "type": "email",
            "otp_code": otp.code,
        }
        response = api_client.post(self.verify_url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert "reset_token" in response.data["data"]

        # Verify token in DB
        reset_token_str = response.data["data"]["reset_token"]
        token_obj = PasswordResetToken.objects.get(token=reset_token_str)
        assert token_obj.user == active_user
        assert token_obj.is_used is False

    def test_forgot_password_reset_success(self, api_client, active_user):
        otp = OTPService.create_otp(
            destination=active_user.email,
            purpose=OTPCode.PURPOSE_PASSWORD_RESET,
            channel=OTPCode.CHANNEL_EMAIL,
            user=active_user,
        )
        verify_res = api_client.post(
            self.verify_url,
            data={"destination": active_user.email, "type": "email", "otp_code": otp.code},
            format="json",
        )
        reset_token = verify_res.data["data"]["reset_token"]

        payload = {
            "reset_token": reset_token,
            "new_password": "NewStrongPassword789!",
            "confirm_password": "NewStrongPassword789!",
        }
        response = api_client.post(self.reset_url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True

        # Check user can authenticate with new password
        active_user.refresh_from_db()
        assert active_user.check_password("NewStrongPassword789!")

        # Token is now used
        token_obj = PasswordResetToken.objects.get(token=reset_token)
        assert token_obj.is_used is True

        # Replay attempt fails
        replay_res = api_client.post(self.reset_url, data=payload, format="json")
        assert replay_res.status_code == status.HTTP_400_BAD_REQUEST

    def test_forgot_password_reset_mismatched_passwords_fails(self, api_client, active_user):
        payload = {
            "reset_token": "any-token",
            "new_password": "PasswordOne123!",
            "confirm_password": "PasswordTwo456!",
        }
        response = api_client.post(self.reset_url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "confirm_password" in response.data["error"]["details"]
