from __future__ import annotations

import json
import hashlib
from typing import Dict, List

import streamlit as st

from app.agents.graph import PlanGraph
from app.models import UserProfile
from app.models.exercise import Equipment
from app.services.allowed_exercises import shortlist
from app.services.catalog import load_catalog
from app.services.export import to_csv, to_markdown
from app.services.planner_local import replace_one_exercise
from app.config import get_settings

st.set_page_config(page_title="Gym Planner", page_icon="🏋️", layout="wide")


def get_all_muscles() -> List[str]:
    muscles: set[str] = set()
    for ex in load_catalog():
        for m in ex.primary_muscles:
            muscles.add(m)
    return sorted(muscles)


def profile_hash(profile: UserProfile | None) -> str:
    if profile is None:
        return "unknown"
    data = profile.model_dump(mode="json")
    data_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(data_str.encode("utf-8")).hexdigest()[:10]


if "plan" not in st.session_state:
    st.session_state["plan"] = None
if "profile" not in st.session_state:
    st.session_state["profile"] = None

st.title("Gym Plan Creator")

with st.sidebar:
    st.header("Profile")
    goal = st.selectbox("Goal", ["hypertrophy", "strength", "hybrid"], index=0)
    days_per_week = st.slider("Days per week", min_value=1, max_value=6, value=3)
    session_minutes_cap = st.slider("Session length cap (min)", 30, 120, 60, step=5)
    max_exercises_per_day = st.slider("Max exercises per day", 3, 10, 5)
    default_sets = st.slider("Default sets", 2, 6, 3)
    default_reps = st.slider("Default reps", 3, 15, 10)
    rest_seconds = st.slider("Rest (seconds)", 30, 240, 90, step=15)
    supersets_enabled = st.toggle("Supersets enabled", value=False)
    progressive_overload = st.toggle("Progressive overload", value=False)

    equipment_all = list(Equipment.__args__)  # type: ignore[attr-defined]
    allowed_equipment = st.multiselect("Allowed equipment (optional)", equipment_all, default=[])
    blacklisted_equipment = st.multiselect("Blacklisted equipment (optional)", equipment_all, default=[])

    muscles_all = get_all_muscles()
    emphasis_sel = st.multiselect("Emphasis muscles (checkbox)", muscles_all, default=[])
    blacklisted_muscles = st.multiselect("Blacklisted muscles (optional)", muscles_all, default=[])

    # Build emphasis map 0/1
    emphasis_map: Dict[str, int] = {m: (1 if m in emphasis_sel else 0) for m in muscles_all}

    profile = UserProfile(
        goal=goal,
        days_per_week=days_per_week,
        session_minutes_cap=session_minutes_cap,
        max_exercises_per_day=max_exercises_per_day,
        default_sets=default_sets,
        default_reps=default_reps,
        rest_seconds=rest_seconds,
        supersets_enabled=supersets_enabled,
        progressive_overload=progressive_overload,
        allowed_equipment=allowed_equipment,  # type: ignore[arg-type]
        blacklisted_equipment=blacklisted_equipment,  # type: ignore[arg-type]
        emphasis=emphasis_map,
        blacklisted_muscles=blacklisted_muscles,
        blacklisted_exercise_ids=[],
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Generate plan", use_container_width=True):
            ids = shortlist(profile)
            if not ids:
                st.error("No exercises available with the current constraints. Adjust filters and try again.")
            else:
                graph = PlanGraph()
                state = graph.invoke(profile)
                st.session_state["plan"] = state["plan_res"].plan  # type: ignore[index]
                st.session_state["profile"] = profile
                st.toast("Plan generated.")
    with col_b:
        if st.button("Regenerate (clear)", use_container_width=True):
            st.session_state["plan"] = None
            st.session_state["profile"] = None

plan = st.session_state.get("plan")
current_profile: UserProfile | None = st.session_state.get("profile")

if plan is None:
    st.info("Use the sidebar to create a profile and click Generate plan.")
else:
    st.subheader(f"Plan — {len(plan.days)} days (Profile {profile_hash(current_profile)})")

    # Downloads
    csv_bytes = to_csv(plan)
    md_text = to_markdown(plan)
    col1, col2, col3 = st.columns([1,1,6])
    with col1:
        st.download_button("Download CSV", data=csv_bytes, file_name="gym_plan.csv", mime="text/csv")
    with col2:
        st.download_button("Download Markdown", data=md_text, file_name="gym_plan.md", mime="text/markdown")

    # Simple local explanation
    with st.expander("Explanation", expanded=False):
        overall = f"This plan targets your goal of {current_profile.goal} with {len(plan.days)} sessions focusing on variety and your emphasized muscles."
        day_summaries = []
        for day in plan.days:
            musc = sorted({m for ex in day.exercises for m in ex.primary_muscles})
            day_summaries.append(f"Day {day.day_index+1} covers: {', '.join(musc)}")
        st.write(overall)
        for s in day_summaries:
            st.write("- " + s)

    # Per-day display
    muscle_emojis: Dict[str, str] = {}
    for day in plan.days:
        with st.expander(f"Day {day.day_index + 1}: {day.label}"):
            st.caption(f"Sets: {day.sets}  Reps: {day.reps}  Rest: {day.rest_seconds}s")
            for ex in day.exercises:
                cols = st.columns([5, 3, 2])
                with cols[0]:
                    st.markdown(f"**[{ex.name}]({ex.exrx_url})**")
                    st.caption(f"{', '.join(ex.primary_muscles)} · {ex.function} · {', '.join(ex.equipment)}")
                with cols[1]:
                    st.empty()
                with cols[2]:
                    if st.button("Change", key=f"chg-{day.day_index}-{ex.id}"):
                        allowed_ids = shortlist(current_profile)
                        st.session_state["plan"] = replace_one_exercise(
                            current_profile, st.session_state["plan"], day.day_index, ex.id, allowed_ids
                        )
                        st.rerun()

st.markdown("---")
settings = get_settings()
if settings.GROQ_API_KEY:
    st.caption("LLM mode enabled — Groq structured outputs for generate/validate/repair with local fallback.")
else:
    st.caption("Local mode — using built-in planner/validator. Set GROQ_API_KEY to enable LLM.")
