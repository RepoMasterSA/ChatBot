"""Runtime configuration, read once from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful, concise assistant. Answer clearly and keep track of "
    "the conversation so far."
)


def _as_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    api_keys: tuple[str, ...] = ()
    model: str = "gemini/gemini-2.5-flash-lite"
    database_path: str = "/data/app.db"
    allowed_origins: tuple[str, ...] = ("http://localhost:3000",)
    enable_failure_simulation: bool = False
    cache_type: str = "local"  # "local" (in-memory) or "disk"
    cache_dir: str = "/data/llm_cache"
    default_system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_history_messages: int = 40
    request_timeout_s: int = 30
    key_ids: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "key_ids",
            tuple(f"key_{i}" for i in range(1, len(self.api_keys) + 1)),
        )


def database_path_from_url(url: str) -> str:
    """sqlite:////data/app.db -> /data/app.db ; sqlite:///./app.db -> ./app.db"""
    prefix = "sqlite:///"
    if url.startswith(prefix):
        return url[len(prefix):]
    return url


def load_settings() -> Settings:
    return Settings(
        api_keys=tuple(_as_list(os.getenv("LLM_API_KEYS"))),
        model=os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash-lite").strip(),
        database_path=database_path_from_url(
            os.getenv("DATABASE_URL", "sqlite:////data/app.db").strip()
        ),
        allowed_origins=tuple(
            _as_list(os.getenv("ALLOWED_ORIGINS", "http://localhost:3000"))
        ),
        enable_failure_simulation=_as_bool(os.getenv("ENABLE_FAILURE_SIMULATION")),
        cache_type=os.getenv("CACHE_TYPE", "local").strip().lower(),
        cache_dir=os.getenv("CACHE_DIR", "/data/llm_cache").strip(),
        default_system_prompt=os.getenv("DEFAULT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
        max_history_messages=int(os.getenv("MAX_HISTORY_MESSAGES", "40")),
        request_timeout_s=int(os.getenv("REQUEST_TIMEOUT_S", "30")),
    )
