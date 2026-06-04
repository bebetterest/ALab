from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path

from .context import path_hash
from .db import Database, canonical_json
from .errors import AlabError
from .home import Home
from .ids import new_id
from .proc import run_cmd
from .service_contracts import cache_metadata_json_obj
from .service_models import FilesystemRemovalTarget, TrashStage
from .timeutil import utc_now


def _remove_path_if_safe(path: Path, root: Path) -> None:
    resolved = path.expanduser().resolve()
    root_resolved = root.expanduser().resolve()
    if resolved == root_resolved or not str(resolved).startswith(str(root_resolved) + os.sep):
        raise AlabError("CONFIG_INVALID", "refusing to prune a path outside ALab home")
    if not resolved.exists():
        return
    if resolved.is_dir():
        shutil.rmtree(resolved)
    else:
        resolved.unlink()


def _path_present(path: Path | None) -> bool:
    return bool(path and (path.exists() or path.is_symlink()))


def _trash_plan(home: Home, target: str | Path | None) -> str | None:
    if not target:
        return None
    path = Path(target)
    return f"{path} -> {home.tmp_path / 'trash' / '<audit_id>' / (path.name or 'path')}"


def _worktree_dirty_state(path: str | Path | None) -> str:
    if not path:
        return "missing"
    worktree = Path(path)
    if not _path_present(worktree):
        return "missing"
    result = run_cmd(["git", "-C", str(worktree), "status", "--porcelain"], check=False)
    if result.returncode != 0:
        return "unknown"
    return "dirty" if result.stdout.strip() else "clean"


def _stage_path_to_trash(home: Home, target: str | Path | None, audit_id: str) -> TrashStage:
    if not target:
        return TrashStage(audit_id, None, None, None, "none", False, True)
    source = Path(target).expanduser()
    if not _path_present(source):
        return TrashStage(audit_id, source, None, None, "none", False, True)
    resolved = source.resolve()
    home_resolved = home.path.resolve()
    if resolved == home_resolved:
        raise AlabError("STORAGE_ERROR", "refusing to trash ALab home")
    home_trash_dir = home.tmp_path / "trash" / audit_id
    created_home_trash_dir = not home_trash_dir.exists()
    trash_name = source.name or "path"
    home_trash_path = home_trash_dir / trash_name
    if home_trash_path.exists():
        digest = path_hash(source).split(":", 1)[1][:12]
        home_trash_path = home_trash_dir / f"{trash_name}-{digest}"
    try:
        home_trash_dir.mkdir(parents=True, exist_ok=True)
        source.rename(home_trash_path)
        return TrashStage(
            audit_id,
            source,
            home_trash_path,
            str(home_trash_path.relative_to(home.path)),
            "home",
            True,
            False,
        )
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            if created_home_trash_dir:
                shutil.rmtree(home_trash_dir, ignore_errors=True)
            raise AlabError("STORAGE_ERROR", f"failed to stage path for trash: {exc}") from exc
        if created_home_trash_dir:
            shutil.rmtree(home_trash_dir, ignore_errors=True)
        same_parent = source.parent / f".alab-trash-{audit_id}"
        if same_parent.exists():
            digest = path_hash(source).split(":", 1)[1][:12]
            same_parent = source.parent / f".alab-trash-{audit_id}-{digest}"
        try:
            source.rename(same_parent)
        except OSError as fallback_exc:
            raise AlabError("STORAGE_ERROR", f"failed to stage path in same-parent trash: {fallback_exc}") from fallback_exc
        return TrashStage(audit_id, source, same_parent, same_parent.name, "same_parent", True, False)


def _stage_targets_to_trash(home: Home, targets: list[FilesystemRemovalTarget], audit_id: str) -> list[TrashStage]:
    stages: list[TrashStage] = []
    try:
        for target in targets:
            stages.append(_stage_path_to_trash(home, target.path, audit_id))
    except Exception:
        for stage in reversed(stages):
            try:
                _restore_staged_trash(stage)
            except Exception:
                pass
        raise
    return stages


def _restore_staged_trash(stage: TrashStage) -> None:
    if not stage.moved or stage.original_path is None or stage.trash_path is None:
        return
    if _path_present(stage.original_path):
        raise AlabError("STORAGE_ERROR", "cannot restore trashed path because original path is occupied")
    stage.trash_path.rename(stage.original_path)
    if stage.mode == "home":
        try:
            stage.trash_path.parent.rmdir()
        except OSError:
            pass


