from __future__ import annotations

from app.agents.graph import PlanGraph
from app.models import UserProfile
from app.services.export import to_pdf


def test_export_pdf() -> None:
    profile = UserProfile(
        goal="hypertrophy",
        days_per_week=2,
        session_minutes_cap=60,
        max_exercises_per_day=4,
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

    pdf_bytes = to_pdf(plan)
    assert isinstance(pdf_bytes, (bytes, bytearray)) and len(pdf_bytes) > 1000, "PDF export seems too small or empty"
