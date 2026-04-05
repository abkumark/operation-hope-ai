"""
Secure Database Connection Management

This module provides secure, thread-safe database connections with
proper error handling, connection pooling, and transaction management.
"""

import logging
import sqlite3
import threading
import contextlib
from pathlib import Path
from typing import Optional, Generator, Any, Dict
from contextlib import contextmanager

from config.settings import get_settings

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom database error."""
    pass


class DatabaseManager:
    """
    Thread-safe database connection manager with proper connection pooling.
    """

    def __init__(self, database_path: Optional[Path] = None):
        """
        Initialize database manager.

        Args:
            database_path: Path to SQLite database file
        """
        self._lock = threading.Lock()
        self._local = threading.local()
        self._database_path = database_path or self._get_database_path()
        self._initialized = False

    def _get_database_path(self) -> Path:
        """Get database path from settings."""
        settings = get_settings()
        db_path = Path(settings.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Get thread-safe database connection with automatic cleanup.

        Yields:
            SQLite connection with proper configuration

        Raises:
            DatabaseError: If connection fails
        """
        connection = None
        try:
            connection = self._get_or_create_connection()
            yield connection
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"Database operation failed: {e}")
            raise DatabaseError(f"Database operation failed: {e}")
        finally:
            # Connection will be reused in the same thread
            pass

    def _get_or_create_connection(self) -> sqlite3.Connection:
        """Get existing connection or create new one for current thread."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = self._create_connection()

        # Test if connection is still valid
        try:
            self._local.connection.execute("SELECT 1")
            return self._local.connection
        except sqlite3.Error:
            # Connection is stale, create new one
            self._local.connection = self._create_connection()
            return self._local.connection

    def _create_connection(self) -> sqlite3.Connection:
        """Create new database connection with secure configuration."""
        try:
            # Use safer connection settings
            connection = sqlite3.connect(
                str(self._database_path),
                check_same_thread=True,  # More secure for thread safety
                timeout=30.0,
                isolation_level=None,  # Autocommit mode for better control
            )

            # Configure connection for security and performance
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA temp_store=MEMORY")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA secure_delete=ON")

            # Set timeout for busy operations
            connection.execute("PRAGMA busy_timeout=10000")

            logger.debug(f"Created new database connection for thread {threading.current_thread().ident}")
            return connection

        except sqlite3.Error as e:
            logger.error(f"Failed to create database connection: {e}")
            raise DatabaseError(f"Failed to create database connection: {e}")

    def execute_query(
        self,
        query: str,
        parameters: tuple = (),
        fetch: str = 'none'
    ) -> Any:
        """
        Execute SQL query with parameters safely.

        Args:
            query: SQL query with ? placeholders
            parameters: Query parameters tuple
            fetch: How to fetch results ('none', 'one', 'all')

        Returns:
            Query results based on fetch parameter

        Raises:
            DatabaseError: If query execution fails
        """
        with self.get_connection() as conn:
            try:
                cursor = conn.execute(query, parameters)

                if fetch == 'one':
                    return cursor.fetchone()
                elif fetch == 'all':
                    return cursor.fetchall()
                elif fetch == 'none':
                    conn.commit()
                    return cursor.rowcount
                else:
                    raise ValueError(f"Invalid fetch parameter: {fetch}")

            except sqlite3.Error as e:
                logger.error(f"Query execution failed: {query[:100]}... Error: {e}")
                raise DatabaseError(f"Query execution failed: {e}")

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Execute operations within a database transaction.

        Yields:
            Database connection within transaction context

        Raises:
            DatabaseError: If transaction fails
        """
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN TRANSACTION")
                yield conn
                conn.commit()
                logger.debug("Transaction committed successfully")
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction rolled back due to error: {e}")
                raise DatabaseError(f"Transaction failed: {e}")

    def close_all_connections(self) -> None:
        """Close all connections (call at shutdown)."""
        if hasattr(self._local, 'connection') and self._local.connection:
            try:
                self._local.connection.close()
                self._local.connection = None
                logger.debug("Database connections closed")
            except sqlite3.Error as e:
                logger.warning(f"Error closing database connection: {e}")

    def init_database(self) -> None:
        """Initialize database schema with security considerations."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            try:
                with self.get_connection() as conn:
                    # Create schema
                    self._create_schema(conn)

                    # Run migrations
                    self._run_migrations(conn)

                self._initialized = True
                logger.info("Database initialized successfully")

            except Exception as e:
                logger.error(f"Database initialization failed: {e}")
                raise DatabaseError(f"Database initialization failed: {e}")

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        """Create database schema."""
        schema_sql = """
        -- Ticket sequence for unique IDs
        CREATE TABLE IF NOT EXISTS ticket_sequence (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            next_value INTEGER NOT NULL DEFAULT 1
        );

        INSERT OR IGNORE INTO ticket_sequence (id, next_value) VALUES (1, 1);

        -- Main tickets table
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            subject TEXT NOT NULL CHECK (length(subject) > 0 AND length(subject) <= 255),
            description TEXT NOT NULL CHECK (length(description) > 0),
            submitter TEXT NOT NULL CHECK (length(submitter) > 0),
            submitter_email TEXT NOT NULL CHECK (submitter_email LIKE '%@%'),
            phone_number TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Open'
                CHECK (status IN ('Open', 'Assigned', 'WorkInProgress', 'Resolved', 'Completed', 'Escalated', 'HR')),
            ai_resolution TEXT DEFAULT '',
            similar_ticket_ids TEXT DEFAULT '[]',
            assigned_to TEXT DEFAULT '',
            classification_json TEXT NOT NULL DEFAULT '{}',
            routing_json TEXT NOT NULL DEFAULT '{}',
            response_json TEXT DEFAULT NULL,
            processed_at TEXT NOT NULL,
            processing_time_ms REAL NOT NULL CHECK (processing_time_ms >= 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            -- Constraints
            CONSTRAINT valid_json_classification CHECK (json_valid(classification_json)),
            CONSTRAINT valid_json_routing CHECK (json_valid(routing_json)),
            CONSTRAINT valid_json_response CHECK (response_json IS NULL OR json_valid(response_json)),
            CONSTRAINT valid_json_similar CHECK (json_valid(similar_ticket_ids))
        );

        -- Approvals table
        CREATE TABLE IF NOT EXISTS approvals (
            ticket_id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
            ai_category TEXT NOT NULL,
            ai_confidence REAL NOT NULL CHECK (ai_confidence >= 0 AND ai_confidence <= 1),
            ai_response TEXT NOT NULL,
            assigned_queue TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            reviewed_by TEXT DEFAULT '',
            reviewer_notes TEXT DEFAULT '',
            final_response TEXT DEFAULT '',

            FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
        );

        -- Approval events for audit trail
        CREATE TABLE IF NOT EXISTS approval_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL,
            event_type TEXT NOT NULL CHECK (event_type IN ('created', 'approved', 'rejected', 'modified')),
            actor TEXT NOT NULL,
            details TEXT DEFAULT '',
            created_at TEXT NOT NULL,

            FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
        );

        -- Metrics table for analytics
        CREATE TABLE IF NOT EXISTS metrics (
            ticket_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            first_response_at TEXT,
            resolved_at TEXT,
            category TEXT NOT NULL,
            queue TEXT NOT NULL,
            was_auto_resolved INTEGER NOT NULL CHECK (was_auto_resolved IN (0, 1)),

            FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
        );

        -- Email notifications
        CREATE TABLE IF NOT EXISTS email_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL,
            recipient TEXT NOT NULL CHECK (recipient LIKE '%@%'),
            subject TEXT NOT NULL,
            body_preview TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'sent', 'failed', 'retry')),
            sent_at TEXT,
            error_message TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),

            FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
        );

        -- Engineer expertise mapping
        CREATE TABLE IF NOT EXISTS engineer_expertise (
            engineer_username TEXT NOT NULL,
            category_id TEXT NOT NULL,
            expertise_level INTEGER DEFAULT 1 CHECK (expertise_level BETWEEN 1 AND 5),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),

            PRIMARY KEY (engineer_username, category_id)
        );

        -- Knowledge base drafts
        CREATE TABLE IF NOT EXISTS kb_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL,
            title TEXT NOT NULL CHECK (length(title) > 0),
            category TEXT DEFAULT '',
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'review', 'published', 'archived')),
            created_by TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            published_at TEXT,

            FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
        );

        -- Resolution feedback
        CREATE TABLE IF NOT EXISTS resolution_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL,
            submitter_email TEXT DEFAULT '',
            helpful INTEGER NOT NULL CHECK (helpful IN (0, 1)),
            comment TEXT DEFAULT '',
            created_at TEXT NOT NULL,

            FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
        );

        -- Audit log for security
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            details TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """

        conn.executescript(schema_sql)

        # Create indexes for performance
        self._create_indexes(conn)

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """Create database indexes for performance."""
        indexes_sql = """
        -- Performance indexes
        CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
        CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to ON tickets(assigned_to);
        CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);
        CREATE INDEX IF NOT EXISTS idx_tickets_updated_at ON tickets(updated_at);
        CREATE INDEX IF NOT EXISTS idx_tickets_processed_at ON tickets(processed_at);
        CREATE INDEX IF NOT EXISTS idx_tickets_submitter_email ON tickets(submitter_email);

        CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
        CREATE INDEX IF NOT EXISTS idx_approvals_created_at ON approvals(created_at);

        CREATE INDEX IF NOT EXISTS idx_email_notifications_ticket ON email_notifications(ticket_id);
        CREATE INDEX IF NOT EXISTS idx_email_notifications_status ON email_notifications(status);

        CREATE INDEX IF NOT EXISTS idx_approval_events_ticket ON approval_events(ticket_id);
        CREATE INDEX IF NOT EXISTS idx_approval_events_created_at ON approval_events(created_at);

        CREATE INDEX IF NOT EXISTS idx_metrics_category ON metrics(category);
        CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON metrics(created_at);

        CREATE INDEX IF NOT EXISTS idx_resolution_feedback_ticket ON resolution_feedback(ticket_id);

        CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);
        """

        conn.executescript(indexes_sql)

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Run database migrations safely."""
        # Check if migrations table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
        )

        if not cursor.fetchone():
            conn.execute("""
                CREATE TABLE migrations (
                    version INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

        # Add any necessary migrations here
        migrations = [
            # Example migration structure
            # (1, "Initial schema", self._migration_001),
        ]

        for version, description, migration_func in migrations:
            cursor = conn.execute("SELECT 1 FROM migrations WHERE version = ?", (version,))
            if not cursor.fetchone():
                try:
                    migration_func(conn)
                    conn.execute(
                        "INSERT INTO migrations (version, description) VALUES (?, ?)",
                        (version, description)
                    )
                    logger.info(f"Applied migration {version}: {description}")
                except Exception as e:
                    logger.error(f"Migration {version} failed: {e}")
                    raise


# Global database manager instance
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Get database connection context manager."""
    db_manager = get_db_manager()
    with db_manager.get_connection() as conn:
        yield conn


def init_database() -> None:
    """Initialize database schema."""
    db_manager = get_db_manager()
    db_manager.init_database()


def close_connection() -> None:
    """Close all database connections."""
    global _db_manager
    if _db_manager:
        _db_manager.close_all_connections()


def execute_query(query: str, parameters: tuple = (), fetch: str = 'none') -> Any:
    """Execute SQL query safely."""
    db_manager = get_db_manager()
    return db_manager.execute_query(query, parameters, fetch)


@contextmanager
def transaction() -> Generator[sqlite3.Connection, None, None]:
    """Execute operations within a database transaction."""
    db_manager = get_db_manager()
    with db_manager.transaction() as conn:
        yield conn