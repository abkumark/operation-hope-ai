#!/usr/bin/env python3
"""Generate synthetic support tickets for testing and demos."""
import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

# Category templates: (subject_templates, description_templates)
TEMPLATES = {
    "password_reset": (
        [
            "Cannot reset password",
            "Password reset link not working",
            "Forgot password - need help",
            "Password reset email not received",
        ],
        [
            "I've been trying to reset my password but the link in the email doesn't work.",
            "The password reset link says it expired. I need a new one.",
            "I never received the password reset email. Checked spam folder.",
            "I forgot my password and the reset process isn't working.",
        ],
    ),
    "account_access": (
        [
            "Cannot log in",
            "Login not working",
            "Invalid credentials",
            "Email verification issue",
        ],
        [
            "I cannot log in to the portal. It says my credentials are invalid.",
            "I registered but never got the verification code. Can you resend?",
            "My login keeps failing. I'm sure my password is correct.",
            "I verified my email but still can't log in.",
        ],
    ),
    "learning_management": (
        [
            "Course video not playing",
            "Video stuck on loading",
            "Cannot access course content",
        ],
        [
            "The course video won't play. I've tried different browsers.",
            "Video is stuck on loading. I've refreshed multiple times.",
            "I cannot access the video content in the Homeownership module.",
        ],
    ),
    "client_portal": (
        [
            "Cannot find workplan",
            "Stuck on task",
            "Programs not showing",
            "Workplan not loading",
        ],
        [
            "I cannot find my workplan. I'm enrolled but don't see it.",
            "I'm stuck on a task. The checkmark won't appear.",
            "My programs are not showing on the dashboard.",
            "The workplan page just spins and never loads.",
        ],
    ),
    "hud_certificate": (
        [
            "HUD certificate request",
            "Need HUD certificate",
        ],
        [
            "I completed all requirements. How do I get my HUD certificate?",
            "I need to request my HUD certificate for completion.",
        ],
    ),
    "delta_sso": (
        [
            "Delta SSO login issue",
            "Delta SSO redirect error",
        ],
        [
            "I'm trying to log in through Delta SSO but it redirects to an error page.",
            "Delta SSO login keeps failing. I'm an employee.",
        ],
    ),
    "coach_assignment": (
        [
            "No coach assigned",
            "Coach assignment delay",
        ],
        [
            "I completed intake but haven't been assigned a coach yet.",
            "It's been 2 weeks and I still don't have a coach. Who do I contact?",
        ],
    ),
    "survey_issue": (
        [
            "Survey won't submit",
            "Intake survey problem",
        ],
        [
            "The intake survey won't submit. The Submit button is grayed out.",
            "I filled out the survey but it won't let me submit.",
        ],
    ),
    "no_information": (
        [
            "No information in account",
            "Empty account",
        ],
        [
            "I logged in but there's no information in my account. No programs, nothing.",
            "My account is empty. Is this normal?",
        ],
    ),
    "duplicate_records": (
        [
            "Duplicate profile",
            "Two accounts",
        ],
        [
            "I think I have two accounts. I registered twice. Can you merge them?",
            "I have duplicate records. Can you delete the duplicate?",
        ],
    ),
    "lms_enrollment": (
        [
            "LMS course not showing",
            "Course not in LMS",
        ],
        [
            "I was enrolled but the course doesn't show in my LMS.",
            "The course shows in the portal but not in the learning platform.",
        ],
    ),
}

# Spanish templates for a few categories
SPANISH_TEMPLATES = {
    "password_reset": (
        ["No puedo restablecer mi contraseña", "Enlace de restablecimiento no funciona"],
        [
            "He intentado restablecer mi contraseña varias veces pero no recibo el correo.",
            "El enlace de restablecimiento dice que expiró.",
        ],
    ),
    "account_access": (
        ["No puedo iniciar sesión", "Problemas de login"],
        [
            "No puedo iniciar sesión en el portal. Dice que mis credenciales son inválidas.",
            "Ya verifiqué mi correo pero no puedo iniciar sesión.",
        ],
    ),
}

FIRST_NAMES = [
    "Maria", "James", "Sarah", "Robert", "Linda", "David", "Jennifer", "Michael",
    "Amanda", "Christopher", "Patricia", "Daniel", "Nancy", "Kevin", "Carlos",
    "Elena", "Fernando", "Susan", "Thomas", "Rebecca",
]
LAST_NAMES = [
    "Johnson", "Wilson", "Chen", "Davis", "Martinez", "Brown", "Lee", "Taylor",
    "White", "Clark", "Garcia", "Harris", "Anderson", "Thompson", "Rodriguez",
    "Vargas", "Lopez", "Moore", "Jackson", "Wright",
]
DOMAINS = ["example.com", "email.org", "company.com", "mail.net"]


def random_email() -> str:
    """Generate a random email address."""
    first = random.choice(FIRST_NAMES).lower()
    last = random.choice(LAST_NAMES).lower()
    domain = random.choice(DOMAINS)
    return f"{first}.{last}@{domain}"


def random_name() -> str:
    """Generate a random full name."""
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_date(days_back: int = 30) -> str:
    """Generate a random datetime within the last N days."""
    dt = datetime.now() - timedelta(days=random.randint(0, days_back))
    dt = dt.replace(
        hour=random.randint(8, 17),
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
    )
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def generate_ticket(
    ticket_id: str,
    category: str,
    use_spanish: bool = False,
) -> dict:
    """Generate a single synthetic ticket."""
    if use_spanish and category in SPANISH_TEMPLATES:
        subs, descs = SPANISH_TEMPLATES[category]
    else:
        subs, descs = TEMPLATES.get(
            category,
            (["General support request"], ["I need help with something."]),
        )
    subject = random.choice(subs)
    description = random.choice(descs)
    # Add optional variation
    if random.random() < 0.3:
        description += " I've tried refreshing and different browsers."
    return {
        "ticket_id": ticket_id,
        "subject": subject,
        "description": description,
        "submitter_name": random_name(),
        "submitter_email": random_email(),
        "created_date": random_date(),
        "category": category,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic support tickets")
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=50,
        help="Number of tickets to generate",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/sample_tickets/synthetic_tickets.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "--spanish-ratio",
        type=float,
        default=0.15,
        help="Fraction of tickets to generate in Spanish (0-1)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    categories = list(TEMPLATES.keys())
    rows = []
    for i in range(args.count):
        ticket_id = f"TKT-SYN-{i + 1:05d}"
        category = random.choice(categories)
        use_spanish = random.random() < args.spanish_ratio
        rows.append(generate_ticket(ticket_id, category, use_spanish))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ticket_id", "subject", "description", "submitter_name", "submitter_email", "created_date", "category"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {args.count} tickets in {args.output}")


if __name__ == "__main__":
    main()
