import random
import uuid
from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Q
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.merchant.models import Order, OrderChatMessage, OrderItem, Product
from apps.users.models import MerchantStore, RiderProfile
from apps.rider.serializers import OrderChatMessageSerializer
from .models import CustomerAddress, CustomerFavorite, PromoBanner
from .serializers import (
    CustomerAddressSerializer,
    CustomerFavoriteSerializer,
    CustomerFavoriteToggleSerializer,
    CustomerOrderCreateSerializer,
    CustomerOrderSerializer,
    CustomerProductSerializer,
    CustomerStoreSerializer,
    PromoBannerSerializer,
)


class CustomerHomeView(APIView):
    """
    Public customer marketplace homepage endpoint.
    Aggregates active banners, dynamic product/store categories,
    trending products, and top verified stores.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Customer Home Dashboard",
        description="Returns banners, categories, trending products, and top-rated stores.",
    )
    def get(self, request, *args, **kwargs):
        # 1. Banners
        banners = PromoBanner.objects.filter(is_active=True)
        if not banners.exists():
            # Create a default promo banner if none exists
            default_banner = PromoBanner.objects.create(
                title="Fresh Groceries\nDelivered Fast",
                subtitle="Save up to 30% OFF",
                discount_text="30% OFF",
                image_url="https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80",
                link_category="Grocery",
            )
            banners = [default_banner]
        banner_data = PromoBannerSerializer(banners, many=True, context={"request": request}).data

        # 2. Categories with active product counts
        categories = [
            {
                "title": "All",
                "icon": "grid_view_rounded",
                "icon_color": "#FF7449",
                "count": Product.objects.filter(~Q(status=Product.STATUS_ARCHIVED), stock__gt=0).count(),
            },
            {
                "title": "Food",
                "icon": "restaurant_menu_rounded",
                "icon_color": "#FF7449",
                "count": Product.objects.filter(category__in=["Meat", "Dairy", "Bakery"], stock__gt=0).exclude(status=Product.STATUS_ARCHIVED).count(),
            },
            {
                "title": "Grocery",
                "icon": "local_mall_outlined",
                "icon_color": "#10B981",
                "count": Product.objects.filter(category__in=["Vegetables", "Fruits", "Grains"], stock__gt=0).exclude(status=Product.STATUS_ARCHIVED).count(),
            },
            {
                "title": "Vegetables",
                "icon": "eco_outlined",
                "icon_color": "#10B981",
                "count": Product.objects.filter(category="Vegetables", stock__gt=0).exclude(status=Product.STATUS_ARCHIVED).count(),
            },
            {
                "title": "Fruits",
                "icon": "nutrition_outlined",
                "icon_color": "#F59E0B",
                "count": Product.objects.filter(category="Fruits", stock__gt=0).exclude(status=Product.STATUS_ARCHIVED).count(),
            },
            {
                "title": "Bakery",
                "icon": "bakery_dining_outlined",
                "icon_color": "#D97706",
                "count": Product.objects.filter(category="Bakery", stock__gt=0).exclude(status=Product.STATUS_ARCHIVED).count(),
            },
            {
                "title": "Pharmacy",
                "icon": "medical_services_outlined",
                "icon_color": "#3B82F6",
                "count": Product.objects.filter(category="Other", stock__gt=0).exclude(status=Product.STATUS_ARCHIVED).count(),
            },
        ]

        # 3. Trending Products
        trending_products = Product.objects.filter(
            ~Q(status=Product.STATUS_ARCHIVED),
            stock__gt=0,
            store__is_open=True,
        ).select_related("store").order_by("-sold_count", "-created_at")[:10]
        trending_data = CustomerProductSerializer(
            trending_products,
            many=True,
            context={"request": request},
        ).data

        # 4. Top Rated Stores
        top_stores = MerchantStore.objects.filter(
            is_open=True,
            is_verified=True,
        ).order_by("-rating", "-reviews_count")[:6]
        stores_data = CustomerStoreSerializer(
            top_stores,
            many=True,
            context={"request": request},
        ).data

        return Response({
            "success": True,
            "data": {
                "banners": banner_data,
                "categories": categories,
                "trending_products": trending_data,
                "top_stores": stores_data,
            },
        })


class CustomerProductsListView(generics.ListAPIView):
    """
    Search and filter products across all open stores.
    Supports ?category=..., ?store_id=..., ?search=..., ?trending=true
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomerProductSerializer

    def get_queryset(self):
        qs = Product.objects.filter(
            ~Q(status=Product.STATUS_ARCHIVED),
            stock__gt=0,
            store__is_open=True,
        ).select_related("store")

        category = self.request.query_params.get("category")
        if category and category.lower() != "all":
            if category.lower() == "food":
                qs = qs.filter(category__in=["Meat", "Dairy", "Bakery"])
            elif category.lower() == "grocery":
                qs = qs.filter(category__in=["Vegetables", "Fruits", "Grains", "Bakery"])
            else:
                qs = qs.filter(category__iexact=category)

        store_id = self.request.query_params.get("store_id")
        if store_id:
            qs = qs.filter(store_id=store_id)

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(category__icontains=search)
                | Q(store__name__icontains=search)
            )

        trending = self.request.query_params.get("trending")
        if trending and trending.lower() == "true":
            qs = qs.order_by("-sold_count")
        else:
            qs = qs.order_by("-created_at")

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True, context={"request": request})
        return Response({
            "success": True,
            "data": serializer.data,
            "count": len(serializer.data),
        })


class CustomerProductDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomerProductSerializer
    queryset = Product.objects.select_related("store")

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})


class CustomerStoresListView(generics.ListAPIView):
    """
    List and search active stores. Supports ?category=... and ?search=...
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomerStoreSerializer

    def get_queryset(self):
        qs = MerchantStore.objects.filter(is_open=True)

        category = self.request.query_params.get("category")
        if category and category.lower() != "all":
            qs = qs.filter(category__iexact=category)

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(category__icontains=search)
                | Q(address__icontains=search)
            )

        return qs.order_by("-rating", "-reviews_count")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True, context={"request": request})
        return Response({
            "success": True,
            "data": serializer.data,
            "count": len(serializer.data),
        })


class CustomerStoreDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomerStoreSerializer
    queryset = MerchantStore.objects.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})


class CustomerOrdersView(generics.ListAPIView):
    """
    List past and active orders for the currently authenticated customer.
    Supports ?status=delivered|cancelled|active
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomerOrderSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.filter(
            Q(customer=user)
            | Q(customer_email__iexact=user.email)
            | Q(customer_phone=user.phone)
        ).select_related("store").prefetch_related("items").order_by("-created_at")

        status_param = self.request.query_params.get("status")
        if status_param:
            status_param = status_param.lower()
            if status_param == "delivered":
                qs = qs.filter(status=Order.STATUS_DELIVERED)
            elif status_param == "cancelled":
                qs = qs.filter(status=Order.STATUS_CANCELLED)
            elif status_param == "active":
                qs = qs.filter(status__in=[
                    Order.STATUS_NEW,
                    Order.STATUS_PREPARING,
                    Order.STATUS_READY,
                    Order.STATUS_ON_THE_WAY,
                ])

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True, context={"request": request})
        return Response({
            "success": True,
            "data": serializer.data,
            "count": len(serializer.data),
        })

    def post(self, request, *args, **kwargs):
        serializer = CustomerOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        items_data = data["items"]

        # Resolve store
        store = None
        store_id = data.get("store_id")
        if store_id:
            try:
                s_uuid = uuid.UUID(str(store_id))
                store = MerchantStore.objects.filter(id=s_uuid).first()
            except (ValueError, TypeError):
                store = MerchantStore.objects.filter(name__icontains=str(store_id)).first()
        
        # If no store specified, try resolving from first item's product or fallback
        if not store and items_data:
            first_prod_id = items_data[0].get("product_id")
            if first_prod_id:
                try:
                    uuid_val = uuid.UUID(str(first_prod_id))
                    prod = Product.objects.filter(id=uuid_val).select_related("store").first()
                    if prod:
                        store = prod.store
                except (ValueError, TypeError):
                    pass
        if not store:
            store = MerchantStore.objects.first()

        if not store:
            return Response(
                {"success": False, "message": "No active merchant store available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calculate totals safely with Decimal
        subtotal = data.get("subtotal")
        if not subtotal:
            subtotal = sum((Decimal(str(item["price"])) * item["quantity"] for item in items_data), Decimal("0.00"))
        else:
            subtotal = Decimal(str(subtotal))

        delivery_fee = Decimal(str(data.get("delivery_fee", "0.00")))
        discount = Decimal(str(data.get("discount", "0.00")))
        total_amount = data.get("total_amount")
        if not total_amount:
            total_amount = subtotal + delivery_fee - discount
        else:
            total_amount = Decimal(str(total_amount))

        # Generate unique order number and 4-digit numeric OTP code
        order_num = f"#TBK-{random.randint(1045, 9999)}"
        otp_code = str(random.randint(1000, 9999))

        # Assign an active rider if available
        rider = RiderProfile.objects.filter(status=RiderProfile.STATUS_ACTIVE).first()
        if not rider:
            rider = RiderProfile.objects.first()

        with transaction.atomic():
            order = Order.objects.create(
                store=store,
                order_number=order_num,
                customer=user,
                customer_name=user.full_name or "Valued Customer",
                customer_email=user.email,
                customer_phone=user.phone or "",
                delivery_address=data["delivery_address"],
                delivery_method=data.get("delivery_method", "Standard Delivery"),
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                discount=discount,
                total_amount=total_amount,
                payment_method=data.get("payment_method", "Cash on Delivery"),
                status=Order.STATUS_NEW,
                rider=rider,
                otp_code=otp_code,
                delivery_step=0,
            )

            for item_data in items_data:
                prod_fk = None
                raw_prod_id = item_data.get("product_id")
                if raw_prod_id:
                    try:
                        p_uuid = uuid.UUID(str(raw_prod_id))
                        prod_fk = Product.objects.filter(id=p_uuid).first()
                    except (ValueError, TypeError):
                        prod_fk = None

                OrderItem.objects.create(
                    order=order,
                    product=prod_fk,
                    product_name=item_data["product_name"],
                    description=item_data.get("description", ""),
                    price=item_data["price"],
                    quantity=item_data["quantity"],
                    image_url=item_data.get("image_url", ""),
                )

        return Response(
            {
                "success": True,
                "message": "Order placed successfully! Track your delivery status.",
                "data": CustomerOrderSerializer(order, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CustomerOrderDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomerOrderSerializer

    def get_object(self):
        lookup = self.kwargs.get("order_lookup") or self.kwargs.get("pk")
        user = self.request.user
        qs = Order.objects.filter(
            Q(customer=user)
            | Q(customer_email__iexact=user.email)
            | Q(customer_phone=user.phone)
        ).select_related("store", "rider", "rider__user").prefetch_related("items")

        order = None
        if lookup:
            try:
                val = uuid.UUID(str(lookup))
                order = qs.filter(id=val).first()
            except (ValueError, TypeError):
                pass

            if not order:
                order = qs.filter(
                    Q(order_number__iexact=str(lookup))
                    | Q(order_number__iexact=f"#{lookup}")
                    | Q(order_number__iexact=str(lookup).replace('#', ''))
                ).first()

        if not order:
            from django.http import Http404
            raise Http404("Order not found.")
        return order

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response({"success": True, "data": serializer.data})


class CustomerOrderRateView(APIView):
    """
    Submit customer rating for order store and rider.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_lookup, *args, **kwargs):
        user = request.user
        qs = Order.objects.filter(
            Q(customer=user)
            | Q(customer_email__iexact=user.email)
            | Q(customer_phone=user.phone)
        ).select_related("store", "rider", "rider__user")

        order = None
        try:
            val = uuid.UUID(str(order_lookup))
            order = qs.filter(id=val).first()
        except (ValueError, TypeError):
            pass

        if not order:
            order = qs.filter(
                Q(order_number__iexact=str(order_lookup))
                | Q(order_number__iexact=f"#{order_lookup}")
                | Q(order_number__iexact=str(order_lookup).replace('#', ''))
            ).first()

        if not order:
            return Response(
                {"success": False, "message": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        store_rating = request.data.get("store_rating", 5)
        rider_rating = request.data.get("rider_rating", 5)
        store_comment = request.data.get("store_comment", "")
        rider_comment = request.data.get("rider_comment", "")

        # Update store rating statistics
        if order.store:
            try:
                new_rating = Decimal(str(store_rating))
                current_cnt = order.store.reviews_count or 0
                current_avg = order.store.rating or Decimal("5.00")
                updated_avg = ((current_avg * current_cnt) + new_rating) / (current_cnt + 1)
                order.store.rating = round(updated_avg, 2)
                order.store.reviews_count = current_cnt + 1
                order.store.save(update_fields=["rating", "reviews_count"])
            except Exception:
                pass

        # Mark order as delivered and complete step
        if order.status != Order.STATUS_DELIVERED:
            order.status = Order.STATUS_DELIVERED
            order.delivery_step = 4
            order.save(update_fields=["status", "delivery_step", "updated_at"])

        return Response({
            "success": True,
            "message": "Thank you for your rating and feedback!",
            "data": CustomerOrderSerializer(order, context={"request": request}).data,
        })


class CustomerOrderChatView(APIView):
    """
    Customer chat interface with assigned rider for an order.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _resolve_order(self, user, order_lookup=None):
        qs = Order.objects.filter(
            Q(customer=user)
            | Q(customer_email__iexact=user.email)
            | Q(customer_phone=user.phone)
        ).select_related("store", "rider", "rider__user")

        if order_lookup and str(order_lookup).lower() != "active":
            try:
                val = uuid.UUID(str(order_lookup))
                order = qs.filter(id=val).first()
                if order:
                    return order
            except (ValueError, TypeError):
                pass

            order = qs.filter(
                Q(order_number__iexact=str(order_lookup))
                | Q(order_number__iexact=f"#{order_lookup}")
                | Q(order_number__iexact=str(order_lookup).replace('#', ''))
            ).first()
            if order:
                return order

        # Default to latest active or latest order
        active = qs.filter(
            status__in=[
                Order.STATUS_NEW,
                Order.STATUS_PREPARING,
                Order.STATUS_READY,
                Order.STATUS_ON_THE_WAY,
            ]
        ).first()
        return active or qs.first()

    def get(self, request, order_lookup=None):
        order = self._resolve_order(request.user, order_lookup)
        if not order:
            return Response({"success": True, "data": [], "messages": []})

        msgs = OrderChatMessage.objects.filter(order=order).order_by("created_at")

        if not msgs.exists():
            store_title = order.store.name if order.store else "the store"
            rider_title = order.rider.user.full_name if (order.rider and order.rider.user) else "Marc Antoine"
            OrderChatMessage.objects.create(
                order=order,
                sender=order.rider.user if (order.rider and order.rider.user) else request.user,
                sender_role="rider",
                sender_name=f"{rider_title} (Rider)",
                message=f"Hello! I have your order from {store_title} and am on my way to deliver.",
            )
            msgs = OrderChatMessage.objects.filter(order=order).order_by("created_at")

        serializer = OrderChatMessageSerializer(msgs, many=True)
        return Response({
            "success": True,
            "data": serializer.data,
            "messages": serializer.data,
            "order": {
                "id": str(order.id),
                "order_number": order.order_number,
                "rider_name": order.rider.user.full_name if (order.rider and order.rider.user) else "Marc Antoine",
                "rider_phone": order.rider.user.phone if (order.rider and order.rider.user) else "+509 3700-1234",
                "rider_vehicle": order.rider.vehicle_type if order.rider else "Motorcycle",
                "status": order.status,
            },
        })

    def post(self, request, order_lookup=None):
        text = (request.data.get("message") or request.data.get("text") or "").strip()
        if not text:
            return Response({"success": False, "message": "Message text is required."}, status=status.HTTP_400_BAD_REQUEST)

        order = self._resolve_order(request.user, order_lookup)
        if not order:
            return Response({"success": False, "message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        msg = OrderChatMessage.objects.create(
            order=order,
            sender=request.user,
            sender_role="customer",
            sender_name=request.user.full_name or "Valued Customer",
            message=text,
        )

        return Response({
            "success": True,
            "message": "Message sent.",
            "data": OrderChatMessageSerializer(msg).data,
        }, status=status.HTTP_201_CREATED)



class CustomerAddressListCreateView(generics.ListCreateAPIView):
    """
    List and create saved delivery addresses for authenticated customer.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomerAddressSerializer

    def get_queryset(self):
        return CustomerAddress.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"success": True, "data": serializer.data})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        address = serializer.save()
        return Response(
            {
                "success": True,
                "message": "Delivery address added successfully.",
                "data": CustomerAddressSerializer(address).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CustomerAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a customer saved delivery address.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomerAddressSerializer

    def get_queryset(self):
        return CustomerAddress.objects.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({"success": True, "data": serializer.data})

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "success": True,
            "message": "Address updated successfully.",
            "data": serializer.data,
        })

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        was_default = instance.is_default
        instance.delete()

        # If deleted address was default, make the most recent remaining one default
        if was_default:
            next_addr = CustomerAddress.objects.filter(user=request.user).first()
            if next_addr:
                next_addr.is_default = True
                next_addr.save()

        return Response({
            "success": True,
            "message": "Address deleted successfully.",
        })


class CustomerAddressSetDefaultView(APIView):
    """
    Set an address as the default delivery address.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        try:
            address = CustomerAddress.objects.get(pk=pk, user=request.user)
        except CustomerAddress.DoesNotExist:
            return Response(
                {"success": False, "message": "Address not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        CustomerAddress.objects.filter(user=request.user, is_default=True).update(is_default=False)
        address.is_default = True
        address.save()

        return Response({
            "success": True,
            "message": "Default address updated.",
            "data": CustomerAddressSerializer(address).data,
        })


class CustomerFavoritesView(APIView):
    """
    Get customer favorite products and stores, or toggle favorite status.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        fav_products = CustomerFavorite.objects.filter(
            user=request.user,
            product__isnull=False,
        ).select_related("product", "product__store")

        fav_stores = CustomerFavorite.objects.filter(
            user=request.user,
            store__isnull=False,
        ).select_related("store")

        products_data = []
        for fav in fav_products:
            if fav.product:
                image_url = ""
                if fav.product.image:
                    image_url = request.build_absolute_uri(fav.product.image.url)
                elif fav.product.image_url_fallback:
                    image_url = fav.product.image_url_fallback
                else:
                    image_url = "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=300&q=80"

                products_data.append({
                    "id": str(fav.product.id),
                    "name": fav.product.name,
                    "title": fav.product.name,
                    "store_name": fav.product.store.name if fav.product.store else "TiBoutik Store",
                    "store_id": str(fav.product.store.id) if fav.product.store else None,
                    "image_url": image_url,
                    "price": float(fav.product.price),
                    "original_price": float(fav.product.price),
                    "discount": "Fresh",
                    "in_stock": fav.product.stock > 0,
                    "sold_count": fav.product.sold_count,
                    "rating": 4.9,
                    "category": fav.product.category,
                    "unit": "each",
                    "is_favorited": True,
                    "favorite_id": str(fav.id),
                })

        stores_data = []
        for fav in fav_stores:
            if fav.store:
                store_img = ""
                if fav.store.logo:
                    store_img = request.build_absolute_uri(fav.store.logo.url)
                elif fav.store.banner:
                    store_img = request.build_absolute_uri(fav.store.banner.url)
                else:
                    store_img = "https://images.unsplash.com/photo-1578916171728-46686eac8d58?auto=format&fit=crop&w=300&q=80"

                banner_img = ""
                if fav.store.banner:
                    banner_img = request.build_absolute_uri(fav.store.banner.url)
                else:
                    banner_img = "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80"

                stores_data.append({
                    "id": str(fav.store.id),
                    "name": fav.store.name,
                    "title": fav.store.name,
                    "category": fav.store.category,
                    "image_url": store_img,
                    "logo_url": store_img,
                    "banner_url": banner_img,
                    "rating": float(fav.store.rating),
                    "reviews_count": fav.store.reviews_count,
                    "is_verified": fav.store.is_verified,
                    "time": "15-25 min",
                    "distance": "0.8 km",
                    "is_favorited": True,
                    "favorite_id": str(fav.id),
                })

        return Response({
            "success": True,
            "data": {
                "products": products_data,
                "stores": stores_data,
                "total_count": len(products_data) + len(stores_data),
            },
        })

    def post(self, request, *args, **kwargs):
        serializer = CustomerFavoriteToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data.get("product_id")
        store_id = serializer.validated_data.get("store_id")

        if product_id:
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                return Response(
                    {"success": False, "message": "Product not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            existing = CustomerFavorite.objects.filter(user=request.user, product=product).first()
            if existing:
                existing.delete()
                return Response({
                    "success": True,
                    "is_favorited": False,
                    "message": "Product removed from favorites.",
                })
            else:
                CustomerFavorite.objects.create(user=request.user, product=product)
                return Response({
                    "success": True,
                    "is_favorited": True,
                    "message": "Product added to favorites.",
                })

        if store_id:
            try:
                store = MerchantStore.objects.get(pk=store_id)
            except MerchantStore.DoesNotExist:
                return Response(
                    {"success": False, "message": "Store not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            existing = CustomerFavorite.objects.filter(user=request.user, store=store).first()
            if existing:
                existing.delete()
                return Response({
                    "success": True,
                    "is_favorited": False,
                    "message": "Store removed from favorites.",
                })
            else:
                CustomerFavorite.objects.create(user=request.user, store=store)
                return Response({
                    "success": True,
                    "is_favorited": True,
                    "message": "Store added to favorites.",
                })

        return Response(
            {"success": False, "message": "Invalid request."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, *args, **kwargs):
        product_id = request.data.get("product_id") or request.query_params.get("product_id")
        store_id = request.data.get("store_id") or request.query_params.get("store_id")
        favorite_id = request.data.get("favorite_id") or request.query_params.get("favorite_id")

        if favorite_id:
            CustomerFavorite.objects.filter(user=request.user, pk=favorite_id).delete()
        elif product_id:
            CustomerFavorite.objects.filter(user=request.user, product_id=product_id).delete()
        elif store_id:
            CustomerFavorite.objects.filter(user=request.user, store_id=store_id).delete()
        else:
            return Response(
                {"success": False, "message": "Must provide favorite_id, product_id, or store_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "success": True,
            "is_favorited": False,
            "message": "Removed from favorites.",
        })


class CustomerFavoriteDetailDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, *args, **kwargs):
        fav = CustomerFavorite.objects.filter(user=request.user, pk=pk).first()
        if not fav:
            return Response(
                {"success": False, "message": "Favorite not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        fav.delete()
        return Response({
            "success": True,
            "is_favorited": False,
            "message": "Removed from favorites.",
        })


class CustomerProfileSummaryView(APIView):
    """
    Profile summary numbers: active orders, total orders, favorites count, addresses count.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        orders_qs = Order.objects.filter(
            Q(customer=user)
            | Q(customer_email__iexact=user.email)
            | Q(customer_phone=user.phone)
        )
        active_orders = orders_qs.filter(
            status__in=[
                Order.STATUS_NEW,
                Order.STATUS_PREPARING,
                Order.STATUS_READY,
                Order.STATUS_ON_THE_WAY,
            ]
        ).count()
        total_orders = orders_qs.count()
        addresses_count = CustomerAddress.objects.filter(user=user).count()
        favorites_count = CustomerFavorite.objects.filter(user=user).count()

        return Response({
            "success": True,
            "data": {
                "active_orders_count": active_orders,
                "total_orders_count": total_orders,
                "addresses_count": addresses_count,
                "favorites_count": favorites_count,
            },
        })
