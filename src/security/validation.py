"""
Input Validation and Sanitization Module

This module provides comprehensive input validation, sanitization,
and security checks to prevent common web vulnerabilities.
"""

import html
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, EmailStr, validator, Field
import bleach

logger = logging.getLogger(__name__)

# Security configuration
ALLOWED_HTML_TAGS = ['p', 'br', 'b', 'i', 'u', 'strong', 'em']
ALLOWED_HTML_ATTRIBUTES = {}
MAX_TEXT_LENGTH = 10000
MAX_SUBJECT_LENGTH = 255
MAX_EMAIL_LENGTH = 255


class ValidationError(Exception):
    """Custom validation error."""
    pass


class TicketSubmissionRequest(BaseModel):
    """Validated ticket submission request."""
    subject: str = Field(..., min_length=5, max_length=MAX_SUBJECT_LENGTH)
    description: str = Field(..., min_length=10, max_length=MAX_TEXT_LENGTH)
    submitter_name: str = Field(..., min_length=2, max_length=100)
    submitter_email: EmailStr
    phone_number: Optional[str] = Field(None, max_length=20)

    @validator('subject')
    def validate_subject(cls, v):
        """Validate and sanitize subject."""
        if not v or not v.strip():
            raise ValueError('Subject cannot be empty')
        return sanitize_text(v.strip())

    @validator('description')
    def validate_description(cls, v):
        """Validate and sanitize description."""
        if not v or not v.strip():
            raise ValueError('Description cannot be empty')
        return sanitize_html(v.strip())

    @validator('submitter_name')
    def validate_submitter_name(cls, v):
        """Validate submitter name."""
        if not v or not v.strip():
            raise ValueError('Submitter name cannot be empty')
        # Only allow letters, spaces, hyphens, and apostrophes
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", v.strip()):
            raise ValueError('Submitter name contains invalid characters')
        return v.strip()

    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Validate phone number format."""
        if v is None or v.strip() == '':
            return None
        return validate_phone_number(v.strip())


class TicketUpdateRequest(BaseModel):
    """Validated ticket update request."""
    subject: Optional[str] = Field(None, max_length=MAX_SUBJECT_LENGTH)
    description: Optional[str] = Field(None, max_length=MAX_TEXT_LENGTH)
    status: Optional[str] = Field(None, regex=r'^(Open|Assigned|WorkInProgress|Resolved|Completed|Escalated|HR)$')
    assigned_to: Optional[str] = Field(None, max_length=50)
    ai_resolution: Optional[str] = Field(None, max_length=MAX_TEXT_LENGTH)

    @validator('subject')
    def validate_subject(cls, v):
        """Validate and sanitize subject."""
        if v is not None and v.strip():
            return sanitize_text(v.strip())
        return v

    @validator('description')
    def validate_description(cls, v):
        """Validate and sanitize description."""
        if v is not None and v.strip():
            return sanitize_html(v.strip())
        return v

    @validator('ai_resolution')
    def validate_ai_resolution(cls, v):
        """Validate and sanitize AI resolution."""
        if v is not None and v.strip():
            return sanitize_html(v.strip())
        return v


def validate_email(email: str) -> str:
    """
    Validate and normalize email address.

    Args:
        email: Email address to validate

    Returns:
        Normalized email address

    Raises:
        ValidationError: If email is invalid
    """
    if not email or not email.strip():
        raise ValidationError("Email address is required")

    email = email.strip().lower()

    if len(email) > MAX_EMAIL_LENGTH:
        raise ValidationError(f"Email address too long (max {MAX_EMAIL_LENGTH} characters)")

    # Basic email validation regex
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        raise ValidationError("Invalid email address format")

    # Check for suspicious patterns
    suspicious_patterns = [
        r'javascript:', r'data:', r'vbscript:', r'onload=', r'onerror='
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, email, re.IGNORECASE):
            raise ValidationError("Email contains suspicious content")

    return email


def validate_phone_number(phone: str) -> str:
    """
    Validate and normalize phone number.

    Args:
        phone: Phone number to validate

    Returns:
        Normalized phone number

    Raises:
        ValidationError: If phone number is invalid
    """
    if not phone or not phone.strip():
        return ""

    # Remove common separators
    phone = re.sub(r'[\s\-\(\)\.]', '', phone.strip())

    # Allow international format with + prefix
    if phone.startswith('+'):
        phone_regex = r'^\+[1-9]\d{6,14}$'
    else:
        # US format validation
        phone_regex = r'^[1-9]\d{9}$'

    if not re.match(phone_regex, phone):
        raise ValidationError("Invalid phone number format")

    return phone


def sanitize_text(text: str) -> str:
    """
    Sanitize plain text input.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text

    Raises:
        ValidationError: If text contains dangerous content
    """
    if not isinstance(text, str):
        raise ValidationError("Text must be a string")

    if len(text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"Text too long (max {MAX_TEXT_LENGTH} characters)")

    # HTML escape the text
    sanitized = html.escape(text)

    # Check for potential script injection
    dangerous_patterns = [
        r'javascript:', r'data:', r'vbscript:', r'onload=', r'onerror=',
        r'<script', r'</script>', r'eval\(', r'setTimeout\(', r'setInterval\('
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            logger.warning(f"Potentially dangerous content detected: {pattern}")
            raise ValidationError("Text contains potentially dangerous content")

    return sanitized


def sanitize_html(html_content: str) -> str:
    """
    Sanitize HTML content using whitelist approach.

    Args:
        html_content: HTML content to sanitize

    Returns:
        Sanitized HTML content

    Raises:
        ValidationError: If content is invalid
    """
    if not isinstance(html_content, str):
        raise ValidationError("HTML content must be a string")

    if len(html_content) > MAX_TEXT_LENGTH:
        raise ValidationError(f"HTML content too long (max {MAX_TEXT_LENGTH} characters)")

    try:
        # Use bleach to sanitize HTML with whitelist approach
        sanitized = bleach.clean(
            html_content,
            tags=ALLOWED_HTML_TAGS,
            attributes=ALLOWED_HTML_ATTRIBUTES,
            strip=True  # Remove disallowed tags entirely
        )

        # Additional checks for remaining dangerous content
        dangerous_patterns = [
            r'javascript:', r'data:', r'vbscript:',
            r'onload=', r'onerror=', r'onclick='
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logger.warning(f"Dangerous pattern found after sanitization: {pattern}")
                # Remove the entire content if still dangerous
                sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)

        return sanitized.strip()

    except Exception as e:
        logger.error(f"HTML sanitization failed: {e}")
        raise ValidationError("Failed to sanitize HTML content")


def validate_url(url: str) -> str:
    """
    Validate URL format and check for suspicious schemes.

    Args:
        url: URL to validate

    Returns:
        Validated URL

    Raises:
        ValidationError: If URL is invalid or suspicious
    """
    if not url or not url.strip():
        raise ValidationError("URL is required")

    url = url.strip()

    try:
        parsed = urlparse(url)

        # Check for allowed schemes
        allowed_schemes = ['http', 'https']
        if parsed.scheme.lower() not in allowed_schemes:
            raise ValidationError(f"URL scheme not allowed: {parsed.scheme}")

        # Check for localhost/internal URLs in production
        dangerous_hosts = ['localhost', '127.0.0.1', '0.0.0.0', '::1']
        if parsed.hostname and parsed.hostname.lower() in dangerous_hosts:
            logger.warning(f"Potentially dangerous host in URL: {parsed.hostname}")

        return url

    except Exception as e:
        logger.error(f"URL validation failed: {e}")
        raise ValidationError("Invalid URL format")


def validate_ticket_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate complete ticket input data.

    Args:
        data: Dictionary containing ticket data

    Returns:
        Validated and sanitized ticket data

    Raises:
        ValidationError: If validation fails
    """
    try:
        # Use Pydantic model for validation
        if 'ticket_id' in data:
            # This is an update request
            validated = TicketUpdateRequest(**data)
        else:
            # This is a new ticket submission
            validated = TicketSubmissionRequest(**data)

        return validated.dict(exclude_none=True)

    except Exception as e:
        logger.error(f"Ticket input validation failed: {e}")
        raise ValidationError(f"Ticket validation failed: {str(e)}")


