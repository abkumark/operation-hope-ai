# HOPE AI: Architecture & Approach Document

## Executive Summary

Operation HOPE handles approximately 30 support tickets per day with a 48-hour average response time. Most tickets are repetitive — password resets, login issues, course navigation, and similar inquiries. HOPE AI uses GPT-5.2 (Azure OpenAI) combined with Retrieval-Augmented Generation (RAG) over the real Knowledge Base to auto-classify, auto-respond, and intelligently route tickets — reducing response time from 48 hours to minutes for automated cases while maintaining quality and human oversight where needed.

---

## 1. The Challenge

| Dimension | Detail |
|-----------|--------|
| **Volume & Capacity** | 3–5 person support team handles ~30 tickets/day |
| **Response Time** | 48-hour average creates client frustration |
| **Repetitive Workload** | ~70% of tickets are repetitive and automatable |
| **Bilingual Support** | English and Spanish required |
| **Legacy Stack** | No AI capabilities in current Dynamics 365 setup |
| **Knowledge Silos** | Tribal knowledge trapped in team members, not documentation |

## 2. Solution Overview

HOPE AI is an intelligent support system that provides:

- **AI-Powered Classification** — Automatic categorization into 21+ ticket categories
- **RAG-Based Resolution** — Contextual response generation grounded in the Knowledge Base
- **Confidence-Based Routing** — Auto-draft, suggest+review, or human-only based on AI confidence
- **Role-Based Workflows** — Admin oversight, engineer work queues, public ticket submission
- **Strategic Analytics** — Trend detection, knowledge gap identification, performance metrics

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Public Ticket │  │ Staff Login  │  │ Admin Dashboard  │  │
│  │   Submission  │  │ (RBAC)       │  │ Engineer Queue   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│          HTML/CSS/JS + Chart.js + Jinja2 Templates          │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API (JSON)
┌──────────────────────────▼──────────────────────────────────┐
│                       API LAYER                              │
│            FastAPI (async, OpenAPI, CORS)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │  Auth     │ │ Tickets  │ │ KB/RAG   │ │ Analytics    │   │
│  │ Endpoints │ │ CRUD     │ │ Endpoints│ │ & Trends     │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│  ┌──────────┐ ┌──────────────┐ ┌────────────────────────┐  │
│  │ Approvals│ │ Config/Expert│ │ Dynamics 365 / Webhook │  │
│  └──────────┘ └──────────────┘ └────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      AI CORE LAYER                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Classifier   │  │ Router       │  │ Responder        │  │
│  │ (LLM+keyword)│  │ (confidence) │  │ (RAG pipeline)   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Resolution   │  │ Approval     │  │ Escalation       │  │
│  │ Engine       │  │ Workflow     │  │ Rules            │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ Trend Engine │  │ Language     │                         │
│  │ (Analytics)  │  │ Detector     │                         │
│  └──────────────┘  └──────────────┘                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    PERSISTENCE LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ SQLite       │  │ ChromaDB     │  │ Email Service    │  │
│  │ (tickets,    │  │ (vector      │  │ (SMTP outbound)  │  │
│  │  approvals,  │  │  embeddings) │  │                  │  │
│  │  metrics,    │  │              │  │                  │  │
│  │  expertise)  │  │              │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                  INTEGRATION LAYER                            │
│  ┌──────────────┐  ┌──────────────────────────────────────┐ │
│  │ LLM Provider │  │ Dynamics 365 (Dataverse REST API)    │ │
│  │ Abstraction  │  │ Power Automate Webhooks               │ │
│  │ (Azure/OAI/  │  │ (Mock mode for demo)                  │ │
│  │  Ollama)     │  │                                       │ │
│  └──────────────┘  └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend** | Python 3.11+, FastAPI | Async, type hints, OpenAPI docs, production-ready |
| **LLM** | Azure OpenAI GPT-5.2 | Primary; with provider abstraction for OpenAI/Ollama fallback |
| **RAG Vector Store** | ChromaDB + sentence-transformers | Local embeddings, zero external dependency for search |
| **Database** | SQLite | Zero-config, durable, survives restarts, built into Python |
| **Frontend** | HTML/CSS/JS (vanilla) + Chart.js | No build step, fast iteration, branded UI |
| **Templating** | Jinja2 (via FastAPI) | Server-rendered pages with dynamic data |
| **Integration** | Dynamics 365 REST API, Power Automate | Enterprise CRM compatibility |
| **Email** | Python smtplib (SMTP) | Standard outbound notifications |
| **Testing** | pytest, pytest-asyncio | Fixture-based mocking, async test support |
| **Linting** | ruff | Fast Python linter |

---

## 5. Core Modules

### 5.1 Classification Engine (`src/core/classifier.py`)

The classifier determines the ticket category, confidence, sentiment, urgency, and language.

