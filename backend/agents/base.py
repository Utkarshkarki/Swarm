from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC
from typing import Any, Dict, List, Optional, Tuple

from .tools import execute_tool

try:
    from langfuse import observe
except ImportError:
    from langfuse.decorators import observe

from openai import AsyncOpenAI

from ..config import settings
from ..models import UserProfile

# Foundation Agent
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

    @observe(as_type="generation")
    async def _llm(self, system: str, user: str) -> Tuple[str, int, int, float]:
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
        content = resp.choices[0].message.content or ""
        prompt_tokens = resp.usage.prompt_tokens if resp.usage else 0
        completion_tokens = resp.usage.completion_tokens if resp.usage else 0
        cost = (
            (prompt_tokens * settings.INPUT_TOKEN_PRICE_PER_1M / 1_000_000.0)
            + (completion_tokens * settings.OUTPUT_TOKEN_PRICE_PER_1M / 1_000_000.0)
        )
        return content, prompt_tokens, completion_tokens, cost

    @observe(as_type="generation")
    async def _llm_with_tools(
        self,
        system: str,
        user: str,
        tools: List[Dict[str, Any]],
        max_tool_iterations: int = 5,
    ) -> Tuple[str, int, int, float]:
        """
        Agentic tool-calling loop.

        1. Calls the LLM with the supplied tool schemas.
        2. If the model emits tool_calls, executes each locally via execute_tool().
        3. Appends tool results as 'tool' role messages and re-calls the LLM.
        4. Repeats until the model returns a plain-text response (no tool_calls)
           or max_tool_iterations is reached.
        5. Gracefully falls back to plain _llm() if the model does not support
           function calling (i.e. tool_calls is None/empty on the first turn).

        Returns
        -------
        (content, total_prompt_tokens, total_completion_tokens, total_cost)
        """
        _log = logging.getLogger(__name__)
        client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ]

        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cost = 0.0

        for iteration in range(max_tool_iterations):
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=messages,  # type: ignore[arg-type]
                    tools=tools,  # type: ignore[arg-type]
                    tool_choice="auto",
                    temperature=0.7,
                ),
                timeout=settings.AGENT_TIMEOUT,
            )

            prompt_tokens = resp.usage.prompt_tokens if resp.usage else 0
            completion_tokens = resp.usage.completion_tokens if resp.usage else 0
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens
            total_cost += (
                (prompt_tokens * settings.INPUT_TOKEN_PRICE_PER_1M / 1_000_000.0)
                + (completion_tokens * settings.OUTPUT_TOKEN_PRICE_PER_1M / 1_000_000.0)
            )

            choice = resp.choices[0]
            assistant_message = choice.message

            # No tool calls → model is done; return its text
            if not assistant_message.tool_calls:
                if iteration == 0 and not (assistant_message.content or "").strip():
                    # Model may not support tools at all — fall back to plain call
                    _log.warning(
                        "%s: model returned no tool_calls and no content on first turn — "
                        "falling back to plain _llm()", self.agent_name
                    )
                    return await self._llm(system, user)
                content = assistant_message.content or ""
                _log.info("%s: tool loop completed in %d iteration(s)", self.agent_name, iteration + 1)
                return content, total_prompt_tokens, total_completion_tokens, total_cost

            # Append assistant message (with tool_calls) to history
            messages.append(assistant_message.model_dump(exclude_unset=True))

            # Execute each requested tool and append results
            for tc in assistant_message.tool_calls:
                tool_name = tc.function.name
                tool_args = tc.function.arguments  # JSON string
                _log.info("%s: calling tool '%s' with args %s", self.agent_name, tool_name, tool_args)

                tool_result = await asyncio.to_thread(execute_tool, tool_name, tool_args)
                _log.info("%s: tool '%s' result: %s", self.agent_name, tool_name, tool_result[:200])

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })

        # Safety: exceeded max iterations — do a final plain completion
        _log.warning("%s: exceeded max_tool_iterations=%d — forcing final completion",
                     self.agent_name, max_tool_iterations)
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,  # type: ignore[arg-type]
                temperature=0.7,
            ),
            timeout=settings.AGENT_TIMEOUT,
        )
        content = resp.choices[0].message.content or ""
        prompt_tokens = resp.usage.prompt_tokens if resp.usage else 0
        completion_tokens = resp.usage.completion_tokens if resp.usage else 0
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_cost += (
            (prompt_tokens * settings.INPUT_TOKEN_PRICE_PER_1M / 1_000_000.0)
            + (completion_tokens * settings.OUTPUT_TOKEN_PRICE_PER_1M / 1_000_000.0)
        )
        return content, total_prompt_tokens, total_completion_tokens, total_cost

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

    async def round1(
        self, query: str, profile: Optional[UserProfile]
    ) -> Tuple[str, int, int, float]:
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
    ) -> Tuple[str, int, int, float]:
        user_msg = (
            f"USER PROFILE: {_profile_context(profile)}\n\n"
            f"ORIGINAL QUERY: {query}\n\n"
            "React to your colleagues' responses. Reference them by name. Add only new insights."
        )
        return await self._llm(self._sys_round2(others), user_msg)

