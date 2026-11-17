import json
from decimal import Decimal
from rest_framework import serializers
from .models import Product, ProductVariant, Order, OrderItem, PayoutRequest, Transaction


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ["id", "size", "color", "stock", "sku"]


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "category",
            "sku",
            "description",
            "price",
            "discount_price",
            "stock",
            "min_stock",
            "max_stock",
            "sold_count",
            "status",
            "image",
            "variants",
            "created_at",
            "updated_at",
        ]

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return obj.image_url_fallback or ""


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    variants_data = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "sku",
            "description",
            "price",
            "discount_price",
            "stock",
            "min_stock",
            "max_stock",
            "status",
            "image",
            "image_url_fallback",
            "variants_data",
        ]
        extra_kwargs = {
            "image": {"required": False, "allow_null": True},
            "discount_price": {"required": False, "allow_null": True},
        }

    def create(self, validated_data):
        variants_json = validated_data.pop("variants_data", None)
        product = Product.objects.create(**validated_data)

        if variants_json:
            try:
                variants_list = json.loads(variants_json) if isinstance(variants_json, str) else variants_json
                if isinstance(variants_list, list):
                    for v in variants_list:
                        ProductVariant.objects.create(
                            product=product,
                            size=v.get("size", ""),
                            color=v.get("color", ""),
                            stock=int(v.get("stock", 0)),
                            sku=v.get("sku", ""),
                        )
            except Exception:
                pass

        return product

    def update(self, instance, validated_data):
        variants_json = validated_data.pop("variants_data", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if variants_json is not None:
            try:
                variants_list = json.loads(variants_json) if isinstance(variants_json, str) else variants_json
                if isinstance(variants_list, list):
                    instance.variants.all().delete()
                    for v in variants_list:
                        ProductVariant.objects.create(
                            product=instance,
                            size=v.get("size", ""),
                            color=v.get("color", ""),
                            stock=int(v.get("stock", 0)),
                            sku=v.get("sku", ""),
                        )
            except Exception:
                pass

        return instance


class StockAdjustmentSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["add", "remove", "set"])
    quantity = serializers.IntegerField(min_value=1)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "description",
            "price",
            "quantity",
            "image_url",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    items_summary = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_avatar",
            "delivery_address",
            "delivery_method",
            "estimated_delivery",
            "subtotal",
            "delivery_fee",
            "discount",
            "total_amount",
            "payment_method",
            "status",
            "status_display",
            "rejection_reason",
            "items",
            "items_count",
            "items_summary",
            "created_at",
            "updated_at",
        ]

    def get_items_count(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_items_summary(self, obj):
        items = list(obj.items.all())
        if not items:
            return ""
        return ", ".join([f"{item.product_name} ({item.quantity})" for item in items[:3]])


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[
        Order.STATUS_NEW,
        Order.STATUS_PREPARING,
        Order.STATUS_READY,
        Order.STATUS_ON_THE_WAY,
        Order.STATUS_DELIVERED,
        Order.STATUS_CANCELLED,
    ])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


class PayoutRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutRequest
        fields = [
            "id",
            "amount",
            "method",
            "bank_name",
            "account_number",
            "account_holder",
            "routing_number",
            "status",
            "notes",
            "requested_at",
            "processed_at",
        ]
        read_only_fields = ["id", "status", "requested_at", "processed_at"]

    def validate_amount(self, value):
        if value < Decimal("10.00"):
            raise serializers.ValidationError("Minimum payout amount is $10.00.")
        return value


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "transaction_id",
            "type",
            "description",
            "amount",
            "status",
            "created_at",
        ]

