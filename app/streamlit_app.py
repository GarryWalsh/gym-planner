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
import app.llm.groq_client as groq_debug
from app.auth import require_login

st.set_page_config(page_title="Gym Planner", page_icon="🏋️", layout="wide")
settings = get_settings()
require_login()

# ========= Global, robust CSS (APPLIES BEFORE ANY WIDGETS) =========
st.markdown("""
<style>
/* ─────────────────────────────────────────────────────────────────────────────
   CARD: Use a 2×2 CSS Grid
   rows:   title | actions
           chips | actions
   The actions column spans both rows and is right-aligned.
   ───────────────────────────────────────────────────────────────────────────── */

div[data-testid="stVerticalBlockBorderWrapper"]{
  /* Trim the bordered container’s padding so the row doesn’t “float” */
  padding: .20rem .85rem !important;
}

/* Title styling */
.ex-title{
  margin: 0 !important;
  display: flex; align-items: center;
  line-height: 30px;                                /* matches button height */
  font-weight: 700; font-size: 1.08rem;
}
a.exlink{ color: var(--text-color, inherit) !important; text-decoration: none; }
a.exlink:hover{ text-decoration: underline; }

/* Chips row */
.chips{
  margin: 0;                                        /* no extra vertical push */
  display: flex; flex-wrap: wrap;
  gap: .24rem .38rem;
}
.chip{ padding:2px 8px; border-radius:999px; font-size:12px; background:#eef2f7; color:#334155; }
.chip.fn{ background:#e7f5ff; color:#1e3a8a; }
.chip.eq{ background:#f1f5f9; }

/* Compact, uniform buttons */
/* Make ALL action buttons the same size */
.stButton > button,
.stDownloadButton > button,
button[data-testid="baseButton-primary"],
button[data-testid="baseButton-secondary"],
/* Popover trigger buttons (st.popover) */
div[data-testid="stPopover"] > div > button,
button[aria-haspopup="dialog"] {
  display:inline-flex !important;
  align-items:center !important;
  justify-content:center !important;
  height:30px !important;
  min-height:30px !important;
  padding:0 .56rem !important;
  line-height:1.1 !important;
  white-space:nowrap !important;
}


/* ── Sidebar spacing (comfortable but not cramped) ─────────────────────────── */
[data-testid="stSidebar"] .stVerticalBlock{ gap:.55rem !important; }
[data-testid="stSidebar"] .stCheckbox{ margin-bottom:.34rem !important; }
.stCheckbox label{ white-space: nowrap; }

/* === Buttons: unified size (append this at the very bottom) === */
.stButton > button{
  height:30px !important;
  min-height:30px !important;
  min-width:36px !important;
  padding:0 .45rem !important;
}

/* Make the two grid rows (title | chips) size comfortably */
div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"]{
  grid-template-rows: minmax(30px, auto) auto;  /* first row ≥ 30px, chips row auto */
  row-gap: .25rem;                              /* a touch more breathing room */
}

/* Nudge the chips down slightly (optional but helps) */
.chips{ margin-top: .20rem; }

/* Extra breathing room only for exercise cards that have chips */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.chips){
  /* top | sides | bottom  → tweak the last value to taste */
  padding: .6rem .85rem 1.05rem !important;
}

/* Small margin below the chip row */
.chips{ margin-bottom: .35rem !important; }


/* If 7+ chips present, add a bit more bottom padding */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.chips .chip:nth-child(n+7)){
  padding-bottom: 1.25rem !important;
}


/* Chip row can wrap, with small top/bottom spacing */
.chips{
  display: flex; flex-wrap: wrap;
  gap: .24rem .38rem;
  margin: .15rem 0 .25rem 0;
}

/* Keep all small buttons a consistent height */
.stButton > button,
.stDownloadButton > button,
button[data-testid="baseButton-primary"],
button[data-testid="baseButton-secondary"]{
  height:30px !important; min-height:30px !important;
  min-width:36px !important; padding:0 .45rem !important;
}

/* extra space under the chip row */
.chips{ margin-bottom: 1rem !important; }

/* make the bordered card a touch taller globally */
div[data-testid="stVerticalBlockBorderWrapper"]{
  padding-bottom: 1rem !important;
}

/* Marker so we can target the Streamlit bordered wrapper */
.daybox-sentinel { display: none; }

/* Whole day container turns yellow */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.daybox-sentinel){
  background: #fff7cc !important;        /* amber wash */
  border: 1px solid #facc15 !important;
  border-radius: 14px !important;
  padding: .8rem 1rem !important;
}

/* Inside a yellow day container, make exercise rows “flat” so the whole card reads as one */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.daybox-sentinel) .ex-card{
  background: transparent !important;     /* remove tile background */
  border: 0 !important;                   /* no inner border */
  padding: 6px 0 !important;              /* keep nice spacing */
}

/* Optional: style the 3-dot menu trigger a bit */
div[data-testid="stPopover"] > div > button:has(> span.kebab){
  width: 30px; height: 30px; border-radius: 8px;
  background: rgba(0,0,0,.04);
  border: 1px solid rgba(0,0,0,.08);
}
div[data-testid="stPopover"] > div > button:has(> span.kebab):hover{
  background: rgba(0,0,0,.08);
}

</style>
""", unsafe_allow_html=True)
# ================================================================


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

