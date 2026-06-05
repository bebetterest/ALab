from __future__ import annotations

from pathlib import Path
from typing import Any

from . import services as _core
from .db import Database, all_rows, one
from .errors import AlabError
from .home import Home
from .rendering import ResultBlock
from .service_args import (
    flag,
    optional_positional_selector,
    require_dry_run_unforced,
    require_force_confirm,
    require_known_options,
    require_options_at_most_once,
)
from .service_auth import require_home
from .service_models import FilesystemRemovalTarget, GitRefDeletion, Request
from .service_text import _lifecycle_reason
from .timeutil import utc_now

_require_project_admin = _core._require_project_admin
_exp_row = _core._exp_row
_project_paths = _core._project_paths
_experiment_branch_ref = _core._experiment_branch_ref
_git_ref_commit = _core._git_ref_commit
_delete_experiment_branch_ref = _core._delete_experiment_branch_ref
_restore_experiment_branch_ref = _core._restore_experiment_branch_ref
_trash_plan = _core._trash_plan
_stage_targets_to_trash = _core._stage_targets_to_trash
_raise_after_staged_trash_transaction_failure = _core._raise_after_staged_trash_transaction_failure
_restore_staged_trashes = _core._restore_staged_trashes
_finalize_staged_trashes = _core._finalize_staged_trashes
_prune_missing_git_worktrees = _core._prune_missing_git_worktrees
path_hash = _core.path_hash


def audit(*args: Any, **kwargs: Any) -> str:
    return _core.audit(*args, **kwargs)


def new_id(*args: Any, **kwargs: Any) -> str:
    return _core.new_id(*args, **kwargs)


def cmd_exp_archive(args: list[str], req: Request) -> list[ResultBlock]:
    for removed_flag in ("--remove-worktree", "--force-remove-worktree"):
        if flag(args, removed_flag):
            raise AlabError(
                "CONFIG_INVALID",
                f"{removed_flag} was removed from exp archive; use exp worktree remove explicitly",
            )
    require_known_options(args, ("--project",))
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(args, "exp archive accepts exactly one experiment id")
    with Database(req.globals.home).tx() as conn:
        exp = _exp_row(conn, project["project_id"], exp_id)
        previous = exp["status"]
        archived_at = exp["archived_at"] or utc_now()
        if previous != "archived":
            if one(conn, "SELECT lock_name FROM locks WHERE exp_id = ? LIMIT 1", (exp["exp_id"],)):
                raise AlabError("RESOURCE_BUSY", "experiment has active locks")
            conn.execute(
                "UPDATE experiments SET status = 'archived', pre_archive_status = ?, archived_at = ?, updated_at = ? WHERE exp_id = ?",
                (previous, archived_at, archived_at, exp["exp_id"]),
            )
            audit(
                conn,
                action="archive",
                object_type="experiment",
                object_id=exp["exp_id"],
                actor=actor,
                project_id=project["project_id"],
                exp_id=exp["exp_id"],
                metadata={
                    "schema_version": 1,
                    "previous_status": previous,
                    "experiment_status": "archived",
                    "archived_at": archived_at,
                },
            )
        return [
            ResultBlock(
                "experiment",
                [
                    ("exp id", exp["exp_id"]),
                    ("previous status", previous),
                    ("experiment status", "archived"),
                    ("archived at", archived_at),
                ],
            )
        ]


def cmd_exp_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(args, "exp unarchive accepts exactly one experiment id")
    with Database(req.globals.home).tx() as conn:
        exp = _exp_row(conn, project["project_id"], exp_id)
        previous = exp["status"]
        restored = exp["pre_archive_status"] or "closed"
        now = utc_now() if previous == "archived" else None
        if previous == "archived":
            conn.execute(
                "UPDATE experiments SET status = ?, pre_archive_status = NULL, archived_at = NULL, updated_at = ? WHERE exp_id = ?",
                (restored, now, exp["exp_id"]),
            )
            audit(
                conn,
                action="unarchive",
                object_type="experiment",
                object_id=exp["exp_id"],
                actor=actor,
                project_id=project["project_id"],
                exp_id=exp["exp_id"],
                metadata={
                    "schema_version": 1,
                    "previous_status": previous,
                    "experiment_status": restored,
                    "unarchived_at": now,
                },
            )
        return [
            ResultBlock(
                "experiment",
                [
                    ("exp id", exp["exp_id"]),
                    ("previous status", previous),
                    ("experiment status", restored if previous == "archived" else previous),
                    ("unarchived at", now),
                ],
            )
        ]


