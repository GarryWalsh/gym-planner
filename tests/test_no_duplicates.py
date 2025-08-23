from __future__ import annotations

from app.agents.graph import PlanGraph
from app.models import UserProfile


def test_no_duplicates_per_day() -> None:
    profile = UserProfile(
        goal="hypertrophy",
        days_per_week=3,
        session_minutes_cap=60,
        max_exercises_per_day=6,
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
    graph = PlanGraph()
    state = graph.invoke(profile)
    plan = state["plan_res"].plan  # type: ignore[index]

    for day in plan.days:
        ids = [ex.id for ex in day.exercises]
        assert len(ids) == len(set(ids)), f"Duplicates found on day {day.day_index}: {ids}"
