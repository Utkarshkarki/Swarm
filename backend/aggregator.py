from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import List, Optional

from openai import AsyncOpenAI

from .config import settings
from .models import AgentRoundOutput, AgentView, AnalysisResult, KeyInsights, UserProfile

logger = logging.getLogger(__name__)

_SYSTEM = """You are the Senior Real Estate Advisory Manager — final decision-maker for a 5-expert panel.

RESPONSIBILITIES:
1. Synthesize all expert inputs (Round 1 + Round 2 debate).
2. Resolve disagreements using strict priority: Legal > Financial > Investment > Market > Construction.
3. Never hallucinate facts not present in expert responses.
4. Be honest about missing information.

OUTPUT: You MUST return ONLY valid JSON — no markdown, no code fences, no extra text.

EXACT SCHEMA:
{
  "summary": "2-3 sentence executive summary",
  "key_insights": {
    "market": "...",
    "investment": "...",
    "legal": "...",
    "financial": "...",
    "construction": "..."
  },
  "risks": ["risk 1", "risk 2", "risk 3"],
  "recommendation": "Buy" or "Avoid" or "Consider" or "Needs more info",
  "confidence_score": integer 1-10,
  "agent_views": [
    {
      "agent": "agent name",
      "key_points": ["point 1", "point 2"],
      "confidence": "high" or "medium" or "low",
      "dissents_from": ["agent name"]
    }
  ],
  "follow_up_questions": ["question 1", "question 2", "question 3"]
}"""


def _build_prompt(
    query: str, profile: Optional[UserProfile], agent_rounds: List[AgentRoundOutput]
) -> str:
    profile_txt = ""
    if profile:
        parts = [f"Username: {profile.username}"]
        if profile.budget_min and profile.budget_max:
            parts.append(f"Budget ₹{profile.budget_min:,.0f}–₹{profile.budget_max:,.0f}")
        if profile.purpose:
            parts.append(f"Purpose: {profile.purpose}")
        if profile.risk_appetite:
            parts.append(f"Risk: {profile.risk_appetite}")
        if profile.timeline_months:
            parts.append(f"Timeline: {profile.timeline_months} months")
        profile_txt = " | ".join(parts)

    sections = []
    for ar in agent_rounds:
        sections.append(
            f"=== {ar.agent_name.upper()} (confidence: {ar.confidence}) ===\n"
            f"ROUND 1:\n{ar.round1}\n\n"
            f"ROUND 2 (debate):\n{ar.round2}"
        )

    return (
        f"QUERY: {query}\n"
        f"USER PROFILE: {profile_txt or 'Not provided'}\n\n"
        f"EXPERT PANEL:\n\n" + "\n\n".join(sections) +
        "\n\nProduce the final advisory JSON. Legal concerns override all others. Output ONLY valid JSON."
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]+\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON found in aggregator response: {text[:300]}")


async def aggregate(
    query: str,
    profile: Optional[UserProfile],
    agent_rounds: List[AgentRoundOutput],
) -> AnalysisResult:
    client = AsyncOpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)
    prompt = _build_prompt(query, profile, agent_rounds)

    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            ),
            timeout=settings.AGENT_TIMEOUT,
        )
        raw = resp.choices[0].message.content or ""
        data = _extract_json(raw)

        agent_views = [
            AgentView(
                agent=av.get("agent", "Unknown"),
                key_points=av.get("key_points", []),
                confidence=av.get("confidence", "medium"),
                dissents_from=av.get("dissents_from", []),
            )
            for av in data.get("agent_views", [])
        ]

        return AnalysisResult(
            summary=data.get("summary", ""),
            key_insights=KeyInsights(**data.get("key_insights", {})),
            risks=data.get("risks", []),
            recommendation=data.get("recommendation", "Needs more info"),
            confidence_score=max(1, min(10, int(data.get("confidence_score", 5)))),
            agent_views=agent_views,
            follow_up_questions=data.get("follow_up_questions", []),
        )

    except Exception as exc:
        logger.error("Aggregator failed: %s", exc)
        return AnalysisResult(
            summary=f"Aggregation failed: {exc}",
            key_insights=KeyInsights(),
            risks=["System error — please retry"],
            recommendation="Needs more info",
            confidence_score=1,
            agent_views=[],
            follow_up_questions=["Could you retry your query?"],
        )
