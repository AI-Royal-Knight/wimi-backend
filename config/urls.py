"""
URL configuration for Wimi / TiBoutik backend project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from drf_spectacular.utils import extend_schema, extend_schema_view
from apps.core.views import HealthCheckView
from apps.authentication.views import LoginView


@extend_schema_view(post=extend_schema(exclude=True))
class LegacyLoginView(LoginView):
    pass


urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # Health & Readiness Probe
    path("health", HealthCheckView.as_view(), name="root-health"),
    path("health/", HealthCheckView.as_view(), name="root-health-slash"),
    path("api/v1/health/", HealthCheckView.as_view(), name="health-check"),

    # API v1 Authentication & Profile Endpoints
    path("api/v1/auth/", include("apps.authentication.urls", namespace="v1-auth")),
    path("api/v1/admin/", include("apps.admin_panel.urls", namespace="v1-admin")),
    path("api/v1/users/", include("apps.users.urls", namespace="v1-users")),
    path("api/v1/merchant/", include("apps.merchant.urls", namespace="v1-merchant")),
    path("api/v1/customer/", include("apps.customer.urls", namespace="v1-customer")),
    path("api/v1/rider/", include("apps.rider.urls", namespace="v1-rider")),

    # Backward compatibility alias for Flutter app direct /api/auth/login route
    path("api/auth/login", LegacyLoginView.as_view(), name="legacy-login"),
    path("api/auth/login/", LegacyLoginView.as_view(), name="legacy-login-slash"),

    # OpenAPI 3.0 Documentation & Schemas
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/v1/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = "apps.core.views.custom_404_handler"
