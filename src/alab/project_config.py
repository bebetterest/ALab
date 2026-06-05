from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import services as _core
from .auth import Actor
from .configs import (
    ENV_NAME_RE,
    ProjectConfig,
    config_hash,
    dumps_toml,
    is_free_evaluation_config,
    load_project_config,
    project_config_json_obj,
    set_nested_toml_value,
)
from .db import Database, all_rows, canonical_json, one
from .errors import AlabError
from .rendering import ResultBlock, multiline_text
from .service_args import (
    command_arg,
    flag,
    require_dry_run_skip_baseline_compatible,
    require_exactly_one_option_pair,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_auth import require_actor, require_home
from .service_models import Request
from .service_text import _read_text_input_file
from .timeutil import utc_now

_project_id_from_request = _core._project_id_from_request
_project_row = _core._project_row
_selected_config_row = _core._selected_config_row
_assert_export_output_path = _core._assert_export_output_path
_require_project_admin = _core._require_project_admin
_validate_project_config_text_fields = _core._validate_project_config_text_fields
_validate_docker_config_capabilities = _core._validate_docker_config_capabilities
_validate_adapter_config_refs = _core._validate_adapter_config_refs
_secret_fingerprint = _core._secret_fingerprint
_store_secret_values = _core._store_secret_values
_source_for_ref = _core._source_for_ref
_execution_record_object_json = _core._execution_record_object_json
_run_validation = _core._run_validation
_baseline_failure_fields = _core._baseline_failure_fields
_result_failure_tail = _core._result_failure_tail

RUNTIME_CONFIG_KEYS = {"source", "runner", "reward", "artifacts", "logs", "env", "secret_env"}


def audit(*args: Any, **kwargs: Any) -> str:
    return _core.audit(*args, **kwargs)


def new_id(*args: Any, **kwargs: Any) -> str:
    return _core.new_id(*args, **kwargs)


def _runner_sandbox_summary(config: ProjectConfig) -> str:
    if config.runner.type == "skydiscover_python":
        return "not-os-sandbox"
    return "not-declared"


def _exportable_config_json(config_json: dict[str, Any]) -> dict[str, Any]:
    exported = json.loads(canonical_json(config_json))
    secret_env = exported.get("secret_env", {})
    exported["secret_env"] = {
        name: {"retain": True, "fingerprint": marker.get("fingerprint")}
        for name, marker in sorted(secret_env.items())
        if isinstance(marker, dict)
    }
    return exported


def _runtime_signature(config_json: dict[str, Any]) -> str:
    return canonical_json({key: config_json.get(key) for key in sorted(RUNTIME_CONFIG_KEYS)})


def _secret_marker_summary(config_json: dict[str, Any]) -> tuple[list[str], list[str]]:
    secret_env = config_json.get("secret_env", {})
    names: list[str] = []
    fingerprints: list[str] = []
    for name in sorted(secret_env):
        marker = secret_env[name]
        names.append(name)
        fingerprints.append(marker.get("fingerprint") if isinstance(marker, dict) else "none")
    return names, fingerprints


def _validate_env_name(name: str) -> None:
    if not ENV_NAME_RE.match(name):
        raise AlabError("CONFIG_INVALID", f"invalid environment variable name: {name}")


def _apply_project_config(
    args: list[str],
    req: Request,
    *,
    project: Any,
    actor: Actor,
    next_config: ProjectConfig,
    dry_run: bool = False,
    skip_baseline: bool = False,
) -> list[ResultBlock]:
    _validate_project_config_text_fields(next_config)
    if dry_run and skip_baseline:
        raise AlabError("CONFIG_INVALID", "--dry-run conflicts with --skip-baseline-test")
    warning_codes: list[str] = []
    db = Database(req.globals.home)
    conn = require_home(req.globals.home)
    try:
        current_version = project["latest_attempted_config_version"]
        current_row = one(
            conn,
            "SELECT * FROM project_config_versions WHERE project_id = ? AND version = ?",
            (project["project_id"], current_version),
        )
        if current_row is None:
            raise AlabError("PROJECT_INVALID", "project has no config version")
        current_json = project_config_json_obj(current_row["canonical_config_json"])
        base_secret_markers = current_json.get("secret_env", {})
        fingerprint_key = bytes(project["secret_fingerprint_key"])
        if dry_run:
            # Validate secret retain markers and raw secret shape without writing new rows.
            for name, value in next_config.secret_env.items():
                if isinstance(value, dict) and value.get("retain"):
                    marker = base_secret_markers.get(name)
                    if marker is None:
                        raise AlabError(
                            "CONFIG_INVALID",
                            f"secret_env.{name} retain marker has no previous secret value",
                        )
                    if (
                        value.get("fingerprint")
                        and marker.get("fingerprint")
                        and value["fingerprint"] != marker["fingerprint"]
                    ):
                        raise AlabError(
                            "CONFIG_INVALID",
                            f"secret_env.{name} retain marker fingerprint does not match",
                        )
                if isinstance(value, str) and (
                    "\n" in value or "\0" in value or len(value.encode("utf-8")) < 4
                ):
                    raise AlabError(
                        "CONFIG_INVALID",
                        "secret_env values must be single-line UTF-8 strings at least 4 bytes",
                    )
            _validate_docker_config_capabilities(conn, next_config, allow_probe=False)
            _validate_adapter_config_refs(conn, next_config, allow_probe=False)
            next_json = next_config.canonical_dict()
            for name, marker in list(next_json.get("secret_env", {}).items()):
                if isinstance(marker, dict) and marker.get("retain"):
                    next_json["secret_env"][name] = base_secret_markers[name]
                elif isinstance(marker, str):
                    next_json["secret_env"][name] = {
                        "fingerprint": _secret_fingerprint(fingerprint_key, name, marker)
                    }
            new_hash = config_hash(next_json)
            runtime_affecting = _runtime_signature(current_json) != _runtime_signature(next_json)
            return [
                ResultBlock(
                    "project_config",
                    [
                        ("project id", project["project_id"]),
                        ("previous active config version", project["active_valid_config_version"]),
                        ("latest attempted config version", current_version),
                        ("runtime affecting", runtime_affecting),
                        ("validation status", "dry-run"),
                        ("project status", project["status"]),
                        ("next", "rerun without --dry-run"),
                    ],
                )
            ]
    finally:
        conn.close()

    with db.tx() as tx:
        project = dict(_project_row(tx, project["project_id"]))
        current_version = project["latest_attempted_config_version"]
        current_row = one(
            tx,
            "SELECT * FROM project_config_versions WHERE project_id = ? AND version = ?",
            (project["project_id"], current_version),
        )
        if current_row is None:
            raise AlabError("PROJECT_INVALID", "project has no config version")
        current_json = project_config_json_obj(current_row["canonical_config_json"])
        _validate_docker_config_capabilities(tx, next_config)
        _validate_adapter_config_refs(tx, next_config)
        config_json, raw_secrets = _store_secret_values(
            tx,
            project["project_id"],
            bytes(project["secret_fingerprint_key"]),
            next_config,
            actor,
            current_json.get("secret_env", {}),
        )
        new_hash = config_hash(config_json)
        runtime_affecting = _runtime_signature(current_json) != _runtime_signature(config_json)
        free_evaluation = is_free_evaluation_config(next_config)
        if new_hash == current_row["config_hash"]:
            return [
                ResultBlock(
                    "project_config",
                    [
                        ("project id", project["project_id"]),
                        ("previous active config version", project["active_valid_config_version"]),
                        ("latest attempted config version", current_version),
                        ("runtime affecting", False),
                        ("validation status", current_row["validation_status"]),
                        ("project status", project["status"]),
                        ("next", "none"),
                    ],
                )
            ]
        new_version = int(current_version) + 1
        now = utc_now()
        validation_id = new_id("val", "config")
        inherited_validation_id = project["active_validation_id"] if not runtime_affecting else None
        validation_status = (
            "not_required"
            if runtime_affecting and free_evaluation
            else "running"
            if runtime_affecting and not skip_baseline
            else "skipped"
            if runtime_affecting
            else "inherited"
        )
        tx.execute(
            """
            INSERT INTO project_config_versions(project_id, version, canonical_config_json, config_hash,
              baseline_required, validation_status, inherited_from_validation_id, created_at, created_by_credential_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project["project_id"],
                new_version,
                canonical_json(project_config_json_obj(canonical_json(config_json))),
                new_hash,
                1 if runtime_affecting and not free_evaluation else 0,
                validation_status,
                inherited_validation_id,
                now,
                actor.credential_id,
            ),
        )
        source = _source_for_ref(
            tx, project["project_id"], config_json.get("source", {}).get("default_source_ref")
        )
        if runtime_affecting:
            tx.execute(
                """
                INSERT INTO project_validations(validation_id, project_id, config_version, source_ref, source_commit,
                  status, exit_code, reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
                VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, 'not_attempted', 'active', ?, ?, ?)
                """,
                (
                    validation_id,
                    project["project_id"],
                    new_version,
                    source["source_ref"],
                    source["source_commit"],
                    "not_required" if free_evaluation else "skipped" if skip_baseline else "running",
                    now,
                    now if free_evaluation or skip_baseline else None,
                    _execution_record_object_json(
                        config_hash_value=new_hash,
                        runner_type=next_config.runner.type,
                        reward_type=next_config.reward.type,
                    ),
                ),
            )
        next_status = project["status"]
        if runtime_affecting and free_evaluation:
            next_active = new_version
            next_active_validation = validation_id
            next_status = "valid"
        elif not runtime_affecting and project["active_valid_config_version"]:
            next_active = new_version
            next_active_validation = project["active_validation_id"]
        else:
            next_active = project["active_valid_config_version"]
            next_active_validation = project["active_validation_id"]
        if runtime_affecting and skip_baseline and not free_evaluation:
            next_status = "invalid"
        tx.execute(
            """
            UPDATE projects
            SET latest_attempted_config_version = ?, active_valid_config_version = ?, active_validation_id = ?, updated_at = ?, status = ?
            WHERE project_id = ?
            """,
            (
                new_version,
                next_active,
                next_active_validation,
                now,
                next_status,
                project["project_id"],
            ),
        )
    if runtime_affecting and not skip_baseline and not free_evaluation:
        with db.tx() as tx:
            validation_status, exit_code, reward, reward_parse_status, warning_codes = (
                _run_validation(
                    tx,
                    req.globals.home,
                    project["project_id"],
                    validation_id,
                    source["source_ref"],
                    source["source_commit"],
                    new_version,
                    next_config,
                    raw_secrets,
                )
            )
            project_status = "valid" if validation_status == "passed" else "invalid"
            active_version = (
                new_version
                if validation_status == "passed"
                else project["active_valid_config_version"]
            )
            active_validation = (
                validation_id if validation_status == "passed" else project["active_validation_id"]
            )
            tx.execute(
                "UPDATE projects SET status = ?, active_valid_config_version = ?, active_validation_id = ?, updated_at = ? WHERE project_id = ?",
                (
                    project_status,
                    active_version,
                    active_validation,
                    utc_now(),
                    project["project_id"],
                ),
            )
            tx.execute(
                "UPDATE project_config_versions SET validation_status = ? WHERE project_id = ? AND version = ?",
                (validation_status, project["project_id"], new_version),
            )
    else:
        project_status = (
            "valid"
            if runtime_affecting and free_evaluation
            else "invalid"
            if runtime_affecting and skip_baseline
            else project["status"]
        )
    next_action = (
        "alab exp create --name <name>" if project_status == "valid" else "alab project validate"
    )
    fields: list[tuple[str, Any]] = [
        ("project id", project["project_id"]),
        ("previous active config version", project["active_valid_config_version"]),
        ("latest attempted config version", new_version),
        ("runtime affecting", runtime_affecting),
        ("validation status", validation_status),
        ("project status", project_status),
        ("warning code", warning_codes),
    ]
    failure_fields = _baseline_failure_fields(validation_status, next_action)
    if failure_fields:
        fields.extend(failure_fields)
    else:
        fields.append(("next", next_action))
    return [ResultBlock("project_config", fields)]


def cmd_project_config_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--version"))
    require_options_at_most_once(args, ("--version",))
    project_id = _project_id_from_request(args, req)
    require_actor(req, ("root", "admin"), project_id=project_id)
    require_positional_count(args, 0, "project config show accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        version, selector, cfg_row = _selected_config_row(
            conn, project, command_arg(args, "--version", default="latest-attempted")
        )
        config_json = project_config_json_obj(cfg_row["canonical_config_json"])
        cfg = ProjectConfig.model_validate(config_json)
        secret_names, secret_fingerprints = _secret_marker_summary(config_json)
        return [
            ResultBlock(
                "project_config",
                [
                    ("project id", project["project_id"]),
                    ("config version", version),
                    ("version selector", selector),
                    ("config hash", cfg_row["config_hash"]),
                    ("project name", cfg.project.name),
                    ("task", multiline_text(cfg.project.task)),
                    ("goal", multiline_text(cfg.project.goal)),
                    ("default source", cfg.source.default_source_ref),
                    ("runner type", cfg.runner.type),
                    ("sandbox", _runner_sandbox_summary(cfg)),
                    ("runner working directory", cfg.runner.working_directory),
                    ("timeout seconds", cfg.runner.timeout_seconds),
                    ("env mode", cfg.runner.env_mode),
                    ("reward type", cfg.reward.type),
                    ("reward direction", cfg.reward.direction),
                    ("primary metric", cfg.reward.primary_metric),
                    ("artifact glob count", len(cfg.artifacts.globs)),
                    ("stdout limit bytes", cfg.logs.stdout_limit_bytes),
                    ("stderr limit bytes", cfg.logs.stderr_limit_bytes),
                    (
                        "mutable summary",
                        f"include={len(cfg.mutable.include)} exclude={len(cfg.mutable.exclude)}",
                    ),
                    ("visibility scope", cfg.visibility.scope),
                    ("public exp create", cfg.project.allow_public_exp_create),
                    ("env name", sorted(config_json.get("env", {}).keys())),
                    ("secret name", secret_names),
                    ("secret fingerprint", secret_fingerprints),
                ],
            )
        ]
    finally:
        conn.close()


def cmd_project_config_export(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--out", "--version", "--overwrite"))
    require_options_at_most_once(args, ("--out", "--version", "--overwrite"))
    project_id = _project_id_from_request(args, req)
    require_actor(req, ("root", "admin"), project_id=project_id)
    out = command_arg(args, "--out", required=True)
    require_positional_count(args, 0, "project config export accepts no positional arguments")
    out_path = Path(out).expanduser()
    _assert_export_output_path(
        out_path, overwrite=flag(args, "--overwrite"), require_existing_parent=False
    )
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        version, _selector, cfg_row = _selected_config_row(
            conn, project, command_arg(args, "--version", default="latest-attempted")
        )
        export_json = _exportable_config_json(
            project_config_json_obj(cfg_row["canonical_config_json"])
        )
    finally:
        conn.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dumps_toml(export_json), encoding="utf-8")
    return [
        ResultBlock(
            "project_config",
            [
                ("project id", project["project_id"]),
                ("config version", version),
                ("out", str(out_path)),
                ("wrote", True),
                ("secret mode", "retain"),
            ],
        )
    ]


def cmd_project_config_import(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--config", "--dry-run", "--skip-baseline-test"))
    require_options_at_most_once(args, ("--config", "--dry-run", "--skip-baseline-test"))
    require_dry_run_skip_baseline_compatible(args)
    project, actor = _require_project_admin(args, req)
    config_path = Path(command_arg(args, "--config", required=True))
    require_positional_count(args, 0, "project config import accepts no positional arguments")
    next_config = load_project_config(config_path)
    return _apply_project_config(
        args,
        req,
        project=project,
        actor=actor,
        next_config=next_config,
        dry_run=flag(args, "--dry-run"),
        skip_baseline=flag(args, "--skip-baseline-test"),
    )


def cmd_project_config_set(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--skip-baseline-test"))
    require_options_at_most_once(args, ("--dry-run", "--skip-baseline-test"))
    require_dry_run_skip_baseline_compatible(args)
    project, actor = _require_project_admin(args, req)
    pos = require_positional_count(args, 2, "project config set requires field and TOML literal")
    field, value = pos[0], pos[1]
    if field == "secret_env" or field.startswith("secret_env."):
        raise AlabError(
            "CONFIG_INVALID",
            "secret_env changes must use project secret or config import retain markers",
        )
    conn = require_home(req.globals.home)
    try:
        _version, _selector, cfg_row = _selected_config_row(conn, project, "latest-attempted")
        data = project_config_json_obj(cfg_row["canonical_config_json"])
    finally:
        conn.close()
    data = set_nested_toml_value(data, field, value)
    try:
        next_config = ProjectConfig.model_validate(data)
    except Exception as exc:
        raise AlabError("CONFIG_INVALID", str(exc)) from exc
    return _apply_project_config(
        args,
        req,
        project=project,
        actor=actor,
        next_config=next_config,
        dry_run=flag(args, "--dry-run"),
        skip_baseline=flag(args, "--skip-baseline-test"),
    )


def cmd_project_env_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project_id = _project_id_from_request(args, req)
    require_actor(req, ("root", "admin"), project_id=project_id)
    require_positional_count(args, 0, "project env list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        version, _selector, cfg_row = _selected_config_row(conn, project, "latest-attempted")
        env = project_config_json_obj(cfg_row["canonical_config_json"]).get("env", {})
        return [
            ResultBlock(
                "project_env",
                [
                    ("project id", project_id),
                    ("config version", version),
                    ("env name", name),
                    ("value", value),
                ],
            )
            for name, value in sorted(env.items())
        ]
    finally:
        conn.close()


def cmd_project_env_set(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--skip-baseline-test"))
    require_options_at_most_once(args, ("--dry-run", "--skip-baseline-test"))
    require_dry_run_skip_baseline_compatible(args)
    project, actor = _require_project_admin(args, req)
    pos = require_positional_count(args, 2, "project env set requires name and value")
    name, value = pos[0], pos[1]
    _validate_env_name(name)
    conn = require_home(req.globals.home)
    try:
        _version, _selector, cfg_row = _selected_config_row(conn, project, "latest-attempted")
        data = project_config_json_obj(cfg_row["canonical_config_json"])
    finally:
        conn.close()
    data.setdefault("env", {})[name] = value
    next_config = ProjectConfig.model_validate(data)
    blocks = _apply_project_config(
        args,
        req,
        project=project,
        actor=actor,
        next_config=next_config,
        dry_run=flag(args, "--dry-run"),
        skip_baseline=flag(args, "--skip-baseline-test"),
    )
    fields = dict(blocks[0].fields)
    result_fields: list[tuple[str, Any]] = [
        ("project id", project["project_id"]),
        ("config version", fields.get("latest attempted config version")),
        ("env name", name),
        ("action", "set"),
        ("runtime affecting", fields.get("runtime affecting")),
        ("validation status", fields.get("validation status")),
    ]
    result_fields.extend(_result_failure_tail(blocks[0].fields))
    return [
        ResultBlock(
            "project_env",
            result_fields,
        )
    ]


def cmd_project_env_unset(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--skip-baseline-test"))
    require_options_at_most_once(args, ("--dry-run", "--skip-baseline-test"))
    require_dry_run_skip_baseline_compatible(args)
    project, actor = _require_project_admin(args, req)
    pos = require_positional_count(args, 1, "project env unset requires name")
    name = pos[0]
    _validate_env_name(name)
    conn = require_home(req.globals.home)
    try:
        _version, _selector, cfg_row = _selected_config_row(conn, project, "latest-attempted")
        data = project_config_json_obj(cfg_row["canonical_config_json"])
    finally:
        conn.close()
    data.setdefault("env", {}).pop(name, None)
    next_config = ProjectConfig.model_validate(data)
    blocks = _apply_project_config(
        args,
        req,
        project=project,
        actor=actor,
        next_config=next_config,
        dry_run=flag(args, "--dry-run"),
        skip_baseline=flag(args, "--skip-baseline-test"),
    )
    fields = dict(blocks[0].fields)
    result_fields: list[tuple[str, Any]] = [
        ("project id", project["project_id"]),
        ("config version", fields.get("latest attempted config version")),
        ("env name", name),
        ("action", "unset"),
        ("runtime affecting", fields.get("runtime affecting")),
        ("validation status", fields.get("validation status")),
    ]
    result_fields.extend(_result_failure_tail(blocks[0].fields))
    return [
        ResultBlock(
            "project_env",
            result_fields,
        )
    ]


def _read_secret_input(args: list[str]) -> str:
    require_exactly_one_option_pair(
        args,
        "--value-stdin",
        "--value-file",
        "project secret set requires exactly one of --value-stdin or --value-file",
    )
    value_file = command_arg(args, "--value-file")
    value = _read_text_input_file(value_file, "secret value") if value_file else sys.stdin.read()
    if value.endswith("\n"):
        value = value[:-1]
    if not value or "\n" in value or "\0" in value or len(value.encode("utf-8")) < 4:
        raise AlabError(
            "CONFIG_INVALID", "secret value must be a single-line UTF-8 string at least 4 bytes"
        )
    return value


def cmd_project_secret_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project_id = _project_id_from_request(args, req)
    require_actor(req, ("root", "admin"), project_id=project_id)
    require_positional_count(args, 0, "project secret list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        _project_row(conn, project_id)
        rows = all_rows(
            conn,
            "SELECT * FROM secret_values WHERE project_id = ? ORDER BY name, created_at",
            (project_id,),
        )
        referenced_ids: set[str] = set()
        for cfg in all_rows(
            conn,
            "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ?",
            (project_id,),
        ):
            for marker in (
                project_config_json_obj(cfg["canonical_config_json"]).get("secret_env", {}).values()
            ):
                if isinstance(marker, dict) and marker.get("secret_value_id"):
                    referenced_ids.add(marker["secret_value_id"])
        return [
            ResultBlock(
                "project_secret",
                [
                    ("project id", project_id),
                    ("secret name", row["name"]),
                    ("secret fingerprint", row["fingerprint"]),
                    ("referenced", row["secret_value_id"] in referenced_ids),
                    ("created at", row["created_at"]),
                    ("replaced at", row["replaced_at"]),
                ],
            )
            for row in rows
        ]
    finally:
        conn.close()


def cmd_project_secret_set(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args, ("--project", "--value-stdin", "--value-file", "--dry-run", "--skip-baseline-test")
    )
    require_options_at_most_once(
        args, ("--value-stdin", "--value-file", "--dry-run", "--skip-baseline-test")
    )
    require_dry_run_skip_baseline_compatible(args)
    project, actor = _require_project_admin(args, req)
    pos = require_positional_count(args, 1, "project secret set requires name")
    name = pos[0]
    _validate_env_name(name)
    value = _read_secret_input(args)
    conn = require_home(req.globals.home)
    try:
        _version, _selector, cfg_row = _selected_config_row(conn, project, "latest-attempted")
        data = project_config_json_obj(cfg_row["canonical_config_json"])
    finally:
        conn.close()
    data.setdefault("secret_env", {})[name] = value
    next_config = ProjectConfig.model_validate(data)
    blocks = _apply_project_config(
        args,
        req,
        project=project,
        actor=actor,
        next_config=next_config,
        dry_run=flag(args, "--dry-run"),
        skip_baseline=flag(args, "--skip-baseline-test"),
    )
    fields = dict(blocks[0].fields)
    conn = require_home(req.globals.home)
    try:
        _version, _selector, cfg_row = _selected_config_row(
            conn, _project_row(conn, project["project_id"]), "latest-attempted"
        )
        marker = (
            project_config_json_obj(cfg_row["canonical_config_json"])
            .get("secret_env", {})
            .get(name, {})
        )
    finally:
        conn.close()
    result_fields: list[tuple[str, Any]] = [
        ("project id", project["project_id"]),
        ("config version", fields.get("latest attempted config version")),
        ("secret name", name),
        ("action", "set"),
        ("secret fingerprint", marker.get("fingerprint") if isinstance(marker, dict) else None),
        ("runtime affecting", fields.get("runtime affecting")),
        ("validation status", fields.get("validation status")),
    ]
    result_fields.extend(_result_failure_tail(blocks[0].fields))
    return [
        ResultBlock(
            "project_secret",
            result_fields,
        )
    ]


def cmd_project_secret_unset(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--skip-baseline-test"))
    require_options_at_most_once(args, ("--dry-run", "--skip-baseline-test"))
    require_dry_run_skip_baseline_compatible(args)
    project, actor = _require_project_admin(args, req)
    pos = require_positional_count(args, 1, "project secret unset requires name")
    name = pos[0]
    _validate_env_name(name)
    conn = require_home(req.globals.home)
    try:
        _version, _selector, cfg_row = _selected_config_row(conn, project, "latest-attempted")
        data = project_config_json_obj(cfg_row["canonical_config_json"])
        marker = data.setdefault("secret_env", {}).pop(name, None)
    finally:
        conn.close()
    next_config = ProjectConfig.model_validate(data)
    blocks = _apply_project_config(
        args,
        req,
        project=project,
        actor=actor,
        next_config=next_config,
        dry_run=flag(args, "--dry-run"),
        skip_baseline=flag(args, "--skip-baseline-test"),
    )
    fields = dict(blocks[0].fields)
    result_fields: list[tuple[str, Any]] = [
        ("project id", project["project_id"]),
        ("config version", fields.get("latest attempted config version")),
        ("secret name", name),
        ("action", "unset"),
        ("secret fingerprint", marker.get("fingerprint") if isinstance(marker, dict) else None),
        ("runtime affecting", fields.get("runtime affecting")),
        ("validation status", fields.get("validation status")),
    ]
    result_fields.extend(_result_failure_tail(blocks[0].fields))
    return [
        ResultBlock(
            "project_secret",
            result_fields,
        )
    ]


def _referenced_secret_ids(conn, project_id: str) -> set[str]:
    referenced_ids: set[str] = set()
    for cfg in all_rows(
        conn,
        "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ?",
        (project_id,),
    ):
        for marker in (
            project_config_json_obj(cfg["canonical_config_json"]).get("secret_env", {}).values()
        ):
            if isinstance(marker, dict) and marker.get("secret_value_id"):
                referenced_ids.add(marker["secret_value_id"])
    return referenced_ids


def cmd_project_secret_gc(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--apply"))
    require_options_at_most_once(args, ("--dry-run", "--apply"))
    project, actor = _require_project_admin(args, req)
    require_positional_count(args, 0, "project secret gc accepts no positional arguments")
    require_exactly_one_option_pair(
        args,
        "--dry-run",
        "--apply",
        "project secret gc requires exactly one of --dry-run or --apply",
    )
    apply = flag(args, "--apply")
    with Database(req.globals.home).tx() as conn:
        referenced_ids = _referenced_secret_ids(conn, project["project_id"])
        rows = all_rows(
            conn,
            "SELECT * FROM secret_values WHERE project_id = ? ORDER BY created_at",
            (project["project_id"],),
        )
        unreferenced = [row for row in rows if row["secret_value_id"] not in referenced_ids]
        audit_id = None
        if apply and unreferenced:
            conn.executemany(
                "DELETE FROM secret_values WHERE secret_value_id = ?",
                [(row["secret_value_id"],) for row in unreferenced],
            )
            audit_id = audit(
                conn,
                action="gc",
                object_type="secret_value",
                object_id=project["project_id"],
                actor=actor,
                project_id=project["project_id"],
                metadata={"schema_version": 1, "deleted_count": len(unreferenced)},
            )
    return [
        ResultBlock(
            "project_secret",
            [
                ("project id", project["project_id"]),
                ("dry run", not apply),
                ("deleted count", len(unreferenced)),
                ("secret value id", [row["secret_value_id"] for row in unreferenced]),
                ("audit id", audit_id),
            ],
        )
    ]
