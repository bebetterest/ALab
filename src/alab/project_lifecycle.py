from __future__ import annotations

from pathlib import Path
from typing import Any

from . import services as _core
from .configs import project_config_json_obj
from .context import path_hash
from .db import Database, all_rows, one
from .errors import AlabError
from .home import Home
from .project_config import _runner_sandbox_summary
from .removal import (
    _finalize_staged_trashes,
    _raise_after_staged_trash_transaction_failure,
    _stage_targets_to_trash,
    _trash_plan,
)
from .rendering import ResultBlock, multiline_text
from .service_args import (
    flag,
    require_dry_run_unforced,
    require_force_confirm,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_auth import require_actor, require_home
from .service_models import FilesystemRemovalTarget, Request, ResolvedRemovalTarget
from .service_text import _lifecycle_reason
from .timeutil import utc_now

_load_config_and_secrets = _core._load_config_and_secrets
_project_id_from_request = _core._project_id_from_request
_project_paths = _core._project_paths
_project_row = _core._project_row
_require_project_admin = _core._require_project_admin


def audit(*args: Any, **kwargs: Any) -> str:
    return _core.audit(*args, **kwargs)


def new_id(*args: Any, **kwargs: Any) -> str:
    return _core.new_id(*args, **kwargs)


def cmd_project_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--include-archived",))
    require_options_at_most_once(args, ("--include-archived",))
    require_actor(req, "root")
    require_positional_count(args, 0, "project list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        if flag(args, "--include-archived"):
            rows = all_rows(conn, "SELECT * FROM projects ORDER BY created_at")
        else:
            rows = all_rows(conn, "SELECT * FROM projects WHERE status != 'archived' ORDER BY created_at")
        return [
            ResultBlock(
                "project",
                [
                    ("project id", row["project_id"]),
                    (
                        "project name",
                        project_config_json_obj(
                            one(
                                conn,
                                "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?",
                                (row["project_id"], row["latest_attempted_config_version"]),
                            )["canonical_config_json"]
                        )["project"]["name"],
                    ),
                    ("project status", row["status"]),
                    ("created at", row["created_at"]),
                    ("updated at", row["updated_at"]),
                    ("archived at", row["archived_at"]),
                ],
            )
            for row in rows
        ]
    finally:
        conn.close()


def cmd_project_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project_id = _project_id_from_request(args, req)
    require_actor(req, ("root", "admin"), project_id=project_id)
    require_positional_count(args, 0, "project show accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        cfg, _, _cfg_json = _load_config_and_secrets(
            conn, project["project_id"], project["latest_attempted_config_version"]
        )
        return [
            ResultBlock(
                "project",
                [
                    ("project id", project["project_id"]),
                    ("home id", one(conn, "SELECT home_id FROM homes LIMIT 1")["home_id"]),
                    ("project name", cfg.project.name),
                    ("status", project["status"]),
                    ("task", multiline_text(cfg.project.task)),
                    ("goal", multiline_text(cfg.project.goal)),
                    ("active config version", project["active_valid_config_version"]),
                    ("latest attempted config version", project["latest_attempted_config_version"]),
                    ("default source", cfg.source.default_source_ref),
                    ("runner type", cfg.runner.type),
                    ("sandbox", _runner_sandbox_summary(cfg)),
                    ("reward type", cfg.reward.type),
                    ("visibility scope", cfg.visibility.scope),
                    ("mutable summary", f"include={len(cfg.mutable.include)} exclude={len(cfg.mutable.exclude)}"),
                    ("public exp create", cfg.project.allow_public_exp_create),
                ],
            )
        ]
    finally:
        conn.close()


def cmd_project_archive(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project, actor = _require_project_admin(args, req)
    require_positional_count(args, 0, "project archive accepts no positional arguments")
    with Database(req.globals.home).tx() as conn:
        project = dict(_project_row(conn, project["project_id"]))
        previous = project["status"]
        archived_at = project["archived_at"] or utc_now()
        if previous != "archived":
            active_lock = one(conn, "SELECT lock_name FROM locks WHERE project_id = ? LIMIT 1", (project["project_id"],))
            if active_lock:
                raise AlabError("RESOURCE_BUSY", "project has active locks")
            conn.execute(
                "UPDATE projects SET status = 'archived', pre_archive_status = ?, archived_at = ?, updated_at = ? WHERE project_id = ?",
                (previous, archived_at, archived_at, project["project_id"]),
            )
            audit(
                conn,
                action="archive",
                object_type="project",
                object_id=project["project_id"],
                actor=actor,
                project_id=project["project_id"],
                metadata={
                    "schema_version": 1,
                    "previous_status": previous,
                    "project_status": "archived",
                    "archived_at": archived_at,
                },
            )
        return [
            ResultBlock(
                "project",
                [
                    ("project id", project["project_id"]),
                    ("previous status", previous),
                    ("project status", "archived"),
                    ("archived at", archived_at),
                ],
            )
        ]


def cmd_project_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project, actor = _require_project_admin(args, req)
    require_positional_count(args, 0, "project unarchive accepts no positional arguments")
    with Database(req.globals.home).tx() as conn:
        project = dict(_project_row(conn, project["project_id"]))
        previous = project["status"]
        restored = project["pre_archive_status"] or "invalid"
        now = utc_now() if previous == "archived" else None
        if previous == "archived":
            conn.execute(
                "UPDATE projects SET status = ?, pre_archive_status = NULL, archived_at = NULL, updated_at = ? WHERE project_id = ?",
                (restored, now, project["project_id"]),
            )
            audit(
                conn,
                action="unarchive",
                object_type="project",
                object_id=project["project_id"],
                actor=actor,
                project_id=project["project_id"],
                metadata={
                    "schema_version": 1,
                    "previous_status": previous,
                    "project_status": restored,
                    "unarchived_at": now,
                },
            )
        return [
            ResultBlock(
                "project",
                [
                    ("project id", project["project_id"]),
                    ("previous status", previous),
                    ("project status", restored if previous == "archived" else previous),
                    ("unarchived at", now),
                ],
            )
        ]


def _resolve_removal_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _dedupe_nested_removal_targets(targets: list[FilesystemRemovalTarget]) -> list[FilesystemRemovalTarget]:
    resolved_targets = [
        ResolvedRemovalTarget(target, _resolve_removal_path(target.path), order)
        for order, target in enumerate(targets)
    ]
    resolved_targets.sort(key=lambda item: (len(item.resolved.parts), str(item.resolved), item.order))
    kept: list[ResolvedRemovalTarget] = []
    seen: set[str] = set()
    for item in resolved_targets:
        key = str(item.resolved)
        if key in seen:
            continue
        if any(item.resolved == kept_item.resolved or kept_item.resolved in item.resolved.parents for kept_item in kept):
            continue
        seen.add(key)
        kept.append(item)
    return [item.target for item in kept]


def _project_remove_filesystem_targets(conn, home: Home, project: dict[str, Any]) -> list[FilesystemRemovalTarget]:
    project_id = project["project_id"]
    project_root, repo_git, artifact_store = _project_paths(home, project_id)
    targets: list[FilesystemRemovalTarget] = [
        FilesystemRemovalTarget("project_root", project_id, project_root),
        FilesystemRemovalTarget(
            "project_repo",
            project_id,
            Path(project["canonical_repo_path"]) if project.get("canonical_repo_path") else repo_git,
        ),
        FilesystemRemovalTarget("project_artifacts", project_id, artifact_store),
    ]
    if project.get("control_path"):
        targets.append(FilesystemRemovalTarget("project_control", project_id, Path(project["control_path"])))
    for row in all_rows(
        conn,
        """
        SELECT path_registry_id, context_type, token_id, path
        FROM path_registry
        WHERE project_id = ? AND status = 'active'
        ORDER BY context_type, path_registry_id
        """,
        (project_id,),
    ):
        object_id = row["token_id"] if row["context_type"] == "inspection" and row["token_id"] else row["path_registry_id"]
        targets.append(FilesystemRemovalTarget(row["context_type"], object_id, Path(row["path"])))
    return _dedupe_nested_removal_targets(targets)


def cmd_project_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--cascade", "--force", "--confirm", "--reason"))
    project_id = _project_id_from_request(args, req)
    actor = require_actor(req, "root", project_id=project_id)
    require_options_at_most_once(args, ("--dry-run", "--cascade", "--reason"))
    require_dry_run_unforced(args)
    require_positional_count(args, 0, "project remove accepts no positional arguments")
    dry_run = flag(args, "--dry-run")
    cascade = flag(args, "--cascade")
    conn = require_home(req.globals.home)
    try:
        project = dict(_project_row(conn, project_id))
        blockers = [] if project["status"] == "archived" else ["target_not_archived"]
        if one(conn, "SELECT lock_name FROM locks WHERE project_id = ? LIMIT 1", (project["project_id"],)):
            blockers.append("project_has_active_lock")
        counts = {
            "experiments": one(conn, "SELECT count(*) AS c FROM experiments WHERE project_id = ?", (project["project_id"],))["c"],
            "runs": one(conn, "SELECT count(*) AS c FROM runs WHERE project_id = ?", (project["project_id"],))["c"],
            "artifacts": one(conn, "SELECT count(*) AS c FROM artifacts WHERE project_id = ?", (project["project_id"],))["c"],
            "logs": one(conn, "SELECT count(*) AS c FROM log_streams WHERE project_id = ?", (project["project_id"],))["c"],
            "sources": one(conn, "SELECT count(*) AS c FROM sources WHERE project_id = ?", (project["project_id"],))["c"],
        }
        filesystem_targets = _project_remove_filesystem_targets(conn, req.globals.home, project)
    finally:
        conn.close()
    reason = _lifecycle_reason(args)
    if not cascade:
        raise AlabError("CONFIG_INVALID", "project remove requires --cascade")
    if dry_run:
        return [
            ResultBlock(
                "project",
                [
                    ("project id", project["project_id"]),
                    ("dry run", True),
                    ("removed", False),
                    ("cascade", cascade),
                    ("audit id", None),
                    ("blocker", blockers),
                    ("deleted experiments", counts["experiments"]),
                    ("deleted runs", counts["runs"]),
                    ("deleted artifacts", counts["artifacts"]),
                    ("deleted logs", counts["logs"]),
                    ("deleted sources", counts["sources"]),
                    ("deleted filesystem paths", len(filesystem_targets)),
                    ("filesystem path", [str(target.path) for target in filesystem_targets]),
                    ("planned trash move", [_trash_plan(req.globals.home, target.path) for target in filesystem_targets]),
                ],
            )
        ]
    require_force_confirm(args, project["project_id"], "project remove requires --force and matching --confirm")
    if blockers:
        raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
    audit_id = new_id("aud", "remove")
    stages = _stage_targets_to_trash(req.globals.home, filesystem_targets, audit_id)
    try:
        with Database(req.globals.home).tx() as tx:
            now = utc_now()
            tx.execute(
                "UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE project_id = ? AND status = 'active'",
                (now, project["project_id"]),
            )
            tx.execute(
                "UPDATE path_registry SET status = 'removed', removed_at = ?, removed_by_credential_id = ?, updated_at = ? WHERE project_id = ? AND status = 'active'",
                (now, actor.credential_id, now, project["project_id"]),
            )
            audit(
                tx,
                action="remove",
                object_type="project",
                object_id=project["project_id"],
                actor=actor,
                audit_id=audit_id,
                project_id=project["project_id"],
                cascade=True,
                reason=reason,
                metadata={
                    "schema_version": 1,
                    "filesystem_target_count": len(filesystem_targets),
                    "filesystem_absent_count": sum(1 for stage in stages if stage.already_absent),
                    "trash": [
                        {
                            "kind": target.kind,
                            "object_id": target.object_id,
                            "mode": stage.mode,
                            "label": stage.audit_label,
                            "original_path_hash": path_hash(stage.original_path) if stage.original_path else None,
                            "already_absent": stage.already_absent,
                        }
                        for target, stage in zip(filesystem_targets, stages, strict=False)
                    ],
                },
            )
            tx.execute(
                "DELETE FROM annotation_revisions WHERE annotation_id IN (SELECT annotation_id FROM annotations WHERE project_id = ?)",
                (project["project_id"],),
            )
            for table in [
                "annotations",
                "experiment_tags",
                "experiment_submissions",
                "runs",
                "project_validations",
                "artifacts",
                "log_streams",
                "experiments",
                "sources",
                "project_config_versions",
                "secret_values",
                "locks",
                "projects",
            ]:
                tx.execute(f"DELETE FROM {table} WHERE project_id = ?", (project["project_id"],))
    except Exception as exc:
        _raise_after_staged_trash_transaction_failure(exc, stages)
    trash_cleanup_pending = _finalize_staged_trashes(req.globals.home, stages, project["project_id"])
    return [
        ResultBlock(
            "project",
            [
                ("project id", project["project_id"]),
                ("dry run", False),
                ("removed", True),
                ("cascade", True),
                ("audit id", audit_id),
                ("deleted experiments", counts["experiments"]),
                ("deleted runs", counts["runs"]),
                ("deleted artifacts", counts["artifacts"]),
                ("deleted logs", counts["logs"]),
                ("deleted sources", counts["sources"]),
                ("deleted filesystem paths", len(filesystem_targets)),
                ("trash cleanup pending", trash_cleanup_pending),
            ],
        )
    ]


def cmd_project_locks_clear_stale(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project, actor = _require_project_admin(args, req)
    require_positional_count(args, 0, "project locks clear-stale accepts no positional arguments")
    with Database(req.globals.home).tx() as conn:
        now = utc_now()
        rows = all_rows(conn, "SELECT * FROM locks WHERE project_id = ? AND expires_at < ? ORDER BY lock_name", (project["project_id"], now))
        lock_names = [row["lock_name"] for row in rows]
        audit_id = None
        if lock_names:
            conn.executemany("DELETE FROM locks WHERE lock_name = ?", [(name,) for name in lock_names])
            audit_id = audit(
                conn,
                action="clear",
                object_type="lock",
                object_id=project["project_id"],
                actor=actor,
                project_id=project["project_id"],
                metadata={"schema_version": 1, "cleared_count": len(lock_names)},
            )
    return [
        ResultBlock(
            "lock_clear",
            [
                ("project id", project["project_id"]),
                ("cleared count", len(lock_names)),
                ("lock name", lock_names),
                ("audit id", audit_id),
            ],
        )
    ]
