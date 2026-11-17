from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from apps.authentication.services import AuthService


class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_creates_unverified_user_and_otp(self):
        user, otp = AuthService.signup(
            full_name="Jean Baptiste",
            email="jean.baptiste@example.com",
            phone="+50931234567",
            password="SecurePassword123!",
            terms_accepted=True,
        )
        self.assertFalse(user.is_verified)
        self.assertFalse(user.is_active)
        self.assertIsNotNone(otp)
        self.assertEqual(otp.destination, "jean.baptiste@example.com")

    def test_signup_collision_on_verified_user_returns_validation_error(self):
        User.objects.create_user(
            email="verified@example.com",
            phone="+50931111111",
            full_name="Verified User",
            password="Password123!",
            is_verified=True,
            is_active=True,
        )
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError) as ctx:
            AuthService.signup(
                full_name="Attempt Dup",
                email="verified@example.com",
                phone="+50932222222",
                password="Password123!",
                terms_accepted=True,
            )
        self.assertIn("email", ctx.exception.detail)

    def test_signup_cross_account_pending_collision(self):
        # User 1 has email1 and phone1
        User.objects.create_user(
            email="user1@example.com",
            phone="+50933333331",
            full_name="User 1",
            password="Password123!",
            is_verified=False,
            is_active=False,
        )
        # User 2 has email2 and phone2
        User.objects.create_user(
            email="user2@example.com",
            phone="+50933333332",
            full_name="User 2",
            password="Password123!",
            is_verified=False,
            is_active=False,
        )
        # Signup with email1 and phone2
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError) as ctx:
            AuthService.signup(
                full_name="Mix User",
                email="user1@example.com",
                phone="+50933333332",
                password="Password123!",
                terms_accepted=True,
            )
        self.assertIn("email", ctx.exception.detail)

    def test_login_banned_user_returns_suspended_message(self):
        banned_user = User.objects.create_user(
            email="banned@example.com",
            phone="+50934444444",
            full_name="Banned Person",
            password="Password123!",
            is_verified=True,
            is_active=False,
            is_banned=True,
            ban_reason="Violation of platform terms",
        )
        from rest_framework.exceptions import AuthenticationFailed
        with self.assertRaises(AuthenticationFailed) as ctx:
            AuthService.login(identifier="banned@example.com", password="Password123!")
        self.assertIn("suspended", str(ctx.exception).lower())
        self.assertIn("Violation of platform terms", str(ctx.exception))

    def test_login_unverified_account_raises_unverified_error(self):
        User.objects.create_user(
            email="unverified@example.com",
            phone="+50935555555",
            full_name="Unverified User",
            password="Password123!",
            is_verified=False,
            is_active=False,
        )
        from apps.core.exceptions import UnverifiedAccountError
        with self.assertRaises(UnverifiedAccountError):
            AuthService.login(identifier="unverified@example.com", password="Password123!")

