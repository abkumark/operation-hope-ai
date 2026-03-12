"""Tests for the end-to-end pipeline (mocked LLM)."""
import pytest
from unittest.mock import patch

from src.workflow.pipeline import process_ticket, PipelineResult
from src.core.router import RoutingAction


class TestPipeline:
    @patch("src.core.classifier.get_llm_provider")
    def test_pipeline_with_fallback(self, mock_provider):
        """Pipeline works with keyword fallback when LLM fails."""
        mock_provider.side_effect = Exception("No LLM configured")

        result = process_ticket(
            subject="Password reset",
            description="I forgot my password and need to reset it",
            submitter="test@example.com",
        )

        assert isinstance(result, PipelineResult)
        assert result.ticket_id.startswith("HOPE-")
        assert result.classification.category_id == "password_reset"
        assert result.routing is not None
        assert result.processing_time_ms >= 0

    @patch("src.core.classifier.get_llm_provider")
    def test_pipeline_assigns_ticket_id(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")

        result = process_ticket("Test", "Test description", "test")
        assert result.ticket_id.startswith("HOPE-")

    @patch("src.core.classifier.get_llm_provider")
    def test_pipeline_custom_ticket_id(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")

        result = process_ticket("Test", "Test", "test", ticket_id="CUSTOM-001")
        assert result.ticket_id == "CUSTOM-001"

    @patch("src.core.classifier.get_llm_provider")
    def test_pipeline_action_summary(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")

        result = process_ticket("Password reset", "Reset my password", "test")
        assert isinstance(result.action_summary, str)
        assert len(result.action_summary) > 0
