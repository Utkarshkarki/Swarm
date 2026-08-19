"""
OAISS Orchestrator — Orchestrated Agent Interaction with Structured Synthesis

Dynamic flow (NOT a fixed pipeline):
  Phase 1 → Round 1: Initial agents respond independently (parallel)
  Phase 2 → OAISS loop:
      - Orchestrator reads HANDOFF_SIGNAL from each response
      - Routes to the signalled agent with enriched context
      - Agent reads ALL previous outputs and adds only NEW insights
      - Loop exits when: CONSENSUS signal | max_turns reached | queue empty
  Phase 3 → Aggregator synthesises final structured output
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from langfuse.decorators import observe



from .agents.base import BaseAgent
from .confidence import compute_confidence
from .models import AgentRoundOutput, UserProfile


logger = logging.getLogger(__name__)

MAX_TURNS = 10  # absolute safety cap
STREAM_HEARTBEAT_SECONDS = 15.0

#  Signal 

_SIGNAL_RE = re.compile(r"HANDOFF_SIGNAL:\s*([A-Z_]+)\s*\|\s*(.*)", re.IGNORECASE)

# maps anything the LLM might write → canonical agent_id
# This  is normalization layer
_ALIAS: Dict[str, Optional[str]] = {
    "legal": "legal", "legal_agent": "legal",
    "broker": "broker", "broker_agent": "broker",
    "investor": "investor", "investor_agent": "investor",
    "developer": "developer", "developer_agent": "developer",
    "banker": "banker", "banker_agent": "banker",
    "none": None, "done": None, "complete": None, "finished": None,
    "consensus": None, "ready": None,
}


@dataclass
class Signal:
    kind: str                    # "HANDOFF" | "CONSENSUS" | "NONE"
    target: Optional[str] = None  # agent_id
    reason: str = ""


def _parse_signal(text: str) -> Signal:
    m = _SIGNAL_RE.search(text)
    if not m:
        return Signal(kind="NONE")
    raw = m.group(1).lower().strip()
    reason = m.group(2).strip()
    if raw in ("consensus", "ready"):
        return Signal(kind="CONSENSUS", reason=reason)
    agent_id = _ALIAS.get(raw)
    if agent_id:
        return Signal(kind="HANDOFF", target=agent_id, reason=reason)
    return Signal(kind="NONE", reason=reason)


def _strip_signal(text: str) -> str:
    """Remove the HANDOFF_SIGNAL line so it doesn't appear in the UI."""
    return _SIGNAL_RE.sub("", text).strip()


# Turn record 
# Stores one complete step of the conversation so the system can track,
# Debug, and understand the entire multi-agent interaction.
@dataclass
class OAISSTurn:
    number: int
    agent_id: str
    agent_name: str
    response: str
    signal: Signal
    is_round1: bool = False


#  Orchestrator 

