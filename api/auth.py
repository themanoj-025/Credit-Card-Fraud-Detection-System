"""
FraudLens API — Authentication & Authorization

API key authentication via X-API-Key header, validated against
configured keys. Supports read-only and admin key tiers.

Usage:
    from api.auth import require_api_key, require_admin_key

    @router.post("/predict")
    async def predict(api_key: str = Depends(require_api_key)) -> Any:
        ...
"""

import hashlib
import hmac
import logging
import os

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# Configuration

# Load API keys from environment (semicolon-separated for multiple keys)
# Format: FRAUDLENS_API_KEYS="key1_hash=admin;key2_hash=readonly"
# Keys are stored as SHA-256 hashes, never in plaintext.
_API_KEY_CONFIG = os.environ.get("FRAUDLENS_API_KEYS", "")
_ADMIN_SECRET = os.environ.get("FRAUDLENS_ADMIN_SECRET", "")

# Security scheme

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _verify_api_key(api_key: str) -> str | None:
    """
    Verify an API key against configured hashed keys.

    Args:
        api_key: The raw API key from the request header

    Returns:
        The key's role ("admin" or "readonly") if valid, None otherwise
    """
    if not _API_KEY_CONFIG:
        # No keys configured — allow all requests (development mode)
        return "admin"

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    for entry in _API_KEY_CONFIG.split(";"):
        entry = entry.strip()
        if "=" in entry:
            stored_hash, role = entry.split("=", 1)
            if hmac.compare_digest(key_hash, stored_hash):
                return role
    return None


async def require_api_key(
    api_key: str | None = Security(api_key_header),
) -> str | None:
    """
    Dependency that requires a valid API key (any role).

    In development mode (no FRAUDLENS_API_KEYS configured), authentication
    is skipped and all requests are allowed.

    Usage:
        @router.get("/predict")
        async def predict(key: str | None = Depends(require_api_key)) -> Any:
            ...
    """
    # Dev mode: no API keys configured — allow all requests
    if not is_auth_enabled():
        return "dev-mode"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "APIKey"},
        )

    role = _verify_api_key(api_key)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "APIKey"},
        )

    return api_key


async def require_admin_key(
    api_key: str = Depends(require_api_key),
) -> str:
    """
    Dependency that requires a valid ADMIN-level API key.

    Usage:
        @router.post("/admin/keys")
        async def create_key(key: str = Depends(require_admin_key)) -> Any:
            ...
    """
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    for entry in _API_KEY_CONFIG.split(";"):
        entry = entry.strip()
        if "=" in entry:
            stored_hash, role = entry.split("=", 1)
            if hmac.compare_digest(key_hash, stored_hash) and role == "admin":
                return api_key

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )


def is_auth_enabled() -> bool:
    """Check if authentication is configured."""
    return bool(_API_KEY_CONFIG)
