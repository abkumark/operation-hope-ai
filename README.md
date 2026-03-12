# Operation HOPE AI

AI-powered support ticket classification, routing, and response generation for Operation HOPE's help desk.

## Overview

Operation HOPE handles ~30 support tickets per day with a 48-hour average response time. Most tickets are repetitive — password resets, login issues, course navigation, and similar inquiries.

**HOPE AI** uses Azure OpenAI (GPT) combined with Retrieval-Augmented Generation (RAG) over a real Knowledge Base to:

- **Auto-classify** tickets into 21+ categories with confidence scoring
- **Auto-generate** contextual responses grounded in KB articles (English + Spanish)
- **Route intelligently** based on confidence — auto-draft, suggest+review, or escalate to human
- **Provide analytics** — trend detection, knowledge gaps, training alerts, engineer performance

Target: reduce response time from 48 hours to minutes for 60-70% of tickets while maintaining human oversight for complex or sensitive cases.

## Architecture

```
Ticket Input → Classify → Route → Generate Response (RAG) → Create Approval
                                    → Find Similar Tickets
                                    → Generate AI Resolution
                                    → Persist to SQLite
                                    → Send Email Notification
```

| Component        | Technology                         |
|------------------|------------------------------------|
| Backend          | Python 3.11+, FastAPI              |
| LLM              | Azure OpenAI (with fallback chain) |
| RAG Vector Store | ChromaDB + sentence-transformers   |
| Database         | SQLite                             |
| Frontend         | Vanilla HTML/CSS/JS + Chart.js     |
| Integration      | Dynamics 365 REST API, Power Automate |

See [APPROACH.md](APPROACH.md) for the full technical architecture document.

## Prerequisites

- **Python 3.11+**
- pip or uv

## Quick Start

### 1. Install

```bash
cd operation-hope-ai
pip install -e .
```

For development (includes pytest, ruff):

```bash
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Azure OpenAI credentials
```

Required environment variables for AI features:

| Variable | Description |
|----------|-------------|
| `LLM_PROVIDER` | `azure`, `openai`, or `ollama` |
| `AZURE_OPENAI_ENDPOINT` | Your Azure OpenAI resource endpoint |
| `AZURE_OPENAI_KEY` | Your Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name for chat completions |
| `AZURE_OPENAI_API_VERSION` | API version (default: `2024-12-01-preview`) |

Optional: SMTP settings for email notifications, Dynamics 365 credentials for CRM integration.

### 3. Run

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) for the branded web dashboard.

**Demo credentials:**
| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Admin (full access) |
| `torri` / `danita` / `shonda` / `abhishek` / `praveen` | `Welcome123` | Engineer (work queue) |

## Project Structure

```
operation-hope-ai/
├── src/
│   ├── api/               # FastAPI app and 37 REST endpoints
│   ├── core/              # AI classification, routing, response, resolution
│   ├── workflow/          # Ticket pipeline, approval state machine, escalation
│   ├── knowledge/         # RAG pipeline, ChromaDB vector store, KB ingestion
│   ├── llm/               # LLM provider abstraction (Azure/OpenAI/Ollama/Fallback)
│   ├── analytics/         # Trend engine, metrics, reports
│   ├── integration/       # Dynamics 365 client + mock, Power Automate webhook
│   ├── notifications/     # SMTP email service
│   └── storage/           # SQLite schema, migrations, CRUD
├── config/
│   ├── settings.py        # Pydantic settings from .env
│   ├── categories.py      # 21-category ticket taxonomy
│   └── routing_rules.py   # Routing rule definitions
├── templates/             # Jinja2 HTML templates (single-page app)
├── static/                # CSS and JavaScript assets
├── data/
│   ├── knowledge_base/    # 24+ KB articles (EN + ES)
│   ├── sample_tickets/    # Sample ticket CSV
│   └── synthetic/         # Ticket generator script
├── tests/                 # pytest test suite (79 tests)
├── APPROACH.md            # Full architecture document
├── pyproject.toml         # Dependencies and build config
└── .env.example           # Environment variable template
```

## Running Tests

Tests mock LLM calls — no API key needed:

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

## API Endpoints

All routes are under `/api/v1/`. Key groups:

| Category | Key Endpoints |
|----------|--------------|
| Auth | `POST /auth/login` |
| Tickets | submit, process, list, get, delete, patch, approve-close, assign |
| Knowledge Base | ingest, status, articles, search |
| Analytics | summary, trends |
| Approvals | list, detail, history, approve, reject, reroute |
| Dynamics 365 | create, list, get, update cases |
| Configuration | expertise mapping, engineer list |

## Confidence-Based Routing

| Confidence | Action | Description |
|-----------|--------|-------------|
| ≥ 85% + auto-resolvable | `AUTO_RESOLVE` | AI draft created, queued for approval |
| 60–85% | `SUGGESTED_REVIEW` | Agent reviews AI suggestion before sending |
| < 60% | `ROUTE_TO_HUMAN` | Fully manual handling |
| HR keywords detected | `HR_EXCLUDED` | Always routed to human |
| Urgency/time rules | `ESCALATED` | Priority escalation |

## Sample Data

- **Sample tickets**: `data/sample_tickets/sample_tickets.csv` — 20 realistic tickets
- **Synthetic generator**: `python data/synthetic/generate_tickets.py --count 50`

## Linting

```bash
ruff check src/ config/ tests/
```

## License

MIT
