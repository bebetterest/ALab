from __future__ import annotations

import shutil
from typing import Any

from .configs import project_config_json_obj
from .db import Database, all_rows, one
from .errors import AlabError
from .ids import new_id, require_complete_id
from .rendering import ResultBlock
from .service_args import (
    command_arg,
    flag,
    optional_positional_selector,
    require_dry_run_unforced,
    require_force_confirm,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_audit import audit
from .service_auth import require_actor, require_home
from .service_contracts import source_origin_metadata_obj
from .service_models import GitRefDeletion, Request
from .service_text import _lifecycle_reason
from .services import (
    _assert_source_import_no_existing_source_selectors,
    _delete_source_ref,
    _derived_source_name,
    _import_prepared_source_snapshot,
    _load_config_and_secrets,
    _prepare_source_work,
    _project_id_from_request,
    _project_paths,
    _require_project_admin,
    _restore_source_ref,
    _source_import_limits,
    _source_origin_mode,
)
from .timeutil import utc_now


def cmd_source_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--include-archived"))
    require_options_at_most_once(args, ("--project", "--include-archived"))
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    require_actor(req, ("root", "admin"), project_id=project_id)
    require_positional_count(args, 0, "source list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        if flag(args, "--include-archived"):
            rows = all_rows(conn, "SELECT * FROM sources WHERE project_id = ? ORDER BY created_at", (project_id,))
        else:
            rows = all_rows(conn, "SELECT * FROM sources WHERE project_id = ? AND status = 'active' ORDER BY created_at", (project_id,))
        return [
            ResultBlock(
                "source",
                [
                    ("source id", row["source_id"]),
                    ("source ref", row["source_ref"]),
                    ("source name", row["name"]),
                    ("status", row["status"]),
                    ("tree hash", row["tree_hash"]),
                    ("created at", row["created_at"]),
                    ("archived at", row["archived_at"]),
                ],
            )
            for row in rows
        ]
    finally:
        conn.close()

def cmd_source_import(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--name",
            "--source-path",
            "--source-git",
            "--source-empty",
            "--source-ref",
            "--git-ref",
            "--source-subdir",
            "--from-exp",
            "--from-commit",
            "--max-files",
            "--max-total-bytes",
            "--max-file-bytes",
        ),
    )
    require_options_at_most_once(
        args,
        (
            "--name",
            "--source-path",
            "--source-git",
            "--source-empty",
            "--source-ref",
            "--git-ref",
            "--source-subdir",
            "--from-exp",
            "--from-commit",
            "--max-files",
            "--max-total-bytes",
            "--max-file-bytes",
        ),
    )
    project, actor = _require_project_admin(args, req)
    _assert_source_import_no_existing_source_selectors(args)
    mode = _source_origin_mode(args)
    require_positional_count(args, 0, "source import accepts no positional arguments")
    limits = _source_import_limits(args)
    home = req.globals.home
    operation_dir = home.tmp_path / "source-import" / new_id("op", mode)
    operation_dir.mkdir(parents=True, exist_ok=True)
    try:
        prepared_source = _prepare_source_work(args, mode, operation_dir)
        conn = require_home(home)
        try:
            cfg, _secrets, _cfg_json = _load_config_and_secrets(conn, project["project_id"], project["latest_attempted_config_version"])
        finally:
            conn.close()
        name = _derived_source_name(args, mode)
        _project_root, repo_git, _artifact_store = _project_paths(home, project["project_id"])
        result = _import_prepared_source_snapshot(
            home=home,
            project_id=project["project_id"],
            repo_git=repo_git,
            cfg=cfg,
            actor=actor,
            prepared_source=prepared_source,
            source_name=name,
            limits=limits,
            warn_on_name_mismatch=command_arg(args, "--name") is not None,
        )
        return [
            ResultBlock(
                "source",
                [
                    ("project id", project["project_id"]),
                    ("source id", result.source_id),
                    ("source ref", result.source_ref),
                    ("source name", result.name),
                    ("tree hash", result.tree_hash),
                    ("deduped", result.deduped),
                    ("warning", result.warnings),
                ],
            )
        ]
    finally:
        shutil.rmtree(operation_dir, ignore_errors=True)

def _source_row(conn, project_id: str, source_id_or_ref: str | None) -> Any:
    if not source_id_or_ref:
        raise AlabError("SOURCE_NOT_FOUND", "source id is required")
    if not source_id_or_ref.startswith("alab/source/"):
        source_id_or_ref = require_complete_id(source_id_or_ref, "src")
    row = one(
        conn,
        "SELECT * FROM sources WHERE project_id = ? AND (source_id = ? OR source_ref = ?)",
        (project_id, source_id_or_ref, source_id_or_ref),
    )
    if row is None:
        raise AlabError("SOURCE_NOT_FOUND", "source not found")
    return row

def cmd_source_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--source-ref"))
    require_options_at_most_once(args, ("--source-ref",))
    project_id = _project_id_from_request(args, req)
    require_actor(req, ("root", "admin"), project_id=project_id)
    source_pos = optional_positional_selector(args, "source show accepts at most one source selector")
    source_ref = command_arg(args, "--source-ref")
    if source_pos and source_ref:
        raise AlabError("CONFIG_INVALID", "source show accepts only one source selector")
    source_selector = source_pos or source_ref
    conn = require_home(req.globals.home)
    try:
        source = _source_row(conn, project_id, source_selector)
        meta = source_origin_metadata_obj(source["origin_metadata_json"])
        origin = meta.get("primary_origin", {})
        return [
            ResultBlock(
                "source",
                [
                    ("source id", source["source_id"]),
                    ("source ref", source["source_ref"]),
                    ("source name", source["name"]),
                    ("status", source["status"]),
                    ("source commit", source["source_commit"]),
                    ("tree hash", source["tree_hash"]),
                    ("origin type", origin.get("origin_type")),
                    ("origin summary", origin.get("safe_summary")),
                ],
            )
        ]
    finally:
        conn.close()


def cmd_source_archive(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project, actor = _require_project_admin(args, req)
    source_selector = optional_positional_selector(args, "source archive accepts exactly one source selector")
    with Database(req.globals.home).tx() as conn:
        source = _source_row(conn, project["project_id"], source_selector)
        cfg, _secrets, _cfg_json = _load_config_and_secrets(conn, project["project_id"], project["latest_attempted_config_version"])
        if source["source_ref"] == cfg.source.default_source_ref and source["status"] != "archived":
            raise AlabError("RESOURCE_BUSY", "active default source cannot be archived")
        previous = source["status"]
        archived_at = source["archived_at"] or utc_now()
        if previous != "archived":
            conn.execute("UPDATE sources SET status = 'archived', archived_at = ? WHERE source_id = ?", (archived_at, source["source_id"]))
            audit(
                conn,
                action="archive",
                object_type="source",
                object_id=source["source_id"],
                actor=actor,
                project_id=project["project_id"],
                metadata={
                    "schema_version": 1,
                    "previous_status": previous,
                    "source_status": "archived",
                    "archived_at": archived_at,
                },
            )
        return [
            ResultBlock(
                "source",
                [
                    ("source id", source["source_id"]),
                    ("previous status", previous),
                    ("source status", "archived"),
                    ("archived at", archived_at),
                ],
            )
        ]


def cmd_source_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project, actor = _require_project_admin(args, req)
    source_selector = optional_positional_selector(args, "source unarchive accepts exactly one source selector")
    with Database(req.globals.home).tx() as conn:
        source = _source_row(conn, project["project_id"], source_selector)
        previous = source["status"]
        now = utc_now() if previous != "active" else None
        if previous != "active":
            conn.execute("UPDATE sources SET status = 'active', archived_at = NULL WHERE source_id = ?", (source["source_id"],))
            audit(
                conn,
                action="unarchive",
                object_type="source",
                object_id=source["source_id"],
                actor=actor,
                project_id=project["project_id"],
                metadata={
                    "schema_version": 1,
                    "previous_status": previous,
                    "source_status": "active",
                    "unarchived_at": now,
                },
            )
        return [
            ResultBlock(
                "source",
                [
                    ("source id", source["source_id"]),
                    ("previous status", previous),
                    ("source status", "active"),
                    ("unarchived at", now),
                ],
            )
        ]


def _source_remove_blockers(conn: Any, project_id: str, source: Any, *, cascade: bool) -> list[str]:
    blockers: list[str] = []
    if source["status"] != "archived":
        blockers.append("target_not_archived")
    for cfg_row in all_rows(conn, "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ?", (project_id,)):
        cfg_json = project_config_json_obj(cfg_row["canonical_config_json"])
        if cfg_json.get("source", {}).get("default_source_ref") == source["source_ref"]:
            blockers.append("referenced_by_config_version")
            break
    dependent_experiments = all_rows(
        conn,
        "SELECT exp_id, status FROM experiments WHERE project_id = ? AND source_id = ? ORDER BY exp_id",
        (project_id, source["source_id"]),
    )
    if dependent_experiments:
        if not cascade:
            blockers.append("dependent_records_require_cascade")
        elif any(row["status"] != "archived" for row in dependent_experiments):
            blockers.append("dependent_records_not_archived")
    return blockers


def cmd_source_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--cascade", "--force", "--confirm", "--reason"))
    require_options_at_most_once(args, ("--dry-run", "--cascade", "--reason"))
    require_dry_run_unforced(args)
    project, actor = _require_project_admin(args, req)
    source_selector = optional_positional_selector(args, "source remove accepts exactly one source selector")
    dry_run = flag(args, "--dry-run")
    cascade = flag(args, "--cascade")
    conn = require_home(req.globals.home)
    try:
        source = _source_row(conn, project["project_id"], source_selector)
        blockers = _source_remove_blockers(conn, project["project_id"], source, cascade=cascade)
    finally:
        conn.close()
    reason = _lifecycle_reason(args)
    if dry_run:
        return [
            ResultBlock(
                "source",
                [
                    ("source id", source["source_id"]),
                    ("dry run", True),
                    ("removed", False),
                    ("cascade", cascade),
                    ("audit id", None),
                    ("blocker", blockers),
                ],
            )
        ]
    require_force_confirm(args, source["source_id"], "source remove requires --force and matching --confirm")
    if blockers:
        raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
    _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project["project_id"])
    branch_deletion: GitRefDeletion | None = None
    try:
        branch_deletion = _delete_source_ref(repo_git, source["source_ref"])
        with Database(req.globals.home).tx() as tx:
            current_source = _source_row(tx, project["project_id"], source["source_id"])
            current_blockers = _source_remove_blockers(tx, project["project_id"], current_source, cascade=cascade)
            if current_blockers:
                raise AlabError("RESOURCE_BUSY", ", ".join(current_blockers))
            tx.execute("DELETE FROM sources WHERE source_id = ?", (current_source["source_id"],))
            audit_id = audit(
                tx,
                action="remove",
                object_type="source",
                object_id=current_source["source_id"],
                actor=actor,
                project_id=project["project_id"],
                cascade=cascade,
                reason=reason,
                metadata={
                    "schema_version": 1,
                    "branch_ref": branch_deletion.branch_ref,
                    "branch_ref_commit": branch_deletion.commit,
                    "branch_ref_deleted": branch_deletion.deleted,
                    "branch_ref_already_absent": branch_deletion.already_absent,
                },
            )
    except Exception as exc:
        try:
            _restore_source_ref(repo_git, branch_deletion)
        except Exception as restore_exc:
            raise AlabError("STORAGE_ERROR", f"database update failed and source ref restore failed: {restore_exc}", "alab context repair") from restore_exc
        if isinstance(exc, AlabError):
            raise exc
        raise AlabError("STORAGE_ERROR", f"database update failed after source ref deletion: {type(exc).__name__}", "alab context repair") from exc
    return [
        ResultBlock(
            "source",
            [
                ("source id", source["source_id"]),
                ("dry run", False),
                ("removed", True),
                ("cascade", cascade),
                ("audit id", audit_id),
                ("blocker", []),
            ],
        )
    ]
