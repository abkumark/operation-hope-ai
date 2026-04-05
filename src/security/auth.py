"""
Secure Authentication and Authorization Module

This module provides enterprise-grade authentication and authorization
with proper security controls, audit logging, and role-based access control.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Dict, Any
from functools import wraps

import bcrypt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

from config.settings import get_settings

logger = logging.getLogger(__name__)

# Initialize security scheme
security = HTTPBearer(auto_error=False)

class Role(str, Enum):
    """User roles with hierarchical permissions."""
    ADMIN = "admin"
    ENGINEER = "engineer"

    @classmethod
    def get_permissions(cls, role: 'Role') -> set[str]:
        """Get permissions for a given role."""
        permissions = {
            cls.ADMIN: {
                "tickets.read", "tickets.write", "tickets.delete",
                "users.read", "users.write", "analytics.read",
                "config.read", "config.write", "approvals.manage"
            },
            cls.ENGINEER: {
                "tickets.read", "tickets.write", "analytics.read"
            }
        }
        return permissions.get(role, set())


class User(BaseModel):
    """User model with proper validation."""
    username: str
    display_name: str
    role: Role
    email: EmailStr
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        """Pydantic config for User model."""
        use_enum_values = True


class TokenData(BaseModel):
    """JWT token payload data."""
    sub: str  # subject (username)
    role: str
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for token revocation


class AuthenticationError(Exception):
    """Custom authentication error."""
    pass


class AuthorizationError(Exception):
    """Custom authorization error."""
    pass


def _hash_password(password: str) -> str:
    """Hash a password securely using bcrypt with salt."""
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")

    salt = bcrypt.gensalt(rounds=12)  # Higher rounds for better security
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False


def _get_jwt_config() -> tuple[str, str, int]:
    """Get JWT configuration with secure defaults."""
    settings = get_settings()

    # Generate secure secret key if not provided
    secret_key = settings.jwt_secret_key
    if not secret_key or secret_key == "operation-hope-ai-secret-key-change-in-production":
        logger.warning("Using default JWT secret - THIS IS INSECURE FOR PRODUCTION!")
        secret_key = secrets.token_urlsafe(32)

    algorithm = "HS256"
    expire_minutes = 480  # 8 hours

    return secret_key, algorithm, expire_minutes


def create_access_token(username: str, role: Role, user_id: Optional[str] = None) -> str:
    """
    Create a secure JWT access token with proper claims.

    Args:
        username: The username for the token subject
        role: User role for authorization
        user_id: Optional user ID for token binding

    Returns:
        JWT token string

    Raises:
        ValueError: If username or role is invalid
    """
    if not username or not role:
        raise ValueError("Username and role are required")

    secret_key, algorithm, expire_minutes = _get_jwt_config()

    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)

    payload = {
        "sub": username,  # Subject
        "role": role.value,
        "exp": expire,  # Expiration time
        "iat": now,  # Issued at
        "jti": secrets.token_urlsafe(16),  # JWT ID for revocation
    }

    if user_id:
        payload["uid"] = user_id

    try:
        token = jwt.encode(payload, secret_key, algorithm=algorithm)
        logger.info(f"Access token created for user: {username}")
        return token
    except Exception as e:
        logger.error(f"Token creation failed for {username}: {e}")
        raise AuthenticationError("Failed to create access token")


def verify_token(token: str) -> TokenData:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenData with decoded claims

    Raises:
        AuthenticationError: If token is invalid or expired
    """
    if not token:
        raise AuthenticationError("Token is required")

    secret_key, algorithm, _ = _get_jwt_config()

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        # Validate required claims
        username = payload.get("sub")
        role = payload.get("role")
        exp = payload.get("exp")

        if not all([username, role, exp]):
            raise AuthenticationError("Invalid token claims")

        # Check expiration
        exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
        if exp_datetime < datetime.now(timezone.utc):
            raise AuthenticationError("Token has expired")

        return TokenData(
            sub=username,
            role=role,
            exp=exp_datetime,
            iat=datetime.fromtimestamp(payload.get("iat", 0), tz=timezone.utc),
            jti=payload.get("jti", "")
        )

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise AuthenticationError("Invalid token")
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise AuthenticationError("Token verification failed")


