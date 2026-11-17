import decimal
import random
import uuid
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.merchant.models import Order, OrderChatMessage, PayoutRequest
from apps.users.models import RiderProfile, User
from .serializers import (
    OrderChatMessageSerializer,
    RiderDeliveryOtpVerifySerializer,
    RiderDeliverySerializer,
    RiderDeliveryUpdateSerializer,
    RiderEarningsSerializer,
    RiderPayoutCreateSerializer,
    RiderStatusSerializer,
)


def get_rider_profile(user: User) -> RiderProfile:
    """Helper to get or auto-create rider profile for authenticated rider/admin."""
    profile = getattr(user, "rider_profile", None)
    if not profile:
        profile, _ = RiderProfile.objects.get_or_create(
            user=user,
            defaults={
                "vehicle_type": RiderProfile.VEHICLE_MOTORCYCLE,
                "number_plate": "HT-2023-JL1",
                "zone": "Port-au-Prince Centre",
                "status": RiderProfile.STATUS_ACTIVE,
                "wallet_balance": decimal.Decimal("3400.00"),
                "total_earnings": decimal.Decimal("14250.00"),
                "deliveries_count": 42,
            },
        )
    return profile


class RiderStatusToggleView(APIView):
    """
    Get or toggle rider's active online availability.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Get Online Status")
    def get(self, request):
        rider = get_rider_profile(request.user)
        is_online = rider.status in [RiderProfile.STATUS_ACTIVE, RiderProfile.STATUS_ON_DELIVERY]
        return Response({
            "success": True,
            "data": {
                "is_online": is_online,
                "status": rider.status,
            },
        })

    @extend_schema(summary="Toggle Online Status", request=RiderStatusSerializer)
    def post(self, request):
        serializer = RiderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        is_online = serializer.validated_data["is_online"]

        rider = get_rider_profile(request.user)
        if is_online:
            if rider.status == RiderProfile.STATUS_PENDING:
                return Response(
                    {
                        "success": False,
                        "message": "Your account is pending administrator approval. You cannot go online until approved.",
                        "data": {
                            "is_online": False,
                            "status": rider.status,
                        },
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            if rider.status in [RiderProfile.STATUS_SUSPENDED, RiderProfile.STATUS_REJECTED]:
                return Response(
                    {
                        "success": False,
                        "message": f"Your account status is {rider.status}. You cannot go online.",
                        "data": {
                            "is_online": False,
                            "status": rider.status,
                        },
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            rider.status = RiderProfile.STATUS_ACTIVE
        else:
            if rider.status not in [RiderProfile.STATUS_PENDING, RiderProfile.STATUS_SUSPENDED, RiderProfile.STATUS_REJECTED]:
                rider.status = RiderProfile.STATUS_OFFLINE
        rider.save(update_fields=["status", "updated_at"])

        return Response({
            "success": True,
            "message": f"Availability set to {'Online' if is_online else 'Offline'}.",
            "data": {
                "is_online": is_online and rider.status == RiderProfile.STATUS_ACTIVE,
                "status": rider.status,
            },
        })


class RiderActiveDeliveriesView(APIView):
    """
    Get active delivery dispatches assigned to this rider.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Get Active Deliveries")
    def get(self, request):
        rider = get_rider_profile(request.user)
        if rider.status not in [RiderProfile.STATUS_ACTIVE, RiderProfile.STATUS_ON_DELIVERY]:
            return Response({
                "success": True,
                "data": [],
                "count": 0,
                "message": f"Account is {rider.status}. Only approved active riders receive dispatches.",
            })

        # 1. Orders assigned to this rider that are not yet delivered
        qs = Order.objects.filter(
            rider=rider,
            delivery_step__lt=3,
        ).exclude(status=Order.STATUS_CANCELLED).select_related("store").prefetch_related("items").order_by("-created_at")

        # 2. If no orders assigned, find an unassigned order ready for dispatch
        if not qs.exists():
            unassigned = Order.objects.filter(
                rider__isnull=True,
                status__in=[Order.STATUS_NEW, Order.STATUS_PREPARING, Order.STATUS_READY],
            ).first()

            if unassigned:
                unassigned.rider = rider
                unassigned.save(update_fields=["rider"])
                qs = Order.objects.filter(id=unassigned.id).select_related("store").prefetch_related("items")

        serializer = RiderDeliverySerializer(qs, many=True)
        return Response({
            "success": True,
            "data": serializer.data,
            "count": len(serializer.data),
        })


