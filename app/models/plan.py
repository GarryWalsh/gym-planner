from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from .exercise import Exercise


class SupersetPair(BaseModel):
    a_exercise_id: str
    b_exercise_id: str


class DayPlan(BaseModel):
    day_index: int = Field(..., ge=0)
    label: str
    exercises: List[Exercise]
    sets: int = Field(..., ge=1)
    reps: int = Field(..., ge=1)
    rest_seconds: int = Field(..., ge=0)
    supersets: List[SupersetPair] = []


class Plan(BaseModel):
    days: List[DayPlan]
    weekly_focus: Dict[str, int] = Field(default_factory=dict)
    meta: Dict[str, str] = Field(default_factory=dict)
