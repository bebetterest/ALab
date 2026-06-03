from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .auth import Actor
from .db import all_rows, one
from .errors import AlabError
from .rendering import ResultBlock
from .service_args import (
    command_arg,
    flag,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_auth import require_home
from .service_models import Request
from .services import (
    _assert_export_output_path,
    _authorize_observe,
    _complete_id_option,
    _config_json_for_version,
    _exp_visible,
    _optional_best_context,
    _project_id_from_request,
    _project_row,
    _reward_identity_from_config_json,
    _tag_values,
)
from .timeutil import utc_now


def cmd_report(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--exp", "--out", "--overwrite"))
    require_options_at_most_once(args, ("--project", "--exp", "--out", "--overwrite"))
    require_positional_count(args, 0, "report accepts no positional arguments")
    exp_id = _complete_id_option(args, "--exp", "exp")
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id, admin_required=exp_id is None)
    out = Path(command_arg(args, "--out", required=True)).expanduser()
    _assert_export_output_path(out, overwrite=flag(args, "--overwrite"), require_existing_parent=True)
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        if exp_id:
            report_text = _experiment_report_markdown(conn, project=project, exp_id=exp_id, actor=actor)
            scope = "experiment"
        else:
            report_text = _project_report_markdown(conn, project=project)
            scope = "project"
    finally:
        conn.close()
    out.write_text(report_text, encoding="utf-8")
    byte_count = len(report_text.encode("utf-8"))
    return [
        ResultBlock(
            "report",
            [
                ("project id", project_id),
                ("exp id", exp_id),
                ("scope", scope),
                ("out", str(out)),
                ("wrote", True),
                ("bytes", byte_count),
            ],
        )
    ]


def _project_report_markdown(conn, *, project: Any) -> str:
    project_id = project["project_id"]
    config = _report_project_config(conn, project)
    project_cfg = config.get("project") if isinstance(config.get("project"), dict) else {}
    counts = {
        "sources": _report_count(conn, "sources", "project_id = ?", (project_id,)),
        "experiments": _report_count(conn, "experiments", "project_id = ?", (project_id,)),
        "runs": _report_count(conn, "runs", "project_id = ?", (project_id,)),
        "artifacts": _report_count(conn, "artifacts", "project_id = ?", (project_id,)),
        "logs": _report_count(conn, "log_streams", "project_id = ?", (project_id,)),
        "audit events": _report_count(conn, "audit_events", "project_id = ?", (project_id,)),
    }
    reward_identity, direction = _optional_best_context(conn, project)
    experiments = all_rows(conn, "SELECT * FROM experiments WHERE project_id = ? ORDER BY updated_at DESC LIMIT 25", (project_id,))
    runs = all_rows(conn, "SELECT * FROM runs WHERE project_id = ? ORDER BY started_at DESC LIMIT 25", (project_id,))
    artifacts = all_rows(conn, "SELECT * FROM artifacts WHERE project_id = ? ORDER BY created_at DESC LIMIT 25", (project_id,))
    logs = all_rows(conn, "SELECT * FROM log_streams WHERE project_id = ? ORDER BY created_at DESC LIMIT 25", (project_id,))
    best_project_run = _report_best_run(conn, project_id=project_id, exp_id=None, direction=direction, reward_identity=reward_identity)
    lines = [
        "# ALab Project Report",
        "",
        f"Generated: {_report_cell(utc_now())}",
        "",
        "## Project",
        "",
        _report_table(
            ["Field", "Value"],
            [
                ["project id", project_id],
                ["project name", project_cfg.get("name")],
                ["status", project["status"]],
                ["task", project_cfg.get("task")],
                ["goal", project_cfg.get("goal")],
                ["active config version", project["active_valid_config_version"]],
                ["latest attempted config version", project["latest_attempted_config_version"]],
                ["runner type", _report_nested(config, "runner", "type")],
                ["reward", f"{_report_nested(config, 'reward', 'type')} / {direction}"],
                ["best run", best_project_run["run_id"] if best_project_run else None],
                ["best reward", best_project_run["reward_value"] if best_project_run else None],
            ],
        ),
        "",
        "## Counts",
        "",
        _report_table(["Object", "Count"], counts.items()),
        "",
        "## Recent Experiments",
        "",
        _report_table(
            ["Experiment", "Name", "Status", "Tags", "Latest run", "Final run", "Best run", "Reward", "Updated"],
            [_report_experiment_table_row(conn, project_id=project_id, row=row, direction=direction, reward_identity=reward_identity) for row in experiments],
        ),
        "",
        "## Recent Runs",
        "",
        _report_table(
            ["Run", "Experiment", "Status", "Reward", "Parse", "Config", "Commit", "Started", "Ended"],
            [[row["run_id"], row["exp_id"], row["status"], row["reward_value"], row["reward_parse_status"], row["config_version"], row["commit_sha"], row["started_at"], row["ended_at"]] for row in runs],
        ),
        "",
        "## Recent Artifacts",
        "",
        _report_table(
            ["Artifact", "Experiment", "Run", "Validation", "Root", "Path", "Status", "Size", "Created"],
            [[row["artifact_id"], row["exp_id"], row["run_id"], row["validation_id"], row["root"], row["relative_path"], row["status"], row["size_bytes"], row["created_at"]] for row in artifacts],
        ),
        "",
        "## Recent Logs",
        "",
        _report_table(
            ["Log", "Experiment", "Run", "Validation", "Stream", "Hidden", "Stored bytes", "Created"],
            [[row["log_id"], row["exp_id"], row["run_id"], row["validation_id"], row["stream"], bool(row["hidden"]), row["stored_bytes"], row["created_at"]] for row in logs],
        ),
        "",
    ]
    return "\n".join(lines)


def _experiment_report_markdown(conn, *, project: Any, exp_id: str, actor: Actor) -> str:
    project_id = project["project_id"]
    exp = one(conn, "SELECT * FROM experiments WHERE project_id = ? AND exp_id = ?", (project_id, exp_id))
    if exp is None:
        if actor.actor_type == "token":
            raise AlabError("SCOPE_VIOLATION", "experiment is not visible or not found")
        raise AlabError("EXPERIMENT_NOT_FOUND", "experiment not found")
    if not _exp_visible(conn, project_id, actor, exp["exp_id"]):
        raise AlabError("SCOPE_VIOLATION", "experiment is not visible or not found")
    metadata = _report_json_obj(exp["metadata_json"])
    source = one(conn, "SELECT * FROM sources WHERE project_id = ? AND source_id = ?", (project_id, exp["source_id"]))
    submission = one(conn, "SELECT * FROM experiment_submissions WHERE project_id = ? AND exp_id = ?", (project_id, exp_id))
    reward_identity, direction = _optional_best_context(conn, project)
    best = _report_best_run(conn, project_id=project_id, exp_id=exp_id, direction=direction, reward_identity=reward_identity)
    runs = all_rows(conn, "SELECT * FROM runs WHERE project_id = ? AND exp_id = ? ORDER BY started_at DESC LIMIT 25", (project_id, exp_id))
    artifacts = all_rows(conn, "SELECT * FROM artifacts WHERE project_id = ? AND exp_id = ? ORDER BY created_at DESC LIMIT 25", (project_id, exp_id))
    log_clauses = ["project_id = ?", "exp_id = ?"]
    log_params: list[Any] = [project_id, exp_id]
    if actor.actor_type == "token":
        log_clauses.append("hidden = 0")
    logs = all_rows(conn, f"SELECT * FROM log_streams WHERE {' AND '.join(log_clauses)} ORDER BY created_at DESC LIMIT 25", tuple(log_params))
    lines = [
        "# ALab Experiment Report",
        "",
        f"Generated: {_report_cell(utc_now())}",
        "",
        "## Experiment",
        "",
        _report_table(
            ["Field", "Value"],
            [
                ["project id", project_id],
                ["exp id", exp_id],
                ["experiment name", metadata.get("name")],
                ["goal", metadata.get("goal")],
                ["status", exp["status"]],
                ["source id", exp["source_id"]],
                ["source ref", source["source_ref"] if source else None],
                ["bound config version", exp["bound_config_version"]],
                ["latest run", exp["latest_run_id"]],
                ["final run", exp["final_run_id"]],
                ["best run", best["run_id"] if best else None],
                ["best reward", best["reward_value"] if best else None],
                ["tags", _tag_values(conn, exp_id)],
                ["created", exp["created_at"]],
                ["updated", exp["updated_at"]],
                ["closed", exp["closed_at"]],
            ],
        ),
        "",
        "## Submission",
        "",
        _report_submission_markdown(submission),
        "",
        "## Runs",
        "",
        _report_table(
            ["Run", "Status", "Reward", "Parse", "Config", "Commit", "Started", "Ended"],
            [[row["run_id"], row["status"], row["reward_value"], row["reward_parse_status"], row["config_version"], row["commit_sha"], row["started_at"], row["ended_at"]] for row in runs],
        ),
        "",
        "## Artifacts",
        "",
        _report_table(
            ["Artifact", "Run", "Validation", "Root", "Path", "Status", "Size", "Created"],
            [[row["artifact_id"], row["run_id"], row["validation_id"], row["root"], row["relative_path"], row["status"], row["size_bytes"], row["created_at"]] for row in artifacts],
        ),
        "",
        "## Logs",
        "",
        _report_table(
            ["Log", "Run", "Validation", "Stream", "Hidden", "Stored bytes", "Created"],
            [[row["log_id"], row["run_id"], row["validation_id"], row["stream"], bool(row["hidden"]), row["stored_bytes"], row["created_at"]] for row in logs],
        ),
        "",
    ]
    return "\n".join(lines)


def _report_project_config(conn, project: Any) -> dict[str, Any]:
    version = project["active_valid_config_version"] or project["latest_attempted_config_version"]
    if not version:
        return {}
    row = one(
        conn,
        "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?",
        (project["project_id"], int(version)),
    )
    return _report_json_obj(row["canonical_config_json"] if row else None)


def _report_json_obj(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _report_nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _report_best_run(conn, *, project_id: str, exp_id: str | None, direction: str, reward_identity: str | None) -> Any | None:
    clauses = [
        "project_id = ?",
        "status = 'passed'",
        "reward_parse_status = 'parsed'",
        "reward_value IS NOT NULL",
        "archive_status = 'active'",
    ]
    params: list[Any] = [project_id]
    if exp_id:
        clauses.append("exp_id = ?")
        params.append(exp_id)
    rows = all_rows(conn, f"SELECT * FROM runs WHERE {' AND '.join(clauses)}", tuple(params))
    identity_cache: dict[int, str] = {}
    comparable: list[Any] = []
    for row in rows:
        if reward_identity is not None:
            version = int(row["config_version"])
            if version not in identity_cache:
                identity_cache[version] = _reward_identity_from_config_json(_config_json_for_version(conn, project_id, version))
            if identity_cache[version] != reward_identity:
                continue
        comparable.append(row)
    comparable.sort(key=lambda row: row["run_id"])
    comparable.sort(key=lambda row: row["ended_at"] or "", reverse=True)
    comparable.sort(key=lambda row: float(row["reward_value"]), reverse=direction == "maximize")
    return comparable[0] if comparable else None


def _report_experiment_table_row(conn, *, project_id: str, row: Any, direction: str, reward_identity: str | None) -> list[Any]:
    best = _report_best_run(conn, project_id=project_id, exp_id=row["exp_id"], direction=direction, reward_identity=reward_identity)
    return [
        row["exp_id"],
        _report_json_obj(row["metadata_json"]).get("name"),
        row["status"],
        _tag_values(conn, row["exp_id"]),
        row["latest_run_id"],
        row["final_run_id"],
        best["run_id"] if best else None,
        best["reward_value"] if best else None,
        row["updated_at"],
    ]


def _report_count(conn, table: str, where: str, params: tuple[Any, ...]) -> int:
    row = one(conn, f"SELECT COUNT(*) AS count FROM {table} WHERE {where}", params)
    return int(row["count"]) if row else 0


def _report_submission_markdown(row: Any | None) -> str:
    if row is None:
        return "_No submission recorded._"
    refs = _report_json_obj(row["refs_json"]).get("refs") or []
    return "\n".join(
        [
            _report_table(
                ["Field", "Value"],
                [
                    ["submission id", row["submission_id"]],
                    ["final run", row["final_run_id"]],
                    ["final commit", row["final_commit"]],
                    ["message", row["message"]],
                    ["refs", refs],
                    ["created", row["created_at"]],
                ],
            ),
            "",
            "### Summary",
            "",
            _report_block_text(row["summary"]),
            "",
            "### Feedback",
            "",
            _report_block_text(row["feedback"]),
        ]
    )


def _report_table(headers: list[str], rows: Any) -> str:
    materialized = [list(row) for row in rows]
    if not materialized:
        return "_No rows._"
    header = "| " + " | ".join(_report_cell(item) for item in headers) + " |"
    divider = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_report_cell(item) for item in row) + " |" for row in materialized]
    return "\n".join([header, divider, *body])


def _report_cell(value: Any) -> str:
    if value is None or value == "":
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_report_cell(item) for item in value) or "none"
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    text = str(value).replace("\r", " ").replace("\n", "<br>").replace("|", "\\|")
    return text or "none"


def _report_block_text(value: Any) -> str:
    text = "" if value is None else str(value)
    if not text:
        return "_Empty._"
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())
