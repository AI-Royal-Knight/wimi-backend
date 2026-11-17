"""
Local development settings.
"""
from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# In local dev, allow all origins if not explicitly restricted
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=True)

# Console email for testing without live SMTP
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
