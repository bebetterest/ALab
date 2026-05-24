from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = """schema_version = 1

[output]
format = "text"
preview_bytes = 4096

[storage]
busy_timeout_ms = 5000

[locks]
acquire_timeout_ms = 30000
heartbeat_interval_ms = 5000
stale_after_ms = 120000
"""


@dataclass(frozen=True)
class Home:
    path: Path

    @property
    def db_path(self) -> Path:
        return self.path / "alab.db"

    @property
    def config_path(self) -> Path:
        return self.path / "config.toml"

    @property
    def backups_path(self) -> Path:
        return self.path / "backups"

    @property
    def projects_path(self) -> Path:
        return self.path / "projects"

    @property
    def project_workspaces_path(self) -> Path:
        return self.path / "project-workspaces"

    @property
    def tmp_path(self) -> Path:
        return self.path / "tmp"

    @property
    def sources_path(self) -> Path:
        return self.path / "sources"

    @property
    def cache_path(self) -> Path:
        return self.path / "cache"

    @property
    def feedback_path(self) -> Path:
        return self.path / "feedback"


def resolve_home(explicit: str | None = None) -> Home:
    raw = explicit or os.environ.get("ALAB_HOME") or "~/.ALab"
    return Home(Path(raw).expanduser().resolve())


def ensure_layout(home: Home) -> None:
    for path in [
        home.path,
        home.backups_path,
        home.project_workspaces_path,
        home.projects_path,
        home.sources_path / "skydiscover",
        home.cache_path / "docker-images",
        home.cache_path / "skydiscover-python-envs",
        home.feedback_path,
        home.tmp_path,
    ]:
        path.mkdir(parents=True, exist_ok=True)
    if not home.config_path.exists():
        home.config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")


def is_initialized(home: Home) -> bool:
    return home.db_path.exists()