def validate_json_field(json_str: str, max_length: int = 10000) -> str:
    """
    Validate JSON field content.

    Args:
        json_str: JSON string to validate
        max_length: Maximum allowed length

    Returns:
        Validated JSON string

    Raises:
        ValidationError: If JSON is invalid
    """
    if not json_str:
        return "{}"

    if len(json_str) > max_length:
        raise ValidationError(f"JSON content too long (max {max_length} characters)")

    try:
        import json
        # Try to parse to ensure valid JSON
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format: {e}")
        raise ValidationError("Invalid JSON format")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.

    Args:
        filename: Filename to sanitize

    Returns:
        Sanitized filename

    Raises:
        ValidationError: If filename is invalid
    """
    if not filename or not filename.strip():
        raise ValidationError("Filename is required")

    # Remove path separators and dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename.strip())

    # Remove path traversal attempts
    sanitized = sanitized.replace('..', '_')

    # Limit length
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:250] + ext

    if not sanitized or sanitized in ['.', '..']:
        raise ValidationError("Invalid filename")

    return sanitized


def validate_sql_identifier(identifier: str) -> str:
    """
    Validate SQL identifier (table/column name) for dynamic queries.

    Args:
        identifier: SQL identifier to validate

    Returns:
        Validated identifier

    Raises:
        ValidationError: If identifier is invalid
    """
    if not identifier or not identifier.strip():
        raise ValidationError("SQL identifier is required")

    # Only allow alphanumeric characters and underscores
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
        raise ValidationError("Invalid SQL identifier format")

    # Check against SQL keywords (basic list)
    sql_keywords = {
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
        'ALTER', 'INDEX', 'TABLE', 'FROM', 'WHERE', 'ORDER', 'GROUP'
    }

    if identifier.upper() in sql_keywords:
        raise ValidationError("SQL identifier cannot be a reserved keyword")

    return identifier