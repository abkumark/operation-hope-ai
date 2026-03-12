"""Ticket classification taxonomy based on Operation HOPE's actual Knowledge Base."""

from dataclasses import dataclass


@dataclass
class TicketCategory:
    id: str
    name: str
    description: str
    ticket_type: str  # "external", "internal", "any"
    auto_resolvable: bool
    queue: str
    kb_articles: list[str]
    keywords: list[str]


TICKET_CATEGORIES: dict[str, TicketCategory] = {
    "password_reset": TicketCategory(
        id="password_reset",
        name="Password Reset",
        description="Client needs help resetting their password for the OH Client Portal",
        ticket_type="external",
        auto_resolvable=True,
        queue="IT Support",
        kb_articles=["client_login.md"],
        keywords=["password", "reset", "forgot", "can't log in", "login", "sign in", "locked out"],
    ),
    "login_issue": TicketCategory(
        id="login_issue",
        name="Client Login Issue",
        description="Client cannot log in to the Operation HOPE Client Portal",
        ticket_type="external",
        auto_resolvable=True,
        queue="IT Support",
        kb_articles=["client_login.md"],
        keywords=["log in", "login", "sign in", "access", "portal", "can't get in", "unable to access"],
    ),
    "email_verification": TicketCategory(
        id="email_verification",
        name="Email Verification Issue",
        description="Client unable to verify email during registration",
        ticket_type="external",
        auto_resolvable=True,
        queue="IT Support",
        kb_articles=["email_verification.md"],
        keywords=["verify", "verification", "email code", "confirmation", "register", "sign up"],
    ),
    "registration_issue": TicketCategory(
        id="registration_issue",
        name="Registration Issue",
        description="Client having trouble completing the registration process",
        ticket_type="external",
        auto_resolvable=True,
        queue="IT Support",
        kb_articles=["email_verification.md", "client_login.md"],
        keywords=["register", "registration", "sign up", "create account", "new account"],
    ),
    "delta_sso": TicketCategory(
        id="delta_sso",
        name="Delta SSO Login",
        description="Delta employee having trouble with SSO login to Operation HOPE portal",
        ticket_type="external",
        auto_resolvable=True,
        queue="IT Support",
        kb_articles=["delta_sso.md"],
        keywords=["delta", "sso", "single sign on", "delta employee", "delta sign in"],
    ),
    "coach_assignment": TicketCategory(
        id="coach_assignment",
        name="Coach Assignment / Reassignment",
        description="Client wants to change coaches or needs a coach assigned",
        ticket_type="external",
        auto_resolvable=False,
        queue="IT Support",
        kb_articles=["program_enrollment.md"],
        keywords=["coach", "change coach", "reassign", "new coach", "different coach", "assign coach"],
    ),
    "course_video_issue": TicketCategory(
        id="course_video_issue",
        name="Course Videos Not Working",
        description="Client cannot play or view course videos",
        ticket_type="external",
        auto_resolvable=True,
        queue="L&D",
        kb_articles=["course_videos.md"],
        keywords=["video", "not playing", "won't load", "course video", "can't watch", "buffering"],
    ),
    "workplan_navigation": TicketCategory(
        id="workplan_navigation",
        name="Workplan Navigation",
        description="Client needs help navigating workplans on the client portal",
        ticket_type="external",
        auto_resolvable=True,
        queue="L&D",
        kb_articles=["workplan_navigation.md"],
        keywords=["workplan", "work plan", "navigate", "find task", "where is", "how to"],
    ),
    "program_not_showing": TicketCategory(
        id="program_not_showing",
        name="Programs/Workplan/Goals Not Showing",
        description="Programs, workplans, or goals not populating in the client portal",
        ticket_type="external",
        auto_resolvable=True,
        queue="L&D",
        kb_articles=["programs_not_showing.md"],
        keywords=["not showing", "not populating", "missing", "can't see", "disappeared", "goals", "programs"],
    ),
    "stuck_on_task": TicketCategory(
        id="stuck_on_task",
        name="Stuck on a Task",
        description="Client having trouble completing a task in the portal",
        ticket_type="external",
        auto_resolvable=False,
        queue="L&D",
        kb_articles=["stuck_on_task.md"],
        keywords=["stuck", "can't complete", "task", "won't move", "next step", "blocked"],
    ),
    "hud_certificate": TicketCategory(
        id="hud_certificate",
        name="HUD Certificate",
        description="Client needs help obtaining HUD Certification through online learning",
        ticket_type="external",
        auto_resolvable=True,
        queue="L&D",
        kb_articles=["hud_certificate.md"],
        keywords=["hud", "certificate", "certification", "homeownership", "before you buy", "after you buy"],
    ),
    "lms_enrollment": TicketCategory(
        id="lms_enrollment",
        name="LMS / Course Enrollment",
        description="Issues with LMS course enrollments or completion tracking",
        ticket_type="external",
        auto_resolvable=False,
        queue="L&D",
        kb_articles=["lms_enrollments.md"],
        keywords=["lms", "enrollment", "course", "completed", "still showing", "100%"],
    ),
    "survey_issue": TicketCategory(
        id="survey_issue",
        name="Survey Completion Issue",
        description="Client unable to complete a survey due to missing options or errors",
        ticket_type="external",
        auto_resolvable=False,
        queue="L&D",
        kb_articles=["survey_completion.md", "intake_survey_values.md"],
        keywords=["survey", "questionnaire", "can't submit", "missing option", "intake", "output"],
    ),
    "course_feedback": TicketCategory(
        id="course_feedback",
        name="Course Content Feedback",
        description="Feedback about spelling, content errors, or suggestions for courses",
        ticket_type="external",
        auto_resolvable=False,
        queue="L&D",
        kb_articles=["course_feedback.md"],
        keywords=["spelling", "typo", "content", "feedback", "incorrect", "wrong information"],
    ),
    "course_tools": TicketCategory(
        id="course_tools",
        name="Course Tools / Resources Not Working",
        description="Course tools, resources, or features not functioning properly",
        ticket_type="external",
        auto_resolvable=True,
        queue="L&D",
        kb_articles=["course_tools.md"],
        keywords=["tool", "resource", "not working", "broken", "feature", "calculator"],
    ),
    "duplicate_records": TicketCategory(
        id="duplicate_records",
        name="Duplicate Client Records",
        description="Duplicate client records detected in Dynamics 365 that need merging",
        ticket_type="internal",
        auto_resolvable=False,
        queue="IT Support",
        kb_articles=["duplicate_records.md"],
        keywords=["duplicate", "merge", "two records", "multiple accounts", "same person"],
    ),
    "data_request": TicketCategory(
        id="data_request",
        name="Data Request",
        description="Coach requesting data corrections or reports about coaching sessions/workshops",
        ticket_type="internal",
        auto_resolvable=False,
        queue="IT Support",
        kb_articles=[],
        keywords=["data", "report", "coaching sessions", "workshops", "numbers", "not showing correctly"],
    ),
    "follow_up_logging": TicketCategory(
        id="follow_up_logging",
        name="Follow-Up Logging Issue",
        description="Coach follow-up services not reporting correctly on PowerBI dashboard",
        ticket_type="internal",
        auto_resolvable=False,
        queue="IT Support",
        kb_articles=["follow_ups_logging.md"],
        keywords=["follow-up", "follow up", "not logging", "dashboard", "powerbi", "not reporting"],
    ),
    "marketing_request": TicketCategory(
        id="marketing_request",
        name="Marketing Request",
        description="Marketing-related requests (flyers, materials, campaigns)",
        ticket_type="any",
        auto_resolvable=False,
        queue="Marketing",
        kb_articles=[],
        keywords=["marketing", "flyer", "campaign", "promotional", "materials", "branding"],
    ),
    "system_bug": TicketCategory(
        id="system_bug",
        name="System Bug",
        description="System malfunction or unexpected behavior in the platform",
        ticket_type="any",
        auto_resolvable=False,
        queue="IT Support",
        kb_articles=[],
        keywords=["bug", "error", "broken", "crash", "not working", "malfunction", "glitch"],
    ),
    "partnership_request": TicketCategory(
        id="partnership_request",
        name="Partnership Request",
        description="External partnership or collaboration inquiries",
        ticket_type="external",
        auto_resolvable=False,
        queue="Leadership",
        kb_articles=[],
        keywords=["partnership", "partner", "collaborate", "collaboration", "sponsor"],
    ),
    "program_enrollment": TicketCategory(
        id="program_enrollment",
        name="Program Enrollment",
        description="Request to enroll a client in a specific program",
        ticket_type="internal",
        auto_resolvable=False,
        queue="IT Support",
        kb_articles=["program_enrollment.md"],
        keywords=["enroll", "enrollment", "program", "sign up for program"],
    ),
    "no_information": TicketCategory(
        id="no_information",
        name="Insufficient Information",
        description="Ticket lacks enough detail to classify or resolve",
        ticket_type="any",
        auto_resolvable=True,
        queue="IT Support",
        kb_articles=["no_information.md"],
        keywords=[],
    ),
}


def get_category(category_id: str) -> TicketCategory | None:
    return TICKET_CATEGORIES.get(category_id)


def get_all_categories() -> list[TicketCategory]:
    return list(TICKET_CATEGORIES.values())


def get_auto_resolvable_categories() -> list[str]:
    return [cat_id for cat_id, cat in TICKET_CATEGORIES.items() if cat.auto_resolvable]
