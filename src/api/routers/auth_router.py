"""Authentication routes — login, token issuance."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.deps import require_auth
from src.auth import ENGINEER_LIST, User, authenticate, create_access_token

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


@router.post("/auth/login")
async def login(request: LoginRequest) -> dict[str, Any]:
    """Authenticate user and return profile info with JWT token."""
    from fastapi import HTTPException

    user = authenticate(request.username, request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(username=user.username, role=user.role.value)
    return {
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role.value,
        "email": user.email,
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/auth/me")
async def me(user: User = Depends(require_auth)) -> dict[str, Any]:
    """Return the authenticated user's profile for session restore checks."""
    return {
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role.value,
        "email": user.email,
    }


@router.get("/users/engineers")
async def list_engineers() -> dict[str, Any]:
    """Return the list of available engineers for ticket assignment."""
    return {"engineers": ENGINEER_LIST}
