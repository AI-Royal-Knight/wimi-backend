import uuid
from django.db import models
from apps.merchant.models import Product
from apps.users.models import MerchantStore, User


class CustomerAddress(models.Model):
    LABEL_HOME = "Home"
    LABEL_OFFICE = "Office"
    LABEL_OTHER = "Other"

    LABEL_CHOICES = (
        (LABEL_HOME, "Home"),
        (LABEL_OFFICE, "Office"),
        (LABEL_OTHER, "Other"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="customer_addresses",
    )
    label = models.CharField(max_length=50, choices=LABEL_CHOICES, default=LABEL_HOME)
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100, default="Port-au-Prince")
    details = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Apartment, floor, building number, nearby landmark",
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_addresses"
        ordering = ["-is_default", "-created_at"]
        indexes = [
            models.Index(fields=["user", "is_default"]),
        ]

    def save(self, *args, **kwargs):
        if self.is_default:
            # Unmark any existing default addresses for this user
            CustomerAddress.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        else:
            # If user has no other addresses, make this one default
            if not CustomerAddress.objects.filter(user=self.user).exclude(pk=self.pk).exists():
                self.is_default = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label} ({self.street_address}, {self.city}) - {self.user.full_name}"


class CustomerFavorite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="customer_favorites",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="favorited_by",
    )
    store = models.ForeignKey(
        MerchantStore,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customer_favorites"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_user_favorite_product",
                condition=models.Q(product__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["user", "store"],
                name="unique_user_favorite_store",
                condition=models.Q(store__isnull=False),
            ),
        ]

    def __str__(self):
        target = self.product.name if self.product else (self.store.name if self.store else "Unknown")
        return f"Favorite: {target} for {self.user.email}"


class PromoBanner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, default="Fresh Groceries Delivered Fast")
    subtitle = models.CharField(max_length=255, blank=True, default="Save up to 30% OFF")
    discount_text = models.CharField(max_length=100, blank=True, default="30% OFF")
    image_url = models.CharField(
        max_length=500,
        blank=True,
        default="https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80",
    )
    image = models.ImageField(upload_to="banners/", null=True, blank=True)
    link_category = models.CharField(max_length=100, blank=True, default="Grocery")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customer_promo_banners"
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"Banner: {self.title}"

