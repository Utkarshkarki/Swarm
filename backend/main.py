from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .aggregator import aggregate
from .agents.banker import BankerAgent
from .agents.broker import BrokerAgent
from .agents.developer import DeveloperAgent
from .agents.investor import InvestorAgent
from .agents.legal import LegalAgent
from .classifier import classify_query, get_active_agent_ids
from .database import init_db
from .debate import run_debate
from .logger import get_all_history, get_history, log_session
from .memory import get_profile, save_profile
from .models import AnalysisResult, AnalyzeRequest, ProfileUpdateRequest, UserProfile

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

ALL_AGENTS = {
    "broker": BrokerAgent(),
    "investor": InvestorAgent(),
    "legal": LegalAgent(),
    "developer": DeveloperAgent(),
    "banker": BankerAgent(),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialised — ready.")
    yield


app = FastAPI(
    title="Real Estate Advisory API",
    description="Multi-Agent Real Estate Advisory System with Two-Round Debate Engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/analyze", response_model=AnalysisResult)
async def analyze(request: AnalyzeRequest) -> AnalysisResult:
    """Full pipeline: classify → debate (R1+R2) → confidence → aggregate → log."""

    # 1. Load persistent user profile
    profile = await get_profile(request.username)

    # 2. Classify query → active domains + agents
    domains = classify_query(request.query)
    agent_ids = get_active_agent_ids(domains)
    active_agents = [ALL_AGENTS[aid] for aid in agent_ids if aid in ALL_AGENTS]

    if not active_agents:
        active_agents = list(ALL_AGENTS.values())
        domains = ["market", "investment", "legal", "financial", "construction"]

    logger.info(
        "Query='%s...' | domains=%s | agents=%s",
        request.query[:60],
        domains,
        [a.agent_name for a in active_agents],
    )

    # 3. Two-round debate (async parallel per round)
    agent_rounds = await run_debate(active_agents, request.query, profile)

    # 4. Aggregate → strict JSON output
    result = await aggregate(request.query, profile, agent_rounds)
    result.active_domains = domains
    result.agent_rounds = agent_rounds

    # 5. Persist session log
    await log_session(
        username=request.username,
        query=request.query,
        domains=domains,
        round1={ar.agent_name: ar.round1 for ar in agent_rounds},
        round2={ar.agent_name: ar.round2 for ar in agent_rounds},
        output=result.model_dump(exclude={"agent_rounds"}),
    )

    return result


@app.post("/profile")
async def update_profile(request: ProfileUpdateRequest) -> Dict[str, str]:
    """Create or update a user's persistent memory profile."""
    await save_profile(UserProfile(**request.model_dump()))
    return {"status": "ok", "username": request.username}


@app.get("/profile/{username}")
async def get_user_profile(username: str) -> UserProfile:
    profile = await get_profile(username)
    return profile


@app.get("/history/{username}")
async def user_history(username: str, limit: int = 20) -> Dict[str, Any]:
    sessions = await get_history(username, limit)
    return {"username": username, "sessions": sessions}


@app.get("/history")
async def all_history(limit: int = 50) -> Dict[str, Any]:
    sessions = await get_all_history(limit)
    return {"sessions": sessions}