def get_user_by_username(username: str) -> Optional[User]:
    """
    Retrieve user by username from storage.

    This is a temporary implementation using in-memory storage.
    In production, this should use a proper database.
    """
    # Temporary in-memory user store for demo
    # TODO: Replace with database-backed user management
    demo_users = {
        "admin": {
            "password_hash": _hash_password("admin123"),
            "display_name": "System Administrator",
            "role": Role.ADMIN,
            "email": "admin@operationhope.org",
            "created_at": datetime.now(timezone.utc),
        },
        "torri": {
            "password_hash": _hash_password("Welcome123"),
            "display_name": "Torri",
            "role": Role.ENGINEER,
            "email": "torri@operationhope.org",
            "created_at": datetime.now(timezone.utc),
        },
        "danita": {
            "password_hash": _hash_password("Welcome123"),
            "display_name": "Danita",
            "role": Role.ENGINEER,
            "email": "danita@operationhope.org",
            "created_at": datetime.now(timezone.utc),
        },
        "shonda": {
            "password_hash": _hash_password("Welcome123"),
            "display_name": "Shonda",
            "role": Role.ENGINEER,
            "email": "shonda@operationhope.org",
            "created_at": datetime.now(timezone.utc),
        },
        "abhishek": {
            "password_hash": _hash_password("Welcome123"),
            "display_name": "Abhishek",
            "role": Role.ENGINEER,
            "email": "abhishek@operationhope.org",
            "created_at": datetime.now(timezone.utc),
        },
        "praveen": {
            "password_hash": _hash_password("Welcome123"),
            "display_name": "Praveen",
            "role": Role.ENGINEER,
            "email": "praveen@operationhope.org",
            "created_at": datetime.now(timezone.utc),
        },
    }

    user_data = demo_users.get(username.lower())
    if not user_data:
        return None

    return User(
        username=username.lower(),
        display_name=user_data["display_name"],
        role=user_data["role"],
        email=user_data["email"],
        created_at=user_data["created_at"],
    )


def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password.

    Args:
        username: The username to authenticate
        password: The plain text password

    Returns:
        User object if authentication successful, None otherwise

    Raises:
        AuthenticationError: If authentication fails due to system error
    """
    if not username or not password:
        logger.warning("Authentication attempted with empty credentials")
        return None

    try:
        # Get user from storage
        user = get_user_by_username(username)
        if not user:
            logger.warning(f"Authentication failed: user not found - {username}")
            return None

        # Check if user is active
        if not user.is_active:
            logger.warning(f"Authentication failed: inactive user - {username}")
            return None

        # Verify password (this is demo implementation)
        # In production, retrieve password hash from database
        demo_users = {
            "admin": _hash_password("admin123"),
            "torri": _hash_password("Welcome123"),
            "danita": _hash_password("Welcome123"),
            "shonda": _hash_password("Welcome123"),
            "abhishek": _hash_password("Welcome123"),
            "praveen": _hash_password("Welcome123"),
        }

        password_hash = demo_users.get(username.lower())
        if not password_hash or not _verify_password(password, password_hash):
            logger.warning(f"Authentication failed: invalid password - {username}")
            return None

        logger.info(f"User authenticated successfully: {username}")
        return user

    except Exception as e:
        logger.error(f"Authentication system error for {username}: {e}")
        raise AuthenticationError("Authentication system error")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    FastAPI dependency to get current authenticated user.

    Args:
        credentials: HTTP Bearer token from request

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_data = verify_token(credentials.credentials)
        user = get_user_by_username(token_data.sub)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Authentication dependency error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system error"
        )


def require_role(*allowed_roles: Role):
    """
    Decorator to require specific roles for endpoint access.

    Args:
        allowed_roles: Roles that are allowed to access the endpoint

    Returns:
        FastAPI dependency function

    Example:
        @app.get("/admin-only")
        @require_role(Role.ADMIN)
        async def admin_endpoint(user: User = Depends(get_current_user)):
            pass
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                f"Authorization failed: {current_user.username} "
                f"(role: {current_user.role}) attempted to access "
                f"endpoint requiring roles: {allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in allowed_roles]}"
            )
        return current_user

    return role_checker


def require_permission(permission: str):
    """
    Decorator to require specific permission for endpoint access.

    Args:
        permission: Permission string (e.g., "tickets.write")

    Returns:
        FastAPI dependency function
    """
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_permissions = Role.get_permissions(current_user.role)

        if permission not in user_permissions:
            logger.warning(
                f"Permission denied: {current_user.username} "
                f"(role: {current_user.role}) lacks permission: {permission}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}"
            )
        return current_user

    return permission_checker


# Backward compatibility with existing auth.py
def get_user_email(username: str) -> str:
    """Get user email by username for backward compatibility."""
    user = get_user_by_username(username)
    return user.email if user else ""


def get_engineer_emails(usernames: list[str]) -> list[tuple[str, str]]:
    """Get engineer emails for backward compatibility."""
    result = []
    for username in usernames:
        user = get_user_by_username(username)
        if user and user.role == Role.ENGINEER:
            result.append((user.display_name, user.email))
    return result


# Engineer list for backward compatibility
ENGINEER_LIST = [
    {"username": "torri", "display_name": "Torri"},
    {"username": "danita", "display_name": "Danita"},
    {"username": "shonda", "display_name": "Shonda"},
    {"username": "abhishek", "display_name": "Abhishek"},
    {"username": "praveen", "display_name": "Praveen"},
]