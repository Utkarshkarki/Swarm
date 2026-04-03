from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

from .agents.base import BaseAgent
from .confidence import compute_confidence
from .models import AgentRoundOutput, UserProfile

logger = logging.getLogger(__name__)

# Debating agents

async def _round1(
    agents: List[BaseAgent], query: str, profile: Optional[UserProfile]
) -> Dict[str, str]:
    """All agents respond independently in parallel."""

    async def one(agent: BaseAgent) -> Tuple[str, str]:
        try:
            return agent.agent_name, await agent.round1(query, profile)
        except asyncio.TimeoutError:
            logger.warning("%s timed out in Round 1", agent.agent_name)
            return agent.agent_name, f"[{agent.agent_name} timed out]"
        except Exception as exc:
            logger.error("%s failed in Round 1: %s", agent.agent_name, exc)
            return agent.agent_name, f"[{agent.agent_name} error: {exc}]"

    pairs = await asyncio.gather(*[one(a) for a in agents])
    return dict(pairs)


async def _round2(
    agents: List[BaseAgent],
    query: str,
    profile: Optional[UserProfile],
    round1_results: Dict[str, str],
) -> Dict[str, str]:
    """Each agent reads ALL other Round 1 responses and reacts."""

    async def one(agent: BaseAgent) -> Tuple[str, str]:
        others = {n: t for n, t in round1_results.items() if n != agent.agent_name}
        try:
            return agent.agent_name, await agent.round2(query, profile, others)
        except asyncio.TimeoutError:
            logger.warning("%s timed out in Round 2", agent.agent_name)
            return agent.agent_name, f"[{agent.agent_name} timed out in Round 2]"
        except Exception as exc:
            logger.error("%s failed in Round 2: %s", agent.agent_name, exc)
            return agent.agent_name, f"[{agent.agent_name} error in Round 2: {exc}]"

    pairs = await asyncio.gather(*[one(a) for a in agents])
    return dict(pairs)


async def run_debate(
    agents: List[BaseAgent],
    query: str,
    profile: Optional[UserProfile],
) -> List[AgentRoundOutput]:
    """Full two-round debate → list of per-agent round outputs with confidence."""
    r1 = await _round1(agents, query, profile)
    r2 = await _round2(agents, query, profile, r1)

    outputs: List[AgentRoundOutput] = []
    for agent in agents:
        t1 = r1.get(agent.agent_name, "")
        t2 = r2.get(agent.agent_name, "")
        outputs.append(
            AgentRoundOutput(
                agent_id=agent.agent_id,
                agent_name=agent.agent_name,
                emoji=agent.emoji,
                round1=t1,
                round2=t2,
                confidence=compute_confidence(t1 + " " + t2),
            )
        )
    return outputs
