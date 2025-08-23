from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.config import get_settings
from app.llm import chat_json, LLMError
from app.models import (
    AllowedListRequest,
    AllowedListResponse,
    PlanRequest,
    PlanResponse,
    ValidationRequest,
    ValidationReport,
    RepairRequest,
    RepairResponse,
)
from app.services.allowed_exercises import shortlist
from app.services.planner_local import generate_local_plan
from app.services.catalog import load_catalog

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts" / "jobs"


def _llm_enabled() -> bool:
    settings = get_settings()
    return bool(settings.GROQ_API_KEY)


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8")


def _allowed_exercise_details(ids: List[str]) -> List[Dict[str, Any]]:
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


def allowed_list_node(req: AllowedListRequest) -> AllowedListResponse:
    ids = shortlist(req.profile)
    rationale = "Filtered by equipment allow/deny, muscle/ID blacklists, with emphasis and compound priority."
    return AllowedListResponse(exercise_ids=ids, rationale=rationale)


def plan_generate_node(req: PlanRequest) -> PlanResponse:
    # Try LLM first if enabled
    if _llm_enabled():
        try:
            system = _load_prompt("plan_generate.md")
            payload = {
                "PROFILE": req.profile.model_dump(mode="json"),
                "ALLOWED_EXERCISES": _allowed_exercise_details(req.allowed_exercise_ids),
            }
            resp = chat_json(
                schema=PlanResponse.model_json_schema(),
                system=system,
                user=json.dumps(payload, ensure_ascii=False),
                temperature=0.2,
            )
            return PlanResponse.model_validate(resp)
        except Exception:
            # fall back to local
            pass
    plan = generate_local_plan(req.profile, req.allowed_exercise_ids)
    return PlanResponse(plan=plan)


def validate_node(req: ValidationRequest) -> ValidationReport:
    # LLM validator if available
    if _llm_enabled():
        try:
            system = _load_prompt("validate_plan.md")
            payload = {
                "PROFILE": req.profile.model_dump(mode="json"),
                "PLAN": req.plan.model_dump(mode="json"),
            }
            resp = chat_json(
                schema=ValidationReport.model_json_schema(),
                system=system,
                user=json.dumps(payload, ensure_ascii=False),
                temperature=0.0,
            )
            return ValidationReport.model_validate(resp)
        except Exception:
            pass
    # Minimal local validation
    issues: List[Dict[str, str]] = []
    if len(req.plan.days) != req.profile.days_per_week:
        issues.append({"code": "DAY_COUNT_MISMATCH", "message": "Day count does not match profile."})
    for day in req.plan.days:
        if len(day.exercises) > req.profile.max_exercises_per_day:
            issues.append({
                "code": "EXCEEDS_MAX_EXERCISES",
                "message": f"Day {day.day_index} exceeds maximum exercises.",
            })
    ok = len(issues) == 0
    return ValidationReport(ok=ok, issues=issues)  # type: ignore[arg-type]


def repair_node(req: RepairRequest) -> RepairResponse:
    # If LLM available, attempt repair
    if _llm_enabled() and req.issues:
        try:
            system = _load_prompt("repair_plan.md")
            payload = {
                "PROFILE": req.profile.model_dump(mode="json"),
                "PLAN": req.plan.model_dump(mode="json"),
                "ALLOWED_EXERCISES": _allowed_exercise_details(req.allowed_exercise_ids),
                "ISSUES": [i.model_dump(mode="json") for i in req.issues],
            }
            resp = chat_json(
                schema=RepairResponse.model_json_schema(),
                system=system,
                user=json.dumps(payload, ensure_ascii=False),
                temperature=0.2,
            )
            return RepairResponse.model_validate(resp)
        except Exception:
            pass
    # Fallback: pass-through
    return RepairResponse(plan=req.plan)
