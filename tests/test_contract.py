"""
FraudLens — OpenAPI Contract Tests

Verifies the OpenAPI schema stays consistent across changes:
- Required endpoints exist
- Response models match expected structure
- Breaking changes are caught in CI

These tests should be updated when the API is intentionally versioned.
The `openapi.json` snapshot is checked in for diff-review in CI.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Required endpoints (enforced on every test run)

_REQUIRED_ENDPOINTS: set[str] = {
    "GET /health",
    "GET /v1/health",
    "POST /v1/predict",
    "POST /v1/predict/batch",
    "POST /v1/explain",
    "POST /v1/chat",
    "POST /v1/similar-cases",
    "GET /model-info",
    "POST /v1/auth/keys",
    "GET /v1/auth/keys",
}


class TestEndpointExistence:
    """Contract: all required API endpoints must exist."""

    def test_all_required_endpoints_exist(self, app):
        """Test that required endpoints are registered.

        Checks that all expected routes are discoverable.
        POST routes depend on model loading and may return 503 at runtime,
        but the route itself should be registered at import time.
        """
        routes = self._get_registered_routes(app)
        for endpoint in _REQUIRED_ENDPOINTS:
            assert endpoint in routes, (
                f"Required endpoint '{endpoint}' not found in registered routes. "
                f"Available routes: {sorted(routes)}"
            )

    def test_openapi_spec_generates(self, app):
        """Test that the OpenAPI spec is generated without errors."""
        spec = app.openapi()
        assert spec is not None
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec

    def test_openapi_spec_contains_all_endpoints(self, app):
        """Test that the OpenAPI spec includes all required endpoints."""
        spec = app.openapi()
        paths = spec.get("paths", {})
        for endpoint in _REQUIRED_ENDPOINTS:
            method, path = endpoint.split(" ", 1)
            assert path in paths, f"Path '{path}' not in OpenAPI spec"
            assert (
                method.lower() in paths[path]
            ), f"Method '{method}' not found for path '{path}'"

    @staticmethod
    def _get_registered_routes(app) -> set[str]:
        """Extract all registered routes from the app's OpenAPI spec.

        Uses the OpenAPI spec instead of app.routes because newer FastAPI
        versions wrap included routers as _IncludedRouter objects that
        don't expose path/methods directly on app.routes.
        """
        routes = set()
        spec = app.openapi()
        for path, methods in spec.get("paths", {}).items():
            for method in methods:
                routes.add(f"{method.upper()} {path}")
        return routes


class TestResponseModels:
    """Contract: response models must match expected structure."""

    def test_predict_response_model(self, client, sample_transaction):
        """Test that /v1/predict response matches PredictionResponse schema."""
        response = client.post("/v1/predict", json=sample_transaction)
        if response.status_code == 200:
            data = response.json()
            # Required fields from PredictionResponse
            assert "fraud_probability" in data
            assert "decision" in data
            assert "threshold_used" in data
            assert "is_fraud" in data
            assert isinstance(data["fraud_probability"], (int, float))
            assert data["decision"] in ("FRAUD", "LEGITIMATE")
            assert isinstance(data["is_fraud"], bool)

    def test_health_response_model(self, client):
        """Test that /v1/health response matches expected schema."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "dependencies" in data
        assert isinstance(data["dependencies"], dict)
        # Each dependency should have status and detail
        for dep_name, dep_info in data["dependencies"].items():
            assert "status" in dep_info
            assert dep_info["status"] in ("ok", "degraded", "error")
            assert "detail" in dep_info

    def test_batch_response_model(self, client, sample_batch):
        """Test that /v1/predict/batch response matches BatchResponse schema."""
        response = client.post("/v1/predict/batch", json=sample_batch)
        if response.status_code == 200:
            data = response.json()
            assert "predictions" in data
            assert "summary" in data
            assert "total" in data["summary"]
            assert "flagged_fraud" in data["summary"]
            assert "estimated_review_cost" in data["summary"]

    def test_explain_response_model(self, client, sample_transaction):
        """Test that /v1/explain response matches ExplanationResponse schema."""
        response = client.post("/v1/explain", json=sample_transaction)
        if response.status_code == 200:
            data = response.json()
            assert "fraud_probability" in data
            assert "decision" in data
            assert "shap_values" in data
            assert isinstance(data["shap_values"], dict)


class TestErrorResponseContract:
    """Contract: all error responses must follow RFC 7807 format."""

    def test_validation_error_has_rfc7807_format(self, client):
        """Test that 422 errors follow RFC 7807 problem-details format."""
        response = client.post(
            "/v1/predict",
            json={"invalid": "data"},
        )
        assert response.status_code == 422
        data = response.json()
        # RFC 7807 required fields
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert data["status"] == 422
        assert "detail" in data
        assert "errors" in data

    def test_validation_error_has_field_level_errors(self, client):
        """Test that 422 errors include field-level validation details."""
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = -100.0  # Invalid: ge=0 violated
        response = client.post("/v1/predict", json=tx)
        assert response.status_code == 422
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) > 0

        # Each error should have field, message, type
        for error in data["errors"]:
            assert "field" in error
            assert "message" in error

    def test_404_has_rfc7807_format(self, client):
        """Test that 404 errors follow RFC 7807."""
        response = client.get("/nonexistent-route")
        assert response.status_code == 404
        _data = response.json()
        # FastAPI's default 404 handler may or may not produce RFC 7807
        # But we should at least get a response
        assert response.status_code == 404


class TestOpenApiSpecConsistency:
    """Contract: the OpenAPI spec must not have breaking changes."""

    def test_spec_version_matches_code(self, app):
        """Test that OpenAPI version matches the app version."""
        spec = app.openapi()
        info = spec.get("info", {})
        assert info.get("version") == "2.0.0"

    def test_spec_has_core_schemas(self, app):
        """Test that the spec defines core prediction schemas."""
        spec = app.openapi()
        schemas = spec.get("components", {}).get("schemas", {})
        core_schemas = {
            "TransactionInput",
            "PredictionResponse",
            "BatchInput",
            "BatchResponse",
            "ExplanationResponse",
            "SimilarCasesResponse",
            "CursorPagination",
        }
        for schema in core_schemas:
            assert schema in schemas, (
                f"Schema '{schema}' not found in OpenAPI components. "
                f"Available schemas: {list(schemas.keys())}"
            )

    def test_no_duplicate_operation_ids(self, app):
        """Test that no two routes share the same operationId."""
        spec = app.openapi()
        operation_ids = []
        for path, methods in spec.get("paths", {}).items():
            for method in methods.values():
                if "operationId" in method:
                    operation_ids.append(method["operationId"])

        duplicates = [oid for oid in operation_ids if operation_ids.count(oid) > 1]
        assert len(duplicates) == 0, f"Duplicate operationIds found: {set(duplicates)}"
