from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class BurstRateThrottle(AnonRateThrottle):
    scope = "burst"


class SustainedRateThrottle(AnonRateThrottle):
    scope = "sustained"


class SignupRateThrottle(AnonRateThrottle):
    scope = "signup"


class OTPVerifyRateThrottle(SimpleRateThrottle):
    scope = "otp_verify"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        # Combine with email or phone from request payload if available
        email = request.data.get("email") or request.data.get("destination") or ""
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{ident}:{email}",
        }


class OTPResendRateThrottle(SimpleRateThrottle):
    scope = "otp_resend"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        email = request.data.get("email") or request.data.get("destination") or ""
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{ident}:{email}",
        }


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class PasswordResetRateThrottle(AnonRateThrottle):
    scope = "password_reset"
