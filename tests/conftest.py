"""Pytest fixtures for Operation HOPE AI tests.

Uses a SEPARATE test database to prevent wiping production data.
"""
import pytest
import os
import tempfile
from unittest.mock import patch

# Force tests to use fallback provider and a temp database
os.environ.setdefault("LLM_PROVIDER", "fallback")
os.environ.setdefault("AZURE_OPENAI_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")

# Use a temporary DB file so tests never touch the production database
_test_db_dir = tempfile.mkdtemp(prefix="hope_test_")
_test_db_path = os.path.join(_test_db_dir, "test_hope.db")
os.environ["DATABASE_PATH"] = _test_db_path

from config.settings import reset_settings
from src.llm.provider import reset_provider
from src.storage.sqlite_db import clear_all_data, close_connection, init_database


@pytest.fixture(autouse=True)
def reset_state():
    """Reset singletons before each test."""
    reset_settings()
    reset_provider()
    init_database()
    clear_all_data()
    yield
    clear_all_data()
    close_connection()
    reset_settings()
    reset_provider()


@pytest.fixture(autouse=True)
def mock_ticket_embeddings():
    """Prevent pipeline tests from hitting HuggingFace for ticket embeddings."""
    with patch("src.workflow.pipeline.upsert_ticket_embedding"):
        yield
