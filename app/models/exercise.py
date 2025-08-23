from __future__ import annotations

from pydantic import BaseModel, HttpUrl, Field
from typing import List, Literal, Optional


Equipment = Literal[
    "barbell",
    "dumbbell",
    "machines",
    "cables",
    "kettlebells",
    "bodyweight",
]

ExerciseType = Literal["compound", "isolation", "unknown"]


class Exercise(BaseModel):
    id: str = Field(..., description="Catalog ID, e.g., exrx:BBBenchPress")
    name: str
    exrx_url: HttpUrl
    primary_muscles: List[str]
    function: str
    equipment: List[Equipment]
    type: ExerciseType
    enriched: bool
    notes: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "exrx:BBBenchPress",
                    "name": "Barbell Bench Press",
                    "exrx_url": "https://exrx.net/WeightExercises/PectoralSternal/BBBenchPress",
                    "primary_muscles": ["chest", "front_delts", "triceps"],
                    "function": "horizontal_push",
                    "equipment": ["barbell"],
                    "type": "compound",
                    "enriched": False,
                }
            ]
        }
    }
