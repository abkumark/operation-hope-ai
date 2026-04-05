"""
Security Middleware Module

This module provides authentication middleware and security controls
for the FastAPI application.
"""

import logging
import time
from typing import Optional, Set
from urllib.parse import urlparse

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import verify_token, AuthenticationError

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware that enforces authentication on protected endpoints.
    """

    def __init__(
        self,
        app,
        public_endpoints: Optional[Set[str]] = None,
        require_auth_by_default: bool = True
    ):
        """
        Initialize authentication middleware.

        Args:
            app: FastAPI application instance
            public_endpoints: Set of endpoint paths that don't require authentication
            require_auth_by_default: Whether to require auth by default
        """
        super().__init__(app)
        self.require_auth_by_default = require_auth_by_default

        # Default public endpoints
        default_public = {
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/api/v1/tickets/submit",  # Public ticket submission
            "/static",  # Static files
        }

        self.public_endpoints = public_endpoints or default_public

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce authentication."""
        start_time = time.time()

        try:
            # Check if endpoint requires authentication
            if self._is_public_endpoint(request.url.path):
                response = await call_next(request)
                return self._add_security_headers(response, start_time)

            # Extract and validate authentication token
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return self._unauthorized_response("Missing or invalid authorization header")

            token = auth_header.replace("Bearer ", "")

            try:
                # Verify token and add user info to request state
                token_data = verify_token(token)
                request.state.user = token_data
                request.state.authenticated = True

                # Log successful authentication
                logger.info(f"Authenticated request: {request.method} {request.url.path} - User: {token_data.sub}")

            except AuthenticationError as e:
                logger.warning(f"Authentication failed for {request.url.path}: {e}")
                return self._unauthorized_response(str(e))

            # Process request
            response = await call_next(request)
            return self._add_security_headers(response, start_time)

        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Authentication system error"}
            )

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public."""
        # Exact match
        if path in self.public_endpoints:
            return True

        # Prefix match for static files and similar
        for public_path in self.public_endpoints:
            if path.startswith(public_path):
                return True

        return False

    def _unauthorized_response(self, detail: str) -> JSONResponse:
        """Return unauthorized response."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"}
        )

    def _add_security_headers(self, response, start_time: float):
        """Add security headers to response."""
        processing_time = time.time() - start_time

        # Security headers
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "X-Process-Time": str(processing_time),
        }

        for header, value in security_headers.items():
            response.headers[header] = value

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple rate limiting middleware.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000
    ):
        """
        Initialize rate limiting middleware.

        Args:
            app: FastAPI application instance
            requests_per_minute: Maximum requests per minute per IP
            requests_per_hour: Maximum requests per hour per IP
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.request_counts = {}  # In production, use Redis or similar

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce rate limiting."""
        client_ip = self._get_client_ip(request)

        if self._is_rate_limited(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )

        # Record request
        self._record_request(client_ip)

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        # Check for forwarded IP (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Check for real IP (behind load balancer)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to remote address
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if client is rate limited."""
        current_time = time.time()

        # Clean up old entries (older than 1 hour)
        self.request_counts = {
            ip: [timestamp for timestamp in timestamps if current_time - timestamp < 3600]
            for ip, timestamps in self.request_counts.items()
            if any(current_time - timestamp < 3600 for timestamp in timestamps)
        }

        if client_ip not in self.request_counts:
            return False

        timestamps = self.request_counts[client_ip]

        # Check requests in last minute
        minute_ago = current_time - 60
        minute_requests = len([t for t in timestamps if t > minute_ago])
        if minute_requests >= self.requests_per_minute:
            return True

        # Check requests in last hour
        if len(timestamps) >= self.requests_per_hour:
            return True

        return False

    def _record_request(self, client_ip: str) -> None:
        """Record request timestamp."""
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []

        self.request_counts[client_ip].append(time.time())


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add comprehensive security headers.
    """

    def __init__(self, app):
        """Initialize security headers middleware."""
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """Add security headers to all responses."""
        response = await call_next(request)

        # Comprehensive security headers
        security_headers = {
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",

            # Prevent clickjacking
            "X-Frame-Options": "DENY",

            # XSS protection
            "X-XSS-Protection": "1; mode=block",

            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",

            # Content Security Policy (basic)
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self'"
            ),

            # Strict Transport Security (if HTTPS)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",

            # Feature Policy / Permissions Policy
            "Permissions-Policy": (
                "camera=(), microphone=(), geolocation=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            ),
        }

        for header, value in security_headers.items():
            response.headers[header] = value

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for comprehensive request logging.
    """

    def __init__(self, app, log_sensitive_data: bool = False):
        """
        Initialize request logging middleware.

        Args:
            app: FastAPI application instance
            log_sensitive_data: Whether to log potentially sensitive data
        """
        super().__init__(app)
        self.log_sensitive_data = log_sensitive_data

    async def dispatch(self, request: Request, call_next):
        """Log request details and processing time."""
        start_time = time.time()

        # Extract request info
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")
        method = request.method
        path = request.url.path
        query_params = str(request.query_params) if request.query_params else ""

        # Get authenticated user if available
        user_info = getattr(request.state, 'user', None)
        username = user_info.sub if user_info else "anonymous"

        try:
            response = await call_next(request)
            processing_time = time.time() - start_time
            status_code = response.status_code

            # Log request completion
            logger.info(
                f"Request completed - "
                f"Method: {method} "
                f"Path: {path} "
                f"Status: {status_code} "
                f"User: {username} "
                f"IP: {client_ip} "
                f"Time: {processing_time:.3f}s"
            )

            # Add processing time header
            response.headers["X-Process-Time"] = str(processing_time)

            return response

        except Exception as e:
            processing_time = time.time() - start_time

            # Log request error
            logger.error(
                f"Request failed - "
                f"Method: {method} "
                f"Path: {path} "
                f"User: {username} "
                f"IP: {client_ip} "
                f"Time: {processing_time:.3f}s "
                f"Error: {str(e)}"
            )

            raise

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        # Check for forwarded IP (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Check for real IP (behind load balancer)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to remote address
        return request.client.host if request.client else "unknown"