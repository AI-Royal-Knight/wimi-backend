import pytest
from rest_framework import status


@pytest.mark.django_db
class TestSecurityAndSystemHealth:
    def test_health_check_endpoint(self, api_client):
        response = api_client.get("/api/v1/health/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert response.data["status"] == "healthy"
        assert response.data["components"]["database"] == "connected"

    def test_consistent_error_format_on_not_found(self, api_client):
        response = api_client.get("/api/v1/auth/non-existent-endpoint/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json() if hasattr(response, "json") else response.data
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"

    def test_openapi_schema_and_docs_endpoints(self, api_client):
        schema_res = api_client.get("/api/v1/schema/")
        assert schema_res.status_code == status.HTTP_200_OK

        swagger_res = api_client.get("/api/v1/docs/")
        assert swagger_res.status_code == status.HTTP_200_OK

        redoc_res = api_client.get("/api/v1/redoc/")
        assert redoc_res.status_code == status.HTTP_200_OK
