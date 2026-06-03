from __future__ import annotations

from pathlib import Path
from typing import Any

from .auth import Actor
from .context import path_hash
from .db import Database, all_rows, one
from .errors import AlabError
from .home import Home
from .ids import new_id
from .rendering import ResultBlock, multiline_text
from .service_args import (
    _append_time_filter,
    _commit_sha_filter,
    _content_hash_filter,
    _parse_bool_option,
    _parse_float_option,
    _parse_int_option,
    _parse_non_negative_int_option,
    _parse_positive_int_option,
    _register_observe_text_predicates,
    _require_option_choice,
    _require_ordered_range,
    _require_ordered_time_range,
    _sql_order_limit_clause,
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
from .service_auth import require_home
from .service_contracts import execution_record_json_obj
from .service_models import ARTIFACT_ROOTS, LOG_STREAMS, RUNNER_TYPES, Request
from .service_text import _lifecycle_reason
from .services import (
    _append_visible_exp_clause,
    _artifact_log_filesystem_targets,
    _assert_export_output_path,
    _authorize_observe,
    _complete_id_option,
    _complete_id_or_missing,
    _exp_visible,
    _experiment_branch_ref,
    _finalize_staged_trashes,
    _git_ref_commit,
    _interrupt_stale_running_records,
    _project_id_from_request,
    _project_paths,
    _raise_after_staged_trash_transaction_failure,
    _stage_targets_to_trash,
    _trash_plan,
)
from .timeutil import utc_now


def cmd_observe_runs_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--include-archived",
            "--exp",
            "--status",
            "--config-version",
            "--commit",
            "--reward-min",
            "--reward-max",
            "--runner-type",
            "--exit-code",
            "--failure-reason-query",
            "--started-after",
            "--started-before",
            "--ended-after",
            "--ended-before",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    require_options_at_most_once(
        args,
        (
            "--project",
            "--include-archived",
            "--exp",
            "--status",
            "--config-version",
            "--commit",
            "--reward-min",
            "--reward-max",
            "--runner-type",
            "--exit-code",
            "--failure-reason-query",
            "--started-after",
            "--started-before",
            "--ended-after",
            "--ended-before",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    actor = _authorize_observe(req, project_id)
    require_positional_count(args, 0, "runs list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        include_archived = flag(args, "--include-archived")
        clauses = ["project_id = ?"]
        params: list[Any] = [project_id]
        _append_visible_exp_clause(conn, project_id, actor, clauses, params)
        exp_filter = _complete_id_option(args, "--exp", "exp")
        if exp_filter:
            clauses.append("exp_id = ?")
            params.append(exp_filter)
        status = _require_option_choice(command_arg(args, "--status"), "--status", {"passed", "failed", "error", "timeout", "running", "interrupted"})
        if status:
            clauses.append("status = ?")
            params.append(status)
        config_version = _parse_positive_int_option(args, "--config-version")
        if config_version is not None:
            clauses.append("config_version = ?")
            params.append(config_version)
        commit_filter = _commit_sha_filter(command_arg(args, "--commit"))
        if commit_filter:
            clauses.append("commit_sha LIKE ?")
            params.append(f"{commit_filter}%")
        reward_min = _parse_float_option(args, "--reward-min")
        reward_max = _parse_float_option(args, "--reward-max")
        _require_ordered_range(reward_min, reward_max, "--reward-min", "--reward-max")
        if reward_min is not None:
            clauses.append("reward_value >= ?")
            params.append(reward_min)
        if reward_max is not None:
            clauses.append("reward_value <= ?")
            params.append(reward_max)
        exit_code = _parse_int_option(args, "--exit-code")
        if exit_code is not None:
            clauses.append("exit_code = ?")
            params.append(exit_code)
        _require_ordered_time_range(args, "--started-after", "--started-before")
        _require_ordered_time_range(args, "--ended-after", "--ended-before")
        for option, column, op in [
            ("--started-after", "started_at", ">="),
            ("--started-before", "started_at", "<="),
            ("--ended-after", "ended_at", ">="),
            ("--ended-before", "ended_at", "<="),
        ]:
            _append_time_filter(args, clauses, params, option, column, op)
        if not include_archived:
            clauses.append("archive_status = 'active'")
        runner_type = _require_option_choice(command_arg(args, "--runner-type"), "--runner-type", RUNNER_TYPES)
        if runner_type:
            clauses.append("record_json LIKE ?")
            params.append(f'%"runner":{{%"type":"{runner_type}"%')
        failure_query = command_arg(args, "--failure-reason-query")
        if failure_query:
            _register_observe_text_predicates(conn)
            clauses.append("alab_record_json_field_casefold_contains(record_json, 'failure', ?) = 1")
            params.append(failure_query)
        order_sql, order_params = _sql_order_limit_clause(
            args,
            default="started:desc",
            subject="runs",
            allowed={
                "started": "started_at",
                "ended": "ended_at",
                "reward": "reward_value",
                "status": "LOWER(status)",
                "config-version": "config_version",
                "exit-code": "exit_code",
            },
            tie_breakers=("started_at DESC", "rowid ASC"),
        )
        rows = all_rows(conn, f"SELECT * FROM runs WHERE {' AND '.join(clauses)} {order_sql}", (*params, *order_params))
        return [_run_result_block(conn, row) for row in rows]
    finally:
        conn.close()

def _run_result_block(conn, row: Any) -> ResultBlock:
    logs = all_rows(conn, "SELECT * FROM log_streams WHERE run_id = ? AND archive_status = 'active'", (row["run_id"],))
    artifacts = all_rows(conn, "SELECT * FROM artifacts WHERE run_id = ? AND archive_status = 'active'", (row["run_id"],))
    stdout = next((log["preview_text"] for log in logs if log["stream"] == "stdout"), None)
    stderr = next((log["preview_text"] for log in logs if log["stream"] == "stderr"), None)
    record = execution_record_json_obj(row["record_json"])
    return ResultBlock(
        "run",
        [
            ("run id", row["run_id"]),
            ("exp id", row["exp_id"]),
            ("commit", row["commit_sha"]),
            ("run status", row["status"]),
            ("exit code", row["exit_code"]),
            ("reward", row["reward_value"]),
            ("reward parse status", row["reward_parse_status"]),
            ("config version", row["config_version"]),
            ("stdout preview", stdout),
            ("stderr preview", stderr),
            ("artifact count", len(artifacts)),
            ("log count", len(logs)),
            ("hidden log available", any(bool(log["hidden"]) for log in logs)),
            ("started at", row["started_at"]),
            ("ended at", row["ended_at"]),
            ("warning code", record.get("warnings", [])),
        ],
    )


def _run_row(conn, project_id: str, run_id: str | None, actor: Actor) -> Any:
    run_id = _complete_id_or_missing(run_id, prefix="run", code="RUN_NOT_FOUND", label="run id")
    row = one(conn, "SELECT * FROM runs WHERE project_id = ? AND run_id = ?", (project_id, run_id))
    if row is None:
        if actor.actor_type == "token":
            raise AlabError("SCOPE_VIOLATION", "run is not visible or not found")
        raise AlabError("RUN_NOT_FOUND", "run not found")
    if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, row["exp_id"]):
        raise AlabError("SCOPE_VIOLATION", "run is not visible or not found")
    return row


def cmd_observe_runs_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    run_id = optional_positional_selector(args, "runs show accepts exactly one run id")
    conn = require_home(req.globals.home)
    try:
        return [_run_result_block(conn, _run_row(conn, project_id, run_id, actor))]
    finally:
        conn.close()


def cmd_observe_runs_archive(args: list[str], req: Request) -> list[ResultBlock]:
    return _archive_observe_record(args, req, table="runs", id_column="run_id", object_type="run", not_found="RUN_NOT_FOUND")


def cmd_observe_runs_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    return _unarchive_observe_record(args, req, table="runs", id_column="run_id", object_type="run", not_found="RUN_NOT_FOUND")


def cmd_observe_runs_remove(args: list[str], req: Request) -> list[ResultBlock]:
    return _remove_observe_record(args, req, table="runs", id_column="run_id", object_type="run", not_found="RUN_NOT_FOUND")


def _artifact_block(row: Any, out: str | None = None) -> ResultBlock:
    return ResultBlock(
        "artifact",
        [
            ("artifact id", row["artifact_id"]),
            ("exp id", row["exp_id"]),
            ("run id", row["run_id"]),
            ("validation id", row["validation_id"]),
            ("root", row["root"]),
            ("path", row["relative_path"]),
            ("status", row["status"]),
            ("archive status", row["archive_status"]),
            ("size bytes", row["size_bytes"]),
            ("content hash", row["content_hash"]),
            ("created at", row["created_at"]),
            ("out", out),
        ],
    )


def _artifact_row(conn, project_id: str, artifact_id: str | None, actor: Actor) -> Any:
    artifact_id = _complete_id_or_missing(artifact_id, prefix="art", code="ARTIFACT_NOT_FOUND", label="artifact id")
    row = one(conn, "SELECT * FROM artifacts WHERE project_id = ? AND artifact_id = ?", (project_id, artifact_id))
    if row is None:
        if actor.actor_type == "token":
            raise AlabError("SCOPE_VIOLATION", "artifact is not visible or not found")
        raise AlabError("ARTIFACT_NOT_FOUND", "artifact not found")
    if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, row["exp_id"]):
        raise AlabError("SCOPE_VIOLATION", "artifact is not visible or not found")
    return row


def cmd_observe_artifacts_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--include-archived",
            "--exp",
            "--run",
            "--validation",
            "--root",
            "--status",
            "--path-query",
            "--content-hash",
            "--created-after",
            "--created-before",
            "--size-min",
            "--size-max",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    require_options_at_most_once(
        args,
        (
            "--project",
            "--include-archived",
            "--exp",
            "--run",
            "--validation",
            "--root",
            "--status",
            "--path-query",
            "--content-hash",
            "--created-after",
            "--created-before",
            "--size-min",
            "--size-max",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    require_positional_count(args, 0, "artifacts list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        clauses = ["project_id = ?"]
        params: list[Any] = [project_id]
        _append_visible_exp_clause(conn, project_id, actor, clauses, params)
        exp_filter = _complete_id_option(args, "--exp", "exp")
        if exp_filter:
            clauses.append("exp_id = ?")
            params.append(exp_filter)
        run_filter = _complete_id_option(args, "--run", "run")
        if run_filter:
            clauses.append("run_id = ?")
            params.append(run_filter)
        validation_filter = _complete_id_option(args, "--validation", "val")
        if validation_filter:
            clauses.append("validation_id = ?")
            params.append(validation_filter)
        root_filter = _require_option_choice(command_arg(args, "--root"), "--root", ARTIFACT_ROOTS)
        if root_filter:
            clauses.append("root = ?")
            params.append(root_filter)
        status = _require_option_choice(command_arg(args, "--status"), "--status", {"captured", "skipped", "error"})
        if status:
            clauses.append("status = ?")
            params.append(status)
        if command_arg(args, "--path-query"):
            clauses.append("relative_path LIKE ?")
            params.append(f"%{command_arg(args, '--path-query')}%")
        content_hash = _content_hash_filter(command_arg(args, "--content-hash"))
        if content_hash:
            clauses.append("content_hash = ?")
            params.append(content_hash)
        size_min = _parse_non_negative_int_option(args, "--size-min")
        size_max = _parse_non_negative_int_option(args, "--size-max")
        _require_ordered_range(size_min, size_max, "--size-min", "--size-max")
        if size_min is not None:
            clauses.append("size_bytes >= ?")
            params.append(size_min)
        if size_max is not None:
            clauses.append("size_bytes <= ?")
            params.append(size_max)
        _require_ordered_time_range(args, "--created-after", "--created-before")
        _append_time_filter(args, clauses, params, "--created-after", "created_at", ">=")
        _append_time_filter(args, clauses, params, "--created-before", "created_at", "<=")
        if not flag(args, "--include-archived"):
            clauses.append("archive_status = 'active'")
        order_sql, order_params = _sql_order_limit_clause(
            args,
            default="created:desc",
            subject="artifacts",
            allowed={
                "created": "created_at",
                "path": "LOWER(relative_path)",
                "size": "size_bytes",
                "status": "LOWER(status)",
                "content-hash": "content_hash",
            },
            tie_breakers=("created_at DESC", "rowid ASC"),
        )
        rows = all_rows(conn, f"SELECT * FROM artifacts WHERE {' AND '.join(clauses)} {order_sql}", (*params, *order_params))
        return [_artifact_block(row) for row in rows]
    finally:
        conn.close()


def cmd_observe_artifacts_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    artifact_id = optional_positional_selector(args, "artifacts show accepts exactly one artifact id")
    conn = require_home(req.globals.home)
    try:
        return [_artifact_block(_artifact_row(conn, project_id, artifact_id, actor))]
    finally:
        conn.close()


def cmd_observe_artifacts_export(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--out", "--overwrite", "--include-archived"))
    require_options_at_most_once(args, ("--out", "--overwrite", "--include-archived"))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    artifact_id = optional_positional_selector(args, "artifacts export accepts exactly one artifact id")
    out = Path(command_arg(args, "--out", required=True)).expanduser()
    _assert_export_output_path(out, overwrite=flag(args, "--overwrite"), require_existing_parent=True)
    conn = require_home(req.globals.home)
    try:
        row = _artifact_row(conn, project_id, artifact_id, actor)
        if row["archive_status"] == "archived" and not flag(args, "--include-archived"):
            raise AlabError("CONFIG_INVALID", "exporting archived artifacts requires --include-archived")
        if row["status"] != "captured" or not row["blob_path"]:
            raise AlabError("ARTIFACT_NOT_FOUND", "artifact bytes were not captured")
        _project_root, _repo_git, artifact_store = _project_paths(req.globals.home, project_id)
        data = (artifact_store / row["blob_path"]).read_bytes()
    finally:
        conn.close()
    out.write_bytes(data)
    return [_artifact_block(row, str(out))]


def cmd_observe_artifacts_archive(args: list[str], req: Request) -> list[ResultBlock]:
    return _archive_observe_record(args, req, table="artifacts", id_column="artifact_id", object_type="artifact", not_found="ARTIFACT_NOT_FOUND")


def cmd_observe_artifacts_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    return _unarchive_observe_record(args, req, table="artifacts", id_column="artifact_id", object_type="artifact", not_found="ARTIFACT_NOT_FOUND")


def cmd_observe_artifacts_remove(args: list[str], req: Request) -> list[ResultBlock]:
    return _remove_observe_record(args, req, table="artifacts", id_column="artifact_id", object_type="artifact", not_found="ARTIFACT_NOT_FOUND")


def _log_block(row: Any, out: str | None = None, audit_id: str | None = None) -> ResultBlock:
    return ResultBlock(
        "log",
        [
            ("log id", row["log_id"]),
            ("exp id", row["exp_id"]),
            ("run id", row["run_id"]),
            ("validation id", row["validation_id"]),
            ("stream", row["stream"]),
            ("size bytes", row["size_bytes"]),
            ("stored bytes", row["stored_bytes"]),
            ("truncated", bool(row["truncated"])),
            ("hidden", bool(row["hidden"])),
            ("archive status", row["archive_status"]),
            ("preview", row["preview_text"]),
            ("out", out),
            ("audit id", audit_id),
        ],
    )


def _log_show_block(row: Any, content: str) -> ResultBlock:
    return ResultBlock(
        "log",
        [
            ("log id", row["log_id"]),
            ("exp id", row["exp_id"]),
            ("run id", row["run_id"]),
            ("validation id", row["validation_id"]),
            ("stream", row["stream"]),
            ("size bytes", row["size_bytes"]),
            ("stored bytes", row["stored_bytes"]),
            ("truncated", bool(row["truncated"])),
            ("hidden", bool(row["hidden"])),
            ("archive status", row["archive_status"]),
            ("preview", row["preview_text"]),
            ("content", multiline_text(content)),
            ("out", None),
            ("audit id", None),
        ],
    )


def _read_log_text(home: Home, project_id: str, row: Any) -> str:
    _project_root, _repo_git, artifact_store = _project_paths(home, project_id)
    return (artifact_store / row["file_path"]).read_bytes().decode("utf-8", errors="replace")


def _log_row(conn, project_id: str, log_id: str | None, actor: Actor, *, include_hidden: bool = False) -> Any:
    log_id = _complete_id_or_missing(log_id, prefix="log", code="LOG_NOT_FOUND", label="log id")
    row = one(conn, "SELECT * FROM log_streams WHERE project_id = ? AND log_id = ?", (project_id, log_id))
    if row is None:
        if actor.actor_type == "token":
            raise AlabError("SCOPE_VIOLATION", "log is not visible or not found")
        raise AlabError("LOG_NOT_FOUND", "log not found")
    if actor.actor_type == "token":
        if not _exp_visible(conn, project_id, actor, row["exp_id"]):
            raise AlabError("SCOPE_VIOLATION", "log is not visible or not found")
        if row["hidden"]:
            raise AlabError("SCOPE_VIOLATION", "log is not visible or not found")
    if row["hidden"] and not include_hidden:
        raise AlabError("SCOPE_VIOLATION", "hidden log requires --include-hidden")
    return row


def cmd_observe_logs_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--include-hidden",
            "--include-archived",
            "--exp",
            "--run",
            "--validation",
            "--stream",
            "--truncated",
            "--created-after",
            "--created-before",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    require_options_at_most_once(
        args,
        (
            "--project",
            "--include-hidden",
            "--include-archived",
            "--exp",
            "--run",
            "--validation",
            "--stream",
            "--truncated",
            "--created-after",
            "--created-before",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    if actor.actor_type == "token" and flag(args, "--include-hidden"):
        raise AlabError("SCOPE_VIOLATION", "hidden logs require admin/root")
    require_positional_count(args, 0, "logs list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        clauses = ["project_id = ?"]
        params: list[Any] = [project_id]
        if actor.actor_type == "token":
            _append_visible_exp_clause(conn, project_id, actor, clauses, params)
            clauses.append("hidden = 0")
        elif not flag(args, "--include-hidden"):
            clauses.append("hidden = 0")
        exp_filter = _complete_id_option(args, "--exp", "exp")
        if exp_filter:
            clauses.append("exp_id = ?")
            params.append(exp_filter)
        run_filter = _complete_id_option(args, "--run", "run")
        if run_filter:
            clauses.append("run_id = ?")
            params.append(run_filter)
        validation_filter = _complete_id_option(args, "--validation", "val")
        if validation_filter:
            clauses.append("validation_id = ?")
            params.append(validation_filter)
        stream_filter = _require_option_choice(command_arg(args, "--stream"), "--stream", LOG_STREAMS)
        if stream_filter:
            clauses.append("stream = ?")
            params.append(stream_filter)
        truncated = _parse_bool_option(args, "--truncated")
        if truncated is not None:
            clauses.append("truncated = ?")
            params.append(1 if truncated else 0)
        _require_ordered_time_range(args, "--created-after", "--created-before")
        _append_time_filter(args, clauses, params, "--created-after", "created_at", ">=")
        _append_time_filter(args, clauses, params, "--created-before", "created_at", "<=")
        if not flag(args, "--include-archived"):
            clauses.append("archive_status = 'active'")
        order_sql, order_params = _sql_order_limit_clause(
            args,
            default="created:desc",
            subject="logs",
            allowed={
                "created": "created_at",
                "stream": "LOWER(stream)",
                "size": "size_bytes",
                "stored-bytes": "stored_bytes",
                "hidden": "hidden",
                "truncated": "truncated",
            },
            tie_breakers=("created_at DESC", "rowid ASC"),
        )
        rows = all_rows(conn, f"SELECT * FROM log_streams WHERE {' AND '.join(clauses)} {order_sql}", (*params, *order_params))
        return [_log_block(row) for row in rows]
    finally:
        conn.close()


def cmd_observe_logs_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--include-hidden"))
    require_options_at_most_once(args, ("--include-hidden",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    if actor.actor_type == "token" and flag(args, "--include-hidden"):
        raise AlabError("SCOPE_VIOLATION", "hidden logs require admin/root")
    log_id = optional_positional_selector(args, "logs show accepts exactly one log id")
    conn = require_home(req.globals.home)
    try:
        row = _log_row(conn, project_id, log_id, actor, include_hidden=flag(args, "--include-hidden"))
        return [_log_show_block(row, _read_log_text(req.globals.home, project_id, row))]
    finally:
        conn.close()


def cmd_observe_logs_export(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--out", "--overwrite", "--include-archived", "--include-hidden"))
    require_options_at_most_once(args, ("--out", "--overwrite", "--include-archived", "--include-hidden"))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    if actor.actor_type == "token" and flag(args, "--include-hidden"):
        raise AlabError("SCOPE_VIOLATION", "hidden logs require admin/root")
    log_id = optional_positional_selector(args, "logs export accepts exactly one log id")
    out = Path(command_arg(args, "--out", required=True)).expanduser()
    _assert_export_output_path(out, overwrite=flag(args, "--overwrite"), require_existing_parent=True)
    conn = require_home(req.globals.home)
    try:
        row = _log_row(conn, project_id, log_id, actor, include_hidden=flag(args, "--include-hidden"))
        if row["archive_status"] == "archived" and not flag(args, "--include-archived"):
            raise AlabError("CONFIG_INVALID", "exporting archived logs requires --include-archived")
        _project_root, _repo_git, artifact_store = _project_paths(req.globals.home, project_id)
        data = (artifact_store / row["file_path"]).read_bytes()
    finally:
        conn.close()
    out.write_bytes(data)
    return [_log_block(row, str(out))]


def cmd_observe_logs_archive(args: list[str], req: Request) -> list[ResultBlock]:
    return _archive_observe_record(args, req, table="log_streams", id_column="log_id", object_type="log", not_found="LOG_NOT_FOUND")


def cmd_observe_logs_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    return _unarchive_observe_record(args, req, table="log_streams", id_column="log_id", object_type="log", not_found="LOG_NOT_FOUND")


def cmd_observe_logs_remove(args: list[str], req: Request) -> list[ResultBlock]:
    return _remove_observe_record(args, req, table="log_streams", id_column="log_id", object_type="log", not_found="LOG_NOT_FOUND")

def _observe_record_row(conn, *, project_id: str, table: str, id_column: str, object_id: str | None, not_found: str, actor: Actor) -> Any:
    prefix = {"run_id": "run", "artifact_id": "art", "log_id": "log"}[id_column]
    object_id = _complete_id_or_missing(object_id, prefix=prefix, code=not_found, label="object id")
    row = one(conn, f"SELECT * FROM {table} WHERE project_id = ? AND {id_column} = ?", (project_id, object_id))
    if row is None:
        if actor.actor_type == "token":
            raise AlabError("SCOPE_VIOLATION", "object is not visible or not found")
        raise AlabError(not_found, "object not found")
    if actor.actor_type == "token" and "exp_id" in row.keys() and not _exp_visible(conn, project_id, actor, row["exp_id"]):
        raise AlabError("SCOPE_VIOLATION", "object is not visible or not found")
    if table == "log_streams" and actor.actor_type == "token" and row["hidden"]:
        raise AlabError("SCOPE_VIOLATION", "object is not visible or not found")
    return row


def _remaining_latest_run(conn, exp_id: str, removed_run_id: str) -> Any | None:
    return one(
        conn,
        """
        SELECT * FROM runs
        WHERE exp_id = ? AND run_id != ?
        ORDER BY COALESCE(ended_at, started_at) DESC, started_at DESC, run_id DESC
        LIMIT 1
        """,
        (exp_id, removed_run_id),
    )


def _archive_observe_record(args: list[str], req: Request, *, table: str, id_column: str, object_type: str, not_found: str) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    object_id = optional_positional_selector(args, f"{object_type} archive accepts exactly one object id")
    with Database(req.globals.home).tx() as conn:
        if object_type == "run":
            _interrupt_stale_running_records(conn, project_id=project_id)
        row = _observe_record_row(conn, project_id=project_id, table=table, id_column=id_column, object_id=object_id, not_found=not_found, actor=actor)
        if actor.actor_type == "token" and "exp_id" in row.keys() and row["exp_id"] != actor.exp_id:
            raise AlabError("SCOPE_VIOLATION", "object is not visible or not found")
        previous = row["archive_status"]
        archived_at = row["archived_at"] if previous == "archived" and row["archived_at"] else utc_now()
        audit_id = None
        if previous != "archived":
            conn.execute(f"UPDATE {table} SET archive_status = 'archived', archived_at = ? WHERE {id_column} = ?", (archived_at, row[id_column]))
            audit_id = audit(
                conn,
                action="archive",
                object_type=object_type,
                object_id=row[id_column],
                actor=actor,
                project_id=project_id,
                exp_id=row["exp_id"] if "exp_id" in row.keys() else None,
                metadata={
                    "schema_version": 1,
                    "previous_archive_status": previous,
                    "archive_status": "archived",
                    "archived_at": archived_at,
                },
            )
        return [
            ResultBlock(
                object_type,
                [
                    (f"{object_type} id", row[id_column]),
                    ("previous archive status", previous),
                    ("archive status", "archived"),
                    ("archived at", archived_at),
                    ("audit id", audit_id),
                ],
            )
        ]


def _unarchive_observe_record(args: list[str], req: Request, *, table: str, id_column: str, object_type: str, not_found: str) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    object_id = optional_positional_selector(args, f"{object_type} unarchive accepts exactly one object id")
    with Database(req.globals.home).tx() as conn:
        if object_type == "run":
            _interrupt_stale_running_records(conn, project_id=project_id)
        row = _observe_record_row(conn, project_id=project_id, table=table, id_column=id_column, object_id=object_id, not_found=not_found, actor=actor)
        if actor.actor_type == "token" and "exp_id" in row.keys() and row["exp_id"] != actor.exp_id:
            raise AlabError("SCOPE_VIOLATION", "object is not visible or not found")
        previous = row["archive_status"]
        unarchived_at = utc_now() if previous != "active" else row["unarchived_at"]
        audit_id = None
        if previous != "active":
            conn.execute(f"UPDATE {table} SET archive_status = 'active', archived_at = NULL, unarchived_at = ? WHERE {id_column} = ?", (unarchived_at, row[id_column]))
            audit_id = audit(
                conn,
                action="unarchive",
                object_type=object_type,
                object_id=row[id_column],
                actor=actor,
                project_id=project_id,
                exp_id=row["exp_id"] if "exp_id" in row.keys() else None,
                metadata={
                    "schema_version": 1,
                    "previous_archive_status": previous,
                    "archive_status": "active",
                    "unarchived_at": unarchived_at,
                },
            )
        return [
            ResultBlock(
                object_type,
                [
                    (f"{object_type} id", row[id_column]),
                    ("previous archive status", previous),
                    ("archive status", "active"),
                    ("unarchived at", unarchived_at),
                    ("audit id", audit_id),
                ],
            )
        ]


def _remove_observe_record(args: list[str], req: Request, *, table: str, id_column: str, object_type: str, not_found: str) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--cascade", "--force", "--confirm", "--reason"))
    require_options_at_most_once(args, ("--dry-run", "--cascade", "--reason"))
    require_dry_run_unforced(args)
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id, admin_required=True)
    object_id = optional_positional_selector(args, f"{object_type} remove accepts exactly one object id")
    dry_run = flag(args, "--dry-run")
    cascade = flag(args, "--cascade")
    conn = require_home(req.globals.home)
    try:
        if object_type == "run":
            _interrupt_stale_running_records(conn, project_id=project_id)
            conn.commit()
        row = dict(_observe_record_row(conn, project_id=project_id, table=table, id_column=id_column, object_id=object_id, not_found=not_found, actor=actor))
        blockers = [] if row["archive_status"] == "archived" else ["target_not_archived"]
        deleted_artifacts = 0
        deleted_logs = 0
        active_dependent_artifacts = 0
        active_dependent_logs = 0
        latest_run_id_before = None
        latest_run_id_after = None
        final_run_removed = False
        dependent_artifact_rows: list[Any] = []
        dependent_log_rows: list[Any] = []
        if object_type == "run":
            dependent_artifact_rows = all_rows(conn, "SELECT * FROM artifacts WHERE project_id = ? AND run_id = ? ORDER BY artifact_id", (project_id, row["run_id"]))
            dependent_log_rows = all_rows(conn, "SELECT * FROM log_streams WHERE project_id = ? AND run_id = ? ORDER BY log_id", (project_id, row["run_id"]))
            deleted_artifacts = len(dependent_artifact_rows)
            deleted_logs = len(dependent_log_rows)
            if (deleted_artifacts or deleted_logs) and not cascade:
                blockers.append("dependent_records_require_cascade")
            active_dependent_artifacts = sum(1 for artifact in dependent_artifact_rows if artifact["archive_status"] != "archived")
            active_dependent_logs = sum(1 for log in dependent_log_rows if log["archive_status"] != "archived")
            if cascade and (active_dependent_artifacts or active_dependent_logs):
                blockers.append("dependent_records_not_archived")
            exp_row = one(conn, "SELECT * FROM experiments WHERE project_id = ? AND exp_id = ?", (project_id, row["exp_id"]))
            latest_run_id_before = exp_row["latest_run_id"] if exp_row else None
            final_run_removed = bool(exp_row and exp_row["final_run_id"] == row["run_id"])
            if exp_row and exp_row["latest_run_id"] == row["run_id"]:
                remaining = _remaining_latest_run(conn, row["exp_id"], row["run_id"])
                latest_run_id_after = remaining["run_id"] if remaining else None
            else:
                latest_run_id_after = latest_run_id_before
        filesystem_targets = _artifact_log_filesystem_targets(
            conn,
            req.globals.home,
            project_id,
            artifact_rows=dependent_artifact_rows if object_type == "run" else [row] if object_type == "artifact" else [],
            log_rows=dependent_log_rows if object_type == "run" else [row] if object_type == "log" else [],
        )
    finally:
        conn.close()
    reason = _lifecycle_reason(args)
    if dry_run:
        fields = [
            (f"{object_type} id", row[id_column]),
            ("dry run", True),
            ("removed", False),
            ("cascade", cascade),
            ("audit id", None),
            ("blocker", blockers),
        ]
        if object_type == "run":
            fields.extend(
                [
                    ("deleted artifacts", deleted_artifacts),
                    ("deleted logs", deleted_logs),
                    ("active dependent artifacts", active_dependent_artifacts),
                    ("active dependent logs", active_dependent_logs),
                    ("latest run id before", latest_run_id_before),
                    ("latest run id after", latest_run_id_after),
                    ("final run removed", final_run_removed),
                ]
            )
        fields.extend(
            [
                ("deleted filesystem paths", len(filesystem_targets)),
                ("filesystem path", [str(target.path) for target in filesystem_targets]),
                ("planned trash move", [_trash_plan(req.globals.home, target.path) for target in filesystem_targets]),
            ]
        )
        return [
            ResultBlock(
                object_type,
                fields,
            )
        ]
    require_force_confirm(args, row[id_column], f"{object_type} remove requires --force and matching --confirm")
    if blockers:
        raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
    audit_id = new_id("aud", "remove")
    stages = _stage_targets_to_trash(req.globals.home, filesystem_targets, audit_id)
    try:
        with Database(req.globals.home).tx() as tx:
            exp_row = one(tx, "SELECT * FROM experiments WHERE project_id = ? AND exp_id = ?", (project_id, row["exp_id"])) if object_type == "run" else None
            latest_run_id_before = exp_row["latest_run_id"] if exp_row else latest_run_id_before
            latest_commit_after = exp_row["latest_commit"] if exp_row else None
            if object_type == "run" and exp_row and exp_row["latest_run_id"] == row["run_id"]:
                remaining = _remaining_latest_run(tx, row["exp_id"], row["run_id"])
                if remaining:
                    latest_run_id_after = remaining["run_id"]
                    latest_commit_after = remaining["commit_sha"]
                else:
                    _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project_id)
                    branch_head = _git_ref_commit(repo_git, _experiment_branch_ref(exp_row["branch_name"]))
                    latest_run_id_after = None
                    latest_commit_after = branch_head or exp_row["latest_commit"] or row["commit_sha"]
            final_run_removed = bool(object_type == "run" and exp_row and exp_row["final_run_id"] == row["run_id"])
            metadata = {
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
            }
            if object_type == "run":
                metadata.update(
                    {
                        "deleted_artifact_count": deleted_artifacts,
                        "deleted_log_count": deleted_logs,
                        "active_dependent_artifact_count": active_dependent_artifacts,
                        "active_dependent_log_count": active_dependent_logs,
                        "latest_run_id_before": latest_run_id_before,
                        "latest_run_id_after": latest_run_id_after,
                        "final_run_removed": final_run_removed,
                    }
                )
            audit(
                tx,
                action="remove",
                object_type=object_type,
                object_id=row[id_column],
                actor=actor,
                audit_id=audit_id,
                project_id=project_id,
                exp_id=row["exp_id"] if "exp_id" in row.keys() else None,
                cascade=cascade,
                reason=reason,
                metadata=metadata,
            )
            if object_type == "run":
                now = utc_now()
                if exp_row and exp_row["latest_run_id"] == row["run_id"]:
                    tx.execute(
                        "UPDATE experiments SET latest_run_id = ?, latest_commit = ?, updated_at = ? WHERE exp_id = ?",
                        (latest_run_id_after, latest_commit_after, now, row["exp_id"]),
                    )
                if final_run_removed:
                    tx.execute(
                        "UPDATE experiments SET final_run_removed_at = ?, final_run_removed_by = ?, final_run_removed_audit_id = ?, updated_at = ? WHERE exp_id = ?",
                        (now, actor.credential_id, audit_id, now, row["exp_id"]),
                    )
                tx.execute("DELETE FROM artifacts WHERE run_id = ?", (row["run_id"],))
                tx.execute("DELETE FROM log_streams WHERE run_id = ?", (row["run_id"],))
            tx.execute(f"DELETE FROM {table} WHERE {id_column} = ?", (row[id_column],))
    except Exception as exc:
        _raise_after_staged_trash_transaction_failure(exc, stages)
    trash_cleanup_pending = _finalize_staged_trashes(req.globals.home, stages, project_id)
    fields = [
        (f"{object_type} id", row[id_column]),
        ("dry run", False),
        ("removed", True),
        ("cascade", cascade),
        ("audit id", audit_id),
        ("blocker", []),
    ]
    if object_type == "run":
        fields.extend(
            [
                ("deleted artifacts", deleted_artifacts),
                ("deleted logs", deleted_logs),
                ("active dependent artifacts", active_dependent_artifacts),
                ("active dependent logs", active_dependent_logs),
                ("latest run id before", latest_run_id_before),
                ("latest run id after", latest_run_id_after),
                ("final run removed", final_run_removed),
            ]
        )
    fields.extend(
        [
            ("deleted filesystem paths", len(filesystem_targets)),
            ("trash cleanup pending", trash_cleanup_pending),
        ]
    )
    return [
        ResultBlock(
            object_type,
            fields,
        )
    ]
