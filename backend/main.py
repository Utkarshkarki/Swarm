import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .aggregator import aggregate
from .agents.banker import BankerAgent
from .agents.broker import BrokerAgent
from .agents.developer import DeveloperAgent
from .agents.investor import InvestorAgent
from .agents.legal import LegalAgent
from .cache import semantic_cache
from .classifier import classify_query, get_active_agent_ids
from .database import init_db
from .orchestrator import OAISSOrchestrator
from .logger import get_all_history, get_history, log_session
from .memory import get_profile, save_profile
from .models import AgentRoundOutput, AnalysisResult, AnalyzeRequest, ProfileUpdateRequest, UserProfile

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


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@app.post("/analyze")
async def analyze(payload: AnalyzeRequest, http_request: Request):
    """
    Streaming SSE endpoint:
    1. Check Semantic Cache (similarity >= 0.95)
    2. Stream live Round 1 & Round 2 agent thoughts and handoffs
    3. Synthesize structured AnalysisResult and persist to cache & SQLite
    """

    async def event_generator():
        async def emit(event: str, data: Any) -> str:
            if await http_request.is_disconnected():
                raise asyncio.CancelledError
            return _sse(event, data)

        try:
            # 1. Semantic Cache check
            cached_result, similarity = await semantic_cache.lookup(payload.query)
            if cached_result is not None and similarity is not None:
                cached_payload = AnalysisResult.model_validate(cached_result).model_dump(mode="json")
                yield await emit(
                    "cache_hit",
                    {
                        "similarity": similarity,
                        "message": f"Instant Semantic Cache Hit ({similarity * 100:.1f}% similarity)",
                    },
                )
                yield await emit("final_result", cached_payload)
                return

            # 2. Load persistent user profile
            profile = await get_profile(payload.username)

            # 3. Classify query → active domains + agents
            domains = classify_query(payload.query)
            agent_ids = get_active_agent_ids(domains)
            active_agents = [ALL_AGENTS[aid] for aid in agent_ids if aid in ALL_AGENTS]

            if not active_agents:
                active_agents = list(ALL_AGENTS.values())
                domains = ["market", "investment", "legal", "financial", "construction"]

            yield await emit(
                "classification",
                {
                    "domains": domains,
                    "agents": [a.agent_name for a in active_agents],
                    "message": f"Classified domains: {domains}",
                },
            )

            # 4. OAISS dynamic streaming orchestration
            orchestrator = OAISSOrchestrator(ALL_AGENTS)
            agent_rounds_data: List[Dict[str, Any]] = []
            prompt_tokens = 0
            completion_tokens = 0
            total_cost = 0.0

            async for event in orchestrator.run_stream(payload.query, profile, active_agents):
                if event.get("event") == "orchestration_complete":
                    metrics_payload = event.get("data", {})
                    agent_rounds_data = metrics_payload.get("agent_rounds", [])
                    prompt_tokens = metrics_payload.get("prompt_tokens", 0)
                    completion_tokens = metrics_payload.get("completion_tokens", 0)
                    total_cost = metrics_payload.get("total_cost", 0.0)
                yield await emit(event["event"], event.get("data", {}))

            # Reconstruct typed AgentRoundOutput objects for aggregation
            agent_rounds = [AgentRoundOutput(**ar) for ar in agent_rounds_data]

            # 5. Aggregate → strict JSON output
            yield await emit(
                "aggregator_start",
                {
                    "message": "Senior Advisor is synthesizing expert consensus and resolving conflicts...",
                },
            )
            result = await aggregate(payload.query, profile, agent_rounds)
            result.active_domains = domains
            result.agent_rounds = agent_rounds

            final_dict = result.model_dump(mode="json")

            # 6. Save to Semantic Cache
            await semantic_cache.set(payload.query, final_dict)

            # 7. Persist session log to SQLite
            await log_session(
                username=payload.username,
                query=payload.query,
                domains=domains,
                round1={ar.agent_name: ar.round1 for ar in agent_rounds},
                round2={ar.agent_name: ar.round2 for ar in agent_rounds},
                output=result.model_dump(exclude={"agent_rounds"}),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_cost=total_cost,
            )

            # 8. Emit final complete payload
            yield await emit("final_result", final_dict)

        except asyncio.CancelledError:
            logger.info("SSE client disconnected before analysis completed.")
            return
        except Exception as exc:
            logger.exception("SSE stream error: %s", exc)
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )




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