**Strategy: LLM + Keyword Fallback**
- Primary: GPT-5.2 via structured JSON prompt with 21-category taxonomy
- Fallback: Deterministic keyword matching using term frequency when LLM is unavailable
- HR Detection: Sensitive HR keywords trigger exclusion from automated drafting

**Output:** `ClassificationResult` dataclass with `category_name`, `category_id`, `confidence`, `is_hr_related`, `sentiment`, `urgency`, `summary`, `language`.

### 5.2 Routing Engine (`src/core/router.py`)

Confidence-based routing determines the action for each ticket:

| Confidence | Action | Meaning |
|-----------|--------|---------|
| ≥ 85% + auto-resolvable | `AUTO_RESOLVE` | AI draft created, queued for approval |
| 60–85% | `SUGGESTED_REVIEW` | Agent reviews AI suggestion before sending |
| < 60% | `ROUTE_TO_HUMAN` | Fully manual handling |
| HR keywords | `HR_EXCLUDED` | Always routed to human |
| Urgency/time rules | `ESCALATED` | Priority escalation |

### 5.3 RAG Pipeline (`src/knowledge/`)

**Knowledge Base Ingestion:**
1. Parse markdown KB articles with YAML frontmatter metadata
2. Chunk into content, resolution steps, and response template segments
3. Embed using sentence-transformers and store in ChromaDB
4. Support for bilingual articles (English + Spanish subdirectory)

**Response Generation:**
1. Embed incoming ticket description
2. Top-k retrieval from ChromaDB with optional category/language filtering
3. LLM generates contextual response conditioned on retrieved chunks
4. Response includes citations to source KB articles

### 5.4 Resolution Engine (`src/core/resolution_engine.py`)

AI-powered resolution for admin review:

1. **Similar Ticket Search** — Keyword-based similarity (SequenceMatcher) against historical tickets
2. **Context Building** — Current issue + top 3 similar historical tickets fed to LLM
3. **Structured Output** — Step-by-step proposed resolution + reference ticket IDs
4. **Fallback** — Template-based resolution when LLM is unavailable

### 5.5 Approval Workflow (`src/workflow/approval.py`)

State machine for AI-generated responses:

```
draft → pending_review → sent | rejected | rerouted
```

- Admins can edit AI drafts before approval
- Full audit trail via `approval_events` table
- Reroute to different queue or engineer

### 5.6 Ticket Processing Pipeline (`src/workflow/pipeline.py`)

Orchestrates the end-to-end flow:

```
Incoming Ticket
  → Classify (category, confidence, sentiment, urgency, language)
  → Route (auto-resolve / suggest-review / human / HR-excluded / escalate)
  → Generate Response (RAG pipeline)
  → Create Approval Record
  → Find Similar Tickets
  → Generate AI Resolution
  → Persist to SQLite
  → Record Metrics
  → Send Email Notification
```

### 5.7 Trend Engine (`src/analytics/trend_engine.py`)

Strategic analytics for admin decision-making:

- **Problem Clustering** — Groups tickets by category + subject similarity; detects volume spikes
- **Knowledge Gap Detection** — Identifies "how-to" tickets (user error, not technical) via keyword analysis
- **Training Alerts** — Flags categories with >5 "how-to" tickets suggesting a need for training/FAQ
- **Engineer Performance** — Tracks assignment counts, resolution counts, and open tickets per engineer
- **AI vs. Human Ratio** — Measures AI-resolved vs. manually-routed ticket percentages

---

## 6. Data Model

### SQLite Schema (`data/app/hope_ai.db`)

| Table | Purpose |
|-------|---------|
| `tickets` | Core ticket data: ID, subject, description, submitter, email, status, AI resolution, classification/routing/response JSON, similar ticket IDs, assigned engineer, timestamps |
| `approvals` | Approval state per ticket: status, AI category/confidence/response, queue, reviewer, notes, final response |
| `approval_events` | Audit trail: event type, actor, details, timestamp per ticket |
| `metrics` | Performance data: created/response/resolved timestamps, category, queue, auto-resolve flag |
| `email_notifications` | Email log: recipient, subject, status (sent/pending/failed), timestamps |
| `engineer_expertise` | Category-to-engineer expertise mapping for routing recommendations |
| `mock_cases` | Dynamics 365 mock data for demo mode |
| `ticket_sequence` | Auto-incrementing ticket ID generator (HOPE-00001, HOPE-00002, ...) |

### ChromaDB (`data/chroma_db/`)

- Collection: `hope_kb`
- Chunks: content, resolution steps, response template per article
- Metadata: filename, chunk_type, category, language, auto_resolvable
- Embeddings: sentence-transformers (all-MiniLM-L6-v2)

---

## 7. User Roles & Access Control

| Role | Access |
|------|--------|
| **Public (Unauthenticated)** | Submit tickets via the public form; receive ticket ID and email confirmation |
| **Admin** | Full dashboard: all tickets, management (edit/approve/close/delete), analytics, trend engine, knowledge base, configuration, engineer routing |
| **Engineer** | Personal work queue: tickets assigned to them; submit manual resolutions for admin review |

