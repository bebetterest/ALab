from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .db import connect_initialized, one
from .errors import AlabError
from .home import Home


@dataclass(frozen=True)
class Context:
    context_type: str
    path: Path
    marker: dict[str, Any]
    project_id: str | None
    exp_id: str | None
    token_id: str | None
    path_hash: str


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve()


def _swap_case_name(path: Path) -> Path | None:
    name = path.name
    swapped = name.swapcase()
    if not name or name == swapped:
        return None
    return path.with_name(swapped)


@lru_cache(maxsize=128)
def _device_is_case_insensitive(device_id: int, probe_path: str) -> bool:
    path = Path(probe_path)
    for candidate in [path, *path.parents]:
        swapped = _swap_case_name(candidate)
        if swapped is None:
            continue
        try:
            if swapped.exists():
                return os.path.samefile(candidate, swapped)
        except OSError:
            continue
    return False


def _is_case_insensitive_path(path: Path) -> bool:
    for candidate in [path, *path.parents]:
        try:
            stat = candidate.stat()
        except OSError:
            continue
        return _device_is_case_insensitive(stat.st_dev, str(candidate))
    return False


def _path_hash_text(path: Path) -> str:
    normalized = str(normalize_path(path))
    if _is_case_insensitive_path(Path(normalized)):
        return normalized.casefold()
    return normalized


def path_hash(path: Path) -> str:
    digest = hashlib.sha256(_path_hash_text(path).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def marker_path(path: Path) -> Path:
    return path / ".alab" / "context.json"


CONTEXT_MARKER_KEYS = {
    "marker_version",
    "home_id",
    "context_type",
    "project_id",
    "exp_id",
    "token_id",
    "canonical_repo_path_hash",
    "inspection_commit",
    "created_at",
    "repaired_at",
}


def context_marker_obj(text: str) -> dict[str, Any]:
    try:
        marker = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AlabError("CONTEXT_CONFLICT", "context marker is invalid JSON") from exc
    if not isinstance(marker, dict):
        raise AlabError("CONTEXT_CONFLICT", "context marker must be a JSON object")
    unknown = sorted(set(marker) - CONTEXT_MARKER_KEYS)
    if unknown:
        raise AlabError("CONTEXT_CONFLICT", f"context marker contains unknown JSON keys: {', '.join(unknown)}")
    if marker.get("marker_version") != 1:
        raise AlabError("CONTEXT_CONFLICT", "context marker marker_version must be 1")
    context_type = marker.get("context_type")
    if context_type not in {"project", "experiment", "inspection"}:
        raise AlabError("CONTEXT_CONFLICT", "context marker has invalid context_type")
    for key in ("home_id", "project_id", "created_at"):
        if not isinstance(marker.get(key), str) or not marker[key]:
            raise AlabError("CONTEXT_CONFLICT", f"context marker {key} must be a non-empty string")
    repaired_at = marker.get("repaired_at")
    if repaired_at is not None and (not isinstance(repaired_at, str) or not repaired_at):
        raise AlabError("CONTEXT_CONFLICT", "context marker repaired_at must be a non-empty string")
    exp_id = marker.get("exp_id")
    token_id = marker.get("token_id")
    repo_hash = marker.get("canonical_repo_path_hash")
    inspection_commit = marker.get("inspection_commit")
    if context_type == "project":
        if exp_id is not None or token_id is not None:
            raise AlabError("CONTEXT_CONFLICT", "project context marker must not contain exp_id or token_id")
        if not isinstance(repo_hash, str) or not repo_hash.startswith("sha256:"):
            raise AlabError("CONTEXT_CONFLICT", "project context marker requires canonical_repo_path_hash")
        if inspection_commit is not None:
            raise AlabError("CONTEXT_CONFLICT", "project context marker must not contain inspection_commit")
    else:
        if not isinstance(exp_id, str) or not exp_id:
            raise AlabError("CONTEXT_CONFLICT", "experiment context marker requires exp_id")
        if not isinstance(token_id, str) or not token_id:
            raise AlabError("CONTEXT_CONFLICT", "experiment context marker requires token_id")
        if repo_hash is not None:
            raise AlabError("CONTEXT_CONFLICT", "experiment context marker must not contain canonical_repo_path_hash")
        if context_type == "inspection":
            if not isinstance(inspection_commit, str) or not inspection_commit:
                raise AlabError("CONTEXT_CONFLICT", "inspection context marker requires inspection_commit")
        elif inspection_commit is not None:
            raise AlabError("CONTEXT_CONFLICT", "experiment context marker must not contain inspection_commit")
    return marker


def find_marker(start: Path) -> tuple[Path, dict[str, Any]] | None:
    current = normalize_path(start)
    for candidate in [current, *current.parents]:
        marker = marker_path(candidate)
        if marker.exists():
            return candidate, context_marker_obj(marker.read_text(encoding="utf-8"))
    return None


def write_marker(path: Path, data: dict[str, Any]) -> None:
    marker_dir = path / ".alab"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = context_marker_obj(json.dumps(data))
    marker_path(path).write_text(json.dumps(marker, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def detect_context(home: Home, cwd: Path | None = None) -> Context | None:
    cwd = normalize_path(cwd or Path.cwd())
    found = find_marker(cwd)
    if found is None:
        return None
    root, marker = found
    conn = connect_initialized(home)
    try:
        home_row = one(conn, "SELECT home_id FROM homes LIMIT 1")
        if home_row is None or marker.get("home_id") != home_row["home_id"]:
            raise AlabError("CONTEXT_CONFLICT", "context marker belongs to a different ALab home")
        ph = path_hash(root)
        row = one(
            conn,
            "SELECT * FROM path_registry WHERE path_hash = ? AND status = 'active'",
            (ph,),
        )
        if row is None:
            raise AlabError("CONTEXT_CONFLICT", "context marker has no active registry row")
        if row["context_type"] != marker.get("context_type"):
            raise AlabError("CONTEXT_CONFLICT", "context marker and registry disagree")
        return Context(
            context_type=row["context_type"],
            path=root,
            marker=marker,
            project_id=row["project_id"],
            exp_id=row["exp_id"],
            token_id=row["token_id"],
            path_hash=ph,
        )
    finally:
        conn.close()
