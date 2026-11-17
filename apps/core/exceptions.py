import logging
from typing import Any, Dict, Optional
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class AppException(exceptions.APIException):
    """Base application exception for domain errors."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "APP_ERROR"
    default_detail = "An application error occurred."

    def __init__(
        self,
        detail: Optional[str] = None,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if status_code is not None:
            self.status_code = status_code
        self.code = code or self.default_code
        self.details = details or {}
        super().__init__(detail=detail or self.default_detail, code=self.code)


class OTPExpiredError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "OTP_EXPIRED"
    default_detail = "Verification code has expired. Please request a new one."


class OTPInvalidError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "OTP_INVALID"
    default_detail = "Invalid verification code."


class OTPAttemptsExceededError(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "OTP_MAX_ATTEMPTS_EXCEEDED"
    default_detail = "Maximum verification attempts exceeded. Please request a new code."


class CooldownActiveError(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "COOLDOWN_ACTIVE"
    default_detail = "Please wait before requesting another verification code."


class AccountAlreadyVerifiedError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "ACCOUNT_ALREADY_VERIFIED"
    default_detail = "This account is already verified."


class UnverifiedAccountError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "UNVERIFIED_ACCOUNT"
    default_detail = "Account is unverified. Please verify your account with OTP."


def custom_exception_handler(exc: Exception, context: Dict[str, Any]) -> Optional[Response]:
    """
    Standardized DRF Exception Handler.
    Converts all API errors into a consistent structure:
    {
        "success": false,
        "error": {
            "code": "ERROR_CODE",
            "message": "Human readable message",
            "details": { ...field errors or context... }
        }
    }
    """
    # Convert Django standard exceptions to DRF exceptions
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            exc = exceptions.ValidationError(detail=exc.message_dict)
        elif hasattr(exc, "messages"):
            exc = exceptions.ValidationError(detail=exc.messages)
        else:
            exc = exceptions.ValidationError(detail=str(exc))

    response = exception_handler(exc, context)

    if response is None:
        # Unhandled server exception
        logger.exception("Unhandled server exception encountered in API view", exc_info=exc)
        return Response(
            {
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                    "details": {},
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Determine code and message
    code = "API_ERROR"
    message = "An error occurred."
    details = {}

    if isinstance(exc, AppException):
        code = exc.code
        message = str(exc.detail)
        details = exc.details
    elif isinstance(exc, exceptions.ValidationError):
        code = "VALIDATION_ERROR"
        if isinstance(response.data, dict):
            details = response.data
            # Extract first error message for top-level message
            for field, errs in response.data.items():
                if isinstance(errs, list) and errs:
                    message = f"{field}: {errs[0]}" if field != "non_field_errors" else str(errs[0])
                    break
                elif isinstance(errs, str):
                    message = errs
                    break
        elif isinstance(response.data, list) and response.data:
            message = str(response.data[0])
            details = {"non_field_errors": response.data}
    elif isinstance(exc, exceptions.NotAuthenticated):
        code = "NOT_AUTHENTICATED"
        message = "Authentication credentials were not provided."
    elif isinstance(exc, exceptions.AuthenticationFailed):
        code = "AUTHENTICATION_FAILED"
        message = str(exc.detail) if hasattr(exc, "detail") else "Invalid credentials."
    elif isinstance(exc, exceptions.PermissionDenied):
        code = "PERMISSION_DENIED"
        message = "You do not have permission to perform this action."
    elif isinstance(exc, exceptions.Throttled):
        code = "THROTTLED"
        wait_seconds = exc.wait
        message = f"Request was throttled. Expected available in {wait_seconds} seconds."
        details = {"wait_seconds": wait_seconds}
    elif isinstance(exc, exceptions.NotFound):
        code = "NOT_FOUND"
        message = "The requested resource was not found."
    else:
        if hasattr(exc, "get_codes"):
            codes = exc.get_codes()
            code = str(codes) if isinstance(codes, str) else "API_ERROR"
        if hasattr(exc, "detail"):
            message = str(exc.detail)

    response.data = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }

    return response
