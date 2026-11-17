import uuid
from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import Product, ProductVariant, Order, OrderItem, PayoutRequest, Transaction
from .permissions import IsMerchantUser
from .serializers import (
    ProductSerializer,
    ProductCreateUpdateSerializer,
    StockAdjustmentSerializer,
    OrderSerializer,
    OrderStatusUpdateSerializer,
    PayoutRequestSerializer,
    TransactionSerializer,
)


class BaseMerchantAPIView(APIView):
    permission_classes = [IsAuthenticated, IsMerchantUser]

    def get_store(self, request):
        try:
            return request.user.merchant_store
        except Exception:
            from apps.users.models import MerchantStore
            store, _ = MerchantStore.objects.get_or_create(
                owner=request.user,
                defaults={
                    "name": f"{request.user.full_name}'s Store" if request.user.full_name else "TiBoutik Store",
                    "category": MerchantStore.CATEGORY_GROCERY,
                    "address": "Port-au-Prince, Haiti",
                    "account_holder": request.user.full_name or "Store Owner",
                    "status": MerchantStore.STATUS_ACTIVE,
                },
            )
            return store


class MerchantDashboardView(BaseMerchantAPIView):
    """
    Returns high-level store stats and recent orders for the merchant dashboard.
    """
    @extend_schema(summary="Merchant dashboard metrics and recent orders")
    def get(self, request):
        store = self.get_store(request)
        today = timezone.now().date()

        # Today's orders
        today_orders = Order.objects.filter(store=store, created_at__date=today)
        today_sales_val = today_orders.exclude(status=Order.STATUS_CANCELLED).aggregate(
            total=Sum("total_amount")
        )["total"] or Decimal("0.00")

        # Counts
        pending_count = Order.objects.filter(
            store=store, status__in=[Order.STATUS_NEW, Order.STATUS_PREPARING]
        ).count()
        completed_today_count = today_orders.filter(status=Order.STATUS_DELIVERED).count()

        total_products_count = Product.objects.filter(store=store).exclude(status=Product.STATUS_ARCHIVED).count()
        active_products_count = Product.objects.filter(store=store, status=Product.STATUS_ACTIVE).count()

        # Recent orders
        recent_orders_qs = Order.objects.filter(store=store).prefetch_related("items")[:6]
        recent_orders_data = OrderSerializer(recent_orders_qs, many=True, context={"request": request}).data

        return Response({
            "success": True,
            "data": {
                "store_name": store.name,
                "today_sales": float(today_sales_val),
                "today_sales_formatted": f"${today_sales_val:,.2f}",
                "pending_orders": pending_count,
                "completed_today": completed_today_count,
                "active_products": active_products_count,
                "total_products": total_products_count,
                "recent_orders": recent_orders_data,
            }
        })


class MerchantOrderListView(BaseMerchantAPIView):
    """
    List and filter store orders by status tab (new, active, completed, cancelled) or search query.
    """
    @extend_schema(
        summary="List merchant orders with tab filters and search",
        parameters=[
            OpenApiParameter(name="tab", description="Filter tab: new | active | completed | cancelled | all", type=str),
            OpenApiParameter(name="search", description="Search by customer name, order number, or phone", type=str),
        ]
    )
    def get(self, request):
        store = self.get_store(request)
        qs = Order.objects.filter(store=store).prefetch_related("items")

        tab = request.query_params.get("tab", "").lower()
        if tab == "new":
            qs = qs.filter(status=Order.STATUS_NEW)
        elif tab == "active":
            qs = qs.filter(status__in=[Order.STATUS_PREPARING, Order.STATUS_READY, Order.STATUS_ON_THE_WAY])
        elif tab == "completed":
            qs = qs.filter(status=Order.STATUS_DELIVERED)
        elif tab == "cancelled":
            qs = qs.filter(status=Order.STATUS_CANCELLED)

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(order_number__icontains=search) |
                Q(customer_name__icontains=search) |
                Q(customer_phone__icontains=search) |
                Q(customer_email__icontains=search)
            )

        serializer = OrderSerializer(qs, many=True, context={"request": request})
        return Response({
            "success": True,
            "count": qs.count(),
            "data": serializer.data,
        })


