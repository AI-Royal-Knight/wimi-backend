import pytest
from rest_framework import status


@pytest.mark.django_db
class TestLogin:
    url = "/api/v1/auth/login/"

    def test_login_with_email_success(self, api_client, active_user):
        payload = {
            "identifier": active_user.email,
            "password": "ValidPassword123!",
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert "access" in response.data["data"]
        assert "refresh" in response.data["data"]
        assert response.data["data"]["user"]["email"] == active_user.email

    def test_login_with_phone_success(self, api_client, active_user):
        payload = {
            "phone": active_user.phone,
            "password": "ValidPassword123!",
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert response.data["data"]["user"]["id"] == str(active_user.id)

    def test_login_invalid_password_returns_401(self, api_client, active_user):
        payload = {
            "identifier": active_user.email,
            "password": "WrongPassword!",
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["success"] is False
        assert response.data["error"]["code"] == "AUTHENTICATION_FAILED"

    def test_login_unverified_account_returns_403(self, api_client, unverified_user):
        payload = {
            "identifier": unverified_user.email,
            "password": "ValidPassword123!",
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"]["code"] == "UNVERIFIED_ACCOUNT"
        assert response.data["error"]["details"]["email"] == unverified_user.email

    def test_legacy_endpoint_compatibility(self, api_client, active_user):
        """Tests /api/auth/login route specified in Flutter Endpoints.login"""
        payload = {
            "identifier": active_user.email,
            "password": "ValidPassword123!",
        }
        response = api_client.post("/api/auth/login", data=payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
