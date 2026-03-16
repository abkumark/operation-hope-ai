"""JWT authentication dependency for FastAPI routes.

Usage:
    from src.api.deps import require_auth, require_admin

    @router.get("/protected")
    async def protected(user: User = Depends(require_auth)):
        ...

    @router.get("/admin-only")
    async def admin_only(user: User = Depends(require_admin)):
        ...
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth import Role, User, verify_token

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[User]:
    """Extract and verify JWT from Authorization header. Returns None if no token."""
    if credentials is None:
        return None
    user = verify_token(credentials.credentials)
    return user


async def require_auth(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """Dependency that requires a valid JWT token. Returns the authenticated User."""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    user: User = Depends(require_auth),
) -> User:
    """Dependency that requires an admin user."""
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin access required.",
        )
    return user


async def require_engineer_or_admin(
    user: User = Depends(require_auth),
) -> User:
    """Dependency that requires an engineer or admin role."""
    if user.role not in (Role.ADMIN, Role.ENGINEER):
        raise HTTPException(status_code=403, detail="Insufficient permissions.")
    return user
