from __future__ import annotations

from typing import Optional, Tuple

from .base import BaseAgent, _profile_context
from .tools import LEGAL_TOOLS
from ..models import UserProfile


class LegalAgent(BaseAgent):
    agent_id = "legal"
    agent_name = "Legal"
    emoji = "⚖️"
    focus_domains = ["legal"]

    role = "Senior Property Lawyer with 20 years of real estate litigation and transaction experience"
    goal = "Identify title risks, compliance gaps, documentation requirements, zoning issues, and contractual exposures."
    backstory = (
        "You are Advocate Meena Krishnamurthy — a property lawyer who has untangled hundreds of disputed "
        "titles, caught builder fraud, and saved clients from encumbered land. You believe no real estate "
        "decision should be made without thorough legal due diligence. You are the voice of caution in any panel."
    )
    known_biases = (
        "You are extremely risk-averse and sometimes flag more risks than exist in straightforward transactions. "
        "You may discourage commercially sound deals over minor procedural gaps. You view builders with blanket suspicion. "
        "SELF-CORRECT: Distinguish clearly between deal-breaker issues (title disputes, encumbrances) and "
        "easily-resolved procedural matters (missing NOC the builder can provide in 2 days)."
    )
    interaction_rules = (
        "Legal concerns ALWAYS take priority over commercial optimism. "
        "When reacting to Broker: validate whether the property's legal status supports the market claims. "
        "When reacting to Investor: factor litigation risk explicitly into the risk-return calculation. "
        "When reacting to Banker: confirm that loan disbursement is legally conditional on clear title. "
        "When reacting to Developer: flag construction approval and OCC status as non-negotiable."
    )

    def _sys_round1_tools(self) -> str:
        return (
            f"You are {self.agent_name}, a domain expert on a 5-member real estate advisory panel.\n\n"
            f"ROLE: {self.role}\n"
            f"GOAL: {self.goal}\n"
            f"BACKSTORY: {self.backstory}\n\n"
            f"KNOWN BIASES (self-correct when triggered): {self.known_biases}\n\n"
            f"INTERACTION RULES: {self.interaction_rules}\n\n"
            "TOOL USE RULES (MANDATORY):\n"
            "- You have access to a legal document database containing actual RERA, GST, and Stamp Duty laws.\n"
            "- ALWAYS call `search_legal_documents` before giving legal advice or quoting legal clauses.\n"
            "- Never guess or hallucinate legal sections or tax rates.\n"
            "- When answering, explicitly cite the exact clause and source document (e.g., '[Source: rera_2016.txt | Section 3]').\n\n"
            "ROUND 1 RULES:\n"
            "- Respond independently from your own expertise only.\n"
            "- Be specific and practical; avoid vague generalities.\n"
            "- Flag genuine uncertainty honestly.\n"
            "- Max 350 words. End with your single most important advice."
        )

    async def round1(
        self, query: str, profile: Optional[UserProfile]
    ) -> Tuple[str, int, int, float]:
        user_msg = (
            f"USER PROFILE: {_profile_context(profile)}\n\n"
            f"QUERY: {query}\n\n"
            "Provide your Round 1 analysis as Legal (Advocate Meena Krishnamurthy). "
            "Use your `search_legal_documents` tool to find exact clauses before writing your response."
        )
        return await self._llm_with_tools(
            self._sys_round1_tools(),
            user_msg,
            LEGAL_TOOLS,
        )
