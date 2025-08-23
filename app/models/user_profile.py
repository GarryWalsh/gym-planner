from __future__ import annotations

from typing import Dict, List, Literal
from pydantic import BaseModel, Field

from .exercise import Equipment


Goal = Literal["hypertrophy", "strength", "hybrid"]


class UserProfile(BaseModel):
    goal: Goal
    days_per_week: int = Field(..., ge=1, le=6)
    session_minutes_cap: int = Field(..., ge=30, le=120)
    max_exercises_per_day: int = Field(..., ge=3, le=10)
    default_sets: int = Field(..., ge=2, le=6)
    default_reps: int = Field(..., ge=3, le=15)
    rest_seconds: int = Field(..., ge=30, le=240)
    supersets_enabled: bool = False
    progressive_overload: bool = False

    allowed_equipment: List[Equipment] = Field(default_factory=list)
    blacklisted_equipment: List[Equipment] = Field(default_factory=list)

    emphasis: Dict[str, int] = Field(default_factory=dict, description="muscle -> 0|1")
    blacklisted_muscles: List[str] = Field(default_factory=list)
    blacklisted_exercise_ids: List[str] = Field(default_factory=list)
