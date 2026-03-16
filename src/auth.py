"""Authentication module for Operation HOPE AI.

Provides user authentication with role-based access control + JWT tokens.
Roles:
  - admin:    Full access to management, approvals, analytics, routing.
  - engineer: Sees only tickets assigned to them; can provide resolutions.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import bcrypt
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET_KEY = "operation-hope-ai-secret-key-change-in-production"  # Override via env
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 480  # 8 hours


class Role(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"


@dataclass
class User:
    username: str
    display_name: str
    role: Role
    email: str


def _hash_pw(pw: str) -> str:
    """Hash a password with bcrypt (salt is embedded in the hash)."""
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _verify_pw(pw: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


_USERS: dict[str, dict] = {
    "admin": {
        "password_hash": _hash_pw("admin123"),
        "display_name": "Admin",
        "role": Role.ADMIN,
        "email": "admin@operationhope.org",
    },
    "torri": {
        "password_hash": _hash_pw("Welcome123"),
        "display_name": "Torri",
        "role": Role.ENGINEER,
        "email": "torri@operationhope.org",
    },
    "danita": {
        "password_hash": _hash_pw("Welcome123"),
        "display_name": "Danita",
        "role": Role.ENGINEER,
        "email": "danita@operationhope.org",
    },
    "shonda": {
        "password_hash": _hash_pw("Welcome123"),
        "display_name": "Shonda",
        "role": Role.ENGINEER,
        "email": "shonda@operationhope.org",
    },
    "abhishek": {
        "password_hash": _hash_pw("Welcome123"),
        "display_name": "Abhishek",
        "role": Role.ENGINEER,
        "email": "abhishek@operationhope.org",
    },
    "praveen": {
        "password_hash": _hash_pw("Welcome123"),
        "display_name": "Praveen",
        "role": Role.ENGINEER,
        "email": "praveen@operationhope.org",
    },
}

ENGINEER_LIST = [
    {"username": u, "display_name": d["display_name"]}
    for u, d in _USERS.items()
    if d["role"] == Role.ENGINEER
]


def get_user_email(username: str) -> str:
    """Return the email address for a given username, or empty string if not found."""
    user_data = _USERS.get(username.lower())
    return user_data["email"] if user_data else ""


def get_engineer_emails(usernames: list[str]) -> list[tuple[str, str]]:
    """Return list of (display_name, email) tuples for the given engineer usernames."""
    result = []
    for u in usernames:
        data = _USERS.get(u.lower())
        if data and data.get("email"):
            result.append((data["display_name"], data["email"]))
    return result


def authenticate(username: str, password: str) -> User | None:
    """Validate credentials and return a User object, or None if invalid."""
    user_data = _USERS.get(username.lower())
    if user_data is None:
        return None
    if not _verify_pw(password, user_data["password_hash"]):
        return None
    return User(
        username=username.lower(),
        display_name=user_data["display_name"],
        role=user_data["role"],
        email=user_data["email"],
    )


def create_access_token(username: str, role: str) -> str:
    """Create a JWT access token with expiration."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[User]:
    """Verify a JWT token and return the User, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub", "")
        if not username:
            return None
        user_data = _USERS.get(username.lower())
        if user_data is None:
            return None
        return User(
            username=username.lower(),
            display_name=user_data["display_name"],
            role=user_data["role"],
            email=user_data["email"],
        )
    except JWTError:
        return None