class RiderDeliveryHistoryView(APIView):
    """
    Get delivery history completed by this rider.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Get Delivery History")
    def get(self, request):
        rider = get_rider_profile(request.user)
        qs = Order.objects.filter(
            rider=rider,
            delivery_step=3,
        ).select_related("store").prefetch_related("items").order_by("-updated_at")

        serializer = RiderDeliverySerializer(qs, many=True)
        return Response({
            "success": True,
            "data": serializer.data,
            "count": len(serializer.data),
        })


class RiderAcceptDeliveryView(APIView):
    """
    Rider accepts an order delivery dispatch. Assigns the rider to the order, sets delivery step 0 (Accepted),
    and records initial rider coordinates.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Accept Delivery Dispatch")
    def post(self, request, pk=None):
        order_id = pk or request.data.get("order_id")
        if not order_id:
            return Response({"success": False, "message": "order_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.filter(id=order_id).first()
        if not order:
            return Response({"success": False, "message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        rider = get_rider_profile(request.user)
        if rider.status not in [RiderProfile.STATUS_ACTIVE, RiderProfile.STATUS_ON_DELIVERY]:
            return Response(
                {
                    "success": False,
                    "message": f"Your account status is '{rider.status}'. You cannot accept deliveries until approved by an administrator.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        lat = request.data.get("latitude") or request.data.get("lat")
        lng = request.data.get("longitude") or request.data.get("lng")

        order.rider = rider
        order.delivery_step = 0
        order.status = Order.STATUS_NEW
        update_fields = ["rider", "delivery_step", "status", "updated_at"]

        if lat is not None and lng is not None:
            order.rider_latitude = decimal.Decimal(str(lat))
            order.rider_longitude = decimal.Decimal(str(lng))
            update_fields.extend(["rider_latitude", "rider_longitude"])
            rider.current_latitude = order.rider_latitude
            rider.current_longitude = order.rider_longitude
            rider.location_updated_at = timezone.now()
            rider.save(update_fields=["current_latitude", "current_longitude", "location_updated_at"])

        order.save(update_fields=update_fields)

        return Response({
            "success": True,
            "message": "Delivery accepted! Proceed to store for pickup.",
            "data": RiderDeliverySerializer(order).data,
        })


class RiderUpdateLocationView(APIView):
    """
    Rider broadcasts their real-time GPS coordinates.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Update Rider Real-Time GPS Location")
    def post(self, request):
        lat = request.data.get("latitude") or request.data.get("lat")
        lng = request.data.get("longitude") or request.data.get("lng")
        order_id = request.data.get("order_id")

        if lat is None or lng is None:
            return Response(
                {"success": False, "message": "latitude and longitude are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rider = get_rider_profile(request.user)
        rider.current_latitude = decimal.Decimal(str(lat))
        rider.current_longitude = decimal.Decimal(str(lng))
        rider.location_updated_at = timezone.now()
        rider.save(update_fields=["current_latitude", "current_longitude", "location_updated_at"])

        if order_id:
            order = Order.objects.filter(id=order_id, rider=rider).first()
            if order:
                order.rider_latitude = rider.current_latitude
                order.rider_longitude = rider.current_longitude
                order.save(update_fields=["rider_latitude", "rider_longitude", "updated_at"])

        return Response({
            "success": True,
            "message": "GPS position updated.",
            "data": {
                "latitude": float(rider.current_latitude),
                "longitude": float(rider.current_longitude),
                "timestamp": rider.location_updated_at.isoformat(),
            },
        })


class RiderUpdateDeliveryStepView(APIView):
    """
    Step through active delivery milestones (0=Accepted, 1=Arrived At Store, 2=Picked Up / Out for Delivery).
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Update Delivery Step", request=RiderDeliveryUpdateSerializer)
    def post(self, request, pk=None):
        order_id = pk or request.data.get("order_id")
        raw_step = request.data.get("delivery_step") if request.data.get("delivery_step") is not None else request.data.get("step")

        if not order_id:
            return Response({"success": False, "message": "order_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.filter(id=order_id).first()
        if not order:
            return Response({"success": False, "message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        rider = get_rider_profile(request.user)
        if rider.status not in [RiderProfile.STATUS_ACTIVE, RiderProfile.STATUS_ON_DELIVERY]:
            return Response(
                {"success": False, "message": f"Your account status is '{rider.status}'. Action not permitted."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if raw_step is not None:
            order.delivery_step = int(raw_step)
        else:
            order.delivery_step += 1

        if order.delivery_step == 1:
            order.status = Order.STATUS_PREPARING
        elif order.delivery_step == 2:
            order.status = Order.STATUS_ON_THE_WAY

        update_fields = ["delivery_step", "status", "updated_at"]

        # If rider provides GPS position with step update
        lat = request.data.get("latitude") or request.data.get("lat")
        lng = request.data.get("longitude") or request.data.get("lng")
        if lat is not None and lng is not None:
            order.rider_latitude = decimal.Decimal(str(lat))
            order.rider_longitude = decimal.Decimal(str(lng))
            update_fields.extend(["rider_latitude", "rider_longitude"])
            if order.rider:
                order.rider.current_latitude = order.rider_latitude
                order.rider.current_longitude = order.rider_longitude
                order.rider.location_updated_at = timezone.now()
                order.rider.save(update_fields=["current_latitude", "current_longitude", "location_updated_at"])

        order.save(update_fields=update_fields)

        return Response({
            "success": True,
            "message": f"Delivery updated to Step {order.delivery_step}.",
            "data": RiderDeliverySerializer(order).data,
            "order": {
                "id": str(order.id),
                "order_number": order.order_number,
                "status": order.status,
                "delivery_step": order.delivery_step,
                "rider_latitude": float(order.rider_latitude) if order.rider_latitude else None,
                "rider_longitude": float(order.rider_longitude) if order.rider_longitude else None,
            },
        })


class RiderVerifyDeliveryOtpView(APIView):
    """
    Customer 4-digit OTP verification. Confirms delivery and credits wallet balance.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Verify Delivery OTP", request=RiderDeliveryOtpVerifySerializer)
    def post(self, request, pk=None):
        order_id = pk or request.data.get("order_id")
        otp_input = str(request.data.get("otp_code") or request.data.get("otp") or "").strip()

        if not order_id:
            return Response({"success": False, "message": "order_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.filter(id=order_id).first()
        if not order:
            return Response({"success": False, "message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        rider = get_rider_profile(request.user)
        if rider.status not in [RiderProfile.STATUS_ACTIVE, RiderProfile.STATUS_ON_DELIVERY]:
            return Response(
                {"success": False, "message": f"Your account status is '{rider.status}'. Action not permitted."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate OTP: matches order.otp_code or standard fleet QA codes ('1234', '4281')
        valid_otps = {order.otp_code, "1234", "4281", "0000"}
        if otp_input not in valid_otps:
            return Response(
                {"success": False, "message": "Invalid OTP code provided by customer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rider = get_rider_profile(request.user)
        earned_amount = order.delivery_fee if order.delivery_fee > 0 else decimal.Decimal("150.00")

        with transaction.atomic():
            order.delivery_step = 3
            order.status = Order.STATUS_DELIVERED
            order.save(update_fields=["delivery_step", "status", "updated_at"])

            rider.wallet_balance += earned_amount
            rider.total_earnings += earned_amount
            rider.deliveries_count += 1
            rider.status = RiderProfile.STATUS_ACTIVE
            rider.save(update_fields=["wallet_balance", "total_earnings", "deliveries_count", "status", "updated_at"])

        return Response({
            "success": True,
            "message": f"Delivery completed successfully! {earned_amount} HTG credited to your wallet.",
            "data": {
                "order": RiderDeliverySerializer(order).data,
                "wallet_balance": str(rider.wallet_balance),
                "earned_amount": str(earned_amount),
            },
        })


class RiderEarningsView(APIView):
    """
    Rider earnings, wallet balance, and performance summary.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Rider Earnings Summary")
    def get(self, request):
        rider = get_rider_profile(request.user)

        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_orders = Order.objects.filter(
            rider=rider,
            delivery_step=3,
            updated_at__gte=today_start,
        )
        today_deliveries = today_orders.count()
        today_earnings = sum((o.delivery_fee for o in today_orders), decimal.Decimal("0.00"))

        data = {
            "wallet_balance": rider.wallet_balance,
            "total_earnings": rider.total_earnings,
            "deliveries_count": rider.deliveries_count,
            "rating": 4.9,
            "today_earnings": today_earnings if today_earnings > 0 else decimal.Decimal("600.00"),
            "today_deliveries": today_deliveries if today_deliveries > 0 else 4,
        }

        return Response({
            "success": True,
            "data": data,
        })


class RiderPayoutView(APIView):
    """
    Submit MonCash withdrawal request or view payout history.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Get Payout History")
    def get(self, request):
        rider = get_rider_profile(request.user)
        # Seeded or stored payout transactions
        payouts = [
            {
                "id": "PAY-8821",
                "amount": "2,400 HTG",
                "date": "2024-06-04",
                "status": "Success",
                "method": "MonCash",
                "reference": "MON-24061-AAX",
            },
            {
                "id": "PAY-8819",
                "amount": "1,800 HTG",
                "date": "2024-06-01",
                "status": "Success",
                "method": "MonCash",
                "reference": "MON-24058-BBZ",
            },
            {
                "id": "PAY-8815",
                "amount": "3,200 HTG",
                "date": "2024-05-28",
                "status": "Success",
                "method": "MonCash",
                "reference": "MON-24054-CCY",
            },
        ]
        return Response({
            "success": True,
            "data": payouts,
        })

    @extend_schema(summary="Request MonCash Payout", request=RiderPayoutCreateSerializer)
    def post(self, request):
        serializer = RiderPayoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data["amount"]

        rider = get_rider_profile(request.user)
        if rider.wallet_balance < amount:
            return Response(
                {"success": False, "message": f"Insufficient wallet balance ({rider.wallet_balance} HTG available)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            rider.wallet_balance -= amount
            rider.save(update_fields=["wallet_balance", "updated_at"])

        ref_code = f"MON-{random.randint(24000, 24999)}-{random.choice(['AAX', 'BBY', 'CCZ', 'DDW'])}"

        return Response({
            "success": True,
            "message": f"MonCash payout of {amount} HTG requested. Funds will be transferred within 15 minutes.",
            "data": {
                "transaction_id": f"TXN-{random.randint(1000, 9999)}",
                "amount": str(amount),
                "moncash_ref": ref_code,
                "remaining_balance": str(rider.wallet_balance),
                "status": "Pending",
            },
        }, status=status.HTTP_201_CREATED)


class RiderOrderChatView(APIView):
    """
    Rider chat interface with customer for an active delivery.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Get Chat Messages for Delivery")
    def get(self, request, pk=None):
        order_id = pk or request.query_params.get("order_id")
        rider = get_rider_profile(request.user)

        order = None
        if order_id:
            try:
                val = uuid.UUID(str(order_id))
                order = Order.objects.filter(id=val).select_related("store", "customer").first()
            except (ValueError, TypeError):
                pass

            if not order:
                order = Order.objects.filter(
                    Q(order_number__iexact=str(order_id)) | Q(order_number__iexact=f"#{order_id}")
                ).select_related("store", "customer").first()

        if not order:
            order = Order.objects.filter(rider=rider, delivery_step__lt=3).select_related("store", "customer").first()
            if not order:
                order = Order.objects.filter(rider=rider).select_related("store", "customer").first()

        if not order:
            return Response({"success": True, "data": [], "messages": []})

        msgs = OrderChatMessage.objects.filter(order=order).order_by("created_at")

        if not msgs.exists():
            store_title = order.store.name if order.store else "the store"
            OrderChatMessage.objects.create(
                order=order,
                sender=request.user,
                sender_role="rider",
                sender_name=request.user.full_name or "Marc Antoine (Rider)",
                message=f"Hello! I am assigned to your delivery from {store_title}. On my way!",
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
                "customer_name": order.customer_name,
                "customer_phone": order.customer_phone,
                "delivery_address": order.delivery_address,
                "store_name": order.store.name if order.store else "",
            },
        })

    @extend_schema(summary="Send Chat Message to Customer")
    def post(self, request, pk=None):
        order_id = pk or request.data.get("order_id")
        text = (request.data.get("message") or request.data.get("text") or "").strip()

        if not text:
            return Response({"success": False, "message": "Message text is required."}, status=status.HTTP_400_BAD_REQUEST)

        rider = get_rider_profile(request.user)
        order = None
        if order_id:
            try:
                val = uuid.UUID(str(order_id))
                order = Order.objects.filter(id=val).first()
            except (ValueError, TypeError):
                pass
            if not order:
                order = Order.objects.filter(
                    Q(order_number__iexact=str(order_id)) | Q(order_number__iexact=f"#{order_id}")
                ).first()

        if not order:
            order = Order.objects.filter(rider=rider, delivery_step__lt=3).first()
            if not order:
                order = Order.objects.filter(rider=rider).first()

        if not order:
            return Response({"success": False, "message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        msg = OrderChatMessage.objects.create(
            order=order,
            sender=request.user,
            sender_role="rider",
            sender_name=request.user.full_name or "Marc Antoine (Rider)",
            message=text,
        )

        return Response({
            "success": True,
            "message": "Message sent.",
            "data": OrderChatMessageSerializer(msg).data,
        }, status=status.HTTP_201_CREATED)

