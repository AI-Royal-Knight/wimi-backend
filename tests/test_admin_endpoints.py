import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.urls import reverse
from apps.users.models import User, MerchantStore, RiderProfile


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    user = User.objects.create(
        email="test_admin@wimi.com",
        phone="+50937001122",
        full_name="Admin QA",
        role=User.ROLE_ADMIN,
        is_staff=True,
        is_superuser=True,
        is_active=True,
        is_verified=True,
    )
    user.set_password("AdminPass123!")
    user.save()
    return user


@pytest.fixture
def merchant_user(db):
    user = User.objects.create(
        email="merchant_qa@wimi.com",
        phone="+50937003344",
        full_name="Merchant QA",
        role=User.ROLE_MERCHANT,
        is_active=True,
        is_verified=True,
    )
    user.set_password("MerchantPass123!")
    user.save()
    MerchantStore.objects.create(
        owner=user,
        name="Merchant Store QA",
        category=MerchantStore.CATEGORY_GROCERY,
        status="Pending Verification",
    )
    return user


@pytest.fixture
def customer_user(db):
    user = User.objects.create(
        email="customer_qa@wimi.com",
        phone="+50937005566",
        full_name="Customer QA",
        role=User.ROLE_CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    user.set_password("CustomerPass123!")
    user.save()
    return user


@pytest.fixture
def rider_user(db):
    user = User.objects.create(
        email="rider_qa@wimi.com",
        phone="+50937007788",
        full_name="Rider QA",
        role=User.ROLE_RIDER,
        is_active=True,
        is_verified=True,
    )
    user.set_password("RiderPass123!")
    user.save()
    RiderProfile.objects.create(
        user=user,
        vehicle_type="Motorcycle",
        zone="Delmas",
        status="Pending Verification",
    )
    return user


@pytest.mark.django_db
class TestAdminEndpoints:
    def test_unauthenticated_access_denied(self, api_client):
        res = api_client.get("/api/v1/admin/stats/")
        assert res.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_non_admin_access_forbidden(self, api_client, customer_user):
        api_client.force_authenticate(user=customer_user)
        res = api_client.get("/api/v1/admin/stats/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_stats(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        res = api_client.get("/api/v1/admin/stats/")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["success"] is True
        assert "totalCustomers" in res.data["data"]
        assert "totalMerchants" in res.data["data"]

    def test_admin_customers_list_and_ban(self, api_client, admin_user, customer_user):
        api_client.force_authenticate(user=admin_user)
        res = api_client.get("/api/v1/admin/customers/")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["success"] is True

        # Toggle ban
        ban_res = api_client.post(
            f"/api/v1/admin/customers/{customer_user.id}/toggle-ban/",
            data={"reason": "Terms violation"},
            format="json",
        )
        assert ban_res.status_code == status.HTTP_200_OK
        customer_user.refresh_from_db()
        assert customer_user.is_banned is True

    def test_admin_merchants_list_and_verify(self, api_client, admin_user, merchant_user):
        api_client.force_authenticate(user=admin_user)
        res = api_client.get("/api/v1/admin/merchants/")
        assert res.status_code == status.HTTP_200_OK

        store = merchant_user.merchant_store
        verify_res = api_client.post(f"/api/v1/admin/merchants/{store.id}/verify/")
        assert verify_res.status_code == status.HTTP_200_OK
        store.refresh_from_db()
        assert store.status == "Active"
        assert store.is_verified is True

    def test_admin_riders_list_and_verify(self, api_client, admin_user, rider_user):
        api_client.force_authenticate(user=admin_user)
        res = api_client.get("/api/v1/admin/riders/")
        assert res.status_code == status.HTTP_200_OK

        rider_profile = rider_user.rider_profile
        verify_res = api_client.post(f"/api/v1/admin/riders/{rider_profile.id}/verify/")
        assert verify_res.status_code == status.HTTP_200_OK
        rider_profile.refresh_from_db()
        assert rider_profile.status == "Active"
