from django.db import connection
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse


class HealthCheckView(APIView):
    """
    Health and readiness probe endpoint.
    Verifies database connectivity and service status.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Service Health Check",
        description="Returns operational status of the service and database connection.",
        responses={
            200: OpenApiResponse(description="Service is healthy"),
            503: OpenApiResponse(description="Database or dependency is unhealthy"),
        },
    )
    def get(self, request, *args, **kwargs):
        db_healthy = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
                db_healthy = bool(row and row[0] == 1)
        except Exception:
            db_healthy = False

        status_code = status.HTTP_200_OK if db_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(
            {
                "success": db_healthy,
                "status": "healthy" if db_healthy else "degraded",
                "components": {
                    "database": "connected" if db_healthy else "disconnected",
                },
            },
            status=status_code,
        )


def custom_404_handler(request, exception=None):
    from django.http import JsonResponse
    return JsonResponse(
        {
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested resource was not found.",
                "details": {},
            },
        },
        status=404,
    )
