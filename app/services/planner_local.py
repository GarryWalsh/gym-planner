from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from app.models.plan import Plan, DayPlan
from app.models.user_profile import UserProfile
from app.services.catalog import load_catalog, get_by_ids


def _label_for_day(i: int, days: int) -> str:
    if days == 1:
        return "Full Body"
    labels = [
        "Upper Body",
        "Lower Body",
        "Push",
        "Pull",
        "Full Body",
        "Accessory",
    ]
    return labels[i % len(labels)]


def _compute_weekly_focus(plan: Plan) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for day in plan.days:
        for ex in day.exercises:
            for m in ex.primary_muscles:
                counts[m] += 1
    return dict(counts)


def generate_local_plan(profile: UserProfile, allowed_exercise_ids: Sequence[str]) -> Plan:
    catalog = {ex.id: ex for ex in load_catalog()}

    # Pick exercises in order from allowed_exercise_ids; we will allow reuse across days,
    # but keep uniqueness within a day. We also try to diversify functions when possible.
    allowed = [catalog[eid] for eid in allowed_exercise_ids if eid in catalog]
    if not allowed:
        raise ValueError("No exercises available after applying constraints.")

    days: List[DayPlan] = []
    cursor = 0

    for d in range(profile.days_per_week):
        day_label = _label_for_day(d, profile.days_per_week)
        day_exercises: List = []
        seen_ids: set[str] = set()

        # Pass 1: prefer unique functions
        attempts = 0
        while len(day_exercises) < profile.max_exercises_per_day and attempts < len(allowed) * 3:
            ex = allowed[cursor % len(allowed)]
            cursor += 1
            attempts += 1
            if ex.id in seen_ids:
                continue
            if any(e.function == ex.function for e in day_exercises):
                continue
            day_exercises.append(ex)
            seen_ids.add(ex.id)

        # Pass 2: relax function diversity to fill remaining slots with unique IDs
        attempts2 = 0
        while len(day_exercises) < profile.max_exercises_per_day and attempts2 < len(allowed) * 3:
            ex = allowed[cursor % len(allowed)]
            cursor += 1
            attempts2 += 1
            if ex.id in seen_ids:
                continue
            day_exercises.append(ex)
            seen_ids.add(ex.id)

        # Ensure at least one exercise
        if not day_exercises:
            fallback_ex = allowed[cursor % len(allowed)]
            day_exercises.append(fallback_ex)
            cursor += 1

        day = DayPlan(
            day_index=d,
            label=day_label,
            exercises=day_exercises,
            sets=profile.default_sets,
            reps=profile.default_reps,
            rest_seconds=profile.rest_seconds,
            supersets=[],
        )
        days.append(day)

    plan = Plan(days=days, weekly_focus={}, meta={"source": "local"})
    plan.weekly_focus = _compute_weekly_focus(plan)

    # Ensure emphasized muscles appear at least once/week by small adjustments if needed
    emphasized = {m for m, v in (profile.emphasis or {}).items() if v == 1}
    if emphasized:
        covered = set(k for k, v in plan.weekly_focus.items() if v > 0) & emphasized
        missing = list(emphasized - covered)
        if missing:
            # try to swap last exercise of first day with one hitting a missing muscle
            pool = [ex for ex in allowed if any(m in emphasized for m in ex.primary_muscles)]
            if pool:
                plan.days[0].exercises[-1] = pool[0]
                plan.weekly_focus = _compute_weekly_focus(plan)

    return plan


def replace_one_exercise(
    profile: UserProfile,
    plan: Plan,
    day_index: int,
    replace_exercise_id: str,
    allowed_exercise_ids: Sequence[str],
) -> Plan:
    catalog = {ex.id: ex for ex in load_catalog()}
    allowed = [catalog[eid] for eid in allowed_exercise_ids if eid in catalog]
    day = plan.days[day_index]
    current_ids = {ex.id for ex in day.exercises}

    target_idx = next((i for i, ex in enumerate(day.exercises) if ex.id == replace_exercise_id), None)
    if target_idx is None:
        return plan

    target = day.exercises[target_idx]

    # find candidate with similar function or overlapping muscles
    def is_candidate(ex):
        if ex.id in current_ids:
            return False
        if ex.id == replace_exercise_id:
            return False
        same_fn = ex.function == target.function
        overlap = bool(set(m.lower() for m in ex.primary_muscles) & set(m.lower() for m in target.primary_muscles))
        return same_fn or overlap

    for ex in allowed:
        if is_candidate(ex):
            day.exercises[target_idx] = ex
            break

    plan.weekly_focus = _compute_weekly_focus(plan)
    return plan
