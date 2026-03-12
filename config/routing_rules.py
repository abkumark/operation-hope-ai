"""Routing rules mapping ticket categories to Dynamics 365 queues."""

from dataclasses import dataclass


@dataclass
class QueueConfig:
    name: str
    dynamics_queue_id: str
    owner: str
    description: str


QUEUES: dict[str, QueueConfig] = {
    "IT Support": QueueConfig(
        name="IT Support",
        dynamics_queue_id="",
        owner="Case Owner",
        description="IT, Product & L&D tickets (OH Business Unit)",
    ),
    "L&D": QueueConfig(
        name="L&D",
        dynamics_queue_id="",
        owner="Case Owner",
        description="Learning & Development tickets",
    ),
    "Marketing": QueueConfig(
        name="Marketing",
        dynamics_queue_id="",
        owner="Marketing Case Owner",
        description="Marketing-related requests",
    ),
    "Leadership": QueueConfig(
        name="Leadership",
        dynamics_queue_id="",
        owner="David Christensen",
        description="Partnership and strategic requests",
    ),
}

EXCLUDED_CATEGORIES = {"hr_request"}

HR_KEYWORDS = [
    "human resources", "hr ", "payroll", "benefits", "leave request",
    "time off", "pto", "employee complaint", "harassment",
]

ROUTING_RULES = {
    "password_reset": "IT Support",
    "login_issue": "IT Support",
    "email_verification": "IT Support",
    "registration_issue": "IT Support",
    "delta_sso": "IT Support",
    "coach_assignment": "IT Support",
    "course_video_issue": "L&D",
    "workplan_navigation": "L&D",
    "program_not_showing": "L&D",
    "stuck_on_task": "L&D",
    "hud_certificate": "L&D",
    "lms_enrollment": "L&D",
    "survey_issue": "L&D",
    "course_feedback": "L&D",
    "course_tools": "L&D",
    "duplicate_records": "IT Support",
    "data_request": "IT Support",
    "follow_up_logging": "IT Support",
    "marketing_request": "Marketing",
    "system_bug": "IT Support",
    "partnership_request": "Leadership",
    "program_enrollment": "IT Support",
    "no_information": "IT Support",
}


def get_queue_for_category(category_id: str) -> str:
    return ROUTING_RULES.get(category_id, "IT Support")


def is_hr_ticket(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in HR_KEYWORDS)


def get_queue_config(queue_name: str) -> QueueConfig | None:
    return QUEUES.get(queue_name)
