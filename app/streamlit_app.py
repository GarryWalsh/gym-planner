from __future__ import annotations

# Ensure the repository root is on sys.path so that absolute imports like `app.*` work
# when Streamlit runs this file from within the app/ directory on cloud runtimes.
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import hashlib
from typing import Dict, List

import streamlit as st

from app.agents.graph import PlanGraph
from app.models import UserProfile
from app.models.exercise import Equipment
from app.services.allowed_exercises import shortlist
from app.services.catalog import load_catalog
from app.services.export import to_csv, to_markdown, to_pdf
from app.services.planner_local import replace_one_exercise
from app.config import get_settings
from app.services.llm_jobs import explain_plan_llm, replace_exercise_llm

st.set_page_config(page_title="Gym Planner", page_icon="🏋️", layout="wide")
settings = get_settings()


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
# Info popover explaining how LLM is used
info_cols = st.columns([8, 1])
with info_cols[1]:
    with st.popover("ℹ️ Info"):
        st.markdown(
            """
            This app creates a weekly gym plan from a local ExRx-linked exercise catalog.
            
            How it works:
            - Allowed list: filters the catalog by your equipment and muscle choices.
            - Generate: builds a balanced plan (push/pull/legs/full-body variety) with no per-day duplicates.
            - Validate & Repair: if LLM is enabled (GROQ_API_KEY set), the plan is checked and minimally fixed via structured outputs; otherwise a local validator runs.
            - Explain & Replace: summary and single-exercise swap can use the LLM when available, with a local fallback.
            
            Privacy & Safety:
            - No uploads of personal data; only your selections and exercise metadata are used.
            - All LLM responses are schema-enforced JSON, then rendered here.
            """
        )

with st.sidebar:
    st.header("Profile")
    goal = st.selectbox("Goal", ["hypertrophy", "strength", "hybrid"], index=0)
    days_per_week = st.slider("Days per week", min_value=1, max_value=6, value=3)
    session_minutes_cap = st.slider("Session length cap (min)", 30, 120, 60, step=5)
    max_exercises_per_day = st.slider("Max exercises per day", 3, 10, 5)
    default_sets = st.slider("Default sets", 2, 6, 3)
    default_reps = st.slider("Default reps", 3, 15, 10)
    rest_seconds = st.slider("Rest (seconds)", 30, 240, 90, step=15)

    # Helper: pill groups (fallback to multiselect if unavailable)
    def pills_or_multiselect(label: str, options: List[str], default: List[str]) -> List[str]:
        try:
            pills_fn = getattr(st, "pills", None)
            if pills_fn:
                try:
                    result = pills_fn(label, options=options, selection=default)
                except TypeError:
                    # older signature
                    result = pills_fn(label, options, default=default)
                # If the widget returns a non-list (e.g., single selection), fall back to multiselect for multi-choice UX
                if not isinstance(result, (list, tuple, set)):
                    raise TypeError("pills returned single selection; need multi-select")
                return list(result)
        except Exception:
            pass
        return st.multiselect(label, options, default=default)

    equipment_all = list(Equipment.__args__)  # type: ignore[attr-defined]
    selected_equipment = pills_or_multiselect("Equipment", equipment_all, equipment_all)

    muscles_all = get_all_muscles()
    selected_muscles = pills_or_multiselect("Muscles", muscles_all, muscles_all)

    # Build emphasis map 0/1 from selected muscles and derive blacklist as complement
    emphasis_map: Dict[str, int] = {m: (1 if m in selected_muscles else 0) for m in muscles_all}
    blacklisted_muscles = [m for m in muscles_all if m not in selected_muscles]

    profile = UserProfile(
        goal=goal,
        days_per_week=days_per_week,
        session_minutes_cap=session_minutes_cap,
        max_exercises_per_day=max_exercises_per_day,
        default_sets=default_sets,
        default_reps=default_reps,
        rest_seconds=rest_seconds,
        allowed_equipment=selected_equipment,  # type: ignore[arg-type]
        blacklisted_equipment=[],  # single selector UX; blacklist derived from deselection if needed
        emphasis=emphasis_map,
        blacklisted_muscles=blacklisted_muscles,
        blacklisted_exercise_ids=[],
    )

    if st.button("Generate plan", use_container_width=True):
        ids = shortlist(profile)
        if not ids:
            st.error("No exercises available with the current constraints. Adjust filters and try again.")
        else:
            import time as _time
            graph = PlanGraph()
            seed = int(_time.time() * 1000) & 0x7FFFFFFF
            state = graph.invoke(profile, seed=seed)
            st.session_state["plan"] = state["plan_res"].plan  # type: ignore[index]
            st.session_state["profile"] = profile
            st.toast("Plan generated.")

