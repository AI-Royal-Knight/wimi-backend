from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
from apps.core.utils import normalize_email, normalize_phone


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames.
    """

    def create_user(self, email: str, password: str = None, **extra_fields):
        if not email:
            raise ValueError(_("An email address must be provided."))

        email = normalize_email(email)
        if "phone" in extra_fields and extra_fields["phone"]:
            extra_fields["phone"] = normalize_phone(extra_fields["phone"])

        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        # Default is_active is False until OTP verification is completed,
        # unless explicitly passed (e.g. for superusers or seeded accounts)
        extra_fields.setdefault("is_active", False)

        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str = None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("terms_accepted", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(email, password, **extra_fields)
