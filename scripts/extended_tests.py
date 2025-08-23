from __future__ import annotations

from typing import List

from app.agents.graph import PlanGraph
from app.agents.nodes import allowed_list_node, validate_node
from app.models import AllowedListRequest, PlanRequest, ValidationRequest, UserProfile
from app.services.allowed_exercises import shortlist
from app.services.export import to_csv, to_markdown
from app.services.planner_local import replace_one_exercise


def build_profile(days: int = 3, max_per_day: int = 5) -> UserProfile:
    return UserProfile(
        goal="hypertrophy",
        days_per_week=days,
        session_minutes_cap=60,
        max_exercises_per_day=max_per_day,
        default_sets=3,
        default_reps=10,
        rest_seconds=90,
        supersets_enabled=False,
        progressive_overload=False,
        allowed_equipment=[],
        blacklisted_equipment=[],
        emphasis={},
        blacklisted_muscles=[],
        blacklisted_exercise_ids=[],
    )


def test_nodes_and_graph() -> None:
    profile = build_profile()

    # allowed_list_node
    al_req = AllowedListRequest(profile=profile)
    al_res = allowed_list_node(al_req)
    assert isinstance(al_res.exercise_ids, list) and len(al_res.exercise_ids) > 0, "Allowed list is empty"
    assert isinstance(al_res.rationale, str) and len(al_res.rationale) > 0, "Missing rationale"

    # Graph end-to-end
    graph = PlanGraph()
    state = graph.invoke(profile)
    plan = state["plan_res"].plan  # type: ignore[index]

    assert len(plan.days) == profile.days_per_week, "Plan day count mismatch"
    for day in plan.days:
        assert len(day.exercises) <= profile.max_exercises_per_day, "Exceeded max exercises/day"

    # Validate node
    v_req = ValidationRequest(profile=profile, plan=plan)
    v_res = validate_node(v_req)
    assert v_res.ok, f"Validation failed with issues: {v_res.issues}"

    # Exporters
    assert to_csv(plan), "CSV export is empty"
    assert to_markdown(plan), "Markdown export is empty"

    # Replacement flow on day 0, exercise 0
    allowed_ids = shortlist(profile)
    if plan.days and plan.days[0].exercises:
        orig_id = plan.days[0].exercises[0].id
        plan2 = replace_one_exercise(profile, plan, 0, orig_id, allowed_ids)
        # Either changed or remained same if no candidate found, but plan remains valid
        v2 = validate_node(ValidationRequest(profile=profile, plan=plan2))
        assert v2.ok, f"Validation after replacement failed: {v2.issues}"

    total_ex = sum(len(d.exercises) for d in plan.days)
    print(f"EXTENDED TESTS OK — days={len(plan.days)} total_exercises={total_ex} allowed={len(al_res.exercise_ids)}")


if __name__ == "__main__":
    test_nodes_and_graph()