with st.sidebar:
    st.header("AI Gym Plan Creator")
    goal = st.selectbox("Goal", ["hypertrophy", "strength", "hybrid"], index=0, format_func=lambda s: s.title())
    days_per_week = st.slider("Days per week", min_value=1, max_value=6, value=3)
    max_exercises_per_workout = st.slider("Max exercises per workout", 3, 10, 5)
    session_minutes_cap = st.slider("Session length (min)", 30, 120, 60, step=5)
    # Prescription removed from UI; using internal defaults
    default_sets = 3
    default_reps = 10
    rest_seconds = 90

    # Checkbox grid helpers for better UX
    def _slug(s: str) -> str:
        return s.lower().replace(" ", "_").replace("/", "_")

    def toggle_grid(prefix: str, label: str, options: List[str], default_selected: List[str], cols: int = 3) -> List[str]:
        """
        Render a compact multi-column toggle grid with Select/Clear controls.
        Uses session_state keys; no value= passed to widgets to avoid conflicts.
        """
        st.caption(label)

        # Initialize defaults before rendering any toggle widgets
        for opt in options:
            key = f"{prefix}-tg-{_slug(opt)}"
            if key not in st.session_state:
                st.session_state[key] = opt in default_selected

        # Select/Clear controls
        ctrl1, ctrl2 = st.columns([1, 1])
        if ctrl1.button("Select all", key=f"{prefix}-select-all", use_container_width=True):
            for opt in options:
                st.session_state[f"{prefix}-tg-{_slug(opt)}"] = True
            st.rerun()
        if ctrl2.button("Clear all", key=f"{prefix}-clear-all", use_container_width=True):
            for opt in options:
                st.session_state[f"{prefix}-tg-{_slug(opt)}"] = False
            st.rerun()

        # Multi-column grid of toggles
        selected: List[str] = []
        columns = st.columns(cols, gap="small")
        for i, opt in enumerate(options):
            key = f"{prefix}-tg-{_slug(opt)}"
            col = columns[i % cols]
            with col:
                if st.toggle(pretty_text(opt), key=key):
                    selected.append(opt)
        return selected

    equipment_all = list(Equipment.__args__)  # type: ignore[attr-defined]
    with st.expander("Equipment", expanded=False):
        selected_equipment = toggle_grid("eq", "", equipment_all, equipment_all, cols=2)

    muscles_all_raw = get_all_muscles()
    with st.expander("Muscles", expanded=False):
        selected_muscles = toggle_grid("ms", "", muscles_all_raw, muscles_all_raw, cols=2)

    # Build emphasis map 0/1 from selected muscles and derive blacklist as complement
    emphasis_map: Dict[str, int] = {m: (1 if m in selected_muscles else 0) for m in muscles_all_raw}
    blacklisted_muscles = [m for m in muscles_all_raw if m not in selected_muscles]

    profile = UserProfile(
        goal=goal,
        days_per_week=days_per_week,
        session_minutes_cap=session_minutes_cap,
        max_exercises_per_day=max_exercises_per_workout,
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
        import time as _time
        with st.spinner("Generating plan…"):
            ids = shortlist(profile)
            if not ids:
                st.error("No exercises available with the current constraints. Adjust filters and try again.")
            else:
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
    try:
        _src = (getattr(plan, "meta", {}) or {}).get("source")  # type: ignore[attr-defined]
    except Exception:
        _src = None
    if not _src:
        _src = "llm" if settings.GROQ_API_KEY else "local"
    badge = "🧠 Generated by AI" if _src == "llm" else "🛠️ Crafted Locally"
    st.markdown(f"<div style='text-align:right;padding-bottom:20px'>{badge}</div>", unsafe_allow_html=True)


    # Single-row actions: plan options left, export right
    csv_bytes = to_csv(plan)
    md_text = to_markdown(plan)
    pdf_bytes = b""
    pdf_error = None
    try:
        pdf_bytes = to_pdf(plan)
    except Exception as _e:  # pragma: no cover
        pdf_error = str(_e)

    # Toolbar: unified Actions (Regenerate/Clear) and Export (CSV/MD/PDF)
    with st.container():
        text_col, spacer_col, actions_col, how_col, export_col = st.columns([4, 4, 1, 2, 1])
        with text_col:
            st.subheader(f"Your {len(plan.days)} Day Plan")
        with actions_col:
            with st.popover("⚙️ Actions"):
                if st.button("🔁 Regenerate plan", key="btn-regenerate", use_container_width=True, type="secondary"):
                    import time as _time
                    with st.spinner("Regenerating plan…"):
                        ids = shortlist(profile)
                        if not ids:
                            st.error("No exercises available with the current constraints. Adjust filters and try again.")
                        else:
                            graph = PlanGraph()
                            seed = int(_time.time() * 1000) & 0x7FFFFFFF
                            state = graph.invoke(profile, seed=seed)
                            st.session_state["plan"] = state["plan_res"].plan  # type: ignore[index]
                            st.session_state["profile"] = profile
                            st.toast("Plan regenerated.")
                    st.rerun()
                if st.button("🧹 Clear plan", key="btn-clear", use_container_width=True):
                    st.session_state["plan"] = None
                    st.session_state["profile"] = None
                    st.toast("Cleared.")
                    st.rerun()
        with how_col:
            with st.popover("ℹ️ How it works"):
                tab_summary, tab_how = st.tabs(["Summary", "How it works"])
                with tab_how:
                    st.markdown(
                        """
                        **How it works (in plain English):**
                        - You choose your goal, days, equipment, and muscles. 
                        - Our AI builds a weekly plan tailored to those choices using a curated exercise catalog (with ExRx links).
                        - The AI then checks the plan against your limits (days, max exercises per day, equipment filters) and lightly fixes issues.
                        - No personal data is sent beyond your selections and the plan itself; all AI responses are strict JSON and validated before display.
                        - You can swap or remove exercises any time and download to CSV/Markdown/PDF.
                        """
                    )
                with tab_summary:
                    overall: str
                    day_summaries: List[str]
                    summary_llm: bool = False
                    if settings.GROQ_API_KEY:
                        try:
                            with st.spinner("Summarizing plan via LLM…"):
                                exr = explain_plan_llm(current_profile, plan)  # type: ignore[arg-type]
                                overall = exr.overall
                                day_summaries = exr.day_summaries
                                summary_llm = True
                        except Exception:
                            day_summaries = []
                            overall = f"Your plan supports a {current_profile.goal} goal with {len(plan.days)} sessions, balancing major muscle groups and your selections."
                            for d in plan.days:
                                musc = sorted({m for ex in d.exercises for m in ex.primary_muscles})
                                musc_pretty = [pretty_text(m) for m in musc]
                                day_summaries.append(f"Day {d.day_index + 1}: {', '.join(musc_pretty)}")
                    else:
                        day_summaries = []
                        overall = f"Your plan supports a {current_profile.goal} goal with {len(plan.days)} sessions, balancing major muscle groups and your selections."
                        for d in plan.days:
                            musc = sorted({m for ex in d.exercises for m in ex.primary_muscles})
                            musc_pretty = [pretty_text(m) for m in musc]
                            day_summaries.append(f"Day {d.day_index + 1}: {', '.join(musc_pretty)}")

                    # Local reasoning bullets
                    try:
                        eq_txt = ", ".join(pretty_text(e) for e in (current_profile.allowed_equipment or [])) if current_profile else ""
                        emphasized = [m for m, v in (getattr(current_profile, "emphasis", {}) or {}).items() if v == 1] if current_profile else []
                        covered = [m for m in emphasized if plan.weekly_focus.get(m, 0) > 0]
                        functions = sorted({getattr(ex, "function", "") for d in plan.days for ex in d.exercises}) if plan.days else []
                        mx = getattr(current_profile, "max_exercises_per_day", None)
                        cap = getattr(current_profile, "session_minutes_cap", None)
                        reasoning = []
                        if functions:
                            reasoning.append(f"Balanced variety of movement patterns ({', '.join(pretty_text(f) for f in functions)}) across the week.")
                        if eq_txt:
                            reasoning.append(f"Matches your equipment selections: {eq_txt}.")
                        if emphasized:
                            if covered:
                                pretty_cov = ", ".join(pretty_text(m) for m in covered)
                                reasoning.append(f"Honors your focus areas — included: {pretty_cov}.")
                            else:
                                reasoning.append("Attempts to honor your muscle focus while respecting other constraints.")
                        reasoning.append("Avoids duplicate exercises within each session to keep training fresh.")
                        if mx:
                            reasoning.append(f"Keeps each day within your max of {mx} exercises")
                        if cap:
                            reasoning.append(f"and targets efficient sessions around {cap} minutes.")
                        if mx and cap and len(reasoning) >= 2 and reasoning[-2].endswith("exercises") and reasoning[-1].startswith("and "):
                            merged = reasoning[-2] + ", " + reasoning[-1]
                            reasoning = reasoning[:-2] + [merged]
                    except Exception:
                        reasoning = [
                            "Balanced selection across major muscle groups.",
                            "Respects your equipment constraints.",
                            "No duplicates per day for better quality volume.",
                        ]

                    st.markdown("**Overview:**")
                    st.markdown("\n".join({overall}))
                    _sum_badge = "🧠 Generated by AI" if summary_llm else "🛠️ Crafted locally"
                    st.markdown("<div style='text-align:right'><span style='font-size:12px;color:#64748b'>" + _sum_badge + "</span></div>", unsafe_allow_html=True)
                    st.markdown("**By day:**")
                    st.markdown("\n".join(f"- {s}" for s in day_summaries))
                    st.markdown("**Why this plan works:**")
                    st.markdown("\n".join(f"- {r}" for r in reasoning))
        with export_col:
            with st.popover("⬇️ Export"):
                st.download_button("📄 CSV", data=csv_bytes, file_name="gym_plan.csv", mime="text/csv", use_container_width=True)
                st.download_button("📝 Markdown", data=md_text, file_name="gym_plan.md", mime="text/markdown", use_container_width=True)
                if pdf_bytes:
                    st.download_button("📘 PDF", data=pdf_bytes, file_name="gym_plan.pdf", mime="application/pdf", use_container_width=True)
                elif pdf_error:
                    st.caption("PDF unavailable: " + pdf_error)

    # Fitness Q&A (strictly validated)
    st.markdown("\n")
    with st.container():
        st.empty()  # How it works merged into toolbar; removed duplicate here

        # Inline form so Enter submits, with Ask button on the same line
        with st.form("qa-form", clear_on_submit=False):
            row = st.columns([8, 1])
            with row[0]:
                q = st.text_input(
                    "Ask about your plan",
                    value="",
                    placeholder="Ask about your plan e.g. Which days train chest? Where are legs trained?",
                    key="qa-input",
                    label_visibility="collapsed",
                )
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
                # Generic fitness verbs
                verbs = {"train", "exercise", "workout", "work out", "build", "grow", "strengthen", "target", "hit", "develop"}
                has_verb = any(v in lower for v in verbs)
                # Baseline fitness/muscle keywords
                fitness_kw = {
                    "exercise", "exercises", "set", "sets", "rep", "reps", "rest",
                    "muscle", "muscles", "volume", "frequency", "intensity",
                    "superset", "warmup", "cooldown", "day", "plan",
                    "chest", "back", "legs", "shoulders", "biceps", "triceps",
                    "quads", "hamstrings", "glutes", "calves", "core", "abs"
                }
                has_kw = any(k in lower for k in fitness_kw)
                # Fuzzy muscle match (handles minor misspellings like "braccialis")
                def _lev(a: str, b: str) -> int:
                    m, n = len(a), len(b)
                    if m == 0:
                        return n
                    if n == 0:
                        return m
                    dp = list(range(n + 1))
                    for i in range(1, m + 1):
                        prev = dp[0]
                        dp[0] = i
                        for j in range(1, n + 1):
                            temp = dp[j]
                            cost = 0 if a[i - 1] == b[j - 1] else 1
                            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
                            prev = temp
                    return dp[n]
                words = [w.strip(" ,.?;:!()").lower() for w in t.split()]
                muscles = [m.lower() for m in get_all_muscles()]
                fuzzy_hit = False
                for w in words:
                    if len(w) < 3:
                        continue
                    # direct containment
                    if any(w in m or m in w for m in muscles):
                        fuzzy_hit = True
                        break
                    # edit-distance check (<=2)
                    for m in muscles:
                        if _lev(w, m) <= 2:
                            fuzzy_hit = True
                            break
                    if fuzzy_hit:
                        break
                ok = has_kw or has_verb or fuzzy_hit
                return (True, None) if ok else (False, "Only fitness-related questions are allowed.")

            ok, err = _is_valid_question(q)
            if not ok:
                st.error(err)
            else:
                answer_text: str | None = None
                if settings.GROQ_API_KEY:
                    try:
                        with st.spinner("Answering with LLM…"):
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
                        muscles = sorted({m.lower() for d in plan.days for ex in d.exercises for m in ex.primary_muscles}) if plan.days else []
                        target_muscles = [m for m in muscles if m in lower]
                        if target_muscles:
                            for tm in target_muscles:
                                hits = []
                                for day in plan.days:
                                    exes = [ex.name for ex in day.exercises if tm in [mm.lower() for mm in ex.primary_muscles]]
                                    if exes:
                                        hits.append(f"Day {day.day_index + 1}: " + ", ".join(exes))
                                if hits:
                                    lines.append(f"Muscle '{pretty_text(tm)}' appears in → " + " | ".join(hits))
                        if any(x in lower for x in ["set", "sets", "rep", "reps", "rest"]):
                            lines.append("This MVP focuses on exercise selection; sets/reps/rest are not configured in the UI.")
                        if not lines:
                            lines.append(
                                "This plan is designed around your selections. Try asking about muscles (e.g., chest) or which days cover a body part."
                            )
                        return "\n".join(lines)

                    answer_text = _answer(q)
                st.info(answer_text)

    # =========================
    # Per-day exercise cards (3 per row; stack on narrow screens)
    # =========================
    grid_cols = st.columns(3)
    for i, day in enumerate(plan.days):
        col = grid_cols[i % 3]
        with col:
            day_card = st.container(border=True)
            with day_card:
                st.markdown('<span class="daybox-sentinel"></span>', unsafe_allow_html=True)
                st.markdown(f"### Day {day.day_index + 1}: {day.label}")
                for idx, ex in enumerate(day.exercises):
                    row_l, row_r = st.columns([10, 2])
                    with row_l:
                        html = (
                            f"<div class='ex-card'>"
                            f"<div class='ex-title'><a class='exlink' href='{ex.exrx_url}' target='_blank'>{ex.name}</a></div>"
                        )
                        chips_m = "".join(f"<span class='chip'>{pretty_text(m)}</span>" for m in ex.primary_muscles)
                        chip_fn = f"<span class='chip fn'>{pretty_text(ex.function)}</span>"
                        chips_eq = "".join(f"<span class='chip eq'>{pretty_text(e)}</span>" for e in ex.equipment)
                        html += f"<div class='chips'>{chips_m}{chip_fn}{chips_eq}</div></div>"
                        st.markdown(html, unsafe_allow_html=True)
                    with row_r:
                        # 3-dot menu for actions
                        pop_label = f"⋯\u200B"
                        with st.popover(pop_label):
                            swap_clicked = st.button("🔀 Swap exercise", key=f"swap-{day.day_index}-{idx}-{ex.id}",
                                                     use_container_width=True)
                            remove_clicked = st.button("🗑️ Remove", key=f"remove-{day.day_index}-{idx}-{ex.id}",
                                                       use_container_width=True)
                    if swap_clicked:
                        allowed_ids = shortlist(current_profile)
                        with st.spinner("Swapping…"):
                            if settings.GROQ_API_KEY:
                                try:
                                    st.session_state["plan"] = replace_exercise_llm(current_profile, st.session_state["plan"], day.day_index, ex.id, allowed_ids)
                                except Exception:
                                    st.session_state["plan"] = replace_one_exercise(current_profile, st.session_state["plan"], day.day_index, ex.id, allowed_ids)
                            else:
                                st.session_state["plan"] = replace_one_exercise(current_profile, st.session_state["plan"], day.day_index, ex.id, allowed_ids)
                        st.toast("Exercise swapped.")
                        st.rerun()
                    if remove_clicked:
                        _plan = st.session_state.get("plan")
                        if _plan is not None:
                            _day = _plan.days[day.day_index]
                            for _j, _e in enumerate(_day.exercises):
                                if _e.id == ex.id:
                                    del _day.exercises[_j]
                                    break
                            _counts: Dict[str, int] = {}
                            for _d in _plan.days:
                                for _ex in _d.exercises:
                                    for _m in _ex.primary_muscles:
                                        _counts[_m] = _counts.get(_m, 0) + 1
                            _plan.weekly_focus = _counts
                            st.session_state["plan"] = _plan
                            st.toast("Exercise removed.")
                            st.rerun()


# AI Insight: show when there was an LLM request or an LLM error recorded in plan meta
_meta = (getattr(plan, "meta", {}) or {}) if plan is not None else {}
_show_ai = bool(groq_debug.LAST_REQUEST) or bool(_meta.get("llm_error"))
if _show_ai:
    ai_scope = st.container()
    with ai_scope:
        with st.expander("AI Insight", expanded=False):
            model_used = (groq_debug.LAST_USED_MODEL or "unknown")
            st.markdown(f"**Model:** `{model_used}`")
            # Timestamp (UTC) if available
            try:
                ts = (groq_debug.LAST_REQUEST or {}).get("ts")
            except Exception:
                ts = None
            if ts:
                st.markdown(f"**Requested at:** {ts} (UTC)")

            # If there was an AI failure, show details here
            if _meta.get("llm_error"):
                st.markdown("**Why AI failed:**")
                tried = _meta.get("llm_model") or model_used
                note = _meta.get("llm_note")
                err = _meta.get("llm_error")
                detail = _meta.get("llm_error_detail") or err
                if note:
                    st.markdown(f"- Note: {note}")
                if err:
                    st.markdown("- Summary error:")
                    st.code(str(err))
                if detail and detail != err:
                    st.markdown("- Full error detail:")
                    st.code(str(detail))

            # Prompt/response telemetry
            if groq_debug.LAST_REQUEST:
                st.markdown("**System prompt:**")
                st.code(groq_debug.LAST_REQUEST.get("system", ""))
                st.markdown("**User payload (JSON):**")
                st.code(groq_debug.LAST_REQUEST.get("user", ""), language="json")
            if groq_debug.LAST_RESPONSE_TEXT:
                st.markdown("**Raw response:**")
                st.code(groq_debug.LAST_RESPONSE_TEXT)