plan = st.session_state.get("plan")
current_profile: UserProfile | None = st.session_state.get("profile")

if plan is None:
    st.info("Use the sidebar to create a profile and click Generate plan.")
else:
    st.subheader(f"Plan — {len(plan.days)} days (Profile {profile_hash(current_profile)})")

    # Single-row actions: plan options left, export right
    csv_bytes = to_csv(plan)
    md_text = to_markdown(plan)
    pdf_bytes = b""
    pdf_error = None
    try:
        pdf_bytes = to_pdf(plan)
    except Exception as _e:  # pragma: no cover
        pdf_error = str(_e)

    left1, left2, spacer, right1, right2, right3 = st.columns([1, 1, 6, 1, 1, 1])
    with left1:
        if st.button("🔁 Regenerate plan", key="btn-regenerate", use_container_width=True):
            ids = shortlist(profile)
            if not ids:
                st.error("No exercises available with the current constraints. Adjust filters and try again.")
            else:
                import time as _time
                graph = PlanGraph()
                seed = int(_time.time() * 1000) & 0x7FFFFFFF
                state = graph.invoke(profile, seed=seed)
                st.session_state["plan"] = state["plan_res"].plan  # type: ignore[index]
                st.session_state["profile"] = profile
                st.toast("Plan regenerated.")
                st.rerun()
    with left2:
        if st.button("🧹 Clear plan", key="btn-clear", use_container_width=True):
            st.session_state["plan"] = None
            st.session_state["profile"] = None
            st.toast("Cleared.")
            st.rerun()
    with right1:
        st.download_button("📄 CSV", data=csv_bytes, file_name="gym_plan.csv", mime="text/csv")
    with right2:
        st.download_button("📝 Markdown", data=md_text, file_name="gym_plan.md", mime="text/markdown")
    with right3:
        if pdf_bytes:
            st.download_button("📘 PDF", data=pdf_bytes, file_name="gym_plan.pdf", mime="application/pdf")
        elif pdf_error:
            st.caption("PDF unavailable: " + pdf_error)

    # Fitness Q&A (strictly validated)
    st.markdown("\n")
    with st.container():
        st.subheader("Ask about your plan")
        q = st.text_input("Question (fitness topics only)", value="", placeholder="e.g., Which days train chest? How many sets are in this plan?", key="qa-input")
        ask = st.button("❓ Ask", key="qa-ask")
        if ask:
            def _is_valid_question(text: str) -> tuple[bool, str | None]:
                t = (text or "").strip()
                if len(t) < 5 or len(t) > 300:
                    return False, "Please enter a concise question (5–300 chars)."
                lower = t.lower()
                # No URLs/emails
                if "http://" in lower or "https://" in lower or "www." in lower or "@" in lower:
                    return False, "Links, emails, or external references are not allowed."
                # Require fitness-related keywords or muscles
                fitness_kw = {
                    "exercise","exercises","set","sets","rep","reps","rest","muscle","muscles",
                    "volume","frequency","intensity","superset","warmup","cooldown","day","plan",
                    "chest","back","legs","shoulders","biceps","triceps","quads","hamstrings","glutes","calves","core","abs"
                }
                has_kw = any(k in lower for k in fitness_kw)
                return (True, None) if has_kw else (False, "Only fitness-related questions are allowed.")

            ok, err = _is_valid_question(q)
            if not ok:
                st.error(err)
            else:
                # Build a safe local answer based on the current plan
                def _answer(text: str) -> str:
                    lower = text.lower()
                    lines = []
                    # Summaries per day
                    if any(x in lower for x in ["day","which","when"]):
                        for day in plan.days:
                            musc = sorted({m for ex in day.exercises for m in ex.primary_muscles})
                            lines.append(f"Day {day.day_index+1} ({day.label}) covers: {', '.join(musc)}")
                    # Muscles mentioned
                    muscles = sorted({m.lower() for d in plan.days for ex in d.exercises for m in ex.primary_muscles}) if plan.days else []
                    target_muscles = [m for m in muscles if m in lower]
                    if target_muscles:
                        for tm in target_muscles:
                            hits = []
                            for day in plan.days:
                                exes = [ex.name for ex in day.exercises if tm in [mm.lower() for mm in ex.primary_muscles]]
                                if exes:
                                    hits.append(f"Day {day.day_index+1}: " + ", ".join(exes))
                            if hits:
                                lines.append(f"Muscle '{tm}' appears in → " + " | ".join(hits))
                    # Sets/reps/rest
                    if any(x in lower for x in ["set","sets","rep","reps","rest"]):
                        if plan.days:
                            d0 = plan.days[0]
                            lines.append(f"Default prescription: {d0.sets} sets × {d0.reps} reps; rest {d0.rest_seconds}s.")
                    if not lines:
                        lines.append("This plan is designed around your selections. Try asking about muscles (e.g., chest), days, or sets/reps/rest.")
                    return "\n".join(lines)

                st.info(_answer(q))

    # Plan summary popover (LLM if available, else local)
    summary_cols = st.columns([8, 1])
    with summary_cols[1]:
        with st.popover("🧠 Summary"):
            overall: str
            day_summaries: List[str]
            if settings.GROQ_API_KEY:
                try:
                    exr = explain_plan_llm(current_profile, plan)  # type: ignore[arg-type]
                    overall = exr.overall
                    day_summaries = exr.day_summaries
                except Exception:
                    day_summaries = []
                    overall = f"Your plan supports a {current_profile.goal} goal with {len(plan.days)} sessions, balancing major muscle groups and your selections."
                    for day in plan.days:
                        musc = sorted({m for ex in day.exercises for m in ex.primary_muscles})
                        day_summaries.append(f"Day {day.day_index+1}: {', '.join(musc)}")
            else:
                day_summaries = []
                overall = f"Your plan supports a {current_profile.goal} goal with {len(plan.days)} sessions, balancing major muscle groups and your selections."
                for day in plan.days:
                    musc = sorted({m for ex in day.exercises for m in ex.primary_muscles})
                    day_summaries.append(f"Day {day.day_index+1}: {', '.join(musc)}")
            st.markdown(f"**Overview:** {overall}")
            st.markdown("**By day:**")
            for s in day_summaries:
                st.markdown(f"- {s}")

    # Per-day display
    muscle_emojis: Dict[str, str] = {}
    for day in plan.days:
        with st.expander(f"Day {day.day_index + 1}: {day.label}"):
            st.caption(f"Sets: {day.sets}  Reps: {day.reps}  Rest: {day.rest_seconds}s")
            for idx, ex in enumerate(day.exercises):
                cols = st.columns([5, 3, 2])
                with cols[0]:
                    st.markdown(f"**[{ex.name}]({ex.exrx_url})**")
                    st.caption(f"{', '.join(ex.primary_muscles)} · {ex.function} · {', '.join(ex.equipment)}")
                with cols[1]:
                    st.empty()
                with cols[2]:
                    if st.button("Change", key=f"chg-{day.day_index}-{idx}-{ex.id}"):
                        allowed_ids = shortlist(current_profile)
                        if settings.GROQ_API_KEY:
                            try:
                                st.session_state["plan"] = replace_exercise_llm(
                                    current_profile, st.session_state["plan"], day.day_index, ex.id, allowed_ids
                                )
                            except Exception:
                                st.session_state["plan"] = replace_one_exercise(
                                    current_profile, st.session_state["plan"], day.day_index, ex.id, allowed_ids
                                )
                        else:
                            st.session_state["plan"] = replace_one_exercise(
                                current_profile, st.session_state["plan"], day.day_index, ex.id, allowed_ids
                            )
                        st.rerun()
