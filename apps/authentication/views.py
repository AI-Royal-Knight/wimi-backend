from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.throttling import (
    LoginRateThrottle,
    OTPResendRateThrottle,
    OTPVerifyRateThrottle,
    PasswordResetRateThrottle,
    SignupRateThrottle,
)
from .serializers import (
    AuthResponseDataSerializer,
    ChangePasswordSerializer,
    ForgotPasswordRequestSerializer,
    ForgotPasswordVerifySerializer,
    LoginSerializer,
    LogoutRequestSerializer,
    MerchantAuthResponseDataSerializer,
    MerchantRegisterSerializer,
    ResendOtpSerializer,
    ResetPasswordSerializer,
    RiderAuthResponseDataSerializer,
    RiderRegisterSerializer,
    SignupSerializer,
    VerifyOtpSerializer,
)
from .services import AuthService


class SignupView(APIView):
    """
    Initial registration endpoint.
    Creates an inactive user and sends a 4-digit verification code to the provided email.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [SignupRateThrottle]

    @extend_schema(
        summary="User Registration",
        description="Submit registration details. Validates inputs, creates inactive account, and dispatches a 4-digit OTP code to the email.",
        request=SignupSerializer,
        responses={
            201: OpenApiResponse(description="Registration successful, OTP dispatched"),
            400: OpenApiResponse(description="Validation error or account already exists"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, otp = AuthService.signup(
            full_name=serializer.validated_data["full_name"],
            email=serializer.validated_data["email"],
            phone=serializer.validated_data["phone"],
            password=serializer.validated_data["password"],
            terms_accepted=serializer.validated_data["terms_accepted"],
        )

        return Response(
            {
                "success": True,
                "message": "Verification code has been sent to your email address.",
                "data": {
                    "email": user.email,
                    "expires_in_seconds": 600,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyOtpView(APIView):
    """
    Verify 4-digit numeric OTP code for account signup.
    Activates the user and returns JWT access and refresh tokens.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OTPVerifyRateThrottle]

    @extend_schema(
        summary="Verify Signup OTP",
        description="Verify the 4-digit OTP sent to email. On success, activates the account and returns JWT credentials.",
        request=VerifyOtpSerializer,
        responses={
            200: OpenApiResponse(response=AuthResponseDataSerializer, description="Account activated successfully"),
            400: OpenApiResponse(description="Invalid or expired OTP code"),
            429: OpenApiResponse(description="Max attempts exceeded or rate-limited"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        auth_data = AuthService.verify_signup_otp(
            email=serializer.validated_data["email"],
            otp_code=serializer.validated_data["otp_code"],
        )

        return Response(
            {
                "success": True,
                "message": "Account verified and activated successfully.",
                "data": auth_data,
            },
            status=status.HTTP_200_OK,
        )


class ResendOtpView(APIView):
    """
    Resend verification code for signup.
    Enforces a 60-second cooldown period matching frontend countdown timer.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OTPResendRateThrottle]

    @extend_schema(
        summary="Resend Signup OTP",
        description="Request a new 4-digit OTP code. Enforces a 60-second cooldown between requests.",
        request=ResendOtpSerializer,
        responses={
            200: OpenApiResponse(description="New code sent successfully"),
            400: OpenApiResponse(description="Account already verified or not found"),
            429: OpenApiResponse(description="Cooldown active or rate limited"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = ResendOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.resend_signup_otp(email=serializer.validated_data["email"])

        return Response(
            {
                "success": True,
                "message": "A new verification code has been sent to your email address.",
                "data": {
                    "email": serializer.validated_data["email"],
                    "cooldown_seconds": 60,
                },
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    """
    Authenticate user via Email or Phone + Password.
    Returns JWT access and refresh tokens.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(
        summary="User Sign In",
        description="Authenticate user with either Email or Phone number and Password.",
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(response=AuthResponseDataSerializer, description="Login successful"),
            401: OpenApiResponse(description="Invalid credentials"),
            403: OpenApiResponse(description="Unverified account"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        auth_data = AuthService.login(
            identifier=serializer.validated_data["identifier"],
            password=serializer.validated_data["password"],
        )

        return Response(
            {
                "success": True,
                "message": "Logged in successfully.",
                "data": auth_data,
            },
            status=status.HTTP_200_OK,
        )


class ForgotPasswordRequestView(APIView):
    """
    Request password recovery OTP for Email or Phone.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    @extend_schema(
        summary="Forgot Password - Request Code",
        description="Sends a 4-digit password recovery code to registered email or phone.",
        request=ForgotPasswordRequestSerializer,
        responses={
            200: OpenApiResponse(description="Recovery code sent if account exists"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.request_password_reset(
            destination=serializer.validated_data["destination"],
            dest_type=serializer.validated_data["type"],
        )

        return Response(
            {
                "success": True,
                "message": "If an account matches that destination, a recovery code has been sent.",
            },
            status=status.HTTP_200_OK,
        )


class ForgotPasswordVerifyView(APIView):
    """
    Verify 4-digit recovery OTP and receive a single-use password reset token.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OTPVerifyRateThrottle]

    @extend_schema(
        summary="Forgot Password - Verify Code",
        description="Verify recovery OTP and receive a temporary reset token.",
        request=ForgotPasswordVerifySerializer,
        responses={
            200: OpenApiResponse(description="Code verified, reset token returned"),
            400: OpenApiResponse(description="Invalid or expired recovery code"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = ForgotPasswordVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reset_token = AuthService.verify_password_reset_otp(
            destination=serializer.validated_data["destination"],
            otp_code=serializer.validated_data["otp_code"],
            dest_type=serializer.validated_data["type"],
        )

        return Response(
            {
                "success": True,
                "message": "Verification code accepted.",
                "data": {"reset_token": reset_token},
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    """
    Set a new password using the validated reset token.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    @extend_schema(
        summary="Forgot Password - Set New Password",
        description="Set new password using single-use reset token.",
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(description="Password reset successfully"),
            400: OpenApiResponse(description="Invalid reset token or validation error"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.reset_password(
            reset_token=serializer.validated_data["reset_token"],
            new_password=serializer.validated_data["new_password"],
        )

        return Response(
            {
                "success": True,
                "message": "Password reset successfully. Please sign in with your new password.",
            },
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    """
    Update password for authenticated user with current password validation.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Change Password",
        description="Change password for authenticated user (requires current password).",
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description="Password changed successfully"),
            400: OpenApiResponse(description="Current password incorrect or complexity validation failed"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.change_password(
            user=request.user,
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
        )

        return Response(
            {
                "success": True,
                "message": "Password updated successfully.",
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    Revoke refresh token and log user out.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Sign Out / Revoke Token",
        description="Blacklist refresh token to safely log user out.",
        request=LogoutRequestSerializer,
        responses={
            200: OpenApiResponse(description="Logged out successfully"),
        },
    )
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass

        return Response(
            {
                "success": True,
                "message": "Logged out successfully.",
            },
            status=status.HTTP_200_OK,
        )


class CustomTokenRefreshView(BaseTokenRefreshView):
    """
    Refresh JWT access token.
    """
    @extend_schema(
        summary="Refresh JWT Token",
        description="Obtain a renewed access token using a valid refresh token.",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class MerchantRegisterView(APIView):
    """
    Register a new merchant account along with their business store.
    Directly activates the merchant account and returns JWT credentials.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [SignupRateThrottle]

    @extend_schema(
        summary="Merchant & Store Registration",
        description="Register a new merchant partner and create their store on TiBoutik. Returns authenticated JWT credentials.",
        request=MerchantRegisterSerializer,
        responses={
            201: OpenApiResponse(response=MerchantAuthResponseDataSerializer, description="Merchant and store registered successfully"),
            400: OpenApiResponse(description="Validation error or account already exists"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = MerchantRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = AuthService.register_merchant(
            full_name=serializer.validated_data["full_name"],
            email=serializer.validated_data["email"],
            phone=serializer.validated_data["phone"],
            password=serializer.validated_data["password"],
            store_name=serializer.validated_data["store_name"],
            category=serializer.validated_data.get("category", "Grocery"),
            store_address=serializer.validated_data.get("store_address", ""),
            store_description=serializer.validated_data.get("store_description", ""),
            terms_accepted=serializer.validated_data["terms_accepted"],
        )

        return Response(
            {
                "success": True,
                "message": "Merchant store registered successfully. Welcome to TiBoutik!",
                "data": data,
            },
            status=status.HTTP_201_CREATED,
        )


class RiderRegisterView(APIView):
    """
    Register a new delivery partner / rider account along with their fleet profile.
    Directly activates the rider account and returns JWT credentials.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [SignupRateThrottle]

    @extend_schema(
        summary="Rider / Delivery Partner Registration",
        description="Register a new delivery partner and create their fleet profile on TiBoutik. Returns authenticated JWT credentials.",
        request=RiderRegisterSerializer,
        responses={
            201: OpenApiResponse(response=RiderAuthResponseDataSerializer, description="Rider registered successfully"),
            400: OpenApiResponse(description="Validation error or account already exists"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = RiderRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = AuthService.register_rider(
            full_name=serializer.validated_data["full_name"],
            email=serializer.validated_data["email"],
            phone=serializer.validated_data["phone"],
            password=serializer.validated_data["password"],
            vehicle_type=serializer.validated_data.get("vehicle_type", "Motorcycle"),
            number_plate=serializer.validated_data.get("number_plate", ""),
            zone=serializer.validated_data.get("zone", "Port-au-Prince Centre"),
            terms_accepted=serializer.validated_data["terms_accepted"],
        )

        return Response(
            {
                "success": True,
                "message": "Delivery partner registered successfully. Your account is pending administrator approval before you can start accepting deliveries.",
                "data": data,
            },
            status=status.HTTP_201_CREATED,
        )

