"""Tests for keyword-based classification (no LLM required)."""
import pytest

from src.core.classifier import _classify_with_keywords, ClassificationResult
from config.routing_rules import is_hr_ticket


class TestKeywordClassification:
    """Test _classify_with_keywords for various categories."""

    def test_password_reset(self):
        result = _classify_with_keywords("Cannot reset my password", "The password reset link doesn't work.", "Test")
        assert result.category_id == "password_reset"
        assert result.confidence > 0.3

    def test_login_issue(self):
        result = _classify_with_keywords("Login not working", "I can't log in to the portal.", "Test")
        assert result.category_id in ("login_issue", "password_reset")
        assert result.confidence > 0.3

    def test_email_verification(self):
        result = _classify_with_keywords("Email verification code", "I never received the verification code.", "Test")
        assert result.category_id == "email_verification"
        assert result.confidence > 0.3

    def test_course_video_issue(self):
        result = _classify_with_keywords("Video won't play", "The course video is not playing in Chrome.", "Test")
        assert result.category_id == "course_video_issue"
        assert result.confidence > 0.3

    def test_workplan_navigation(self):
        result = _classify_with_keywords("Where is my workplan?", "I cannot find my workplan in the portal.", "Test")
        assert result.category_id == "workplan_navigation"
        assert result.confidence > 0.3

    def test_hud_certificate(self):
        result = _classify_with_keywords("HUD Certificate", "I need my HUD certification for homeownership.", "Test")
        assert result.category_id == "hud_certificate"
        assert result.confidence > 0.3

    def test_delta_sso(self):
        result = _classify_with_keywords("Delta SSO login issue", "I'm a Delta employee trying to sign in.", "Test")
        assert result.category_id == "delta_sso"
        assert result.confidence > 0.3

    def test_coach_assignment(self):
        result = _classify_with_keywords("Need new coach", "I need to change coach and be reassigned.", "Test")
        assert result.category_id == "coach_assignment"
        assert result.confidence > 0.3

    def test_duplicate_records(self):
        result = _classify_with_keywords("Duplicate records", "I have two records that need to merge.", "Test")
        assert result.category_id == "duplicate_records"
        assert result.confidence > 0.3

    def test_lms_enrollment(self):
        result = _classify_with_keywords("LMS enrollment issue", "My LMS course enrollment still showing.", "Test")
        assert result.category_id == "lms_enrollment"
        assert result.confidence > 0.3

    def test_no_information_fallback(self):
        result = _classify_with_keywords("Random query", "Something completely unrelated xyz abc.", "Test")
        assert result.category_id == "no_information"
        assert result.confidence <= 0.3

    def test_result_has_all_fields(self):
        result = _classify_with_keywords("Password reset", "Reset my password", "Test")
        assert isinstance(result, ClassificationResult)
        assert result.language in ("en", "es", "unknown")
        assert result.sentiment == "neutral"
        assert result.urgency == "medium"
        assert result.is_hr is False


class TestHRDetection:
    """Test HR ticket detection."""

    def test_hr_harassment(self):
        assert is_hr_ticket("I want to file a harassment complaint against my supervisor")

    def test_hr_payroll(self):
        assert is_hr_ticket("I have a question about my payroll deductions")

    def test_hr_benefits(self):
        assert is_hr_ticket("Need help with my employee benefits enrollment")

    def test_non_hr_password(self):
        assert not is_hr_ticket("I cannot reset my password for the portal")

    def test_non_hr_login(self):
        assert not is_hr_ticket("I can't log in to the client portal")
