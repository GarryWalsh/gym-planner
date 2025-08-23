from __future__ import annotations

from typing import List, Dict

from app.config import get_settings
from app.models.user_profile import UserProfile
from app.models.exercise import Exercise
from .catalog import load_catalog, filter_by_equipment, filter_by_muscles


def shortlist(profile: UserProfile) -> List[str]:
    """Return a shortlist of exercise IDs based on profile constraints.
    Rules:
    - Apply equipment allow/deny.
    - Exclude blacklisted muscles and explicit exercise IDs.
    - Prioritize compound exercises and emphasized muscles.
    - Cap the list size by settings.MAX_ALLOWED_EXERCISES.
    """
    settings = get_settings()

    catalog = load_catalog()

    # Equipment filters
    catalog = filter_by_equipment(
        catalog,
        allowed=profile.allowed_equipment or None,
        blacklisted=profile.blacklisted_equipment or None,
    )

    # Muscle blacklist
    catalog = filter_by_muscles(catalog, banned_muscles=profile.blacklisted_muscles)

    # ID blacklist
    banned_ids = set(profile.blacklisted_exercise_ids)
    catalog = [ex for ex in catalog if ex.id not in banned_ids]

    # Prioritize emphasized muscles and compound type
    emphasis = {k.lower(): v for k, v in (profile.emphasis or {}).items()}

    def score(ex: Exercise) -> tuple:
        has_emphasis = int(any(emphasis.get(m.lower(), 0) == 1 for m in ex.primary_muscles))
        is_compound = 1 if ex.type == "compound" else 0
        return (has_emphasis, is_compound)

    catalog.sort(key=score, reverse=True)

    # Cap size
    max_n = settings.MAX_ALLOWED_EXERCISES
    return [ex.id for ex in catalog[:max_n]]
