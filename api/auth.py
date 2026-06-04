"""API key authentication for the Savisor Node REST API.

Uses a pre-shared key passed via the ``SAVISOR_API_KEY`` environment variable.
Callers must present the key in the ``Authorization: Bearer <key>`` header.
Comparison is constant-time (``hmac.compare_digest``) to prevent timing
side-channels.
"""

import hmac
import logging
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger("api.auth")

_API_KEY: str | None = os.environ.get("SAVISOR_API_KEY")

_bearer_scheme = HTTPBearer(
    scheme_name="BearerAPIKey",
    description="Pre-shared API key sent as a Bearer token.",
    auto_error=False,
)


def enforce_api_key_configured() -> None:
    """Raise if the API key env var is missing or empty.

    Call this during application startup to crash fast rather than
    silently serving unauthenticated traffic.
    """
    if not _API_KEY:
        raise RuntimeError(
            "SAVISOR_API_KEY environment variable is not set. "
            "The API refuses to start without an API key configured."
        )
    logger.info("API key authentication is active.")


_bearer_dependency = Depends(_bearer_scheme)


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = _bearer_dependency,
) -> str:
    """FastAPI dependency that enforces Bearer-token authentication.

    Returns the validated token string on success.
    Raises ``HTTPException(401)`` on missing/invalid credentials.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # _API_KEY is guaranteed non-None after enforce_api_key_configured()
    if not hmac.compare_digest(credentials.credentials, _API_KEY):  # type: ignore[arg-type]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