def _restore_staged_trashes(stages: list[TrashStage]) -> None:
    for stage in reversed(stages):
        _restore_staged_trash(stage)


def _raise_after_staged_trash_transaction_failure(exc: Exception, stages: list[TrashStage], *, next_action: str = "alab context repair") -> None:
    try:
        _restore_staged_trashes(stages)
    except Exception as restore_exc:
        raise AlabError("STORAGE_ERROR", f"database update failed and trash restore failed: {restore_exc}", next_action) from restore_exc
    if isinstance(exc, AlabError):
        raise exc
    raise AlabError("STORAGE_ERROR", f"database update failed after trash staging: {type(exc).__name__}", next_action) from exc


def _delete_trash_path(stage: TrashStage, home: Home) -> None:
    if not stage.moved or stage.trash_path is None:
        return
    resolved = stage.trash_path.resolve()
    home_trash = (home.tmp_path / "trash").resolve()
    if stage.mode == "home":
        if not str(resolved).startswith(str(home_trash) + os.sep):
            raise AlabError("STORAGE_ERROR", "refusing to delete unexpected home trash path")
    elif stage.mode == "same_parent":
        if not stage.trash_path.name.startswith(".alab-trash-"):
            raise AlabError("STORAGE_ERROR", "refusing to delete unexpected same-parent trash path")
    else:
        raise AlabError("STORAGE_ERROR", "unknown trash staging mode")
    if stage.trash_path.is_dir() and not stage.trash_path.is_symlink():
        shutil.rmtree(stage.trash_path)
    else:
        stage.trash_path.unlink()
    if stage.mode == "home":
        try:
            stage.trash_path.parent.rmdir()
        except OSError:
            pass


def _record_pending_trash_cleanup(home: Home, stage: TrashStage, project_id: str | None, deletion_error: Exception) -> None:
    if not stage.moved or stage.trash_path is None:
        return
    now = utc_now()
    metadata = {
        "schema_version": 1,
        "safe_summary": f"pending trash cleanup for {stage.audit_label}",
        "inputs_hash": path_hash(stage.original_path) if stage.original_path else stage.audit_id,
        "warnings": [f"trash deletion failed: {type(deletion_error).__name__}"],
    }
    metadata_json = canonical_json(cache_metadata_json_obj(canonical_json(metadata)))
    with Database(home).tx() as conn:
        conn.execute(
            """
            INSERT INTO cache_entries(cache_id, cache_kind, cache_key, project_id, path, docker_tag,
              size_bytes, status, metadata_json, created_at, last_used_at, removed_at)
            VALUES (?, 'trash', ?, ?, ?, NULL, NULL, 'active', ?, ?, ?, NULL)
            """,
            (new_id("cache", "trash"), stage.audit_id, project_id, str(stage.trash_path), metadata_json, now, now),
        )


def _finalize_staged_trash(home: Home, stage: TrashStage, project_id: str | None) -> bool:
    if not stage.moved:
        return False
    try:
        _delete_trash_path(stage, home)
    except Exception as exc:
        _record_pending_trash_cleanup(home, stage, project_id, exc)
        return True
    return False


def _finalize_staged_trashes(home: Home, stages: list[TrashStage], project_id: str | None) -> bool:
    pending = False
    for stage in stages:
        pending = _finalize_staged_trash(home, stage, project_id) or pending
    return pending


def _remove_trash_cache_path(path: Path, home: Home) -> None:
    resolved = path.expanduser().resolve()
    home_trash = (home.tmp_path / "trash").resolve()
    if str(resolved).startswith(str(home_trash) + os.sep):
        if resolved.exists():
            if resolved.is_dir() and not resolved.is_symlink():
                shutil.rmtree(resolved)
            else:
                resolved.unlink()
        return
    if path.name.startswith(".alab-trash-"):
        if resolved.exists():
            if resolved.is_dir() and not resolved.is_symlink():
                shutil.rmtree(resolved)
            else:
                resolved.unlink()
        return
    raise AlabError("CONFIG_INVALID", "refusing to prune an unexpected trash path")
