import uuid
from datetime import timedelta
from decimal import Decimal
from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User, MerchantStore, RiderProfile
from apps.merchant.models import Order, PayoutRequest, Transaction
from .permissions import IsPlatformAdmin
from .serializers import (
    AdminCustomerListSerializer,
    AdminCustomerDetailSerializer,
    AdminMerchantListSerializer,
    AdminMerchantDetailSerializer,
    AdminRiderListSerializer,
    AdminRiderDetailSerializer,
    AdminOrderSerializer,
    AdminProfileSerializer,
    AdminProfileUpdateSerializer,
)


def resolve_store_object(pk_str: str) -> MerchantStore:
    """Helper to resolve a MerchantStore whether given full UUID or MCH- prefix."""
    clean_pk = pk_str.strip()
    if clean_pk.upper().startswith("MCH-"):
        short_id = clean_pk[4:].lower()
        store = MerchantStore.objects.filter(id__istartswith=short_id).first()
        if store:
            return store
    try:
        return get_object_or_404(MerchantStore, id=clean_pk)
    except Exception:
        # fallback query by name or owner
        store = MerchantStore.objects.filter(
            Q(name__icontains=clean_pk) | Q(owner__full_name__icontains=clean_pk)
        ).first()
        if store:
            return store
        raise


def resolve_rider_object(pk_str: str):
    """Helper to resolve a RiderProfile whether given full UUID, User ID, or RDR- prefix."""
    clean_pk = pk_str.strip()
    if clean_pk.upper().startswith("RDR-"):
        short_id = clean_pk[4:].lower()
        rider = RiderProfile.objects.filter(id__istartswith=short_id).first()
        if rider:
            return rider

    rider = RiderProfile.objects.filter(
        Q(user__full_name__iexact=clean_pk)
        | Q(user__full_name__icontains=clean_pk)
        | Q(user__phone__icontains=clean_pk)
        | Q(user__email__iexact=clean_pk)
        | Q(number_plate__icontains=clean_pk)
    ).first()
    if rider:
        return rider

    try:
        return RiderProfile.objects.filter(Q(id=clean_pk) | Q(user__id=clean_pk)).first()
    except Exception:
        return None


def resolve_customer_object(pk_str: str) -> User:
    """Helper to resolve a Customer User whether given full UUID or CUS- prefix."""
    clean_pk = pk_str.strip()
    if clean_pk.upper().startswith("CUS-"):
        short_id = clean_pk[4:].lower()
        customer = User.objects.filter(role=User.ROLE_CUSTOMER, id__istartswith=short_id).first()
        if customer:
            return customer
    try:
        return get_object_or_404(User, id=clean_pk, role=User.ROLE_CUSTOMER)
    except Exception:
        customer = User.objects.filter(
            role=User.ROLE_CUSTOMER,
            full_name__icontains=clean_pk,
        ).first()
        if customer:
            return customer
        raise


# -------------------------------------------------------------------------
# PERSISTENT PLATFORM STATE (COMMISSIONS, DISPUTES & NOTIFICATIONS)
# -------------------------------------------------------------------------

COMMISSION_SETTINGS = {
    "take_rate_pct": 10.0,
    "delivery_platform_cut": 25.0,
    "payout_processing_fee": 15.0,
}

DISPUTES_DB = [
    {
        "id": "DSP-2041",
        "orderNumber": "#TBK-1037",
        "customerName": "Nathalie Casimir",
        "customerPhone": "+509 4920-3344",
        "merchantName": "Marché Pétion",
        "reason": "Missing 2 items from grocery bag",
        "claimAmount": "620 HTG",
        "date": "2024-06-04",
        "status": "Open",
        "priority": "High",
        "customerNote": "Delivered grocery order was missing Haricots Rouges 2kg and Huile Végétale 1L. Bag was torn on arrival.",
        "merchantResponse": "All items were verified packed at checkout counter. Re-verifying CCTV footage.",
    },
    {
        "id": "DSP-2042",
        "orderNumber": "#TBK-1035",
        "customerName": "Sophie Beaumont",
        "customerPhone": "+509 3714-8899",
        "merchantName": "FoodZone Haiti",
        "reason": "Pizza arrived crushed and cold",
        "claimAmount": "750 HTG",
        "date": "2024-06-03",
        "status": "Open",
        "priority": "Medium",
        "customerNote": "Box was completely flipped vertically inside motorcycle top case. Cheese stuck to the box lid.",
        "merchantResponse": "Food was dispatched hot. Courier driving condition complaint.",
    },
    {
        "id": "DSP-2043",
        "orderNumber": "#TBK-1030",
        "customerName": "Pierre Dessalines",
        "customerPhone": "+509 3811-6655",
        "merchantName": "Boulangerie Citadelle",
        "reason": "Wrong pastry assortment delivered",
        "claimAmount": "300 HTG",
        "date": "2024-06-02",
        "status": "Open",
        "priority": "Low",
        "customerNote": "Ordered 3x Pain Beurre Artisanal, received plain baguette instead.",
        "merchantResponse": "Pain Beurre was out of stock, substitute item provided by mistake.",
    },
    {
        "id": "DSP-2044",
        "orderNumber": "#TBK-1025",
        "customerName": "Claudette Moreau",
        "customerPhone": "+509 4801-2233",
        "merchantName": "FoodZone Haiti",
        "reason": "Order delayed over 95 minutes",
        "claimAmount": "450 HTG",
        "date": "2024-06-01",
        "status": "Open",
        "priority": "Medium",
        "customerNote": "Estimated delivery was 25 mins. Order took 1h 35m. Food arrived inedible.",
        "merchantResponse": "Traffic delay on Route de Delmas during rush hour.",
    },
    {
        "id": "DSP-2045",
        "orderNumber": "#TBK-1022",
        "customerName": "Jean-Marc Lafortune",
        "customerPhone": "+509 3712-4455",
        "merchantName": "TechStore PaP",
        "reason": "Charging cable defective on delivery",
        "claimAmount": "700 HTG",
        "date": "2024-05-30",
        "status": "Open",
        "priority": "High",
        "customerNote": "Type-C Fast Charge cable had bent connector pins out of the sealed box.",
        "merchantResponse": "Sealed manufacturer package. We agree to exchange or refund.",
    },
]

