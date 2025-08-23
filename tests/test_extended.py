from __future__ import annotations

from app.agents.graph import PlanGraph
from app.agents.nodes import allowed_list_node, validate_node
from app.models import AllowedListRequest, ValidationRequest, UserProfile
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


def test_nodes_graph_and_exports() -> None:
    profile = build_profile()

    # allowed list node
    al = allowed_list_node(AllowedListRequest(profile=profile))
    assert al.exercise_ids, "Allowed list should not be empty"

    # graph end-to-end
    graph = PlanGraph()
    state = graph.invoke(profile)
    plan = state["plan_res"].plan  # type: ignore[index]

    assert len(plan.days) == profile.days_per_week
    for day in plan.days:
        assert len(day.exercises) <= profile.max_exercises_per_day

    # validation
    v = validate_node(ValidationRequest(profile=profile, plan=plan))
    assert v.ok, f"Validation issues: {v.issues}"

    # exports
    assert to_csv(plan)
    assert to_markdown(plan)

    # replacement local path (LLM not required for tests)
    allowed_ids = shortlist(profile)
    if plan.days and plan.days[0].exercises:
        ex_id = plan.days[0].exercises[0].id
        plan2 = replace_one_exercise(profile, plan, 0, ex_id, allowed_ids)
        v2 = validate_node(ValidationRequest(profile=profile, plan=plan2))
        assert v2.ok