**Authentication:** SHA-256 hashed passwords (demo-grade). Users: admin, torri, danita, shonda, abhishek, praveen.

---

## 8. UI Architecture

### Landing Page (Public Access)
- **Tab 1: Get Help** — Public ticket submission form with email, subject, description, sample chips for quick input
- **Tab 2: Staff Login** — Username/password authentication with role-based redirect

### Admin Dashboard
- **Dashboard** — KPIs (total tickets, AI-resolved %, open tickets, avg response time), recent tickets, quick actions
- **Ticket Management** — Full ticket list with status badges, side-by-side review pane (user issue vs. AI resolution), quick approve/manual override/route/delete actions
- **Ticket Explorer** — Two-pane layout with compact tabbed detail view:
  - Overview tab: metadata, classification, timestamps
  - Resolution tab: AI resolution, expandable KB article references
  - Routing tab: assignment, engineer recommendations based on expertise + workload
- **Analytics** — KPIs, problem clusters, volume spikes, knowledge gaps, training alerts, engineer performance, AI vs. human metrics, Chart.js visualizations
- **Knowledge Base** — Two-pane layout: scrollable article list + full article detail (resolution steps, response template, internal notes)
- **Configuration** — Queue routing map with inline engineer expertise tagging

### Engineer Dashboard
- **My Queue** — Tickets assigned to the logged-in engineer; resolution input form; submit back to admin for final approval

---

## 9. Integration Points

### Dynamics 365 (Dataverse)
- REST API integration for creating, reading, updating, and listing cases
- Field mapping configurable via settings (entity name, status field, AI fields, etc.)
- Mock mode for demo; live mode for production

### Power Automate
- Webhook endpoint (`/webhook/power-automate`) for inbound ticket creation
- Designed for integration with Power Automate flows triggered by Dynamics 365 events

### Email (SMTP)
- Outbound notifications on ticket creation and status changes
- Configurable SMTP settings (host, port, TLS, credentials)
- Email tracking in `email_notifications` table

---

## 10. API Endpoints Summary

| Category | Endpoints | Count |
|----------|-----------|-------|
| Authentication | POST login | 1 |
| Tickets | submit, process, list, get, delete, patch resolution, approve-close, similar, assign, engineer-resolve, my-queue, recommend-engineer | 12 |
| Knowledge Base | ingest, status, articles list, article detail, search | 5 |
| Analytics | summary, trends | 2 |
| Approvals | list, detail, history, approve, reject, reroute | 6 |
| Dynamics 365 | create, list, get, update cases | 4 |
| Configuration | get/set expertise, list engineers | 3 |
| System | health, integration status, Power Automate webhook, notifications | 4 |
| **Total** | | **37** |

---

## 11. Expected Impact

| Metric | Current | Target |
|--------|---------|--------|
| Response Time | 48 hours | Minutes for AI-drafted cases |
| AI Draft Coverage | 0% | 60–70% of tickets |
| Cost Savings | — | ~2–3 FTE hours/day recovered |
| Classification Accuracy | — | >85% |
| Bilingual Coverage | Partial | Full EN/ES |
| Knowledge Gap Visibility | None | Automated identification + training alerts |

---

## 12. Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 1: Demo** | Standalone branded web UI, AI pipeline, mock integrations, analytics | **Current** |
| **Phase 2: Pilot** | Power Automate integration, live Dynamics 365, SMTP email, SSO | Planned |
| **Phase 3: Production** | Azure-hosted, Copilot Studio agent, advanced ML clustering, SLA enforcement | Future |

---

## 13. Known Limitations & Future Improvements

### Security (Demo-Grade)
- Password hashing uses SHA-256 (upgrade to bcrypt/argon2 for production)
- API endpoints lack per-request authentication middleware (add FastAPI `Depends` guards)
- Session management is client-side (`sessionStorage`); move to server-side sessions with HttpOnly cookies

### Robustness
- Many exception handlers silently swallow errors; add structured logging
- `update_ticket_fields` accepts dynamic column names; add whitelist validation
- LLM API calls lack retry logic and timeout configuration
- SQLite `check_same_thread=False` may cause issues under high concurrency; consider connection pooling

### Scalability
- SQLite is suitable for demo/pilot; migrate to PostgreSQL for production
- ChromaDB is local; consider managed vector database for production scale
- Similar ticket search is keyword-based (SequenceMatcher); upgrade to semantic search using embeddings

### Frontend
- Several empty `catch {}` blocks in JavaScript; add user-facing error feedback
- Unused CSS classes from previous iterations should be cleaned up
- Accessibility improvements needed (ARIA roles, keyboard navigation, focus management)

---

## 14. Team

T4SG Hackathon Team — Operation HOPE
