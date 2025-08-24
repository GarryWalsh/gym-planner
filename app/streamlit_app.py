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
from app.services.llm_jobs import explain_plan_llm, replace_exercise_llm, answer_plan_question_llm

st.set_page_config(page_title="Gym Planner", page_icon="🏋️", layout="wide")
settings = get_settings()

# Minimal styling for exercise cards and chips
st.markdown(
    """
    <style>
    /* Compact exercise cards */
    .ex-card {padding:8px 10px; border:1px solid #e6e6e6; border-radius:8px; margin-bottom:8px; background:#fafafa;}
    .chips {margin-top:4px;}
    .chip {display:inline-block; padding:2px 8px; margin:2px 6px 2px 0; background:#eef2f7; border-radius:12px; font-size:12px; color:#334155;}
    .chip.fn {background:#e7f5ff; color:#1e3a8a;}
    .chip.eq {background:#f1f5f9;}
    a.exlink {color:#0f172a; text-decoration:none; font-weight:600;}
    a.exlink:hover {text-decoration:underline;}

    /* Prevent checkbox labels from wrapping letter-by-letter */
    .stCheckbox label { white-space: nowrap; }

    /* Tighter checkbox spacing in the sidebar */
    section[data-testid="stSidebar"] .stCheckbox { margin-bottom: 0.2rem; }
    section[data-testid="stSidebar"] label[data-baseweb="checkbox"] { margin-bottom: 0.1rem; }
    /* Override common layout gap class if present */
    section[data-testid="stSidebar"] .st-emotion-cache-tn0cau { gap: 0.25rem !important; }
    /* Generic vertical block gap reduction in sidebar */
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] { gap: 0.25rem !important; }

    /* Small vertical nudge for header/right-aligned popovers */
    .header-right button { margin-top: 6px; }
    .qa-right button { margin-top: 4px; margin-left: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_all_muscles() -> List[str]:
    muscles: set[str] = set()
    for ex in load_catalog():
        for m in ex.primary_muscles:
            muscles.add(m)
    return sorted(muscles)


def pretty_text(s: str) -> str:
    """Prettify identifiers like 'front_delts' or 'horizontal_push' for UI display."""
    return s.replace("_", " ").replace("-", " ").title()


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

header_cols = st.columns([9, 1])
with header_cols[0]:
    st.title("Gym Plan Creator")
with header_cols[1]:
    st.markdown("<div class='header-right'>", unsafe_allow_html=True)
    with st.popover("ℹ️ Info"):
        st.markdown("""
            Welcome! This tool builds a weekly gym plan from a curated exercise catalog (with ExRx links).
            
            What happens when you click Generate:
            - We shortlist exercises that match your equipment and muscle choices.
            - A plan is created with simple, balanced days and no duplicates within a day.
            - If you’ve set a GROQ_API_KEY, an LLM double‑checks and lightly repairs the plan using strict JSON outputs. Otherwise a local checker runs.
            - You can swap or remove individual exercises at any time.
            
            Notes on privacy & safety:
            - We only use your selections and exercise metadata; no personal data is sent.
            - LLM responses are strictly schema‑validated before being shown.
            """)
    st.markdown("</div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("Profile")
    goal = st.selectbox("Goal", ["Hypertrophy", "Strength", "Hybrid"], index=0)
    days_per_week = st.slider("Days per week", min_value=1, max_value=6, value=3)
    session_minutes_cap = st.slider("Session length cap (min)", 30, 120, 60, step=5)
    max_exercises_per_day = st.slider("Max exercises per day", 3, 10, 5)
    # Prescription removed from UI; using internal defaults
    default_sets = 3
    default_reps = 10
    rest_seconds = 90


    # Checkbox grid helpers for better UX
    def _slug(s: str) -> str:
        return s.lower().replace(" ", "_").replace("/", "_")

    def checkbox_grid(prefix: str, label: str, options: List[str], default_selected: List[str]) -> List[str]:
        st.caption(label)
        # Initialize defaults before rendering any checkbox widgets
        for opt in options:
            key = f"{prefix}-cb-{_slug(opt)}"
            if key not in st.session_state:
                st.session_state[key] = opt in default_selected
        # Select/Clear controls
        ctrl1, ctrl2 = st.columns([1, 1])
        if ctrl1.button("Select all", key=f"{prefix}-select-all"):
            for opt in options:
                st.session_state[f"{prefix}-cb-{_slug(opt)}"] = True
            st.rerun()
        if ctrl2.button("Clear all", key=f"{prefix}-clear-all"):
            for opt in options:
                st.session_state[f"{prefix}-cb-{_slug(opt)}"] = False
            st.rerun()
        selected: List[str] = []
        for opt in options:
            key = f"{prefix}-cb-{_slug(opt)}"
            # Use key only; do not pass value= when using session_state
            val = st.checkbox(pretty_text(opt), key=key)
            if val:
                selected.append(opt)
        return selected

    equipment_all = list(Equipment.__args__)  # type: ignore[attr-defined]
    selected_equipment = checkbox_grid("eq", "Equipment", equipment_all, equipment_all)

    muscles_all_raw = get_all_muscles()
    selected_muscles = checkbox_grid("ms", "Muscles", muscles_all_raw, muscles_all_raw)

    # Build emphasis map 0/1 from selected muscles and derive blacklist as complement
    emphasis_map: Dict[str, int] = {m: (1 if m in selected_muscles else 0) for m in muscles_all_raw}
    blacklisted_muscles = [m for m in muscles_all_raw if m not in selected_muscles]

    profile = UserProfile(goal=goal, days_per_week=days_per_week, session_minutes_cap=session_minutes_cap,
                          max_exercises_per_day=max_exercises_per_day, default_sets=default_sets,
                          default_reps=default_reps, rest_seconds=rest_seconds, allowed_equipment=selected_equipment,
                          # type: ignore[arg-type]
                          blacklisted_equipment=[],  # single selector UX; blacklist derived from deselection if needed
                          emphasis=emphasis_map, blacklisted_muscles=blacklisted_muscles, blacklisted_exercise_ids=[], )

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
    st.subheader(f"{len(plan.days)} Day Plan")

    # Single-row actions: plan options left, export right
    csv_bytes = to_csv(plan)
    md_text = to_markdown(plan)
    pdf_bytes = b""
    pdf_error = None
    try:
        pdf_bytes = to_pdf(plan)
    except Exception as _e:  # pragma: no cover
        pdf_error = str(_e)

    # Toolbar: left actions (Regenerate, Clear), right exports (CSV/MD/PDF)
    with st.container():
        left_zone, spacer_zone, right_zone = st.columns([6, 2, 6])
        with left_zone:
            a1, a2 = st.columns([2, 1])
            with a1:
                if st.button("🔁 Regenerate plan", key="btn-regenerate", use_container_width=True, type="secondary"):
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
            with a2:
                if st.button("🧹 Clear plan", key="btn-clear", use_container_width=True):
                    st.session_state["plan"] = None
                    st.session_state["profile"] = None
                    st.toast("Cleared.")
                    st.rerun()
        with right_zone:
            d1, d2, d3 = st.columns(3)
            with d1:
                st.download_button("📄 CSV", data=csv_bytes, file_name="gym_plan.csv", mime="text/csv", use_container_width=True)
            with d2:
                st.download_button("📝 Markdown", data=md_text, file_name="gym_plan.md", mime="text/markdown", use_container_width=True)
            with d3:
                if pdf_bytes:
                    st.download_button("📘 PDF", data=pdf_bytes, file_name="gym_plan.pdf", mime="application/pdf", use_container_width=True)
                elif pdf_error:
                    st.caption("PDF unavailable: " + pdf_error)

    # Fitness Q&A (strictly validated)
    st.markdown("\n")
    with st.container():
        hdr = st.columns([9, 1])
        with hdr[0]:
            st.subheader("Ask about your plan")
        with hdr[1]:
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
                            musc_pretty = [pretty_text(m) for m in musc]
                            day_summaries.append(f"Day {day.day_index + 1}: {', '.join(musc_pretty)}")
                else:
                    day_summaries = []
                    overall = f"Your plan supports a {current_profile.goal} goal with {len(plan.days)} sessions, balancing major muscle groups and your selections."
                    for day in plan.days:
                        musc = sorted({m for ex in day.exercises for m in ex.primary_muscles})
                        musc_pretty = [pretty_text(m) for m in musc]
                        day_summaries.append(f"Day {day.day_index + 1}: {', '.join(musc_pretty)}")
                st.markdown(f"**Overview:** {overall}")
                st.markdown("**By day:**")
                for s in day_summaries:
                    st.markdown(f"- {s}")

        # Inline form so Enter submits, with Ask button on the same line
        with st.form("qa-form", clear_on_submit=False):
            row = st.columns([8, 1])
            with row[0]:
                q = st.text_input("Ask about your plan", value="",
                                  placeholder="e.g. Which days train chest? Where are legs trained?",
                                  key="qa-input", label_visibility="collapsed", )
            with row[1]:
                submitted = st.form_submit_button("❓ Ask", use_container_width=True)
        if submitted:
            def _is_valid_question(text: str) -> tuple[bool, str | None]:
                t = (text or "").strip()
                if len(t) < 5 or len(t) > 300:
                    return False, "Please enter a concise question (5–300 chars)."
                lower = t.lower()
                if "http://" in lower or "https://" in lower or "www." in lower or "@" in lower:
                    return False, "Links, emails, or external references are not allowed."
                fitness_kw = {"exercise", "exercises", "set", "sets", "rep", "reps", "rest", "muscle", "muscles",
                              "volume", "frequency", "intensity", "superset", "warmup", "cooldown", "day", "plan",
                              "chest", "back", "legs", "shoulders", "biceps", "triceps", "quads", "hamstrings",
                              "glutes", "calves", "core", "abs"}
                has_kw = any(k in lower for k in fitness_kw)
                return (True, None) if has_kw else (False, "Only fitness-related questions are allowed.")


            ok, err = _is_valid_question(q)
            if not ok:
                st.error(err)
            else:
                answer_text: str | None = None
                if settings.GROQ_API_KEY:
                    try:
                        qa = answer_plan_question_llm(current_profile, plan, q)  # type: ignore[arg-type]
                        answer_text = (qa.answer or "").strip()
                    except Exception:
                        answer_text = None
                if not answer_text:
                    # Local fallback based on the current plan
                    def _answer(text: str) -> str:
                        lower = text.lower()
                        lines = []
                        if any(x in lower for x in ["day", "which", "when"]):
                            for day in plan.days:
                                musc = sorted({m for ex in day.exercises for m in ex.primary_muscles})
                                musc_pretty = [pretty_text(m) for m in musc]
                                lines.append(f"Day {day.day_index + 1} ({day.label}) covers: {', '.join(musc_pretty)}")
                        muscles = sorted({m.lower() for d in plan.days for ex in d.exercises for m in
                                          ex.primary_muscles}) if plan.days else []
                        target_muscles = [m for m in muscles if m in lower]
                        if target_muscles:
                            for tm in target_muscles:
                                hits = []
                                for day in plan.days:
                                    exes = [ex.name for ex in day.exercises if
                                            tm in [mm.lower() for mm in ex.primary_muscles]]
                                    if exes:
                                        hits.append(f"Day {day.day_index + 1}: " + ", ".join(exes))
                                if hits:
                                    lines.append(f"Muscle '{pretty_text(tm)}' appears in → " + " | ".join(hits))
                        if any(x in lower for x in ["set", "sets", "rep", "reps", "rest"]):
                            lines.append("This MVP focuses on exercise selection; sets/reps/rest are not configured in the UI.")
                        if not lines:
                            lines.append(
                                "This plan is designed around your selections. Try asking about muscles (e.g., chest) or which days cover a body part.")
                        return "\n".join(lines)


                    answer_text = _answer(q)
                st.info(answer_text)

    # Per-day display
    muscle_emojis: Dict[str, str] = {}
    for day in plan.days:
        with st.expander(f"Day {day.day_index + 1}: {day.label}"):
            for idx, ex in enumerate(day.exercises):
                cols = st.columns([10, 2])
                with cols[0]:
                    html = "<div class='ex-card'>"
                    html += f"<a class='exlink' href='{ex.exrx_url}' target='_blank'>{ex.name}</a>"
                    chips_m = "".join(f"<span class='chip'>{pretty_text(m)}</span>" for m in ex.primary_muscles)
                    chip_fn = f"<span class='chip fn'>{pretty_text(ex.function)}</span>"
                    chips_eq = "".join(f"<span class='chip eq'>{pretty_text(e)}</span>" for e in ex.equipment)
                    html += f"<div class='chips'>{chips_m}{chip_fn}{chips_eq}</div>"
                    html += "</div>"
                    st.markdown(html, unsafe_allow_html=True)
                with cols[1]:
                    if st.button("🔀 Swap", key=f"chg-{day.day_index}-{idx}-{ex.id}", use_container_width=True):
                        allowed_ids = shortlist(current_profile)
                        if settings.GROQ_API_KEY:
                            try:
                                st.session_state["plan"] = replace_exercise_llm(current_profile,
                                                                                st.session_state["plan"], day.day_index,
                                                                                ex.id, allowed_ids)
                            except Exception:
                                st.session_state["plan"] = replace_one_exercise(current_profile,
                                                                                st.session_state["plan"], day.day_index,
                                                                                ex.id, allowed_ids)
                        else:
                            st.session_state["plan"] = replace_one_exercise(current_profile, st.session_state["plan"],
                                                                            day.day_index, ex.id, allowed_ids)
                        st.rerun()
                    if st.button("🗑 Remove", key=f"rm-{day.day_index}-{idx}-{ex.id}", use_container_width=True):
                        # Remove this exercise from the day and recompute weekly focus
                        _plan = st.session_state.get("plan")
                        if _plan is not None:
                            _day = _plan.days[day.day_index]
                            # remove by id (first match)
                            for _j, _e in enumerate(_day.exercises):
                                if _e.id == ex.id:
                                    del _day.exercises[_j]
                                    break
                            # recompute weekly_focus
                            _counts: Dict[str, int] = {}
                            for _d in _plan.days:
                                for _ex in _d.exercises:
                                    for _m in _ex.primary_muscles:
                                        _counts[_m] = _counts.get(_m, 0) + 1
                            _plan.weekly_focus = _counts
                            st.session_state["plan"] = _plan
                            st.toast("Exercise removed.")
                            st.rerun()
