from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    username: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    location_preference: List[str] = []
    purpose: Optional[Literal["investment", "self_use", "commercial"]] = None
    risk_appetite: Optional[Literal["low", "medium", "high"]] = None
    timeline_months: Optional[int] = None
    existing_properties: int = 0
    preferred_property_type: Optional[str] = None
    citizenship_status: Optional[str] = None
    loan_eligibility_known: bool = False


class AnalyzeRequest(BaseModel):
    query: str
    username: str


class ProfileUpdateRequest(BaseModel):
    username: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    location_preference: List[str] = []
    purpose: Optional[Literal["investment", "self_use", "commercial"]] = None
    risk_appetite: Optional[Literal["low", "medium", "high"]] = None
    timeline_months: Optional[int] = None
    existing_properties: int = 0
    preferred_property_type: Optional[str] = None
    citizenship_status: Optional[str] = None
    loan_eligibility_known: bool = False


class AgentRoundOutput(BaseModel):
    agent_id: str
    agent_name: str
    emoji: str = ""
    round1: str
    round2: str
    confidence: Literal["high", "medium", "low"]


class AgentView(BaseModel):
    agent: str
    key_points: List[str]
    confidence: Literal["high", "medium", "low"]
    dissents_from: List[str] = []


class KeyInsights(BaseModel):
    market: str = ""
    investment: str = ""
    legal: str = ""
    financial: str = ""
    construction: str = ""


class AnalysisResult(BaseModel):
    summary: str
    key_insights: KeyInsights
    risks: List[str]
    recommendation: Literal["Buy", "Avoid", "Consider", "Needs more info"]
    confidence_score: int = Field(ge=1, le=10)
    agent_views: List[AgentView]
    follow_up_questions: List[str]
    active_domains: List[str] = []
    agent_rounds: List[AgentRoundOutput] = []
