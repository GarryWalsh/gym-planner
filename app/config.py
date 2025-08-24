from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "dev"
    LOG_LEVEL: str = "INFO"

    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    GROQ_TEMPERATURE: float = 0.2

    # App-level policies
    MAX_REPAIR_ITERATIONS: int = 2
    MAX_ALLOWED_EXERCISES: int = 200


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Allow Streamlit Cloud secrets to override or provide env values
    overrides: dict = {}
    try:
        import streamlit as _st  # type: ignore
        sec = getattr(_st, "secrets", None)
        if sec:
            for k in ["APP_ENV", "LOG_LEVEL", "GROQ_API_KEY", "GROQ_MODEL", "GROQ_TEMPERATURE"]:
                if k in sec and sec[k] is not None and sec[k] != "":
                    overrides[k] = sec[k]
    except Exception:
        pass
    s = Settings(**overrides)  # type: ignore[call-arg]
    # Extra fallback: if GROQ_API_KEY is blank/None but present in process env, use it
    if not s.GROQ_API_KEY:
        env_key = os.environ.get("GROQ_API_KEY")
        if env_key:
            try:
                s.GROQ_API_KEY = env_key  # type: ignore[assignment]
            except Exception:
                pass
    return s
