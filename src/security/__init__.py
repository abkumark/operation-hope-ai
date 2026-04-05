"""Security module for authentication, authorization, and validation."""

from .auth import (
    authenticate_user,
    create_access_token,
    verify_token,
    get_current_user,
    require_role,
)
from .validation import (
    validate_email,
    validate_phone_number,
    sanitize_html,
    validate_ticket_input,
)
from .middleware import AuthenticationMiddleware

__all__ = [
    "authenticate_user",
    "create_access_token",
    "verify_token",
    "get_current_user",
    "require_role",
    "validate_email",
    "validate_phone_number",
    "sanitize_html",
    "validate_ticket_input",
    "AuthenticationMiddleware",
]