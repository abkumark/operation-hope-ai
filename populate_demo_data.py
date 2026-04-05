#!/usr/bin/env python3
"""
Demo Data Population Script for Operation HOPE AI

This script populates the database with comprehensive demo data for showcasing:
- Tickets assigned to all engineers across all categories
- Comprehensive analytics data with meaningful insights
- Realistic ticket statuses and workflows
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.categories import TICKET_CATEGORIES
from storage.sqlite_db import init_database, get_connection, clear_all_data


def create_demo_ticket(
    ticket_id: str,
    subject: str,
    description: str,
    submitter: str,
    submitter_email: str,
    phone_number: str,
    category_id: str,
    assigned_to: str,
    status: str,
    days_ago: int = 0,
    processing_time_ms: float = 2500.0,
) -> None:
    """Create a fully processed demo ticket with AI classification and routing."""

    # Calculate timestamps
    created_time = datetime.now() - timedelta(days=days_ago)
    processed_time = created_time + timedelta(minutes=2)  # Processing delay
    updated_time = processed_time + timedelta(hours=1)   # Status updates

    category = TICKET_CATEGORIES[category_id]

    # AI Classification JSON
    classification = {
        "category_id": category_id,
        "category_name": category.name,
        "confidence": 0.92,
        "language": "es" if "español" in description.lower() or "contraseña" in description.lower() else "en",
        "sentiment": "frustrated" if "stuck" in description.lower() or "not working" in description.lower() else "neutral",
        "urgency": "high" if "urgent" in description.lower() or "asap" in description.lower() else "medium",
        "is_hr": False,
        "summary": f"User experiencing {category.name.lower()} issue",
        "raw_text": description
    }

    # AI Routing JSON
    routing = {
        "action": "assign_to_engineer" if assigned_to else "queue",
        "queue": category.queue,
        "reason": f"Classified as {category.name} with high confidence",
        "requires_approval": not category.auto_resolvable,
        "assigned_to": assigned_to
    }

    # AI Response JSON (sample response)
    response = {
        "response": f"Thank you for contacting Operation HOPE. I understand you're having trouble with {category.name.lower()}. Based on your description, here are some steps that should help resolve your issue:\n\n1. Clear your browser cache and cookies\n2. Try using an incognito/private browsing window\n3. Ensure you're using a supported browser (Chrome, Firefox, Safari)\n\nIf these steps don't resolve the issue, our {category.queue} team will follow up with you within 24 hours.",
        "confidence": 0.88,
        "kb_articles_used": category.kb_articles,
        "generated_at": processed_time.isoformat()
    }

    # AI Resolution (for some tickets)
    ai_resolution = ""
    if status in ["Resolved", "Completed"]:
        ai_resolution = f"Issue resolved through standard {category.name.lower()} troubleshooting procedure. User confirmed resolution via follow-up."

    # Similar tickets (mock data)
    similar_tickets = ["HOPE-00001", "HOPE-00002"] if category_id != "no_information" else []

    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO tickets (
                ticket_id, subject, description, submitter, submitter_email, phone_number,
                status, ai_resolution, similar_ticket_ids, assigned_to,
                classification_json, routing_json, response_json,
                processed_at, processing_time_ms, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                subject,
                description,
                submitter,
                submitter_email,
                phone_number,
                status,
                ai_resolution,
                json.dumps(similar_tickets),
                assigned_to,
                json.dumps(classification),
                json.dumps(routing),
                json.dumps(response),
                processed_time.isoformat(),
                processing_time_ms,
                created_time.isoformat(),
                updated_time.isoformat(),
            ),
        )

        # Add metrics record
        conn.execute(
            """
            INSERT OR REPLACE INTO metrics (
                ticket_id, created_at, first_response_at, resolved_at,
                category, queue, was_auto_resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                created_time.isoformat(),
                processed_time.isoformat(),
                updated_time.isoformat() if status in ["Resolved", "Completed"] else None,
                category_id,
                category.queue,
                1 if category.auto_resolvable else 0,
            ),
        )

        # Add resolution feedback for some completed tickets
        if status in ["Resolved", "Completed"] and days_ago > 1:
            helpful = 1 if "password" not in category_id and "login" not in category_id else 0
            comment = "Very helpful, resolved my issue quickly!" if helpful else "Didn't solve my problem, had to contact support again."

            conn.execute(
                """
                INSERT OR REPLACE INTO resolution_feedback (
                    ticket_id, submitter_email, helpful, comment, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    ticket_id,
                    submitter_email,
                    helpful,
                    comment,
                    updated_time.isoformat(),
                ),
            )


def populate_demo_data():
    """Populate comprehensive demo data covering all categories and engineers."""

    print("Initializing database...")
    init_database()

    print("Clearing existing data...")
    clear_all_data()

    print("Creating demo tickets...")

    engineers = ["torri", "danita", "shonda", "abhishek", "praveen"]
    ticket_counter = 1

    # Demo ticket templates organized by category
    demo_tickets = {
        "password_reset": [
            {
                "subject": "Cannot reset password - link expired",
                "description": "I've been trying to reset my password for the client portal but the link in the email doesn't work. I've tried multiple times over the past 2 days. Please help.",
                "submitter": "Maria Rodriguez",
                "email": "mrodriguez@example.com",
                "phone": "+1-555-0101"
            },
            {
                "subject": "Password reset email not received",
                "description": "I requested a password reset 3 hours ago but haven't received the email. I checked spam/junk folders. My account email is correct.",
                "submitter": "James Wilson",
                "email": "jwilson@email.org",
                "phone": "+1-555-0102"
            }
        ],
        "login_issue": [
            {
                "subject": "Cannot login - credentials invalid error",
                "description": "I cannot log in to the portal. It says my credentials are invalid but I'm sure they're correct. I registered last week and logged in successfully before.",
                "submitter": "Sarah Chen",
                "email": "s.chen@company.com",
                "phone": "+1-555-0103"
            },
            {
                "subject": "Login page keeps redirecting",
                "description": "When I try to login, the page keeps redirecting me back to the login screen. I've cleared my browser cache but still having issues.",
                "submitter": "Robert Davis",
                "email": "rdavis@mail.net",
                "phone": "+1-555-0104"
            }
        ],
        "email_verification": [
            {
                "subject": "Email verification code not received",
                "description": "I signed up yesterday but never got the email verification code. I checked spam folder multiple times. Can you resend the verification?",
                "submitter": "Linda Martinez",
                "email": "lmartinez@example.com",
                "phone": "+1-555-0105"
            }
        ],
        "registration_issue": [
            {
                "subject": "Registration form won't submit",
                "description": "I'm trying to register but the form won't submit. The submit button becomes grayed out after I fill everything. I'm using Chrome on Windows.",
                "submitter": "David Brown",
                "email": "dbrown@email.org",
                "phone": "+1-555-0106"
            }
        ],
        "delta_sso": [
            {
                "subject": "Delta SSO authentication failing",
                "description": "I'm trying to log in through Delta SSO but it keeps redirecting me to an error page. I'm a Delta employee and this worked before.",
                "submitter": "Amanda White",
                "email": "awhite@delta.com",
                "phone": "+1-555-0107"
            }
        ],
        "coach_assignment": [
            {
                "subject": "No coach assigned after 2 weeks",
                "description": "I completed the intake process 2 weeks ago but haven't been assigned a coach yet. Who should I contact about this?",
                "submitter": "Christopher Clark",
                "email": "cclark@example.com",
                "phone": "+1-555-0108"
            },
            {
                "subject": "Request to change coach",
                "description": "I need to request a different coach. My current coach's schedule doesn't align with my availability. Can someone help with reassignment?",
                "submitter": "Patricia Garcia",
                "email": "pgarcia@email.org",
                "phone": "+1-555-0109"
            }
        ],
        "course_video_issue": [
            {
                "subject": "Course videos not loading",
                "description": "The course video is stuck on loading screen. I've tried Chrome and Firefox. It's the Homeownership Counseling module, Session 3.",
                "submitter": "Jennifer Lee",
                "email": "jlee@company.com",
                "phone": "+1-555-0110"
            },
            {
                "subject": "Video buffering constantly",
                "description": "Course videos keep buffering every few seconds. My internet connection is fine for other sites. This is happening in the Credit Management course.",
                "submitter": "Michael Taylor",
                "email": "mtaylor@mail.net",
                "phone": "+1-555-0111"
            }
        ],
        "workplan_navigation": [
            {
                "subject": "Cannot find my workplan",
                "description": "I cannot find my workplan anywhere in the portal. I'm enrolled in Credit & Money Management but don't see where to access the workplan.",
                "submitter": "Daniel Harris",
                "email": "dharris@company.com",
                "phone": "+1-555-0112"
            }
        ],
        "program_not_showing": [
            {
                "subject": "Programs disappeared from dashboard",
                "description": "My programs are not showing on the dashboard anymore. I was enrolled last month in Financial Wellness. Now I only see a blank page.",
                "submitter": "Nancy Anderson",
                "email": "nanderson@mail.net",
                "phone": "+1-555-0113"
            },
            {
                "subject": "Goals not populating in portal",
                "description": "My workplan goals are not showing up in the client portal. I can see the program but no individual goals or tasks are visible.",
                "submitter": "Kevin Thompson",
                "email": "kthompson@example.com",
                "phone": "+1-555-0114"
            }
        ],
        "stuck_on_task": [
            {
                "subject": "Stuck on Task 3 - cannot proceed",
                "description": "I'm stuck on Task 3 in the workplan. It shows as complete but the checkmark won't appear and I can't move to the next task. I've refreshed multiple times.",
                "submitter": "Susan Moore",
                "email": "smoore@example.com",
                "phone": "+1-555-0115"
            }
        ],
        "hud_certificate": [
            {
                "subject": "HUD Certificate not generated",
                "description": "I need to request my HUD certificate for completion. I finished all the requirements last week but don't see how to generate or download it.",
                "submitter": "Thomas Jackson",
                "email": "tjackson@email.org",
                "phone": "+1-555-0116"
            }
        ],
        "lms_enrollment": [
            {
                "subject": "Course enrollment not syncing",
                "description": "I was enrolled in the Financial Wellness course but it doesn't show in my LMS. I can see it in the portal but not in the learning platform.",
                "submitter": "Rebecca Wright",
                "email": "rwright@company.com",
                "phone": "+1-555-0117"
            }
        ],
        "survey_issue": [
            {
                "subject": "Survey won't submit - missing options",
                "description": "The intake survey won't submit. I filled everything out but the Submit button is grayed out. There seem to be missing options in the dropdown for employment status.",
                "submitter": "Carlos Rodriguez",
                "email": "crodriguez@email.org",
                "phone": "+1-555-0118"
            }
        ],
        "course_feedback": [
            {
                "subject": "Spelling errors in Course Module 2",
                "description": "I found several spelling errors in the Financial Wellness course, Module 2. There are typos on slides 5, 8, and 12 that should be corrected.",
                "submitter": "Elena Vargas",
                "email": "evargas@company.com",
                "phone": "+1-555-0119"
            }
        ],
        "course_tools": [
            {
                "subject": "Budget calculator not working",
                "description": "The budget calculator tool in the Financial Wellness course is not working. When I enter numbers and click Calculate, nothing happens.",
                "submitter": "Fernando Lopez",
                "email": "flopez@mail.net",
                "phone": "+1-555-0120"
            }
        ],
        "duplicate_records": [
            {
                "subject": "Duplicate client records need merging",
                "description": "Client Maria Santos appears to have two records in the system (ID: 12345 and 67890). Both have the same email and phone number. Please merge these records.",
                "submitter": "Staff Member - IT",
                "email": "it-support@operationhope.org",
                "phone": "+1-555-0200"
            }
        ],
        "data_request": [
            {
                "subject": "Coaching session data discrepancy",
                "description": "The PowerBI dashboard shows 15 coaching sessions for client Johnson, but my records show 18 sessions. Can someone verify the data accuracy?",
                "submitter": "Coach Williams",
                "email": "cwilliams@operationhope.org",
                "phone": "+1-555-0201"
            }
        ],
        "follow_up_logging": [
            {
                "subject": "Follow-ups not appearing on dashboard",
                "description": "My follow-up services are not reporting correctly on the PowerBI dashboard. I've logged 12 follow-ups this month but only 8 are showing.",
                "submitter": "Coach Thompson",
                "email": "tthompson@operationhope.org",
                "phone": "+1-555-0202"
            }
        ],
        "marketing_request": [
            {
                "subject": "Flyer design request - Financial Wellness",
                "description": "We need a promotional flyer designed for the upcoming Financial Wellness workshop series. Please include the new branding guidelines and contact information.",
                "submitter": "Marketing Team",
                "email": "marketing@operationhope.org",
                "phone": "+1-555-0300"
            }
        ],
        "system_bug": [
            {
                "subject": "Portal crashes when uploading documents",
                "description": "The client portal crashes consistently when users try to upload documents larger than 5MB. This is affecting multiple users across different browsers.",
                "submitter": "Support Team",
                "email": "support@operationhope.org",
                "phone": "+1-555-0400"
            }
        ],
        "partnership_request": [
            {
                "subject": "Partnership inquiry - Local Credit Union",
                "description": "ABC Credit Union is interested in partnering with Operation HOPE for financial literacy workshops. They want to discuss collaboration opportunities.",
                "submitter": "John Smith - ABC Credit Union",
                "email": "jsmith@abccu.org",
                "phone": "+1-555-0500"
            }
        ],
        "program_enrollment": [
            {
                "subject": "Bulk enrollment request - Corporate Partnership",
                "description": "Delta Airlines has 25 employees ready for enrollment in the Financial Wellness program. Please process their bulk enrollment and send confirmation.",
                "submitter": "Delta HR Representative",
                "email": "hr.training@delta.com",
                "phone": "+1-555-0600"
            }
        ],
        "no_information": [
            {
                "subject": "Help needed",
                "description": "I need help with something but not sure what category this falls under. Can someone contact me?",
                "submitter": "Confused User",
                "email": "confused@example.com",
                "phone": "+1-555-0700"
            }
        ]
    }

    # Status distribution for realistic analytics
    status_distribution = [
        ("Open", 15),           # 15% open tickets
        ("Assigned", 20),       # 20% assigned
        ("WorkInProgress", 25), # 25% in progress
        ("Resolved", 30),       # 30% resolved
        ("Completed", 10)       # 10% completed
    ]

    # Create tickets for each category
    for category_id, tickets in demo_tickets.items():
        if category_id not in TICKET_CATEGORIES:
            continue

        for i, ticket_data in enumerate(tickets):
            ticket_id = f"HOPE-{ticket_counter:05d}"

            # Round-robin assign to engineers
            engineer = engineers[(ticket_counter - 1) % len(engineers)]

            # Distribute status based on ticket age
            days_ago = (ticket_counter % 14) + 1  # 1-14 days ago
            if days_ago <= 2:
                status = "Open"
            elif days_ago <= 5:
                status = "Assigned"
            elif days_ago <= 8:
                status = "WorkInProgress"
            elif days_ago <= 11:
                status = "Resolved"
            else:
                status = "Completed"

            # Don't assign engineers to open tickets initially
            assigned_engineer = engineer if status != "Open" else ""

            create_demo_ticket(
                ticket_id=ticket_id,
                subject=ticket_data["subject"],
                description=ticket_data["description"],
                submitter=ticket_data["submitter"],
                submitter_email=ticket_data["email"],
                phone_number=ticket_data["phone"],
                category_id=category_id,
                assigned_to=assigned_engineer,
                status=status,
                days_ago=days_ago,
                processing_time_ms=2000 + (ticket_counter % 3000)  # Vary processing time
            )

            ticket_counter += 1

    # Add some Spanish language tickets
    spanish_tickets = [
        {
            "category": "password_reset",
            "subject": "No puedo restablecer mi contraseña",
            "description": "He intentado restablecer mi contraseña varias veces pero no recibo el correo electrónico. Revisé la carpeta de spam. ¿Pueden ayudarme por favor?",
            "submitter": "Ana Gutierrez",
            "email": "agutierrez@example.com",
            "phone": "+1-555-1001"
        },
        {
            "category": "course_video_issue",
            "subject": "Videos del curso no se reproducen",
            "description": "Los videos del módulo de Propiedades no se reproducen. Solo muestran una pantalla negra. Mi conexión de internet funciona bien para otros sitios.",
            "submitter": "Miguel Santos",
            "email": "msantos@email.org",
            "phone": "+1-555-1002"
        }
    ]

    for spanish_ticket in spanish_tickets:
        ticket_id = f"HOPE-{ticket_counter:05d}"
        engineer = engineers[(ticket_counter - 1) % len(engineers)]

        create_demo_ticket(
            ticket_id=ticket_id,
            subject=spanish_ticket["subject"],
            description=spanish_ticket["description"],
            submitter=spanish_ticket["submitter"],
            submitter_email=spanish_ticket["email"],
            phone_number=spanish_ticket["phone"],
            category_id=spanish_ticket["category"],
            assigned_to=engineer,
            status="Assigned",
            days_ago=3,
            processing_time_ms=2800
        )

        ticket_counter += 1

    # Set engineer expertise for better routing
    expertise_mapping = {
        "torri": ["password_reset", "login_issue", "email_verification", "registration_issue"],
        "danita": ["course_video_issue", "workplan_navigation", "program_not_showing", "stuck_on_task"],
        "shonda": ["hud_certificate", "lms_enrollment", "survey_issue", "course_feedback"],
        "abhishek": ["duplicate_records", "data_request", "follow_up_logging", "system_bug"],
        "praveen": ["delta_sso", "coach_assignment", "course_tools", "partnership_request"]
    }

    with get_connection() as conn:
        for engineer, categories in expertise_mapping.items():
            for category in categories:
                conn.execute(
                    "INSERT OR REPLACE INTO engineer_expertise (engineer_username, category_id) VALUES (?, ?)",
                    (engineer, category)
                )

    print(f"Created {ticket_counter - 1} demo tickets")
    print(f"Assigned tickets to {len(engineers)} engineers: {', '.join(engineers)}")
    print(f"Covered {len(demo_tickets)} categories")
    print("Demo data population completed successfully!")


if __name__ == "__main__":
    populate_demo_data()