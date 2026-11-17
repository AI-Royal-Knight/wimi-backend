from rest_framework import serializers
from apps.merchant.models import Order, OrderItem, Product
from apps.users.models import MerchantStore
from .models import CustomerAddress, CustomerFavorite, PromoBanner


class CustomerAddressSerializer(serializers.ModelSerializer):
    label = serializers.CharField(max_length=50, default="Home", required=False)

    class Meta:
        model = CustomerAddress
        fields = [
            "id",
            "label",
            "street_address",
            "city",
            "details",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        user = self.context["request"].user
        is_first = not CustomerAddress.objects.filter(user=user).exists()
        if validated_data.get("is_default") or is_first:
            validated_data["is_default"] = True
            CustomerAddress.objects.filter(user=user, is_default=True).update(is_default=False)
        return CustomerAddress.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        if validated_data.get("is_default") is True:
            CustomerAddress.objects.filter(user=instance.user, is_default=True).exclude(pk=instance.pk).update(is_default=False)
        return super().update(instance, validated_data)


class PromoBannerSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PromoBanner
        fields = [
            "id",
            "title",
            "subtitle",
            "discount_text",
            "image_url",
            "link_category",
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return obj.image_url


class CustomerProductSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="name", read_only=True)
    original_price = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    store_name = serializers.CharField(source="store.name", read_only=True)
    store_id = serializers.UUIDField(source="store.id", read_only=True)
    image_url = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "name",
            "store_id",
            "store_name",
            "category",
            "sku",
            "description",
            "price",
            "discount_price",
            "original_price",
            "discount",
            "stock",
            "sold_count",
            "rating",
            "unit",
            "image_url",
            "is_favorited",
            "status",
        ]

    def get_original_price(self, obj):
        if obj.discount_price and obj.discount_price > obj.price:
            return float(obj.discount_price)
        return float(obj.price)

    def get_discount(self, obj):
        if obj.discount_price and obj.discount_price > obj.price:
            diff = obj.discount_price - obj.price
            pct = int((diff / obj.discount_price) * 100)
            return f"{pct}% OFF"
        if obj.sold_count > 50:
            return "Popular"
        return "Fresh"

    def get_rating(self, obj):
        # Default high rating for presentation
        return 4.8

    def get_unit(self, obj):
        cat = (obj.category or "").lower()
        if "fruit" in cat or "veg" in cat:
            return "per lb"
        if "bread" in cat or "bakery" in cat:
            return "each"
        return "each"

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return obj.image_url_fallback or "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=600&q=80"

    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return CustomerFavorite.objects.filter(user=request.user, product=obj).exists()
        return False


class CustomerStoreSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="name", read_only=True)
    time = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()

    class Meta:
        model = MerchantStore
        fields = [
            "id",
            "title",
            "name",
            "category",
            "address",
            "description",
            "phone",
            "rating",
            "reviews_count",
            "is_verified",
            "is_open",
            "time",
            "distance",
            "logo_url",
            "banner_url",
            "is_favorited",
        ]

    def get_time(self, obj):
        return "15-25 min"

    def get_distance(self, obj):
        return "0.8 km"

    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return "https://images.unsplash.com/photo-1578916171728-46686eac8d58?auto=format&fit=crop&w=300&q=80"

    def get_banner_url(self, obj):
        if obj.banner:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.banner.url)
            return obj.banner.url
        return "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80"

    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return CustomerFavorite.objects.filter(user=request.user, store=obj).exists()
        return False


class CustomerOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_name",
            "description",
            "price",
            "quantity",
            "image_url",
        ]


