from decimal import Decimal
from rest_framework import serializers
from apps.users.models import User, MerchantStore, RiderProfile
from apps.merchant.models import Order, OrderItem, Product


def format_htg(amount: Decimal | float | int | None) -> str:
    """Format decimal or integer into Haitian Gourde string (e.g., '124,800 HTG')."""
    if amount is None:
        amount = 0
    val = int(amount)
    return f"{val:,} HTG"


class AdminCustomerListSerializer(serializers.ModelSerializer):
    display_id = serializers.SerializerMethodField()
    name = serializers.CharField(source="full_name")
    orders = serializers.SerializerMethodField()
    spent = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    joined = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "display_id",
            "name",
            "phone",
            "email",
            "joined",
            "orders",
            "spent",
            "status",
            "is_banned",
            "ban_reason",
            "is_active",
            "is_verified",
        ]

    def get_display_id(self, obj) -> str:
        return f"CUS-{str(obj.id)[:8].upper()}"

    def get_orders(self, obj) -> int:
        return getattr(obj, "total_orders_count", obj.customer_orders.count())

    def get_spent(self, obj) -> str:
        total = getattr(obj, "total_spent_amount", None)
        if total is None:
            orders = obj.customer_orders.exclude(status="cancelled")
            total = sum((o.total_amount for o in orders), Decimal("0.00"))
        return format_htg(total)

    def get_status(self, obj) -> str:
        if obj.is_banned or not obj.is_active:
            return "Banned"
        return "Active"

    def get_joined(self, obj) -> str:
        return obj.date_joined.strftime("%Y-%m-%d") if obj.date_joined else ""


class AdminCustomerDetailSerializer(AdminCustomerListSerializer):
    addresses = serializers.SerializerMethodField()
    recent_orders = serializers.SerializerMethodField()

    class Meta(AdminCustomerListSerializer.Meta):
        fields = AdminCustomerListSerializer.Meta.fields + [
            "avatar",
            "addresses",
            "recent_orders",
        ]

    def get_addresses(self, obj):
        return [
            {
                "id": str(addr.id),
                "label": addr.label,
                "street": addr.street_address,
                "city": addr.city,
                "details": addr.details,
                "is_default": addr.is_default,
            }
            for addr in obj.customer_addresses.all()
        ]

    def get_recent_orders(self, obj):
        orders = obj.customer_orders.select_related("store").order_by("-created_at")[:20]
        return [
            {
                "id": order.order_number,
                "date": order.created_at.strftime("%Y-%m-%d") if order.created_at else "",
                "store": order.store.name if order.store else "Direct Order",
                "amount": format_htg(order.total_amount),
                "status": order.status.replace("_", " ").title(),
            }
            for order in orders
        ]


class AdminMerchantListSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    shopName = serializers.CharField(source="name")
    owner = serializers.CharField(source="owner.full_name")
    email = serializers.CharField(source="owner.email")
    phone = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    totalSales = serializers.SerializerMethodField()
    joined = serializers.SerializerMethodField()
    walletBalance = serializers.SerializerMethodField()
    kyc = serializers.SerializerMethodField()
    rejectionReason = serializers.CharField(source="rejection_reason", default="")
    suspensionReason = serializers.CharField(source="suspension_reason", default="")
    raw_id = serializers.CharField(source="id", read_only=True)

    class Meta:
        model = MerchantStore
        fields = [
            "id",
            "raw_id",
            "shopName",
            "owner",
            "email",
            "phone",
            "category",
            "status",
            "products",
            "totalSales",
            "joined",
            "walletBalance",
            "kyc",
            "rejection_reason",
            "suspension_reason",
            "rejectionReason",
            "suspensionReason",
        ]

    def get_id(self, obj) -> str:
        return f"MCH-{str(obj.id)[:8].upper()}"

    def get_phone(self, obj) -> str:
        return obj.phone or obj.owner.phone or ""

    def get_products(self, obj) -> int:
        return obj.products.count()

    def get_totalSales(self, obj) -> str:
        delivered_orders = obj.orders.filter(status="delivered")
        total = sum((o.total_amount for o in delivered_orders), Decimal("0.00"))
        return format_htg(total)

    def get_joined(self, obj) -> str:
        return obj.created_at.strftime("%Y-%m-%d") if obj.created_at else ""

    def get_walletBalance(self, obj) -> str:
        return format_htg(obj.wallet_balance)

    def get_kyc(self, obj) -> dict:
        return {
            "businessName": obj.name,
            "businessType": obj.business_type or "Retail Store",
            "regNumber": obj.reg_number or f"HT-PAT-2024-{str(obj.id)[:4].upper()}",
            "address": obj.address or "Delmas, Port-au-Prince",
            "city": obj.city or "Port-au-Prince",
            "zip": obj.zip_code or "HT-6110",
            "ownerName": obj.owner.full_name,
            "ownerAddress": obj.address or "Port-au-Prince, Haiti",
            "ownerPhone": obj.owner.phone,
            "ownerEmail": obj.owner.email,
        }


