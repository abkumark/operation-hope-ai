"""Pytest fixtures for Operation HOPE AI tests."""
import pytest
import os

os.environ.setdefault("LLM_PROVIDER", "fallback")
os.environ.setdefault("AZURE_OPENAI_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")

from config.settings import reset_settings
from src.llm.provider import reset_provider
from src.storage.sqlite_db import clear_all_data, init_database


@pytest.fixture(autouse=True)
def reset_state():
    """Reset singletons before each test."""
    reset_settings()
    reset_provider()
    init_database()
    clear_all_data()
    yield
    clear_all_data()
    reset_settings()
    reset_provider()
