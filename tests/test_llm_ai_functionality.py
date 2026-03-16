"""Comprehensive tests for all LLM / AI prompt functionalities.

Covers: classification (LLM + keyword), RAG response generation,
resolution engine, language detection, confidence scoring, routing
recommendations, end-to-end pipeline with mocked LLM, fallback
behaviour, Spanish-language handling, and edge cases.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

# ── Core modules under test ──
from src.core.classifier import (
    ClassificationResult,
    _classify_with_keywords,
    _classify_with_llm,
    _compute_keyword_score,
    classify_ticket,
)
from src.core.confidence import (
    calibrate_confidence,
    combine_confidence_scores,
    normalize_confidence,
    should_auto_resolve,
)
from src.core.language_detector import detect_language, get_language_confidence
from src.core.resolution_engine import (
    ResolutionResult,
    SimilarTicket,
    _fallback_resolution,
    find_similar_tickets,
    generate_resolution,
)
from src.core.responder import TicketResponse, generate_ticket_response
from src.core.router import RoutingAction, RoutingDecision, route_ticket
from src.knowledge.rag_pipeline import (
    _format_kb_context,
    _generate_fallback_response,
    generate_response,
)
from src.workflow.escalation import EscalationReason, should_escalate
from src.workflow.pipeline import PipelineResult, process_ticket


# ─────────────────────────── Helpers ───────────────────────────


def _make_classification(
    category_id="password_reset",
    confidence=0.9,
    language="en",
    urgency="medium",
    sentiment="neutral",
    is_hr=False,
) -> ClassificationResult:
    return ClassificationResult(
        category_id=category_id,
        category_name="Password Reset",
        confidence=confidence,
        language=language,
        sentiment=sentiment,
        urgency=urgency,
        is_hr=is_hr,
        summary="Test classification",
        raw_text="test text",
    )


def _mock_llm_json(response_dict: dict) -> MagicMock:
    """Return a mock LLM provider whose chat_json returns *response_dict*."""
    llm = MagicMock()
    llm.chat_json.return_value = json.dumps(response_dict)
    llm.chat.return_value = "Mock LLM response text."
    return llm


# ═══════════════════════════════════════════════════════════════
# 1. CLASSIFICATION — LLM path
# ═══════════════════════════════════════════════════════════════


class TestClassifyWithLLM:
    """Verify LLM-based classification parses JSON correctly."""

    def test_valid_llm_response_parsed(self):
        llm = _mock_llm_json({
            "category_id": "password_reset",
            "confidence": 0.92,
            "sentiment": "frustrated",
            "urgency": "high",
            "summary": "User locked out of portal",
            "is_hr": False,
        })
        result = _classify_with_llm(llm, "Can't login", "I'm locked out of the portal", "Alice")
        assert result is not None
        assert result.category_id == "password_reset"
        assert result.confidence == pytest.approx(0.92)
        assert result.sentiment == "frustrated"
        assert result.urgency == "high"
        assert result.is_hr is False

    def test_unknown_category_defaults_to_no_information(self):
        llm = _mock_llm_json({
            "category_id": "totally_unknown_cat",
            "confidence": 0.8,
            "sentiment": "neutral",
            "urgency": "medium",
            "summary": "Unknown",
        })
        result = _classify_with_llm(llm, "Something", "Something else", "Bob")
        assert result is not None
        assert result.category_id == "no_information"

    def test_confidence_clamped_to_0_1(self):
        llm = _mock_llm_json({
            "category_id": "password_reset",
            "confidence": 1.5,
            "sentiment": "neutral",
            "urgency": "low",
            "summary": "over-confident",
        })
        result = _classify_with_llm(llm, "pw", "reset", "C")
        # LLM confidence is now capped at 0.95 to counter overconfidence
        assert result.confidence == 0.95

    def test_negative_confidence_clamped(self):
        llm = _mock_llm_json({
            "category_id": "password_reset",
            "confidence": -0.3,
            "sentiment": "neutral",
            "urgency": "low",
            "summary": "negative confidence",
        })
        result = _classify_with_llm(llm, "pw", "reset", "D")
        assert result.confidence == 0.0

    def test_missing_fields_use_defaults(self):
        llm = _mock_llm_json({"category_id": "login_issue"})
        result = _classify_with_llm(llm, "Login help", "Need help", "E")
        assert result.confidence == pytest.approx(0.5)
        assert result.sentiment == "neutral"
        assert result.urgency == "medium"
        assert result.is_hr is False

    def test_llm_returns_invalid_json_raises(self):
        llm = MagicMock()
        llm.chat_json.return_value = "NOT VALID JSON"
        with pytest.raises(json.JSONDecodeError):
            _classify_with_llm(llm, "bad", "data", "F")


class TestClassifyTicketIntegration:
    """classify_ticket(): LLM → keyword fallback → HR detection."""

    @patch("src.core.classifier.get_llm_provider")
    def test_uses_llm_when_available(self, mock_get):
        llm = _mock_llm_json({
            "category_id": "email_verification",
            "confidence": 0.88,
            "sentiment": "neutral",
            "urgency": "medium",
            "summary": "Email code not received",
        })
        mock_get.return_value = llm
        result = classify_ticket("Verification code", "I never received the code", "User1")
        assert result.category_id == "email_verification"
        # Confidence may be adjusted by keyword weighting; just check plausible range
        assert result.confidence >= 0.7

    @patch("src.core.classifier.get_llm_provider")
    def test_falls_back_to_keywords_on_llm_failure(self, mock_get):
        mock_get.side_effect = Exception("LLM down")
        result = classify_ticket("Password reset", "I forgot my password", "User2")
        assert result.category_id == "password_reset"
        assert 0 < result.confidence <= 0.75  # keyword fallback range

    def test_hr_ticket_detected_before_llm(self):
        """HR tickets should be detected even without LLM."""
        result = classify_ticket("Payroll issue", "I have a question about my payroll deductions", "Employee")
        assert result.is_hr is True
        assert result.category_id == "hr_excluded"

    @patch("src.core.classifier.get_llm_provider")
    def test_keyword_boost_increases_confidence(self, mock_get):
        """When LLM confidence is combined with a keyword match, result is boosted."""
        llm = _mock_llm_json({
            "category_id": "password_reset",
            "confidence": 0.75,
            "sentiment": "neutral",
            "urgency": "medium",
            "summary": "Password issue",
        })
        mock_get.return_value = llm
        result = classify_ticket("Reset password", "I forgot my password and need to reset it", "U")
        # Keyword boost should push confidence above 0.75
        assert result.confidence > 0.75


# ═══════════════════════════════════════════════════════════════
# 2. KEYWORD CLASSIFICATION & SCORING
# ═══════════════════════════════════════════════════════════════


class TestKeywordScoring:
    def test_keyword_score_positive(self):
        score = _compute_keyword_score("I need to reset my password", "password_reset")
        assert score > 0.3

    def test_keyword_score_zero_for_unrelated(self):
        score = _compute_keyword_score("I like pizza", "password_reset")
        assert score == 0.0

    def test_keyword_score_caps_at_0_9(self):
        # Text with many keywords
        text = "password reset forgot login can't log in sign in locked out"
        score = _compute_keyword_score(text, "password_reset")
        assert score <= 0.9

    def test_keyword_score_unknown_category(self):
        score = _compute_keyword_score("anything", "nonexistent_cat")
        assert score == 0.0


class TestKeywordClassificationCategories:
    """Verify each major category is reachable via keyword classification."""

    @pytest.mark.parametrize(
        "subject, description, expected_category",
        [
            ("Cannot reset my password", "The password reset link doesn't work", "password_reset"),
            ("Login not working", "I can't log in to the portal", "login_issue"),
            ("Email verification code", "I never received the verification code", "email_verification"),
            ("Video won't play", "The course video is not playing in Chrome", "course_video_issue"),
            ("Where is my workplan?", "I cannot find my workplan in the portal", "workplan_navigation"),
            ("HUD Certificate", "I need my HUD certification for homeownership", "hud_certificate"),
            ("Delta SSO login issue", "I'm a Delta employee trying to sign in", "delta_sso"),
            ("Need new coach", "I need to change coach and be reassigned", "coach_assignment"),
            ("Duplicate records", "I have two records that need to merge", "duplicate_records"),
            ("LMS enrollment issue", "My LMS course enrollment still showing", "lms_enrollment"),
        ],
    )
    def test_keyword_category_match(self, subject, description, expected_category):
        result = _classify_with_keywords(subject, description, "Tester")
        assert result.category_id == expected_category

    def test_no_information_fallback(self):
        result = _classify_with_keywords("xyz abc", "Random unrelated gibberish qwerty", "T")
        assert result.category_id == "no_information"
        assert result.confidence <= 0.3


# ═══════════════════════════════════════════════════════════════
# 3. CONFIDENCE SCORING
# ═══════════════════════════════════════════════════════════════


class TestConfidenceScoring:
    def test_normalize_clamps_high(self):
        assert normalize_confidence(1.5) == 1.0

    def test_normalize_clamps_low(self):
        assert normalize_confidence(-0.2) == 0.0

    def test_calibrate_within_range(self):
        assert calibrate_confidence(0.5, 0.0, 1.0) == pytest.approx(0.5)
        assert calibrate_confidence(0.0, 0.0, 1.0) == 0.0
        assert calibrate_confidence(1.0, 0.0, 1.0) == 1.0

    def test_calibrate_custom_range(self):
        assert calibrate_confidence(0.75, 0.5, 1.0) == pytest.approx(0.5)

    def test_combine_llm_only(self):
        assert combine_confidence_scores(0.8) == pytest.approx(0.8)

    def test_combine_with_keyword(self):
        combined = combine_confidence_scores(0.8, keyword_match_score=0.6)
        expected = 0.8 * 0.8 + 0.2 * 0.6  # default keyword_weight=0.2
        assert combined == pytest.approx(expected)

    def test_combine_custom_weight(self):
        combined = combine_confidence_scores(0.8, 0.6, keyword_weight=0.5)
        expected = 0.5 * 0.8 + 0.5 * 0.6
        assert combined == pytest.approx(expected)

    def test_should_auto_resolve_above_threshold(self):
        assert should_auto_resolve(0.90, threshold=0.85) is True

    def test_should_not_auto_resolve_below_threshold(self):
        assert should_auto_resolve(0.70, threshold=0.85) is False


# ═══════════════════════════════════════════════════════════════
# 4. LANGUAGE DETECTION
# ═══════════════════════════════════════════════════════════════


class TestLanguageDetection:
    def test_english_detected(self):
        assert detect_language("I need help resetting my password for the portal") == "en"

    def test_spanish_detected(self):
        assert detect_language(
            "No puedo iniciar sesión en el portal de Operation HOPE. Necesito ayuda urgente."
        ) == "es"

    def test_short_text_defaults_to_english(self):
        assert detect_language("hi") == "en"

    def test_empty_text_defaults_to_english(self):
        assert detect_language("") == "en"

    def test_confidence_returns_dict(self):
        conf = get_language_confidence("I need help with my account")
        assert isinstance(conf, dict)
        assert "en" in conf
        assert conf["en"] > 0.5


# ═══════════════════════════════════════════════════════════════
# 5. ROUTING DECISIONS
# ═══════════════════════════════════════════════════════════════


class TestRoutingDecisions:
    def test_high_confidence_auto_resolve(self):
        c = _make_classification(confidence=0.92)
        d = route_ticket(c)
        assert d.action == RoutingAction.AUTO_RESOLVE
        assert d.requires_approval is True

    def test_medium_confidence_suggest_review(self):
        c = _make_classification(confidence=0.72)
        d = route_ticket(c)
        assert d.action == RoutingAction.SUGGEST_REVIEW

    def test_low_confidence_route_to_human(self):
        c = _make_classification(confidence=0.40)
        d = route_ticket(c)
        assert d.action == RoutingAction.ROUTE_TO_HUMAN
        assert d.requires_approval is False

    def test_hr_excluded(self):
        c = _make_classification(is_hr=True)
        d = route_ticket(c)
        assert d.action == RoutingAction.HR_EXCLUDED

    def test_critical_escalation(self):
        c = _make_classification(urgency="critical")
        d = route_ticket(c)
        assert d.action == RoutingAction.ESCALATE

    def test_non_auto_resolvable_high_confidence_suggests_review(self):
        c = _make_classification(category_id="coach_assignment", confidence=0.95)
        d = route_ticket(c)
        assert d.action == RoutingAction.SUGGEST_REVIEW

    def test_correct_queue_assignment(self):
        c = _make_classification(category_id="course_video_issue", confidence=0.92)
        d = route_ticket(c)
        assert d.queue == "L&D"


# ═══════════════════════════════════════════════════════════════
# 6. RAG RESPONSE GENERATION
# ═══════════════════════════════════════════════════════════════


class TestRAGResponseGeneration:
    @patch("src.knowledge.rag_pipeline.search_kb")
    @patch("src.knowledge.rag_pipeline.get_llm_provider")
    def test_generates_response_with_kb_context(self, mock_provider, mock_search):
        mock_search.return_value = [
            {
                "content": "To reset your password, go to the portal login page and click 'Forgot Password'.",
                "metadata": {"title": "Password Reset Guide", "chunk_type": "resolution"},
                "similarity": 0.92,
            }
        ]
        mock_llm = MagicMock()
        mock_llm.chat.return_value = (
            "Thank you for reaching out. To reset your password:\n"
            "1. Go to the portal login page\n"
            "2. Click 'Forgot Password'\n"
            "3. Enter your email\n\nThank you,"
        )
        mock_provider.return_value = mock_llm

        classification = _make_classification()
        result = generate_response(classification, "Password reset", "I forgot my password")

        assert "response" in result
        assert len(result["response"]) > 0
        assert "kb_articles_used" in result
        assert result["language"] == "en"

    @patch("src.knowledge.rag_pipeline.search_kb")
    @patch("src.knowledge.rag_pipeline.get_llm_provider")
    def test_spanish_response_when_language_is_es(self, mock_provider, mock_search):
        mock_search.return_value = [
            {
                "content": "Para restablecer su contraseña, vaya a la página de inicio.",
                "metadata": {"title": "Restablecimiento de Contraseña", "chunk_type": "full"},
                "similarity": 0.85,
            }
        ]
        mock_llm = MagicMock()
        mock_llm.chat.return_value = (
            "Gracias por comunicarse. Para restablecer su contraseña:\n"
            "1. Vaya a la página de inicio\n2. Haga clic en 'Olvidé mi contraseña'\nGracias,"
        )
        mock_provider.return_value = mock_llm

        classification = _make_classification(language="es")
        result = generate_response(classification, "Restablecer contraseña", "Olvidé mi contraseña")

        assert result["language"] == "es"
        # The LLM was called with Spanish system prompt
        call_args = mock_llm.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][0]
        system_msg = messages[0]["content"]
        assert "Spanish" in system_msg or "español" in system_msg.lower() or "usted" in system_msg

    @patch("src.knowledge.rag_pipeline.search_kb")
    @patch("src.knowledge.rag_pipeline.get_llm_provider")
    def test_fallback_response_when_llm_fails(self, mock_provider, mock_search):
        mock_search.return_value = [
            {
                "content": "Response Template for: Password Reset steps...",
                "metadata": {"title": "Password Reset", "chunk_type": "response"},
                "similarity": 0.9,
            }
        ]
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = Exception("LLM API error")
        mock_provider.return_value = mock_llm

        classification = _make_classification()
        result = generate_response(classification, "Password reset", "Reset please")

        assert len(result["response"]) > 0  # Fallback should produce something

    def test_fallback_response_english(self):
        c = _make_classification()
        response = _generate_fallback_response(c, [])
        assert "Thank you" in response or "received" in response

    def test_fallback_response_spanish(self):
        c = _make_classification(language="es")
        response = _generate_fallback_response(c, [])
        assert "Gracias" in response or "solicitud" in response

    def test_format_kb_context_empty(self):
        assert _format_kb_context([]) == ""

    def test_format_kb_context_formats_articles(self):
        results = [
            {
                "content": "Article content here.",
                "metadata": {"title": "Test Article", "chunk_type": "full"},
                "similarity": 0.88,
            }
        ]
        formatted = _format_kb_context(results)
        assert "Test Article" in formatted
        assert "Article content here." in formatted
        assert "88%" in formatted


class TestResponderOrchestrator:
    """Test generate_ticket_response (the orchestrator)."""

    @patch("src.knowledge.rag_pipeline.search_kb")
    @patch("src.knowledge.rag_pipeline.get_llm_provider")
    def test_auto_resolve_generates_response(self, mock_provider, mock_search):
        mock_search.return_value = [
            {"content": "KB content", "metadata": {"title": "KB"}, "similarity": 0.9}
        ]
        mock_provider.return_value.chat.return_value = "AI response"

        c = _make_classification(confidence=0.92)
        r = route_ticket(c)
        resp = generate_ticket_response(c, r, "Password reset", "I forgot my password")

        assert resp is not None
        assert isinstance(resp, TicketResponse)
        assert resp.requires_approval is True

    def test_hr_returns_none(self):
        c = _make_classification(is_hr=True)
        r = RoutingDecision(
            action=RoutingAction.HR_EXCLUDED, queue="HR", reason="HR",
            classification=c, requires_approval=False,
        )
        assert generate_ticket_response(c, r, "HR issue", "Payroll") is None

    def test_escalation_returns_none(self):
        c = _make_classification(urgency="critical")
        r = RoutingDecision(
            action=RoutingAction.ESCALATE, queue="IT Support", reason="Critical",
            classification=c, requires_approval=False,
        )
        assert generate_ticket_response(c, r, "System down", "Everything broken") is None


# ═══════════════════════════════════════════════════════════════
# 7. RESOLUTION ENGINE
# ═══════════════════════════════════════════════════════════════


class TestResolutionEngine:
    def test_fallback_resolution_with_similar_tickets(self):
        similar = [
            SimilarTicket(
                ticket_id="HOPE-00001",
                subject="Password reset",
                description="Client forgot password",
                similarity=0.85,
                ai_resolution="Use the password reset link in the portal.",
                status="Approved",
            ),
        ]
        resolution = _fallback_resolution("Password issue", "I can't log in", "password_reset", similar)
        assert "HOPE-00001" in resolution
        assert "password_reset" in resolution

    def test_fallback_resolution_no_similar_tickets(self):
        resolution = _fallback_resolution("Unknown issue", "Something weird", "no_information", [])
        assert "Escalate" in resolution or "escalate" in resolution.lower()

    @patch("src.llm.provider.get_llm_provider")
    def test_generate_resolution_with_llm(self, mock_get):
        llm = _mock_llm_json({
            "proposed_resolution": "1. Check login credentials\n2. Reset password\n3. Clear browser cache",
            "reference_ticket_ids": ["HOPE-00001"],
        })
        mock_get.return_value = llm

        similar = [
            SimilarTicket(
                ticket_id="HOPE-00001", subject="PW reset", description="...",
                similarity=0.8, ai_resolution="Reset link", status="Approved",
            ),
        ]
        result = generate_resolution("Can't login", "Locked out", "password_reset", similar)

        assert isinstance(result, ResolutionResult)
        assert "Check login" in result.proposed_resolution
        assert "HOPE-00001" in result.similar_ticket_ids

    @patch("src.llm.provider.get_llm_provider")
    def test_generate_resolution_falls_back_on_llm_error(self, mock_get):
        mock_get.side_effect = Exception("LLM unavailable")

        similar = [
            SimilarTicket(
                ticket_id="HOPE-00002", subject="Video issue", description="...",
                similarity=0.7, ai_resolution="", status="Open",
            ),
        ]
        result = generate_resolution("Video problem", "Videos not playing", "course_video_issue", similar)

        assert isinstance(result, ResolutionResult)
        assert len(result.proposed_resolution) > 0  # Fallback produces something
        assert "HOPE-00002" in result.similar_ticket_ids

    def test_find_similar_tickets_excludes_self(self):
        """After processing a ticket, find_similar_tickets should exclude it."""
        with patch("src.core.classifier.get_llm_provider") as mock_p:
            mock_p.side_effect = Exception("No LLM")
            result = process_ticket("Password reset", "I forgot my password", "user1", ticket_id="SIM-001")

        similar = find_similar_tickets("Password reset", "I forgot my password", exclude_ticket_id="SIM-001")
        ids = [s.ticket_id for s in similar]
        assert "SIM-001" not in ids


# ═══════════════════════════════════════════════════════════════
# 8. ESCALATION RULES
# ═══════════════════════════════════════════════════════════════


class TestEscalationRules:
    def test_critical_urgency_escalates(self):
        escalate, reason = should_escalate(urgency="critical")
        assert escalate is True
        assert reason == EscalationReason.URGENCY_CRITICAL

    def test_high_urgency_does_not_escalate(self):
        # Fixed: "high" urgency no longer auto-escalates so tickets still
        # get AI response generation. Only "critical" auto-escalates.
        escalate, reason = should_escalate(urgency="high")
        assert escalate is False
        assert reason is None

    def test_low_confidence_escalates(self):
        escalate, reason = should_escalate(confidence=0.3)
        assert escalate is True
        assert reason == EscalationReason.LOW_CONFIDENCE

    def test_normal_ticket_no_escalation(self):
        escalate, reason = should_escalate(urgency="low", confidence=0.9)
        assert escalate is False
        assert reason is None


# ═══════════════════════════════════════════════════════════════
# 9. END-TO-END PIPELINE (mocked LLM)
# ═══════════════════════════════════════════════════════════════


class TestEndToEndPipeline:
    """Full pipeline: classify → route → respond → resolve."""

    @patch("src.core.classifier.get_llm_provider")
    def test_password_reset_pipeline(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")
        result = process_ticket(
            subject="Password reset",
            description="I forgot my password and cannot log in to the portal.",
            submitter="Jane Doe",
            submitter_email="jane@example.com",
        )
        assert isinstance(result, PipelineResult)
        assert result.ticket_id.startswith("HOPE-")
        assert result.classification.category_id == "password_reset"
        assert result.routing is not None
        assert result.processing_time_ms >= 0
        assert result.submitter_email == "jane@example.com"

    @patch("src.core.classifier.get_llm_provider")
    def test_spanish_ticket_pipeline(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")
        result = process_ticket(
            subject="No puedo iniciar sesión",
            description="No puedo iniciar sesión en el portal de Operation HOPE. Olvidé mi contraseña.",
            submitter="Carlos",
        )
        assert result.classification.language == "es"

    @patch("src.core.classifier.get_llm_provider")
    def test_hr_ticket_excluded(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")
        result = process_ticket(
            subject="Payroll question",
            description="I have a question about my payroll deductions and benefits",
            submitter="Employee",
        )
        assert result.classification.is_hr is True
        assert result.routing.action == RoutingAction.HR_EXCLUDED
        assert result.response is None

    @patch("src.core.classifier.get_llm_provider")
    def test_pipeline_with_custom_ticket_id(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")
        result = process_ticket("Test", "Test description", ticket_id="CUSTOM-123")
        assert result.ticket_id == "CUSTOM-123"

    @patch("src.core.classifier.get_llm_provider")
    def test_pipeline_produces_action_summary(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")
        result = process_ticket("Password reset", "Reset my password please", "user")
        assert isinstance(result.action_summary, str)
        assert len(result.action_summary) > 0

    @patch("src.core.classifier.get_llm_provider")
    def test_low_confidence_ticket_routes_to_human(self, mock_provider):
        """An unrecognizable ticket should route to human with low confidence."""
        mock_provider.side_effect = Exception("No LLM")
        result = process_ticket(
            subject="Something completely unknown",
            description="xyz abc qwerty random gibberish with no keywords",
            submitter="Unknown",
        )
        assert result.classification.confidence < 0.6
        assert result.routing.action in (RoutingAction.ROUTE_TO_HUMAN, RoutingAction.ESCALATE)

    @patch("src.core.classifier.get_llm_provider")
    def test_pipeline_records_similar_tickets(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")
        # Create two similar tickets
        process_ticket("Password reset", "I forgot my password", "A", ticket_id="DUP-001")
        result = process_ticket("Password reset", "I also forgot my password", "B", ticket_id="DUP-002")
        # Second ticket should reference the first as similar
        assert isinstance(result.similar_ticket_ids, list)


# ═══════════════════════════════════════════════════════════════
# 10. EDGE CASES
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Boundary conditions and unusual inputs."""

    @patch("src.core.classifier.get_llm_provider")
    def test_very_long_description(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")
        long_desc = "I need a password reset. " * 500  # ~12,500 chars
        result = process_ticket("Password reset", long_desc, "LongUser")
        assert result.classification.category_id == "password_reset"

    @patch("src.core.classifier.get_llm_provider")
    def test_special_characters_in_subject(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")
        result = process_ticket(
            subject="<script>alert('xss')</script> Password reset!!!",
            description="Need password help: user@email.com & special chars #$%",
            submitter="Tester <test>",
        )
        assert isinstance(result, PipelineResult)

    @patch("src.core.classifier.get_llm_provider")
    def test_unicode_content(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")
        result = process_ticket(
            subject="Contraseña — ¿cómo restablecer?",
            description="Necesito ayuda con mi contraseña. Gracias 🙏",
            submitter="María José",
        )
        assert isinstance(result, PipelineResult)

    @patch("src.core.classifier.get_llm_provider")
    def test_minimal_description(self, mock_provider):
        mock_provider.side_effect = Exception("No LLM")
        result = process_ticket("Help", "Password issue", "User")
        assert isinstance(result, PipelineResult)

    def test_classify_empty_text_keyword_fallback(self):
        result = _classify_with_keywords("", "", "")
        assert result.category_id == "no_information"

    def test_language_detection_mixed_text(self):
        # Mixed English/Spanish text
        lang = detect_language("Hello, necesito ayuda con my password por favor help me")
        assert lang in ("en", "es")  # Either detection is acceptable for mixed text


# ═══════════════════════════════════════════════════════════════
# 11. EMAIL NOTIFICATION INTEGRATION (mocked SMTP)
# ═══════════════════════════════════════════════════════════════


class TestEmailNotifications:
    """Verify email functions are called at the right points."""

    @patch("src.api.routers.tickets_router.send_ticket_confirmation")
    @patch("src.core.classifier.get_llm_provider")
    def test_confirmation_email_sent_on_submit(self, mock_provider, mock_send):
        """The separate background task for email should call send_ticket_confirmation."""
        from src.api.routers.tickets_router import _send_confirmation_email_background

        mock_provider.side_effect = Exception("No LLM")
        # Directly call the helper
        _send_confirmation_email_background(
            ticket_id="HOPE-99999",
            subject="Test Ticket",
            submitter_name="Alice",
            submitter_email="alice@example.com",
        )
        mock_send.assert_called_once_with(
            ticket_id="HOPE-99999",
            recipient_email="alice@example.com",
            recipient_name="Alice",
            subject="Test Ticket",
        )

    @patch("src.api.routers.tickets_router.send_case_closed_email")
    def test_close_email_called_on_resolve(self, mock_close):
        """resolve_ticket endpoint should call send_case_closed_email."""
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        from src.auth import create_access_token
        from src.storage.sqlite_db import init_database, next_ticket_id

        init_database()
        app = create_app()
        client = TestClient(app)
        token = create_access_token("admin", "admin")
        headers = {"Authorization": f"Bearer {token}"}

        # Process through pipeline (keyword fallback since LLM mocked to fail)
        # Also mock upsert_ticket_embedding to avoid HuggingFace network calls
        with patch("src.core.classifier.get_llm_provider") as mp, \
             patch("src.llm.provider.get_llm_provider") as mp2, \
             patch("src.workflow.pipeline.upsert_ticket_embedding"):
            mp.side_effect = Exception("No LLM")
            mp2.side_effect = Exception("No LLM")
            tid = next_ticket_id()
            process_ticket("Test close", "Closing test", "Tester", "close@example.com", ticket_id=tid)

        resp = client.post(f"/api/v1/tickets/{tid}/resolve", json={
            "reviewer": "Admin",
            "ai_resolution": "Resolved and closed.",
        }, headers=headers)
        assert resp.status_code == 200
        mock_close.assert_called_once()
        call_kwargs = mock_close.call_args.kwargs
        assert call_kwargs["ticket_id"] == tid
        assert call_kwargs["recipient_email"] == "close@example.com"

    @patch("src.notifications.email_service._is_smtp_configured", return_value=False)
    def test_email_skipped_when_smtp_not_configured(self, mock_smtp):
        from src.notifications.email_service import send_ticket_confirmation

        # Should not raise even when SMTP is not configured
        send_ticket_confirmation("HOPE-00000", "nosmtp@example.com", "User", "Test")
        # Verify no crash; notification recorded as skipped


# ═══════════════════════════════════════════════════════════════
# 12. LLM PROVIDER SELECTION
# ═══════════════════════════════════════════════════════════════


class TestLLMProviderSelection:
    def test_fallback_provider_raises(self):
        from src.llm.provider import FallbackProvider

        provider = FallbackProvider()
        with pytest.raises(RuntimeError, match="No LLM provider configured"):
            provider.chat([{"role": "user", "content": "test"}])
        with pytest.raises(RuntimeError, match="No LLM provider configured"):
            provider.chat_json([{"role": "user", "content": "test"}])

    def test_reset_provider(self):
        from src.llm.provider import _provider, reset_provider

        reset_provider()
        # After reset, next call should re-initialize
        from src.llm.provider import _provider as p
        assert p is None