class AdminMerchantDetailSerializer(AdminMerchantListSerializer):
    recentOrders = serializers.SerializerMethodField()
    payoutHistory = serializers.SerializerMethodField()

    class Meta(AdminMerchantListSerializer.Meta):
        fields = AdminMerchantListSerializer.Meta.fields + [
            "recentOrders",
            "payoutHistory",
            "bank_name",
            "account_number",
            "account_holder",
            "routing_number",
            "rating",
            "reviews_count",
            "is_open",
            "is_verified",
        ]

    def get_recentOrders(self, obj):
        return [
            {
                "id": o.order_number,
                "amount": format_htg(o.total_amount),
                "status": o.status.replace("_", " ").title(),
            }
            for o in obj.orders.order_by("-created_at")[:8]
        ]

    def get_payoutHistory(self, obj):
        payouts = getattr(obj, "payouts", None)
        if payouts and hasattr(payouts, "all") and payouts.exists():
            return [
                {
                    "date": p.created_at.strftime("%b %d, %Y") if p.created_at else "",
                    "amount": format_htg(p.amount),
                    "status": getattr(p, "status", "Released").title(),
                }
                for p in payouts.order_by("-created_at")[:5]
            ]
        return []


class AdminRiderListSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    raw_id = serializers.CharField(source="id", read_only=True)
    name = serializers.CharField(source="user.full_name")
    phone = serializers.CharField(source="user.phone")
    vehicle = serializers.CharField(source="vehicle_type")
    deliveries = serializers.IntegerField(source="deliveries_count")
    earnings = serializers.SerializerMethodField()
    joined = serializers.SerializerMethodField()
    walletBalance = serializers.SerializerMethodField()
    kyc = serializers.SerializerMethodField()
    suspensionReason = serializers.CharField(source="suspension_reason", default="")
    rejectionReason = serializers.CharField(source="rejection_reason", default="")

    class Meta:
        model = RiderProfile
        fields = [
            "id",
            "raw_id",
            "name",
            "phone",
            "zone",
            "vehicle",
            "status",
            "deliveries",
            "earnings",
            "joined",
            "walletBalance",
            "kyc",
            "suspension_reason",
            "rejection_reason",
            "suspensionReason",
            "rejectionReason",
        ]

    def get_id(self, obj) -> str:
        return f"RDR-{str(obj.id)[:8].upper()}"

    def get_earnings(self, obj) -> str:
        return format_htg(obj.total_earnings)

    def get_joined(self, obj) -> str:
        return obj.created_at.strftime("%Y-%m-%d") if obj.created_at else ""

    def get_walletBalance(self, obj) -> str:
        return format_htg(obj.wallet_balance)

    def get_kyc(self, obj) -> dict:
        date_str = (
            obj.submission_date.strftime("%Y-%m-%d")
            if obj.submission_date
            else (obj.created_at.strftime("%Y-%m-%d") if obj.created_at else "2024-05-30")
        )
        return {
            "nidFront": obj.nid_front or "/file.svg",
            "nidBack": obj.nid_back or "/file.svg",
            "licenseFront": obj.license_front or "/file.svg",
            "licenseBack": obj.license_back or "/file.svg",
            "vehicleType": obj.vehicle_type,
            "numberPlate": obj.number_plate or f"HT-2024-{str(obj.id)[:4].upper()}",
            "frontFacePhoto": obj.front_face_photo or "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=300&auto=format&fit=crop&q=80",
            "leftFacePhoto": obj.left_face_photo or "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=300&auto=format&fit=crop&q=80",
            "rightFacePhoto": obj.right_face_photo or "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=300&auto=format&fit=crop&q=80",
            "submissionDate": date_str,
            "submissionId": obj.submission_id or f"SUB-{str(obj.id)[:6].upper()}",
        }


class AdminRiderDetailSerializer(AdminRiderListSerializer):
    recentDeliveries = serializers.SerializerMethodField()

    class Meta(AdminRiderListSerializer.Meta):
        fields = AdminRiderListSerializer.Meta.fields + [
            "recentDeliveries",
        ]

    def get_recentDeliveries(self, obj):
        orders = Order.objects.filter(rider=obj).select_related("store").order_by("-created_at")[:8]
        status_map = {
            Order.STATUS_DELIVERED: "Completed",
            Order.STATUS_CANCELLED: "Failed",
            Order.STATUS_ON_THE_WAY: "In Transit",
            Order.STATUS_READY: "In Transit",
            Order.STATUS_PREPARING: "In Transit",
            Order.STATUS_NEW: "In Transit",
        }
        res = []
        for o in orders:
            store_name = o.store.name if o.store else "TiBoutik Merchant"
            dest = o.delivery_address or "Customer Address"
            route = f"{store_name} → {dest[:25]}" if dest else store_name
            res.append({
                "id": o.order_number,
                "route": route,
                "status": status_map.get(o.status, "Completed"),
                "amount": format_htg(o.total_amount),
            })
        return res


class AdminProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "full_name",
            "role",
            "avatar",
            "is_staff",
            "is_superuser",
            "date_joined",
        ]
        read_only_fields = ["id", "role", "is_staff", "is_superuser", "date_joined"]


class AdminProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False, max_length=150)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False, max_length=30)
    current_password = serializers.CharField(required=False, write_only=True)
    new_password = serializers.CharField(required=False, write_only=True)

    def validate(self, attrs):
        user = self.context.get("request").user
        current_pw = attrs.get("current_password")
        new_pw = attrs.get("new_password")

        if new_pw:
            if not current_pw:
                raise serializers.ValidationError(
                    {"current_password": "Current password is required to set a new password."}
                )
            if not user.check_password(current_pw):
                raise serializers.ValidationError(
                    {"current_password": "The current password provided is incorrect."}
                )
            if len(new_pw) < 8:
                raise serializers.ValidationError(
                    {"new_password": "New password must be at least 8 characters long."}
                )

        return attrs


class AdminOrderItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="product_name", read_only=True)
    qty = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["name", "qty", "price"]

    def get_qty(self, obj):
        return f"{obj.quantity}x"

    def get_price(self, obj):
        try:
            val = float(obj.price)
            return f"{val:,.0f} HTG"
        except Exception:
            return f"{obj.price} HTG"


class AdminOrderSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    raw_id = serializers.UUIDField(source="id", read_only=True)
    customer = serializers.SerializerMethodField()
    merchant = serializers.SerializerMethodField()
    rider = serializers.SerializerMethodField()
    orderStatus = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    deliveryAddress = serializers.CharField(source="delivery_address")
    otpConfirmed = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    deliveryFee = serializers.SerializerMethodField()
    step = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "raw_id",
            "customer",
            "merchant",
            "rider",
            "orderStatus",
            "payment",
            "amount",
            "date",
            "deliveryAddress",
            "otpConfirmed",
            "subtotal",
            "deliveryFee",
            "step",
            "items",
        ]

    def get_id(self, obj):
        num = str(obj.order_number or "").strip()
        if not num.startswith("#"):
            return f"#{num}"
        return num

    def get_customer(self, obj):
        if obj.customer_name and obj.customer_name.strip():
            return obj.customer_name.strip()
        if obj.customer and obj.customer.full_name:
            return obj.customer.full_name
        return "Customer"

    def get_merchant(self, obj):
        if obj.store and obj.store.name:
            return obj.store.name
        return "Direct Merchant"

    def get_rider(self, obj):
        if obj.rider and obj.rider.user:
            return obj.rider.user.full_name
        return "Unassigned"

    def get_orderStatus(self, obj):
        status_map = {
            Order.STATUS_NEW: "Placed",
            Order.STATUS_PREPARING: "Accepted",
            Order.STATUS_READY: "Picked Up",
            Order.STATUS_ON_THE_WAY: "Picked Up",
            Order.STATUS_DELIVERED: "Delivered",
            Order.STATUS_CANCELLED: "Cancelled",
        }
        return status_map.get(obj.status, "Placed")

    def get_payment(self, obj):
        if obj.status == Order.STATUS_DELIVERED:
            return "Paid"
        if obj.status == Order.STATUS_CANCELLED:
            return "Refunded"
        if obj.payment_method == "Card":
            return "Paid"
        return "Held"

    def get_amount(self, obj):
        try:
            val = float(obj.total_amount)
            return f"{val:,.0f} HTG"
        except Exception:
            return f"{obj.total_amount} HTG"

    def get_date(self, obj):
        return obj.created_at.strftime("%Y-%m-%d")

    def get_otpConfirmed(self, obj):
        if obj.status == Order.STATUS_CANCELLED:
            return "No"
        return "Yes ✓" if obj.delivery_step >= 3 or obj.status == Order.STATUS_DELIVERED else "Pending"

    def get_subtotal(self, obj):
        try:
            val = float(obj.subtotal)
            return f"{val:,.0f} HTG"
        except Exception:
            return f"{obj.subtotal} HTG"

    def get_deliveryFee(self, obj):
        try:
            val = float(obj.delivery_fee)
            return f"{val:,.0f} HTG"
        except Exception:
            return f"{obj.delivery_fee} HTG"

    def get_step(self, obj):
        if obj.status == Order.STATUS_CANCELLED:
            return 0
        if obj.status == Order.STATUS_DELIVERED:
            return 5
        if obj.delivery_step == 2 or obj.status == Order.STATUS_ON_THE_WAY:
            return 4
        if obj.delivery_step == 1 or obj.status == Order.STATUS_READY:
            return 3
        if obj.status == Order.STATUS_PREPARING:
            return 2
        return 1

    def get_items(self, obj):
        items = obj.items.all()
        if items.exists():
            return AdminOrderItemSerializer(items, many=True).data
        return [
            {
                "name": f"Articles {obj.order_number}",
                "qty": "1x",
                "price": self.get_subtotal(obj),
            }
        ]


