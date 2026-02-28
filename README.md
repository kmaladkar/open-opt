# Open Opt

**Wealthsimple-style family finance app** with household accounts, goals, transaction patterns, and AI-powered recommendations. Built for Canadian rules (TFSA, RRSP, FHSA, RESP/CESG) and designed to feel human and actionable.

---

## What it does

- **Households & members** — Families with parents and children; each member can log in and see shared household data.
- **Accounts** — Chequing, savings, TFSA, RRSP, FHSA, RESP, non-registered; balances in cents; optional per-member ownership or joint.
- **Goals** — Emergency, education, retirement, first home; target amounts and dates.
- **Transactions** — Stored in SQLite with pattern (recurring/one-off) and category; used for pay-pattern analysis and household income/expense rollups.
- **Recommendations** — Question-driven narrative + 5-year projection charts. Uses either **Cursor API** or **OpenAI** when configured; otherwise a **question-aware rule-based fallback**.
- **Dashboard** — Single-page UI: login, total across accounts, households, goals, “Get recommendations” (custom question + chart), “Recommended for you” (auto list + charts), and account tables with cumulative totals.

---

## Tech stack

| Layer        | Choice |
|-------------|--------|
| Backend     | Python 3.11+, FastAPI |
| DB          | SQLite (SQLAlchemy 2, `app.db`) |
| Auth        | JWT (python-jose), bcrypt |
| LLM         | OpenAI-compatible API (OpenAI or Cursor); optional keys |
| Frontend    | Vanilla JS, Chart.js, static HTML/CSS |
| Package mgmt| uv (recommended) or pip |

---

## Project structure

```
open-opt/
├── app/
│   ├── api/              # REST routes
│   │   ├── accounts.py   # Accounts CRUD, transaction_patterns
│   │   ├── agent_help.py # Help topics for agents
│   │   ├── auth.py      # Register, login (JWT)
│   │   ├── goals.py     # Goals CRUD
│   │   ├── health.py    # Health + LLM provider status
│   │   ├── households.py# Households CRUD, members, transaction_patterns
│   │   └── recommendations.py  # POST recommendations, GET /auto
│   ├── agents/
│   │   ├── help.py      # Routing, Canadian rules, synthesis guidance
│   │   ├── recommendation_agent.py  # Tools + context → visualization
│   │   └── subagents/
│   │       ├── banking.py      # Accounts, balances, transactions
│   │       ├── family.py       # Members, goals, RESP/CESG
│   │       ├── investing.py   # Contribution room, tax loss harvesting
│   │       ├── research.py    # Canadian rules (TFSA/RRSP/FHSA/RESP)
│   │       └── visualization.py # LLM call, chart specs, fallback
│   ├── core/
│   │   ├── config.py    # Settings (DB, auth, LLM provider/keys)
│   │   └── database.py # Engine, session, init_db
│   ├── data/
│   │   ├── canadian_rules.py   # Limits, CESG, FHSA, superficial loss
│   │   ├── rate_assumptions.py# Projection rates (savings, growth)
│   │   ├── recommendation_prompts.py
│   │   └── wealthsimple_products.py
│   ├── models/         # SQLAlchemy (User, Household, HouseholdMember, Account, Goal, Transaction)
│   ├── schemas/        # Pydantic request/response
│   ├── services/
│   │   ├── transaction_patterns.py  # Per-account and household rollups
│   │   └── open_banking.py         # Optional adapter
│   ├── static/         # index.html, styles.css, app.js
│   └── main.py         # FastAPI app, lifespan, routes
├── scripts/
│   └── seed_mock_data.py   # Single mock household (2 parents, 2 children)
├── tests/
│   ├── conftest.py     # In-memory SQLite, client
│   ├── test_health.py
│   ├── test_recommendations.py
│   ├── test_recommendation_visualization.py
│   ├── test_math_consistency.py
│   └── ...
├── docs/
│   └── MOCK_DATA.md    # (Legacy fixture notes; current seed is single family)
├── .env.example
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Prerequisites

- **Python 3.11+**
- **uv** (recommended): `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## Setup

1. **Clone and enter the repo**

   ```bash
   cd open-opt
   ```

2. **Create a virtualenv and install dependencies**

   ```bash
   uv sync
   ```

   Or with pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

3. **Environment variables**

   Copy the example and edit as needed:

   ```bash
   cp .env.example .env
   ```

   | Variable | Description | Default |
   |----------|-------------|---------|
   | `DATABASE_URL` | SQLite path | `sqlite:///./app.db` |
   | `SECRET_KEY` | JWT signing | Change in production |
   | `LLM_PROVIDER` | `openai` or `cursor` | `cursor` |
   | `LLM_MODEL` | Model name (OpenAI path) | `gpt-4o-mini` |
   | `OPENAI_API_KEY` | OpenAI key (if provider=openai) | — |
   | `CURSOR_API_KEY` | Cursor API key (if provider=cursor) | — |
   | `CURSOR_BASE_URL` | Cursor API base | `https://api.cursor.com/v1` |
   | `CURSOR_MODEL` | Model for Cursor | `gpt-4o-mini` |

   If no LLM key is set, the app uses a **question-aware fallback** (no external API calls).

---

## Run the app

```bash
uv run uvicorn app.main:app --reload
```

- **API:** http://127.0.0.1:8000  
- **Docs:** http://127.0.0.1:8000/docs  
- **Health:** http://127.0.0.1:8000/api/health  
- **Dashboard:** http://127.0.0.1:8000/app  

---

## Mock data (single household)

The seed script creates **one family**: **Mock Alvarez Family** (2 parents, 2 children), with multiple accounts and a dense transaction history.

