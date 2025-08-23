from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from app.config import get_settings
from app.models import (
    AllowedListRequest,
    AllowedListResponse,
    PlanRequest,
    PlanResponse,
    ValidationRequest,
    ValidationReport,
    RepairRequest,
    RepairResponse,
    UserProfile,
)
from .nodes import allowed_list_node, plan_generate_node, validate_node, repair_node


@dataclass
class GraphState:
    allowed_req: AllowedListRequest | None = None
    allowed_res: AllowedListResponse | None = None
    plan_req: PlanRequest | None = None
    plan_res: PlanResponse | None = None
    validation_req: ValidationRequest | None = None
    validation: ValidationReport | None = None
    repair_req: RepairRequest | None = None


class PlanGraph:
    def __init__(self) -> None:
        self.settings = get_settings()

    def invoke(self, profile: UserProfile, seed: int | None = None) -> Dict[str, Any]:
        import random
        state = GraphState()
        # allowed_list
        state.allowed_req = AllowedListRequest(profile=profile)
        state.allowed_res = allowed_list_node(state.allowed_req)
        # Optional shuffle of allowed ids to diversify plans
        allowed_ids = list(state.allowed_res.exercise_ids)
        if seed is not None:
            rnd = random.Random(seed)
            rnd.shuffle(allowed_ids)
        # plan_generate
        state.plan_req = PlanRequest(profile=profile, allowed_exercise_ids=allowed_ids)
        state.plan_res = plan_generate_node(state.plan_req)
        # validate and repair loop
        iter_left = self.settings.MAX_REPAIR_ITERATIONS
        while True:
            state.validation_req = ValidationRequest(profile=profile, plan=state.plan_res.plan)
            state.validation = validate_node(state.validation_req)
            if state.validation.ok:
                break
            if iter_left <= 0:
                break
            iter_left -= 1
            state.repair_req = RepairRequest(
                profile=profile,
                plan=state.plan_res.plan,
                allowed_exercise_ids=allowed_ids,
                issues=state.validation.issues,
            )
            repaired = repair_node(state.repair_req)
            state.plan_res = PlanResponse(plan=repaired.plan)
        return state.__dict__
