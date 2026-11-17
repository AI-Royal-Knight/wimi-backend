from django.urls import path
from .views import (
    MerchantDashboardView,
    MerchantOrderListView,
    MerchantOrderDetailView,
    MerchantOrderAcceptView,
    MerchantOrderRejectView,
    MerchantOrderStatusUpdateView,
    MerchantProductListCreateView,
    MerchantProductDetailView,
    MerchantProductStockAdjustView,
    MerchantInventoryView,
    MerchantEarningsView,
    MerchantPayoutListCreateView,
    MerchantNotificationsView,
    MerchantNotificationActionView,
)

app_name = "merchant"

urlpatterns = [
    # Dashboard stats
    path("dashboard/", MerchantDashboardView.as_view(), name="dashboard"),

    # Orders management
    path("orders/", MerchantOrderListView.as_view(), name="order-list"),
    path("orders/<uuid:pk>/", MerchantOrderDetailView.as_view(), name="order-detail"),
    path("orders/<uuid:pk>/accept/", MerchantOrderAcceptView.as_view(), name="order-accept"),
    path("orders/<uuid:pk>/reject/", MerchantOrderRejectView.as_view(), name="order-reject"),
    path("orders/<uuid:pk>/status/", MerchantOrderStatusUpdateView.as_view(), name="order-status"),

    # Products catalog
    path("products/", MerchantProductListCreateView.as_view(), name="product-list"),
    path("products/<uuid:pk>/", MerchantProductDetailView.as_view(), name="product-detail"),
    path("products/<uuid:pk>/stock/", MerchantProductStockAdjustView.as_view(), name="product-stock-adjust"),

    # Inventory management
    path("inventory/", MerchantInventoryView.as_view(), name="inventory"),

    # Earnings & payouts
    path("earnings/", MerchantEarningsView.as_view(), name="earnings"),
    path("payouts/", MerchantPayoutListCreateView.as_view(), name="payouts"),

    # Notifications
    path("notifications/", MerchantNotificationsView.as_view(), name="notifications"),
    path("notifications/read-all/", MerchantNotificationActionView.as_view(), name="notifications-read-all"),
    path("notifications/<str:pk>/read/", MerchantNotificationActionView.as_view(), name="notification-mark-read"),
]

