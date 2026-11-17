import decimal
from rest_framework import serializers
from apps.merchant.models import Order, OrderChatMessage, OrderItem, PayoutRequest
from apps.users.models import RiderProfile


class OrderChatMessageSerializer(serializers.ModelSerializer):
    formatted_time = serializers.SerializerMethodField()
    is_rider = serializers.SerializerMethodField()

    class Meta:
        model = OrderChatMessage
        fields = [
            "id",
            "sender_role",
            "sender_name",
            "message",
            "formatted_time",
            "is_rider",
            "created_at",
        ]

    def get_formatted_time(self, obj):
        return obj.created_at.strftime("%I:%M %p")

    def get_is_rider(self, obj):
        return obj.sender_role == "rider"


class RiderStatusSerializer(serializers.Serializer):
    is_online = serializers.BooleanField()


class RiderDeliveryItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="product_name", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "name",
            "product_name",
            "quantity",
            "price",
            "description",
            "image_url",
        ]


class RiderDeliverySerializer(serializers.ModelSerializer):
    items = RiderDeliveryItemSerializer(many=True, read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    store_address = serializers.CharField(source="store.address", read_only=True)
    store_phone = serializers.CharField(source="store.phone", read_only=True)
    earnings = serializers.DecimalField(source="delivery_fee", max_digits=10, decimal_places=2, read_only=True)
    rider_latitude = serializers.DecimalField(max_digits=10, decimal_places=6, read_only=True)
    rider_longitude = serializers.DecimalField(max_digits=10, decimal_places=6, read_only=True)
    store_latitude = serializers.DecimalField(source="store.latitude", max_digits=10, decimal_places=6, read_only=True)
    store_longitude = serializers.DecimalField(source="store.longitude", max_digits=10, decimal_places=6, read_only=True)
    delivery_latitude = serializers.DecimalField(max_digits=10, decimal_places=6, read_only=True)
    delivery_longitude = serializers.DecimalField(max_digits=10, decimal_places=6, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "delivery_step",
            "store_name",
            "store_address",
            "store_phone",
            "customer_name",
            "customer_phone",
            "delivery_address",
            "delivery_method",
            "payment_method",
            "subtotal",
            "delivery_fee",
            "total_amount",
            "earnings",
            "items",
            "rider_latitude",
            "rider_longitude",
            "store_latitude",
            "store_longitude",
            "delivery_latitude",
            "delivery_longitude",
            "created_at",
            "updated_at",
        ]


class RiderDeliveryUpdateSerializer(serializers.Serializer):
    order_id = serializers.UUIDField(required=True)
    delivery_step = serializers.IntegerField(min_value=0, max_value=3, required=True)


class RiderDeliveryOtpVerifySerializer(serializers.Serializer):
    order_id = serializers.UUIDField(required=True)
    otp_code = serializers.CharField(max_length=10, required=True)


class RiderEarningsSerializer(serializers.Serializer):
    wallet_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    deliveries_count = serializers.IntegerField()
    rating = serializers.FloatField(default=4.9)
    today_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    today_deliveries = serializers.IntegerField()


class RiderPayoutCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=decimal.Decimal("100.00"))
    phone = serializers.CharField(max_length=30, required=False, default="")
    notes = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
