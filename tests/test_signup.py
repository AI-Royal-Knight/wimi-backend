import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework import status
from apps.authentication.models import OTPCode

User = get_user_model()


@pytest.mark.django_db
class TestSignup:
    url = "/api/v1/auth/signup/"

    def test_signup_success_creates_inactive_user_and_sends_otp(self, api_client):
        payload = {
            "full_name": "Jean-Pierre Laurent",
            "email": "jean.laurent@email.com",
            "phone": "+509 1234 5678",
            "password": "SecurePassword123!",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"] is True
        assert response.data["data"]["email"] == "jean.laurent@email.com"

        # Verify user created in DB as inactive and unverified
        user = User.objects.get(email="jean.laurent@email.com")
        assert user.is_active is False
        assert user.is_verified is False
        assert user.full_name == "Jean-Pierre Laurent"
        assert user.terms_accepted is True
        assert user.terms_accepted_at is not None

        # Verify OTP code created and sent via email
        otp = OTPCode.objects.filter(destination="jean.laurent@email.com", purpose=OTPCode.PURPOSE_SIGNUP).first()
        assert otp is not None
        assert len(otp.code) == 4
        assert otp.code.isdigit()
        assert otp.is_used is False

        # Verify email dispatched
        assert len(mail.outbox) == 1
        assert "TiBoutik - Verify your account" in mail.outbox[0].subject
        assert otp.code in mail.outbox[0].body

    def test_signup_validation_short_name(self, api_client):
        payload = {
            "full_name": "Jo",
            "email": "valid@email.com",
            "phone": "+50912345678",
            "password": "SecurePassword123!",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False
        assert "full_name" in response.data["error"]["details"]

    def test_signup_validation_invalid_email(self, api_client):
        payload = {
            "full_name": "Jean Laurent",
            "email": "not-an-email",
            "phone": "+50912345678",
            "password": "SecurePassword123!",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False
        assert "email" in response.data["error"]["details"]

    def test_signup_validation_short_phone(self, api_client):
        payload = {
            "full_name": "Jean Laurent",
            "email": "valid@email.com",
            "phone": "1234",
            "password": "SecurePassword123!",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False
        assert "phone" in response.data["error"]["details"]

    def test_signup_validation_short_password(self, api_client):
        payload = {
            "full_name": "Jean Laurent",
            "email": "valid@email.com",
            "phone": "+50912345678",
            "password": "short",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False
        assert "password" in response.data["error"]["details"]

    def test_signup_validation_terms_not_accepted(self, api_client):
        payload = {
            "full_name": "Jean Laurent",
            "email": "valid@email.com",
            "phone": "+50912345678",
            "password": "SecurePassword123!",
            "terms_accepted": False,
        }
        response = api_client.post(self.url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False
        assert "terms_accepted" in response.data["error"]["details"]

    def test_signup_duplicate_verified_account_fails(self, api_client, active_user):
        payload = {
            "full_name": "Duplicate User",
            "email": active_user.email,
            "phone": "+50999999999",
            "password": "AnotherPassword123!",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False
        assert "email" in response.data["error"]["details"]

    def test_signup_duplicate_unverified_account_updates_and_resends_code(self, api_client, unverified_user):
        payload = {
            "full_name": "Updated Name",
            "email": unverified_user.email,
            "phone": unverified_user.phone,
            "password": "BrandNewPassword123!",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"] is True

        unverified_user.refresh_from_db()
        assert unverified_user.full_name == "Updated Name"
        assert unverified_user.check_password("BrandNewPassword123!")
        assert len(mail.outbox) == 1
