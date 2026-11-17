"""
Test environment settings.
Optimized for testing speed and deterministic assertions.
"""
from .base import *  # noqa: F403

DEBUG = False
TESTING = True
SECRET_KEY = "test-secret-key-only-used-for-automated-tests"

# Fast in-memory database for testing
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Fast password hasher for test execution speed
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# In-memory email backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Test SMS backend
SMS_BACKEND = "apps.notifications.sms.LocMemSMSBackend"

# Disable throttling or set high limits during standard tests
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "1000/minute",
    "user": "1000/minute",
    "burst": "1000/minute",
    "sustained": "10000/hour",
    "signup": "1000/minute",
    "otp_verify": "1000/minute",
    "otp_resend": "1000/minute",
    "login": "1000/minute",
    "password_reset": "1000/minute",
}
