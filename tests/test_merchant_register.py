import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from apps.users.models import MerchantStore

User = get_user_model()


@pytest.mark.django_db
class TestMerchantRegistration:
    url = "/api/v1/auth/merchant/register/"
    login_url = "/api/v1/auth/login/"

    def test_merchant_register_success(self, api_client):
        payload = {
            "full_name": "Marcus Aurelius",
            "email": "marcus.store@tiboutik.com",
            "phone": "+509 3344 5566",
            "password": "StorePassword123!",
            "store_name": "Marcus Organic Groceries",
            "category": "Grocery",
            "store_address": "12 Boulevard Jean-Jacques Dessalines, Port-au-Prince",
            "store_description": "Finest fresh organic produce and Caribbean groceries.",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["success"] is True
        assert "access" in response.data["data"]
        assert "refresh" in response.data["data"]
        assert response.data["data"]["user"]["role"] == User.ROLE_MERCHANT
        assert response.data["data"]["store"]["name"] == "Marcus Organic Groceries"
        assert response.data["data"]["store"]["category"] == "Grocery"

        # Verify DB records
        user = User.objects.get(email="marcus.store@tiboutik.com")
        assert user.role == User.ROLE_MERCHANT
        assert user.is_active is True
        assert user.is_verified is True
        assert user.full_name == "Marcus Aurelius"

        store = MerchantStore.objects.get(owner=user)
        assert store.name == "Marcus Organic Groceries"
        assert store.category == "Grocery"
        assert store.address == "12 Boulevard Jean-Jacques Dessalines, Port-au-Prince"
        assert store.is_verified is True

    def test_merchant_register_duplicate_email_fails(self, api_client, active_user):
        payload = {
            "full_name": "New Owner",
            "email": active_user.email,
            "phone": "+509 9988 7766",
            "password": "StorePassword123!",
            "store_name": "New Store",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False
        assert "email" in response.data["error"]["details"]

    def test_merchant_register_duplicate_phone_fails(self, api_client, active_user):
        payload = {
            "full_name": "New Owner",
            "email": "brandnew@tiboutik.com",
            "phone": active_user.phone,
            "password": "StorePassword123!",
            "store_name": "New Store",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["success"] is False
        assert "phone" in response.data["error"]["details"]

    def test_merchant_register_short_store_name_fails(self, api_client):
        payload = {
            "full_name": "Owner Name",
            "email": "store@tiboutik.com",
            "phone": "+509 1122 3344",
            "password": "StorePassword123!",
            "store_name": "M",
            "terms_accepted": True,
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "store_name" in response.data["error"]["details"]

    def test_merchant_register_terms_not_accepted_fails(self, api_client):
        payload = {
            "full_name": "Owner Name",
            "email": "store@tiboutik.com",
            "phone": "+509 1122 3344",
            "password": "StorePassword123!",
            "store_name": "My Great Store",
            "terms_accepted": False,
        }
        response = api_client.post(self.url, data=payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "terms_accepted" in response.data["error"]["details"]

    def test_registered_merchant_can_log_in_via_login_api(self, api_client):
        # 1. Register merchant
        reg_payload = {
            "full_name": "Sophie Merchant",
            "email": "sophie.bakery@tiboutik.com",
            "phone": "+509 4455 6677",
            "password": "BakeryPassword123!",
            "store_name": "Sophie Delice Bakery",
            "category": "Bakery",
            "terms_accepted": True,
        }
        reg_res = api_client.post(self.url, data=reg_payload, format="json")
        assert reg_res.status_code == status.HTTP_201_CREATED

        # 2. Log in using email
        login_res = api_client.post(
            self.login_url,
            data={"identifier": "sophie.bakery@tiboutik.com", "password": "BakeryPassword123!"},
            format="json",
        )
        assert login_res.status_code == status.HTTP_200_OK
        assert login_res.data["success"] is True
        assert login_res.data["data"]["user"]["role"] == User.ROLE_MERCHANT
        assert login_res.data["data"]["user"]["store"]["name"] == "Sophie Delice Bakery"

        # 3. Log in using phone
        login_phone_res = api_client.post(
            self.login_url,
            data={"identifier": "+509 4455 6677", "password": "BakeryPassword123!"},
            format="json",
        )
        assert login_phone_res.status_code == status.HTTP_200_OK
        assert login_phone_res.data["success"] is True
