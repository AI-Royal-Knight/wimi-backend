import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from apps.core.utils import normalize_email, normalize_phone
from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for TiBoutik / Wimi.
    Email is the primary login credential, and phone is a required verified attribute.
    """
    ROLE_CUSTOMER = "customer"
    ROLE_MERCHANT = "merchant"
    ROLE_RIDER = "rider"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = (
        (ROLE_CUSTOMER, "Customer"),
        (ROLE_MERCHANT, "Merchant"),
        (ROLE_RIDER, "Rider"),
        (ROLE_ADMIN, "Admin"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True, max_length=255)
    phone = models.CharField(unique=True, db_index=True, max_length=30)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CUSTOMER, db_index=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    # State & Verification
    is_active = models.BooleanField(
        default=False,
        help_text="Designates whether this user should be treated as active. "
                  "Unselect this instead of deleting accounts. New signups are inactive until OTP verified.",
    )
    is_banned = models.BooleanField(
        default=False,
        help_text="Designates whether this user account has been banned by an administrator.",
    )
    ban_reason = models.CharField(max_length=255, blank=True, default="")
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates whether the user can log into the admin site.",
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Designates whether the user has completed email/phone OTP verification.",
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)

    # Legal & Compliance
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    # Audit Timestamps
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name", "phone"]

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["email"], name="idx_user_email"),
            models.Index(fields=["phone"], name="idx_user_phone"),
            models.Index(fields=["role"], name="idx_user_role"),
            models.Index(fields=["is_active", "is_verified"], name="idx_user_status"),
        ]

    def clean(self):
        super().clean()
        if self.email:
            self.email = normalize_email(self.email)
        if self.phone:
            self.phone = normalize_phone(self.phone)
        if self.is_banned:
            self.is_active = False
        if self.is_superuser or self.is_staff:
            if self.role == self.ROLE_CUSTOMER:
                self.role = self.ROLE_ADMIN

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def mark_verified(self, channel: str = "email"):
        """Activates user and records verification timestamp."""
        now = timezone.now()
        self.is_active = True
        self.is_verified = True
        if channel == "email":
            self.email_verified_at = now
        elif channel == "phone":
            self.phone_verified_at = now
        self.save(update_fields=["is_active", "is_verified", "email_verified_at", "phone_verified_at", "updated_at"])

    def __str__(self):
        return f"{self.full_name} <{self.email}> ({self.role})"


class MerchantStore(models.Model):
    """
    Physical or online merchant store registered on TiBoutik marketplace.
    """
    CATEGORY_GROCERY = "Grocery"
    CATEGORY_BAKERY = "Bakery"
    CATEGORY_RESTAURANT = "Restaurant"
    CATEGORY_PHARMACY = "Pharmacy"
    CATEGORY_BOUTIQUE = "Boutique"
    CATEGORY_SUPERMARKET = "Supermarket"
    CATEGORY_OTHER = "Other"

    CATEGORY_CHOICES = (
        (CATEGORY_GROCERY, "Grocery & Fresh Produce"),
        (CATEGORY_BAKERY, "Bakery & Pastries"),
        (CATEGORY_RESTAURANT, "Restaurant & Food"),
        (CATEGORY_PHARMACY, "Pharmacy & Health"),
        (CATEGORY_BOUTIQUE, "Fashion & Boutique"),
        (CATEGORY_SUPERMARKET, "Supermarket"),
        (CATEGORY_OTHER, "General Store / Other"),
    )

    STATUS_ACTIVE = "Active"
    STATUS_PENDING = "Pending Verification"
    STATUS_SUSPENDED = "Suspended"
    STATUS_REJECTED = "Rejected"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_PENDING, "Pending Verification"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_REJECTED, "Rejected"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="merchant_store",
    )
    name = models.CharField(max_length=200, help_text="Public store name")
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default=CATEGORY_GROCERY)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    business_type = models.CharField(max_length=100, blank=True, default="Retail")
    reg_number = models.CharField(max_length=100, blank=True, default="")
    address = models.CharField(max_length=300, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="Port-au-Prince")
    zip_code = models.CharField(max_length=20, blank=True, default="")
    description = models.TextField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    logo = models.ImageField(upload_to="stores/logos/", null=True, blank=True)
    banner = models.ImageField(upload_to="stores/banners/", null=True, blank=True)
    is_verified = models.BooleanField(default=True, help_text="Verified merchant store status")
    is_open = models.BooleanField(default=True, help_text="Whether store is accepting orders")
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    reviews_count = models.PositiveIntegerField(default=0)
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Live Rider GPS Coordinates
    current_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, default=18.543700)
    current_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, default=-72.330900)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    suspension_reason = models.TextField(blank=True, default="")

    # Store Geolocation Coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, default=18.539200)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, default=-72.336400)

    # Bank & Payout Information
    bank_name = models.CharField(max_length=150, blank=True, default="Chase Bank")
    account_number = models.CharField(max_length=100, blank=True, default="4532")
    account_holder = models.CharField(max_length=150, blank=True, default="")
    routing_number = models.CharField(max_length=100, blank=True, default="021000021")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "merchant_stores"
        verbose_name = "Merchant Store"
        verbose_name_plural = "Merchant Stores"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - Owner: {self.owner.full_name}"


class RiderProfile(models.Model):
    """
    Rider profile for delivery fleet and KYC verification.
    """
    STATUS_ACTIVE = "Active"
    STATUS_ON_DELIVERY = "On Delivery"
    STATUS_OFFLINE = "Offline"
    STATUS_PENDING = "Pending Verification"
    STATUS_SUSPENDED = "Suspended"
    STATUS_REJECTED = "Rejected"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_ON_DELIVERY, "On Delivery"),
        (STATUS_OFFLINE, "Offline"),
        (STATUS_PENDING, "Pending Verification"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_REJECTED, "Rejected"),
    )

    VEHICLE_MOTORCYCLE = "Motorcycle"
    VEHICLE_BICYCLE = "Bicycle"
    VEHICLE_CHOICES = (
        (VEHICLE_MOTORCYCLE, "Motorcycle"),
        (VEHICLE_BICYCLE, "Bicycle"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="rider_profile",
    )
    vehicle_type = models.CharField(max_length=50, choices=VEHICLE_CHOICES, default=VEHICLE_MOTORCYCLE)
    number_plate = models.CharField(max_length=50, blank=True, default="")
    zone = models.CharField(max_length=100, default="Port-au-Prince Centre")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    deliveries_count = models.PositiveIntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Live Rider GPS Coordinates
    current_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, default=18.543700)
    current_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, default=-72.330900)
    location_updated_at = models.DateTimeField(null=True, blank=True)

    # KYC Documents & Biometric/Face Photos
    nid_front = models.CharField(max_length=500, blank=True, default="")
    nid_back = models.CharField(max_length=500, blank=True, default="")
    license_front = models.CharField(max_length=500, blank=True, default="")
    license_back = models.CharField(max_length=500, blank=True, default="")
    front_face_photo = models.CharField(max_length=500, blank=True, default="")
    left_face_photo = models.CharField(max_length=500, blank=True, default="")
    right_face_photo = models.CharField(max_length=500, blank=True, default="")
    submission_date = models.DateField(null=True, blank=True)
    submission_id = models.CharField(max_length=100, blank=True, default="")

    suspension_reason = models.TextField(blank=True, default="")
    rejection_reason = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rider_profiles"
        verbose_name = "Rider Profile"
        verbose_name_plural = "Rider Profiles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Rider: {self.user.full_name} ({self.vehicle_type} - {self.status})"
