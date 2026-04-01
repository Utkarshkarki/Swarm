# 🏘️ Real Estate Advisory — Multi-Agent AI System

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat-square&logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

**A production-grade multi-agent AI system where five domain-specific experts collaboratively analyze real estate queries through structured two-round debate, dynamic OAISS orchestration, and confidence-weighted synthesis.**

[Architecture](#-architecture) · [Quick Start](#-quick-start) · [API Reference](#-api-reference) · [Configuration](#%EF%B8%8F-configuration) · [Project Structure](#-project-structure)

</div>

---

## 📌 Overview

This is **not a chatbot**. It is a **multi-agent decision system** built on the OAISS (Orchestrated Agent Interaction with Structured Synthesis) pattern.

When a user submits a real estate query, the system:

1. **Classifies** the query into relevant domains (market, legal, financial, construction, investment)
2. **Selects** only the agents relevant to those domains
3. **Runs Round 1** — all selected agents analyze independently in parallel
4. **Runs Round 2 (OAISS loop)** — agents react to each other's output, with dynamic handoffs driven by `HANDOFF_SIGNAL` tokens
5. **Aggregates** all outputs into a single structured JSON result with recommendation, risks, and follow-up questions
6. **Persists** every session to SQLite for debugging and prompt improvement

### The Five Domain Experts

| Agent | Domain | Focus |
|---|---|---|
| 🏠 **Real Estate Broker** | Market | Pricing realism, comparables, negotiation strategy, inventory |
| ⚖️ **Property Lawyer** | Legal | Title issues, contracts, due diligence, zoning, compliance |
| 🏗️ **Developer / Builder** | Construction | Build quality, renovation feasibility, permits, cost realism |
| 🏦 **Banker** | Financial | Affordability, EMI pressure, credit readiness, interest-rate risk |
| 📈 **Property Investor** | Investment | Rental yield, ROI, hold-vs-flip strategy, exit flexibility |

---

## 🏗️ Architecture

```
                    ┌──────────────────────────────────┐
                    │         Streamlit Frontend       |
                    │  • Query input                   │
                    │  • Sidebar profile (budget,      │
                    │    purpose, risk appetite)       │
                    │  • Structured result display     │
                    │  • Agent debate expanders        │
                    │  • Clickable follow-up questions │
                    └──────────────┬───────────────────┘
                                   │  HTTP (POST /analyze)
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend                             │
│                                                                      │
│   POST /analyze                                                      │
│   ├── 1. Load UserProfile          (memory.py → SQLite)              │
│   ├── 2. Classify Query            (classifier.py)                   │
│   │       └─► domains: [market, legal, financial, ...]               │
│   │       └─► agent_ids: [broker, legal, banker, ...]                │
│   │                                                                  │
│   ├── 3. OAISS Orchestrator        (orchestrator.py)                 │
│   │       │                                                          │
│   │       ├── Phase 1 — Parallel Round 1 (asyncio.gather)            │
│   │       │     ├── 🏠 Broker Agent    ──► Round 1 response          |
│   │       │     ├── ⚖️  Legal Agent    ──► Round 1 response         │
│   │       │     ├── 🏦 Banker Agent    ──► Round 1 response         │
│   │       │     ├── 📈 Investor Agent  ──► Round 1 response         │
│   │       │     └── 🏗️  Developer Agent ──► Round 1 response        │
│   │       │           (each call: 90s timeout via asyncio.wait_for)  │
│   │       │                                                          │
│   │       └── Phase 2 — Dynamic OAISS Loop (non-fixed pipeline)      │
│   │             Agent reads ALL prior outputs (enriched context)     │
│   │             Emits HANDOFF_SIGNAL: <target> | <reason>            │
│   │             ├── HANDOFF  → enqueue target agent (front)          │
│   │             ├── CONSENSUS → exit loop immediately                │
│   │             └── max_turns = 10 → forced exit                     │
│   │                                                                  │
│   ├── 4. Aggregator                (aggregator.py)                   │
│   │       └─► Structured JSON: recommendation, risks, insights,      │
│   │           confidence_score, agent_views, follow_up_questions     │
│   │                                                                  │
│   └── 5. Logger                   (logger.py)                        │
│           └─► Persist full session to SQLite                         │
│                                                                      │
│   GET  /history/{username}   ──► past sessions (per user)            │
│   GET  /history              ──► all sessions  (admin)               │
│   POST /profile              ──► upsert user profile                 │
│   GET  /profile/{username}   ──► read user profile                   │
│   GET  /health               ──► { "status": "ok" }                  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │         SQLite  (swarm.db)     | 
              │                                │
              │  ┌─────────────────────────┐   │
              │  │  sessions               │   │
              │  │  ─────────────────────  │   │
              │  │  id          INTEGER PK │   │
              │  │  username    TEXT       │   │
              │  │  query       TEXT       │   │
              │  │  domains_json TEXT      │   │
              │  │  round1_json TEXT       │   │
              │  │  round2_json TEXT       │   │
              │  │  output_json TEXT       │   │
              │  │  created_at  TEXT       │   │
              │  └─────────────────────────┘   │
              │                                │
              │  ┌─────────────────────────┐   │
              │  │  user_profiles          │   │
              │  │  ─────────────────────  │   │
              │  │  username      TEXT PK  │   │
              │  │  profile_json  TEXT     │   │
              │  │  updated_at    TEXT     │   │
              │  └─────────────────────────┘   │
              └────────────────────────────────┘
```

### OAISS — Dynamic Control Flow

The orchestrator is **not a fixed pipeline**. Agents dynamically hand off control at runtime:

```
Agent A responds → HANDOFF_SIGNAL: legal | needs title review
                         ↓
              Legal Agent gets enqueued (front of queue)
                         ↓
Legal Agent responds → HANDOFF_SIGNAL: banker | financing concern
                         ↓
              Banker Agent gets enqueued (if not already done)
                         ↓
Banker Agent → HANDOFF_SIGNAL: consensus | all concerns addressed
                         ↓
              Loop exits → Aggregator runs
```

- Signals are parsed via regex from each agent response
- `CONSENSUS` exits the loop early
- `MAX_TURNS = 10` is the absolute safety cap
- Each agent call has a **90-second timeout** via `asyncio.wait_for`

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- An LLM backend accessible via OpenAI-compatible API:
  - **Local**: [Ollama](https://ollama.ai) (recommended for development)
  - **Cloud**: OpenAI, Together AI, Groq, etc.

### 1. Clone & Install

```bash
git clone https://github.com/your-username/real-estate-advisory.git
cd real-estate-advisory
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# LLM Backend (OpenAI-compatible)
LLM_BASE_URL=http://localhost:11434/v1   # Ollama default
LLM_MODEL=llama3.2                       # or qwen3, mistral, etc.
LLM_API_KEY=ollama                       # use "ollama" for local

# Database
DB_PATH=swarm.db

# Service URLs
BACKEND_URL=http://localhost:8000
AGENT_TIMEOUT=90
```

### 3. Start the Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

Backend will be available at `http://localhost:8000`
Interactive API docs at `http://localhost:8000/docs`

### 4. Start the Frontend

```bash
streamlit run frontend/app.py
```

Frontend will be available at `http://localhost:8501`

---

## 📡 API Reference

### `POST /analyze`

Runs the full multi-agent pipeline for a real estate query.

**Request**
```json
{
  "query": "Should I buy a 2-BHK in Pune for ₹90L as a rental investment?",
  "username": "priya_investor"
}
```

**Response**
```json
{
  "recommendation": "Consider",
  "confidence_score": 7,
  "summary": "The panel sees moderate opportunity with manageable risks...",
  "key_insights": {
    "market": "...",
    "investment": "...",
    "legal": "...",
    "financial": "...",
    "construction": "..."
  },
  "risks": ["High stamp duty in Maharashtra", "..."],
  "agent_views": [
    {
      "agent": "Real Estate Broker",
      "key_points": ["..."],
      "confidence": "high",
      "dissents_from": ["Property Investor"]
    }
  ],
  "follow_up_questions": [
    "What is the current rental yield for similar properties in Baner?",
    "..."
  ],
  "active_domains": ["market", "investment", "legal", "financial"],
  "agent_rounds": [...]
}
```

| Field | Type | Description |
|---|---|---|
| `recommendation` | `Buy \| Avoid \| Consider \| Needs more info` | Panel's verdict |
| `confidence_score` | `int` (1–10) | Aggregate confidence |
| `summary` | `string` | 2–3 sentence executive summary |
| `key_insights` | `object` | Per-domain insight |
| `risks` | `string[]` | All flagged risks |
| `agent_views` | `object[]` | Per-agent summary with dissents |
| `follow_up_questions` | `string[]` | Clickable follow-up prompts |
| `agent_rounds` | `object[]` | Full Round 1 + Round 2 text per agent |

---

### `POST /profile`

Create or update a user's persistent memory profile.

**Request**
```json
{
  "username": "priya_investor",
  "budget_min": 5000000,
  "budget_max": 9000000,
  "purpose": "investment",
  "risk_appetite": "medium",
  "timeline_months": 6,
  "location_preference": ["Pune", "Bangalore"],
  "preferred_property_type": "apartment",
  "existing_properties": 1,
  "citizenship_status": "Indian",
  "loan_eligibility_known": true
}
```

**Response**
```json
{ "status": "ok", "username": "priya_investor" }
```

---

### `GET /history`

Returns all sessions across all users (admin view).

**Query params:** `?limit=50` (default)

---

### `GET /history/{username}`

Returns past sessions for a specific user.

**Query params:** `?limit=20` (default)

---

### `GET /profile/{username}`

Returns the stored profile for a user.

---

### `GET /health`

```json
{ "status": "ok", "version": "1.0.0" }
```

---

## ⚙️ Configuration

All configuration is via environment variables (`.env` file):

| Variable | Default | Description |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible LLM endpoint |
| `LLM_MODEL` | `llama3.2` | Model name to use for all agents |
| `LLM_API_KEY` | `ollama` | API key (`ollama` for local Ollama) |
| `DB_PATH` | `swarm.db` | SQLite database file path |
| `BACKEND_URL` | `http://localhost:8000` | FastAPI server URL (used by frontend) |
| `AGENT_TIMEOUT` | `90` | Per-agent async timeout in seconds |

### Recommended Models

| Use Case | Model | Why |
|---|---|---|
| **Best MVP** | `Qwen3-32B` | Strong reasoning, 128K context, supports thinking/non-thinking modes |
| **Lower latency** | `Mistral Small 3.2` | 24B, Apache 2.0, excellent instruction following |
| **Strongest reasoning** | `DeepSeek-R1-Distill-Qwen-32B` | Best for legal/financial/risk debate |
| **Stable fallback** | `Qwen2.5-32B-Instruct` | Reliable, widely used, long prompts |

---

## 📁 Project Structure

```
real-estate-advisory/
│
├── backend/
│   ├── main.py              # FastAPI app, all endpoints
│   ├── orchestrator.py      # OAISS dynamic orchestration engine
│   ├── debate.py            # Two-round debate runner
│   ├── aggregator.py        # Structured output synthesiser
│   ├── classifier.py        # Query → domain → agent selection
│   ├── memory.py            # User profile persistence (SQLite)
│   ├── logger.py            # Session logging (SQLite)
│   ├── database.py          # DB schema initialisation
│   ├── confidence.py        # Per-agent confidence scoring
│   ├── models.py            # Pydantic data models
│   ├── config.py            # Environment-based settings
│   └── agents/
│       ├── base.py          # BaseAgent: round1(), round2(), LLM call
│       ├── broker.py        # Real Estate Broker agent
│       ├── legal.py         # Property Lawyer agent
│       ├── developer.py     # Developer / Builder agent
│       ├── banker.py        # Banker & Mortgage Expert agent
│       └── investor.py      # Property Investor agent
│
├── frontend/
│   └── app.py               # Streamlit UI (login, sidebar, results, history)
│
├── app.py                   # Legacy standalone Streamlit prototype
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── .gitignore
└── Readme.md
```

---

## 🔬 Key Design Decisions

### Why OAISS over a fixed pipeline?

A fixed pipeline (Agent A → B → C) forces a predetermined reasoning order. OAISS allows agents to signal where expertise is needed next. A broker might detect a title dispute mid-analysis and hand off to the legal agent before the investor weighs in — exactly how a real advisory panel operates.

### Why SQLite for MVP?

Every agent response (Round 1 and Round 2) is stored verbatim alongside the final output. This makes it possible to:
- Diff what changed between rounds to see debate impact
- Identify which agent prompted hallucinations
- Replay sessions to test prompt changes without re-calling the LLM

### Why Pydantic v2 for output?

The aggregator's output schema is enforced at the type level via `AnalysisResult`. If the LLM returns a malformed JSON, Pydantic raises a validation error early rather than silently passing garbage to the frontend.

---

## 🧪 Development

### Running tests

```bash
pytest tests/ -v
```

### Linting

```bash
ruff check .
```

### Type checking

```bash
mypy backend/
```

---

## ⚠️ Disclaimer

This system is a **decision-support tool**, not a licensed advisory service. All outputs — legal, financial, construction, and market — must be independently verified by qualified professionals before acting on them. The system intentionally surfaces disagreement, missing data, and risk rather than projecting false certainty.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
