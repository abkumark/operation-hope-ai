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


@pytest.fixture
def admin_headers(client):
    """Login as admin and return auth headers."""
    resp = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def engineer_headers(client):
    """Login as engineer and return auth headers."""
    resp = client.post("/api/v1/auth/login", json={
        "username": "torri",
        "password": "Welcome123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoint:
    def test_health_check(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "llm_provider" in data


class TestAuthEndpoint:
    def test_login_success(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "admin"

    def test_login_invalid_password(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_protected_endpoint_without_token(self, client):
        resp = client.get("/api/v1/tickets")
        assert resp.status_code == 401


class TestTicketEndpoints:
    @patch("src.core.classifier.get_llm_provider")
    def test_process_ticket(self, mock_provider, client, admin_headers):
        mock_provider.side_effect = Exception("No LLM")
        resp = client.post("/api/v1/tickets/process", json={
            "subject": "Password reset",
            "description": "I need help resetting my password",
            "submitter": "test@example.com",
        }, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "ticket_id" in data
        assert "category_id" in data
        assert "confidence" in data
        assert data["processing_time_ms"] >= 0

    @patch("src.core.classifier.get_llm_provider")
    def test_list_tickets(self, mock_provider, client, admin_headers):
        mock_provider.side_effect = Exception("No LLM")
        client.post("/api/v1/tickets/process", json={
            "subject": "Test ticket",
            "description": "Testing list endpoint",
        }, headers=admin_headers)
        resp = client.get("/api/v1/tickets", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert "offset" in data
        assert "limit" in data

    @patch("src.core.classifier.get_llm_provider")
    def test_get_ticket_by_id(self, mock_provider, client, admin_headers):
        mock_provider.side_effect = Exception("No LLM")
        create_resp = client.post("/api/v1/tickets/process", json={
            "subject": "Test ticket",
            "description": "Testing get endpoint",
        }, headers=admin_headers)
        ticket_id = create_resp.json()["ticket_id"]
        resp = client.get(f"/api/v1/tickets/{ticket_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["ticket_id"] == ticket_id

    @patch("src.api.routers.tickets_router.process_ticket")
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
            status="WorkInProgress",
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
    def test_resolve_ticket(self, mock_provider, client, admin_headers):
        mock_provider.side_effect = Exception("No LLM")
        create_resp = client.post("/api/v1/tickets/process", json={
            "subject": "Password reset",
            "description": "Need help resetting my password",
            "submitter": "test@example.com",
        }, headers=admin_headers)
        ticket_id = create_resp.json()["ticket_id"]

        resp = client.post(f"/api/v1/tickets/{ticket_id}/resolve", json={
            "reviewer": "Admin",
            "ai_resolution": "Password reset steps were provided and access is restored.",
        }, headers=admin_headers)

        assert resp.status_code == 200
        assert resp.json()["ticket_status"] == "Completed"

        detail_resp = client.get(f"/api/v1/tickets/{ticket_id}", headers=admin_headers)
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["status"] == "Completed"
        assert detail["ai_resolution"] == "Password reset steps were provided and access is restored."

    @patch("src.api.routers.tickets_router.send_case_closed_email")
    @patch("src.workflow.pipeline.upsert_ticket_embedding")
    @patch("src.core.classifier.get_llm_provider")
    def test_resolve_ticket_sends_close_email(self, mock_provider, mock_embed, mock_send_closed, client, admin_headers):
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
        }, headers=admin_headers)

        assert resp.status_code == 200
        mock_send_closed.assert_called_once_with(
            ticket_id=ticket_id,
            recipient_email="test@example.com",
            recipient_name="Test User",
            resolution_text="Password reset steps were provided and the ticket is now closed.",
        )

    def test_get_nonexistent_ticket(self, client, admin_headers):
        resp = client.get("/api/v1/tickets/nonexistent-id", headers=admin_headers)
        assert resp.status_code == 404

    @patch("src.llm.provider.get_llm_provider")
    @patch("src.core.classifier.get_llm_provider")
    def test_translate_ticket_text(self, mock_classifier_provider, mock_translate_provider, client, admin_headers):
        mock_classifier_provider.side_effect = Exception("No LLM")
        mock_provider = mock_translate_provider.return_value
        mock_provider.chat.return_value = "I need to reset my password."

        create_resp = client.post("/api/v1/tickets/process", json={
            "subject": "Necesito ayuda",
            "description": "No puedo restablecer mi contraseña.",
            "submitter": "test@example.com",
        }, headers=admin_headers)
        ticket_id = create_resp.json()["ticket_id"]

        resp = client.post(f"/api/v1/tickets/{ticket_id}/translate", json={
            "text": "No puedo restablecer mi contraseña.",
            "source_language": "es",
            "target_language": "en",
        }, headers=admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["translated_text"] == "I need to reset my password."
        assert data["source_language"] == "es"
        assert data["target_language"] == "en"

    @patch("src.core.classifier.get_llm_provider")
    def test_ticket_detail_includes_translation_metadata(self, mock_provider, client, admin_headers):
        mock_provider.side_effect = Exception("No LLM")

        create_resp = client.post("/api/v1/tickets/process", json={
            "subject": "Necesito ayuda",
            "description": "No puedo restablecer mi contraseña.",
            "submitter": "test@example.com",
        }, headers=admin_headers)
        ticket_id = create_resp.json()["ticket_id"]

        detail_resp = client.get(f"/api/v1/tickets/{ticket_id}", headers=admin_headers)

        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["translation"]["ticket"]["can_translate_to_english"] is True
        assert detail["translation"]["ticket"]["detected_source_language"] == "es"
        assert detail["translation"]["resolution"]["target_language"] == "en"

    def test_translate_ticket_text_missing_ticket_returns_404(self, client, admin_headers):
        resp = client.post("/api/v1/tickets/HOPE-99999/translate", json={
            "text": "No puedo restablecer mi contraseña.",
            "source_language": "es",
            "target_language": "en",
        }, headers=admin_headers)

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

    def test_kb_search(self, client, admin_headers):
        resp = client.get("/api/v1/kb/search", params={"query": "password reset"}, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "results" in data


class TestApprovalEndpoints:
    @patch("src.core.classifier.get_llm_provider")
    def test_list_approvals(self, mock_provider, client, admin_headers):
        mock_provider.side_effect = Exception("No LLM")
        client.post("/api/v1/tickets/process", json={
            "subject": "Password reset",
            "description": "Need password help",
        }, headers=admin_headers)
        resp = client.get("/api/v1/approvals", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "approvals" in data

    @patch("src.core.classifier.get_llm_provider")
    def test_approve_ticket(self, mock_provider, client, admin_headers):
        mock_provider.side_effect = Exception("No LLM")
        create_resp = client.post("/api/v1/tickets/process", json={
            "subject": "Password reset",
            "description": "Need password help",
        }, headers=admin_headers)
        ticket_id = create_resp.json()["ticket_id"]
        resp = client.post(f"/api/v1/approvals/{ticket_id}/approve", json={
            "reviewer": "Admin",
            "final_response": "Your password has been reset.",
            "send": True,
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_approve_nonexistent_ticket(self, client, admin_headers):
        resp = client.post("/api/v1/approvals/fake-id/approve", json={
            "reviewer": "Admin",
        }, headers=admin_headers)
        assert resp.status_code == 404

    def test_reject_nonexistent_ticket(self, client, admin_headers):
        resp = client.post("/api/v1/approvals/fake-id/reject", json={
            "reviewer": "Admin",
            "notes": "Not applicable",
        }, headers=admin_headers)
        assert resp.status_code == 404


class TestAnalyticsEndpoint:
    def test_analytics_summary(self, client, admin_headers):
        resp = client.get("/api/v1/analytics/summary", headers=admin_headers)
        assert resp.status_code == 200

    def test_analytics_requires_auth(self, client):
        resp = client.get("/api/v1/analytics/summary")
        assert resp.status_code == 401


class TestIntegrationEndpoint:
    def test_integration_status(self, client, admin_headers):
        resp = client.get("/api/v1/integration/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "use_mock_dynamics" in data
