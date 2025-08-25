from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

from app.config import get_settings
from app.llm import chat_json
from app.models import (
    ExplainRequest,
    ExplainResponse,
    ReplacementRequest,
    ReplacementResponse,
    UserProfile,
    PlanQAResponse,
)
from app.models.plan import Plan
from app.services.catalog import load_catalog
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts" / "jobs"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _allowed_exercise_details(ids: Sequence[str]) -> List[Dict[str, Any]]:
    catalog = {ex.id: ex for ex in load_catalog()}
    out: List[Dict[str, Any]] = []
    for eid in ids:
        ex = catalog.get(eid)
        if not ex:
            continue
        out.append({
            "id": ex.id,
            "name": ex.name,
            "exrx_url": str(ex.exrx_url),
            "primary_muscles": ex.primary_muscles,
            "function": ex.function,
            "equipment": ex.equipment,
            "type": ex.type,
        })
    return out


def explain_plan_llm(profile: UserProfile, plan: Plan) -> ExplainResponse:
    settings = get_settings()
    system = _load_prompt("explain_plan.md")
    payload = {
        "PROFILE": profile.model_dump(mode="json"),
        "PLAN": plan.model_dump(mode="json"),
    }
    resp = chat_json(
        schema=ExplainResponse.model_json_schema(),
        system=system,
        user=json.dumps(payload, ensure_ascii=False),
        temperature=0.2,
        job="explain",
    )
    return ExplainResponse.model_validate(resp)


def replace_exercise_llm(
    profile: UserProfile,
    plan: Plan,
    day_index: int,
    replace_exercise_id: str,
    allowed_exercise_ids: Sequence[str],
) -> Plan:
    system = _load_prompt("replace_exercise.md")
    payload = {
        "PROFILE": profile.model_dump(mode="json"),
        "PLAN": plan.model_dump(mode="json"),
        "day_index": day_index,
        "replace_exercise_id": replace_exercise_id,
        "ALLOWED_EXERCISES": _allowed_exercise_details(list(allowed_exercise_ids)),
    }
    resp = chat_json(
        schema=ReplacementResponse.model_json_schema(),
        system=system,
        user=json.dumps(payload, ensure_ascii=False),
        temperature=0.2,
        job="replace",
    )
    rr = ReplacementResponse.model_validate(resp)
    return rr.plan


def answer_plan_question_llm(profile: UserProfile, plan: Plan, question: str) -> PlanQAResponse:
    system = _load_prompt("qa_plan.md")
    payload = {
        "PROFILE": profile.model_dump(mode="json"),
        "PLAN": plan.model_dump(mode="json"),
        "QUESTION": question,
    }
    resp = chat_json(
        schema=PlanQAResponse.model_json_schema(),
        system=system,
        user=json.dumps(payload, ensure_ascii=False),
        temperature=0.2,
        job="qa",
    )
    return PlanQAResponse.model_validate(resp)
