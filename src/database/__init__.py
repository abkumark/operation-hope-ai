"""Database module with secure operations and connection management."""

from .connection import (
    get_connection,
    init_database,
    close_connection,
    DatabaseManager,
)
from .models import (
    TicketModel,
    ApprovalModel,
    UserModel,
    MetricsModel,
)
from .repository import (
    TicketRepository,
    ApprovalRepository,
    MetricsRepository,
)

__all__ = [
    "get_connection",
    "init_database",
    "close_connection",
    "DatabaseManager",
    "TicketModel",
    "ApprovalModel",
    "UserModel",
    "MetricsModel",
    "TicketRepository",
    "ApprovalRepository",
    "MetricsRepository",
]