from __future__ import annotations

from typing import Any

from . import services as _core
from .configs import config_hash, is_free_evaluation_config
from .db import Database, all_rows, one
from .errors import AlabError
from .rendering import ResultBlock
from .service_args import (
    flag,
    optional_positional_selector,
    require_dry_run_unforced,
    require_force_confirm,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_auth import require_home
from .service_models import Request
from .service_text import _lifecycle_reason
from .timeutil import utc_now

_require_project_admin = _core._require_project_admin
_project_row = _core._project_row
_complete_id_or_missing = _core._complete_id_or_missing
_interrupt_stale_running_records = _core._interrupt_stale_running_records
_load_config_and_secrets = _core._load_config_and_secrets
_source_for_ref = _core._source_for_ref
_execution_record_object_json = _core._execution_record_object_json
_run_validation = _core._run_validation
_baseline_failure_fields = _core._baseline_failure_fields
_artifact_log_filesystem_targets = _core._artifact_log_filesystem_targets
_trash_plan = _core._trash_plan
_stage_targets_to_trash = _core._stage_targets_to_trash
_raise_after_staged_trash_transaction_failure = _core._raise_after_staged_trash_transaction_failure
_finalize_staged_trashes = _core._finalize_staged_trashes
path_hash = _core.path_hash


def audit(*args: Any, **kwargs: Any) -> str:
    return _core.audit(*args, **kwargs)


def new_id(*args: Any, **kwargs: Any) -> str:
    return _core.new_id(*args, **kwargs)


def cmd_project_validate(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project, actor = _require_project_admin(args, req)
    require_positional_count(args, 0, "project validate accepts no positional arguments")
    db = Database(req.globals.home)
    with db.tx() as conn:
        _interrupt_stale_running_records(conn, project_id=project["project_id"])
        project = dict(_project_row(conn, project["project_id"]))
        version = project["latest_attempted_config_version"]
        cfg, secrets_map, cfg_json = _load_config_and_secrets(conn, project["project_id"], version)
        source = _source_for_ref(conn, project["project_id"], cfg.source.default_source_ref)
        validation_id = new_id("val", "manual")
        now = utc_now()
        free_evaluation = is_free_evaluation_config(cfg)
        conn.execute(
            """
            INSERT INTO project_validations(validation_id, project_id, config_version, source_ref, source_commit,
              status, exit_code, reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, 'not_attempted', 'active', ?, ?, ?)
            """,
            (
                validation_id,
                project["project_id"],
                version,
                source["source_ref"],
                source["source_commit"],
                "not_required" if free_evaluation else "running",
                now,
                now if free_evaluation else None,
                _execution_record_object_json(
                    config_hash_value=config_hash(cfg_json),
                    runner_type=cfg.runner.type,
                    reward_type=cfg.reward.type,
                ),
            ),
        )
        conn.execute(
            "UPDATE project_config_versions SET baseline_required = ?, validation_status = ?, inherited_from_validation_id = NULL WHERE project_id = ? AND version = ?",
            (
                0 if free_evaluation else 1,
                "not_required" if free_evaluation else "running",
                project["project_id"],
                version,
            ),
        )
    if free_evaluation:
        status, exit_code, reward, reward_parse_status, warning_codes = "not_required", None, None, "not_attempted", []
        project_status = "valid"
        with db.tx() as conn:
            conn.execute(
                "UPDATE projects SET status = 'valid', active_valid_config_version = ?, active_validation_id = ?, updated_at = ? WHERE project_id = ?",
                (version, validation_id, utc_now(), project["project_id"]),
            )
    else:
        with db.tx() as conn:
            status, exit_code, reward, reward_parse_status, warning_codes = _run_validation(
                conn,
                req.globals.home,
                project["project_id"],
                validation_id,
                source["source_ref"],
                source["source_commit"],
                version,
                cfg,
                secrets_map,
            )
            project_status = "valid" if status == "passed" else "invalid"
            active_version = version if status == "passed" else project["active_valid_config_version"]
            active_validation = validation_id if status == "passed" else project["active_validation_id"]
            conn.execute(
                "UPDATE projects SET status = ?, active_valid_config_version = ?, active_validation_id = ?, updated_at = ? WHERE project_id = ?",
                (project_status, active_version, active_validation, utc_now(), project["project_id"]),
            )
            conn.execute(
                "UPDATE project_config_versions SET validation_status = ? WHERE project_id = ? AND version = ?",
                (status, project["project_id"], version),
            )
    next_action = (
        "alab exp create --name <name>"
        if project_status == "valid"
        else "fix config or source and rerun alab project validate"
    )
    fields: list[tuple[str, Any]] = [
        ("project id", project["project_id"]),
        ("validation id", validation_id),
        ("config version", version),
        ("validation status", status),
        ("exit code", exit_code),
        ("reward", reward),
        ("reward parse status", reward_parse_status),
        ("project status", project_status),
        ("warning code", warning_codes),
    ]
    failure_fields = _baseline_failure_fields(status, next_action)
    if failure_fields:
        fields.extend(failure_fields)
    else:
        fields.append(("next", next_action))
    return [ResultBlock("validation", fields)]


def _validation_row(conn, project_id: str, validation_id: str | None) -> Any:
    validation_id = _complete_id_or_missing(
        validation_id, prefix="val", code="VALIDATION_NOT_FOUND", label="validation id"
    )
    row = one(
        conn,
        "SELECT * FROM project_validations WHERE project_id = ? AND validation_id = ?",
        (project_id, validation_id),
    )
    if row is None:
        raise AlabError("VALIDATION_NOT_FOUND", "validation not found")
    return row


def _validation_blockers(project: Any, row: Any) -> list[str]:
    blockers: list[str] = []
    if row["validation_id"] == project["active_validation_id"]:
        blockers.append("active_validation")
    if row["status"] == "running":
        blockers.append("validation_running")
    return blockers


def cmd_project_validation_archive(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project, actor = _require_project_admin(args, req)
    validation_id = optional_positional_selector(
        args, "validation archive accepts exactly one validation id"
    )
    with Database(req.globals.home).tx() as conn:
        _interrupt_stale_running_records(conn, project_id=project["project_id"])
        row = _validation_row(conn, project["project_id"], validation_id)
        blockers = _validation_blockers(project, row)
        if blockers:
            raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
        previous = row["archive_status"]
        archived_at = (
            row["archived_at"] if previous == "archived" and row["archived_at"] else utc_now()
        )
        audit_id = None
        if previous != "archived":
            conn.execute(
                "UPDATE project_validations SET archive_status = 'archived', archived_at = ? WHERE validation_id = ?",
                (archived_at, row["validation_id"]),
            )
            audit_id = audit(
                conn,
                action="archive",
                object_type="validation",
                object_id=row["validation_id"],
                actor=actor,
                project_id=project["project_id"],
                metadata={
                    "schema_version": 1,
                    "previous_archive_status": previous,
                    "archive_status": "archived",
                    "archived_at": archived_at,
                },
            )
    return [
        ResultBlock(
            "validation",
            [
                ("project id", project["project_id"]),
                ("validation id", validation_id),
                ("previous archive status", previous),
                ("archive status", "archived"),
                ("archived at", archived_at),
                ("audit id", audit_id),
            ],
        )
    ]


def cmd_project_validation_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project, actor = _require_project_admin(args, req)
    validation_id = optional_positional_selector(
        args, "validation unarchive accepts exactly one validation id"
    )
    with Database(req.globals.home).tx() as conn:
        _interrupt_stale_running_records(conn, project_id=project["project_id"])
        row = _validation_row(conn, project["project_id"], validation_id)
        previous = row["archive_status"]
        unarchived_at = utc_now() if previous != "active" else row["unarchived_at"]
        audit_id = None
        if previous != "active":
            conn.execute(
                "UPDATE project_validations SET archive_status = 'active', archived_at = NULL, unarchived_at = ? WHERE validation_id = ?",
                (unarchived_at, row["validation_id"]),
            )
            audit_id = audit(
                conn,
                action="unarchive",
                object_type="validation",
                object_id=row["validation_id"],
                actor=actor,
                project_id=project["project_id"],
                metadata={
                    "schema_version": 1,
                    "previous_archive_status": previous,
                    "archive_status": "active",
                    "unarchived_at": unarchived_at,
                },
            )
    return [
        ResultBlock(
            "validation",
            [
                ("project id", project["project_id"]),
                ("validation id", validation_id),
                ("previous archive status", previous),
                ("archive status", "active"),
                ("unarchived at", unarchived_at),
                ("audit id", audit_id),
            ],
        )
    ]


def cmd_project_validation_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args, ("--project", "--dry-run", "--cascade", "--force", "--confirm", "--reason")
    )
    require_options_at_most_once(args, ("--dry-run", "--cascade", "--reason"))
    require_dry_run_unforced(args)
    project, actor = _require_project_admin(args, req)
    validation_id = optional_positional_selector(
        args, "validation remove accepts exactly one validation id"
    )
    dry_run = flag(args, "--dry-run")
    cascade = flag(args, "--cascade")
    conn = require_home(req.globals.home)
    try:
        _interrupt_stale_running_records(conn, project_id=project["project_id"])
        conn.commit()
        row = dict(_validation_row(conn, project["project_id"], validation_id))
        blockers = _validation_blockers(project, row)
        if row["archive_status"] != "archived":
            blockers.append("target_not_archived")
        artifact_rows = all_rows(
            conn,
            "SELECT * FROM artifacts WHERE project_id = ? AND validation_id = ? ORDER BY artifact_id",
            (project["project_id"], row["validation_id"]),
        )
        log_rows = all_rows(
            conn,
            "SELECT * FROM log_streams WHERE project_id = ? AND validation_id = ? ORDER BY log_id",
            (project["project_id"], row["validation_id"]),
        )
        counts = {"artifacts": len(artifact_rows), "logs": len(log_rows)}
        active_dependent_artifacts = sum(
            1 for artifact in artifact_rows if artifact["archive_status"] != "archived"
        )
        active_dependent_logs = sum(1 for log in log_rows if log["archive_status"] != "archived")
        if (counts["artifacts"] or counts["logs"]) and not cascade:
            blockers.append("dependent_records_require_cascade")
        if cascade and (active_dependent_artifacts or active_dependent_logs):
            blockers.append("dependent_records_not_archived")
        filesystem_targets = _artifact_log_filesystem_targets(
            conn,
            req.globals.home,
            project["project_id"],
            artifact_rows=artifact_rows,
            log_rows=log_rows,
        )
    finally:
        conn.close()
    reason = _lifecycle_reason(args)
    if dry_run:
        return [
            ResultBlock(
                "validation",
                [
                    ("project id", project["project_id"]),
                    ("validation id", row["validation_id"]),
                    ("dry run", True),
                    ("removed", False),
                    ("cascade", cascade),
                    ("audit id", None),
                    ("blocker", blockers),
                    ("deleted artifacts", counts["artifacts"]),
                    ("deleted logs", counts["logs"]),
                    ("active dependent artifacts", active_dependent_artifacts),
                    ("active dependent logs", active_dependent_logs),
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
        args, row["validation_id"], "validation remove requires --force and matching --confirm"
    )
    if blockers:
        raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
    audit_id = new_id("aud", "remove")
    stages = _stage_targets_to_trash(req.globals.home, filesystem_targets, audit_id)
    try:
        with Database(req.globals.home).tx() as tx:
            audit(
                tx,
                action="remove",
                object_type="validation",
                object_id=row["validation_id"],
                actor=actor,
                audit_id=audit_id,
                project_id=project["project_id"],
                cascade=cascade,
                reason=reason,
                metadata={
                    "schema_version": 1,
                    "deleted_artifact_count": counts["artifacts"],
                    "deleted_log_count": counts["logs"],
                    "active_dependent_artifact_count": active_dependent_artifacts,
                    "active_dependent_log_count": active_dependent_logs,
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
            tx.execute("DELETE FROM artifacts WHERE validation_id = ?", (row["validation_id"],))
            tx.execute("DELETE FROM log_streams WHERE validation_id = ?", (row["validation_id"],))
            tx.execute(
                "DELETE FROM project_validations WHERE validation_id = ?", (row["validation_id"],)
            )
    except Exception as exc:
        _raise_after_staged_trash_transaction_failure(exc, stages)
    trash_cleanup_pending = _finalize_staged_trashes(
        req.globals.home, stages, project["project_id"]
    )
    return [
        ResultBlock(
            "validation",
            [
                ("project id", project["project_id"]),
                ("validation id", row["validation_id"]),
                ("dry run", False),
                ("removed", True),
                ("cascade", cascade),
                ("audit id", audit_id),
                ("blocker", []),
                ("deleted artifacts", counts["artifacts"]),
                ("deleted logs", counts["logs"]),
                ("active dependent artifacts", active_dependent_artifacts),
                ("active dependent logs", active_dependent_logs),
                ("deleted filesystem paths", len(filesystem_targets)),
                ("trash cleanup pending", trash_cleanup_pending),
            ],
        )
    ]
