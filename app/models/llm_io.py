from __future__ import annotations

from typing import List, Dict, Literal
from pydantic import BaseModel, Field

from .plan import Plan
from .user_profile import UserProfile


class AllowedListRequest(BaseModel):
    profile: UserProfile


class AllowedListResponse(BaseModel):
    exercise_ids: List[str]
    rationale: str = ""


class PlanRequest(BaseModel):
    profile: UserProfile
    allowed_exercise_ids: List[str]


class PlanResponse(BaseModel):
    plan: Plan


class Issue(BaseModel):
    code: Literal[
        "DAY_COUNT_MISMATCH",
        "EXCEEDS_MAX_EXERCISES",
        "EQUIPMENT_BLOCKED",
        "MUSCLE_UNDERCOVERED",
        "DUPLICATE_EXERCISE",
        "SEQUENCING_IMPLAUSIBLE",
    ]
    message: str


class ValidationRequest(BaseModel):
    profile: UserProfile
    plan: Plan


class ValidationReport(BaseModel):
    ok: bool
    issues: List[Issue] = Field(default_factory=list)


class RepairRequest(BaseModel):
    profile: UserProfile
    plan: Plan
    allowed_exercise_ids: List[str]
    issues: List[Issue]


class RepairResponse(BaseModel):
    plan: Plan


class ReplacementRequest(BaseModel):
    profile: UserProfile
    plan: Plan
    day_index: int
    replace_exercise_id: str
    allowed_exercise_ids: List[str] | None = None


class ReplacementResponse(BaseModel):
    plan: Plan


class ExplainRequest(BaseModel):
    profile: UserProfile
    plan: Plan


class ExplainResponse(BaseModel):
    overall: str
    day_summaries: List[str]


class PlanQARequest(BaseModel):
    profile: UserProfile
    plan: Plan
    question: str


class PlanQAResponse(BaseModel):
    answer: str
