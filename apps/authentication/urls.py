from django.urls import path
from apps.users.views import UserProfileView
from .views import (
    ChangePasswordView,
    CustomTokenRefreshView,
    ForgotPasswordRequestView,
    ForgotPasswordVerifyView,
    LoginView,
    LogoutView,
    MerchantRegisterView,
    ResendOtpView,
    ResetPasswordView,
    RiderRegisterView,
    SignupView,
    VerifyOtpView,
)

app_name = "authentication"

urlpatterns = [
    # Customer Registration Flow
    path("signup/", SignupView.as_view(), name="signup"),
    path("signup/verify/", VerifyOtpView.as_view(), name="signup-verify"),
    path("signup/resend-otp/", ResendOtpView.as_view(), name="signup-resend-otp"),

    # Merchant Registration Flow
    path("merchant/register/", MerchantRegisterView.as_view(), name="merchant-register"),

    # Rider / Delivery Partner Registration Flow
    path("rider/register/", RiderRegisterView.as_view(), name="rider-register"),

    # Authentication & Session
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),

    # Password Recovery Flow
    path("forgot-password/request/", ForgotPasswordRequestView.as_view(), name="forgot-password-request"),
    path("forgot-password/verify/", ForgotPasswordVerifyView.as_view(), name="forgot-password-verify"),
    path("forgot-password/reset/", ResetPasswordView.as_view(), name="forgot-password-reset"),

    # Authenticated User Actions
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("me/", UserProfileView.as_view(), name="user-me"),
]
