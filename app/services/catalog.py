from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from app.models.exercise import Exercise, Equipment

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "exrx_catalog.json"


@lru_cache(maxsize=1)
def load_catalog() -> List[Exercise]:
    with CATALOG_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Exercise.model_validate(item) for item in raw]


def filter_by_equipment(exercises: Sequence[Exercise], allowed: Sequence[Equipment] | None = None,
                        blacklisted: Sequence[Equipment] | None = None) -> List[Exercise]:
    allowed_set = set(allowed or [])
    black_set = set(blacklisted or [])
    out: List[Exercise] = []
    for ex in exercises:
        eq = set(ex.equipment)
        if allowed_set and eq.isdisjoint(allowed_set):
            continue
        if black_set and not eq.isdisjoint(black_set):
            continue
        out.append(ex)
    return out


def filter_by_muscles(exercises: Sequence[Exercise], banned_muscles: Sequence[str] | None = None) -> List[Exercise]:
    banned = set(m.lower() for m in (banned_muscles or []))
    if not banned:
        return list(exercises)
    out: List[Exercise] = []
    for ex in exercises:
        pm = set(m.lower() for m in ex.primary_muscles)
        if pm.isdisjoint(banned):
            out.append(ex)
    return out


def get_by_ids(ids: Iterable[str]) -> List[Exercise]:
    id_set = set(ids)
    return [ex for ex in load_catalog() if ex.id in id_set]
