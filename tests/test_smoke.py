from __future__ import annotations

from app.agents.graph import PlanGraph
from app.models import UserProfile
from app.services.allowed_exercises import shortlist
from app.services.export import to_csv, to_markdown


def test_smoke_end_to_end() -> None:
    profile = UserProfile(
        goal="hypertrophy",
        days_per_week=3,
        session_minutes_cap=60,
        max_exercises_per_day=5,
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

    ids = shortlist(profile)
    assert ids, "Shortlist returned no exercises"

    graph = PlanGraph()
    state = graph.invoke(profile)
    plan = state["plan_res"].plan  # type: ignore[index]

    assert len(plan.days) == profile.days_per_week
    total_ex = sum(len(d.exercises) for d in plan.days)
    assert total_ex > 0

    csv_bytes = to_csv(plan)
    md_text = to_markdown(plan)
    assert isinstance(csv_bytes, (bytes, bytearray)) and len(csv_bytes) > 0
    assert isinstance(md_text, str) and len(md_text) > 0
