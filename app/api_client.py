import requests

"""
FraudLens — Shared API Client for Streamlit Dashboard

Provides a centralized, resilient HTTP client with:
- Automatic retries with exponential backoff (via tenacity or manual)
- Connection pooling via httpx
- Configurable timeouts
- Consistent error handling and logging

Usage:
    from app.api_client import FraudLensAPI

    api = FraudLensAPI()
    result = api.predict(transaction)
    explain = api.explain(transaction)
"""

import logging
import time
from typing import Any

import httpx
import streamlit as st

from src.fraudlens.config import API_URL

logger = logging.getLogger(__name__)

# Default timeout configuration
_DEFAULT_TIMEOUT = 10.0  # seconds
_DEFAULT_RETRIES = 2
_DEFAULT_RETRY_DELAY = 0.5  # seconds


class FraudLensAPIError(Exception):
    """Custom exception for API errors with status code context."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class FraudLensAPI:
    """
    Resilient HTTP client for the FraudLens API.

    Features:
    - Automatic retries on transient failures (connection errors, 5xx)
    - Configurable timeouts per endpoint
    - Connection pooling via httpx
    - API health checking
    - Loading state support for Streamlit spinners
    """

    def __init__(
        self,
        base_url: str = API_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_RETRIES,
    ) -> None:
        """
        Args:
            base_url: Base URL of the FraudLens API
            timeout: Default timeout for requests (seconds)
            max_retries: Number of retries on transient failures
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        # Build httpx client with connection pooling
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
            ),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    def _handle_response(self, response: httpx.Response, label: str) -> dict:
        """Handle API response, raising typed errors on failure."""
        if response.is_success:
            return response.json()

        if response.status_code == 503:
            raise FraudLensAPIError(
                f"Service unavailable: {label}",
                status_code=503,
            )
        elif response.status_code == 422:
            raise FraudLensAPIError(
                f"Validation error: {response.text}",
                status_code=422,
            )
        elif response.status_code == 401:
            raise FraudLensAPIError(
                "Authentication required. Set X-API-Key header.",
                status_code=401,
            )
        else:
            raise FraudLensAPIError(
                f"API error ({response.status_code}): {response.text[:200]}",
                status_code=response.status_code,
            )

    def _request_with_retry(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
        label: str = "request",
    ) -> dict:
        """Make an HTTP request with automatic retries on transient failures."""
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(method, path, json=json_data)
                return self._handle_response(response, label)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(_DEFAULT_RETRY_DELAY * (2**attempt))
                    continue
            except FraudLensAPIError:
                raise
            except (requests.RequestException, ValueError, OSError) as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(_DEFAULT_RETRY_DELAY)
                    continue
                break

        raise FraudLensAPIError(
            f"{label} failed after {self.max_retries} retries: {last_error}"
        )

    def check_health(self) -> dict:
        """Check API health with per-dependency status."""
        try:
            return self._request_with_retry("GET", "/v1/health", label="health check")
        except FraudLensAPIError as e:
            if e.status_code in (503, 502):
                # Try unversioned health endpoint
                try:
                    response = self._client.get("/health")
                    return response.json()
                except (requests.RequestException, ValueError):
                    pass
            return {"status": "error", "detail": str(e)}

    def predict(self, transaction: dict, explain: bool = False) -> dict:
        """Predict fraud for a single transaction."""
        path = f"/v1/predict{'?explain=true' if explain else ''}"
        return self._request_with_retry(
            "POST", path, json_data=transaction, label="prediction"
        )

    def predict_batch(self, transactions: list[dict]) -> dict:
        """Predict fraud for multiple transactions."""
        return self._request_with_retry(
            "POST",
            "/v1/predict/batch",
            json_data={"transactions": transactions},
            label="batch prediction",
        )

    def explain(self, transaction: dict) -> dict:
        """Get SHAP explanation + narrative for a transaction."""
        return self._request_with_retry(
            "POST", "/v1/explain", json_data=transaction, label="explanation"
        )

    def get_similar_cases(
        self,
        transaction: dict,
        top_k: int = 3,
        cursor: str | None = None,
    ) -> dict:
        """Get similar historical cases with cursor pagination."""
        params = f"?top_k={top_k}"
        if cursor:
            params += f"&cursor={cursor}"
        return self._request_with_retry(
            "POST",
            f"/v1/similar-cases{params}",
            json_data=transaction,
            label="similar cases",
        )

    def chat(self, message: str, history: list[dict] | None = None) -> dict:
        """Send a message to the analyst copilot."""
        return self._request_with_retry(
            "POST",
            "/v1/chat",
            json_data={
                "message": message,
                "conversation_history": history or [],
            },
            label="chat",
        )

    # ─── Admin: Model Management ────────────────────────────────────────

    def get_candidates(
        self,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        List model candidates with optional status filter.

        Requires FRAUDLENS_DASHBOARD_API_KEY env var with admin-level key.
        """
        path = "/v1/admin/models/candidates"
        params = f"?limit={limit}&offset={offset}"
        if status_filter:
            params += f"&status_filter={status_filter}"
        return self._admin_request("GET", f"{path}{params}", label="list candidates")

    def promote_candidate(self, model_version: str) -> dict:
        """Promote a candidate model to production.

        Requires FRAUDLENS_DASHBOARD_API_KEY env var with admin-level key.
        """
        return self._admin_request(
            "POST",
            f"/v1/admin/models/candidates/{model_version}/promote",
            label=f"promote {model_version}",
        )

    def reject_candidate(self, model_version: str) -> dict:
        """Reject a candidate model.

        Requires FRAUDLENS_DASHBOARD_API_KEY env var with admin-level key.
        """
        return self._admin_request(
            "POST",
            f"/v1/admin/models/candidates/{model_version}/reject",
            label=f"reject {model_version}",
        )

    def compare_candidate(self, model_version: str) -> dict:
        """Compare a candidate against the current production model.

        Requires FRAUDLENS_DASHBOARD_API_KEY env var with admin-level key.
        """
        return self._admin_request(
            "GET",
            f"/v1/admin/models/candidates/{model_version}/compare",
            label=f"compare {model_version}",
        )

    # ─── Admin Helpers ───────────────────────────────────────────────────

    def _admin_request(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
        label: str = "admin request",
    ) -> dict:
        """Make an authenticated admin API request using the dashboard API key."""
        import os

        api_key = os.environ.get("FRAUDLENS_DASHBOARD_API_KEY", "")
        if not api_key:
            raise FraudLensAPIError(
                "Admin operations require FRAUDLENS_DASHBOARD_API_KEY environment "
                "variable with an admin-level API key.",
                status_code=401,
            )

        with httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-API-Key": api_key,
            },
        ) as admin_client:
            last_error: Exception | None = None
            for attempt in range(self.max_retries + 1):
                try:
                    response = admin_client.request(method, path, json=json_data)
                    return self._handle_response(response, label)
                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    last_error = e
                    if attempt < self.max_retries:
                        time.sleep(_DEFAULT_RETRY_DELAY * (2**attempt))
                        continue
                except FraudLensAPIError:
                    raise
                except (requests.RequestException, ValueError, OSError) as e:
                    last_error = e
                    if attempt < self.max_retries:
                        time.sleep(_DEFAULT_RETRY_DELAY)
                        continue
                    break

        raise FraudLensAPIError(
            f"{label} failed after {self.max_retries} retries: {last_error}"
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "FraudLensAPI":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# Streamlit Integration Helpers


@st.cache_resource
def get_api_client() -> FraudLensAPI:
    """Get or create a cached API client instance for Streamlit."""
    return FraudLensAPI()


def api_call_with_spinner(
    api_method: str,
    *args,
    spinner_text: str = "Processing...",
    **kwargs,
) -> Any:
    """Make an API call with a Streamlit spinner and graceful error handling.

    Usage:
        result = api_call_with_spinner(
            "predict", transaction,
            spinner_text="Analyzing transaction..."
        )
    """
    client = get_api_client()
    method = getattr(client, api_method, None)
    if method is None:
        st.error(f"Unknown API method: {api_method}")
        return None

    try:
        with st.spinner(spinner_text):
            result = method(*args, **kwargs)
        return result
    except FraudLensAPIError as e:
        if e.status_code == 503:
            st.warning(f"⚠️ Service temporarily unavailable: {e}")
        else:
            st.error(f"❌ Request failed: {e}")
        return None
    except (requests.RequestException, ValueError, OSError) as e:
        st.error(f"❌ Unexpected error: {e}")
        return None
