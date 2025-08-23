from __future__ import annotations

import csv
import io
from typing import List

from app.models.plan import Plan


def to_csv(plan: Plan) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "day_index",
        "day_label",
        "exercise_id",
        "exercise_name",
        "primary_muscles",
        "function",
        "equipment",
        "sets",
        "reps",
        "rest_seconds",
        "exrx_url",
    ])
    for day in plan.days:
        for ex in day.exercises:
            writer.writerow([
                day.day_index,
                day.label,
                ex.id,
                ex.name,
                ";".join(ex.primary_muscles),
                ex.function,
                ";".join(ex.equipment),
                day.sets,
                day.reps,
                day.rest_seconds,
                str(ex.exrx_url),
            ])
    return output.getvalue().encode("utf-8")


def to_markdown(plan: Plan) -> str:
    lines: List[str] = []
    lines.append(f"# Gym Plan ({len(plan.days)} days)\n")
    for day in plan.days:
        lines.append(f"\n## Day {day.day_index + 1}: {day.label}")
        lines.append(f"Sets: {day.sets}  Reps: {day.reps}  Rest: {day.rest_seconds}s\n")
        for ex in day.exercises:
            equip = ", ".join(ex.equipment)
            musc = ", ".join(ex.primary_muscles)
            lines.append(f"- [{ex.name}]({ex.exrx_url}) — {musc}; {ex.function}; {equip}")
    if plan.weekly_focus:
        lines.append("\n### Weekly focus")
        for k, v in plan.weekly_focus.items():
            lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"
