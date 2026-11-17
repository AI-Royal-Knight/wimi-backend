from django.urls import path
from .views import UserProfileView, MerchantStoreView

app_name = "users"

urlpatterns = [
    path("profile/", UserProfileView.as_view(), name="profile"),
    path("me/", UserProfileView.as_view(), name="me"),
    path("store/", MerchantStoreView.as_view(), name="store"),
]