**Seed the database:**

```bash
uv run python scripts/seed_mock_data.py
```

**List logins (no DB write):**

```bash
uv run python scripts/seed_mock_data.py --print-logins
```

**Mock logins (password for all: `mock123`):**

| Role   | Email |
|--------|--------|
| Parent 1 | `mock_alvarez_family_0@example.com` |
| Parent 2 | `mock_alvarez_family_1@example.com` |
| Child 1  | `mock_alvarez_family_2@example.com` |
| Child 2   | `mock_alvarez_family_3@example.com` |

Re-running the seed **replaces** existing mock households and mock users, then re-seeds.

---

## API overview

All authenticated routes expect:

```http
Authorization: Bearer <access_token>
```

Obtain a token via `POST /api/auth/login` with `email` and `password`.

### Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register (email, password) |
| POST | `/api/auth/login` | Login → `{ "access_token": "..." }` |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | `status`, `database`, `llm` (provider, configured) |

### Households

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/households` | List households for current user |
| POST | `/api/households` | Create household |
| GET | `/api/households/{id}` | Get one |
| PATCH | `/api/households/{id}` | Update |
| DELETE | `/api/households/{id}` | Delete |
| GET | `/api/households/{id}/members` | List members |
| GET | `/api/households/{id}/transaction_patterns?days_back=90` | Household pay patterns |

### Accounts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/accounts` | List accounts (optional `?household_id=` to filter) |
| POST | `/api/accounts` | Create account |
| GET | `/api/accounts/{id}` | Get one |
| GET | `/api/accounts/{id}/transaction_patterns?days_back=90` | Account pay patterns |

### Goals

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/goals` | List goals (optional `?household_id=` to filter) |
| POST | `/api/goals` | Create goal |
| GET | `/api/goals/{id}` | Get one |
| PATCH | `/api/goals/{id}` | Update |
| DELETE | `/api/goals/{id}` | Delete |

### Recommendations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/recommendations` | Body: `question`, `household_id?`, `include_visualization`. Returns narrative + optional `chart_spec` (question-driven 5-year projection). |
| GET | `/api/recommendations/auto` | Auto list of 5+ recommendations + one chart; used by dashboard “Recommended for you”. |

### Agent help

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/help/topics` | List help topic names |
| GET | `/api/help?topic=...` | Get guidance (routing, canadian_rules, synthesis, etc.) |

---

## LLM integration (Cursor vs OpenAI)

- **Default provider:** `cursor` (see `LLM_PROVIDER` in config).
- **Cursor:** Set `CURSOR_API_KEY` (and optionally `CURSOR_BASE_URL`, `CURSOR_MODEL`). Requests go to the Cursor API.
- **OpenAI:** Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY`. Requests use OpenAI.
- **No key:** App uses the built-in **question-aware fallback** (no external API). Responses and charts still vary by question (RESP vs TFSA vs RRSP, etc.).

**Health** (`GET /api/health`) includes `llm.provider` and `llm.configured` so you can confirm which path is active. Startup logs also report `llm_provider` and `api_key_configured`.

---

## Canadian rules and recommendation logic

- **Limits** (in `app/data/canadian_rules.py`): TFSA annual, RRSP cap, FHSA annual/lifetime, RESP CESG/CLB, income thresholds for additional CESG, superficial loss 61-day rule.
- **Contribution room** (`app/agents/subagents/investing.py`): Household-level TFSA/RRSP/FHSA room; scales by number of eligible adults (parents) in the household.
- **Charts:** “Get recommendations” and each auto-recommendation item use strategy-specific assumptions (RESP+CESG, TFSA, RRSP, FHSA, cash optimization, etc.), so the 5-year projection and `rates_note` vary by question/topic.

---

## Frontend (dashboard)

- **Entry:** http://127.0.0.1:8000/app  
- **Login** with a mock or registered user; then:
  - Total across all accounts (formatted with commas)
  - Household list and member counts
  - “Get recommendations”: text area + submit → narrative + question-driven chart
  - Account tables per household (columns for each member + household/joint, balance, cumulative)
  - Goals list
  - “Recommended for you”: auto list with per-item charts and metrics

Charts are built with Chart.js; currency formatting uses `toLocaleString` for comma-separated amounts.

---

## Tests

```bash
uv run pytest
```

- **Health:** `/api/health` returns ok and includes `llm`.
- **Recommendations:** Auth required for POST; fallback and visualization tests.
- **Recommendation visualization:** List format, chart spec shape, question-driven chart difference, fallback narrative varies by question.
- **Math consistency:** Projection series, household transaction rollups, contribution room non-negativity, multi-adult scaling.

Tests use an in-memory SQLite database (see `tests/conftest.py`).

---

## Configuration reference

| Setting | Env var | Default | Notes |
|--------|---------|--------|-------|
| Database | `DATABASE_URL` | `sqlite:///./app.db` | SQLite path |
| JWT secret | `SECRET_KEY` | `change-me-in-production` | Must change in production |
| LLM provider | `LLM_PROVIDER` | `cursor` | `openai` or `cursor` |
| OpenAI key | `OPENAI_API_KEY` | — | Used when provider=openai |
| Cursor key | `CURSOR_API_KEY` | — | Used when provider=cursor |
| Cursor base URL | `CURSOR_BASE_URL` | `https://api.cursor.com/v1` | Override if needed |
| Cursor model | `CURSOR_MODEL` | `gpt-4o-mini` | Model name for Cursor |
| Langfuse | `LANGFUSE_*` | — | Optional observability |

---

## License

See repository for license information.
