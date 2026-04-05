from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    runs_dir: Path
    workspace_dir: Path
    openai_api_key: str | None
    openai_model: str | None
    github_token: str | None
    github_username: str | None
    github_api_url: str
    allowed_origins: list[str]
    max_snippet_lines: int = 8


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "data"
    runs_dir = data_dir / "runs"
    workspace_dir = data_dir / "workspace"
    runs_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    allowed_origins = [origin.strip() for origin in origins.split(",") if origin.strip()]

    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        runs_dir=runs_dir,
        workspace_dir=workspace_dir,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL"),
        github_token=os.getenv("GITHUB_TOKEN"),
        github_username=os.getenv("GITHUB_USERNAME"),
        github_api_url=os.getenv("GITHUB_API_URL", "https://api.github.com"),
        allowed_origins=allowed_origins,
    )
