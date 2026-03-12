"""Authentication module for Operation HOPE AI.

Provides user authentication with role-based access control.
Roles:
  - admin:    Full access to management, approvals, analytics, routing.
  - engineer: Sees only tickets assigned to them; can provide resolutions.
"""

import hashlib
from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"


@dataclass
class User:
    username: str
    display_name: str
    role: Role
    email: str


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


_USERS: dict[str, dict] = {
    "admin": {
        "password_hash": _hash("admin123"),
        "display_name": "Admin",
        "role": Role.ADMIN,
        "email": "admin@operationhope.org",
    },
    "torri": {
        "password_hash": _hash("Welcome123"),
        "display_name": "Torri",
        "role": Role.ENGINEER,
        "email": "torri@operationhope.org",
    },
    "danita": {
        "password_hash": _hash("Welcome123"),
        "display_name": "Danita",
        "role": Role.ENGINEER,
        "email": "danita@operationhope.org",
    },
    "shonda": {
        "password_hash": _hash("Welcome123"),
        "display_name": "Shonda",
        "role": Role.ENGINEER,
        "email": "shonda@operationhope.org",
    },
    "abhishek": {
        "password_hash": _hash("Welcome123"),
        "display_name": "Abhishek",
        "role": Role.ENGINEER,
        "email": "abhishek@operationhope.org",
    },
    "praveen": {
        "password_hash": _hash("Welcome123"),
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


def authenticate(username: str, password: str) -> User | None:
    """Validate credentials and return a User object, or None if invalid."""
    user_data = _USERS.get(username.lower())
    if user_data is None:
        return None
    if _hash(password) != user_data["password_hash"]:
        return None
    return User(
        username=username.lower(),
        display_name=user_data["display_name"],
        role=user_data["role"],
        email=user_data["email"],
    )
