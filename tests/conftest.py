import pytest
from django.core import mail
from rest_framework.test import APIClient
from apps.notifications.sms import LocMemSMSBackend
from .factories import UserFactory


@pytest.fixture(autouse=True)
def clean_notifications():
    """Clear in-memory email and SMS outboxes between tests."""
    mail.outbox.clear()
    LocMemSMSBackend.clear()
    yield
    mail.outbox.clear()
    LocMemSMSBackend.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def active_user(db):
    return UserFactory(
        email="jean.laurent@email.com",
        phone="+50912345678",
        full_name="Jean-Pierre Laurent",
        is_active=True,
        is_verified=True,
        password="ValidPassword123!",
    )


@pytest.fixture
def unverified_user(db):
    return UserFactory(
        email="unverified@email.com",
        phone="+50987654321",
        full_name="Unverified User",
        is_active=False,
        is_verified=False,
        password="ValidPassword123!",
    )


@pytest.fixture
def authenticated_client(api_client, active_user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(active_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client
