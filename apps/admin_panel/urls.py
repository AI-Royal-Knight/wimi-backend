from django.urls import path
from .views import (
    AdminStatsView,
    AdminCustomerListView,
    AdminCustomerDetailView,
    AdminCustomerToggleBanView,
    AdminMerchantListView,
    AdminMerchantDetailView,
    AdminMerchantVerifyView,
    AdminMerchantRejectView,
    AdminMerchantSuspendView,
    AdminRiderListView,
    AdminRiderDetailView,
    AdminRiderVerifyView,
    AdminRiderRejectView,
    AdminRiderSuspendView,
    AdminProfileView,
    AdminOrderListView,
    AdminOrderDetailView,
    AdminOrderReassignView,
    AdminDeliveriesView,
    AdminPayoutsView,
    AdminPayoutApproveView,
    AdminCommissionsView,
    AdminCommissionSettingsView,
    AdminDisputesListView,
    AdminDisputeResolveView,
    AdminNotificationsView,
    AdminNotificationActionView,
    AdminUserListView,
    AdminUserDetailView,
)

app_name = "admin_panel"

urlpatterns = [
    # Dashboard stats
    path("stats/", AdminStatsView.as_view(), name="stats"),

    # Commissions
    path("commissions/", AdminCommissionsView.as_view(), name="commissions-overview"),
    path("commissions/settings/", AdminCommissionSettingsView.as_view(), name="commissions-settings"),

    # Disputes
    path("disputes/", AdminDisputesListView.as_view(), name="disputes-list"),
    path("disputes/<str:pk>/resolve/", AdminDisputeResolveView.as_view(), name="disputes-resolve"),

    # Notifications & Broadcasts
    path("notifications/", AdminNotificationsView.as_view(), name="notifications-list"),
    path("notifications/broadcast/", AdminNotificationsView.as_view(), name="notifications-broadcast"),
    path("notifications/<str:pk>/read/", AdminNotificationActionView.as_view(), name="notifications-read"),
    path("notifications/read-all/", AdminNotificationActionView.as_view(), name="notifications-read-all"),

    # Orders
    path("orders/", AdminOrderListView.as_view(), name="orders-list"),
    path("orders/<str:pk>/", AdminOrderDetailView.as_view(), name="orders-detail"),
    path("orders/<str:pk>/reassign/", AdminOrderReassignView.as_view(), name="orders-reassign"),

    # Deliveries
    path("deliveries/", AdminDeliveriesView.as_view(), name="deliveries-list"),

    # Payouts
    path("payouts/", AdminPayoutsView.as_view(), name="payouts-list"),
    path("payouts/approve/", AdminPayoutApproveView.as_view(), name="payouts-approve"),
    path("payouts/<str:pk>/approve/", AdminPayoutApproveView.as_view(), name="payouts-approve-pk"),

    # Customers
    path("customers/", AdminCustomerListView.as_view(), name="customers-list"),
    path("customers/<str:pk>/", AdminCustomerDetailView.as_view(), name="customers-detail"),
    path("customers/<str:pk>/toggle-ban/", AdminCustomerToggleBanView.as_view(), name="customers-toggle-ban"),

    # Merchants
    path("merchants/", AdminMerchantListView.as_view(), name="merchants-list"),
    path("merchants/<str:pk>/", AdminMerchantDetailView.as_view(), name="merchants-detail"),
    path("merchants/<str:pk>/verify/", AdminMerchantVerifyView.as_view(), name="merchants-verify"),
    path("merchants/<str:pk>/reject/", AdminMerchantRejectView.as_view(), name="merchants-reject"),
    path("merchants/<str:pk>/suspend/", AdminMerchantSuspendView.as_view(), name="merchants-suspend"),

    # Riders
    path("riders/", AdminRiderListView.as_view(), name="riders-list"),
    path("riders/<str:pk>/", AdminRiderDetailView.as_view(), name="riders-detail"),
    path("riders/<str:pk>/verify/", AdminRiderVerifyView.as_view(), name="riders-verify"),
    path("riders/<str:pk>/reject/", AdminRiderRejectView.as_view(), name="riders-reject"),
    path("riders/<str:pk>/suspend/", AdminRiderSuspendView.as_view(), name="riders-suspend"),

    # Admin profile
    path("profile/", AdminProfileView.as_view(), name="profile"),

    # Users management
    path("users/", AdminUserListView.as_view(), name="users-list"),
    path("users/<str:pk>/", AdminUserDetailView.as_view(), name="users-detail"),
]