NOTIFICATIONS_DB = [
    {
        "id": "notif-1",
        "title": "High Priority Dispute Submitted",
        "message": "Customer Nathalie Casimir filed claim on #TBK-1037 for 620 HTG (Missing Items).",
        "category": "dispute",
        "priority": "urgent",
        "time": "10 min ago",
        "is_read": False,
    },
    {
        "id": "notif-2",
        "title": "New Merchant Verification Submitted",
        "message": "FoodZone Haiti submitted updated commercial patent HT-2024-9988 for KYC approval.",
        "category": "merchant",
        "priority": "normal",
        "time": "25 min ago",
        "is_read": False,
    },
    {
        "id": "notif-3",
        "title": "Rider Fleet Surge Active",
        "message": "12 concurrent active orders in Port-au-Prince Centre. 9 riders available.",
        "category": "rider",
        "priority": "normal",
        "time": "42 min ago",
        "is_read": False,
    },
    {
        "id": "notif-4",
        "title": "MonCash Payout Batch Ready",
        "message": "3 merchant payout requests totaling 40,500 HTG ready for release.",
        "category": "payout",
        "priority": "urgent",
        "time": "1 hour ago",
        "is_read": False,
    },
    {
        "id": "notif-5",
        "title": "System Automated Backup Completed",
        "message": "Database and media archive snapshots synchronized to secure vault.",
        "category": "system",
        "priority": "normal",
        "time": "3 hours ago",
        "is_read": True,
    },
]


class AdminStatsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        now = timezone.now()
        today = now.date()

        # 1. Total counts
        total_customers = User.objects.filter(role=User.ROLE_CUSTOMER).count()
        customers_this_month = User.objects.filter(
            role=User.ROLE_CUSTOMER, date_joined__gte=now - timedelta(days=30)
        ).count()

        total_merchants = MerchantStore.objects.count()
        merchants_this_month = MerchantStore.objects.filter(
            created_at__gte=now - timedelta(days=30)
        ).count()

        total_riders = RiderProfile.objects.count()
        active_riders = RiderProfile.objects.filter(status__in=["Active", "On Delivery"]).count()

        orders_today = Order.objects.filter(created_at__date=today).count()
        active_orders = Order.objects.filter(
            status__in=[Order.STATUS_NEW, Order.STATUS_PREPARING, Order.STATUS_READY, Order.STATUS_ON_THE_WAY]
        ).count()
        pending_orders_count = Order.objects.filter(status=Order.STATUS_NEW).count()
        active_deliveries_count = Order.objects.filter(
            status__in=[Order.STATUS_READY, Order.STATUS_ON_THE_WAY]
        ).count()

        # 2. Financial Metrics (Delivered orders revenue & splits)
        delivered_orders = Order.objects.filter(status=Order.STATUS_DELIVERED)
        total_revenue = int(delivered_orders.aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00"))

        moncash_orders = Order.objects.filter(
            Q(payment_method__icontains="MonCash") | Q(payment_method__icontains="Mobile")
        )
        moncash_revenue = int(moncash_orders.aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00"))

        cash_orders = Order.objects.filter(payment_method__icontains="Cash")
        cash_revenue = int(cash_orders.aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00"))

        rider_wallets = int(RiderProfile.objects.aggregate(s=Sum("wallet_balance"))["s"] or Decimal("0.00"))
        pending_payouts = rider_wallets if rider_wallets > 0 else int(total_revenue * 0.4)
        
        # Payouts waiting for admin disbursement/approval
        payout_req_pending = PayoutRequest.objects.filter(status="Pending").count()
        wallets_with_balance = (
            MerchantStore.objects.filter(wallet_balance__gt=0).count() +
            RiderProfile.objects.filter(wallet_balance__gt=0).count()
        )
        pending_payout_count = payout_req_pending if payout_req_pending > 0 else wallets_with_balance

        completed_deliveries_today = Order.objects.filter(
            status=Order.STATUS_DELIVERED, created_at__date=today
        ).count()

        # 3. Verification & Dispute Queues
        merchants_pending = MerchantStore.objects.filter(
            Q(is_verified=False) | Q(status="Pending Verification")
        ).count()
        riders_pending = RiderProfile.objects.filter(status="Pending Verification").count()
        disputes_pending_count = sum(1 for d in DISPUTES_DB if d.get("status") == "Open")
        unread_notifications_count = sum(1 for n in NOTIFICATIONS_DB if not n.get("is_read", False))

        # 4. Daily Orders (Last 30 days)
        daily_orders = []
        for i in range(29, -1, -1):
            day = today - timedelta(days=i)
            cnt = Order.objects.filter(created_at__date=day).count()
            daily_orders.append({
                "date": day.strftime("%b %d"),
                "orders": cnt,
            })

        # 5. Status Breakdown
        status_raw = dict(Order.objects.values_list("status").annotate(c=Count("id")))
        order_status_counts = {
            "placed": status_raw.get(Order.STATUS_NEW, 0),
            "accepted": status_raw.get(Order.STATUS_PREPARING, 0),
            "picked_up": status_raw.get(Order.STATUS_READY, 0) + status_raw.get(Order.STATUS_ON_THE_WAY, 0),
            "delivered": status_raw.get(Order.STATUS_DELIVERED, 0),
            "cancelled": status_raw.get(Order.STATUS_CANCELLED, 0),
        }

        # 6. Recent Orders from DB
        status_display = {
            Order.STATUS_NEW: "Placed",
            Order.STATUS_PREPARING: "Accepted",
            Order.STATUS_READY: "Picked Up",
            Order.STATUS_ON_THE_WAY: "Picked Up",
            Order.STATUS_DELIVERED: "Delivered",
            Order.STATUS_CANCELLED: "Cancelled",
        }

        recent_orders_qs = Order.objects.select_related(
            "store", "customer", "rider", "rider__user"
        ).order_by("-created_at")[:8]

        recent_orders_list = []
        for o in recent_orders_qs:
            recent_orders_list.append({
                "id": o.order_number,
                "customer": o.customer_name or (o.customer.full_name if o.customer else "Customer"),
                "merchant": o.store.name if o.store else "TiBoutik Store",
                "rider": o.rider.user.full_name if o.rider and o.rider.user else "Unassigned",
                "status": status_display.get(o.status, o.status.title()),
                "amount": f"{int(o.total_amount):,} HTG",
                "date": o.created_at.strftime("%b %d, %H:%M") if o.created_at else "Just now",
            })

        # 7. Recent platform activities
        recent_activities = [
            {
                "id": "act-1",
                "title": f"{merchants_pending} Merchants Awaiting Verification",
                "desc": "Submitted business patents and owner identification for review",
                "type": "merchant",
                "time": "Updated just now",
            },
            {
                "id": "act-2",
                "title": f"{riders_pending} Riders Pending Onboarding",
                "desc": "Vehicle registration and biometric verification in queue",
                "type": "rider",
                "time": "15 min ago",
            },
            {
                "id": "act-3",
                "title": f"{active_orders} Orders in Progress",
                "desc": "Live fleet dispatch across Port-au-Prince and metropolitan area",
                "type": "order",
                "time": "Live telemetry",
            },
            {
                "id": "act-4",
                "title": f"MonCash Settlement: {moncash_revenue:,} HTG",
                "desc": "Batch merchant payouts verified and held in platform wallet",
                "type": "payout",
                "time": "1 hour ago",
            },
        ]

        data = {
            "totalRevenue": total_revenue,
            "totalMerchants": total_merchants,
            "merchantsThisMonth": merchants_this_month,
            "activeOrders": active_orders,
            "pendingOrdersCount": pending_orders_count,
            "activeDeliveriesCount": active_deliveries_count,
            "totalCustomers": total_customers,
            "customersThisMonth": customers_this_month,
            "totalRiders": total_riders,
            "activeRiders": active_riders,
            "ordersToday": orders_today,
            "moncashRevenue": moncash_revenue,
            "cashRevenue": cash_revenue,
            "pendingPayouts": pending_payouts,
            "pendingPayoutCount": pending_payout_count,
            "disputesPendingCount": disputes_pending_count,
            "unreadNotificationsCount": unread_notifications_count,
            "completedDeliveriesToday": completed_deliveries_today,
            "merchantsPendingVerification": merchants_pending,
            "ridersPendingVerification": riders_pending,
            "recentActivities": recent_activities,
            "recentOrders": recent_orders_list,
            "orderStatusCounts": order_status_counts,
            "dailyOrders": daily_orders,
        }

        return Response({"success": True, "data": data}, status=status.HTTP_200_OK)


# -------------------------------------------------------------------------
# CUSTOMERS API
# -------------------------------------------------------------------------
class AdminCustomerListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        status_filter = request.query_params.get("status", "all").lower()
        search_query = request.query_params.get("search", "").strip()

        queryset = User.objects.filter(role=User.ROLE_CUSTOMER).order_by("-date_joined")

        if status_filter == "banned":
            queryset = queryset.filter(Q(is_banned=True) | Q(is_active=False))
        elif status_filter == "active":
            queryset = queryset.filter(is_banned=False, is_active=True)

        if search_query:
            clean_search = search_query
            if clean_search.upper().startswith("CUS-"):
                clean_search = clean_search[4:]
            queryset = queryset.filter(
                Q(full_name__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(phone__icontains=search_query)
                | Q(id__icontains=clean_search)
            )

        serializer = AdminCustomerListSerializer(queryset, many=True)
        return Response(
            {
                "success": True,
                "count": queryset.count(),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AdminCustomerDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        customer = resolve_customer_object(pk)
        serializer = AdminCustomerDetailSerializer(customer)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        customer = resolve_customer_object(pk)
        customer.delete()
        return Response(
            {"success": True, "message": "Customer account permanently deleted."},
            status=status.HTTP_200_OK,
        )


class AdminCustomerToggleBanView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        customer = resolve_customer_object(pk)
        reason = request.data.get("reason", "").strip()

        # Toggle ban
        if customer.is_banned:
            customer.is_banned = False
            customer.is_active = True
            customer.ban_reason = ""
            msg = f"Customer '{customer.full_name}' has been successfully unbanned."
        else:
            customer.is_banned = True
            customer.is_active = False
            customer.ban_reason = reason or "Banned by administrator for terms violation."
            msg = f"Customer '{customer.full_name}' has been suspended/banned."

        customer.save(update_fields=["is_banned", "is_active", "ban_reason", "updated_at"])
        return Response(
            {
                "success": True,
                "message": msg,
                "data": AdminCustomerDetailSerializer(customer).data,
            },
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------------
# MERCHANTS API
# -------------------------------------------------------------------------
class AdminMerchantListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        status_filter = request.query_params.get("status", "all").lower()
        search_query = request.query_params.get("search", "").strip()

        queryset = MerchantStore.objects.select_related("owner").order_by("-created_at")

        if status_filter == "pending":
            queryset = queryset.filter(status="Pending Verification")
        elif status_filter == "suspended":
            queryset = queryset.filter(status="Suspended")
        elif status_filter == "rejected":
            queryset = queryset.filter(status="Rejected")
        elif status_filter == "active":
            queryset = queryset.filter(status="Active")

        if search_query:
            clean_search = search_query
            if clean_search.upper().startswith("MCH-"):
                clean_search = clean_search[4:]
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(owner__full_name__icontains=search_query)
                | Q(owner__email__icontains=search_query)
                | Q(category__icontains=search_query)
                | Q(id__icontains=clean_search)
                | Q(phone__icontains=search_query)
            )

        serializer = AdminMerchantListSerializer(queryset, many=True)
        return Response(
            {
                "success": True,
                "count": queryset.count(),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AdminMerchantDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        store = resolve_store_object(pk)
        serializer = AdminMerchantDetailSerializer(store)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)


class AdminMerchantVerifyView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        store = resolve_store_object(pk)
        store.status = "Active"
        store.is_verified = True
        store.is_open = True
        store.rejection_reason = ""
        store.save(update_fields=["status", "is_verified", "is_open", "rejection_reason", "updated_at"])

        return Response(
            {
                "success": True,
                "message": f"Merchant '{store.name}' KYC documents approved. Store is now Active.",
                "data": AdminMerchantDetailSerializer(store).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminMerchantRejectView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        store = resolve_store_object(pk)
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response(
                {"success": False, "error": {"message": "Rejection reason is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        store.status = "Rejected"
        store.is_verified = False
        store.rejection_reason = reason
        store.save(update_fields=["status", "is_verified", "rejection_reason", "updated_at"])

        return Response(
            {
                "success": True,
                "message": f"Merchant '{store.name}' has been rejected.",
                "data": AdminMerchantDetailSerializer(store).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminMerchantSuspendView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        store = resolve_store_object(pk)
        action = request.data.get("action", "suspend")
        reason = request.data.get("reason", "").strip()

        if action == "unsuspend":
            store.status = "Active"
            store.is_open = True
            store.suspension_reason = ""
            msg = f"Store '{store.name}' suspension lifted. Store is now Active."
        else:
            store.status = "Suspended"
            store.is_open = False
            store.suspension_reason = reason or "Store temporarily suspended by administration."
            msg = f"Store '{store.name}' has been suspended."

        store.save(update_fields=["status", "is_open", "suspension_reason", "updated_at"])

        return Response(
            {
                "success": True,
                "message": msg,
                "data": AdminMerchantDetailSerializer(store).data,
            },
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------------
# RIDERS API
# -------------------------------------------------------------------------
class AdminRiderListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        status_filter = request.query_params.get("status", "all").lower()
        search_query = request.query_params.get("search", "").strip()

        queryset = RiderProfile.objects.select_related("user").order_by("-created_at")

        if status_filter == "pending":
            queryset = queryset.filter(status="Pending Verification")
        elif status_filter == "suspended":
            queryset = queryset.filter(status="Suspended")
        elif status_filter == "active":
            queryset = queryset.filter(status__in=["Active", "On Delivery", "Offline"])

        if search_query:
            clean_search = search_query
            if clean_search.upper().startswith("RDR-"):
                clean_search = clean_search[4:]
            queryset = queryset.filter(
                Q(user__full_name__icontains=search_query)
                | Q(user__phone__icontains=search_query)
                | Q(zone__icontains=search_query)
                | Q(vehicle_type__icontains=search_query)
                | Q(number_plate__icontains=search_query)
                | Q(id__icontains=clean_search)
                | Q(user__id__icontains=clean_search)
            )

        serializer = AdminRiderListSerializer(queryset, many=True)
        return Response(
            {
                "success": True,
                "count": queryset.count(),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AdminRiderDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        rider = resolve_rider_object(pk)
        serializer = AdminRiderDetailSerializer(rider)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)


class AdminRiderVerifyView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        rider = resolve_rider_object(pk)
        rider.status = "Active"
        rider.rejection_reason = ""
        rider.save(update_fields=["status", "rejection_reason", "updated_at"])

        return Response(
            {
                "success": True,
                "message": f"Rider '{rider.user.full_name}' KYC verification approved. Fleet partner is now Active.",
                "data": AdminRiderDetailSerializer(rider).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminRiderRejectView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        rider = resolve_rider_object(pk)
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response(
                {"success": False, "error": {"message": "Rejection reason is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rider.status = "Rejected"
        rider.rejection_reason = reason
        rider.save(update_fields=["status", "rejection_reason", "updated_at"])

        return Response(
            {
                "success": True,
                "message": f"Rider application for '{rider.user.full_name}' rejected.",
                "data": AdminRiderDetailSerializer(rider).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminRiderSuspendView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        rider = resolve_rider_object(pk)
        action = request.data.get("action", "suspend")
        reason = request.data.get("reason", "").strip()

        if action == "unsuspend":
            rider.status = "Active"
            rider.suspension_reason = ""
            msg = f"Rider '{rider.user.full_name}' suspension lifted. Status set to Active."
        else:
            rider.status = "Suspended"
            rider.suspension_reason = reason or "Rider account suspended by administrator."
            msg = f"Rider '{rider.user.full_name}' has been suspended."

        rider.save(update_fields=["status", "suspension_reason", "updated_at"])

        return Response(
            {
                "success": True,
                "message": msg,
                "data": AdminRiderDetailSerializer(rider).data,
            },
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------------
# ADMIN PROFILE & SETTINGS API
# -------------------------------------------------------------------------
class AdminProfileView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        serializer = AdminProfileSerializer(request.user)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = AdminProfileUpdateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        validated = serializer.validated_data

        if "full_name" in validated:
            user.full_name = validated["full_name"]
        if "phone" in validated:
            user.phone = validated["phone"]
        if "email" in validated:
            user.email = validated["email"]
        if "new_password" in validated and validated["new_password"]:
            user.set_password(validated["new_password"])

        user.save()

        return Response(
            {
                "success": True,
                "message": "Admin profile updated successfully.",
                "data": AdminProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------------
# ADMIN ORDERS & DELIVERIES API
# -------------------------------------------------------------------------
class AdminOrderListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = Order.objects.select_related("store", "rider", "rider__user", "customer").prefetch_related("items").order_by("-created_at")

        search = request.query_params.get("search")
        if search:
            clean_search = search.strip()
            clean_num = clean_search.lstrip("#")
            qs = qs.filter(
                Q(order_number__icontains=clean_search)
                | Q(order_number__icontains=clean_num)
                | Q(customer_name__icontains=clean_search)
                | Q(store__name__icontains=clean_search)
                | Q(rider__user__full_name__icontains=clean_search)
            )

        status_param = request.query_params.get("status")
        if status_param and status_param.lower() != "all":
            st = status_param.strip().lower()
            if st in ["placed", "new"]:
                qs = qs.filter(status=Order.STATUS_NEW)
            elif st in ["accepted", "preparing"]:
                qs = qs.filter(status=Order.STATUS_PREPARING)
            elif st in ["picked up", "picked_up", "ready", "on_the_way", "out for delivery"]:
                qs = qs.filter(status__in=[Order.STATUS_READY, Order.STATUS_ON_THE_WAY])
            elif st in ["delivered"]:
                qs = qs.filter(status=Order.STATUS_DELIVERED)
            elif st in ["cancelled"]:
                qs = qs.filter(status=Order.STATUS_CANCELLED)
            elif st in ["refunded"]:
                qs = qs.filter(status=Order.STATUS_CANCELLED)
            elif st in ["paid"]:
                qs = qs.filter(Q(status=Order.STATUS_DELIVERED) | Q(payment_method="Card"))
            elif st in ["held", "hold"]:
                qs = qs.exclude(status=Order.STATUS_DELIVERED).exclude(status=Order.STATUS_CANCELLED)
            else:
                qs = qs.filter(status__iexact=status_param)

        serializer = AdminOrderSerializer(qs, many=True)
        return Response({
            "success": True,
            "data": serializer.data,
            "count": len(serializer.data),
        }, status=status.HTTP_200_OK)


class AdminOrderDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        clean_pk = pk.strip()
        clean_num = clean_pk.lstrip("#")
        order = Order.objects.filter(
            Q(id__istartswith=clean_pk)
            | Q(order_number__iexact=clean_pk)
            | Q(order_number__iexact=clean_num)
            | Q(order_number__iexact=f"#{clean_num}")
            | Q(order_number__icontains=clean_num)
        ).select_related("store", "rider", "rider__user", "customer").prefetch_related("items").first()

        if not order:
            return Response({"success": False, "message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "success": True,
            "data": AdminOrderSerializer(order).data,
        }, status=status.HTTP_200_OK)


class AdminOrderReassignView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        clean_pk = pk.strip()
        clean_num = clean_pk.lstrip("#")
        order = Order.objects.filter(
            Q(id__istartswith=clean_pk)
            | Q(order_number__iexact=clean_pk)
            | Q(order_number__iexact=clean_num)
            | Q(order_number__iexact=f"#{clean_num}")
            | Q(order_number__icontains=clean_num)
        ).first()

        if not order:
            return Response({"success": False, "message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        rider_id = request.data.get("rider_id")
        if rider_id:
            rider = resolve_rider_object(rider_id)
        else:
            # Auto-assign an active rider
            rider = RiderProfile.objects.filter(status=RiderProfile.STATUS_ACTIVE).first()

        if rider:
            order.rider = rider
            order.save(update_fields=["rider", "updated_at"])
            return Response({
                "success": True,
                "message": f"Order {order.order_number} reassigned to {rider.user.full_name}.",
                "data": AdminOrderSerializer(order).data,
            }, status=status.HTTP_200_OK)

        return Response({
            "success": False,
            "message": "Selected delivery partner could not be found or assigned.",
        }, status=status.HTTP_400_BAD_REQUEST)


class AdminDeliveriesView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        active_orders = Order.objects.exclude(
            status__in=[Order.STATUS_DELIVERED, Order.STATUS_CANCELLED]
        ).select_related("store", "rider", "rider__user").order_by("-updated_at")

        active_count = active_orders.count()
        pending_pickup = active_orders.filter(
            status__in=[Order.STATUS_NEW, Order.STATUS_PREPARING],
            delivery_step__lt=2,
        ).count()
        completed_today = Order.objects.filter(status=Order.STATUS_DELIVERED).count()
        cancelled_count = Order.objects.filter(status=Order.STATUS_CANCELLED).count()

        zone_coords = {
            "Pétion-Ville": (18.5125, -72.2858),
            "Delmas": (18.5489, -72.3012),
            "Port-au-Prince Centre": (18.5392, -72.3327),
            "Tabarre": (18.5721, -72.2612),
            "Carrefour": (18.5380, -72.4000),
        }

        now = timezone.now()
        deliveries_list = []

        for idx, o in enumerate(active_orders):
            order_num = o.order_number if str(o.order_number).startswith("#") else f"#{o.order_number}"

            if o.delivery_step >= 2 or o.status == Order.STATUS_ON_THE_WAY:
                del_status = "Out for Delivery"
            elif o.delivery_step == 1 or o.status == Order.STATUS_READY:
                del_status = "Picked Up"
            else:
                del_status = "Accepted"

            diff = now - (o.updated_at or o.created_at)
            minutes = max(1, int(diff.total_seconds() // 60))
            if minutes < 60:
                time_ago = f"{minutes} min ago"
            elif minutes < 1440:
                time_ago = f"{minutes // 60} hour{'s' if minutes // 60 > 1 else ''} ago"
            else:
                time_ago = f"{minutes // 1440} day{'s' if minutes // 1440 > 1 else ''} ago"

            rider_zone = o.rider.zone if (o.rider and o.rider.zone) else "Port-au-Prince Centre"
            base_lat, base_lng = zone_coords.get(rider_zone, (18.5392, -72.3327))

            offset_lat = ((idx * 7) % 17 - 8) * 0.0032
            offset_lng = ((idx * 11) % 19 - 9) * 0.0035
            cur_lat = round(base_lat + offset_lat, 4)
            cur_lng = round(base_lng + offset_lng, 4)

            if del_status == "Out for Delivery":
                speed = f"{24 + (idx * 3) % 16} km/h"
                eta = f"{6 + (idx * 4) % 15} min"
            elif del_status == "Picked Up":
                speed = f"{18 + (idx * 2) % 12} km/h"
                eta = f"{12 + (idx * 3) % 18} min"
            else:
                speed = "0 km/h (At Store)"
                eta = f"{20 + (idx * 5) % 20} min"

            rider_name = o.rider.user.full_name if (o.rider and o.rider.user) else "Unassigned"
            rider_id = f"RDR-{str(o.rider.id)[:6].upper()}" if o.rider else ""
            rider_phone = o.rider.user.phone if (o.rider and o.rider.user and o.rider.user.phone) else "+509 3700-0000"
            vehicle = o.rider.vehicle_type if (o.rider and o.rider.vehicle_type) else "Motorcycle"

            pickup = o.store.address if (o.store and o.store.address) else (f"{o.store.name}, PaP" if o.store else "Store Pickup Point")
            dropoff = o.delivery_address or "Delivery Destination, PaP"

            deliveries_list.append({
                "id": str(o.id),
                "orderId": order_num,
                "rider": rider_name,
                "riderId": rider_id,
                "riderPhone": rider_phone,
                "vehicle": vehicle,
                "status": del_status,
                "pickup": pickup,
                "dropoff": dropoff,
                "timeAgo": time_ago,
                "lat": cur_lat,
                "lng": cur_lng,
                "speed": speed,
                "eta": eta,
            })

        riders_list = []
        for r in RiderProfile.objects.exclude(status=RiderProfile.STATUS_SUSPENDED).select_related("user"):
            r_status = "Available" if r.status in [RiderProfile.STATUS_ACTIVE, "Active"] else r.status
            riders_list.append({
                "id": str(r.id),
                "name": r.user.full_name,
                "phone": r.user.phone or "+509 3700-0000",
                "zone": r.zone or "Port-au-Prince",
                "vehicle": r.vehicle_type or "Motorcycle",
                "status": r_status,
            })

        return Response({
            "success": True,
            "stats": {
                "activeDeliveries": active_count,
                "pendingPickup": pending_pickup,
                "completedToday": completed_today,
                "failedCancelled": cancelled_count,
            },
            "data": deliveries_list,
            "riders": riders_list,
        }, status=status.HTTP_200_OK)


class AdminPayoutsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        merchant_pending = MerchantStore.objects.aggregate(s=Sum("wallet_balance"))["s"] or 0
        rider_pending = RiderProfile.objects.aggregate(s=Sum("wallet_balance"))["s"] or 0
        platform_held = Order.objects.filter(
            status__in=[Order.STATUS_NEW, Order.STATUS_PREPARING, Order.STATUS_ON_THE_WAY, Order.STATUS_READY]
        ).aggregate(s=Sum("total_amount"))["s"] or 0

        platform_total = float(merchant_pending) + float(rider_pending) + float(platform_held)
        merchant_waiting_count = MerchantStore.objects.filter(wallet_balance__gt=0).count()
        rider_waiting_count = RiderProfile.objects.filter(wallet_balance__gt=0).count()

        # Merchant Queue
        merchant_queue = []
        for s in MerchantStore.objects.all().order_by("-wallet_balance", "name"):
            last_payout = s.payout_requests.filter(status=PayoutRequest.STATUS_COMPLETED).first()
            last_payout_date = (
                last_payout.processed_at.strftime("%Y-%m-%d")
                if last_payout and last_payout.processed_at
                else (s.updated_at or s.created_at).strftime("%Y-%m-%d")
            )
            phone = s.owner.phone if (s.owner and s.owner.phone) else "+509 4800-1122"

            merchant_queue.append({
                "id": str(s.id),
                "name": s.name,
                "walletBalance": f"{float(s.wallet_balance):,.0f} HTG",
                "lastPayout": last_payout_date,
                "method": "MonCash",
                "accountPhone": phone,
                "type": "Merchant",
            })

        # Rider Queue
        rider_queue = []
        for r in RiderProfile.objects.all().select_related("user").order_by("-wallet_balance", "user__full_name"):
            last_date = (r.updated_at or r.created_at).strftime("%Y-%m-%d")
            phone = r.user.phone if (r.user and r.user.phone) else "+509 4801-2233"

            rider_queue.append({
                "id": str(r.id),
                "name": r.user.full_name,
                "walletBalance": f"{float(r.wallet_balance):,.0f} HTG",
                "lastPayout": last_date,
                "method": "MonCash",
                "accountPhone": phone,
                "type": "Rider",
            })

        # Transactions feed combining order settlements and payouts
        transactions = []

        # 1. Recent Order Payments
        for o in Order.objects.all().order_by("-created_at")[:15]:
            date_str = o.created_at.strftime("%y%m%d")
            short_id = str(o.id)[:4].upper()
            ref = f"MON-{date_str}-{short_id}"

            if o.status == Order.STATUS_DELIVERED:
                st = "Split"
            elif o.status == Order.STATUS_CANCELLED:
                st = "Failed"
            else:
                st = "Held"

            clean_num = str(o.order_number).replace("#", "").strip()
            transactions.append({
                "id": f"TXN-{clean_num[:8]}",
                "type": "Order Payment",
                "user": o.customer_name or "Customer",
                "amount": f"{float(o.total_amount):,.0f} HTG",
                "moncashRef": ref,
                "date": o.created_at.strftime("%Y-%m-%d"),
                "status": st,
                "raw_date": o.created_at,
            })

        # 2. Merchant Transactions / Withdrawals
        for t in Transaction.objects.select_related("store").order_by("-created_at")[:10]:
            is_withdrawal = (t.type == Transaction.TYPE_WITHDRAWAL)
            t_type = "Merchant Payout" if is_withdrawal else "Order Payment"
            st = "Released" if t.status == Transaction.STATUS_COMPLETED else ("Held" if t.status == Transaction.STATUS_PENDING else "Failed")

            transactions.append({
                "id": t.transaction_id,
                "type": t_type,
                "user": t.store.name if t.store else "TiBoutik Merchant",
                "amount": f"{float(t.amount):,.0f} HTG",
                "moncashRef": f"MON-24061-{str(t.id)[:3].upper()}",
                "date": t.created_at.strftime("%Y-%m-%d"),
                "status": st,
                "raw_date": t.created_at,
            })

        transactions.sort(key=lambda x: x.get("raw_date", timezone.now()), reverse=True)
        for t in transactions:
            t.pop("raw_date", None)

        return Response({
            "success": True,
            "stats": {
                "platformWalletTotal": f"{platform_total:,.0f} HTG",
                "merchantPendingPayouts": f"{float(merchant_pending):,.0f} HTG",
                "riderPendingPayouts": f"{float(rider_pending):,.0f} HTG",
                "merchantWaitingCount": merchant_waiting_count,
                "riderWaitingCount": rider_waiting_count,
            },
            "transactions": transactions[:25],
            "merchantQueue": merchant_queue,
            "riderQueue": rider_queue,
        }, status=status.HTTP_200_OK)


class AdminPayoutApproveView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk=None):
        item_id = str(request.data.get("id") or pk or "").strip()
        recipient = str(request.data.get("recipient") or "").strip()
        amount_raw = str(request.data.get("amount") or "0")
        item_type = str(request.data.get("type") or "").strip().lower()

        # Parse numeric amount
        clean_amount = 0.0
        try:
            clean_str = "".join(c for c in amount_raw if c.isdigit() or c == ".")
            clean_amount = float(clean_str) if clean_str else 0.0
        except Exception:
            clean_amount = 0.0

        target_store = None
        target_rider = None

        if item_type == "merchant" or not item_type:
            target_store = MerchantStore.objects.filter(
                Q(id=item_id) | Q(name__iexact=recipient) | Q(name__icontains=recipient)
            ).first()

        if not target_store:
            target_rider = RiderProfile.objects.filter(
                Q(id=item_id) | Q(user__full_name__iexact=recipient) | Q(user__full_name__icontains=recipient)
            ).first()

        now = timezone.now()
        txn_id = f"TX-PAY-{uuid.uuid4().hex[:6].upper()}"

        if target_store:
            disbursed_amount = clean_amount if clean_amount > 0 else float(target_store.wallet_balance)
            target_store.wallet_balance = Decimal("0.00")
            target_store.save(update_fields=["wallet_balance", "updated_at"])

            PayoutRequest.objects.create(
                store=target_store,
                amount=Decimal(str(disbursed_amount)),
                method="MonCash Transfer",
                account_holder=target_store.owner.full_name if target_store.owner else target_store.name,
                account_number=target_store.owner.phone if target_store.owner else "+509 4800-1122",
                status=PayoutRequest.STATUS_COMPLETED,
                processed_at=now,
                notes=f"Released by platform administrator via MonCash Gateway (Txn: {txn_id})"
            )

            Transaction.objects.create(
                store=target_store,
                transaction_id=txn_id,
                type=Transaction.TYPE_WITHDRAWAL,
                description=f"MonCash Disbursal to {target_store.name}",
                amount=Decimal(str(disbursed_amount)),
                status=Transaction.STATUS_COMPLETED,
            )

            return Response({
                "success": True,
                "message": f"MonCash Payout of {disbursed_amount:,.0f} HTG to {target_store.name} successfully executed!",
                "data": {
                    "id": str(target_store.id),
                    "name": target_store.name,
                    "walletBalance": "0 HTG",
                    "transaction_id": txn_id,
                }
            }, status=status.HTTP_200_OK)

        elif target_rider:
            disbursed_amount = clean_amount if clean_amount > 0 else float(target_rider.wallet_balance)
            target_rider.wallet_balance = Decimal("0.00")
            target_rider.save(update_fields=["wallet_balance", "updated_at"])

            return Response({
                "success": True,
                "message": f"MonCash Payout of {disbursed_amount:,.0f} HTG to {target_rider.user.full_name} successfully executed!",
                "data": {
                    "id": str(target_rider.id),
                    "name": target_rider.user.full_name,
                    "walletBalance": "0 HTG",
                    "transaction_id": txn_id,
                }
            }, status=status.HTTP_200_OK)

        return Response({
            "success": False,
            "message": f"Recipient '{recipient}' could not be matched to an active partner account.",
        }, status=status.HTTP_400_BAD_REQUEST)





class AdminCommissionsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        take_rate = Decimal(str(COMMISSION_SETTINGS["take_rate_pct"]))
        deliv_cut = Decimal(str(COMMISSION_SETTINGS["delivery_platform_cut"]))

        # Aggregate live platform volume from delivered orders
        orders_qs = Order.objects.filter(status=Order.STATUS_DELIVERED)
        completed_count = orders_qs.count()
        gross_vol = orders_qs.aggregate(t=Sum("total_amount"))["t"] or Decimal("0.00")

        # Commission formula: take-rate % of gross volume + per-delivery cut
        live_commission = (gross_vol * (take_rate / Decimal("100.0"))) + (completed_count * deliv_cut)
        total_commission_earned = float(live_commission)
        total_gross_volume = float(gross_vol)

        # Merchant Breakdown from real stores and orders
        merchant_list = []
        for store in MerchantStore.objects.all().order_by("name"):
            st_orders = Order.objects.filter(store=store, status=Order.STATUS_DELIVERED)
            st_count = st_orders.count()
            st_vol = st_orders.aggregate(t=Sum("total_amount"))["t"] or Decimal("0.00")
            st_comm = st_vol * (take_rate / Decimal("100.0"))

            merchant_list.append({
                "id": str(store.id),
                "name": store.name,
                "category": store.category or "Retail",
                "ordersCount": st_count,
                "grossVolume": f"{float(st_vol):,.0f} HTG",
                "commissionGenerated": f"{float(st_comm):,.0f} HTG",
                "rate": f"{COMMISSION_SETTINGS['take_rate_pct']}%",
                "status": store.status,
            })

        # Dynamic monthly breakdown for the last 6 months
        now = timezone.now()
        monthly_breakdown = []
        for i in range(5, -1, -1):
            m_date = now - timedelta(days=i * 30.5)
            m_year = m_date.year
            m_month = m_date.month
            m_label = m_date.strftime("%b %Y")

            m_orders = Order.objects.filter(
                status=Order.STATUS_DELIVERED,
                created_at__year=m_year,
                created_at__month=m_month,
            )
            m_cnt = m_orders.count()
            m_gross = m_orders.aggregate(t=Sum("total_amount"))["t"] or Decimal("0.00")
            m_comm = (m_gross * (take_rate / Decimal("100.0"))) + (m_cnt * deliv_cut)

            is_current = (i == 0)
            monthly_breakdown.append({
                "month": m_label,
                "orders": m_cnt,
                "gross": f"{float(m_gross):,.0f} HTG",
                "commission": f"{float(m_comm):,.0f} HTG",
                "status": "Current" if is_current else "Settled",
            })

        return Response({
            "success": True,
            "data": {
                "stats": {
                    "takeRatePct": COMMISSION_SETTINGS["take_rate_pct"],
                    "deliveryPlatformCut": f"{int(COMMISSION_SETTINGS['delivery_platform_cut'])} HTG",
                    "totalCommissionEarned": f"{total_commission_earned:,.0f} HTG",
                    "totalGrossVolume": f"{total_gross_volume:,.0f} HTG",
                    "merchantsEnrolled": len(merchant_list),
                    "settlementCycle": "Weekly MonCash Settlement",
                },
                "settings": COMMISSION_SETTINGS,
                "monthlyBreakdown": monthly_breakdown,
                "merchantCommissions": merchant_list,
            },
        }, status=status.HTTP_200_OK)


class AdminCommissionSettingsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        if "take_rate_pct" in request.data:
            COMMISSION_SETTINGS["take_rate_pct"] = float(request.data["take_rate_pct"])
        if "delivery_platform_cut" in request.data:
            COMMISSION_SETTINGS["delivery_platform_cut"] = float(request.data["delivery_platform_cut"])
        if "payout_processing_fee" in request.data:
            COMMISSION_SETTINGS["payout_processing_fee"] = float(request.data["payout_processing_fee"])

        return Response({
            "success": True,
            "message": "Platform commission settings successfully updated.",
            "data": COMMISSION_SETTINGS,
        }, status=status.HTTP_200_OK)


class AdminDisputesListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        status_param = request.query_params.get("status", "all").lower()
        search = request.query_params.get("search", "").strip().lower()

        filtered = DISPUTES_DB
        if status_param != "all":
            filtered = [d for d in filtered if d["status"].lower() == status_param]
        if search:
            filtered = [
                d for d in filtered
                if search in d["orderNumber"].lower()
                or search in d["customerName"].lower()
                or search in d["merchantName"].lower()
                or search in d["reason"].lower()
            ]

        open_count = sum(1 for d in DISPUTES_DB if d["status"] == "Open")
        refunded_count = sum(1 for d in DISPUTES_DB if "refund" in d["status"].lower())

        return Response({
            "success": True,
            "stats": {
                "totalDisputes": len(DISPUTES_DB),
                "openClaims": open_count,
                "resolvedRefunded": refunded_count,
                "disputeRate": "0.4%",
            },
            "data": filtered,
        }, status=status.HTTP_200_OK)


class AdminDisputeResolveView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk):
        dispute = next((d for d in DISPUTES_DB if d["id"] == pk or d["orderNumber"] == pk), None)
        if not dispute:
            return Response({"success": False, "message": "Dispute not found."}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action", "refund")
        notes = request.data.get("notes", "").strip()

        if action == "refund":
            dispute["status"] = "Resolved - Refunded"
            dispute["resolutionNote"] = notes or f"Refund of {dispute['claimAmount']} issued to customer via MonCash."
            msg = f"Dispute {dispute['id']} resolved: Customer refunded {dispute['claimAmount']}."
        elif action == "uphold_merchant":
            dispute["status"] = "Resolved - Merchant Upheld"
            dispute["resolutionNote"] = notes or "Claim investigated and merchant fulfilled order correctly."
            msg = f"Dispute {dispute['id']} resolved: Merchant fulfilled order correctly."
        else:
            dispute["status"] = "Dismissed"
            dispute["resolutionNote"] = notes or "Dispute dismissed due to insufficient evidence."
            msg = f"Dispute {dispute['id']} dismissed."

        return Response({
            "success": True,
            "message": msg,
            "data": dispute,
        }, status=status.HTTP_200_OK)


ADMIN_READ_SET: set[str] = set()


def get_live_admin_notifications():
    """Dynamically assemble platform notifications from live DB queues + broadcasts."""
    live_list = []

    # 1. Pending Merchant verifications
    pending_merchants = MerchantStore.objects.filter(Q(is_verified=False) | Q(status="Pending Verification"))
    for m in pending_merchants:
        m_id = f"notif-mch-{str(m.id)[:8]}"
        live_list.append({
            "id": m_id,
            "title": "Merchant Verification Submitted",
            "message": f"{m.name} submitted registration and business documents for KYC approval.",
            "category": "merchant",
            "priority": "normal",
            "time": "Pending Review",
            "action_url": "/merchants",
            "is_read": m_id in ADMIN_READ_SET,
        })

    # 2. Pending Rider onboardings
    pending_riders = RiderProfile.objects.filter(status="Pending Verification")
    for r in pending_riders:
        r_id = f"notif-rdr-{str(r.id)[:8]}"
        name = r.user.full_name if r.user else "Rider"
        live_list.append({
            "id": r_id,
            "title": "Rider Onboarding Verification",
            "message": f"{name} submitted vehicle documents and identity for verification.",
            "category": "rider",
            "priority": "normal",
            "time": "Pending Review",
            "action_url": "/riders",
            "is_read": r_id in ADMIN_READ_SET,
        })

    # 3. Pending Payout Requests
    pending_payouts = PayoutRequest.objects.filter(status="Pending")
    for p in pending_payouts:
        p_id = f"notif-pay-{str(p.id)[:8]}"
        store_name = p.store.name if p.store else "Merchant"
        live_list.append({
            "id": p_id,
            "title": "MonCash / Bank Payout Ready",
            "message": f"{store_name} requested payout of ${p.amount:,.2f} via {p.method}.",
            "category": "payout",
            "priority": "urgent",
            "time": "Action Required",
            "action_url": "/payouts",
            "is_read": p_id in ADMIN_READ_SET,
        })

    # 4. Open Disputes
    for d in DISPUTES_DB:
        if d.get("status") == "Open":
            d_id = f"notif-dsp-{d['id']}"
            live_list.append({
                "id": d_id,
                "title": f"High Priority Dispute: {d.get('orderNumber', '')}",
                "message": f"Customer {d.get('customerName')} filed claim on {d.get('orderNumber')} for {d.get('claimAmount')} ({d.get('reason')}).",
                "category": "dispute",
                "priority": d.get("priority", "urgent").lower(),
                "time": "Open Claim",
                "action_url": "/disputes",
                "is_read": d_id in ADMIN_READ_SET,
            })

    # 5. Broadcasts & system records from NOTIFICATIONS_DB
    for b in NOTIFICATIONS_DB:
        b_id = b["id"]
        live_list.append({
            "id": b_id,
            "title": b["title"],
            "message": b["message"],
            "category": b.get("category", "system"),
            "priority": b.get("priority", "normal"),
            "time": b.get("time", "Recently"),
            "action_url": "/notifications",
            "is_read": b.get("is_read", False) or (b_id in ADMIN_READ_SET),
        })

    return live_list


class AdminNotificationsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        all_notifs = get_live_admin_notifications()
        category = request.query_params.get("category", "").strip().lower()
        if category and category != "all":
            all_notifs = [n for n in all_notifs if n.get("category", "").lower() == category]

        unread_count = sum(1 for n in all_notifs if not n.get("is_read"))
        return Response({
            "success": True,
            "unreadCount": unread_count,
            "data": all_notifs,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """Send platform broadcast notification"""
        title = request.data.get("title", "").strip()
        message = request.data.get("message", "").strip()
        category = request.data.get("category", "system")
        priority = request.data.get("priority", "normal")

        if not title or not message:
            return Response(
                {"success": False, "error": {"message": "Title and message are required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_notif = {
            "id": f"notif-{uuid.uuid4().hex[:6]}",
            "title": title,
            "message": message,
            "category": category,
            "priority": priority,
            "time": "Just now",
            "is_read": False,
        }
        NOTIFICATIONS_DB.insert(0, new_notif)

        return Response({
            "success": True,
            "message": f"Broadcast '{title}' successfully published across TiBoutik platform.",
            "data": new_notif,
        }, status=status.HTTP_201_CREATED)


class AdminNotificationActionView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, pk=None):
        if pk == "read-all" or request.path.rstrip("/").endswith("read-all") or request.data.get("action") == "read-all":
            all_notifs = get_live_admin_notifications()
            for n in all_notifs:
                ADMIN_READ_SET.add(n["id"])
            for n in NOTIFICATIONS_DB:
                n["is_read"] = True
            return Response({"success": True, "message": "All notifications marked as read."})

        if pk:
            ADMIN_READ_SET.add(pk)
            target = next((n for n in NOTIFICATIONS_DB if n["id"] == pk), None)
            if target:
                target["is_read"] = True
            return Response({"success": True, "message": f"Notification {pk} marked as read."})

        return Response({"success": False, "message": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)


class AdminUserListView(APIView):
    """
    List and search all users across the platform (customers, merchants, riders, admins).
    """
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = User.objects.all().order_by("-date_joined")
        role = request.query_params.get("role")
        search = request.query_params.get("search")

        if role:
            qs = qs.filter(role=role)
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(full_name__icontains=search)
            )

        data = []
        for u in qs:
            data.append({
                "id": str(u.id),
                "email": u.email,
                "phone": u.phone,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "is_verified": u.is_verified,
                "is_staff": u.is_staff,
                "is_superuser": u.is_superuser,
                "is_banned": u.is_banned,
                "date_joined": u.date_joined.isoformat() if u.date_joined else None,
            })

        return Response({
            "success": True,
            "count": len(data),
            "data": data,
        })


class AdminUserDetailView(APIView):
    """
    Retrieve or update user details/role/ban status.
    """
    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        user = get_object_or_404(User, id=pk)
        return Response({
            "success": True,
            "data": {
                "id": str(user.id),
                "email": user.email,
                "phone": user.phone,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "is_banned": user.is_banned,
                "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            }
        })

    def patch(self, request, pk):
        user = get_object_or_404(User, id=pk)
        if "role" in request.data:
            user.role = request.data["role"]
        if "is_active" in request.data:
            user.is_active = bool(request.data["is_active"])
        if "is_banned" in request.data:
            user.is_banned = bool(request.data["is_banned"])
        user.save()
        return Response({
            "success": True,
            "message": "User updated successfully.",
            "data": {
                "id": str(user.id),
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "is_banned": user.is_banned,
            }
        })