def _stored_relative_path(base: Path, stored: str | None) -> Path | None:
    if not stored:
        return None
    path = Path(stored)
    return path if path.is_absolute() else base / path


def _artifact_log_filesystem_targets(
    conn,
    home: Home,
    project_id: str,
    *,
    artifact_rows: list[Any] | None = None,
    log_rows: list[Any] | None = None,
) -> list[FilesystemRemovalTarget]:
    artifact_rows = artifact_rows or []
    log_rows = log_rows or []
    _project_root, _repo_git, artifact_store = _project_paths(home, project_id)
    targets: list[FilesystemRemovalTarget] = []
    artifact_ids = {row["artifact_id"] for row in artifact_rows}
    log_ids = {row["log_id"] for row in log_rows}
    seen: set[tuple[str, str]] = set()

    for row in artifact_rows:
        blob_path = row["blob_path"]
        if not blob_path:
            continue
        key = ("artifact", blob_path)
        if key in seen:
            continue
        seen.add(key)
        refs = all_rows(
            conn,
            "SELECT artifact_id FROM artifacts WHERE project_id = ? AND blob_path = ?",
            (project_id, blob_path),
        )
        if any(ref["artifact_id"] not in artifact_ids for ref in refs):
            continue
        targets.append(
            FilesystemRemovalTarget(
                "artifact",
                row["artifact_id"],
                _stored_relative_path(artifact_store, blob_path) or artifact_store / blob_path,
            )
        )

    for row in log_rows:
        file_path = row["file_path"]
        if not file_path:
            continue
        key = ("log", file_path)
        if key in seen:
            continue
        seen.add(key)
        refs = all_rows(
            conn,
            "SELECT log_id FROM log_streams WHERE project_id = ? AND file_path = ?",
            (project_id, file_path),
        )
        if any(ref["log_id"] not in log_ids for ref in refs):
            continue
        targets.append(
            FilesystemRemovalTarget(
                "log",
                row["log_id"],
                _stored_relative_path(artifact_store, file_path) or artifact_store / file_path,
            )
        )
    return targets


def _experiment_remove_filesystem_targets(
    conn, home: Home, project_id: str, exp_id: str
) -> list[FilesystemRemovalTarget]:
    _project_root, _repo_git, artifact_store = _project_paths(home, project_id)
    targets: list[FilesystemRemovalTarget] = []
    seen: set[str] = set()

    def add(kind: str, object_id: str, path: Path | None) -> None:
        if path is None:
            return
        key = str(path.expanduser())
        if key in seen:
            return
        seen.add(key)
        targets.append(FilesystemRemovalTarget(kind=kind, object_id=object_id, path=path))

    for row in all_rows(
        conn,
        """
        SELECT path_registry_id, context_type, token_id, path
        FROM path_registry
        WHERE project_id = ? AND exp_id = ? AND status = 'active'
        ORDER BY context_type, path_registry_id
        """,
        (project_id, exp_id),
    ):
        object_id = (
            row["token_id"]
            if row["context_type"] == "inspection" and row["token_id"]
            else row["path_registry_id"]
        )
        add(row["context_type"], object_id, Path(row["path"]))

    for row in all_rows(
        conn,
        """
        SELECT DISTINCT l.file_path
        FROM log_streams l
        WHERE l.project_id = ? AND l.exp_id = ? AND l.file_path IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM log_streams other
            WHERE other.project_id = l.project_id
              AND other.file_path = l.file_path
              AND COALESCE(other.exp_id, '') != ?
          )
        ORDER BY l.file_path
        """,
        (project_id, exp_id, exp_id),
    ):
        add("log", row["file_path"], _stored_relative_path(artifact_store, row["file_path"]))

    for row in all_rows(
        conn,
        """
        SELECT DISTINCT a.blob_path
        FROM artifacts a
        WHERE a.project_id = ? AND a.exp_id = ? AND a.blob_path IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM artifacts other
            WHERE other.project_id = a.project_id
              AND other.blob_path = a.blob_path
              AND COALESCE(other.exp_id, '') != ?
          )
        ORDER BY a.blob_path
        """,
        (project_id, exp_id, exp_id),
    ):
        add("artifact", row["blob_path"], _stored_relative_path(artifact_store, row["blob_path"]))
    return targets


