import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from apps.users.models import MerchantStore, User


class Product(models.Model):
    STATUS_ACTIVE = "Active"
    STATUS_LOW_STOCK = "Low Stock"
    STATUS_OUT_OF_STOCK = "Out of Stock"
    STATUS_ARCHIVED = "Archived"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_LOW_STOCK, "Low Stock"),
        (STATUS_OUT_OF_STOCK, "Out of Stock"),
        (STATUS_ARCHIVED, "Archived"),
    )

    CATEGORY_CHOICES = (
        ("Vegetables", "Vegetables"),
        ("Fruits", "Fruits"),
        ("Dairy", "Dairy"),
        ("Meat", "Meat"),
        ("Bakery", "Bakery"),
        ("Grains", "Grains"),
        ("Beverages", "Beverages"),
        ("Pharmacy", "Pharmacy & Health"),
        ("Health", "Health & Wellness"),
        ("Restaurant", "Restaurant & Food"),
        ("Boutique", "Boutique & Fashion"),
        ("Electronics", "Electronics"),
        ("Grocery", "Grocery"),
        ("Other", "Other"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        MerchantStore,
        on_delete=models.CASCADE,
        related_name="products",
    )
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default="Vegetables")
    sku = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField(default=0)
    min_stock = models.IntegerField(default=50)
    max_stock = models.IntegerField(default=200)
    sold_count = models.IntegerField(default=0)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    image_url_fallback = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "merchant_products"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["store", "status"]),
            models.Index(fields=["store", "category"]),
            models.Index(fields=["store", "sku"]),
        ]

    def recalculate_status(self):
        if self.status == self.STATUS_ARCHIVED:
            return
        if self.stock <= 0:
            self.status = self.STATUS_OUT_OF_STOCK
        elif self.stock <= self.min_stock:
            self.status = self.STATUS_LOW_STOCK
        else:
            self.status = self.STATUS_ACTIVE

    def save(self, *args, **kwargs):
        self.recalculate_status()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.sku}) - {self.store.name}"


class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.CharField(max_length=50, blank=True, default="")
    color = models.CharField(max_length=50, blank=True, default="")
    stock = models.IntegerField(default=0)
    sku = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "merchant_product_variants"

    def __str__(self):
        return f"Variant of {self.product.name}: {self.size} / {self.color}"


class Order(models.Model):
    STATUS_NEW = "new"
    STATUS_PREPARING = "preparing"
    STATUS_READY = "ready"
    STATUS_ON_THE_WAY = "on_the_way"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_NEW, "New Order"),
        (STATUS_PREPARING, "Preparing"),
        (STATUS_READY, "Ready"),
        (STATUS_ON_THE_WAY, "On The Way"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    PAYMENT_CASH = "Cash on Delivery"
    PAYMENT_CARD = "Card"
    PAYMENT_MOBILE_MONEY = "Mobile Money"

    PAYMENT_CHOICES = (
        (PAYMENT_CASH, "Cash on Delivery"),
        (PAYMENT_CARD, "Card"),
        (PAYMENT_MOBILE_MONEY, "Mobile Money"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        MerchantStore,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    customer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_orders",
    )
    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField(blank=True, default="")
    customer_phone = models.CharField(max_length=50, blank=True, default="")
    customer_avatar = models.CharField(max_length=500, blank=True, default="")
    delivery_address = models.CharField(max_length=300, default="")
    delivery_method = models.CharField(max_length=100, default="Standard Delivery")
    estimated_delivery = models.CharField(max_length=100, blank=True, default="")

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    payment_method = models.CharField(max_length=50, choices=PAYMENT_CHOICES, default=PAYMENT_CASH)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)
    rejection_reason = models.TextField(blank=True, default="")

    rider = models.ForeignKey(
        "users.RiderProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
    )
    otp_code = models.CharField(max_length=10, blank=True, default="4281")
    delivery_step = models.IntegerField(default=0)

    # GPS Coordinates for Real-Time Delivery Tracking
    delivery_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, default=18.548200)
    delivery_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, default=-72.325400)
    rider_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    rider_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "merchant_orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["store", "status"]),
            models.Index(fields=["store", "created_at"]),
        ]

    def __str__(self):
        return f"{self.order_number} ({self.status}) - {self.customer_name}"


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    image_url = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "merchant_order_items"

    def __str__(self):
        return f"{self.product_name} x {self.quantity} for {self.order.order_number}"


class PayoutRequest(models.Model):
    STATUS_PENDING = "Pending"
    STATUS_PROCESSING = "Processing"
    STATUS_COMPLETED = "Completed"
    STATUS_REJECTED = "Rejected"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_REJECTED, "Rejected"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        MerchantStore,
        on_delete=models.CASCADE,
        related_name="payout_requests",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=100, default="Bank Transfer")
    bank_name = models.CharField(max_length=150, default="")
    account_number = models.CharField(max_length=100, default="")
    account_holder = models.CharField(max_length=150, default="")
    routing_number = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_PENDING)
    notes = models.TextField(blank=True, default="")
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "merchant_payout_requests"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Payout {self.amount} ({self.status}) - {self.store.name}"


class Transaction(models.Model):
    TYPE_EARNING = "earning"
    TYPE_WITHDRAWAL = "withdrawal"

    TYPE_CHOICES = (
        (TYPE_EARNING, "Earning"),
        (TYPE_WITHDRAWAL, "Withdrawal"),
    )

    STATUS_COMPLETED = "Completed"
    STATUS_PENDING = "Pending"
    STATUS_FAILED = "Failed"

    STATUS_CHOICES = (
        (STATUS_COMPLETED, "Completed"),
        (STATUS_PENDING, "Pending"),
        (STATUS_FAILED, "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        MerchantStore,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_id = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "merchant_transactions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.transaction_id} ({self.type} - {self.amount}) - {self.store.name}"


class OrderChatMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="chat_messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_chat_messages")
    sender_role = models.CharField(max_length=50, default="customer")
    sender_name = models.CharField(max_length=150, blank=True, default="")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_chat_messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"Chat on {self.order.order_number} by {self.sender_name} ({self.sender_role})"


