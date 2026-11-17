from django.urls import path
from .views import (
    RiderAcceptDeliveryView,
    RiderActiveDeliveriesView,
    RiderDeliveryHistoryView,
    RiderEarningsView,
    RiderOrderChatView,
    RiderPayoutView,
    RiderStatusToggleView,
    RiderUpdateDeliveryStepView,
    RiderUpdateLocationView,
    RiderVerifyDeliveryOtpView,
)

app_name = "rider"

urlpatterns = [
    # Availability
    path("status/", RiderStatusToggleView.as_view(), name="status"),
    path("location/", RiderUpdateLocationView.as_view(), name="location"),

    # Deliveries
    path("deliveries/active/", RiderActiveDeliveriesView.as_view(), name="deliveries-active"),
    path("deliveries/history/", RiderDeliveryHistoryView.as_view(), name="deliveries-history"),
    path("deliveries/accept/", RiderAcceptDeliveryView.as_view(), name="deliveries-accept"),
    path("deliveries/<uuid:pk>/accept/", RiderAcceptDeliveryView.as_view(), name="deliveries-accept-pk"),
    path("deliveries/update/", RiderUpdateDeliveryStepView.as_view(), name="deliveries-update"),
    path("deliveries/<uuid:pk>/update/", RiderUpdateDeliveryStepView.as_view(), name="deliveries-update-pk"),
    path("deliveries/verify-otp/", RiderVerifyDeliveryOtpView.as_view(), name="deliveries-verify-otp"),
    path("deliveries/<uuid:pk>/verify-otp/", RiderVerifyDeliveryOtpView.as_view(), name="deliveries-verify-otp-pk"),
    path("deliveries/chat/", RiderOrderChatView.as_view(), name="deliveries-chat"),
    path("deliveries/<uuid:pk>/chat/", RiderOrderChatView.as_view(), name="deliveries-chat-pk"),

    # Earnings & Payouts
    path("earnings/", RiderEarningsView.as_view(), name="earnings"),
    path("payouts/", RiderPayoutView.as_view(), name="payouts"),
]

