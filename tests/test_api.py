"""Tests for FastAPI API endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.core.classifier import ClassificationResult
from src.core.router import RoutingAction, RoutingDecision
from src.workflow.pipeline import PipelineResult


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestTicketEndpoints:
    @patch("src.core.classifier.get_llm_provider")
    def test_process_ticket(self, mock_provider, client):
        mock_provider.side_effect = Exception("No LLM")
        resp = client.post("/api/v1/tickets/process", json={
            "subject": "Password reset",
            "description": "I need help resetting my password",
            "submitter": "test@example.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "ticket_id" in data
        assert "category_id" in data
        assert "confidence" in data
        assert data["processing_time_ms"] >= 0

    @patch("src.core.classifier.get_llm_provider")
    def test_list_tickets(self, mock_provider, client):
        mock_provider.side_effect = Exception("No LLM")
        client.post("/api/v1/tickets/process", json={
            "subject": "Test ticket",
            "description": "Testing list endpoint",
        })
        resp = client.get("/api/v1/tickets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @patch("src.core.classifier.get_llm_provider")
    def test_get_ticket_by_id(self, mock_provider, client):
        mock_provider.side_effect = Exception("No LLM")
        create_resp = client.post("/api/v1/tickets/process", json={
            "subject": "Test ticket",
            "description": "Testing get endpoint",
        })
        ticket_id = create_resp.json()["ticket_id"]
        resp = client.get(f"/api/v1/tickets/{ticket_id}")
        assert resp.status_code == 200
        assert resp.json()["ticket_id"] == ticket_id

    @patch("src.api.routes.process_ticket")
    def test_public_ticket_submission_requires_admin_resolution(self, mock_process_ticket, client):
        classification = ClassificationResult(
            category_id="password_reset",
            category_name="Password Reset",
            confidence=0.94,
            language="en",
            sentiment="neutral",
            urgency="medium",
            is_hr=False,
            summary="Password reset issue",
            raw_text="Reset my password",
        )
        routing = RoutingDecision(
            action=RoutingAction.AUTO_RESOLVE,
            queue="IT Support",
            reason="High confidence AI draft queued for admin resolution.",
            classification=classification,
            requires_approval=True,
        )
        mock_process_ticket.return_value = PipelineResult(
            ticket_id="HOPE-00001",
            subject="Password reset",
            description="Reset my password",
            submitter="Test User",
            classification=classification,
            routing=routing,
            response=None,
            approval=None,
            submitter_email="test@example.com",
            status="PendingApproval",
            ai_resolution="Use the password reset link to regain access.",
            processing_time_ms=12.5,
        )

        resp = client.post("/api/v1/tickets/submit", json={
            "subject": "Password reset",
            "description": "Reset my password",
            "submitter_name": "Test User",
            "submitter_email": "test@example.com",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["auto_resolved"] is False
        assert data["instant_resolved"] is False
        assert data["ai_resolution"] is None

    @patch("src.core.classifier.get_llm_provider")
    def test_resolve_ticket(self, mock_provider, client):
        mock_provider.side_effect = Exception("No LLM")
        create_resp = client.post("/api/v1/tickets/process", json={
            "subject": "Password reset",
            "description": "Need help resetting my password",
            "submitter": "test@example.com",
        })
        ticket_id = create_resp.json()["ticket_id"]

        resp = client.post(f"/api/v1/tickets/{ticket_id}/resolve", json={
            "reviewer": "Admin",
            "ai_resolution": "Password reset steps were provided and access is restored.",
        })

        assert resp.status_code == 200
        assert resp.json()["ticket_status"] == "Approved"

        detail_resp = client.get(f"/api/v1/tickets/{ticket_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["status"] == "Approved"
        assert detail["ai_resolution"] == "Password reset steps were provided and access is restored."

    @patch("src.api.routes.send_status_update")
    @patch("src.core.classifier.get_llm_provider")
    def test_resolve_ticket_sends_close_email(self, mock_provider, mock_send_status_update, client):
        mock_provider.side_effect = Exception("No LLM")
        create_resp = client.post("/api/v1/tickets/submit", json={
            "subject": "Password reset",
            "description": "Need help resetting my password",
            "submitter_name": "Test User",
            "submitter_email": "test@example.com",
        })
        ticket_id = create_resp.json()["ticket_id"]

        resp = client.post(f"/api/v1/tickets/{ticket_id}/resolve", json={
            "reviewer": "Admin",
            "ai_resolution": "Password reset steps were provided and the ticket is now closed.",
        })

        assert resp.status_code == 200
        mock_send_status_update.assert_called_once_with(
            ticket_id=ticket_id,
            recipient_email="test@example.com",
            recipient_name="Test User",
            new_status="closed",
            details="Password reset steps were provided and the ticket is now closed.",
        )

    def test_get_nonexistent_ticket(self, client):
        resp = client.get("/api/v1/tickets/nonexistent-id")
        assert resp.status_code == 404


class TestKBEndpoints:
    def test_kb_status(self, client):
        resp = client.get("/api/v1/kb/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "article_count" in data
        assert "chunk_count" in data

    def test_kb_articles(self, client):
        resp = client.get("/api/v1/kb/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "articles" in data

    def test_kb_search(self, client):
        resp = client.get("/api/v1/kb/search", params={"query": "password reset"})
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "results" in data


class TestApprovalEndpoints:
    @patch("src.core.classifier.get_llm_provider")
    def test_list_approvals(self, mock_provider, client):
        mock_provider.side_effect = Exception("No LLM")
        client.post("/api/v1/tickets/process", json={
            "subject": "Password reset",
            "description": "Need password help",
        })
        resp = client.get("/api/v1/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "approvals" in data

    @patch("src.core.classifier.get_llm_provider")
    def test_approve_ticket(self, mock_provider, client):
        mock_provider.side_effect = Exception("No LLM")
        create_resp = client.post("/api/v1/tickets/process", json={
            "subject": "Password reset",
            "description": "Need password help",
        })
        ticket_id = create_resp.json()["ticket_id"]
        resp = client.post(f"/api/v1/approvals/{ticket_id}/approve", json={
            "reviewer": "Admin",
            "final_response": "Your password has been reset.",
            "send": True,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_approve_nonexistent_ticket(self, client):
        resp = client.post("/api/v1/approvals/fake-id/approve", json={
            "reviewer": "Admin",
        })
        assert resp.status_code == 404

    def test_reject_nonexistent_ticket(self, client):
        resp = client.post("/api/v1/approvals/fake-id/reject", json={
            "reviewer": "Admin",
            "notes": "Not applicable",
        })
        assert resp.status_code == 404


class TestAnalyticsEndpoint:
    def test_analytics_summary(self, client):
        resp = client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200


class TestIntegrationEndpoint:
    def test_integration_status(self, client):
        resp = client.get("/api/v1/integration/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "use_mock_dynamics" in data