def cmd_exp_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args, ("--project", "--dry-run", "--cascade", "--force", "--confirm", "--reason")
    )
    require_options_at_most_once(args, ("--dry-run", "--cascade", "--reason"))
    require_dry_run_unforced(args)
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(args, "exp remove accepts exactly one experiment id")
    dry_run = flag(args, "--dry-run")
    cascade = flag(args, "--cascade")
    conn = require_home(req.globals.home)
    try:
        exp = dict(_exp_row(conn, project["project_id"], exp_id))
        blockers = [] if exp["status"] == "archived" else ["target_not_archived"]
        if one(conn, "SELECT lock_name FROM locks WHERE exp_id = ? LIMIT 1", (exp["exp_id"],)):
            blockers.append("experiment_has_active_lock")
        counts = {
            "runs": one(conn, "SELECT count(*) AS c FROM runs WHERE exp_id = ?", (exp["exp_id"],))[
                "c"
            ],
            "artifacts": one(
                conn, "SELECT count(*) AS c FROM artifacts WHERE exp_id = ?", (exp["exp_id"],)
            )["c"],
            "logs": one(
                conn, "SELECT count(*) AS c FROM log_streams WHERE exp_id = ?", (exp["exp_id"],)
            )["c"],
            "annotations": one(
                conn,
                "SELECT count(*) AS c FROM annotations WHERE project_id = ? AND (target_id = ? OR json_extract(target_json, '$.exp_id') = ?)",
                (project["project_id"], exp["exp_id"], exp["exp_id"]),
            )["c"],
            "tags": one(
                conn, "SELECT count(*) AS c FROM experiment_tags WHERE exp_id = ?", (exp["exp_id"],)
            )["c"],
            "submissions": one(
                conn,
                "SELECT count(*) AS c FROM experiment_submissions WHERE exp_id = ?",
                (exp["exp_id"],),
            )["c"],
        }
        filesystem_targets = _experiment_remove_filesystem_targets(
            conn, req.globals.home, project["project_id"], exp["exp_id"]
        )
        _project_root, repo_git, _artifact_store = _project_paths(
            req.globals.home, project["project_id"]
        )
        branch_ref = _experiment_branch_ref(exp["branch_name"])
        branch_ref_exists = _git_ref_commit(repo_git, branch_ref) is not None
    finally:
        conn.close()
    reason = _lifecycle_reason(args)
    if dry_run:
        return [
            ResultBlock(
                "experiment",
                [
                    ("exp id", exp["exp_id"]),
                    ("dry run", True),
                    ("removed", False),
                    ("cascade", cascade),
                    ("audit id", None),
                    ("blocker", blockers),
                    ("deleted runs", counts["runs"]),
                    ("deleted artifacts", counts["artifacts"]),
                    ("deleted logs", counts["logs"]),
                    ("deleted annotations", counts["annotations"]),
                    ("deleted tags", counts["tags"]),
                    ("deleted submissions", counts["submissions"]),
                    ("branch ref", branch_ref),
                    ("branch ref exists", branch_ref_exists),
                    ("deleted filesystem paths", len(filesystem_targets)),
                    ("filesystem path", [str(target.path) for target in filesystem_targets]),
                    (
                        "planned trash move",
                        [
                            _trash_plan(req.globals.home, target.path)
                            for target in filesystem_targets
                        ],
                    ),
                ],
            )
        ]
    require_force_confirm(
        args, exp["exp_id"], "experiment remove requires --force and matching --confirm"
    )
    if not cascade:
        raise AlabError("CONFIG_INVALID", "experiment remove requires --cascade")
    if blockers:
        raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
    _project_root, repo_git, _artifact_store = _project_paths(
        req.globals.home, project["project_id"]
    )
    audit_id = new_id("aud", "remove")
    stages = _stage_targets_to_trash(req.globals.home, filesystem_targets, audit_id)
    branch_deletion: GitRefDeletion | None = None
    try:
        branch_deletion = _delete_experiment_branch_ref(repo_git, exp["branch_name"])
        with Database(req.globals.home).tx() as tx:
            now = utc_now()
            tx.execute(
                "UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE exp_id = ? AND credential_type = 'token' AND status = 'active'",
                (now, exp["exp_id"]),
            )
            tx.execute(
                "UPDATE path_registry SET status = 'removed', removed_at = ?, removed_by_credential_id = ?, updated_at = ? WHERE exp_id = ? AND status = 'active'",
                (now, actor.credential_id, now, exp["exp_id"]),
            )
            audit(
                tx,
                action="remove",
                object_type="experiment",
                object_id=exp["exp_id"],
                actor=actor,
                audit_id=audit_id,
                project_id=project["project_id"],
                exp_id=exp["exp_id"],
                cascade=True,
                reason=reason,
                metadata={
                    "schema_version": 1,
                    "branch_ref": branch_deletion.branch_ref,
                    "branch_ref_commit": branch_deletion.commit,
                    "branch_ref_deleted": branch_deletion.deleted,
                    "branch_ref_already_absent": branch_deletion.already_absent,
                    "filesystem_target_count": len(filesystem_targets),
                    "filesystem_absent_count": sum(1 for stage in stages if stage.already_absent),
                    "trash": [
                        {
                            "kind": target.kind,
                            "object_id": target.object_id,
                            "mode": stage.mode,
                            "label": stage.audit_label,
                            "original_path_hash": path_hash(stage.original_path)
                            if stage.original_path
                            else None,
                            "already_absent": stage.already_absent,
                        }
                        for target, stage in zip(filesystem_targets, stages, strict=False)
                    ],
                },
            )
            tx.execute(
                "DELETE FROM annotation_revisions WHERE annotation_id IN (SELECT annotation_id FROM annotations WHERE project_id = ? AND (target_id = ? OR json_extract(target_json, '$.exp_id') = ?))",
                (project["project_id"], exp["exp_id"], exp["exp_id"]),
            )
            tx.execute(
                "DELETE FROM annotations WHERE project_id = ? AND (target_id = ? OR json_extract(target_json, '$.exp_id') = ?)",
                (project["project_id"], exp["exp_id"], exp["exp_id"]),
            )
            for table in [
                "experiment_tags",
                "experiment_submissions",
                "runs",
                "artifacts",
                "log_streams",
            ]:
                tx.execute(f"DELETE FROM {table} WHERE exp_id = ?", (exp["exp_id"],))
            tx.execute("DELETE FROM experiments WHERE exp_id = ?", (exp["exp_id"],))
    except Exception as exc:
        branch_restore_exc: Exception | None = None
        try:
            _restore_experiment_branch_ref(repo_git, branch_deletion)
        except Exception as restore_exc:
            branch_restore_exc = restore_exc
        if branch_restore_exc is not None:
            try:
                _restore_staged_trashes(stages)
            except Exception as restore_exc:
                detail = f"database update failed and trash restore failed: {restore_exc}; branch restore failed: {branch_restore_exc}"
                raise AlabError("STORAGE_ERROR", detail, "alab context repair") from restore_exc
            raise AlabError(
                "STORAGE_ERROR",
                f"database update failed and branch restore failed: {branch_restore_exc}",
                "alab context repair",
            ) from branch_restore_exc
        _raise_after_staged_trash_transaction_failure(exc, stages)
    _prune_missing_git_worktrees(repo_git)
    trash_cleanup_pending = _finalize_staged_trashes(
        req.globals.home, stages, project["project_id"]
    )
    return [
        ResultBlock(
            "experiment",
            [
                ("exp id", exp["exp_id"]),
                ("dry run", False),
                ("removed", True),
                ("cascade", True),
                ("audit id", audit_id),
                ("deleted runs", counts["runs"]),
                ("deleted artifacts", counts["artifacts"]),
                ("deleted logs", counts["logs"]),
                ("deleted annotations", counts["annotations"]),
                ("deleted tags", counts["tags"]),
                ("deleted submissions", counts["submissions"]),
                ("branch ref", branch_deletion.branch_ref if branch_deletion else branch_ref),
                ("deleted branch ref", branch_deletion.deleted if branch_deletion else False),
                (
                    "branch ref existed",
                    not branch_deletion.already_absent if branch_deletion else branch_ref_exists,
                ),
                ("deleted filesystem paths", len(filesystem_targets)),
                ("trash cleanup pending", trash_cleanup_pending),
            ],
        )
    ]