class CustomerOrderSerializer(serializers.ModelSerializer):
    items = CustomerOrderItemSerializer(many=True, read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    store_logo = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()
    formatted_date = serializers.SerializerMethodField()
    formatted_time = serializers.SerializerMethodField()
    display_status = serializers.SerializerMethodField()
    rider_id = serializers.SerializerMethodField()
    rider_name = serializers.SerializerMethodField()
    rider_phone = serializers.SerializerMethodField()
    rider_avatar = serializers.SerializerMethodField()
    rider_vehicle = serializers.SerializerMethodField()
    rider_number_plate = serializers.SerializerMethodField()
    rider_rating = serializers.SerializerMethodField()
    rider_latitude = serializers.SerializerMethodField()
    rider_longitude = serializers.SerializerMethodField()
    store_latitude = serializers.SerializerMethodField()
    store_longitude = serializers.SerializerMethodField()
    delivery_latitude = serializers.SerializerMethodField()
    delivery_longitude = serializers.SerializerMethodField()
    rider_status = serializers.SerializerMethodField()
    delivery_step_text = serializers.SerializerMethodField()
    has_rider = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "otp_code",
            "delivery_step",
            "delivery_step_text",
            "estimated_delivery",
            "store_id",
            "store_name",
            "store_logo",
            "customer_name",
            "delivery_address",
            "delivery_method",
            "subtotal",
            "delivery_fee",
            "discount",
            "total_amount",
            "payment_method",
            "status",
            "display_status",
            "items_count",
            "items",
            "has_rider",
            "rider_id",
            "rider_name",
            "rider_phone",
            "rider_avatar",
            "rider_vehicle",
            "rider_number_plate",
            "rider_rating",
            "rider_status",
            "rider_latitude",
            "rider_longitude",
            "store_latitude",
            "store_longitude",
            "delivery_latitude",
            "delivery_longitude",
            "formatted_date",
            "formatted_time",
            "created_at",
        ]

    def get_store_logo(self, obj):
        if obj.store and obj.store.logo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.store.logo.url)
            return obj.store.logo.url
        return "https://images.unsplash.com/photo-1578916171728-46686eac8d58?auto=format&fit=crop&w=150&q=80"

    def get_items_count(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_formatted_date(self, obj):
        return obj.created_at.strftime("%b %d, %Y")

    def get_formatted_time(self, obj):
        return obj.created_at.strftime("%I:%M %p")

    def get_display_status(self, obj):
        status_map = {
            Order.STATUS_NEW: "New Order",
            Order.STATUS_PREPARING: "Preparing",
            Order.STATUS_READY: "Ready",
            Order.STATUS_ON_THE_WAY: "On The Way",
            Order.STATUS_DELIVERED: "Delivered",
            Order.STATUS_CANCELLED: "Cancelled",
        }
        return status_map.get(obj.status, obj.status.title())

    def get_has_rider(self, obj):
        return obj.rider is not None

    def get_rider_id(self, obj):
        return str(obj.rider.id) if obj.rider else None

    def get_rider_name(self, obj):
        if obj.rider and obj.rider.user:
            return obj.rider.user.full_name or "Marc Antoine"
        return "Marc Antoine"

    def get_rider_phone(self, obj):
        if obj.rider and obj.rider.user:
            return obj.rider.user.phone or "+509 3700-1234"
        return "+509 3700-1234"

    def get_rider_avatar(self, obj):
        if obj.rider and obj.rider.user and obj.rider.user.avatar:
            request = self.context.get("request")
            if request and hasattr(obj.rider.user.avatar, "url"):
                return request.build_absolute_uri(obj.rider.user.avatar.url)
            return str(obj.rider.user.avatar)
        return "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=150&q=80"

    def get_rider_vehicle(self, obj):
        if obj.rider:
            return obj.rider.vehicle_type or "Motorcycle"
        return "Motorcycle"

    def get_rider_number_plate(self, obj):
        if obj.rider:
            return obj.rider.number_plate or "HT-1234"
        return "HT-1234"

    def get_rider_rating(self, obj):
        return 4.9

    def get_rider_latitude(self, obj):
        if getattr(obj, "rider_latitude", None) is not None:
            return float(obj.rider_latitude)
        if obj.rider and getattr(obj.rider, "current_latitude", None) is not None:
            return float(obj.rider.current_latitude)
        step = obj.delivery_step
        if step == 0:
            return 18.536000
        elif step == 1:
            return 18.539200
        elif step == 2:
            return 18.544000
        elif step >= 3:
            return 18.548200
        return 18.543700

    def get_rider_longitude(self, obj):
        if getattr(obj, "rider_longitude", None) is not None:
            return float(obj.rider_longitude)
        if obj.rider and getattr(obj.rider, "current_longitude", None) is not None:
            return float(obj.rider.current_longitude)
        step = obj.delivery_step
        if step == 0:
            return -72.339000
        elif step == 1:
            return -72.336400
        elif step == 2:
            return -72.330000
        elif step >= 3:
            return -72.325400
        return -72.330900

    def get_store_latitude(self, obj):
        if obj.store and getattr(obj.store, "latitude", None) is not None:
            return float(obj.store.latitude)
        return 18.539200

    def get_store_longitude(self, obj):
        if obj.store and getattr(obj.store, "longitude", None) is not None:
            return float(obj.store.longitude)
        return -72.336400

    def get_delivery_latitude(self, obj):
        if getattr(obj, "delivery_latitude", None) is not None:
            return float(obj.delivery_latitude)
        return 18.548200

    def get_delivery_longitude(self, obj):
        if getattr(obj, "delivery_longitude", None) is not None:
            return float(obj.delivery_longitude)
        return -72.325400

    def get_rider_status(self, obj):
        if not obj.rider:
            return "Searching for nearby rider..."
        if obj.delivery_step == 0:
            return "Order Accepted - Rider assigned"
        elif obj.delivery_step == 1:
            return "Rider heading to store"
        elif obj.delivery_step == 2:
            return "Out for Delivery - Rider on the way"
        elif obj.delivery_step >= 3:
            return "Order Delivered"
        return "In Progress"

    def get_delivery_step_text(self, obj):
        steps = {
            0: "Order Accepted",
            1: "Arrived at Store",
            2: "Out for Delivery",
            3: "Delivered",
        }
        return steps.get(obj.delivery_step, "Processing")


class CustomerOrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    product_name = serializers.CharField(max_length=200)
    quantity = serializers.IntegerField(default=1, min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    image_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")


class CustomerOrderCreateSerializer(serializers.Serializer):
    store_id = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    items = CustomerOrderItemCreateSerializer(many=True)
    delivery_address = serializers.CharField(max_length=300, required=False, allow_blank=True)
    shipping_address = serializers.CharField(max_length=300, required=False, allow_blank=True)
    delivery_method = serializers.CharField(max_length=100, default="Standard Delivery")
    payment_method = serializers.CharField(max_length=50, default="Cash on Delivery")
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    delivery_instructions = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("delivery_address") and not attrs.get("shipping_address"):
            attrs["delivery_address"] = "123 Rue de la République, Port-au-Prince, Haiti"
        elif not attrs.get("delivery_address"):
            attrs["delivery_address"] = attrs.get("shipping_address")
        return attrs


class CustomerFavoriteSerializer(serializers.ModelSerializer):
    product = CustomerProductSerializer(read_only=True)
    store = CustomerStoreSerializer(read_only=True)

    class Meta:
        model = CustomerFavorite
        fields = ["id", "product", "store", "created_at"]


class CustomerFavoriteToggleSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(required=False, allow_null=True)
    store_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        prod = attrs.get("product_id")
        store = attrs.get("store_id")
        if not prod and not store:
            raise serializers.ValidationError("Either product_id or store_id must be provided.")
        if prod and store:
            raise serializers.ValidationError("Provide only one of product_id or store_id.")
        return attrs

