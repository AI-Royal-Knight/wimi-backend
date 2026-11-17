import pytest
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db
class TestProfileAndPasswordChange:
    me_url = "/api/v1/auth/me/"
    change_pw_url = "/api/v1/auth/change-password/"
    logout_url = "/api/v1/auth/logout/"

    def test_get_profile_authenticated(self, authenticated_client, active_user):
        response = authenticated_client.get(self.me_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert response.data["data"]["email"] == active_user.email
        assert response.data["data"]["full_name"] == active_user.full_name

    def test_get_profile_unauthenticated_fails_401(self, api_client):
        response = api_client.get(self.me_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["success"] is False

    def test_update_profile_success(self, authenticated_client, active_user):
        payload = {
            "full_name": "Jean-Pierre Updated",
            "phone": "+50998765432",
        }
        response = authenticated_client.patch(self.me_url, data=payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["full_name"] == "Jean-Pierre Updated"

        active_user.refresh_from_db()
        assert active_user.full_name == "Jean-Pierre Updated"
        assert active_user.phone == "+50998765432"

    def test_users_profile_endpoint_alias(self, authenticated_client, active_user):
        users_profile_url = "/api/v1/users/profile/"
        response = authenticated_client.get(users_profile_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert response.data["data"]["email"] == active_user.email

    def test_update_profile_with_avatar(self, authenticated_client, active_user):
        import io
        from PIL import Image

        file_obj = io.BytesIO()
        image = Image.new("RGBA", size=(100, 100), color=(255, 0, 0))
        image.save(file_obj, "png")
        file_obj.seek(0)
        file_obj.name = "avatar.png"

        response = authenticated_client.patch(
            self.me_url,
            data={"avatar": file_obj, "full_name": "Avatar User"},
            format="multipart",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["avatar"] is not None
        assert "avatar" in response.data["data"]["avatar"]
        assert response.data["data"]["full_name"] == "Avatar User"

    def test_change_password_success(self, authenticated_client, active_user):
        payload = {
            "current_password": "ValidPassword123!",
            "new_password": "BrandNewPassword999!",
            "confirm_password": "BrandNewPassword999!",
        }
        response = authenticated_client.post(self.change_pw_url, data=payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True

        active_user.refresh_from_db()
        assert active_user.check_password("BrandNewPassword999!")

    def test_change_password_invalid_current_password(self, authenticated_client):
        payload = {
            "current_password": "WrongCurrentPassword!",
            "new_password": "BrandNewPassword999!",
            "confirm_password": "BrandNewPassword999!",
        }
        response = authenticated_client.post(self.change_pw_url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "current_password" in response.data["error"]["details"]

    def test_change_password_complexity_failure(self, authenticated_client):
        # Missing number
        payload = {
            "current_password": "ValidPassword123!",
            "new_password": "NoNumberPassword!",
            "confirm_password": "NoNumberPassword!",
        }
        response = authenticated_client.post(self.change_pw_url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "new_password" in response.data["error"]["details"]

    def test_logout_blacklists_refresh_token(self, authenticated_client, active_user):
        refresh = RefreshToken.for_user(active_user)
        refresh_str = str(refresh)

        response = authenticated_client.post(self.logout_url, data={"refresh": refresh_str}, format="json")
        assert response.status_code == status.HTTP_200_OK

        # Trying to use blacklisted token to refresh fails
        token_refresh_url = "/api/v1/auth/token/refresh/"
        refresh_res = authenticated_client.post(token_refresh_url, data={"refresh": refresh_str}, format="json")
        assert refresh_res.status_code == status.HTTP_401_UNAUTHORIZED