class MerchantOrderDetailView(BaseMerchantAPIView):
    """
    Retrieve single order details.
    """
    def get(self, request, pk):
        store = self.get_store(request)
        try:
            order = Order.objects.prefetch_related("items").get(pk=pk, store=store)
        except (Order.DoesNotExist, ValueError):
            return Response(
                {"success": False, "error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OrderSerializer(order, context={"request": request})
        return Response({"success": True, "data": serializer.data})


class MerchantOrderAcceptView(BaseMerchantAPIView):
    """
    Accept a new order: moves status from 'new' to 'preparing'.
    """
    def post(self, request, pk):
        store = self.get_store(request)
        try:
            order = Order.objects.get(pk=pk, store=store)
        except (Order.DoesNotExist, ValueError):
            return Response(
                {"success": False, "error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        order.status = Order.STATUS_PREPARING
        order.save(update_fields=["status", "updated_at"])

        serializer = OrderSerializer(order, context={"request": request})
        return Response({
            "success": True,
            "message": f"Order {order.order_number} accepted and moved to Preparing.",
            "data": serializer.data,
        })


class MerchantOrderRejectView(BaseMerchantAPIView):
    """
    Reject an order: moves status to 'cancelled'.
    """
    def post(self, request, pk):
        store = self.get_store(request)
        try:
            order = Order.objects.get(pk=pk, store=store)
        except (Order.DoesNotExist, ValueError):
            return Response(
                {"success": False, "error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        reason = request.data.get("reason", "").strip() or "Cancelled by merchant"
        order.status = Order.STATUS_CANCELLED
        order.rejection_reason = reason
        order.save(update_fields=["status", "rejection_reason", "updated_at"])

        serializer = OrderSerializer(order, context={"request": request})
        return Response({
            "success": True,
            "message": f"Order {order.order_number} rejected.",
            "data": serializer.data,
        })


class MerchantOrderStatusUpdateView(BaseMerchantAPIView):
    """
    Update order status to preparing, ready, on_the_way, delivered, cancelled.
    """
    def patch(self, request, pk):
        store = self.get_store(request)
        try:
            order = Order.objects.get(pk=pk, store=store)
        except (Order.DoesNotExist, ValueError):
            return Response(
                {"success": False, "error": {"code": "ORDER_NOT_FOUND", "message": "Order not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OrderStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "details": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_status = serializer.validated_data["status"]
        order.status = new_status
        if "rejection_reason" in serializer.validated_data:
            order.rejection_reason = serializer.validated_data["rejection_reason"]
        order.save()

        # If delivered, record transaction earning if not already recorded
        if new_status == Order.STATUS_DELIVERED:
            tx_id = f"TX-ORD-{order.order_number.replace('#', '')}"
            if not Transaction.objects.filter(store=store, transaction_id=tx_id).exists():
                Transaction.objects.create(
                    store=store,
                    transaction_id=tx_id,
                    type=Transaction.TYPE_EARNING,
                    description=f"Order {order.order_number} settlement",
                    amount=order.total_amount,
                    status=Transaction.STATUS_COMPLETED,
                )

        return Response({
            "success": True,
            "message": f"Order status updated to {new_status}.",
            "data": OrderSerializer(order, context={"request": request}).data,
        })


class MerchantProductListCreateView(BaseMerchantAPIView):
    """
    List and create products for the store.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(summary="List merchant products with category/status filters and search")
    def get(self, request):
        store = self.get_store(request)
        qs = Product.objects.filter(store=store).prefetch_related("variants")

        category = request.query_params.get("category", "").strip()
        if category and category.lower() != "all":
            qs = qs.filter(category__iexact=category)

        status_param = request.query_params.get("status", "").strip()
        if status_param and status_param.lower() != "all":
            qs = qs.filter(status__iexact=status_param)

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(sku__icontains=search) |
                Q(description__icontains=search)
            )

        serializer = ProductSerializer(qs, many=True, context={"request": request})
        return Response({
            "success": True,
            "count": qs.count(),
            "data": serializer.data,
        })

    @extend_schema(summary="Create a new merchant product")
    def post(self, request):
        store = self.get_store(request)
        serializer = ProductCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "details": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = serializer.save(store=store)
        return Response({
            "success": True,
            "message": "Product created successfully.",
            "data": ProductSerializer(product, context={"request": request}).data,
        }, status=status.HTTP_201_CREATED)


class MerchantProductDetailView(BaseMerchantAPIView):
    """
    Retrieve, update or delete a product.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_product(self, request, pk):
        store = self.get_store(request)
        return Product.objects.prefetch_related("variants").get(pk=pk, store=store)

    def get(self, request, pk):
        try:
            product = self.get_product(request, pk)
        except (Product.DoesNotExist, ValueError):
            return Response(
                {"success": False, "error": {"code": "PRODUCT_NOT_FOUND", "message": "Product not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"success": True, "data": ProductSerializer(product, context={"request": request}).data})

    def patch(self, request, pk):
        try:
            product = self.get_product(request, pk)
        except (Product.DoesNotExist, ValueError):
            return Response(
                {"success": False, "error": {"code": "PRODUCT_NOT_FOUND", "message": "Product not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProductCreateUpdateSerializer(product, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "details": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_product = serializer.save()
        return Response({
            "success": True,
            "message": "Product updated successfully.",
            "data": ProductSerializer(updated_product, context={"request": request}).data,
        })

    def delete(self, request, pk):
        try:
            product = self.get_product(request, pk)
        except (Product.DoesNotExist, ValueError):
            return Response(
                {"success": False, "error": {"code": "PRODUCT_NOT_FOUND", "message": "Product not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        product.delete()
        return Response({
            "success": True,
            "message": "Product deleted successfully.",
        })


class MerchantProductStockAdjustView(BaseMerchantAPIView):
    """
    Quickly add or remove inventory quantity for a product.
    """
    def post(self, request, pk):
        store = self.get_store(request)
        try:
            product = Product.objects.get(pk=pk, store=store)
        except (Product.DoesNotExist, ValueError):
            return Response(
                {"success": False, "error": {"code": "PRODUCT_NOT_FOUND", "message": "Product not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = StockAdjustmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "details": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action = serializer.validated_data["action"]
        qty = serializer.validated_data["quantity"]

        if action == "add":
            product.stock += qty
        elif action == "remove":
            product.stock = max(0, product.stock - qty)
        elif action == "set":
            product.stock = max(0, qty)

        product.save()

        return Response({
            "success": True,
            "message": f"Stock updated to {product.stock} units.",
            "data": ProductSerializer(product, context={"request": request}).data,
        })


class MerchantInventoryView(BaseMerchantAPIView):
    """
    Summary metrics and inventory stock tracking list.
    """
    @extend_schema(summary="Get inventory summary and stock levels")
    def get(self, request):
        store = self.get_store(request)
        qs = Product.objects.filter(store=store).exclude(status=Product.STATUS_ARCHIVED)

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))

        total_count = qs.count()
        low_stock_count = qs.filter(status=Product.STATUS_LOW_STOCK).count()
        out_of_stock_count = qs.filter(status=Product.STATUS_OUT_OF_STOCK).count()

        items_data = []
        for p in qs:
            image_url = ""
            if p.image:
                image_url = request.build_absolute_uri(p.image.url)
            elif p.image_url_fallback:
                image_url = p.image_url_fallback

            # Format status matching frontend inventory page expectation:
            # "In Stock" | "Low" | "Critical" | "Out"
            inv_status = "In Stock"
            if p.stock <= 0 or p.status == Product.STATUS_OUT_OF_STOCK:
                inv_status = "Out"
            elif p.stock <= 25:
                inv_status = "Critical"
            elif p.stock <= p.min_stock or p.status == Product.STATUS_LOW_STOCK:
                inv_status = "Low"

            items_data.append({
                "id": str(p.id),
                "name": p.name,
                "sku": p.sku,
                "status": inv_status,
                "stock": p.stock,
                "maxStock": p.max_stock or 200,
                "minStock": p.min_stock or 50,
                "image": image_url,
                "price": f"${p.price:.2f}",
                "category": p.category,
            })

        return Response({
            "success": True,
            "summary": {
                "total_products": total_count,
                "low_stock": low_stock_count,
                "out_of_stock": out_of_stock_count,
            },
            "data": items_data,
        })


class MerchantEarningsView(BaseMerchantAPIView):
    """
    Get merchant balances (available, pending, lifetime, withdrawn),
    growth metrics, payout requests, and filtered transaction history.
    """
    def get(self, request):
        store = self.get_store(request)
        now = timezone.now()

        # 1. Reconcile any delivered orders for this store into Transaction ledger if not already recorded
        delivered_orders = Order.objects.filter(store=store, status=Order.STATUS_DELIVERED)
        for order in delivered_orders:
            tx_id = f"TX-ORD-{order.order_number.replace('#', '')}"
            if not Transaction.objects.filter(store=store, transaction_id=tx_id).exists():
                Transaction.objects.create(
                    store=store,
                    transaction_id=tx_id,
                    type=Transaction.TYPE_EARNING,
                    description=f"Order {order.order_number} settlement",
                    amount=order.total_amount,
                    status=Transaction.STATUS_COMPLETED,
                    created_at=order.created_at or now,
                )

        # 2. Financial Totals
        completed_earnings = Transaction.objects.filter(
            store=store, type=Transaction.TYPE_EARNING, status=Transaction.STATUS_COMPLETED
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        withdrawals_total = Transaction.objects.filter(
            store=store, type=Transaction.TYPE_WITHDRAWAL, status__in=[Transaction.STATUS_COMPLETED, Transaction.STATUS_PENDING]
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        completed_withdrawals = Transaction.objects.filter(
            store=store, type=Transaction.TYPE_WITHDRAWAL, status=Transaction.STATUS_COMPLETED
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        # Available Balance:
        # If store.wallet_balance is explicitly set higher than computed, respect wallet_balance
        computed_balance = max(Decimal("0.00"), completed_earnings - withdrawals_total)
        available_balance = max(computed_balance, store.wallet_balance or Decimal("0.00"))

        # Pending Clearance: Active in-progress orders + pending earning transactions
        active_orders_amount = Order.objects.filter(
            store=store,
            status__in=[Order.STATUS_NEW, Order.STATUS_PREPARING, Order.STATUS_READY, Order.STATUS_ON_THE_WAY]
        ).aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")

        pending_tx_amount = Transaction.objects.filter(
            store=store, type=Transaction.TYPE_EARNING, status=Transaction.STATUS_PENDING
        ).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

        pending_clearance = active_orders_amount + pending_tx_amount
        pending_orders_count = Order.objects.filter(
            store=store,
            status__in=[Order.STATUS_NEW, Order.STATUS_PREPARING, Order.STATUS_READY, Order.STATUS_ON_THE_WAY]
        ).count()

        lifetime_earnings = completed_earnings

        # Growth calculation (last 30 days vs prior 30 days)
        last_30_earnings = Transaction.objects.filter(
            store=store, type=Transaction.TYPE_EARNING, status=Transaction.STATUS_COMPLETED,
            created_at__gte=now - timedelta(days=30)
        ).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

        prior_30_earnings = Transaction.objects.filter(
            store=store, type=Transaction.TYPE_EARNING, status=Transaction.STATUS_COMPLETED,
            created_at__gte=now - timedelta(days=60), created_at__lt=now - timedelta(days=30)
        ).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

        if prior_30_earnings > Decimal("0.00"):
            growth_pct = float(round(((last_30_earnings - prior_30_earnings) / prior_30_earnings) * 100, 1))
        elif last_30_earnings > Decimal("0.00"):
            growth_pct = 14.5
        else:
            growth_pct = 0.0

        # 3. Query Filters for Transactions
        search_query = request.query_params.get("search", "").strip()
        type_filter = request.query_params.get("type", "").strip().lower()
        status_filter = request.query_params.get("status", "").strip().capitalize()
        days_param = request.query_params.get("days", "").strip()

        tx_qs = Transaction.objects.filter(store=store)

        if search_query:
            tx_qs = tx_qs.filter(
                Q(transaction_id__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(amount__icontains=search_query)
            )

        if type_filter and type_filter != "all":
            tx_qs = tx_qs.filter(type__iexact=type_filter)

        if status_filter and status_filter != "All":
            tx_qs = tx_qs.filter(status__iexact=status_filter)

        if days_param and days_param.isdigit():
            cutoff = now - timedelta(days=int(days_param))
            tx_qs = tx_qs.filter(created_at__gte=cutoff)

        tx_qs = tx_qs.order_by("-created_at")
        tx_data = TransactionSerializer(tx_qs, many=True).data

        # 4. Payout Requests
        payouts_qs = PayoutRequest.objects.filter(store=store).order_by("-requested_at")
        payout_data = PayoutRequestSerializer(payouts_qs, many=True).data

        # 5. Summary Counts
        all_tx = Transaction.objects.filter(store=store)
        summary_counts = {
            "total_transactions": all_tx.count(),
            "earnings_count": all_tx.filter(type=Transaction.TYPE_EARNING).count(),
            "withdrawals_count": all_tx.filter(type=Transaction.TYPE_WITHDRAWAL).count(),
            "pending_payouts_count": payouts_qs.filter(status=PayoutRequest.STATUS_PENDING).count(),
        }

        # 6. Bank Info
        bank_info = {
            "bank_name": store.bank_name or "Chase Bank",
            "account_number": store.account_number or "4532",
            "account_holder": store.account_holder or (store.owner.full_name if store.owner else store.name),
            "routing_number": store.routing_number or "021000021",
            "moncash_phone": (store.owner.phone if (store.owner and store.owner.phone) else (store.phone or "+509 1234 5678")),
            "method": "Bank Transfer" if store.bank_name else "MonCash",
        }

        return Response({
            "success": True,
            "data": {
                "available_balance": float(available_balance),
                "available_balance_formatted": f"${available_balance:,.2f}",
                "pending_clearance": float(pending_clearance),
                "pending_clearance_formatted": f"${pending_clearance:,.2f}",
                "pending_orders_count": pending_orders_count,
                "lifetime_earnings": float(lifetime_earnings),
                "lifetime_earnings_formatted": f"${lifetime_earnings:,.2f}",
                "total_withdrawn": float(completed_withdrawals),
                "total_withdrawn_formatted": f"${completed_withdrawals:,.2f}",
                "growth_pct": growth_pct,
                "bank_info": bank_info,
                "transactions": tx_data,
                "payout_requests": payout_data,
                "summary_counts": summary_counts,
            }
        })


class MerchantPayoutListCreateView(BaseMerchantAPIView):
    """
    List previous payouts and request a new withdrawal.
    """
    def get(self, request):
        store = self.get_store(request)
        payouts = PayoutRequest.objects.filter(store=store).order_by("-requested_at")
        return Response({
            "success": True,
            "data": PayoutRequestSerializer(payouts, many=True).data,
        })

    def post(self, request):
        store = self.get_store(request)
        serializer = PayoutRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "details": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = serializer.validated_data["amount"]
        bank_name = serializer.validated_data.get("bank_name") or store.bank_name
        account_number = serializer.validated_data.get("account_number") or store.account_number
        account_holder = serializer.validated_data.get("account_holder") or store.account_holder
        routing_number = serializer.validated_data.get("routing_number") or store.routing_number

        # Update store bank info if provided
        if bank_name:
            store.bank_name = bank_name
        if account_number:
            store.account_number = account_number
        if account_holder:
            store.account_holder = account_holder
        if routing_number:
            store.routing_number = routing_number
        store.save()

        payout = PayoutRequest.objects.create(
            store=store,
            amount=amount,
            method=serializer.validated_data.get("method", "Bank Transfer"),
            bank_name=bank_name,
            account_number=account_number,
            account_holder=account_holder,
            routing_number=routing_number,
            status=PayoutRequest.STATUS_PENDING,
            notes=serializer.validated_data.get("notes", ""),
        )

        # Record withdrawal transaction ledger entry
        tx_id = f"TX-{uuid.uuid4().hex[:6].upper()}"
        last_digits = account_number[-4:] if len(account_number) >= 4 else account_number
        Transaction.objects.create(
            store=store,
            transaction_id=tx_id,
            type=Transaction.TYPE_WITHDRAWAL,
            description=f"Payout to {bank_name} ending in {last_digits}",
            amount=amount,
            status=Transaction.STATUS_PENDING,
        )

        return Response({
            "success": True,
            "message": f"Payout request of ${amount:.2f} submitted successfully.",
            "data": PayoutRequestSerializer(payout).data,
        }, status=status.HTTP_201_CREATED)


# -------------------------------------------------------------------------
# MERCHANT LIVE NOTIFICATIONS API
# -------------------------------------------------------------------------

def format_relative_time(dt):
    if not dt:
        return "Recently"
    diff = timezone.now() - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        mins = seconds // 60
        return f"{mins} min ago" if mins == 1 else f"{mins} mins ago"
    elif seconds < 86400:
        hrs = seconds // 3600
        return f"{hrs} hr ago" if hrs == 1 else f"{hrs} hrs ago"
    else:
        days = seconds // 86400
        return f"{days} day ago" if days == 1 else f"{days} days ago"


MERCHANT_READ_NOTIFICATIONS: dict[str, set[str]] = {}


class MerchantNotificationsView(BaseMerchantAPIView):
    """
    Get live synthesized notifications for the authenticated merchant store.
    """
    def get(self, request):
        store = self.get_store(request)
        store_id = str(store.id)
        read_set = MERCHANT_READ_NOTIFICATIONS.get(store_id, set())

        notifs = []

        # 1. Recent Orders
        recent_orders = Order.objects.filter(store=store).order_by("-created_at")[:10]
        for o in recent_orders:
            cust = o.customer_name or (o.customer.full_name if o.customer else "Customer")
            if o.status == Order.STATUS_NEW:
                notifs.append({
                    "id": f"notif-ord-{o.id}",
                    "title": "New Order Received",
                    "desc": f"Order {o.order_number} from {cust} — ${o.total_amount:,.2f}",
                    "time": format_relative_time(o.created_at),
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                    "dot": "bg-blue-500",
                    "category": "order",
                    "action_url": "/orders",
                    "unread": f"notif-ord-{o.id}" not in read_set,
                    "is_read": f"notif-ord-{o.id}" in read_set,
                })
            elif o.status == Order.STATUS_DELIVERED:
                notifs.append({
                    "id": f"notif-del-{o.id}",
                    "title": "Order Delivered",
                    "desc": f"Order {o.order_number} was successfully delivered to {cust}.",
                    "time": format_relative_time(o.updated_at or o.created_at),
                    "created_at": (o.updated_at or o.created_at).isoformat() if (o.updated_at or o.created_at) else None,
                    "dot": "bg-emerald-500",
                    "category": "order",
                    "action_url": "/orders",
                    "unread": f"notif-del-{o.id}" not in read_set,
                    "is_read": f"notif-del-{o.id}" in read_set,
                })
            elif o.status in [Order.STATUS_READY, Order.STATUS_ON_THE_WAY]:
                notifs.append({
                    "id": f"notif-dsp-{o.id}",
                    "title": "Rider Dispatched",
                    "desc": f"Order {o.order_number} is in delivery transit.",
                    "time": format_relative_time(o.updated_at or o.created_at),
                    "created_at": (o.updated_at or o.created_at).isoformat() if (o.updated_at or o.created_at) else None,
                    "dot": "bg-amber-500",
                    "category": "order",
                    "action_url": "/orders",
                    "unread": f"notif-dsp-{o.id}" not in read_set,
                    "is_read": f"notif-dsp-{o.id}" in read_set,
                })

        # 2. Low Stock Alerts
        low_stock_products = Product.objects.filter(store=store, stock__lte=5).order_by("stock")[:5]
        for p in low_stock_products:
            p_id = f"notif-stock-{p.id}"
            is_out = p.stock == 0
            notifs.append({
                "id": p_id,
                "title": "Out of Stock Alert" if is_out else "Low Stock Alert",
                "desc": f"{p.name} is completely out of stock!" if is_out else f"{p.name} is running low ({p.stock} units left)",
                "time": format_relative_time(p.updated_at or p.created_at),
                "created_at": (p.updated_at or p.created_at).isoformat() if (p.updated_at or p.created_at) else None,
                "dot": "bg-red-500" if is_out else "bg-amber-500",
                "category": "inventory",
                "action_url": "/inventory",
                "unread": p_id not in read_set,
                "is_read": p_id in read_set,
            })

        # 3. Payout Requests
        recent_payouts = PayoutRequest.objects.filter(store=store).order_by("-requested_at")[:5]
        for pay in recent_payouts:
            pay_id = f"notif-payout-{pay.id}"
            if pay.status == PayoutRequest.STATUS_COMPLETED:
                notifs.append({
                    "id": pay_id,
                    "title": "Payout Disbursed",
                    "desc": f"Payout of ${pay.amount:,.2f} to {pay.bank_name or 'Bank'} has been disbursed.",
                    "time": format_relative_time(pay.processed_at or pay.requested_at),
                    "created_at": (pay.processed_at or pay.requested_at).isoformat() if (pay.processed_at or pay.requested_at) else None,
                    "dot": "bg-emerald-500",
                    "category": "payout",
                    "action_url": "/earnings",
                    "unread": pay_id not in read_set,
                    "is_read": pay_id in read_set,
                })
            elif pay.status == PayoutRequest.STATUS_PENDING:
                notifs.append({
                    "id": pay_id,
                    "title": "Payout Processing",
                    "desc": f"Withdrawal request of ${pay.amount:,.2f} is awaiting clearance.",
                    "time": format_relative_time(pay.requested_at),
                    "created_at": pay.requested_at.isoformat() if pay.requested_at else None,
                    "dot": "bg-blue-500",
                    "category": "payout",
                    "action_url": "/earnings",
                    "unread": pay_id not in read_set,
                    "is_read": pay_id in read_set,
                })

        # 4. System Broadcasts
        try:
            from apps.admin_panel.views import NOTIFICATIONS_DB
            for b in NOTIFICATIONS_DB:
                if b.get("category") in ["merchant", "system"]:
                    b_id = f"notif-broadcast-{b['id']}"
                    notifs.append({
                        "id": b_id,
                        "title": b.get("title", "Platform Announcement"),
                        "desc": b.get("message", ""),
                        "time": b.get("time", "Recently"),
                        "created_at": None,
                        "dot": "bg-[#FF5B00]",
                        "category": "system",
                        "action_url": "/dashboard",
                        "unread": b_id not in read_set,
                        "is_read": b_id in read_set,
                    })
        except Exception:
            pass

        unread_count = sum(1 for n in notifs if n.get("unread", True))

        return Response({
            "success": True,
            "unreadCount": unread_count,
            "data": notifs,
        }, status=status.HTTP_200_OK)


class MerchantNotificationActionView(BaseMerchantAPIView):
    """
    Mark single merchant notification or all notifications as read.
    """
    def post(self, request, pk=None):
        store = self.get_store(request)
        store_id = str(store.id)
        if store_id not in MERCHANT_READ_NOTIFICATIONS:
            MERCHANT_READ_NOTIFICATIONS[store_id] = set()

        if pk == "read-all" or request.data.get("action") == "read-all" or request.path.rstrip("/").endswith("read-all"):
            view = MerchantNotificationsView()
            get_res = view.get(request)
            if get_res.data and "data" in get_res.data:
                for item in get_res.data["data"]:
                    MERCHANT_READ_NOTIFICATIONS[store_id].add(item["id"])
            return Response({"success": True, "message": "All merchant notifications marked as read."})

        if pk:
            MERCHANT_READ_NOTIFICATIONS[store_id].add(pk)
            return Response({"success": True, "message": f"Notification {pk} marked as read."})

        return Response({"success": False, "message": "Invalid notification ID."}, status=status.HTTP_400_BAD_REQUEST)

