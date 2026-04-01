from __future__ import annotations

import asyncio
from abc import ABC
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from ..config import settings
from ..models import UserProfile


def _profile_context(profile: Optional[UserProfile]) -> str:
    if not profile:
        return "No user profile provided."
    parts = [f"Username: {profile.username}"]
    if profile.budget_min is not None and profile.budget_max is not None:
        parts.append(f"Budget: ₹{profile.budget_min:,.0f} – ₹{profile.budget_max:,.0f}")
    elif profile.budget_max:
        parts.append(f"Max budget: ₹{profile.budget_max:,.0f}")
    if profile.location_preference:
        parts.append(f"Locations: {', '.join(profile.location_preference)}")
    if profile.purpose:
        parts.append(f"Purpose: {profile.purpose.replace('_', ' ').title()}")
    if profile.risk_appetite:
        parts.append(f"Risk appetite: {profile.risk_appetite.upper()}")
    if profile.timeline_months:
        parts.append(f"Timeline: {profile.timeline_months} months")
    if profile.existing_properties:
        parts.append(f"Existing properties: {profile.existing_properties}")
    if profile.preferred_property_type:
        parts.append(f"Preferred type: {profile.preferred_property_type}")
    if profile.citizenship_status:
        parts.append(f"Citizenship: {profile.citizenship_status}")
    if profile.loan_eligibility_known:
        parts.append("Loan eligibility: Already assessed")
    return " | ".join(parts)


class BaseAgent(ABC):
    agent_id: str
    agent_name: str
    emoji: str
    role: str
    goal: str
    backstory: str
    known_biases: str
    interaction_rules: str
    focus_domains: List[str]

    async def _llm(self, system: str, user: str) -> str:
        client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.7,
            ),
            timeout=settings.AGENT_TIMEOUT,
        )
        return resp.choices[0].message.content or ""

    def _sys_round1(self) -> str:
        return (
            f"You are {self.agent_name}, a domain expert on a 5-member real estate advisory panel.\n\n"
            f"ROLE: {self.role}\n"
            f"GOAL: {self.goal}\n"
            f"BACKSTORY: {self.backstory}\n\n"
            f"KNOWN BIASES (self-correct when triggered): {self.known_biases}\n\n"
            f"INTERACTION RULES: {self.interaction_rules}\n\n"
            "ROUND 1 RULES:\n"
            "- Respond independently from your own expertise only.\n"
            "- Be specific and practical; avoid vague generalities.\n"
            "- Flag genuine uncertainty honestly.\n"
            "- Max 350 words. End with your single most important advice."
        )

    def _sys_round2(self, others: Dict[str, str]) -> str:
        panel = "\n\n".join(
            f"--- {name.upper()} SAID ---\n{text}" for name, text in others.items()
        )
        return (
            f"You are {self.agent_name} in ROUND 2 of the real estate debate.\n\n"
            f"ROLE: {self.role}\n"
            f"KNOWN BIASES: {self.known_biases}\n\n"
            f"COLLEAGUES' ROUND 1 RESPONSES:\n{panel}\n\n"
            "ROUND 2 STRICT RULES:\n"
            "1. MUST agree or disagree with at least one expert by name.\n"
            '   Format: "I disagree with [Agent] because..." OR "I agree with [Agent], and additionally..."\n'
            "2. Add ONLY new insights not already mentioned by anyone.\n"
            "3. Do NOT repeat information from Round 1.\n"
            "4. Acknowledge your bias if it influenced Round 1.\n"
            "5. Max 300 words."
        )

    async def round1(self, query: str, profile: Optional[UserProfile]) -> str:
        user_msg = (
            f"USER PROFILE: {_profile_context(profile)}\n\n"
            f"QUERY: {query}\n\n"
            f"Provide your Round 1 analysis as {self.agent_name}."
        )
        return await self._llm(self._sys_round1(), user_msg)

    async def round2(
        self,
        query: str,
        profile: Optional[UserProfile],
        others: Dict[str, str],
    ) -> str:
        user_msg = (
            f"USER PROFILE: {_profile_context(profile)}\n\n"
            f"ORIGINAL QUERY: {query}\n\n"
            "React to your colleagues' responses. Reference them by name. Add only new insights."
        )
        return await self._llm(self._sys_round2(others), user_msg)
