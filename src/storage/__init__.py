"""SQLite-backed storage helpers for demo persistence."""

from src.storage.sqlite_db import (
    clear_all_data,
    get_connection,
    init_database,
    next_ticket_id,
)