class OAISSOrchestrator:
    """
    OAISS dynamic agent orchestrator.

    Agents are called sequentially after Round 1, each receiving the
    full enriched context of all previous turns. An agent can hand off
    control to any other agent by emitting a HANDOFF_SIGNAL. The loop
    terminates when consensus is reached or max_turns is exhausted.
    """

    def __init__(self, all_agents: Dict[str, BaseAgent], max_turns: int = MAX_TURNS):
        self.all_agents = all_agents
        self.max_turns = max_turns

    # Internal helpers 

    async def _safe_round1(
        self, agent: BaseAgent, query: str, profile: Optional[UserProfile]
    ) -> Tuple[str, Signal, int, int, float]:
        try:
            raw, p_tokens, c_tokens, cost = await asyncio.wait_for(
                agent.round1(query, profile), timeout=90
            )
            return _strip_signal(raw), _parse_signal(raw), p_tokens, c_tokens, cost
        except asyncio.TimeoutError:
            logger.warning("OAISS R1 timeout: %s", agent.agent_name)
            return f"[{agent.agent_name} timed out in Round 1]", Signal(kind="NONE"), 0, 0, 0.0
        except Exception as exc:
            logger.error("OAISS R1 error (%s): %s", agent.agent_name, exc)
            return f"[{agent.agent_name} error: {exc}]", Signal(kind="NONE"), 0, 0, 0.0

    async def _safe_dynamic(
        self,
        agent: BaseAgent,
        query: str,
        profile: Optional[UserProfile],
        context: Dict[str, str],
    ) -> Tuple[str, Signal, int, int, float]:
        """Dynamic turn — agent reads all previous outputs and reacts."""
        try:
            # Build others context (exclude own previous responses)
            others = {n: t for n, t in context.items() if n != agent.agent_name}
            raw, p_tokens, c_tokens, cost = await asyncio.wait_for(
                agent.round2(query, profile, others), timeout=90
            )
            return _strip_signal(raw), _parse_signal(raw), p_tokens, c_tokens, cost
        except asyncio.TimeoutError:
            logger.warning("OAISS dynamic timeout: %s", agent.agent_name)
            return f"[{agent.agent_name} timed out]", Signal(kind="NONE"), 0, 0, 0.0
        except Exception as exc:
            logger.error("OAISS dynamic error (%s): %s", agent.agent_name, exc)
            return f"[{agent.agent_name} error: {exc}]", Signal(kind="NONE"), 0, 0, 0.0

    def _enqueue_if_new(
        self,
        target_id: str,
        queue: List[BaseAgent],
        done: set[str],
    ) -> bool:
        """Add agent to front of queue only if not already done."""
        agent = self.all_agents.get(target_id)
        if agent and target_id not in done and agent not in queue:
            queue.insert(0, agent)
            return True
        return False

    #  Main orchestration loop 

    @observe()
    async def run(
        self,
        query: str,
        profile: Optional[UserProfile],
        initial_agents: List[BaseAgent],
    ) -> Tuple[List[AgentRoundOutput], int, int, float]:
        """
        Full OAISS run. Returns (AgentRoundOutput list, total_prompt_tokens, total_completion_tokens, total_cost).
        """
        context: Dict[str, str] = {}          # agent_name → latest response text
        round1_map: Dict[str, str] = {}       # agent_name → Round 1 text
        round2_map: Dict[str, str] = {}       # agent_name → latest dynamic text
        turns: List[OAISSTurn] = []
        done: set[str] = set()
        turn_n = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cost = 0.0

        # Phase 1: Round 1 (parallel, independent) 
        logger.info(
            "OAISS Phase 1 — Round 1 (%d agents): %s",
            len(initial_agents),
            [a.agent_name for a in initial_agents],
        )

        r1_coros = [self._safe_round1(a, query, profile) for a in initial_agents]
        r1_results = await asyncio.gather(*r1_coros)

        dynamic_queue: List[BaseAgent] = []

        for agent, (response, signal, p_tokens, c_tokens, cost) in zip(initial_agents, r1_results):
            turn_n += 1
            total_prompt_tokens += p_tokens
            total_completion_tokens += c_tokens
            total_cost += cost
            round1_map[agent.agent_name] = response
            context[agent.agent_name] = response
            done.add(agent.agent_id)
            turns.append(OAISSTurn(turn_n, agent.agent_id, agent.agent_name,
                                   response, signal, is_round1=True))

            if signal.kind == "HANDOFF" and signal.target:
                added = self._enqueue_if_new(signal.target, dynamic_queue, done)
                if added:
                    logger.info(
                        "OAISS R1 hand-off: %s → %s | %s",
                        agent.agent_name,
                        self.all_agents[signal.target].agent_name,
                        signal.reason,
                    )
            elif signal.kind == "CONSENSUS":
                logger.info("OAISS: Consensus signalled by %s at Round 1", agent.agent_name)

        # ── Phase 2: Dynamic OAISS loop ────────────────────────────────────────
        # Agents not yet called get added to continue the debate
        for agent in self.all_agents.values():
            if agent.agent_id not in done and agent not in dynamic_queue:
                dynamic_queue.append(agent)

        logger.info("OAISS Phase 2 — Dynamic loop (queue: %d agents)", len(dynamic_queue))

        while dynamic_queue and turn_n < self.max_turns:
            agent = dynamic_queue.pop(0)
            if agent.agent_id in done:
                continue
            turn_n += 1

            logger.info(
                "OAISS Turn %d: %s reacting to %d previous outputs",
                turn_n, agent.agent_name, len(context),
            )

            response, signal, p_tokens, c_tokens, cost = await self._safe_dynamic(agent, query, profile, context)
            total_prompt_tokens += p_tokens
            total_completion_tokens += c_tokens
            total_cost += cost

            round2_map[agent.agent_name] = response
            context[agent.agent_name] = response
            done.add(agent.agent_id)
            turns.append(OAISSTurn(turn_n, agent.agent_id, agent.agent_name,
                                   response, signal, is_round1=False))

            if signal.kind == "CONSENSUS":
                logger.info(
                    "OAISS Consensus reached at turn %d by %s | %s",
                    turn_n, agent.agent_name, signal.reason,
                )
                break

            elif signal.kind == "HANDOFF" and signal.target:
                added = self._enqueue_if_new(signal.target, dynamic_queue, done)
                if added:
                    logger.info(
                        "OAISS Dynamic hand-off: %s → %s | %s",
                        agent.agent_name,
                        self.all_agents[signal.target].agent_name,
                        signal.reason,
                    )
                else:
                    logger.info(
                        "OAISS: Hand-off target %s already done — skipping",
                        signal.target,
                    )

        logger.info(
            "OAISS complete — %d turns, agents engaged: %s | prompt_tokens=%d, completion_tokens=%d, cost=$%.6f",
            turn_n,
            [t.agent_name for t in turns],
            total_prompt_tokens,
            total_completion_tokens,
            total_cost,
        )

        return self._build_outputs(round1_map, round2_map), total_prompt_tokens, total_completion_tokens, total_cost

    async def run_stream(
        self,
        query: str,
        profile: Optional[UserProfile],
        initial_agents: List[BaseAgent],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming OAISS run. Yields real-time events as agents analyze, hand off, and debate.
        """
        context: Dict[str, str] = {}
        round1_map: Dict[str, str] = {}
        round2_map: Dict[str, str] = {}
        turns: List[OAISSTurn] = []
        done: set[str] = set()
        turn_n = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cost = 0.0

        yield {
            "event": "orchestration_start",
            "data": {
                "agents": [
                    {"agent_id": a.agent_id, "agent_name": a.agent_name, "emoji": a.emoji}
                    for a in initial_agents
                ],
                "message": f"Starting 2-round debate with {len(initial_agents)} expert agents...",
            },
        }

        async def run_round1_agent(
            agent: BaseAgent,
        ) -> Tuple[BaseAgent, Tuple[str, Signal, int, int, float]]:
            return agent, await self._safe_round1(agent, query, profile)

        # Phase 1: Round 1 starts together, then completions stream as they finish.
        for agent in initial_agents:
            yield {
                "event": "agent_start",
                "data": {
                    "agent_id": agent.agent_id,
                    "agent_name": agent.agent_name,
                    "emoji": agent.emoji,
                    "round": 1,
                    "message": f"{agent.emoji} {agent.agent_name} is analyzing independently...",
                },
            }

        round1_tasks = {
            asyncio.create_task(run_round1_agent(agent))
            for agent in initial_agents
        }

        while round1_tasks:
            done_tasks, round1_tasks = await asyncio.wait(
                round1_tasks,
                timeout=STREAM_HEARTBEAT_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done_tasks:
                yield {
                    "event": "heartbeat",
                    "data": {
                        "phase": "round1",
                        "pending_agents": len(round1_tasks),
                        "message": "Still receiving Round 1 analysis from the expert agents...",
                    },
                }
                continue

            for task in done_tasks:
                agent, (response, signal, p_tokens, c_tokens, cost) = await task
                turn_n += 1
                total_prompt_tokens += p_tokens
                total_completion_tokens += c_tokens
                total_cost += cost
                round1_map[agent.agent_name] = response
                context[agent.agent_name] = response
                done.add(agent.agent_id)
                turns.append(OAISSTurn(turn_n, agent.agent_id, agent.agent_name, response, signal, is_round1=True))

                yield {
                    "event": "agent_round1",
                    "data": {
                        "agent_id": agent.agent_id,
                        "agent_name": agent.agent_name,
                        "emoji": agent.emoji,
                        "response": response,
                        "signal": signal.kind,
                        "target": signal.target,
                        "reason": signal.reason,
                    },
                }

                if signal.kind == "HANDOFF" and signal.target and signal.target in self.all_agents:
                    yield {
                        "event": "handoff",
                        "data": {
                            "from": agent.agent_name,
                            "to": self.all_agents[signal.target].agent_name,
                            "reason": signal.reason,
                            "message": f"Dynamic handoff requested from {agent.agent_name} to {self.all_agents[signal.target].agent_name}: {signal.reason}",
                        },
                    }
                elif signal.kind == "CONSENSUS":
                    yield {
                        "event": "consensus",
                        "data": {
                            "agent_name": agent.agent_name,
                            "reason": signal.reason,
                            "message": f"Consensus signaled by {agent.agent_name}: {signal.reason}",
                        },
                    }

        # Dynamic loop preparation
        dynamic_queue: List[BaseAgent] = []
        for t in turns:
            if t.signal.kind == "HANDOFF" and t.signal.target:
                self._enqueue_if_new(t.signal.target, dynamic_queue, done)

        for agent in self.all_agents.values():
            if agent.agent_id not in done and agent not in dynamic_queue:
                dynamic_queue.append(agent)

        yield {
            "event": "debate_start",
            "data": {
                "queue": [a.agent_name for a in dynamic_queue],
                "message": "Round 2: Cross-agent debate & rebuttal loop active...",
            },
        }

        while dynamic_queue and turn_n < self.max_turns:
            agent = dynamic_queue.pop(0)
            if agent.agent_id in done:
                continue
            turn_n += 1

            yield {
                "event": "agent_start",
                "data": {
                    "agent_id": agent.agent_id,
                    "agent_name": agent.agent_name,
                    "emoji": agent.emoji,
                    "round": 2,
                    "message": f"{agent.emoji} {agent.agent_name} is evaluating peer arguments...",
                },
            }

            response, signal, p_tokens, c_tokens, cost = await self._safe_dynamic(agent, query, profile, context)
            total_prompt_tokens += p_tokens
            total_completion_tokens += c_tokens
            total_cost += cost

            round2_map[agent.agent_name] = response
            context[agent.agent_name] = response
            done.add(agent.agent_id)
            turns.append(OAISSTurn(turn_n, agent.agent_id, agent.agent_name, response, signal, is_round1=False))

            yield {
                "event": "agent_round2",
                "data": {
                    "agent_id": agent.agent_id,
                    "agent_name": agent.agent_name,
                    "emoji": agent.emoji,
                    "response": response,
                    "signal": signal.kind,
                    "target": signal.target,
                    "reason": signal.reason,
                },
            }

            if signal.kind == "CONSENSUS":
                yield {
                    "event": "consensus",
                    "data": {
                        "agent_name": agent.agent_name,
                        "reason": signal.reason,
                        "message": f"🤝 Consensus reached by {agent.agent_name}: {signal.reason}",
                    },
                }
                break

            elif signal.kind == "HANDOFF" and signal.target and signal.target in self.all_agents:
                added = self._enqueue_if_new(signal.target, dynamic_queue, done)
                if added:
                    yield {
                        "event": "handoff",
                        "data": {
                            "from": agent.agent_name,
                            "to": self.all_agents[signal.target].agent_name,
                            "reason": signal.reason,
                            "message": f"⚡ Dynamic handoff to {self.all_agents[signal.target].agent_name}: {signal.reason}",
                        },
                    }

        agent_rounds = self._build_outputs(round1_map, round2_map)

        yield {
            "event": "orchestration_complete",
            "data": {
                "agent_rounds": [ar.model_dump() for ar in agent_rounds],
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_cost": total_cost,
            },
        }

    #  Output builder 


    def _build_outputs(
        self,
        round1: Dict[str, str],
        round2: Dict[str, str],
    ) -> List[AgentRoundOutput]:
        outputs: List[AgentRoundOutput] = []
        for agent_id, agent in self.all_agents.items():
            r1 = round1.get(agent.agent_name, "")
            r2 = round2.get(agent.agent_name, "")
            if not r1 and not r2:
                continue  # agent was never called
            outputs.append(
                AgentRoundOutput(
                    agent_id=agent_id,
                    agent_name=agent.agent_name,
                    emoji=agent.emoji,
                    round1=r1,
                    round2=r2,
                    confidence=compute_confidence(r1 + " " + r2),
                )
            )
        return outputs
