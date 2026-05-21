from __future__ import annotations

import errno
import fnmatch
import hashlib
import hmac
import json
import math
import os
import secrets
import shutil
import socket
import sqlite3
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from .auth import (
    Actor,
    create_credential,
    credential_metadata_obj,
    new_home_id,
    read_token,
    verify_raw_credential,
    write_token,
)
from .configs import (
    ENV_NAME_RE,
    ProjectConfig,
    config_hash,
    dumps_toml,
    load_global_config,
    load_project_config,
    project_config_json_obj,
    set_nested_toml_value,
    validate_global_config_data,
)
from .context import (
    Context,
    context_marker_obj,
    find_marker,
    marker_path,
    normalize_path,
    path_hash,
    write_marker,
)
from .db import (
    Database,
    all_rows,
    canonical_json,
    connect_initialized,
    contract_json_obj,
    one,
)
from .docker_platform import normalize_docker_platform
from .errors import AlabError, error_exit_code
from .home import DEFAULT_CONFIG, Home, ensure_layout, is_initialized
from .ids import new_id, require_complete_id, slugify
from .proc import run_cmd
from .rendering import ResultBlock, multiline_text
from .runner import (
    DOCKER_CAPABILITY_KEYS,
    capture_artifacts,
    clean_copy_from_git,
    docker_runtime_fingerprint,
    load_harbor_task,
    probe_docker_capabilities,
    prune_docker_image,
    run_configured_runner,
    store_log_file,
)
from .source_import import (
    canonical_tree_hash,
    copy_filtered_source,
    init_snapshot_repo,
    reject_gitlinks,
)
from .timeutil import parse_rfc3339_utc, utc_now


@dataclass
class GlobalOptions:
    home: Home
    output: str = "text"
    key: str | None = None
    key_source: str | None = None


@dataclass
class Request:
    globals: GlobalOptions
    context: Context | None
    actor: Actor | None = None


@dataclass
class AdapterDerivedSource:
    origin_type: str
    source_path: Path | None
    empty: bool
    safe_summary: str
    exact: dict[str, Any]


@dataclass
class RunExecutionSummary:
    run_id: str
    commit: str
    created_commit: bool
    status: str
    reward: float | None
    reward_parse_status: str
    exit_code: int | None
    stdout_preview: str | None
    stderr_preview: str | None
    artifact_count: int
    failure_reason: str | None
    warning_codes: list[str]


def _failure_fields(code: str, reason: str, next_action: str) -> list[tuple[str, Any]]:
    return [
        ("error code", code),
        ("exit code", error_exit_code(code)),
        ("reason", reason),
        ("next", next_action),
    ]


def _baseline_failure_fields(status: str, next_action: str) -> list[tuple[str, Any]]:
    if status in {"passed", "skipped", "inherited", "dry-run"}:
        return []
    return _failure_fields("BASELINE_VALIDATION_FAILED", f"baseline validation status is {status}", next_action)


def _result_failure_tail(fields: list[tuple[str, Any]]) -> list[tuple[str, Any]]:
    field_map = dict(fields)
    if "error code" not in field_map:
        return []
    return [(label, field_map.get(label)) for label in ("error code", "exit code", "reason", "next")]


def _runner_failure_reason(status: str, exit_code: int | None, reward_parse_status: str, failure_reason: str | None) -> str | None:
    if status == "passed":
        return None
    if failure_reason:
        return failure_reason
    if status == "timeout":
        return "runner timed out"
    if status == "error" and reward_parse_status in {"missing", "invalid", "error"} and exit_code == 0:
        return f"reward parse status is {reward_parse_status}"
    if status == "error":
        return "runner recorded an error"
    exit_detail = f" with code {exit_code}" if exit_code is not None else ""
    return f"runner exited{exit_detail}"


def _run_failure_fields(summary: RunExecutionSummary, next_action: str) -> list[tuple[str, Any]]:
    if summary.status == "passed":
        return []
    reason = _runner_failure_reason(summary.status, summary.exit_code, summary.reward_parse_status, summary.failure_reason)
    if summary.status == "timeout":
        return _failure_fields("RUNNER_TIMEOUT", reason or "runner timed out", next_action)
    if summary.status == "error" and summary.reward_parse_status in {"missing", "invalid", "error"} and summary.exit_code == 0:
        return _failure_fields("REWARD_PARSE_ERROR", f"reward parse status is {summary.reward_parse_status}", next_action)
    if summary.status == "error":
        return _failure_fields("RUNNER_ERROR", reason or "runner recorded an error", next_action)
    return _failure_fields("RUNNER_FAILED", reason or "runner exited", next_action)


def _submission_failure_block(exp_id: str, refs: list[str], code: str, reason: str, next_action: str) -> ResultBlock:
    return ResultBlock(
        "submission",
        [
            ("exp id", exp_id),
            ("submit accepted", False),
            ("final run id", None),
            ("final commit", None),
            ("experiment status", "open"),
            ("summary stored", False),
            ("feedback stored", False),
            ("ref", refs),
            *_failure_fields(code, reason, next_action),
        ],
    )


def _assert_utf8_max_bytes(label: str, value: str, max_bytes: int) -> None:
    if len(value.encode("utf-8")) > max_bytes:
        raise AlabError("CONFIG_INVALID", f"{label} exceeds {max_bytes} bytes")


def _read_text_input_file(path_value: str, label: str) -> str:
    path = Path(path_value)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise AlabError("CONFIG_INVALID", f"{label} file not found") from exc
    except IsADirectoryError as exc:
        raise AlabError("CONFIG_INVALID", f"{label} file is a directory") from exc
    except UnicodeDecodeError as exc:
        raise AlabError("CONFIG_INVALID", f"{label} file must be UTF-8") from exc
    except OSError as exc:
        reason = exc.strerror or str(exc)
        raise AlabError("CONFIG_INVALID", f"{label} file cannot be read: {reason}") from exc


def _assert_non_empty_text(label: str, value: str) -> None:
    if not value:
        raise AlabError("CONFIG_INVALID", f"{label} must be non-empty")


def _assert_display_name(label: str, value: str) -> None:
    _assert_non_empty_text(label, value)
    _assert_utf8_max_bytes(label, value, 120)


def _validate_project_config_text_fields(config: ProjectConfig) -> None:
    _assert_display_name("project.name", config.project.name)
    _assert_non_empty_text("project.task", config.project.task)
    _assert_utf8_max_bytes("project.task", config.project.task, 65536)
    if config.project.goal is not None:
        _assert_utf8_max_bytes("project.goal", config.project.goal, 65536)


def _tag_slug(value: str) -> str:
    slug = slugify(value, "tag")
    _assert_utf8_max_bytes("tag", slug, 64)
    return slug


def _lifecycle_reason(args: list[str]) -> str | None:
    require_options_at_most_once(args, ("--reason",))
    reason = command_arg(args, "--reason")
    if reason is not None:
        _assert_utf8_max_bytes("reason", reason, 65536)
    return reason


@dataclass
class PreparedSource:
    origin_type: str
    source_work: Path
    origin_records: list[dict[str, Any]]


@dataclass(frozen=True)
class SourceImportLimits:
    max_files: int
    max_total_bytes: int
    max_file_bytes: int


@dataclass
class SourceImportResult:
    source_id: str
    source_ref: str
    name: str
    source_commit: str
    tree_hash: str
    deduped: bool
    warnings: list[str]


@dataclass(frozen=True)
class ExperimentOperationLock:
    lock_name: str
    owner_operation_id: str


@dataclass
class TrashStage:
    audit_id: str
    original_path: Path | None
    trash_path: Path | None
    audit_label: str | None
    mode: str
    moved: bool
    already_absent: bool


@dataclass
class FilesystemRemovalTarget:
    kind: str
    object_id: str
    path: Path


@dataclass
class _ResolvedRemovalTarget:
    target: FilesystemRemovalTarget
    resolved: Path
    order: int


@dataclass
class GitRefDeletion:
    branch_ref: str
    commit: str | None
    deleted: bool
    already_absent: bool


DEFAULT_SOURCE_IMPORT_LIMITS = SourceImportLimits(
    max_files=100000,
    max_total_bytes=1073741824,
    max_file_bytes=104857600,
)
SOURCE_ORIGIN_TYPES = {"local", "git", "empty", "harbor", "skydiscover"}
RUNNER_TYPES = {"local", "docker", "harbor", "skydiscover_docker", "skydiscover_python"}
ARTIFACT_ROOTS = {"workspace", "run"}
LOG_STREAMS = {"stdout", "stderr", "hidden_stdout", "hidden_stderr"}
TOKEN_MODES = {"worktree", "inspection"}
VISIBILITY_SCOPES = {"none", "same_project", "explicit"}
EXPERIMENT_STATUSES = {"open", "closed", "archived"}
KEY_ROLES = {"admin"}
AUDIT_OBJECT_TYPES = {
    "annotation",
    "artifact",
    "backup",
    "cache",
    "catalog",
    "credential",
    "experiment",
    "inspection_checkout",
    "lock",
    "log",
    "project",
    "run",
    "secret_value",
    "source",
    "validation",
    "worktree",
}
AUDIT_METADATA_KEYS = {
    "schema_version",
    "active_dependent_artifact_count",
    "active_dependent_log_count",
    "annotation_status",
    "archive_status",
    "archived_at",
    "blockers",
    "branch",
    "branch_ref",
    "branch_ref_already_absent",
    "branch_ref_commit",
    "branch_ref_deleted",
    "cache_kinds",
    "cleared_count",
    "config",
    "context_type",
    "created_credential_id",
    "created_for_path_hash",
    "created_registry_row",
    "created_token_id",
    "credential",
    "credential_status",
    "credential_type",
    "deleted_artifact_count",
    "deleted_count",
    "deleted_log_count",
    "deleted_revision_count",
    "dirty_state",
    "experiment_status",
    "filesystem",
    "filesystem_absent_count",
    "filesystem_path_already_absent",
    "filesystem_target_count",
    "final_run_removed",
    "inspection_commit",
    "latest_run_id_after",
    "latest_run_id_before",
    "path_registry_id",
    "pinned_commit",
    "previous_archive_status",
    "previous_path_hash",
    "previous_status",
    "project_status",
    "pruned_count",
    "registered_path_hash",
    "repair_mode",
    "repaired_at",
    "repaired_path_hash",
    "requested_ref",
    "restored_path_hash",
    "revoked_at",
    "revoked_credential_id",
    "revoked_token_id",
    "role",
    "safe_summary",
    "source_status",
    "token_mode",
    "token_revocation_target",
    "trash",
    "unarchived_at",
    "warning_count",
    "worktree_state",
}


def audit_deleted_ids_json_obj(text: str) -> dict[str, Any]:
    deleted = contract_json_obj(
        text,
        label="audit_events.deleted_ids_json",
        allowed_keys={"schema_version", "counts", "ids"},
        required_keys={"counts", "ids"},
    )
    counts = deleted["counts"]
    ids = deleted["ids"]
    if not isinstance(counts, dict):
        raise AlabError("STORAGE_ERROR", "audit_events.deleted_ids_json counts must be a JSON object")
    if not isinstance(ids, dict):
        raise AlabError("STORAGE_ERROR", "audit_events.deleted_ids_json ids must be a JSON object")
    unknown = sorted((set(counts) | set(ids)) - AUDIT_OBJECT_TYPES)
    if unknown:
        raise AlabError("STORAGE_ERROR", f"audit_events.deleted_ids_json contains unknown object types: {', '.join(unknown)}")
    result_counts: dict[str, int] = {}
    result_ids: dict[str, list[str]] = {}
    for object_type in sorted(set(counts) | set(ids)):
        count = counts.get(object_type, 0)
        id_values = ids.get(object_type, [])
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise AlabError("STORAGE_ERROR", "audit_events.deleted_ids_json counts must be non-negative integers")
        if not isinstance(id_values, list) or not all(isinstance(object_id, str) for object_id in id_values):
            raise AlabError("STORAGE_ERROR", "audit_events.deleted_ids_json ids must be string arrays")
        sorted_ids = sorted(set(id_values))
        if count != len(sorted_ids):
            raise AlabError("STORAGE_ERROR", "audit_events.deleted_ids_json counts must match ids")
        result_counts[object_type] = count
        result_ids[object_type] = sorted_ids
    return {**deleted, "counts": result_counts, "ids": result_ids}


def audit_metadata_json_obj(text: str) -> dict[str, Any]:
    metadata = contract_json_obj(
        text,
        label="audit_events.metadata_json",
        allowed_keys=AUDIT_METADATA_KEYS,
        required_keys=set(),
    )
    if "trash" in metadata and not isinstance(metadata["trash"], (dict, list)):
        raise AlabError("STORAGE_ERROR", "audit_events.metadata_json trash must be an object or array")
    if "blockers" in metadata and (not isinstance(metadata["blockers"], list) or not all(isinstance(blocker, str) for blocker in metadata["blockers"])):
        raise AlabError("STORAGE_ERROR", "audit_events.metadata_json blockers must be a string array")
    if "cache_kinds" in metadata and (not isinstance(metadata["cache_kinds"], list) or not all(isinstance(kind, str) for kind in metadata["cache_kinds"])):
        raise AlabError("STORAGE_ERROR", "audit_events.metadata_json cache_kinds must be a string array")
    for key in ("config", "credential", "filesystem"):
        if key in metadata and not isinstance(metadata[key], dict):
            raise AlabError("STORAGE_ERROR", f"audit_events.metadata_json {key} must be a JSON object")
    return metadata


def audit(
    conn,
    *,
    action: str,
    object_type: str,
    object_id: str,
    actor: Actor | None,
    audit_id: str | None = None,
    project_id: str | None = None,
    exp_id: str | None = None,
    cascade: bool = False,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    audit_id = audit_id or new_id("aud", action)
    conn.execute(
        """
        INSERT INTO audit_events(audit_id, project_id, exp_id, actor_credential_id, actor_type,
          action, object_type, object_id, cascade, reason, deleted_ids_json, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id,
            project_id,
            exp_id,
            actor.credential_id if actor else None,
            actor.actor_type if actor else "system",
            action,
            object_type,
            object_id,
            1 if cascade else 0,
            reason,
            canonical_json(audit_deleted_ids_json_obj(canonical_json({"schema_version": 1, "counts": {}, "ids": {}}))),
            canonical_json(audit_metadata_json_obj(canonical_json(metadata or {"schema_version": 1}))),
            utc_now(),
        ),
    )
    return audit_id


def require_home(home: Home):
    return connect_initialized(home)


def require_actor(req: Request, allowed: str | tuple[str, ...], project_id: str | None = None) -> Actor:
    conn = require_home(req.globals.home)
    try:
        raw = req.globals.key
        if raw is None:
            raw = os.environ.get("ALAB_KEY") or None
        if raw is None:
            raise AlabError("AUTH_REQUIRED", "credential is required")
        return verify_raw_credential(conn, raw, required=allowed, project_id=project_id)
    finally:
        conn.close()


def _actor_is_project_admin_or_root(actor: Actor | None, project_id: str | None) -> bool:
    if actor is None:
        return False
    if actor.actor_type == "root":
        return True
    return bool(project_id and actor.actor_type == "admin" and actor.project_id == project_id)


def cmd_help(args: list[str], req: Request) -> list[ResultBlock]:
    raise AlabError("CONFIG_INVALID", "help is handled by the CLI help renderer")


def command_arg(args: list[str], name: str, *, required: bool = False, default: str | None = None) -> str | None:
    if name in args:
        idx = args.index(name)
        if idx + 1 >= len(args) or args[idx + 1].startswith("--"):
            raise AlabError("CONFIG_INVALID", f"{name} requires a value")
        return _command_value(name, args[idx + 1])
    if required:
        raise AlabError("CONFIG_INVALID", f"missing required option {name}")
    return default


def command_args(args: list[str], name: str) -> list[str]:
    values: list[str] = []
    for idx, item in enumerate(args):
        if item == name:
            if idx + 1 >= len(args) or args[idx + 1].startswith("--"):
                raise AlabError("CONFIG_INVALID", f"{name} requires a value")
            values.append(_command_value(name, args[idx + 1]))
    return values


def option_count(args: list[str], name: str) -> int:
    return sum(1 for item in args if item == name)


OPTIONS_WITH_VALUES = {
    "--home",
    "--output",
    "--key",
    "--role",
    "--config",
    "--project",
    "--source-path",
    "--source-git",
    "--source-ref",
    "--from-exp",
    "--from-commit",
    "--git-ref",
    "--source-subdir",
    "--mutable-include",
    "--mutable-exclude",
    "--visibility-scope",
    "--visible-exp",
    "--name",
    "--task",
    "--goal",
    "--path",
    "--message",
    "--summary",
    "--summary-file",
    "--feedback",
    "--feedback-file",
    "--ref",
    "--out",
    "--version",
    "--confirm",
    "--reason",
    "--body",
    "--body-file",
    "--target",
    "--tag",
    "--limit",
    "--offset",
    "--query",
    "--run",
    "--exp",
    "--validation",
    "--object-type",
    "--object-id",
    "--action",
    "--actor",
    "--created-after",
    "--created-before",
    "--updated-after",
    "--updated-before",
    "--started-after",
    "--started-before",
    "--ended-after",
    "--ended-before",
    "--max-files",
    "--max-total-bytes",
    "--max-file-bytes",
    "--status",
    "--source-id",
    "--name-query",
    "--reward-min",
    "--reward-max",
    "--runner-type",
    "--exit-code",
    "--failure-reason-query",
    "--content-hash",
    "--path-query",
    "--root",
    "--stream",
    "--sort",
    "--config-version",
    "--token-id",
    "--mode",
    "--size-min",
    "--size-max",
    "--truncated",
    "--value-file",
    "--commit",
    "--private-to-exp",
    "--author",
    "--target-type",
    "--target-id",
    "--created-by",
    "--keep",
    "--older-than",
    "--origin-url",
}


EMPTY_COMMAND_VALUE_ALLOWED = {
    "--author",
    "--body",
    "--failure-reason-query",
    "--feedback",
    "--goal",
    "--message",
    "--name-query",
    "--path-query",
    "--query",
    "--reason",
    "--summary",
}


def _command_value(name: str, value: str) -> str:
    if value == "" and name not in EMPTY_COMMAND_VALUE_ALLOWED:
        raise AlabError("CONFIG_INVALID", f"{name} requires a non-empty value")
    return value


def require_options_at_most_once(args: list[str], options: tuple[str, ...]) -> None:
    for option in options:
        if option_count(args, option) > 1:
            raise AlabError("CONFIG_INVALID", f"{option} may be provided once")


def require_known_options(args: list[str], allowed_options: tuple[str, ...]) -> None:
    allowed = set(allowed_options)
    for item in args:
        if item == "--":
            break
        if item.startswith("--") and item not in allowed:
            raise AlabError("CONFIG_INVALID", f"unsupported option {item}")


def require_exactly_one_option_pair(args: list[str], first: str, second: str, message: str) -> None:
    require_options_at_most_once(args, (first, second))
    if option_count(args, first) + option_count(args, second) != 1:
        raise AlabError("CONFIG_INVALID", message)


def require_force_confirm(args: list[str], expected_confirm: str, message: str) -> None:
    require_options_at_most_once(args, ("--force", "--confirm"))
    if option_count(args, "--force") != 1 or option_count(args, "--confirm") != 1 or command_arg(args, "--confirm") != expected_confirm:
        raise AlabError("CONFIG_INVALID", message)


def require_dry_run_unforced(args: list[str]) -> None:
    require_options_at_most_once(args, ("--force", "--confirm"))
    if flag(args, "--dry-run") and (flag(args, "--force") or option_count(args, "--confirm")):
        raise AlabError("CONFIG_INVALID", "--dry-run conflicts with --force/--confirm")


def require_dry_run_skip_baseline_compatible(args: list[str]) -> None:
    if flag(args, "--dry-run") and flag(args, "--skip-baseline-test"):
        raise AlabError("CONFIG_INVALID", "--dry-run conflicts with --skip-baseline-test")


def require_positional_count(args: list[str], count: int, message: str, *, options_with_values: tuple[str, ...] | None = None) -> list[str]:
    pos = positional(args, options_with_values=options_with_values)
    if len(pos) != count:
        raise AlabError("CONFIG_INVALID", message)
    return pos


def optional_positional_selector(args: list[str], message: str, *, options_with_values: tuple[str, ...] | None = None) -> str | None:
    pos = positional(args, options_with_values=options_with_values)
    if len(pos) > 1:
        raise AlabError("CONFIG_INVALID", message)
    return pos[0] if pos else None


def flag(args: list[str], name: str) -> bool:
    return name in args


def positional(args: list[str], *, options_with_values: tuple[str, ...] | None = None) -> list[str]:
    result: list[str] = []
    skip = False
    value_options = OPTIONS_WITH_VALUES if options_with_values is None else set(options_with_values)
    for idx, item in enumerate(args):
        if skip:
            skip = False
            continue
        if item in value_options:
            if idx + 1 >= len(args) or args[idx + 1].startswith("--"):
                raise AlabError("CONFIG_INVALID", f"{item} requires a value")
            _command_value(item, args[idx + 1])
            skip = True
            continue
        if item.startswith("--"):
            continue
        result.append(item)
    return result


def cmd_auth_init(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ())
    require_positional_count(args, 0, "auth init accepts no positional arguments")
    home = req.globals.home
    if home.path.exists() and any(home.path.iterdir()) and not is_initialized(home):
        raise AlabError("HOME_EXISTS", "home exists and is not an initialized ALab home")
    if is_initialized(home):
        raise AlabError("HOME_EXISTS", "ALab home is already initialized")
    ensure_layout(home)
    db = Database(home)
    db.migrate()
    with db.tx() as conn:
        now = utc_now()
        home_id = new_home_id()
        conn.execute(
            "INSERT INTO homes(home_id, schema_version, created_at, updated_at) VALUES (?, 1, ?, ?)",
            (home_id, now, now),
        )
        _, raw_root = create_credential(conn, credential_type="root", metadata={"schema_version": 1})
    return [
        ResultBlock(
            "auth",
            [
                ("home", str(home.path)),
                ("home id", home_id),
                ("root key", raw_root),
                ("created", now),
            ],
        )
    ]


def cmd_auth_root_regenerate(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ())
    actor = require_actor(req, "root")
    require_positional_count(args, 0, "auth root regenerate accepts no positional arguments")
    db = Database(req.globals.home)
    with db.tx() as conn:
        now = utc_now()
        conn.execute(
            "UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_type = 'root' AND status = 'active'",
            (now,),
        )
        key_id, raw = create_credential(conn, credential_type="root", metadata={"schema_version": 1})
        home_id = one(conn, "SELECT home_id FROM homes LIMIT 1")["home_id"]
        audit(
            conn,
            action="regenerate",
            object_type="credential",
            object_id=key_id,
            actor=actor,
            metadata={
                "schema_version": 1,
                "credential_type": "root",
                "revoked_credential_id": actor.credential_id,
                "created_credential_id": key_id,
                "revoked_at": now,
            },
        )
    return [
        ResultBlock(
            "auth",
            [
                ("home", str(req.globals.home.path)),
                ("home id", home_id),
                ("root key", raw),
                ("revoked key id", actor.credential_id),
                ("created key id", key_id),
            ],
        )
    ]


def cmd_key_create(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--role"))
    require_options_at_most_once(args, ("--project", "--role"))
    actor = require_actor(req, "root")
    require_positional_count(args, 0, "key create accepts no positional arguments")
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    role = _require_option_choice(command_arg(args, "--role", default="admin"), "--role", KEY_ROLES)
    with Database(req.globals.home).tx() as conn:
        _project_row(conn, project_id)
        key_id, raw_admin = create_credential(conn, credential_type="admin", project_id=project_id, metadata={"schema_version": 1, "role": "admin"})
        row = one(conn, "SELECT created_at FROM credentials WHERE credential_id = ?", (key_id,))
        audit(conn, action="add", object_type="credential", object_id=key_id, actor=actor, project_id=project_id)
    return [
        ResultBlock(
            "credential",
            [
                ("project id", project_id),
                ("key id", key_id),
                ("role", role),
                ("admin key", raw_admin),
                ("created", row["created_at"] if row else None),
            ],
        )
    ]


def cmd_key_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--root"))
    require_options_at_most_once(args, ("--project", "--root"))
    root_scope = flag(args, "--root")
    explicit_project_id = command_arg(args, "--project")
    project_id = explicit_project_id or (req.context.project_id if req.context else None)
    if root_scope and explicit_project_id:
        raise AlabError("CONFIG_INVALID", "--root conflicts with --project")
    if root_scope:
        require_actor(req, "root")
        require_positional_count(args, 0, "key list accepts no positional arguments", options_with_values=("--project",))
        conn = require_home(req.globals.home)
        try:
            rows = all_rows(conn, "SELECT * FROM credentials WHERE credential_type = 'root' ORDER BY created_at", ())
            return [
                ResultBlock(
                    "credential",
                    [
                        ("key id", row["credential_id"]),
                        ("credential type", row["credential_type"]),
                        ("status", row["status"]),
                        ("created at", row["created_at"]),
                        ("revoked at", row["revoked_at"]),
                    ],
                )
                for row in rows
            ]
        finally:
            conn.close()
    require_actor(req, ("root", "admin"), project_id=project_id)
    require_positional_count(args, 0, "key list accepts no positional arguments", options_with_values=("--project",))
    conn = require_home(req.globals.home)
    try:
        _project_row(conn, project_id)
        rows = all_rows(conn, "SELECT * FROM credentials WHERE credential_type = 'admin' AND project_id = ? ORDER BY created_at", (project_id,))
        return [
            ResultBlock(
                "credential",
                [
                    ("project id", project_id),
                    ("key id", row["credential_id"]),
                    ("role", "admin"),
                    ("status", row["status"]),
                    ("created at", row["created_at"]),
                    ("revoked at", row["revoked_at"]),
                ],
            )
            for row in rows
        ]
    finally:
        conn.close()


def cmd_key_revoke(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    require_options_at_most_once(args, ("--project",))
    actor = require_actor(req, "root")
    key_id = optional_positional_selector(args, "key revoke accepts exactly one key id")
    key_id = _complete_id_or_missing(key_id, prefix="cred", code="CREDENTIAL_NOT_FOUND", label="key id")
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    with Database(req.globals.home).tx() as conn:
        row = one(conn, "SELECT * FROM credentials WHERE credential_id = ?", (key_id,))
        if row is None:
            raise AlabError("CREDENTIAL_NOT_FOUND", "credential not found")
        if project_id and row["project_id"] != project_id:
            raise AlabError("CREDENTIAL_NOT_FOUND", "credential not found in project")
        if row["credential_type"] == "root" and row["status"] == "active":
            active_roots = one(conn, "SELECT count(*) AS c FROM credentials WHERE credential_type = 'root' AND status = 'active'")["c"]
            if active_roots <= 1:
                raise AlabError("CONFIG_INVALID", "cannot revoke the only active root key")
        revoked_at = row["revoked_at"] or utc_now()
        if row["status"] != "revoked":
            conn.execute("UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?", (revoked_at, key_id))
            audit(
                conn,
                action="revoke",
                object_type="credential",
                object_id=key_id,
                actor=actor,
                project_id=row["project_id"],
                exp_id=row["exp_id"],
                metadata={
                    "schema_version": 1,
                    "credential_type": row["credential_type"],
                    "token_mode": row["token_mode"],
                    "previous_status": row["status"],
                    "credential_status": "revoked",
                    "revoked_at": revoked_at,
                },
            )
    return [ResultBlock("credential", [("key id", key_id), ("status", "revoked"), ("revoked at", revoked_at)])]


def cmd_config_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ())
    require_positional_count(args, 0, "config show accepts no positional arguments")
    ensure_layout(req.globals.home)
    data = load_global_config(req.globals.home.config_path)
    return [
        ResultBlock(
            "config",
            [
                ("home", str(req.globals.home.path)),
                ("schema version", data["schema_version"]),
                ("output format", data.get("output", {}).get("format", "text")),
                ("preview bytes", data.get("output", {}).get("preview_bytes", 4096)),
                ("busy timeout ms", data.get("storage", {}).get("busy_timeout_ms", 5000)),
                ("lock acquire timeout ms", data.get("locks", {}).get("acquire_timeout_ms", 30000)),
                ("lock heartbeat interval ms", data.get("locks", {}).get("heartbeat_interval_ms", 5000)),
                ("lock stale after ms", data.get("locks", {}).get("stale_after_ms", 120000)),
                ("config valid", True),
            ],
        )
    ]


GLOBAL_CONFIG_ALLOWED_FIELDS = {
    "output.format",
    "output.preview_bytes",
    "storage.busy_timeout_ms",
    "locks.acquire_timeout_ms",
    "locks.heartbeat_interval_ms",
    "locks.stale_after_ms",
}


def _default_global_config() -> dict[str, Any]:
    return tomllib.loads(DEFAULT_CONFIG)


def _load_global_config_for_edit(home: Home) -> dict[str, Any]:
    try:
        data = tomllib.loads(home.config_path.read_text(encoding="utf-8")) if home.config_path.exists() else _default_global_config()
    except tomllib.TOMLDecodeError as exc:
        raise AlabError("CONFIG_INVALID", f"invalid global config: {exc}", "alab config reset --all") from exc
    if data.get("schema_version") != 1:
        raise AlabError("CONFIG_INVALID", "global config schema_version must be 1")
    return data


def _global_preview_bytes(home: Home) -> int:
    return int(load_global_config(home.config_path).get("output", {}).get("preview_bytes", 4096))


def _validate_global_config_field(field: str) -> None:
    if field not in GLOBAL_CONFIG_ALLOWED_FIELDS:
        raise AlabError("CONFIG_INVALID", "unsupported config field")


def _set_nested_value(data: dict[str, Any], field: str, value: Any) -> dict[str, Any]:
    parts = field.split(".")
    current = data
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value
    return data


def _nested_value(data: dict[str, Any], field: str) -> Any:
    current: Any = data
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _validate_global_config_data(data: dict[str, Any]) -> None:
    validate_global_config_data(data)


def cmd_config_set(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ())
    pos = require_positional_count(args, 2, "config set requires field and TOML literal")
    ensure_layout(req.globals.home)
    _validate_global_config_field(pos[0])
    data = _load_global_config_for_edit(req.globals.home)
    previous = json.loads(json.dumps(data))
    data = set_nested_toml_value(data, pos[0], pos[1])
    _validate_global_config_data(data)
    req.globals.home.config_path.write_text(dumps_toml(data), encoding="utf-8")
    return [
        ResultBlock(
            "config",
            [
                ("field", pos[0]),
                ("previous value", json.dumps(previous, sort_keys=True)),
                ("value", pos[1]),
                ("config valid", True),
            ],
        )
    ]


def cmd_config_reset(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--all",))
    require_options_at_most_once(args, ("--all",))
    ensure_layout(req.globals.home)
    field = optional_positional_selector(args, "config reset requires exactly one field or --all")
    all_flag = flag(args, "--all")
    if all_flag == bool(field):
        raise AlabError("CONFIG_INVALID", "config reset requires exactly one field or --all")
    if all_flag:
        req.globals.home.config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        return [ResultBlock("config", [("reset", "all"), ("field", "all"), ("value", "default"), ("config valid", True)])]
    _validate_global_config_field(field)
    data = _load_global_config_for_edit(req.globals.home)
    default_data = _default_global_config()
    data = _set_nested_value(data, field, _nested_value(default_data, field))
    _validate_global_config_data(data)
    req.globals.home.config_path.write_text(dumps_toml(data), encoding="utf-8")
    return [ResultBlock("config", [("reset", "field"), ("field", field), ("value", "default"), ("config valid", True)])]


def _stored_string_array(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AlabError("STORAGE_ERROR", f"{label} must be a string array")
    return list(value)


def runtime_capability_details_json_obj(text: str) -> dict[str, Any]:
    details = contract_json_obj(
        text,
        label="runtime_capabilities.details_json",
        allowed_keys={"schema_version", "capability", "safe_summary", "probed_values", "error_code"},
        required_keys={"capability", "safe_summary", "probed_values"},
    )
    if not isinstance(details["capability"], str) or not details["capability"]:
        raise AlabError("STORAGE_ERROR", "runtime_capabilities.details_json capability must be a non-empty string")
    if not isinstance(details["safe_summary"], str):
        raise AlabError("STORAGE_ERROR", "runtime_capabilities.details_json safe_summary must be a string")
    if not isinstance(details["probed_values"], dict):
        raise AlabError("STORAGE_ERROR", "runtime_capabilities.details_json probed_values must be a JSON object")
    if "error_code" in details and not isinstance(details["error_code"], str):
        raise AlabError("STORAGE_ERROR", "runtime_capabilities.details_json error_code must be a string")
    return details


def catalog_metadata_json_obj(text: str) -> dict[str, Any]:
    metadata = contract_json_obj(
        text,
        label="catalogs.metadata_json",
        allowed_keys={"schema_version", "safe_summary", "task_refs", "evaluator_refs", "warnings"},
        required_keys={"safe_summary", "task_refs", "evaluator_refs"},
    )
    if not isinstance(metadata["safe_summary"], str):
        raise AlabError("STORAGE_ERROR", "catalogs.metadata_json safe_summary must be a string")
    metadata["task_refs"] = _stored_string_array(metadata["task_refs"], label="catalogs.metadata_json task_refs")
    metadata["evaluator_refs"] = _stored_string_array(metadata["evaluator_refs"], label="catalogs.metadata_json evaluator_refs")
    if "warnings" in metadata:
        metadata["warnings"] = _stored_string_array(metadata["warnings"], label="catalogs.metadata_json warnings")
    return metadata


def cache_metadata_json_obj(text: str) -> dict[str, Any]:
    metadata = contract_json_obj(
        text,
        label="cache_entries.metadata_json",
        allowed_keys={"schema_version", "safe_summary", "inputs_hash", "warnings"},
        required_keys={"safe_summary", "inputs_hash"},
    )
    if not isinstance(metadata["safe_summary"], str):
        raise AlabError("STORAGE_ERROR", "cache_entries.metadata_json safe_summary must be a string")
    if not isinstance(metadata["inputs_hash"], str) or not metadata["inputs_hash"]:
        raise AlabError("STORAGE_ERROR", "cache_entries.metadata_json inputs_hash must be a non-empty string")
    if "warnings" in metadata:
        metadata["warnings"] = _stored_string_array(metadata["warnings"], label="cache_entries.metadata_json warnings")
    return metadata


def _capability_from_row(row) -> dict[str, Any]:
    return {
        "capability_key": row["capability_key"],
        "fingerprint": row["fingerprint"],
        "status": row["status"],
        "details": runtime_capability_details_json_obj(row["details_json"]),
        "checked_at": row["checked_at"],
    }


def _refresh_docker_capability_rows(conn, *, refresh: bool) -> list[dict[str, Any]]:
    placeholders = ", ".join("?" for _ in DOCKER_CAPABILITY_KEYS)
    if refresh:
        conn.execute(f"DELETE FROM runtime_capabilities WHERE capability_key IN ({placeholders})", DOCKER_CAPABILITY_KEYS)
    fingerprint = docker_runtime_fingerprint()
    cached = all_rows(
        conn,
        f"SELECT * FROM runtime_capabilities WHERE capability_key IN ({placeholders}) AND fingerprint = ?",
        (*DOCKER_CAPABILITY_KEYS, fingerprint),
    )
    if len(cached) == len(DOCKER_CAPABILITY_KEYS):
        by_key = {row["capability_key"]: _capability_from_row(row) for row in cached}
        return [by_key[key] for key in DOCKER_CAPABILITY_KEYS]
    probes = probe_docker_capabilities()
    for probe in probes:
        conn.execute(
            """
            INSERT INTO runtime_capabilities(capability_key, fingerprint, status, details_json, checked_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(capability_key) DO UPDATE SET
              fingerprint = excluded.fingerprint,
              status = excluded.status,
              details_json = excluded.details_json,
              checked_at = excluded.checked_at
            """,
            (
                probe["capability_key"],
                probe["fingerprint"],
                probe["status"],
                canonical_json(probe["details"]),
                probe["checked_at"],
            ),
        )
    by_key = {probe["capability_key"]: probe for probe in probes}
    return [by_key[key] for key in DOCKER_CAPABILITY_KEYS]


def _docker_capabilities_for_validation(conn, *, allow_probe: bool) -> list[dict[str, Any]]:
    if allow_probe:
        return _refresh_docker_capability_rows(conn, refresh=False)
    fingerprint = docker_runtime_fingerprint()
    placeholders = ", ".join("?" for _ in DOCKER_CAPABILITY_KEYS)
    rows = all_rows(
        conn,
        f"SELECT * FROM runtime_capabilities WHERE capability_key IN ({placeholders}) AND fingerprint = ?",
        (*DOCKER_CAPABILITY_KEYS, fingerprint),
    )
    return [_capability_from_row(row) for row in rows] if len(rows) == len(DOCKER_CAPABILITY_KEYS) else probe_docker_capabilities()


def _validate_docker_resource_requirements(capabilities: list[dict[str, Any]], *, platform: str | None, cpus_required: bool, memory_required: bool) -> None:
    by_key = {capability["capability_key"]: capability for capability in capabilities}
    blockers: list[str] = []
    normalized_platform = normalize_docker_platform(platform)
    if normalized_platform:
        if normalized_platform == "linux":
            platform_capability = by_key.get("docker.platform.linux")
        elif normalized_platform in {"linux/amd64", "linux/arm64"}:
            platform_capability = by_key.get(f"docker.platform.{normalized_platform}")
        else:
            platform_capability = None
            blockers.append(f"runner.platform {platform} is not a supported V1 Docker platform selector")
        if platform_capability and platform_capability["status"] == "unsupported":
            blockers.append(f"runner.platform {normalized_platform} is not supported by the current Docker runtime")
        elif platform_capability is None and normalized_platform.startswith("linux/"):
            blockers.append("runner.platform is not supported by the current Docker runtime")
    if cpus_required:
        cpus = by_key.get("docker.resource.cpus")
        if cpus and cpus["status"] == "unsupported":
            blockers.append("runner.cpus is not supported by the current Docker runtime")
    if memory_required:
        memory = by_key.get("docker.resource.memory")
        if memory and memory["status"] == "unsupported":
            blockers.append("runner.memory_mb is not supported by the current Docker runtime")
    if blockers:
        raise AlabError("CONFIG_INVALID", "; ".join(blockers), "alab config validate --refresh-capabilities")


def _validate_docker_config_capabilities(conn, config: ProjectConfig, *, allow_probe: bool = True) -> None:
    if config.runner.type not in {"docker", "harbor", "skydiscover_docker"}:
        return
    capabilities = _docker_capabilities_for_validation(conn, allow_probe=allow_probe)
    _validate_docker_resource_requirements(
        capabilities,
        platform=config.runner.platform,
        cpus_required=config.runner.cpus is not None,
        memory_required=config.runner.memory_mb is not None,
    )


def cmd_config_validate(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--refresh-capabilities",))
    require_options_at_most_once(args, ("--refresh-capabilities",))
    require_positional_count(args, 0, "config validate accepts no positional arguments")
    load_global_config(req.globals.home.config_path)
    blocks = [ResultBlock("config", [("config valid", True), ("next", "none")])]
    if not is_initialized(req.globals.home):
        blocks.append(
            ResultBlock(
                "capability",
                [("capability", "none"), ("fingerprint", "none"), ("status", "not cached"), ("checked at", utc_now()), ("next", "alab auth init")],
            )
        )
        return blocks
    with Database(req.globals.home).tx() as conn:
        capabilities = _refresh_docker_capability_rows(conn, refresh=flag(args, "--refresh-capabilities"))
    for capability in capabilities:
        details = capability.get("details", {})
        next_action = "none" if capability["status"] == "supported" else details.get("safe_summary", "inspect local runtime")
        blocks.append(
            ResultBlock(
                "capability",
                [
                    ("capability", capability["capability_key"]),
                    ("fingerprint", capability["fingerprint"]),
                    ("status", capability["status"]),
                    ("checked at", capability["checked_at"]),
                    ("next", next_action),
                ],
            )
        )
    return blocks


def _project_paths(home: Home, project_id: str) -> tuple[Path, Path, Path]:
    project_root = home.projects_path / project_id
    return project_root, project_root / "repo.git", project_root / "artifacts"


def _ensure_project_artifact_layout(artifact_store: Path) -> None:
    (artifact_store / "blobs").mkdir(parents=True, exist_ok=True)
    (artifact_store / "logs").mkdir(parents=True, exist_ok=True)


def _write_git_exclude(path: Path) -> None:
    git_dir = Path(
        run_cmd(["git", "rev-parse", "--git-dir"], cwd=path)
        .stdout.decode("utf-8", errors="replace")
        .strip()
    )
    if not git_dir.is_absolute():
        git_dir = (path / git_dir).resolve()
    (git_dir / "info").mkdir(parents=True, exist_ok=True)
    exclude = git_dir / "info" / "exclude"
    current = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if ".alab/" not in current:
        with exclude.open("a", encoding="utf-8") as fh:
            fh.write("\n.alab/\n")


def _git_path(path: Path, name: str) -> Path:
    resolved = run_cmd(["git", "rev-parse", "--git-path", name], cwd=path).stdout.decode("utf-8", errors="replace").strip()
    git_path = Path(resolved)
    return git_path if git_path.is_absolute() else (path / git_path).resolve()


def _assert_experiment_git_state(exp: Any, worktree: Path) -> None:
    branch = run_cmd(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=worktree, check=False)
    if branch.returncode != 0:
        raise AlabError("GIT_STATE_INVALID", "experiment worktree must be on the registered branch")
    current_branch = branch.stdout.decode("utf-8", errors="replace").strip()
    if current_branch != exp["branch_name"]:
        raise AlabError("GIT_STATE_INVALID", f"experiment worktree is on {current_branch}, expected {exp['branch_name']}")
    for state_name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-merge", "rebase-apply"):
        if _git_path(worktree, state_name).exists():
            raise AlabError("GIT_STATE_INVALID", f"git operation in progress: {state_name}")


def _parse_name_status_z(data: bytes) -> list[str]:
    parts = data.decode("utf-8", errors="surrogateescape").split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    paths: list[str] = []
    idx = 0
    while idx < len(parts):
        status = parts[idx]
        idx += 1
        if not status:
            continue
        code = status[0]
        if code in {"R", "C"} and idx + 1 < len(parts):
            paths.extend([parts[idx], parts[idx + 1]])
            idx += 2
        elif idx < len(parts):
            paths.append(parts[idx])
            idx += 1
    return paths


def _changed_paths(worktree: Path, *args: str) -> list[str]:
    return _parse_name_status_z(run_cmd(["git", *args, "--find-renames", "--find-copies", "--find-copies-harder", "--name-status", "-z"], cwd=worktree).stdout)


def _dirty_paths(worktree: Path) -> list[str]:
    paths = _changed_paths(worktree, "diff", "--cached")
    paths.extend(_changed_paths(worktree, "diff"))
    untracked = run_cmd(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=worktree).stdout
    paths.extend(path for path in untracked.decode("utf-8", errors="surrogateescape").split("\0") if path)
    return _dedupe_paths(paths)


def _dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/").removeprefix("./")
        if not normalized or normalized == ".alab" or normalized.startswith(".alab/") or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _pathspec_from_lines(lines: list[str]):
    try:
        import pathspec

        if hasattr(pathspec, "GitIgnoreSpec"):
            return pathspec.GitIgnoreSpec.from_lines(lines)
        return pathspec.PathSpec.from_lines("gitignore", lines)
    except Exception:
        class FallbackPathSpec:
            def __init__(self, patterns: list[str]):
                self.patterns = patterns

            def match_file(self, rel: str) -> bool:
                normalized = rel.strip("/")
                for pattern in self.patterns:
                    raw = pattern.strip("/")
                    if not raw:
                        continue
                    if raw == "**":
                        return True
                    if raw.endswith("/**"):
                        prefix = raw[:-3].strip("/")
                        if normalized == prefix or normalized.startswith(prefix + "/"):
                            return True
                    if "/" not in raw:
                        if any(part == raw for part in normalized.split("/")) or fnmatch.fnmatch(PurePosixPath(normalized).name, raw):
                            return True
                    elif fnmatch.fnmatch(normalized, raw):
                        return True
                return False

        return FallbackPathSpec(lines)


def _mutable_policy_allows(policy: dict[str, Any], path: str) -> bool:
    normalized = path.replace("\\", "/").removeprefix("./")
    if normalized == ".alab" or normalized.startswith(".alab/"):
        return False
    include = [str(item) for item in policy.get("include") or ["**"]]
    exclude = [str(item) for item in policy.get("exclude") or []]
    if not _pathspec_from_lines(include).match_file(normalized):
        return False
    if exclude and _pathspec_from_lines(exclude).match_file(normalized):
        return False
    return True


def _mutable_policies_for_exp(exp: Any) -> list[dict[str, Any]]:
    policy_json = experiment_policy_json_obj(exp["policy_json"])
    project_policy = policy_json.get("mutable") or {"include": ["**"], "exclude": []}
    override = policy_json.get("mutable_override")
    if isinstance(override, dict):
        return [project_policy, override]
    return [project_policy]


def _mutable_blocked_paths(exp: Any, paths: list[str]) -> list[str]:
    policies = _mutable_policies_for_exp(exp)
    return [path for path in _dedupe_paths(paths) if not all(_mutable_policy_allows(policy, path) for policy in policies)]


def _mutable_scope_reason(blocked: list[str], reason: str) -> str:
    preview = ", ".join(blocked[:5])
    if len(blocked) > 5:
        preview += f", +{len(blocked) - 5} more"
    return f"{reason} outside mutable scope: {preview}"


def _assert_mutable_paths_allowed(exp: Any, paths: list[str], reason: str) -> None:
    blocked = _mutable_blocked_paths(exp, paths)
    if blocked:
        raise AlabError("SCOPE_VIOLATION", _mutable_scope_reason(blocked, reason), "change only files allowed by the experiment mutable policy")


def _experiment_mutable_override(args: list[str]) -> dict[str, Any] | None:
    include = command_args(args, "--mutable-include")
    exclude = command_args(args, "--mutable-exclude")
    if not include and not exclude:
        return None
    patterns = include + exclude
    if any(not pattern or "\0" in pattern or "\n" in pattern for pattern in patterns):
        raise AlabError("CONFIG_INVALID", "mutable patterns must be non-empty single-line values")
    return {"include": include or ["**"], "exclude": exclude}


def _experiment_visibility_override(args: list[str]) -> dict[str, Any] | None:
    require_options_at_most_once(args, ("--visibility-scope",))
    raw_scope = command_arg(args, "--visibility-scope")
    visible_exp_ids = command_args(args, "--visible-exp")
    if raw_scope is None:
        if visible_exp_ids:
            raise AlabError("CONFIG_INVALID", "--visible-exp requires --visibility-scope explicit")
        return None
    scope = _require_option_choice(raw_scope, "--visibility-scope", VISIBILITY_SCOPES)
    if scope != "explicit" and visible_exp_ids:
        raise AlabError("CONFIG_INVALID", "--visible-exp is only valid with --visibility-scope explicit")
    if scope == "explicit" and not visible_exp_ids:
        raise AlabError("CONFIG_INVALID", "--visibility-scope explicit requires --visible-exp")
    ids = [
        _complete_id_or_missing(exp_id, prefix="exp", code="EXPERIMENT_NOT_FOUND", label="visible experiment id")
        for exp_id in visible_exp_ids
    ]
    return {"schema_version": 1, "scope": scope, "experiment_ids": sorted(set(ids))}


def _source_origin_options(args: list[str], *, include_ref: bool = False) -> list[str]:
    origin_options = ("--source-path", "--source-git", "--source-empty")
    if include_ref:
        origin_options = (*origin_options, "--source-ref")
    require_options_at_most_once(args, origin_options)
    _assert_source_option_scope(args)
    selected: list[str] = []
    for option in ("--source-path", "--source-git"):
        selected.extend([option] * option_count(args, option))
    selected.extend(["--source-empty"] * option_count(args, "--source-empty"))
    if include_ref:
        selected.extend(["--source-ref"] * option_count(args, "--source-ref"))
    return selected


def _assert_source_option_scope(args: list[str]) -> None:
    require_options_at_most_once(args, ("--git-ref", "--source-subdir"))
    if command_arg(args, "--git-ref") is not None and command_arg(args, "--source-git") is None:
        raise AlabError("SOURCE_INVALID", "--git-ref requires --source-git")
    if command_arg(args, "--source-subdir") is None:
        return
    if flag(args, "--source-empty"):
        raise AlabError("SOURCE_INVALID", "--source-subdir conflicts with --source-empty")
    if command_arg(args, "--source-path") is None and command_arg(args, "--source-git") is None:
        raise AlabError("SOURCE_INVALID", "--source-subdir requires --source-path or --source-git")


def _source_origin_record(origin_type: str, safe_summary: str, exact: dict[str, Any] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "origin_id": new_id("origin", origin_type),
        "origin_type": origin_type,
        "safe_summary": safe_summary,
        "exact": exact or {},
        "warnings": warnings or [],
    }


def _git_no_prompt_env() -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    return env


def _public_git_credential_warnings(public_caller: bool) -> list[str]:
    if not public_caller:
        return []
    result = run_cmd(["git", "config", "--get-all", "credential.helper"], env=_git_no_prompt_env(), check=False)
    if result.returncode != 0:
        return []
    helpers = [line.strip() for line in result.stdout.decode("utf-8", errors="replace").splitlines()]
    return ["PUBLIC_GIT_CREDENTIAL_HELPER_USED"] if any(helpers) else []


def _merge_warnings(*groups: list[str]) -> list[str]:
    warnings: list[str] = []
    for group in groups:
        for warning in group:
            if warning not in warnings:
                warnings.append(warning)
    return warnings


def _artifact_capture_warning_codes(artifacts: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    if any(artifact.get("status") == "error" for artifact in artifacts):
        warnings.append("ARTIFACT_CAPTURE_ERROR")
    return warnings


def _copy_source_origin(
    args: list[str],
    origin: str,
    workdir: Path,
    source_dir_name: str,
    *,
    public_caller: bool = False,
) -> PreparedSource:
    source_work = workdir / source_dir_name
    if origin == "--source-empty":
        if command_arg(args, "--source-subdir"):
            raise AlabError("SOURCE_INVALID", "--source-subdir conflicts with --source-empty")
        copy_filtered_source(None, source_work, empty=True)
        return PreparedSource("empty", source_work, [_source_origin_record("empty", "empty")])
    if origin == "--source-git":
        url = command_arg(args, "--source-git", required=True)
        clone_dir = workdir / f"{source_dir_name}-git-source"
        git_env = _git_no_prompt_env()
        credential_warnings = _public_git_credential_warnings(public_caller)
        run_cmd(["git", "clone", "--quiet", url, str(clone_dir)], env=git_env)
        git_ref = command_arg(args, "--git-ref")
        if git_ref:
            run_cmd(["git", "checkout", git_ref], cwd=clone_dir, env=git_env)
        resolved_commit = run_cmd(["git", "rev-parse", "HEAD"], cwd=clone_dir, env=git_env).stdout.decode("utf-8", errors="replace").strip()
        source_subdir = command_arg(args, "--source-subdir")
        source_root = clone_dir / source_subdir if source_subdir else clone_dir
        copy_result = copy_filtered_source(source_root, source_work)
        return PreparedSource(
            "git",
            source_work,
            [
                _source_origin_record(
                    "git",
                    "git",
                    {"git_ref": git_ref or "HEAD", "resolved_commit": resolved_commit, "source_subdir": source_subdir},
                    _merge_warnings(copy_result.warnings, credential_warnings),
                )
            ],
        )
    if origin == "--source-path":
        path = Path(command_arg(args, "--source-path", required=True))
        source_subdir = command_arg(args, "--source-subdir")
        source_root = path / source_subdir if source_subdir else path
        copy_result = copy_filtered_source(source_root, source_work)
        return PreparedSource(
            "local",
            source_work,
            [_source_origin_record("local", "local", {"source_subdir": source_subdir}, copy_result.warnings)],
        )
    raise AlabError("SOURCE_INVALID", "exactly one source origin is required")


def _copy_adapter_derived_source(derived: AdapterDerivedSource, workdir: Path, source_dir_name: str) -> PreparedSource:
    source_work = workdir / source_dir_name
    copy_result = copy_filtered_source(derived.source_path, source_work, empty=derived.empty)
    return PreparedSource(
        derived.origin_type,
        source_work,
        [_source_origin_record(derived.origin_type, derived.safe_summary, derived.exact, copy_result.warnings)],
    )


def _prepare_source_work(
    args: list[str],
    mode: str,
    workdir: Path,
    derived_source: AdapterDerivedSource | None = None,
    *,
    public_caller: bool = False,
) -> PreparedSource:
    explicit_origins = _source_origin_options(args)
    all_origins = _source_origin_options(args, include_ref=True)
    if len(all_origins) > 1:
        raise AlabError("SOURCE_INVALID", "exactly one source origin is allowed")
    if mode == "local":
        if explicit_origins != ["--source-path"]:
            raise AlabError("SOURCE_INVALID", "project init local requires --source-path")
        return _copy_source_origin(args, "--source-path", workdir, "source", public_caller=public_caller)
    if mode == "git":
        if explicit_origins != ["--source-git"]:
            raise AlabError("SOURCE_INVALID", "project init git requires --source-git")
        return _copy_source_origin(args, "--source-git", workdir, "source", public_caller=public_caller)
    if mode == "empty":
        if command_arg(args, "--source-subdir"):
            raise AlabError("SOURCE_INVALID", "--source-subdir conflicts with --source-empty")
        if explicit_origins != ["--source-empty"]:
            raise AlabError("SOURCE_INVALID", "project init empty requires --source-empty")
        return _copy_source_origin(args, "--source-empty", workdir, "source", public_caller=public_caller)
    if mode not in {"harbor", "skydiscover"}:
        raise AlabError("SOURCE_INVALID", "exactly one source origin is required")
    if command_arg(args, "--source-ref"):
        raise AlabError("SOURCE_INVALID", "adapter project init does not accept --source-ref")
    if len(explicit_origins) > 1:
        raise AlabError("SOURCE_INVALID", "exactly one explicit source origin is allowed")
    if explicit_origins:
        explicit = _copy_source_origin(args, explicit_origins[0], workdir, "source-explicit", public_caller=public_caller)
        if derived_source is not None:
            derived = _copy_adapter_derived_source(derived_source, workdir, "source-derived")
            if canonical_tree_hash(explicit.source_work) != canonical_tree_hash(derived.source_work):
                raise AlabError("SOURCE_INVALID", "explicit source content conflicts with adapter-derived source")
            explicit.origin_records.extend(derived.origin_records)
        final_source = workdir / "source"
        shutil.move(str(explicit.source_work), final_source)
        explicit.source_work = final_source
        return explicit
    if derived_source is not None:
        return _copy_adapter_derived_source(derived_source, workdir, "source")
    if mode == "harbor":
        copy_filtered_source(None, workdir / "source", empty=True)
        return PreparedSource("empty", workdir / "source", [_source_origin_record("empty", "harbor empty source fallback")])
    raise AlabError("SOURCE_INVALID", "SkyDiscover benchmark has no initial program; provide --source-path, --source-git, or --source-empty")


def _parse_source_limit_arg(args: list[str], option: str, default: int) -> int:
    raw = command_arg(args, option)
    if raw is None:
        return default
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", f"{option} must be an integer") from exc
    if value < 0:
        raise AlabError("CONFIG_INVALID", f"{option} must be non-negative")
    return value


def _source_import_limits(args: list[str], *, public_config: Any | None = None, public_caller: bool = False) -> SourceImportLimits:
    require_options_at_most_once(args, ("--max-files", "--max-total-bytes", "--max-file-bytes"))
    base = (
        SourceImportLimits(
            max_files=public_config.max_files,
            max_total_bytes=public_config.max_total_bytes,
            max_file_bytes=public_config.max_file_bytes,
        )
        if public_config is not None
        else DEFAULT_SOURCE_IMPORT_LIMITS
    )
    limits = SourceImportLimits(
        max_files=_parse_source_limit_arg(args, "--max-files", base.max_files),
        max_total_bytes=_parse_source_limit_arg(args, "--max-total-bytes", base.max_total_bytes),
        max_file_bytes=_parse_source_limit_arg(args, "--max-file-bytes", base.max_file_bytes),
    )
    if public_caller and (
        limits.max_files > base.max_files
        or limits.max_total_bytes > base.max_total_bytes
        or limits.max_file_bytes > base.max_file_bytes
    ):
        raise AlabError("CONFIG_INVALID", "public inline source import limits cannot exceed project policy")
    return limits


def _enforce_source_import_limits(source_work: Path, limits: SourceImportLimits) -> None:
    file_count = 0
    total_bytes = 0
    for root, _dirs, files in os.walk(source_work):
        root_path = Path(root)
        for file_name in files:
            file_count += 1
            file_path = root_path / file_name
            if file_path.is_symlink():
                size = len(os.readlink(file_path).encode("utf-8"))
            else:
                size = file_path.stat().st_size
            if file_count > limits.max_files:
                raise AlabError("SOURCE_LIMIT_EXCEEDED", f"source import exceeds max files: {limits.max_files}")
            if size > limits.max_file_bytes:
                rel = file_path.relative_to(source_work).as_posix()
                raise AlabError("SOURCE_LIMIT_EXCEEDED", f"source file exceeds max bytes: {rel}")
            total_bytes += size
            if total_bytes > limits.max_total_bytes:
                raise AlabError("SOURCE_LIMIT_EXCEEDED", f"source import exceeds max total bytes: {limits.max_total_bytes}")


def _source_origin_with_time(record: dict[str, Any], now: str, warnings: list[str] | None = None) -> dict[str, Any]:
    stored = dict(record)
    stored["warnings"] = list(warnings if warnings is not None else stored.get("warnings", []))
    stored["created_at"] = now
    return stored


def _source_origin_entry_obj(value: dict[str, Any], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AlabError("STORAGE_ERROR", f"{label} must be a JSON object")
    allowed_keys = {"origin_id", "origin_type", "safe_summary", "exact", "warnings", "created_at"}
    required_keys = allowed_keys
    unknown = sorted(set(value) - allowed_keys)
    missing = sorted(required_keys - set(value))
    if missing:
        raise AlabError("STORAGE_ERROR", f"{label} missing JSON keys: {', '.join(missing)}")
    if unknown:
        raise AlabError("STORAGE_ERROR", f"{label} contains unknown JSON keys: {', '.join(unknown)}")
    origin = dict(value)
    if not isinstance(origin["origin_id"], str):
        raise AlabError("STORAGE_ERROR", f"{label} origin_id must be a string")
    try:
        require_complete_id(origin["origin_id"], "origin")
    except AlabError as exc:
        raise AlabError("STORAGE_ERROR", f"{label} origin_id must be a complete origin id") from exc
    if not isinstance(origin["origin_type"], str):
        raise AlabError("STORAGE_ERROR", f"{label} origin_type must be a string")
    if origin["origin_type"] not in SOURCE_ORIGIN_TYPES:
        raise AlabError("STORAGE_ERROR", f"{label} origin_type is invalid")
    if not isinstance(origin["safe_summary"], str):
        raise AlabError("STORAGE_ERROR", f"{label} safe_summary must be a string")
    if not isinstance(origin["exact"], dict):
        raise AlabError("STORAGE_ERROR", f"{label} exact must be a JSON object")
    if not isinstance(origin["warnings"], list) or not all(isinstance(warning, str) for warning in origin["warnings"]):
        raise AlabError("STORAGE_ERROR", f"{label} warnings must be a string array")
    if not isinstance(origin["created_at"], str):
        raise AlabError("STORAGE_ERROR", f"{label} created_at must be a string")
    try:
        parse_rfc3339_utc(origin["created_at"])
    except AlabError as exc:
        raise AlabError("STORAGE_ERROR", f"{label} created_at must be RFC 3339") from exc
    return origin


def source_origin_metadata_obj(text: str) -> dict[str, Any]:
    metadata = contract_json_obj(
        text,
        label="sources.origin_metadata_json",
        allowed_keys={"schema_version", "tree_hash_algorithm", "primary_origin", "origins"},
        required_keys={"tree_hash_algorithm", "primary_origin", "origins"},
    )
    if metadata["tree_hash_algorithm"] != "alab-tree-sha256-v1":
        raise AlabError("STORAGE_ERROR", "sources.origin_metadata_json tree_hash_algorithm is invalid")
    primary_origin = _source_origin_entry_obj(metadata["primary_origin"], label="sources.origin_metadata_json.primary_origin")
    origins_value = metadata["origins"]
    if not isinstance(origins_value, list) or not origins_value:
        raise AlabError("STORAGE_ERROR", "sources.origin_metadata_json origins must be a non-empty array")
    origins = [
        _source_origin_entry_obj(origin, label=f"sources.origin_metadata_json.origins[{index}]")
        for index, origin in enumerate(origins_value)
    ]
    if origins[0] != primary_origin:
        raise AlabError("STORAGE_ERROR", "sources.origin_metadata_json primary_origin must match origins[0]")
    return {**metadata, "primary_origin": primary_origin, "origins": origins}


def _experiment_creation_origin_obj(value: dict[str, Any], *, label: str = "experiments.metadata_json.creation_origin") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AlabError("STORAGE_ERROR", f"{label} must be a JSON object")
    kind = value.get("kind")
    if kind == "source":
        allowed_keys = {"kind", "source_id"}
        required_keys = allowed_keys
    elif kind == "inline_source":
        allowed_keys = {"kind", "source_id", "source_ref"}
        required_keys = allowed_keys
    elif kind == "from_exp":
        allowed_keys = {"kind", "source_exp_id", "from_commit", "resolved_commit", "source_id"}
        required_keys = allowed_keys
    else:
        raise AlabError("STORAGE_ERROR", f"{label} kind is invalid")
    unknown = sorted(set(value) - allowed_keys)
    missing = sorted(required_keys - set(value))
    if missing:
        raise AlabError("STORAGE_ERROR", f"{label} missing JSON keys: {', '.join(missing)}")
    if unknown:
        raise AlabError("STORAGE_ERROR", f"{label} contains unknown JSON keys: {', '.join(unknown)}")
    origin = dict(value)
    try:
        require_complete_id(origin["source_id"], "src")
        if kind == "from_exp":
            require_complete_id(origin["source_exp_id"], "exp")
    except AlabError as exc:
        raise AlabError("STORAGE_ERROR", f"{label} contains invalid object id") from exc
    for key in ("source_ref", "from_commit", "resolved_commit"):
        if key in origin and (not isinstance(origin[key], str) or not origin[key]):
            raise AlabError("STORAGE_ERROR", f"{label} {key} must be a non-empty string")
    return origin


def experiment_metadata_obj(text: str) -> dict[str, Any]:
    metadata = contract_json_obj(
        text,
        label="experiments.metadata_json",
        allowed_keys={"schema_version", "name", "name_slug", "goal", "creation_origin", "requested_path", "source_selector", "display"},
        required_keys={"name", "name_slug", "goal", "creation_origin", "requested_path", "source_selector", "display"},
    )
    for key in ("name", "name_slug", "requested_path", "source_selector"):
        if not isinstance(metadata[key], str) or not metadata[key]:
            raise AlabError("STORAGE_ERROR", f"experiments.metadata_json {key} must be a non-empty string")
    if not isinstance(metadata["goal"], (str, type(None))):
        raise AlabError("STORAGE_ERROR", "experiments.metadata_json goal must be a string or null")
    creation_origin = _experiment_creation_origin_obj(metadata["creation_origin"])
    display = metadata["display"]
    if not isinstance(display, dict):
        raise AlabError("STORAGE_ERROR", "experiments.metadata_json display must be a JSON object")
    display_unknown = sorted(set(display) - {"safe_summary"})
    if display_unknown:
        raise AlabError("STORAGE_ERROR", f"experiments.metadata_json display contains unknown JSON keys: {', '.join(display_unknown)}")
    if not isinstance(display.get("safe_summary"), str):
        raise AlabError("STORAGE_ERROR", "experiments.metadata_json display.safe_summary must be a string")
    return {**metadata, "creation_origin": creation_origin, "display": dict(display)}


def _experiment_mutable_policy_obj(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AlabError("STORAGE_ERROR", f"{label} must be a JSON object")
    allowed_keys = {"include", "exclude"}
    unknown = sorted(set(value) - allowed_keys)
    missing = sorted(allowed_keys - set(value))
    if missing:
        raise AlabError("STORAGE_ERROR", f"{label} missing JSON keys: {', '.join(missing)}")
    if unknown:
        raise AlabError("STORAGE_ERROR", f"{label} contains unknown JSON keys: {', '.join(unknown)}")
    result: dict[str, Any] = {}
    for key in ("include", "exclude"):
        items = value[key]
        if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
            raise AlabError("STORAGE_ERROR", f"{label}.{key} must be a string array")
        if key == "include" and not items:
            raise AlabError("STORAGE_ERROR", f"{label}.include must contain at least one pattern")
        if any(not item or "\n" in item or "\0" in item for item in items):
            raise AlabError("STORAGE_ERROR", f"{label}.{key} patterns must be non-empty single-line values")
        result[key] = list(items)
    return result


def _experiment_visibility_policy_obj(value: Any, *, label: str = "experiments.policy_json.visibility_upper_bound") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AlabError("STORAGE_ERROR", f"{label} must be a JSON object")
    allowed_keys = {"schema_version", "scope", "experiment_ids"}
    unknown = sorted(set(value) - allowed_keys)
    missing = sorted({"scope", "experiment_ids"} - set(value))
    if missing:
        raise AlabError("STORAGE_ERROR", f"{label} missing JSON keys: {', '.join(missing)}")
    if unknown:
        raise AlabError("STORAGE_ERROR", f"{label} contains unknown JSON keys: {', '.join(unknown)}")
    if "schema_version" in value and (isinstance(value["schema_version"], bool) or value["schema_version"] != 1):
        raise AlabError("STORAGE_ERROR", f"{label} schema_version must be 1")
    scope = value["scope"]
    if scope not in VISIBILITY_SCOPES:
        raise AlabError("STORAGE_ERROR", f"{label}.scope is invalid")
    experiment_ids = value["experiment_ids"]
    if not isinstance(experiment_ids, list) or not all(isinstance(exp_id, str) for exp_id in experiment_ids):
        raise AlabError("STORAGE_ERROR", f"{label}.experiment_ids must be a string array")
    if scope == "explicit" and not experiment_ids:
        raise AlabError("STORAGE_ERROR", f"{label}.experiment_ids is required for explicit scope")
    if scope != "explicit" and experiment_ids:
        raise AlabError("STORAGE_ERROR", f"{label}.experiment_ids is only valid for explicit scope")
    for exp_id in experiment_ids:
        try:
            require_complete_id(exp_id, "exp")
        except AlabError as exc:
            raise AlabError("STORAGE_ERROR", f"{label}.experiment_ids entries must be complete experiment ids") from exc
    result = dict(value)
    result["experiment_ids"] = sorted(set(experiment_ids))
    return result


def experiment_policy_json_obj(text: str) -> dict[str, Any]:
    policy = contract_json_obj(
        text,
        label="experiments.policy_json",
        allowed_keys={"schema_version", "mutable", "mutable_override", "visibility_upper_bound"},
        required_keys={"mutable", "visibility_upper_bound"},
    )
    result = {
        **policy,
        "mutable": _experiment_mutable_policy_obj(policy["mutable"], label="experiments.policy_json.mutable"),
        "visibility_upper_bound": _experiment_visibility_policy_obj(policy["visibility_upper_bound"]),
    }
    if "mutable_override" in policy:
        result["mutable_override"] = _experiment_mutable_policy_obj(
            policy["mutable_override"],
            label="experiments.policy_json.mutable_override",
        )
    return result


def _execution_record_nested_obj(value: Any, *, label: str, allowed_keys: set[str], required_keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AlabError("STORAGE_ERROR", f"{label} must be a JSON object")
    unknown = sorted(set(value) - allowed_keys)
    missing = sorted(required_keys - set(value))
    if missing:
        raise AlabError("STORAGE_ERROR", f"{label} missing JSON keys: {', '.join(missing)}")
    if unknown:
        raise AlabError("STORAGE_ERROR", f"{label} contains unknown JSON keys: {', '.join(unknown)}")
    return dict(value)


def _execution_record_metric_map(value: Any, *, label: str) -> dict[str, int | float]:
    if not isinstance(value, dict):
        raise AlabError("STORAGE_ERROR", f"{label} must be a JSON object")
    metrics: dict[str, int | float] = {}
    for key, metric in value.items():
        if not isinstance(key, str) or not isinstance(metric, (int, float)) or isinstance(metric, bool) or not math.isfinite(float(metric)):
            raise AlabError("STORAGE_ERROR", f"{label} must be a string-to-finite-number map")
        metrics[key] = metric
    return metrics


def execution_record_json_obj(text: str) -> dict[str, Any]:
    record = contract_json_obj(
        text,
        label="execution.record_json",
        allowed_keys={
            "schema_version",
            "config_hash",
            "runner",
            "reward",
            "metrics",
            "warnings",
            "failure",
            "artifacts",
            "logs",
            "timeout",
            "adapter_feedback",
            "interrupted",
            "mutable_scope",
        },
        required_keys={
            "config_hash",
            "runner",
            "reward",
            "metrics",
            "warnings",
            "failure",
            "artifacts",
            "logs",
            "timeout",
            "adapter_feedback",
        },
    )
    if not isinstance(record["config_hash"], str) or not record["config_hash"]:
        raise AlabError("STORAGE_ERROR", "execution.record_json config_hash must be a non-empty string")
    runner = _execution_record_nested_obj(
        record["runner"],
        label="execution.record_json.runner",
        allowed_keys={"type", "safe_summary"},
        required_keys={"type"},
    )
    if not isinstance(runner["type"], str) or not runner["type"]:
        raise AlabError("STORAGE_ERROR", "execution.record_json.runner.type must be a non-empty string")
    if "safe_summary" in runner and not isinstance(runner["safe_summary"], str):
        raise AlabError("STORAGE_ERROR", "execution.record_json.runner.safe_summary must be a string")
    reward = _execution_record_nested_obj(
        record["reward"],
        label="execution.record_json.reward",
        allowed_keys={"type", "value"},
        required_keys={"type", "value"},
    )
    if not isinstance(reward["type"], str) or not reward["type"]:
        raise AlabError("STORAGE_ERROR", "execution.record_json.reward.type must be a non-empty string")
    reward_value = reward["value"]
    if reward_value is not None and (not isinstance(reward_value, (int, float)) or isinstance(reward_value, bool) or not math.isfinite(float(reward_value))):
        raise AlabError("STORAGE_ERROR", "execution.record_json.reward.value must be a finite number or null")
    metrics = _execution_record_metric_map(record["metrics"], label="execution.record_json.metrics")
    warnings = record["warnings"]
    if not isinstance(warnings, list) or not all(isinstance(warning, str) for warning in warnings):
        raise AlabError("STORAGE_ERROR", "execution.record_json warnings must be a string array")
    if not isinstance(record["failure"], (str, type(None))):
        raise AlabError("STORAGE_ERROR", "execution.record_json failure must be a string or null")
    for key in ("artifacts", "logs", "adapter_feedback"):
        if not isinstance(record[key], dict):
            raise AlabError("STORAGE_ERROR", f"execution.record_json {key} must be a JSON object")
    if not isinstance(record["timeout"], bool):
        raise AlabError("STORAGE_ERROR", "execution.record_json timeout must be a boolean")
    interrupted = record.get("interrupted")
    if interrupted is not None and not isinstance(interrupted, bool):
        raise AlabError("STORAGE_ERROR", "execution.record_json interrupted must be a boolean")
    mutable_scope = record.get("mutable_scope")
    if mutable_scope is not None:
        mutable_scope = _execution_record_nested_obj(
            mutable_scope,
            label="execution.record_json.mutable_scope",
            allowed_keys={"schema_version", "error_code", "violation_paths", "rolled_back_commit"},
            required_keys={"error_code", "violation_paths", "rolled_back_commit"},
        )
        if isinstance(mutable_scope.get("schema_version", 1), bool) or mutable_scope.get("schema_version", 1) != 1:
            raise AlabError("STORAGE_ERROR", "execution.record_json.mutable_scope schema_version must be 1")
        if mutable_scope["error_code"] != "SCOPE_VIOLATION":
            raise AlabError("STORAGE_ERROR", "execution.record_json.mutable_scope error_code is invalid")
        if not isinstance(mutable_scope["violation_paths"], list) or not all(isinstance(path, str) for path in mutable_scope["violation_paths"]):
            raise AlabError("STORAGE_ERROR", "execution.record_json.mutable_scope violation_paths must be a string array")
        if not isinstance(mutable_scope["rolled_back_commit"], (str, type(None))):
            raise AlabError("STORAGE_ERROR", "execution.record_json.mutable_scope rolled_back_commit must be a string or null")
    result = {**record, "runner": runner, "reward": reward, "metrics": metrics}
    if mutable_scope is not None:
        result["mutable_scope"] = mutable_scope
    return result


def submission_refs_json_obj(text: str) -> dict[str, Any]:
    refs_json = contract_json_obj(
        text,
        label="experiment_submissions.refs_json",
        allowed_keys={"schema_version", "refs"},
        required_keys={"refs"},
    )
    refs = refs_json["refs"]
    if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
        raise AlabError("STORAGE_ERROR", "experiment_submissions.refs_json refs must be a non-empty string array")
    if "none" in refs:
        if refs != ["none"]:
            raise AlabError("STORAGE_ERROR", "experiment_submissions.refs_json ref none must be the only ref")
    else:
        seen: set[str] = set()
        for ref in refs:
            if ref in seen:
                raise AlabError("STORAGE_ERROR", "experiment_submissions.refs_json refs must be deduplicated")
            seen.add(ref)
            try:
                require_complete_id(ref, "exp")
            except AlabError as exc:
                raise AlabError("STORAGE_ERROR", "experiment_submissions.refs_json refs must be complete experiment ids or none") from exc
    return {**refs_json, "refs": list(refs)}


def _source_warning_codes(prepared_source: PreparedSource) -> list[str]:
    warnings: list[str] = []
    for record in prepared_source.origin_records:
        for warning in record.get("warnings", []):
            if warning not in warnings:
                warnings.append(warning)
    return warnings


def _utc_after_ms(milliseconds: int) -> str:
    return (datetime.now(UTC) + timedelta(milliseconds=milliseconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _lock_stale_after_ms(home: Home) -> int:
    value = load_global_config(home.config_path).get("locks", {}).get("stale_after_ms", 120000)
    return int(value)


def _acquire_experiment_run_submit_lock(home: Home, *, project_id: str, exp_id: str) -> ExperimentOperationLock:
    lock_name = f"experiment-run-submit:{exp_id}"
    owner_operation_id = new_id("op", "run-submit")
    now = utc_now()
    expires_at = _utc_after_ms(_lock_stale_after_ms(home))
    with Database(home).tx() as conn:
        conn.execute("DELETE FROM locks WHERE lock_name = ? AND expires_at < ?", (lock_name, now))
        if one(conn, "SELECT lock_name FROM locks WHERE lock_name = ?", (lock_name,)):
            raise AlabError("EXPERIMENT_BUSY", "experiment has an active run or submit lock", "wait for the active run or submit to finish")
        try:
            conn.execute(
                """
                INSERT INTO locks(lock_name, owner_operation_id, owner_host, owner_pid, project_id, exp_id,
                  acquired_at, heartbeat_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (lock_name, owner_operation_id, socket.gethostname(), os.getpid(), project_id, exp_id, now, now, expires_at),
            )
        except sqlite3.IntegrityError as exc:
            raise AlabError("EXPERIMENT_BUSY", "experiment has an active run or submit lock", "wait for the active run or submit to finish") from exc
    return ExperimentOperationLock(lock_name=lock_name, owner_operation_id=owner_operation_id)


def _release_experiment_run_submit_lock(home: Home, lock: ExperimentOperationLock) -> None:
    try:
        with Database(home).tx() as conn:
            conn.execute("DELETE FROM locks WHERE lock_name = ? AND owner_operation_id = ?", (lock.lock_name, lock.owner_operation_id))
    except Exception:
        pass


def _git_commit_identity_env(author_name: str, author_email: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
        }
    )
    return env


def _unique_source_name(conn, project_id: str, desired_name: str, source_id: str, *, allow_suffix: bool) -> tuple[str, str]:
    name_slug = slugify(desired_name, "source")
    if one(conn, "SELECT source_id FROM sources WHERE project_id = ? AND name_slug = ?", (project_id, name_slug)) is None:
        return desired_name, name_slug
    if not allow_suffix:
        raise AlabError("NAME_CONFLICT", "source name already exists")
    suffix = source_id.rsplit("-", 1)[-1][:8]
    suffixed = f"{desired_name}-{suffix}"
    suffixed_slug = slugify(suffixed, "source")
    if one(conn, "SELECT source_id FROM sources WHERE project_id = ? AND name_slug = ?", (project_id, suffixed_slug)) is not None:
        raise AlabError("NAME_CONFLICT", "source name already exists")
    return suffixed, suffixed_slug


def _import_prepared_source_snapshot(
    *,
    home: Home,
    project_id: str,
    repo_git: Path,
    cfg: ProjectConfig,
    actor: Actor | None,
    prepared_source: PreparedSource,
    source_name: str,
    limits: SourceImportLimits,
    allow_name_suffix: bool = False,
    warn_on_name_mismatch: bool = False,
) -> SourceImportResult:
    _assert_display_name("source name", source_name)
    _enforce_source_import_limits(prepared_source.source_work, limits)
    tree_hash = canonical_tree_hash(prepared_source.source_work)
    source_warnings = _source_warning_codes(prepared_source)
    conn = require_home(home)
    try:
        existing = one(conn, "SELECT * FROM sources WHERE project_id = ? AND tree_hash = ? AND status = 'active'", (project_id, tree_hash))
        if existing:
            now = utc_now()
            meta = source_origin_metadata_obj(existing["origin_metadata_json"])
            warnings = list(source_warnings)
            if warn_on_name_mismatch and source_name and source_name != existing["name"] and "SOURCE_DEDUPED_NAME_IGNORED" not in warnings:
                warnings.append("SOURCE_DEDUPED_NAME_IGNORED")
            meta.setdefault("origins", []).extend(_source_origin_with_time(record, now, warnings) for record in prepared_source.origin_records)
            with Database(home).tx() as tx:
                tx.execute(
                    "UPDATE sources SET origin_metadata_json = ? WHERE source_id = ?",
                    (canonical_json(source_origin_metadata_obj(canonical_json(meta))), existing["source_id"]),
                )
            return SourceImportResult(
                source_id=existing["source_id"],
                source_ref=existing["source_ref"],
                name=existing["name"],
                source_commit=existing["source_commit"],
                tree_hash=existing["tree_hash"],
                deduped=True,
                warnings=warnings,
            )
        source_id = new_id("src", source_name)
        name, name_slug = _unique_source_name(conn, project_id, source_name, source_id, allow_suffix=allow_name_suffix)
    finally:
        conn.close()
    source_ref = f"alab/source/{source_id}"
    if not repo_git.exists():
        raise AlabError("PROJECT_INVALID", "project repository is missing")
    source_commit = init_snapshot_repo(prepared_source.source_work, author_name=cfg.git.author_name, author_email=cfg.git.author_email, message=f"ALab source: {source_id}")
    reject_gitlinks(prepared_source.source_work)
    run_cmd(["git", "remote", "add", "alab-project", str(repo_git)], cwd=prepared_source.source_work)
    run_cmd(["git", "push", "alab-project", f"HEAD:refs/heads/alab/source/{source_id}"], cwd=prepared_source.source_work)
    now = utc_now()
    with Database(home).tx() as tx:
        tx.execute(
            """
            INSERT INTO sources(source_id, project_id, name, name_slug, source_ref, source_commit, tree_hash,
              status, origin_metadata_json, created_at, archived_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, NULL)
            """,
            (
                source_id,
                project_id,
                name,
                name_slug,
                source_ref,
                source_commit,
                tree_hash,
                canonical_json(
                    source_origin_metadata_obj(
                        canonical_json(
                            {
                                "schema_version": 1,
                                "tree_hash_algorithm": "alab-tree-sha256-v1",
                                "primary_origin": _source_origin_with_time(prepared_source.origin_records[0], now),
                                "origins": [_source_origin_with_time(record, now) for record in prepared_source.origin_records],
                            }
                        )
                    )
                ),
                now,
            ),
        )
        audit(tx, action="add", object_type="source", object_id=source_id, actor=actor, project_id=project_id)
    return SourceImportResult(
        source_id=source_id,
        source_ref=source_ref,
        name=name,
        source_commit=source_commit,
        tree_hash=tree_hash,
        deduped=False,
        warnings=source_warnings,
    )


def _secret_fingerprint(key: bytes, name: str, value: str) -> str:
    digest = hmac.new(key, name.encode("utf-8") + b"\0" + value.encode("utf-8"), hashlib.sha256).hexdigest()
    return "hmac-sha256:" + digest


def _store_secret_values(
    conn,
    project_id: str,
    fingerprint_key: bytes,
    config: ProjectConfig,
    actor: Actor | None,
    base_secret_markers: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    config_json = config.canonical_dict()
    raw_secrets: dict[str, str] = {}
    stored: dict[str, Any] = {}
    base_secret_markers = base_secret_markers or {}
    for name, value in config.secret_env.items():
        if isinstance(value, dict) and (value.get("retain") or value.get("secret_value_id")):
            marker = base_secret_markers.get(name)
            if marker is None and value.get("secret_value_id"):
                marker = value
            if not isinstance(marker, dict) or not marker.get("secret_value_id"):
                raise AlabError("CONFIG_INVALID", f"secret_env.{name} retain marker has no previous secret value")
            if value.get("fingerprint") and marker.get("fingerprint") and value["fingerprint"] != marker["fingerprint"]:
                raise AlabError("CONFIG_INVALID", f"secret_env.{name} retain marker fingerprint does not match")
            secret_row = one(conn, "SELECT value, fingerprint FROM secret_values WHERE secret_value_id = ? AND project_id = ?", (marker["secret_value_id"], project_id))
            if secret_row is None:
                raise AlabError("CONFIG_INVALID", f"secret_env.{name} retained secret value is missing")
            stored[name] = {"secret_value_id": marker["secret_value_id"], "fingerprint": marker.get("fingerprint") or secret_row["fingerprint"]}
            raw_secrets[name] = secret_row["value"]
            continue
        if not isinstance(value, str) or "\n" in value or "\0" in value or len(value.encode("utf-8")) < 4:
            raise AlabError("CONFIG_INVALID", "secret_env values must be single-line UTF-8 strings at least 4 bytes")
        secret_value_id = new_id("sec", name)
        fingerprint = _secret_fingerprint(fingerprint_key, name, value)
        conn.execute(
            """
            INSERT INTO secret_values(secret_value_id, project_id, name, value, fingerprint, created_at, created_by_credential_id, replaced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (secret_value_id, project_id, name, value, fingerprint, utc_now(), actor.credential_id if actor else None),
        )
        stored[name] = {"secret_value_id": secret_value_id, "fingerprint": fingerprint}
        raw_secrets[name] = value
    config_json["secret_env"] = stored
    return config_json, raw_secrets


def _load_config_and_secrets(conn, project_id: str, version: int) -> tuple[ProjectConfig, dict[str, str], dict[str, Any]]:
    row = one(
        conn,
        "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?",
        (project_id, version),
    )
    if row is None:
        raise AlabError("PROJECT_INVALID", "config version not found")
    config_json = project_config_json_obj(row["canonical_config_json"])
    secret_markers = config_json.get("secret_env", {})
    secrets_map: dict[str, str] = {}
    for name, marker in secret_markers.items():
        if isinstance(marker, dict) and marker.get("secret_value_id"):
            secret_row = one(conn, "SELECT value FROM secret_values WHERE secret_value_id = ?", (marker["secret_value_id"],))
            if secret_row:
                secrets_map[name] = secret_row["value"]
    config_for_model = dict(config_json)
    config_for_model["secret_env"] = {}
    return ProjectConfig.model_validate(config_for_model), secrets_map, config_json


def _config_hash_for_version(conn, project_id: str, version: int) -> str:
    row = one(
        conn,
        "SELECT config_hash FROM project_config_versions WHERE project_id = ? AND version = ?",
        (project_id, version),
    )
    if row is None or not row["config_hash"]:
        raise AlabError("CONFIG_INVALID", "config version not found")
    return row["config_hash"]


def _execution_record_payload(
    *,
    config_hash_value: str,
    runner_type: str,
    reward_type: str,
    reward_value: float | None = None,
    metrics: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    failure: str | None = None,
    artifacts: dict[str, Any] | None = None,
    logs: dict[str, Any] | None = None,
    timeout: bool = False,
    adapter_feedback: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "schema_version": 1,
        "config_hash": config_hash_value,
        "runner": {"type": runner_type},
        "reward": {"type": reward_type, "value": reward_value},
        "metrics": metrics or {},
        "warnings": warnings or [],
        "failure": failure,
        "artifacts": artifacts or {},
        "logs": logs or {},
        "timeout": timeout,
        "adapter_feedback": adapter_feedback or {},
    }
    if extra:
        record.update(extra)
    return record


def _record_defaults_for_version(conn, project_id: str, version: int) -> tuple[str, str, str]:
    row = one(
        conn,
        "SELECT canonical_config_json, config_hash FROM project_config_versions WHERE project_id = ? AND version = ?",
        (project_id, version),
    )
    if row is None:
        return "unknown", "unknown", "unknown"
    config_json = project_config_json_obj(row["canonical_config_json"])
    return (
        row["config_hash"] or "unknown",
        str((config_json.get("runner") or {}).get("type") or "unknown"),
        str((config_json.get("reward") or {}).get("type") or "unknown"),
    )


def _execution_record_object_json(
    *,
    config_hash_value: str,
    runner_type: str,
    reward_type: str,
    reward_value: float | None = None,
    metrics: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    failure: str | None = None,
    artifacts: dict[str, Any] | None = None,
    logs: dict[str, Any] | None = None,
    timeout: bool = False,
    adapter_feedback: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    return canonical_json(
        execution_record_json_obj(
            canonical_json(
                _execution_record_payload(
                    config_hash_value=config_hash_value,
                    runner_type=runner_type,
                    reward_type=reward_type,
                    reward_value=reward_value,
                    metrics=metrics,
                    warnings=warnings,
                    failure=failure,
                    artifacts=artifacts,
                    logs=logs,
                    timeout=timeout,
                    adapter_feedback=adapter_feedback,
                    extra=extra,
                )
            )
        )
    )


def _interrupted_record_json(
    text: str,
    *,
    reason: str,
    config_hash_value: str,
    runner_type: str,
    reward_type: str,
) -> str:
    try:
        record = execution_record_json_obj(text)
    except Exception:
        record = _execution_record_payload(
            config_hash_value=config_hash_value,
            runner_type=runner_type,
            reward_type=reward_type,
        )
    record["failure"] = reason
    record["interrupted"] = True
    return canonical_json(execution_record_json_obj(canonical_json(record)))


def _interrupt_stale_running_records(conn, *, project_id: str | None = None, exp_id: str | None = None) -> dict[str, int]:
    now = utc_now()
    run_clauses = ["status = 'running'"]
    run_params: list[Any] = []
    validation_clauses = ["status = 'running'"]
    validation_params: list[Any] = []
    if project_id is not None:
        run_clauses.append("project_id = ?")
        run_params.append(project_id)
        validation_clauses.append("project_id = ?")
        validation_params.append(project_id)
    if exp_id is not None:
        run_clauses.append("exp_id = ?")
        run_params.append(exp_id)
    running_runs = all_rows(conn, f"SELECT run_id, project_id, config_version, record_json FROM runs WHERE {' AND '.join(run_clauses)}", tuple(run_params))
    for row in running_runs:
        config_hash_value, runner_type, reward_type = _record_defaults_for_version(conn, row["project_id"], int(row["config_version"]))
        conn.execute(
            "UPDATE runs SET status = 'interrupted', ended_at = ?, record_json = ? WHERE run_id = ?",
            (
                now,
                _interrupted_record_json(
                    row["record_json"],
                    reason="stale running run interrupted by later ALab operation",
                    config_hash_value=config_hash_value,
                    runner_type=runner_type,
                    reward_type=reward_type,
                ),
                row["run_id"],
            ),
        )
    running_validations = all_rows(
        conn,
        f"SELECT validation_id, project_id, config_version, record_json FROM project_validations WHERE {' AND '.join(validation_clauses)}",
        tuple(validation_params),
    )
    for row in running_validations:
        config_hash_value, runner_type, reward_type = _record_defaults_for_version(conn, row["project_id"], int(row["config_version"]))
        conn.execute(
            "UPDATE project_validations SET status = 'interrupted', ended_at = ?, record_json = ? WHERE validation_id = ?",
            (
                now,
                _interrupted_record_json(
                    row["record_json"],
                    reason="stale running validation interrupted by later ALab operation",
                    config_hash_value=config_hash_value,
                    runner_type=runner_type,
                    reward_type=reward_type,
                ),
                row["validation_id"],
            ),
        )
        conn.execute(
            """
            UPDATE project_config_versions
            SET validation_status = 'interrupted'
            WHERE project_id = ? AND version = ? AND validation_status = 'running'
            """,
            (row["project_id"], row["config_version"]),
        )
        conn.execute(
            """
            UPDATE projects
            SET status = 'invalid', updated_at = ?
            WHERE project_id = ? AND latest_attempted_config_version = ?
            """,
            (now, row["project_id"], row["config_version"]),
        )
    return {"runs": len(running_runs), "validations": len(running_validations)}


def _run_validation(
    conn,
    home: Home,
    project_id: str,
    validation_id: str,
    source_ref: str,
    source_commit: str,
    config_version: int,
    raw_config: ProjectConfig,
    raw_secrets: dict[str, str],
) -> tuple[str, int | None, float | None, str, list[str]]:
    project_root, repo_git, artifact_store = _project_paths(home, project_id)
    operation_dir = home.tmp_path / project_id / validation_id
    workspace = operation_dir / "workspace"
    run_dir = operation_dir / "run"
    hidden_dir = operation_dir / "hidden"
    try:
        clean_copy_from_git(repo_git, source_commit, workspace)
        result = run_configured_runner(
            config=raw_config,
            workspace=workspace,
            run_dir=run_dir,
            operation_id=validation_id,
            secrets=raw_secrets,
            project_id=project_id,
            config_version=config_version,
            hidden_dir=hidden_dir,
            cache_dir=home.cache_path / "skydiscover-python-envs",
            adapter_resolver=lambda ref: _resolve_runner_adapter_ref(conn, ref),
        )
        _record_runner_cache(conn, result, project_id)
        log_base = artifact_store
        preview_limit = _global_preview_bytes(home)
        stdout_rel, stdout_size, stdout_stored, stdout_hash, stdout_preview, stdout_trunc = store_log_file(
            log_base,
            project_id,
            validation_id,
            "stdout",
            result.stdout,
            raw_config.logs.stdout_limit_bytes,
            preview_limit,
        )
        stderr_rel, stderr_size, stderr_stored, stderr_hash, stderr_preview, stderr_trunc = store_log_file(
            log_base,
            project_id,
            validation_id,
            "stderr",
            result.stderr,
            raw_config.logs.stderr_limit_bytes,
            preview_limit,
        )
        artifacts = capture_artifacts(config=raw_config, workspace=workspace, run_dir=run_dir, artifact_store=artifact_store, project_id=project_id, exp_id=None, run_id=None, validation_id=validation_id)
        warning_codes = _merge_warnings(result.warning_codes or [], _artifact_capture_warning_codes(artifacts))
        now = utc_now()
        failure_reason = _runner_failure_reason(result.status, result.exit_code, result.reward_parse_status, result.failure_reason)
        record_json = _execution_record_object_json(
            config_hash_value=_config_hash_for_version(conn, project_id, config_version),
            runner_type=raw_config.runner.type,
            reward_type=raw_config.reward.type,
            reward_value=result.reward,
            metrics=result.metrics,
            warnings=warning_codes,
            failure=failure_reason,
            timeout=result.status == "timeout",
            adapter_feedback=result.adapter_feedback,
        )
        conn.execute(
            """
            UPDATE project_validations
            SET status = ?, exit_code = ?, reward_value = ?, reward_parse_status = ?, ended_at = ?, record_json = ?
            WHERE validation_id = ?
            """,
            (result.status, result.exit_code, result.reward, result.reward_parse_status, now, record_json, validation_id),
        )
        for stream, rel, size, stored, digest, preview, trunc in [
            ("stdout", stdout_rel, stdout_size, stdout_stored, stdout_hash, stdout_preview, stdout_trunc),
            ("stderr", stderr_rel, stderr_size, stderr_stored, stderr_hash, stderr_preview, stderr_trunc),
        ]:
            conn.execute(
                """
                INSERT INTO log_streams(log_id, project_id, exp_id, run_id, validation_id, stream, size_bytes,
                  stored_bytes, content_hash, truncated, hidden, archive_status, file_path, preview_text, created_at)
                VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, 0, 'active', ?, ?, ?)
                """,
                (new_id("log", stream), project_id, validation_id, stream, size, stored, digest, 1 if trunc else 0, rel, preview, now),
            )
        for stream, data, limit in [
            ("hidden_stdout", result.hidden_stdout, raw_config.logs.stdout_limit_bytes),
            ("hidden_stderr", result.hidden_stderr, raw_config.logs.stderr_limit_bytes),
        ]:
            if not data:
                continue
            rel, size, stored, digest, preview, trunc = store_log_file(log_base, project_id, validation_id, stream, data, limit, preview_limit)
            conn.execute(
                """
                INSERT INTO log_streams(log_id, project_id, exp_id, run_id, validation_id, stream, size_bytes,
                  stored_bytes, content_hash, truncated, hidden, archive_status, file_path, preview_text, created_at)
                VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, 1, 'active', ?, ?, ?)
                """,
                (new_id("log", stream), project_id, validation_id, stream, size, stored, digest, 1 if trunc else 0, rel, preview, now),
            )
        for artifact in artifacts:
            conn.execute(
                """
                INSERT INTO artifacts(artifact_id, project_id, exp_id, run_id, validation_id, root, relative_path,
                  size_bytes, content_hash, status, archive_status, blob_path, capture_error, created_at)
                VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    artifact["artifact_id"],
                    project_id,
                    validation_id,
                    artifact["root"],
                    artifact["relative_path"],
                    artifact["size_bytes"],
                    artifact["content_hash"],
                    artifact["status"],
                    artifact["blob_path"],
                    artifact["capture_error"],
                    now,
                ),
            )
        return result.status, result.exit_code, result.reward, result.reward_parse_status, warning_codes
    finally:
        try:
            run_cmd(["git", f"--git-dir={repo_git}", "worktree", "remove", "--force", str(workspace)], check=False)
        except Exception:
            pass
        shutil.rmtree(operation_dir, ignore_errors=True)


def _record_runner_cache(conn, result: Any, project_id: str) -> None:
    metadata = getattr(result, "cache_metadata", None)
    if not metadata:
        return
    cache_kind = metadata.get("cache_kind")
    cache_key = metadata.get("cache_key")
    if not cache_kind or not cache_key:
        return
    now = utc_now()
    row = one(conn, "SELECT cache_id FROM cache_entries WHERE cache_kind = ? AND cache_key = ? AND status = 'active'", (cache_kind, cache_key))
    path_value = metadata.get("path") if cache_kind == "skydiscover_python_env" else None
    docker_tag = metadata.get("docker_tag") if cache_kind == "docker_image" else None
    safe_metadata = {
        "schema_version": 1,
        "safe_summary": " ".join(str(part) for part in (metadata.get("adapter"), cache_kind, metadata.get("status")) if part),
        "inputs_hash": cache_key,
        "warnings": metadata.get("warnings", []),
    }
    metadata_json = canonical_json(cache_metadata_json_obj(canonical_json(safe_metadata)))
    if row:
        conn.execute(
            "UPDATE cache_entries SET project_id = COALESCE(project_id, ?), path = ?, docker_tag = ?, metadata_json = ?, last_used_at = ? WHERE cache_id = ?",
            (project_id, path_value, docker_tag, metadata_json, now, row["cache_id"]),
        )
        return
    conn.execute(
        """
        INSERT INTO cache_entries(cache_id, cache_kind, cache_key, project_id, path, docker_tag,
          size_bytes, status, metadata_json, created_at, last_used_at, removed_at)
        VALUES (?, ?, ?, ?, ?, ?, NULL, 'active', ?, ?, ?, NULL)
        """,
        (new_id("cache", cache_kind), cache_kind, cache_key, project_id, path_value, docker_tag, metadata_json, now, now),
    )


SKYDISCOVER_ORIGIN_URL = "https://github.com/skydiscover-ai/skydiscover.git"


def _catalog_local_path(home: Home) -> Path:
    return home.sources_path / "skydiscover"


def _catalog_git(repo: Path, args: list[str], reason: str):
    try:
        return run_cmd(["git", *args], cwd=repo if repo.exists() else None)
    except AlabError as exc:
        if exc.code == "GIT_ERROR":
            raise AlabError("CONFIG_INVALID", f"{reason}: {exc.reason}") from exc
        raise


def _resolve_catalog_commit(repo: Path, *, ref: str | None, commit: str | None) -> tuple[str, str]:
    if ref and commit:
        raise AlabError("CONFIG_INVALID", "--ref conflicts with --commit")
    commit = _full_commit_sha_filter(commit)
    _catalog_git(repo, ["fetch", "--quiet", "--tags", "origin"], "catalog fetch failed")
    if commit:
        _catalog_git(repo, ["cat-file", "-e", f"{commit}^{{commit}}"], "catalog commit does not exist")
        return commit.lower(), commit
    requested = ref or "main"
    candidates = [f"origin/{requested}", requested]
    for candidate in candidates:
        completed = run_cmd(["git", "rev-parse", "--verify", f"{candidate}^{{commit}}"], cwd=repo, check=False)
        if completed.returncode == 0:
            return completed.stdout.decode("utf-8", errors="replace").strip(), requested
    raise AlabError("CONFIG_INVALID", f"catalog ref does not resolve to a commit: {requested}")


def _active_catalog_row(conn):
    row = one(conn, "SELECT * FROM catalogs WHERE catalog_key = 'skydiscover' AND status = 'active'")
    if row is None:
        raise AlabError("CATALOG_NOT_FOUND", "active SkyDiscover catalog not found", "alab catalog skydiscover add")
    catalog_metadata_json_obj(row["metadata_json"])
    return row


def _skydiscover_ref_path(ref: str) -> PurePosixPath:
    prefix, _sep, rel = ref.partition(":")
    if prefix != "skydiscover" or not rel:
        raise AlabError("CONFIG_INVALID", "SkyDiscover catalog refs must use skydiscover:<path>")
    pure = PurePosixPath(rel)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise AlabError("CONFIG_INVALID", "SkyDiscover catalog ref path must stay inside the catalog")
    return pure


def _recognize_skydiscover_target(target: Path) -> str:
    if target.is_file() and target.suffix == ".py":
        return "skydiscover_python_evaluator"
    if not target.is_dir():
        raise AlabError("CONFIG_INVALID", "SkyDiscover catalog ref target is not a supported evaluator or task")
    if (target / "task.toml").is_file() or ((target / "instruction.md").is_file() and (target / "tests").is_dir()):
        return "harbor_task"
    if (target / "Dockerfile").is_file() and (target / "evaluate.sh").is_file():
        return "skydiscover_docker_evaluator"
    python_entry = (target / "evaluator.py").is_file() or (target / "evaluate.py").is_file()
    dependency_manifest = (target / "pyproject.toml").is_file() or (target / "requirements.txt").is_file()
    if python_entry or (dependency_manifest and any(child.suffix == ".py" for child in target.iterdir() if child.is_file())):
        return "skydiscover_python_evaluator"
    raise AlabError("CONFIG_INVALID", "SkyDiscover catalog ref target is not a recognized evaluator or task")


def _resolve_skydiscover_catalog_ref(conn, ref: str) -> dict[str, str]:
    rel = _skydiscover_ref_path(ref)
    try:
        catalog = _active_catalog_row(conn)
    except AlabError as exc:
        if exc.code == "CATALOG_NOT_FOUND":
            raise AlabError("CONFIG_INVALID", "active SkyDiscover catalog not found", "alab catalog skydiscover add") from exc
        raise
    catalog_root = Path(catalog["local_path"]).resolve()
    target = (catalog_root / Path(*rel.parts)).resolve()
    if target != catalog_root and catalog_root not in target.parents:
        raise AlabError("CONFIG_INVALID", "SkyDiscover catalog ref path escapes the catalog")
    if not target.exists():
        raise AlabError("CONFIG_INVALID", "SkyDiscover catalog ref target does not exist")
    target_kind = _recognize_skydiscover_target(target)
    return {
        "ref": ref,
        "relative_path": rel.as_posix(),
        "target_kind": target_kind,
        "pinned_commit": catalog["pinned_commit"],
        "target_path": str(target),
    }


def _resolve_local_adapter_ref(ref: str) -> dict[str, str]:
    target = Path(ref).expanduser().resolve()
    if not target.exists():
        raise AlabError("CONFIG_INVALID", "adapter ref target does not exist")
    target_kind = _recognize_skydiscover_target(target)
    return {
        "ref": ref,
        "relative_path": target.name,
        "target_kind": target_kind,
        "pinned_commit": "",
        "target_path": str(target),
    }


def _resolve_harbor_task_ref(conn, ref: str) -> dict[str, str]:
    resolved = _resolve_skydiscover_catalog_ref(conn, ref) if ref.startswith("skydiscover:") else _resolve_local_adapter_ref(ref)
    if resolved["target_kind"] != "harbor_task":
        raise AlabError("CONFIG_INVALID", "runner.harbor_task_ref must resolve to a Harbor-compatible task")
    return resolved


def _resolve_runner_adapter_ref(conn, ref: str) -> dict[str, str]:
    return _resolve_skydiscover_catalog_ref(conn, ref) if ref.startswith("skydiscover:") else _resolve_local_adapter_ref(ref)


ADAPTER_PRIVATE_SOURCE_TOP_LEVELS = {
    "tests",
    "test",
    "environment",
    "solution",
    "solutions",
    "private",
    "hidden",
    "evaluator",
    "evaluators",
    ".git",
    ".alab",
}
ADAPTER_PRIVATE_SOURCE_FILES = {
    "task.toml",
    "instruction.md",
    "Dockerfile",
    "evaluate.sh",
    "evaluator.py",
    "evaluate.py",
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
}
SKYDISCOVER_METADATA_FILES = (
    "benchmark.toml",
    "metadata.toml",
    "skydiscover.toml",
    "benchmark.json",
    "metadata.json",
    "skydiscover.json",
)
SKYDISCOVER_INITIAL_SOURCE_KEYS = (
    "initial_program",
    "initial_program_path",
    "initial_source",
    "initial_source_path",
    "starter",
    "starter_path",
    "starter_source",
    "source",
    "source_path",
)
SKYDISCOVER_CONVENTIONAL_INITIALS = (
    "initial_program",
    "initial_program.py",
    "starter",
    "starter.py",
    "seed",
    "seed.py",
    "program",
    "program.py",
)


def _adapter_child_path(root: Path, rel: str, label: str) -> tuple[Path, PurePosixPath]:
    rel_text = str(rel).strip()
    pure = PurePosixPath(rel_text)
    if not rel_text or "\\" in rel_text or pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise AlabError("CONFIG_INVALID", f"{label} path must stay inside the adapter directory")
    target = (root / Path(*pure.parts)).resolve()
    root_resolved = root.resolve()
    if target == root_resolved or root_resolved not in target.parents:
        raise AlabError("CONFIG_INVALID", f"{label} path escapes the adapter directory")
    return target, pure


def _is_private_adapter_source(pure: PurePosixPath, *, extra_top_levels: set[str] | None = None) -> bool:
    top_levels = ADAPTER_PRIVATE_SOURCE_TOP_LEVELS | (extra_top_levels or set())
    first = pure.parts[0] if pure.parts else ""
    if first in top_levels:
        return True
    return any(part in {".git", ".alab"} for part in pure.parts) or pure.name in ADAPTER_PRIVATE_SOURCE_FILES


def _harbor_source_value(config: dict[str, Any]) -> str | None:
    value = config.get("source")
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("path", "file", "directory"):
            child = value.get(key)
            if isinstance(child, str):
                return child
        return None
    raise AlabError("CONFIG_INVALID", "Harbor source must be a task-relative string path")


def _harbor_derived_source(task: Any) -> AdapterDerivedSource | None:
    rel = _harbor_source_value(task.config)
    if rel is None:
        return None
    target, pure = _adapter_child_path(task.task_dir, rel, "Harbor source")
    if _is_private_adapter_source(pure) or not target.exists():
        return None
    return AdapterDerivedSource(
        origin_type="harbor",
        source_path=target,
        empty=False,
        safe_summary="harbor task source",
        exact={"source_path": pure.as_posix(), "verifier_mode": task.verifier_mode},
    )


def _harbor_instruction_text(task_dir: Path) -> str | None:
    instruction = task_dir / "instruction.md"
    if not instruction.is_file():
        return None
    text = instruction.read_text(encoding="utf-8").strip()
    return text or None


def _harbor_instruction_for_config(conn, config: ProjectConfig) -> str | None:
    if not config.runner.harbor_task_ref:
        return None
    resolved = _resolve_harbor_task_ref(conn, config.runner.harbor_task_ref)
    return _harbor_instruction_text(Path(resolved["target_path"]))


def _metadata_initial_source(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    for key in SKYDISCOVER_INITIAL_SOURCE_KEYS:
        child = value.get(key)
        if isinstance(child, str):
            return child
    for section in ("initial", "program", "source", "benchmark", "starter"):
        child = value.get(section)
        if isinstance(child, dict):
            nested = _metadata_initial_source(child)
            if nested:
                return nested
    return None


def _skydiscover_metadata_initial_source(root: Path) -> str | None:
    for name in SKYDISCOVER_METADATA_FILES:
        path = root / name
        if not path.is_file():
            continue
        try:
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
            raise AlabError("CONFIG_INVALID", f"invalid SkyDiscover metadata file: {name}") from exc
        rel = _metadata_initial_source(data)
        if rel:
            return rel
    return None


def _skydiscover_derived_source(resolved: dict[str, str]) -> AdapterDerivedSource | None:
    target = Path(resolved["target_path"]).resolve()
    root = target if target.is_dir() else target.parent
    rel_candidates: list[str] = []
    metadata_rel = _skydiscover_metadata_initial_source(root)
    if metadata_rel:
        rel_candidates.append(metadata_rel)
    rel_candidates.extend(SKYDISCOVER_CONVENTIONAL_INITIALS)
    seen: set[str] = set()
    for rel in rel_candidates:
        if rel in seen:
            continue
        seen.add(rel)
        candidate, pure = _adapter_child_path(root, rel, "SkyDiscover initial program")
        if _is_private_adapter_source(pure, extra_top_levels={"data", "datasets"}) or not candidate.exists():
            continue
        return AdapterDerivedSource(
            origin_type="skydiscover",
            source_path=candidate,
            empty=False,
            safe_summary="skydiscover initial program",
            exact={
                "initial_program_path": pure.as_posix(),
                "target_kind": resolved["target_kind"],
                "pinned_commit": resolved["pinned_commit"],
                "catalog_path": resolved["relative_path"],
            },
        )
    return None


def _adapter_derived_source(conn, mode: str, config: ProjectConfig) -> AdapterDerivedSource | None:
    if mode == "harbor":
        if not config.runner.harbor_task_ref:
            return None
        resolved = _resolve_harbor_task_ref(conn, config.runner.harbor_task_ref)
        task = load_harbor_task(Path(resolved["target_path"]), config)
        return _harbor_derived_source(task)
    if mode == "skydiscover":
        if not config.runner.skydiscover_task_ref:
            return None
        resolved = _resolve_runner_adapter_ref(conn, config.runner.skydiscover_task_ref)
        if not resolved["target_kind"].startswith("skydiscover_"):
            raise AlabError("CONFIG_INVALID", "runner.skydiscover_task_ref must resolve to a SkyDiscover evaluator")
        return _skydiscover_derived_source(resolved)
    return None


def _validate_adapter_config_refs(conn, config: ProjectConfig, *, allow_probe: bool = True) -> None:
    if config.runner.harbor_task_ref:
        resolved = _resolve_harbor_task_ref(conn, config.runner.harbor_task_ref)
        task = load_harbor_task(Path(resolved["target_path"]), config)
        capabilities = _docker_capabilities_for_validation(conn, allow_probe=allow_probe)
        _validate_docker_resource_requirements(
            capabilities,
            platform=config.runner.platform,
            cpus_required=task.cpus is not None,
            memory_required=task.memory_mb is not None,
        )
    if config.runner.skydiscover_task_ref and config.runner.skydiscover_task_ref.startswith("skydiscover:"):
        resolved = _resolve_skydiscover_catalog_ref(conn, config.runner.skydiscover_task_ref)
        if config.runner.type == "skydiscover_docker" and resolved["target_kind"] != "skydiscover_docker_evaluator":
            raise AlabError("CONFIG_INVALID", "runner.skydiscover_task_ref must resolve to a Docker evaluator")
        if config.runner.type == "skydiscover_python" and resolved["target_kind"] != "skydiscover_python_evaluator":
            raise AlabError("CONFIG_INVALID", "runner.skydiscover_task_ref must resolve to a Python evaluator")
    elif config.runner.skydiscover_task_ref:
        raise AlabError("CONFIG_INVALID", "runner.skydiscover_task_ref must use skydiscover:<path>")


def _upsert_catalog(conn, *, origin_url: str, pinned_commit: str, local_path: Path, status: str) -> None:
    metadata = {
        "schema_version": 1,
        "safe_summary": f"SkyDiscover catalog pinned at {pinned_commit[:12]}",
        "task_refs": [],
        "evaluator_refs": [],
        "warnings": [],
    }
    now = utc_now()
    conn.execute(
        """
        INSERT INTO catalogs(catalog_key, catalog_type, origin_url, pinned_commit, local_path,
          status, metadata_json, retrieved_at, updated_at, removed_at)
        VALUES ('skydiscover', 'skydiscover', ?, ?, ?, ?, ?, ?, ?, NULL)
        ON CONFLICT(catalog_key) DO UPDATE SET
          catalog_type = excluded.catalog_type,
          origin_url = excluded.origin_url,
          pinned_commit = excluded.pinned_commit,
          local_path = excluded.local_path,
          status = excluded.status,
          metadata_json = excluded.metadata_json,
          retrieved_at = excluded.retrieved_at,
          updated_at = excluded.updated_at,
          removed_at = NULL
        """,
        (origin_url, pinned_commit, str(local_path), status, canonical_json(metadata), now, now),
    )


def _clone_or_refresh_catalog(local_path: Path, origin_url: str, *, existing: bool, expected_origin_url: str | None = None) -> None:
    if existing:
        if not (local_path / ".git").exists():
            raise AlabError("CONFIG_INVALID", "catalog local path is not a Git repository")
        current = run_cmd(["git", "remote", "get-url", "origin"], cwd=local_path, check=False)
        if current.returncode != 0:
            raise AlabError("CONFIG_INVALID", "catalog has no origin remote")
        current_url = current.stdout.decode("utf-8", errors="replace").strip()
        if expected_origin_url and current_url != expected_origin_url:
            raise AlabError("CONFIG_INVALID", "catalog has unexpected origin remote")
        if current_url != origin_url:
            _catalog_git(local_path, ["remote", "set-url", "origin", origin_url], "catalog origin update failed")
        dirty = run_cmd(["git", "status", "--porcelain"], cwd=local_path, check=False)
        if dirty.stdout.decode("utf-8", errors="replace").strip():
            raise AlabError("CONFIG_INVALID", "catalog has non-ALab modifications")
        return
    if local_path.exists() and any(local_path.iterdir()):
        raise AlabError("CONFIG_INVALID", "catalog local path already exists")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if local_path.exists():
        local_path.rmdir()
    try:
        run_cmd(["git", "clone", "--quiet", origin_url, str(local_path)])
    except AlabError as exc:
        if exc.code == "GIT_ERROR":
            raise AlabError("CONFIG_INVALID", f"catalog clone failed: {exc.reason}") from exc
        raise


def _catalog_references_skydiscover(value: Any) -> bool:
    if isinstance(value, str):
        return value.startswith("skydiscover:")
    if isinstance(value, dict):
        return any(_catalog_references_skydiscover(child) for child in value.values())
    if isinstance(value, list):
        return any(_catalog_references_skydiscover(child) for child in value)
    return False


def _skydiscover_remove_blockers(conn) -> list[str]:
    blockers: list[str] = []
    projects = all_rows(conn, "SELECT * FROM projects WHERE status != 'archived'", ())
    for project in projects:
        versions = {
            project["latest_attempted_config_version"],
            project["active_valid_config_version"],
        }
        for version in sorted(v for v in versions if v is not None):
            row = one(conn, "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?", (project["project_id"], version))
            if row and _catalog_references_skydiscover(project_config_json_obj(row["canonical_config_json"])):
                blockers.append(f"active_config:{project['project_id']}:{version}")
    open_exps = all_rows(conn, "SELECT project_id, exp_id, bound_config_version FROM experiments WHERE status = 'open'", ())
    for exp in open_exps:
        row = one(conn, "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?", (exp["project_id"], exp["bound_config_version"]))
        if row and _catalog_references_skydiscover(project_config_json_obj(row["canonical_config_json"])):
            blockers.append(f"open_experiment:{exp['exp_id']}")
    return blockers


def cmd_catalog_skydiscover_add(args: list[str], req: Request) -> list[ResultBlock]:
    actor = require_actor(req, "root")
    require_known_options(args, ("--origin-url", "--ref", "--commit"))
    require_options_at_most_once(args, ("--origin-url", "--ref", "--commit"))
    require_positional_count(args, 0, "catalog skydiscover add accepts no positional arguments")
    origin_url = command_arg(args, "--origin-url", default=SKYDISCOVER_ORIGIN_URL)
    ref = command_arg(args, "--ref")
    raw_commit = command_arg(args, "--commit")
    if ref and raw_commit:
        raise AlabError("CONFIG_INVALID", "--ref conflicts with --commit")
    commit = _full_commit_sha_filter(raw_commit)
    db = Database(req.globals.home)
    db.migrate()
    local_path = _catalog_local_path(req.globals.home)
    with db.tx() as conn:
        if one(conn, "SELECT 1 FROM catalogs WHERE catalog_key = 'skydiscover' AND status = 'active'"):
            raise AlabError("CONFIG_INVALID", "active SkyDiscover catalog already exists")
    _clone_or_refresh_catalog(local_path, origin_url, existing=False)
    pinned_commit, requested = _resolve_catalog_commit(local_path, ref=ref, commit=commit)
    _catalog_git(local_path, ["checkout", "--quiet", pinned_commit], "catalog checkout failed")
    with db.tx() as conn:
        _upsert_catalog(conn, origin_url=origin_url, pinned_commit=pinned_commit, local_path=local_path, status="active")
        audit_id = audit(conn, action="add", object_type="catalog", object_id="skydiscover", actor=actor, metadata={"schema_version": 1, "requested_ref": requested, "pinned_commit": pinned_commit})
        row = _active_catalog_row(conn)
    return [
        ResultBlock(
            "catalog",
            [
                ("catalog", "skydiscover"),
                ("origin url", origin_url),
                ("requested ref", requested),
                ("pinned commit", pinned_commit),
                ("local path", str(local_path)),
                ("retrieved at", row["retrieved_at"]),
                ("status", "active"),
                ("audit id", audit_id),
            ],
        )
    ]


def cmd_catalog_skydiscover_update(args: list[str], req: Request) -> list[ResultBlock]:
    actor = require_actor(req, "root")
    require_known_options(args, ("--origin-url", "--ref", "--commit"))
    require_options_at_most_once(args, ("--origin-url", "--ref", "--commit"))
    require_positional_count(args, 0, "catalog skydiscover update accepts no positional arguments")
    ref = command_arg(args, "--ref")
    raw_commit = command_arg(args, "--commit")
    if ref and raw_commit:
        raise AlabError("CONFIG_INVALID", "--ref conflicts with --commit")
    commit = _full_commit_sha_filter(raw_commit)
    with Database(req.globals.home).tx() as conn:
        row = _active_catalog_row(conn)
        origin_url = command_arg(args, "--origin-url", default=row["origin_url"])
        local_path = Path(row["local_path"])
    _clone_or_refresh_catalog(local_path, origin_url, existing=True, expected_origin_url=row["origin_url"])
    pinned_commit, requested = _resolve_catalog_commit(local_path, ref=ref, commit=commit)
    _catalog_git(local_path, ["checkout", "--quiet", pinned_commit], "catalog checkout failed")
    with Database(req.globals.home).tx() as conn:
        _upsert_catalog(conn, origin_url=origin_url, pinned_commit=pinned_commit, local_path=local_path, status="active")
        audit_id = audit(conn, action="update", object_type="catalog", object_id="skydiscover", actor=actor, metadata={"schema_version": 1, "requested_ref": requested, "pinned_commit": pinned_commit})
        row = _active_catalog_row(conn)
    return [
        ResultBlock(
            "catalog",
            [
                ("catalog", "skydiscover"),
                ("origin url", origin_url),
                ("requested ref", requested),
                ("pinned commit", pinned_commit),
                ("local path", str(local_path)),
                ("retrieved at", row["retrieved_at"]),
                ("status", "active"),
                ("audit id", audit_id),
            ],
        )
    ]


def cmd_catalog_skydiscover_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_actor(req, "root")
    require_known_options(args, ())
    require_positional_count(args, 0, "catalog skydiscover show accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        row = _active_catalog_row(conn)
        return [
            ResultBlock(
                "catalog",
                [
                    ("catalog", "skydiscover"),
                    ("origin url", row["origin_url"]),
                    ("pinned commit", row["pinned_commit"]),
                    ("local path", row["local_path"]),
                    ("retrieved at", row["retrieved_at"]),
                    ("status", row["status"]),
                ],
            )
        ]
    finally:
        conn.close()


def cmd_catalog_skydiscover_remove(args: list[str], req: Request) -> list[ResultBlock]:
    actor = require_actor(req, "root")
    require_known_options(args, ("--force", "--confirm", "--reason"))
    require_force_confirm(args, "skydiscover", "catalog remove requires --force and --confirm skydiscover")
    require_positional_count(args, 0, "catalog skydiscover remove accepts no positional arguments")
    reason = _lifecycle_reason(args)
    with Database(req.globals.home).tx() as conn:
        row = _active_catalog_row(conn)
        blockers = _skydiscover_remove_blockers(conn)
        if blockers:
            raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
        local_path = Path(row["local_path"])
        if local_path.exists():
            resolved = local_path.resolve()
            allowed = req.globals.home.sources_path.resolve()
            if resolved != allowed and allowed not in resolved.parents:
                raise AlabError("CONFIG_INVALID", "catalog local path escapes ALAB_HOME sources")
            shutil.rmtree(local_path)
        now = utc_now()
        conn.execute("UPDATE catalogs SET status = 'removed', removed_at = ?, updated_at = ? WHERE catalog_key = 'skydiscover'", (now, now))
        audit_id = audit(conn, action="remove", object_type="catalog", object_id="skydiscover", actor=actor, reason=reason, metadata={"schema_version": 1})
    return [ResultBlock("catalog", [("catalog", "skydiscover"), ("removed", True), ("audit id", audit_id)])]


def cmd_project_init(args: list[str], req: Request) -> list[ResultBlock]:
    _assert_project_init_no_runtime_flags(args)
    require_known_options(
        args,
        (
            "--config",
            "--name",
            "--task",
            "--goal",
            "--source-path",
            "--source-git",
            "--source-empty",
            "--source-ref",
            "--git-ref",
            "--source-subdir",
            "--max-files",
            "--max-total-bytes",
            "--max-file-bytes",
            "--skip-baseline-test",
        ),
    )
    require_options_at_most_once(
        args,
        (
            "--config",
            "--name",
            "--task",
            "--goal",
            "--source-path",
            "--source-git",
            "--source-empty",
            "--source-ref",
            "--git-ref",
            "--source-subdir",
            "--max-files",
            "--max-total-bytes",
            "--max-file-bytes",
            "--skip-baseline-test",
        ),
    )
    mode_pos = require_positional_count(args, 1, "project init requires mode local|git|empty|harbor|skydiscover")
    mode = mode_pos[0]
    if mode not in {"local", "git", "empty", "harbor", "skydiscover"}:
        raise AlabError("CONFIG_INVALID", "project init requires mode local|git|empty|harbor|skydiscover")
    actor = require_actor(req, "root")
    source_limits = _source_import_limits(args)
    config_path = Path(command_arg(args, "--config", required=True))
    raw_config = load_project_config(config_path)
    name_override = command_arg(args, "--name")
    task_override = command_arg(args, "--task")
    goal_override = command_arg(args, "--goal")
    if name_override is not None:
        raw_config.project.name = name_override
    if task_override is not None:
        raw_config.project.task = task_override
    if goal_override is not None:
        raw_config.project.goal = goal_override
    if mode in {"harbor", "skydiscover"}:
        if command_arg(args, "--source-ref"):
            raise AlabError("SOURCE_INVALID", "adapter project init does not accept --source-ref")
    home = req.globals.home
    db = Database(home)
    db.migrate()
    derived_source: AdapterDerivedSource | None = None
    harbor_instruction_task: str | None = None
    with db.tx() as conn:
        _validate_docker_config_capabilities(conn, raw_config)
        _validate_adapter_config_refs(conn, raw_config)
        if mode in {"harbor", "skydiscover"}:
            derived_source = _adapter_derived_source(conn, mode, raw_config)
        if mode == "harbor":
            harbor_instruction_task = _harbor_instruction_for_config(conn, raw_config)
    if mode == "harbor" and harbor_instruction_task and not task_override and not raw_config.project.task.strip():
        raw_config.project.task = harbor_instruction_task
    _validate_project_config_text_fields(raw_config)
    project_id = new_id("proj", raw_config.project.name)
    source_id = new_id("src", command_arg(args, "--name") or raw_config.project.name)
    source_ref = f"alab/source/{source_id}"
    project_root, repo_git, artifact_store = _project_paths(home, project_id)
    control_path = home.project_workspaces_path / project_id
    operation_dir = home.tmp_path / "init" / project_id
    if project_root.exists():
        raise AlabError("NAME_CONFLICT", "project storage path already exists")
    operation_dir.mkdir(parents=True, exist_ok=True)
    project_rows_written = False
    try:
        prepared_source = _prepare_source_work(args, mode, operation_dir, derived_source)
        source_work = prepared_source.source_work
        _enforce_source_import_limits(source_work, source_limits)
        tree_hash = canonical_tree_hash(source_work)
        source_commit = init_snapshot_repo(source_work, author_name=raw_config.git.author_name, author_email=raw_config.git.author_email, message=f"ALab source: {source_id}")
        reject_gitlinks(source_work)
        project_root.mkdir(parents=True)
        _ensure_project_artifact_layout(artifact_store)
        run_cmd(["git", "init", "--bare", str(repo_git)])
        run_cmd(["git", "remote", "add", "alab-project", str(repo_git)], cwd=source_work)
        run_cmd(["git", "push", "alab-project", f"HEAD:refs/heads/alab/source/{source_id}"], cwd=source_work)
        if raw_config.source.default_source_ref and raw_config.source.default_source_ref != source_ref:
            raise AlabError("CONFIG_INVALID", "input source.default_source_ref does not match staged source ref")
        raw_config.source.default_source_ref = source_ref
        fingerprint_key = secrets.token_bytes(32)
        now = utc_now()
        validation_id = new_id("val", "baseline")
        config_version = 1
        with db.tx() as conn:
            home_row = one(conn, "SELECT home_id FROM homes LIMIT 1")
            home_id = home_row["home_id"]
            config_json, raw_secrets = _store_secret_values(conn, project_id, fingerprint_key, raw_config, actor)
            cfg_hash = config_hash(config_json)
            control_path.mkdir(parents=True, exist_ok=True)
            write_marker(
                control_path,
                {
                    "marker_version": 1,
                    "home_id": home_id,
                    "context_type": "project",
                    "project_id": project_id,
                    "exp_id": None,
                    "token_id": None,
                    "canonical_repo_path_hash": path_hash(repo_git),
                    "created_at": now,
                },
            )
            conn.execute(
                """
                INSERT INTO projects(project_id, status, pre_archive_status, canonical_repo_path, control_path,
                  secret_fingerprint_key, latest_attempted_config_version, active_valid_config_version,
                  active_validation_id, created_at, updated_at, archived_at)
                VALUES (?, 'invalid', NULL, ?, ?, ?, 1, NULL, NULL, ?, ?, NULL)
                """,
                (project_id, str(repo_git), str(control_path), fingerprint_key, now, now),
            )
            conn.execute(
                """
                INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id,
                  exp_id, token_id, status, created_at, updated_at)
                VALUES (?, ?, ?, 'project', ?, ?, NULL, NULL, 'active', ?, ?)
                """,
                (new_id("path", "project"), path_hash(control_path), str(control_path.resolve()), home_id, project_id, now, now),
            )
            conn.execute(
                """
                INSERT INTO sources(source_id, project_id, name, name_slug, source_ref, source_commit, tree_hash,
                  status, origin_metadata_json, created_at, archived_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, NULL)
                """,
                (
                    source_id,
                    project_id,
                    raw_config.project.name,
                    slugify(raw_config.project.name, "source"),
                    source_ref,
                    source_commit,
                    tree_hash,
                    canonical_json(
                        source_origin_metadata_obj(
                            canonical_json(
                                {
                                    "schema_version": 1,
                                    "tree_hash_algorithm": "alab-tree-sha256-v1",
                                    "primary_origin": _source_origin_with_time(prepared_source.origin_records[0], now),
                                    "origins": [_source_origin_with_time(record, now) for record in prepared_source.origin_records],
                                }
                            )
                        )
                    ),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO project_config_versions(project_id, version, canonical_config_json, config_hash,
                  baseline_required, validation_status, inherited_from_validation_id, created_at, created_by_credential_id)
                VALUES (?, 1, ?, ?, 1, 'running', NULL, ?, ?)
                """,
                (project_id, canonical_json(project_config_json_obj(canonical_json(config_json))), cfg_hash, now, actor.credential_id),
            )
            conn.execute(
                """
                INSERT INTO project_validations(validation_id, project_id, config_version, source_ref, source_commit,
                  status, exit_code, reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
                VALUES (?, ?, 1, ?, ?, 'running', NULL, NULL, 'not_attempted', 'active', ?, NULL, ?)
                """,
                (
                    validation_id,
                    project_id,
                    source_ref,
                    source_commit,
                    now,
                    _execution_record_object_json(
                        config_hash_value=cfg_hash,
                        runner_type=raw_config.runner.type,
                        reward_type=raw_config.reward.type,
                    ),
                ),
            )
            admin_id, admin_key = create_credential(conn, credential_type="admin", project_id=project_id, metadata={"schema_version": 1, "role": "admin"})
            audit(conn, action="add", object_type="project", object_id=project_id, actor=actor, project_id=project_id)
        project_rows_written = True
        if flag(args, "--skip-baseline-test"):
            with db.tx() as conn:
                conn.execute("UPDATE project_validations SET status = 'skipped', ended_at = ?, reward_parse_status = 'not_attempted' WHERE validation_id = ?", (utc_now(), validation_id))
                conn.execute("UPDATE project_config_versions SET validation_status = 'skipped' WHERE project_id = ? AND version = 1", (project_id,))
                validation_status, exit_code, reward, reward_parse_status, warning_codes = "skipped", None, None, "not_attempted", []
        else:
            with db.tx() as conn:
                validation_status, exit_code, reward, reward_parse_status, warning_codes = _run_validation(conn, home, project_id, validation_id, source_ref, source_commit, config_version, raw_config, raw_secrets)
                project_status = "valid" if validation_status == "passed" else "invalid"
                active_version = 1 if validation_status == "passed" else None
                active_validation = validation_id if validation_status == "passed" else None
                conn.execute(
                    "UPDATE projects SET status = ?, active_valid_config_version = ?, active_validation_id = ?, updated_at = ? WHERE project_id = ?",
                    (project_status, active_version, active_validation, utc_now(), project_id),
                )
                conn.execute("UPDATE project_config_versions SET validation_status = ? WHERE project_id = ? AND version = 1", (validation_status, project_id))
        project_status = "valid" if validation_status == "passed" else "invalid"
        next_action = (
            f"alab exp create --project {project_id} --name <name>"
            if project_status == "valid"
            else f"alab project validate --project {project_id} --key <root-or-admin-key>"
        )
        fields: list[tuple[str, Any]] = [
            ("project id", project_id),
            ("project name", raw_config.project.name),
            ("project status", project_status),
            ("source id", source_id),
            ("source ref", source_ref),
            ("config version", 1),
            ("validation id", validation_id),
            ("validation status", validation_status),
            ("admin key", admin_key),
            ("warning code", warning_codes),
        ]
        failure_fields = _baseline_failure_fields(validation_status, next_action)
        if failure_fields:
            fields.extend(failure_fields)
        else:
            fields.append(("next", next_action))
        return [ResultBlock("project", fields)]
    except Exception:
        if not project_rows_written:
            shutil.rmtree(project_root, ignore_errors=True)
            shutil.rmtree(control_path, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(operation_dir, ignore_errors=True)


def _assert_project_init_no_runtime_flags(args: list[str]) -> None:
    allowed_value_options = {
        "--config",
        "--git-ref",
        "--goal",
        "--max-file-bytes",
        "--max-files",
        "--max-total-bytes",
        "--name",
        "--source-git",
        "--source-path",
        "--source-ref",
        "--source-subdir",
        "--task",
    }
    allowed_flags = {"--skip-baseline-test", "--source-empty"}
    runtime_prefixes = (
        "--artifact",
        "--artifacts",
        "--docker",
        "--env",
        "--harbor",
        "--log",
        "--logs",
        "--reward",
        "--runner",
        "--secret",
        "--skydiscover",
        "--stderr",
        "--stdout",
        "--timeout",
        "--working-directory",
    )
    idx = 0
    while idx < len(args):
        item = args[idx]
        if item == "--":
            return
        if item in allowed_value_options:
            idx += 2
            continue
        if item in allowed_flags:
            idx += 1
            continue
        if item.startswith(runtime_prefixes):
            raise AlabError("CONFIG_INVALID", f"{item} is not accepted by project init; set runtime fields in --config")
        idx += 1


def _project_row(conn, project_id: str | None) -> Any:
    if project_id is None:
        raise AlabError("CONTEXT_NOT_FOUND", "project id is required")
    project_id = require_complete_id(project_id, "proj")
    row = one(conn, "SELECT * FROM projects WHERE project_id = ?", (project_id,))
    if row is None:
        raise AlabError("PROJECT_NOT_FOUND", "project not found")
    return row


def _project_id_from_request(args: list[str], req: Request) -> str | None:
    require_options_at_most_once(args, ("--project",))
    return command_arg(args, "--project") or (req.context.project_id if req.context else None)


def _complete_id_or_missing(value: str | None, *, prefix: str, code: str, label: str) -> str:
    if not value:
        raise AlabError(code, f"{label} is required")
    return require_complete_id(value, prefix)


def _complete_id_option(args: list[str], option: str, prefix: str) -> str | None:
    require_options_at_most_once(args, (option,))
    value = command_arg(args, option)
    return require_complete_id(value, prefix) if value else None


AUDIT_OBJECT_ID_PREFIXES = {
    "annotation": "ann",
    "artifact": "art",
    "credential": "cred",
    "experiment": "exp",
    "inspection_checkout": "cred",
    "log": "log",
    "project": "proj",
    "run": "run",
    "source": "src",
    "validation": "val",
    "worktree": "exp",
}

AUDIT_OBJECT_ID_LITERALS = {
    "backup": {"backups"},
    "cache": {"cache"},
    "catalog": {"skydiscover"},
}

AUDIT_ACTIONS = {
    "add",
    "archive",
    "clear",
    "gc",
    "prune",
    "regenerate",
    "remove",
    "repair",
    "restore",
    "revoke",
    "unarchive",
    "update",
}


ANNOTATION_TARGET_ID_PREFIXES = {
    "artifact": "art",
    "experiment": "exp",
    "run": "run",
}
ANNOTATION_TARGET_TYPES = {"artifact", "experiment", "run", "path", "lines"}


def _annotation_target_id_filter(target_type: str | None, target_id: str | None) -> str | None:
    if not target_id:
        return None
    if target_type in ANNOTATION_TARGET_ID_PREFIXES:
        return require_complete_id(target_id, ANNOTATION_TARGET_ID_PREFIXES[target_type])
    if ":" not in target_id:
        for prefix in ANNOTATION_TARGET_ID_PREFIXES.values():
            if target_id.startswith(prefix + "-"):
                return require_complete_id(target_id, prefix)
    return target_id


def _annotation_created_by_filter(created_by: str | None) -> str | None:
    if not created_by:
        return None
    created_by = require_complete_id(created_by)
    if not (created_by.startswith("exp-") or created_by.startswith("cred-")):
        raise AlabError("CONFIG_INVALID", "--created-by must be an experiment or credential id")
    return created_by


def _audit_object_id_filter(object_type: str | None, object_id: str | None) -> str | None:
    if not object_id:
        return None
    if not object_type:
        literal_ids = set().union(*AUDIT_OBJECT_ID_LITERALS.values())
        if object_id in literal_ids:
            return object_id
        return require_complete_id(object_id)
    if object_type in AUDIT_OBJECT_ID_PREFIXES:
        return require_complete_id(object_id, AUDIT_OBJECT_ID_PREFIXES[object_type])
    if object_type in AUDIT_OBJECT_ID_LITERALS and object_id not in AUDIT_OBJECT_ID_LITERALS[object_type]:
        raise AlabError("CONFIG_INVALID", f"--object-id must be one of {', '.join(sorted(AUDIT_OBJECT_ID_LITERALS[object_type]))}")
    return object_id


def _assert_empty_or_missing_path(path: Path, label: str) -> None:
    if not path.exists():
        return
    if path.is_file() or path.is_symlink():
        raise AlabError("OUTPUT_EXISTS", f"{label} path already exists")
    if any(path.iterdir()):
        raise AlabError("OUTPUT_EXISTS", f"{label} path already exists")


def _assert_missing_path(path: Path, label: str, *, next_action: str | None = None) -> None:
    if path.exists() or path.is_symlink():
        raise AlabError("OUTPUT_EXISTS", f"{label} path already exists", next_action)


def _assert_export_output_path(path: Path, *, overwrite: bool, require_existing_parent: bool) -> None:
    if path.exists():
        if path.is_dir():
            raise AlabError("OUTPUT_EXISTS", "output path already exists")
        if not overwrite:
            raise AlabError("OUTPUT_EXISTS", "output path already exists")
    if require_existing_parent and not path.parent.is_dir():
        raise AlabError("CONFIG_INVALID", "output parent directory does not exist")


def _assert_context_path_nesting(conn, *, target: Path, project_id: str, context_type: str) -> None:
    target = target.expanduser().resolve()
    rows = all_rows(conn, "SELECT project_id, context_type, path FROM path_registry WHERE status = 'active'")
    for row in rows:
        registered = Path(row["path"]).expanduser().resolve()
        if target == registered:
            raise AlabError("CONTEXT_CONFLICT", "target path is already registered")
        target_inside_registered = registered in target.parents
        registered_inside_target = target in registered.parents
        if target_inside_registered:
            if (
                row["context_type"] == "project"
                and row["project_id"] == project_id
                and context_type in {"experiment", "inspection"}
            ):
                continue
            raise AlabError("CONTEXT_CONFLICT", "target path nests inside another ALab context")
        if registered_inside_target:
            raise AlabError("CONTEXT_CONFLICT", "target path would contain another ALab context")


def _assert_new_context_path(conn, *, target: Path, project_id: str, context_type: str, label: str) -> None:
    _assert_empty_or_missing_path(target, label)
    _assert_context_path_nesting(conn, target=target, project_id=project_id, context_type=context_type)


def _require_project_admin(args: list[str], req: Request) -> tuple[Any, Actor]:
    project_id = _project_id_from_request(args, req)
    actor = require_actor(req, ("root", "admin"), project_id=project_id)
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        return dict(project), actor
    finally:
        conn.close()


def _selected_config_row(conn, project: Any, selector: str | None) -> tuple[int, str, Any]:
    selector = selector or "latest-attempted"
    if selector == "latest-attempted":
        version = project["latest_attempted_config_version"]
    elif selector == "active-valid":
        version = project["active_valid_config_version"]
        if version is None:
            raise AlabError("PROJECT_INVALID", "project has no active valid config")
    else:
        try:
            version = int(selector)
        except ValueError as exc:
            raise AlabError("CONFIG_INVALID", "invalid config version selector") from exc
        if version < 1:
            raise AlabError("CONFIG_INVALID", "invalid config version selector")
    row = one(conn, "SELECT * FROM project_config_versions WHERE project_id = ? AND version = ?", (project["project_id"], version))
    if row is None:
        raise AlabError("CONFIG_INVALID", "config version not found")
    return int(version), selector, row


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


RUNTIME_CONFIG_KEYS = {"source", "runner", "reward", "artifacts", "logs", "env", "secret_env"}


def _runtime_signature(config_json: dict[str, Any]) -> str:
    return canonical_json({key: config_json.get(key) for key in sorted(RUNTIME_CONFIG_KEYS)})


def _source_for_ref(conn, project_id: str, source_ref: str | None) -> Any:
    if not source_ref:
        raise AlabError("SOURCE_NOT_FOUND", "source.default_source_ref is not set")
    row = one(
        conn,
        "SELECT * FROM sources WHERE project_id = ? AND (source_ref = ? OR source_id = ?) AND status = 'active'",
        (project_id, source_ref, source_ref),
    )
    if row is None:
        raise AlabError("SOURCE_NOT_FOUND", "source not found")
    return row


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
                        raise AlabError("CONFIG_INVALID", f"secret_env.{name} retain marker has no previous secret value")
                    if value.get("fingerprint") and marker.get("fingerprint") and value["fingerprint"] != marker["fingerprint"]:
                        raise AlabError("CONFIG_INVALID", f"secret_env.{name} retain marker fingerprint does not match")
                if isinstance(value, str) and ("\n" in value or "\0" in value or len(value.encode("utf-8")) < 4):
                    raise AlabError("CONFIG_INVALID", "secret_env values must be single-line UTF-8 strings at least 4 bytes")
            _validate_docker_config_capabilities(conn, next_config, allow_probe=False)
            _validate_adapter_config_refs(conn, next_config, allow_probe=False)
            next_json = next_config.canonical_dict()
            for name, marker in list(next_json.get("secret_env", {}).items()):
                if isinstance(marker, dict) and marker.get("retain"):
                    next_json["secret_env"][name] = base_secret_markers[name]
                elif isinstance(marker, str):
                    next_json["secret_env"][name] = {"fingerprint": _secret_fingerprint(fingerprint_key, name, marker)}
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
        validation_status = "running" if runtime_affecting and not skip_baseline else "skipped" if runtime_affecting else "inherited"
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
                1 if runtime_affecting else 0,
                validation_status,
                inherited_validation_id,
                now,
                actor.credential_id,
            ),
        )
        source = _source_for_ref(tx, project["project_id"], config_json.get("source", {}).get("default_source_ref"))
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
                    "skipped" if skip_baseline else "running",
                    now,
                    now if skip_baseline else None,
                    _execution_record_object_json(
                        config_hash_value=new_hash,
                        runner_type=next_config.runner.type,
                        reward_type=next_config.reward.type,
                    ),
                ),
            )
        next_active = (
            new_version
            if not runtime_affecting and project["active_valid_config_version"]
            else project["active_valid_config_version"]
        )
        next_active_validation = project["active_validation_id"]
        next_status = project["status"]
        if runtime_affecting and skip_baseline:
            next_status = "invalid"
        tx.execute(
            """
            UPDATE projects
            SET latest_attempted_config_version = ?, active_valid_config_version = ?, active_validation_id = ?, updated_at = ?, status = ?
            WHERE project_id = ?
            """,
            (new_version, next_active, next_active_validation, now, next_status, project["project_id"]),
        )
    if runtime_affecting and not skip_baseline:
        with db.tx() as tx:
            validation_status, exit_code, reward, reward_parse_status, warning_codes = _run_validation(
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
            project_status = "valid" if validation_status == "passed" else "invalid"
            active_version = (
                new_version
                if validation_status == "passed"
                else project["active_valid_config_version"]
            )
            active_validation = (
                validation_id
                if validation_status == "passed"
                else project["active_validation_id"]
            )
            tx.execute(
                "UPDATE projects SET status = ?, active_valid_config_version = ?, active_validation_id = ?, updated_at = ? WHERE project_id = ?",
                (project_status, active_version, active_validation, utc_now(), project["project_id"]),
            )
            tx.execute(
                "UPDATE project_config_versions SET validation_status = ? WHERE project_id = ? AND version = ?",
                (validation_status, project["project_id"], new_version),
            )
    else:
        project_status = "invalid" if runtime_affecting and skip_baseline else project["status"]
    next_action = "alab exp create --name <name>" if project_status == "valid" else "alab project validate"
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
                    ("project name", project_config_json_obj(one(conn, "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?", (row["project_id"], row["latest_attempted_config_version"]))["canonical_config_json"])["project"]["name"]),
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
        cfg, _, cfg_json = _load_config_and_secrets(conn, project["project_id"], project["latest_attempted_config_version"])
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
    resolved_targets = [_ResolvedRemovalTarget(target, _resolve_removal_path(target.path), order) for order, target in enumerate(targets)]
    resolved_targets.sort(key=lambda item: (len(item.resolved.parts), str(item.resolved), item.order))
    kept: list[_ResolvedRemovalTarget] = []
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
        FilesystemRemovalTarget("project_repo", project_id, Path(project["canonical_repo_path"]) if project.get("canonical_repo_path") else repo_git),
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
            tx.execute("UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE project_id = ? AND status = 'active'", (now, project["project_id"]))
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
            tx.execute("DELETE FROM annotation_revisions WHERE annotation_id IN (SELECT annotation_id FROM annotations WHERE project_id = ?)", (project["project_id"],))
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


def cmd_project_config_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--version"))
    require_options_at_most_once(args, ("--version",))
    project_id = _project_id_from_request(args, req)
    require_actor(req, ("root", "admin"), project_id=project_id)
    require_positional_count(args, 0, "project config show accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        version, selector, cfg_row = _selected_config_row(conn, project, command_arg(args, "--version", default="latest-attempted"))
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
                    ("mutable summary", f"include={len(cfg.mutable.include)} exclude={len(cfg.mutable.exclude)}"),
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
    _assert_export_output_path(out_path, overwrite=flag(args, "--overwrite"), require_existing_parent=False)
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        version, _selector, cfg_row = _selected_config_row(conn, project, command_arg(args, "--version", default="latest-attempted"))
        export_json = _exportable_config_json(project_config_json_obj(cfg_row["canonical_config_json"]))
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
        raise AlabError("CONFIG_INVALID", "secret_env changes must use project secret or config import retain markers")
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
            ResultBlock("project_env", [("project id", project_id), ("config version", version), ("env name", name), ("value", value)])
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
    require_exactly_one_option_pair(args, "--value-stdin", "--value-file", "project secret set requires exactly one of --value-stdin or --value-file")
    value_file = command_arg(args, "--value-file")
    value = _read_text_input_file(value_file, "secret value") if value_file else sys.stdin.read()
    if value.endswith("\n"):
        value = value[:-1]
    if not value or "\n" in value or "\0" in value or len(value.encode("utf-8")) < 4:
        raise AlabError("CONFIG_INVALID", "secret value must be a single-line UTF-8 string at least 4 bytes")
    return value


def cmd_project_secret_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project_id = _project_id_from_request(args, req)
    require_actor(req, ("root", "admin"), project_id=project_id)
    require_positional_count(args, 0, "project secret list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        _project_row(conn, project_id)
        rows = all_rows(conn, "SELECT * FROM secret_values WHERE project_id = ? ORDER BY name, created_at", (project_id,))
        referenced_ids: set[str] = set()
        for cfg in all_rows(conn, "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ?", (project_id,)):
            for marker in project_config_json_obj(cfg["canonical_config_json"]).get("secret_env", {}).values():
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
    require_known_options(args, ("--project", "--value-stdin", "--value-file", "--dry-run", "--skip-baseline-test"))
    require_options_at_most_once(args, ("--value-stdin", "--value-file", "--dry-run", "--skip-baseline-test"))
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
        _version, _selector, cfg_row = _selected_config_row(conn, _project_row(conn, project["project_id"]), "latest-attempted")
        marker = project_config_json_obj(cfg_row["canonical_config_json"]).get("secret_env", {}).get(name, {})
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
    for cfg in all_rows(conn, "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ?", (project_id,)):
        for marker in project_config_json_obj(cfg["canonical_config_json"]).get("secret_env", {}).values():
            if isinstance(marker, dict) and marker.get("secret_value_id"):
                referenced_ids.add(marker["secret_value_id"])
    return referenced_ids


def cmd_project_secret_gc(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--apply"))
    require_options_at_most_once(args, ("--dry-run", "--apply"))
    project, actor = _require_project_admin(args, req)
    require_positional_count(args, 0, "project secret gc accepts no positional arguments")
    require_exactly_one_option_pair(args, "--dry-run", "--apply", "project secret gc requires exactly one of --dry-run or --apply")
    apply = flag(args, "--apply")
    with Database(req.globals.home).tx() as conn:
        referenced_ids = _referenced_secret_ids(conn, project["project_id"])
        rows = all_rows(conn, "SELECT * FROM secret_values WHERE project_id = ? ORDER BY created_at", (project["project_id"],))
        unreferenced = [row for row in rows if row["secret_value_id"] not in referenced_ids]
        audit_id = None
        if apply and unreferenced:
            conn.executemany("DELETE FROM secret_values WHERE secret_value_id = ?", [(row["secret_value_id"],) for row in unreferenced])
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
        conn.execute(
            """
            INSERT INTO project_validations(validation_id, project_id, config_version, source_ref, source_commit,
              status, exit_code, reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
            VALUES (?, ?, ?, ?, ?, 'running', NULL, NULL, 'not_attempted', 'active', ?, NULL, ?)
            """,
            (
                validation_id,
                project["project_id"],
                version,
                source["source_ref"],
                source["source_commit"],
                now,
                _execution_record_object_json(
                    config_hash_value=config_hash(cfg_json),
                    runner_type=cfg.runner.type,
                    reward_type=cfg.reward.type,
                ),
            ),
        )
        conn.execute(
            "UPDATE project_config_versions SET baseline_required = 1, validation_status = 'running' WHERE project_id = ? AND version = ?",
            (project["project_id"], version),
        )
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
    next_action = "alab exp create --name <name>" if project_status == "valid" else "fix config or source and rerun alab project validate"
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
    validation_id = _complete_id_or_missing(validation_id, prefix="val", code="VALIDATION_NOT_FOUND", label="validation id")
    row = one(conn, "SELECT * FROM project_validations WHERE project_id = ? AND validation_id = ?", (project_id, validation_id))
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
    validation_id = optional_positional_selector(args, "validation archive accepts exactly one validation id")
    with Database(req.globals.home).tx() as conn:
        _interrupt_stale_running_records(conn, project_id=project["project_id"])
        row = _validation_row(conn, project["project_id"], validation_id)
        blockers = _validation_blockers(project, row)
        if blockers:
            raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
        previous = row["archive_status"]
        archived_at = row["archived_at"] if previous == "archived" and row["archived_at"] else utc_now()
        audit_id = None
        if previous != "archived":
            conn.execute("UPDATE project_validations SET archive_status = 'archived', archived_at = ? WHERE validation_id = ?", (archived_at, row["validation_id"]))
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
    validation_id = optional_positional_selector(args, "validation unarchive accepts exactly one validation id")
    with Database(req.globals.home).tx() as conn:
        _interrupt_stale_running_records(conn, project_id=project["project_id"])
        row = _validation_row(conn, project["project_id"], validation_id)
        previous = row["archive_status"]
        unarchived_at = utc_now() if previous != "active" else row["unarchived_at"]
        audit_id = None
        if previous != "active":
            conn.execute("UPDATE project_validations SET archive_status = 'active', archived_at = NULL, unarchived_at = ? WHERE validation_id = ?", (unarchived_at, row["validation_id"]))
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
    require_known_options(args, ("--project", "--dry-run", "--cascade", "--force", "--confirm", "--reason"))
    require_options_at_most_once(args, ("--dry-run", "--cascade", "--reason"))
    require_dry_run_unforced(args)
    project, actor = _require_project_admin(args, req)
    validation_id = optional_positional_selector(args, "validation remove accepts exactly one validation id")
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
        artifact_rows = all_rows(conn, "SELECT * FROM artifacts WHERE project_id = ? AND validation_id = ? ORDER BY artifact_id", (project["project_id"], row["validation_id"]))
        log_rows = all_rows(conn, "SELECT * FROM log_streams WHERE project_id = ? AND validation_id = ? ORDER BY log_id", (project["project_id"], row["validation_id"]))
        counts = {"artifacts": len(artifact_rows), "logs": len(log_rows)}
        active_dependent_artifacts = sum(1 for artifact in artifact_rows if artifact["archive_status"] != "archived")
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
                    ("planned trash move", [_trash_plan(req.globals.home, target.path) for target in filesystem_targets]),
                ],
            )
        ]
    require_force_confirm(args, row["validation_id"], "validation remove requires --force and matching --confirm")
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
                            "original_path_hash": path_hash(stage.original_path) if stage.original_path else None,
                            "already_absent": stage.already_absent,
                        }
                        for target, stage in zip(filesystem_targets, stages, strict=False)
                    ],
                },
            )
            tx.execute("DELETE FROM artifacts WHERE validation_id = ?", (row["validation_id"],))
            tx.execute("DELETE FROM log_streams WHERE validation_id = ?", (row["validation_id"],))
            tx.execute("DELETE FROM project_validations WHERE validation_id = ?", (row["validation_id"],))
    except Exception as exc:
        _raise_after_staged_trash_transaction_failure(exc, stages)
    trash_cleanup_pending = _finalize_staged_trashes(req.globals.home, stages, project["project_id"])
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


def _parse_days(args: list[str], name: str) -> int | None:
    value = command_arg(args, name)
    if value is None:
        return None
    try:
        days = int(value)
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", f"{name} must be an integer number of days") from exc
    if days < 0:
        raise AlabError("CONFIG_INVALID", f"{name} must be zero or greater")
    return days


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


def _parse_backup_keep(args: list[str]) -> int | None:
    keep_value = command_arg(args, "--keep")
    if keep_value is None:
        return None
    try:
        keep = int(keep_value)
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", "--keep must be an integer") from exc
    if keep < 0:
        raise AlabError("CONFIG_INVALID", "--keep must be zero or greater")
    return keep


def cmd_backup_prune(args: list[str], req: Request) -> list[ResultBlock]:
    actor = require_actor(req, "root")
    require_known_options(args, ("--keep", "--older-than"))
    require_exactly_one_option_pair(args, "--keep", "--older-than", "backup prune requires exactly one of --keep or --older-than")
    require_positional_count(args, 0, "backup prune accepts no positional arguments")
    keep = _parse_backup_keep(args)
    older_than = _parse_days(args, "--older-than")
    backups = sorted(req.globals.home.backups_path.glob("*.db"), key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
    if keep is not None:
        prune = backups[keep:]
    else:
        threshold = datetime.now(UTC) - timedelta(days=older_than or 0)
        prune = [path for path in backups if datetime.fromtimestamp(path.stat().st_mtime, UTC) < threshold]
    pruned: list[str] = []
    for path in prune:
        _remove_path_if_safe(path, req.globals.home.path)
        pruned.append(str(path))
    with Database(req.globals.home).tx() as conn:
        audit_id = audit(
            conn,
            action="prune",
            object_type="backup",
            object_id="backups",
            actor=actor,
            metadata={"schema_version": 1, "pruned_count": len(pruned)},
        )
    return [ResultBlock("backup_prune", [("backup pruned count", len(pruned)), ("backup path", pruned), ("audit id", audit_id)])]


def _cache_cutoff(args: list[str]) -> str | None:
    days = _parse_days(args, "--older-than")
    if days is None:
        return None
    return (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cmd_cache_prune(args: list[str], req: Request) -> list[ResultBlock]:
    actor = require_actor(req, "root")
    require_known_options(args, ("--all", "--docker-images", "--skydiscover-envs", "--trash", "--trash-all", "--older-than"))
    require_options_at_most_once(args, ("--all", "--docker-images", "--skydiscover-envs", "--trash", "--trash-all", "--older-than"))
    all_flag = flag(args, "--all")
    explicit_selectors = [flag(args, "--docker-images"), flag(args, "--skydiscover-envs"), flag(args, "--trash"), flag(args, "--trash-all")]
    if all_flag and any(explicit_selectors):
        raise AlabError("CONFIG_INVALID", "--all conflicts with specific cache selectors")
    if all_flag and command_arg(args, "--older-than") is not None:
        raise AlabError("CONFIG_INVALID", "--all conflicts with --older-than")
    if not all_flag and not any(explicit_selectors):
        raise AlabError("CONFIG_INVALID", "cache prune requires at least one selector")
    if flag(args, "--trash") and flag(args, "--trash-all"):
        raise AlabError("CONFIG_INVALID", "--trash conflicts with --trash-all")
    if flag(args, "--trash-all") and command_arg(args, "--older-than") is not None:
        raise AlabError("CONFIG_INVALID", "--trash-all conflicts with --older-than")
    if flag(args, "--trash") and command_arg(args, "--older-than") is None:
        raise AlabError("CONFIG_INVALID", "--trash requires --older-than")
    if not flag(args, "--trash") and command_arg(args, "--older-than") is not None and not all_flag:
        raise AlabError("CONFIG_INVALID", "--older-than is only valid with --trash")
    require_positional_count(args, 0, "cache prune accepts no positional arguments")
    kinds: set[str] = set()
    if all_flag or flag(args, "--docker-images"):
        kinds.add("docker_image")
    if all_flag or flag(args, "--skydiscover-envs"):
        kinds.add("skydiscover_python_env")
    if all_flag or flag(args, "--trash") or flag(args, "--trash-all"):
        kinds.add("trash")
    cutoff = None if all_flag or flag(args, "--trash-all") else _cache_cutoff(args)
    warnings: list[tuple[str, str]] = []
    with Database(req.globals.home).tx() as conn:
        clauses = ["status = 'active'"]
        params: list[Any] = []
        placeholders = ", ".join("?" for _ in kinds)
        clauses.append(f"cache_kind IN ({placeholders})")
        params.extend(sorted(kinds))
        if cutoff:
            clauses.append("(cache_kind != 'trash' OR COALESCE(last_used_at, created_at) < ?)")
            params.append(cutoff)
        rows = all_rows(conn, f"SELECT * FROM cache_entries WHERE {' AND '.join(clauses)} ORDER BY cache_kind, cache_key", tuple(params))
        pruned_count = 0
        for row in rows:
            if row["cache_kind"] == "docker_image" and row["docker_tag"]:
                removed, reason = prune_docker_image(row["docker_tag"])
                if not removed:
                    warnings.append(("DOCKER_CACHE_PRUNE_FAILED", f"{row['docker_tag']}: {reason}"))
                    continue
            if row["path"]:
                if row["cache_kind"] == "trash":
                    _remove_trash_cache_path(Path(row["path"]), req.globals.home)
                else:
                    _remove_path_if_safe(Path(row["path"]), req.globals.home.path)
            conn.execute("UPDATE cache_entries SET status = 'removed', removed_at = ? WHERE cache_id = ?", (utc_now(), row["cache_id"]))
            pruned_count += 1
        audit_id = audit(
            conn,
            action="prune",
            object_type="cache",
            object_id="cache",
            actor=actor,
            metadata={"schema_version": 1, "cache_kinds": sorted(kinds), "pruned_count": pruned_count, "warning_count": len(warnings)},
        )
    blocks = [
        ResultBlock(
            "cache_prune",
            [
                ("cache pruned count", pruned_count),
                ("cache kind", sorted(kinds)),
                ("audit id", audit_id),
            ],
        )
    ]
    for code, reason in warnings:
        blocks.append(ResultBlock("warning", [("warning code", code), ("warning reason", reason)]))
    return blocks


def cmd_status(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    require_options_at_most_once(args, ("--project",))
    require_positional_count(args, 0, "status accepts no positional arguments")
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    with Database(req.globals.home).tx() as conn:
        _interrupt_stale_running_records(conn, project_id=project_id)
        project = _project_row(conn, project_id)
        public_project_status = (
            not _actor_is_project_admin_or_root(req.actor, project["project_id"])
            and (req.context is None or req.context.context_type == "project")
        )
        if public_project_status and project["status"] == "invalid":
            context_type = req.context.context_type if req.context else "public"
            return [
                ResultBlock(
                    "project",
                    [
                        ("context type", context_type),
                        ("project id", project["project_id"]),
                        ("project status", project["status"]),
                        ("next", f"alab project validate --project {project['project_id']} --key <root-or-admin-key>"),
                    ],
                )
            ]
        cfg, _, _ = _load_config_and_secrets(conn, project["project_id"], project["latest_attempted_config_version"])
        fields = [
            ("context type", req.context.context_type if req.context else "public"),
            ("project id", project["project_id"]),
            ("project status", project["status"]),
            ("task", multiline_text(cfg.project.task)),
            ("next", "alab help"),
        ]
        if req.context and req.context.exp_id:
            exp = one(conn, "SELECT * FROM experiments WHERE exp_id = ?", (req.context.exp_id,))
            fields.extend([("exp id", req.context.exp_id), ("experiment status", exp["status"] if exp else None)])
            return [ResultBlock("experiment" if req.context.context_type == "experiment" else "inspection_checkout", fields)]
        return [ResultBlock("project", fields)]


def _context_next(context_type: str | None) -> str:
    if context_type == "project":
        return "alab project show"
    if context_type == "experiment":
        return "alab run --message <message>"
    if context_type == "inspection":
        return "alab runs list"
    return "alab auth init"


def _registry_row_for_marker(conn, marker: dict[str, Any]) -> Any | None:
    token_id = marker.get("token_id")
    if token_id:
        row = one(conn, "SELECT * FROM path_registry WHERE token_id = ? AND status = 'active'", (token_id,))
        if row:
            return row
    context_type = marker.get("context_type")
    project_id = marker.get("project_id")
    exp_id = marker.get("exp_id")
    if context_type == "project":
        return one(conn, "SELECT * FROM path_registry WHERE context_type = 'project' AND project_id = ? AND status = 'active'", (project_id,))
    return one(
        conn,
        "SELECT * FROM path_registry WHERE context_type = ? AND project_id = ? AND exp_id = ? AND status = 'active'",
        (context_type, project_id, exp_id),
    )


def _git_common_dir(path: Path) -> Path | None:
    result = run_cmd(["git", "-C", str(path), "rev-parse", "--git-common-dir"], check=False)
    if result.returncode != 0:
        return None
    text = result.stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    common = Path(text)
    if not common.is_absolute():
        common = path / common
    return common.resolve()


def _git_head_branch(path: Path) -> str | None:
    result = run_cmd(["git", "-C", str(path), "symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip() or None


def _git_head_commit(path: Path) -> str | None:
    result = run_cmd(["git", "-C", str(path), "rev-parse", "--verify", "HEAD^{commit}"], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip() or None


def cmd_context_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--path",))
    require_options_at_most_once(args, ("--path",))
    require_positional_count(args, 0, "context show accepts no positional arguments")
    target = normalize_path(Path(command_arg(args, "--path", default=".") or "."))
    found = find_marker(target)
    if found is None:
        raise AlabError("CONTEXT_NOT_FOUND", "context marker not found")
    root, marker = found
    conn = require_home(req.globals.home)
    try:
        home = one(conn, "SELECT home_id FROM homes LIMIT 1")
        if home is None or marker.get("home_id") != home["home_id"]:
            raise AlabError("CONTEXT_CONFLICT", "context marker belongs to a different ALab home")
        exact = one(conn, "SELECT * FROM path_registry WHERE path_hash = ? AND status = 'active'", (path_hash(root),))
        related = exact or _registry_row_for_marker(conn, marker)
        registered = bool(exact)
        if exact:
            path_status = "present" if root.exists() else "missing"
        elif related:
            related_path = Path(related["path"])
            path_status = "moved" if not related_path.exists() else "conflict"
        else:
            path_status = "unregistered"
        return [
            ResultBlock(
                "context",
                [
                    ("path", str(target)),
                    ("resolved path", str(root)),
                    ("home id", marker.get("home_id")),
                    ("context type", marker.get("context_type")),
                    ("project id", marker.get("project_id")),
                    ("exp id", marker.get("exp_id")),
                    ("token id", marker.get("token_id")),
                    ("registered", registered),
                    ("path status", path_status),
                    ("next", _context_next(marker.get("context_type"))),
                ],
            )
        ]
    finally:
        conn.close()


def _read_exact_marker(path: Path) -> dict[str, Any]:
    marker_file = marker_path(path)
    if not marker_file.exists():
        raise AlabError("CONTEXT_NOT_FOUND", "context marker not found at --path")
    return context_marker_obj(marker_file.read_text(encoding="utf-8"))


def _authorize_context_repair(req: Request, conn, marker: dict[str, Any], target: Path, existing: Any | None) -> tuple[Actor, str]:
    project_id = marker.get("project_id")
    exp_id = marker.get("exp_id")
    context_type = marker.get("context_type")
    token_id = marker.get("token_id")
    raw = req.globals.key
    if raw:
        return verify_raw_credential(conn, raw, required=("root", "admin"), project_id=project_id), "admin"
    if context_type == "project":
        raw = os.environ.get("ALAB_KEY")
        if raw:
            return verify_raw_credential(conn, raw, required=("root", "admin"), project_id=project_id), "admin"
        raise AlabError("AUTH_REQUIRED", "context repair requires admin/root key or matching self token")
    if context_type not in {"experiment", "inspection"} or not token_id:
        raise AlabError("AUTH_REQUIRED", "context repair requires admin/root key or matching self token")
    token = read_token(target)
    actor = verify_raw_credential(
        conn,
        token,
        required="token",
        project_id=project_id,
        exp_id=exp_id,
        token_mode="worktree" if context_type == "experiment" else "inspection",
    )
    if actor.credential_id != token_id:
        raise AlabError("AUTH_DENIED", "token does not match context marker")
    if existing is None:
        raise AlabError("CONTEXT_CONFLICT", "self-repair requires an existing registry row")
    old_path = Path(existing["path"])
    if normalize_path(old_path) != target and old_path.exists():
        raise AlabError("CONTEXT_CONFLICT", "registered path still exists")
    _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project_id)
    common_dir = _git_common_dir(target)
    if common_dir is None or common_dir != repo_git.resolve():
        raise AlabError("CONTEXT_CONFLICT", "self-repair target is not an ALab project Git worktree")
    if context_type == "experiment":
        exp_row = one(conn, "SELECT branch_name FROM experiments WHERE project_id = ? AND exp_id = ?", (project_id, exp_id))
        if exp_row is None:
            raise AlabError("CONTEXT_CONFLICT", "experiment not found for context repair")
        if _git_head_branch(target) != exp_row["branch_name"]:
            raise AlabError("CONTEXT_CONFLICT", "self-repair requires the registered experiment branch")
    else:
        credential = one(conn, "SELECT metadata_json FROM credentials WHERE credential_id = ?", (token_id,))
        if credential:
            credential_metadata_obj(
                credential["metadata_json"],
                credential_type="token",
                token_mode="inspection",
                registered_path_hash=existing["path_hash"],
            )
        expected_commit = marker.get("inspection_commit")
        if not expected_commit:
            raise AlabError("CONTEXT_CONFLICT", "inspection repair requires a pinned commit")
        if _git_head_commit(target) != expected_commit:
            raise AlabError("CONTEXT_CONFLICT", "self-repair requires the pinned inspection commit")
    return actor, "self-token"


def cmd_context_repair(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--path",))
    require_options_at_most_once(args, ("--path",))
    target = normalize_path(Path(command_arg(args, "--path", required=True)))
    require_positional_count(args, 0, "context repair accepts no positional arguments")
    marker = _read_exact_marker(target)
    context_type = marker.get("context_type")
    if context_type not in {"project", "experiment", "inspection"}:
        raise AlabError("CONTEXT_CONFLICT", "context marker has invalid context_type")
    project_id = marker.get("project_id")
    if not project_id:
        raise AlabError("CONTEXT_CONFLICT", "context marker has no project_id")
    conn = require_home(req.globals.home)
    try:
        home = one(conn, "SELECT home_id FROM homes LIMIT 1")
        if home is None or marker.get("home_id") != home["home_id"]:
            raise AlabError("CONTEXT_CONFLICT", "context marker belongs to a different ALab home")
        existing = _registry_row_for_marker(conn, marker)
        actor, repair_mode = _authorize_context_repair(req, conn, marker, target, existing)
        target_hash = path_hash(target)
        occupied = one(conn, "SELECT * FROM path_registry WHERE path_hash = ? AND status = 'active'", (target_hash,))
        if occupied and (existing is None or occupied["path_registry_id"] != existing["path_registry_id"]):
            raise AlabError("CONTEXT_CONFLICT", "target path is already registered")
    finally:
        conn.close()
    with Database(req.globals.home).tx() as tx:
        now = utc_now()
        previous_path_hash = existing["path_hash"] if existing else None
        if existing:
            path_registry_id = existing["path_registry_id"]
            created_registry_row = False
            tx.execute(
                """
                UPDATE path_registry
                SET path = ?, path_hash = ?, status = 'active', removed_at = NULL, removed_by_credential_id = NULL, updated_at = ?
                WHERE path_registry_id = ?
                """,
                (str(target), target_hash, now, existing["path_registry_id"]),
            )
        else:
            path_registry_id = new_id("path", "repair")
            created_registry_row = True
            tx.execute(
                """
                INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id,
                  exp_id, token_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    path_registry_id,
                    target_hash,
                    str(target),
                    context_type,
                    marker["home_id"],
                    project_id,
                    marker.get("exp_id"),
                    marker.get("token_id"),
                    now,
                    now,
                ),
            )
        marker["repaired_at"] = now
        write_marker(target, marker)
        audit_object_type = {"project": "project", "experiment": "worktree", "inspection": "inspection_checkout"}[context_type]
        audit_object_id = marker.get("token_id") if context_type == "inspection" else marker.get("exp_id") or project_id
        audit(
            tx,
            action="repair",
            object_type=audit_object_type,
            object_id=audit_object_id,
            actor=actor,
            project_id=project_id,
            exp_id=marker.get("exp_id"),
            metadata={
                "schema_version": 1,
                "context_type": context_type,
                "repair_mode": repair_mode,
                "path_registry_id": path_registry_id,
                "previous_path_hash": previous_path_hash,
                "repaired_path_hash": target_hash,
                "created_registry_row": created_registry_row,
                "repaired_at": now,
            },
        )
    return [
        ResultBlock(
            "context",
            [
                ("path", str(target)),
                ("resolved path", str(target)),
                ("context type", context_type),
                ("project id", project_id),
                ("exp id", marker.get("exp_id")),
                ("repair mode", repair_mode),
                ("status", "repaired"),
            ],
        )
    ]


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


def _source_origin_mode(args: list[str]) -> str:
    selected = _source_origin_options(args)
    if len(selected) != 1:
        raise AlabError("SOURCE_INVALID", "exactly one source origin is required")
    if selected[0] == "--source-empty" and command_arg(args, "--source-subdir"):
        raise AlabError("SOURCE_INVALID", "--source-subdir conflicts with --source-empty")
    return {"--source-path": "local", "--source-git": "git", "--source-empty": "empty"}[selected[0]]


def _assert_source_import_no_existing_source_selectors(args: list[str]) -> None:
    for option in ("--source-ref", "--from-exp", "--from-commit"):
        if command_arg(args, option) is not None:
            raise AlabError("SOURCE_INVALID", f"{option} is not valid for source import")


def _derived_source_name(args: list[str], mode: str, *, use_explicit_name: bool = True) -> str:
    explicit = command_arg(args, "--name") if use_explicit_name else None
    if explicit:
        return explicit
    if mode == "empty":
        return "empty"
    if mode == "local":
        source_path = Path(command_arg(args, "--source-path", required=True))
        return source_path.name or "local"
    source_git = command_arg(args, "--source-git", required=True)
    name = Path(source_git.rstrip("/")).name
    if name.endswith(".git"):
        name = name[:-4]
    git_ref = command_arg(args, "--git-ref")
    return f"{name}-{git_ref}" if git_ref else name or "git"


def _origin_metadata(origin_type: str, safe_summary: str, now: str, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "origin_type": origin_type,
        "safe_summary": safe_summary,
        "exact": {},
        "warnings": warnings or [],
        "created_at": now,
    }


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


def _optional_request_actor(req: Request, project_id: str | None) -> Actor | None:
    conn = require_home(req.globals.home)
    try:
        raw = req.globals.key
        if raw:
            actor = req.actor or verify_raw_credential(conn, raw)
            if actor.actor_type == "root" or project_id is None or actor.project_id == project_id:
                return actor
            return None
        if req.context and req.context.context_type in {"experiment", "inspection"}:
            try:
                token = read_token(req.context.path)
                return verify_raw_credential(
                    conn,
                    token,
                    required="token",
                    project_id=req.context.project_id,
                    exp_id=req.context.exp_id,
                    token_mode="worktree" if req.context.context_type == "experiment" else "inspection",
                    path_hash=req.context.path_hash,
                )
            except AlabError:
                return None
        return None
    finally:
        conn.close()


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


def cmd_exp_create(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--name",
            "--goal",
            "--path",
            "--tag",
            "--source-ref",
            "--source-path",
            "--source-git",
            "--source-empty",
            "--git-ref",
            "--source-subdir",
            "--from-exp",
            "--from-commit",
            "--mutable-include",
            "--mutable-exclude",
            "--visibility-scope",
            "--visible-exp",
            "--max-files",
            "--max-total-bytes",
            "--max-file-bytes",
        ),
    )
    require_options_at_most_once(
        args,
        (
            "--project",
            "--name",
            "--goal",
            "--path",
            "--source-ref",
            "--source-path",
            "--source-git",
            "--source-empty",
            "--git-ref",
            "--source-subdir",
            "--from-exp",
            "--from-commit",
            "--visibility-scope",
            "--max-files",
            "--max-total-bytes",
            "--max-file-bytes",
        ),
    )
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    name = command_arg(args, "--name", required=True)
    _assert_display_name("experiment name", name)
    goal = command_arg(args, "--goal")
    if goal is not None:
        _assert_utf8_max_bytes("experiment goal", goal, 65536)
    tag_slugs = [_tag_slug(tag) for tag in command_args(args, "--tag")]
    visibility_override = _experiment_visibility_override(args)
    mutable_override = _experiment_mutable_override(args)
    from_exp_id = command_arg(args, "--from-exp")
    from_commit_selector = command_arg(args, "--from-commit")
    source_origins = _source_origin_options(args, include_ref=True)
    inline_source_origins = [origin for origin in source_origins if origin != "--source-ref"]
    if from_exp_id and source_origins:
        raise AlabError("SOURCE_INVALID", "--from-exp conflicts with source selectors")
    if from_commit_selector and not from_exp_id:
        raise AlabError("CONFIG_INVALID", "--from-commit requires --from-exp")
    from_commit_selector = _exp_commit_selector_filter(from_commit_selector)
    if len(source_origins) > 1:
        raise AlabError("SOURCE_INVALID", "exactly one source origin is allowed")
    source_limits = _source_import_limits(args)
    require_positional_count(args, 0, "exp create accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        cfg, _, cfg_json = _load_config_and_secrets(conn, project["project_id"], project["active_valid_config_version"] or 0)
        if project["status"] == "archived":
            raise AlabError("PROJECT_ARCHIVED", "project is archived")
        if project["status"] != "valid":
            raise AlabError("PROJECT_INVALID", "new experiments require a valid project")
        actor = _optional_request_actor(req, project_id)
        if not cfg.project.allow_public_exp_create:
            actor = require_actor(req, ("root", "admin"), project_id=project_id)
        exp_slug = slugify(name, "experiment")
        if one(conn, "SELECT exp_id FROM experiments WHERE project_id = ? AND json_extract(metadata_json,'$.name_slug') = ?", (project_id, exp_slug)):
            raise AlabError("NAME_CONFLICT", "experiment name already exists")
        exp_id = new_id("exp", name)
        _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project_id)
        worktree_path_raw = command_arg(args, "--path")
        worktree_path = Path(worktree_path_raw).expanduser().resolve() if worktree_path_raw else (Path.cwd() / f"{project_id}_{exp_id}").resolve()
        if worktree_path_raw:
            _assert_new_context_path(conn, target=worktree_path, project_id=project_id, context_type="experiment", label="experiment worktree")
        else:
            _assert_missing_path(
                worktree_path,
                "default experiment worktree",
                next_action="pass --path <dir> to choose a custom worktree location",
            )
            _assert_context_path_nesting(conn, target=worktree_path, project_id=project_id, context_type="experiment")
        explicit_source_selector = command_arg(args, "--source-ref")
        source_selector = explicit_source_selector or cfg.source.default_source_ref
        source_exp = None
        origin_kind = "source"
        inline_warnings: list[str] = []
        if from_exp_id:
            source_exp = _exp_row(conn, project_id, from_exp_id)
            if source_exp["status"] == "archived" and not (actor and actor.actor_type in {"root", "admin"}):
                raise AlabError("SCOPE_VIOLATION", "archived source experiments require root/admin for --from-exp")
            if actor and actor.actor_type in {"root", "admin"}:
                pass
            elif actor and actor.actor_type == "token":
                if source_exp["status"] not in {"open", "closed"} or not _exp_visible(conn, project_id, actor, source_exp["exp_id"]):
                    raise AlabError("SCOPE_VIOLATION", "source experiment is not visible to this token")
            elif not _public_from_exp_visible(conn, project, source_exp):
                raise AlabError("SCOPE_VIOLATION", "source experiment is not visible for public inheritance")
            source = one(conn, "SELECT * FROM sources WHERE project_id = ? AND source_id = ?", (project_id, source_exp["source_id"]))
            if source is None:
                raise AlabError("SOURCE_NOT_FOUND", "source not found")
            baseline_commit = _resolve_exp_commit(conn, req.globals.home, project_id, source_exp, from_commit_selector or "latest")
            source_selector = from_exp_id
            origin_kind = "from_exp"
        elif inline_source_origins:
            mode = _source_origin_mode(args)
            public_caller = not (actor and actor.actor_type in {"root", "admin"})
            if public_caller and not cfg.public_source_import.enabled:
                actor = require_actor(req, ("root", "admin"), project_id=project_id)
                public_caller = False
            limits = (
                _source_import_limits(
                    args,
                    public_config=cfg.public_source_import,
                    public_caller=True,
                )
                if public_caller
                else source_limits
            )
            operation_dir = req.globals.home.tmp_path / "inline-source-import" / new_id("op", mode)
            operation_dir.mkdir(parents=True, exist_ok=True)
            try:
                prepared_source = _prepare_source_work(args, mode, operation_dir, public_caller=public_caller)
                inline_result = _import_prepared_source_snapshot(
                    home=req.globals.home,
                    project_id=project_id,
                    repo_git=repo_git,
                    cfg=cfg,
                    actor=actor,
                    prepared_source=prepared_source,
                    source_name=_derived_source_name(args, mode, use_explicit_name=False),
                    limits=limits,
                    allow_name_suffix=True,
                )
            finally:
                shutil.rmtree(operation_dir, ignore_errors=True)
            source = {
                "source_id": inline_result.source_id,
                "source_ref": inline_result.source_ref,
                "source_commit": inline_result.source_commit,
                "tree_hash": inline_result.tree_hash,
            }
            baseline_commit = inline_result.source_commit
            source_selector = inline_result.source_ref
            origin_kind = "inline_source"
            inline_warnings = inline_result.warnings
        else:
            if explicit_source_selector:
                source = one(
                    conn,
                    "SELECT * FROM sources WHERE project_id = ? AND (source_ref = ? OR source_id = ?)",
                    (project_id, source_selector, source_selector),
                )
                if source and source["status"] == "archived" and not (actor and actor.actor_type in {"root", "admin"}):
                    actor = require_actor(req, ("root", "admin"), project_id=project_id)
            else:
                source = one(
                    conn,
                    "SELECT * FROM sources WHERE project_id = ? AND (source_ref = ? OR source_id = ?) AND status = 'active'",
                    (project_id, source_selector, source_selector),
                )
            if source is None:
                raise AlabError("SOURCE_NOT_FOUND", "source not found")
            baseline_commit = source["source_commit"]
        branch = f"alab/exp/{exp_id}"
        start_ref = baseline_commit if from_exp_id else f"refs/heads/alab/source/{source['source_id']}"
        run_cmd(["git", f"--git-dir={repo_git}", "worktree", "add", "-b", branch, str(worktree_path), start_ref])
        with Database(req.globals.home).tx() as tx:
            home_id = one(tx, "SELECT home_id FROM homes LIMIT 1")["home_id"]
            token_id, raw_token = create_credential(
                tx,
                credential_type="token",
                project_id=project_id,
                exp_id=exp_id,
                token_mode="worktree",
                registered_path_hash=path_hash(worktree_path),
                metadata={"schema_version": 1, "token_mode": "worktree", "created_for_path_hash": path_hash(worktree_path)},
            )
            write_marker(
                worktree_path,
                {
                    "marker_version": 1,
                    "home_id": home_id,
                    "context_type": "experiment",
                    "project_id": project_id,
                    "exp_id": exp_id,
                    "token_id": token_id,
                    "created_at": utc_now(),
                },
            )
            write_token(worktree_path, raw_token)
            _write_git_exclude(worktree_path)
            now = utc_now()
            metadata = {
                "schema_version": 1,
                "name": name,
                "name_slug": exp_slug,
                "goal": goal,
                "creation_origin": (
                    {
                        "kind": "from_exp",
                        "source_exp_id": source_exp["exp_id"] if source_exp else None,
                        "from_commit": from_commit_selector or "latest",
                        "resolved_commit": baseline_commit,
                        "source_id": source["source_id"],
                    }
                    if origin_kind == "from_exp"
                    else {"kind": "inline_source", "source_id": source["source_id"], "source_ref": source_selector}
                    if origin_kind == "inline_source"
                    else {"kind": "source", "source_id": source["source_id"]}
                ),
                "requested_path": str(worktree_path),
                "source_selector": source_selector,
                "display": {"safe_summary": name},
            }
            visibility_upper_bound = cfg_json["visibility"]
            if visibility_override is not None:
                scope, explicit_ids = _intersect_visibility(visibility_upper_bound, visibility_override)
                visibility_upper_bound = {"schema_version": 1, "scope": scope, "experiment_ids": sorted(explicit_ids)}
            policy = {"schema_version": 1, "mutable": cfg_json["mutable"], "visibility_upper_bound": visibility_upper_bound}
            if mutable_override is not None:
                policy["mutable_override"] = mutable_override
            tx.execute(
                """
                INSERT INTO experiments(exp_id, project_id, source_id, bound_config_version, bound_validation_id,
                  baseline_commit, branch_name, worktree_path, worktree_path_hash, worktree_state, status,
                  pre_archive_status, metadata_json, policy_json, latest_run_id, latest_commit, final_run_id,
                  final_commit, created_at, updated_at, closed_at, archived_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 'open', NULL, ?, ?, NULL, ?, NULL, NULL, ?, ?, NULL, NULL)
                """,
                (
                    exp_id,
                    project_id,
                    source["source_id"],
                    project["active_valid_config_version"],
                    project["active_validation_id"],
                    baseline_commit,
                    branch,
                    str(worktree_path),
                    path_hash(worktree_path),
                    canonical_json(experiment_metadata_obj(canonical_json(metadata))),
                    canonical_json(experiment_policy_json_obj(canonical_json(policy))),
                    baseline_commit,
                    now,
                    now,
                ),
            )
            tx.execute(
                """
                INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id,
                  exp_id, token_id, status, created_at, updated_at)
                VALUES (?, ?, ?, 'experiment', ?, ?, ?, ?, 'active', ?, ?)
                """,
                (new_id("path", "experiment"), path_hash(worktree_path), str(worktree_path), home_id, project_id, exp_id, token_id, now, now),
            )
            for tag_slug in tag_slugs:
                tx.execute(
                    "INSERT OR IGNORE INTO experiment_tags(project_id, exp_id, tag_slug, created_by_type, created_by_id, created_at) VALUES (?, ?, ?, 'token', ?, ?)",
                    (project_id, exp_id, tag_slug, token_id, now),
                )
        return [
            ResultBlock(
                "experiment",
                [
                    ("project id", project_id),
                    ("exp id", exp_id),
                    ("experiment name", name),
                    ("source id", source["source_id"]),
                    ("branch", branch),
                    ("worktree path", str(worktree_path)),
                    ("token path", str(worktree_path / ".alab" / "token")),
                    ("config version", project["active_valid_config_version"]),
                    ("warning", inline_warnings),
                    ("next", f"cd {worktree_path} && alab run --message <message>"),
                ],
            )
        ]
    finally:
        conn.close()


def _require_experiment_context(req: Request) -> tuple[Any, Any, Actor, ProjectConfig, dict[str, str]]:
    if req.context is None or req.context.context_type != "experiment":
        raise AlabError("CONTEXT_NOT_FOUND", "command must run inside an experiment worktree")
    conn = require_home(req.globals.home)
    try:
        token = read_token(req.context.path)
        actor = verify_raw_credential(conn, token, required="token", project_id=req.context.project_id, exp_id=req.context.exp_id, token_mode="worktree", path_hash=req.context.path_hash)
        exp = one(conn, "SELECT * FROM experiments WHERE exp_id = ?", (req.context.exp_id,))
        if exp is None:
            raise AlabError("EXPERIMENT_NOT_FOUND", "experiment not found")
        project = _project_row(conn, req.context.project_id)
        cfg, secrets_map, _ = _load_config_and_secrets(conn, project["project_id"], exp["bound_config_version"])
        return project, exp, actor, cfg, secrets_map
    finally:
        conn.close()


def _record_scope_violation_run(
    req: Request,
    project: Any,
    exp: Any,
    cfg: ProjectConfig,
    *,
    run_id: str,
    commit: str,
    reason: str,
    violation_paths: list[str],
    rolled_back_commit: str | None = None,
) -> RunExecutionSummary:
    now = utc_now()
    with Database(req.globals.home).tx() as conn:
        record_json = _execution_record_object_json(
            config_hash_value=_config_hash_for_version(conn, project["project_id"], exp["bound_config_version"]),
            runner_type=cfg.runner.type,
            reward_type=cfg.reward.type,
            failure=reason,
            extra={
                "mutable_scope": {
                    "schema_version": 1,
                    "error_code": "SCOPE_VIOLATION",
                    "violation_paths": violation_paths,
                    "rolled_back_commit": rolled_back_commit,
                }
            },
        )
        updated = conn.execute(
            """
            UPDATE runs
            SET commit_sha = ?, status = 'error', exit_code = NULL, reward_value = NULL,
              reward_parse_status = 'not_attempted', ended_at = ?, record_json = ?
            WHERE run_id = ?
            """,
            (commit, now, record_json, run_id),
        ).rowcount
        if updated == 0:
            conn.execute(
                """
                INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, exit_code,
                  reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
                VALUES (?, ?, ?, ?, ?, 'error', NULL, NULL, 'not_attempted', 'active', ?, ?, ?)
                """,
                (run_id, exp["exp_id"], project["project_id"], commit, exp["bound_config_version"], now, now, record_json),
            )
        conn.execute("UPDATE experiments SET latest_run_id = ?, latest_commit = ?, updated_at = ? WHERE exp_id = ?", (run_id, commit, now, exp["exp_id"]))
    return RunExecutionSummary(
        run_id=run_id,
        commit=commit,
        created_commit=False,
        status="error",
        reward=None,
        reward_parse_status="not_attempted",
        exit_code=None,
        stdout_preview="",
        stderr_preview=f"SCOPE_VIOLATION: {reason}",
        artifact_count=0,
        failure_reason=reason,
        warning_codes=[],
    )


def _insert_running_run_record(req: Request, project: Any, exp: Any, cfg: ProjectConfig, *, run_id: str, commit: str) -> None:
    with Database(req.globals.home).tx() as conn:
        now = utc_now()
        conn.execute(
            """
            INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, exit_code,
              reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
            VALUES (?, ?, ?, ?, ?, 'running', NULL, NULL, 'not_attempted', 'active', ?, NULL, ?)
            """,
            (
                run_id,
                exp["exp_id"],
                project["project_id"],
                commit,
                exp["bound_config_version"],
                now,
                _execution_record_object_json(
                    config_hash_value=_config_hash_for_version(conn, project["project_id"], exp["bound_config_version"]),
                    runner_type=cfg.runner.type,
                    reward_type=cfg.reward.type,
                ),
            ),
        )


def _run_experiment(req: Request, message: str) -> RunExecutionSummary:
    project, exp, actor, cfg, secrets_map = _require_experiment_context(req)
    with Database(req.globals.home).tx() as conn:
        _interrupt_stale_running_records(conn, project_id=project["project_id"], exp_id=exp["exp_id"])
    if project["status"] == "archived":
        raise AlabError("PROJECT_ARCHIVED", "project is archived")
    if exp["status"] != "open":
        raise AlabError("EXPERIMENT_CLOSED", "experiment is not open")
    if exp["worktree_state"] != "active":
        raise AlabError("SCOPE_VIOLATION", "experiment worktree is removed")
    worktree = Path(exp["worktree_path"])
    run_id = new_id("run", "run")
    _assert_experiment_git_state(exp, worktree)
    head_before = run_cmd(["git", "rev-parse", "HEAD"], cwd=worktree).stdout.decode().strip()
    committed_paths = _changed_paths(worktree, "diff", f"{exp['baseline_commit']}..{head_before}")
    blocked_committed = _mutable_blocked_paths(exp, committed_paths)
    if blocked_committed:
        return _record_scope_violation_run(
            req,
            project,
            exp,
            cfg,
            run_id=run_id,
            commit=head_before,
            reason=_mutable_scope_reason(blocked_committed, "committed changes"),
            violation_paths=blocked_committed,
        )
    dirty_paths = _dirty_paths(worktree)
    _assert_mutable_paths_allowed(exp, dirty_paths, "worktree changes")
    created_commit = bool(dirty_paths)
    running_record_inserted = False
    if created_commit:
        _insert_running_run_record(req, project, exp, cfg, run_id=run_id, commit=head_before)
        running_record_inserted = True
        run_cmd(["git", "config", "user.name", cfg.git.author_name], cwd=worktree)
        run_cmd(["git", "config", "user.email", cfg.git.author_email], cwd=worktree)
        run_cmd(["git", "config", "commit.gpgsign", "false"], cwd=worktree)
        run_cmd(["git", "add", "-A"], cwd=worktree)
        run_cmd(
            ["git", "commit", "-m", f"ALab run: {message}", "-m", f"ALab-Run: {run_id}\nALab-Experiment: {exp['exp_id']}\nALab-Config-Version: {exp['bound_config_version']}"],
            cwd=worktree,
            env=_git_commit_identity_env(cfg.git.author_name, cfg.git.author_email),
        )
    commit = run_cmd(["git", "rev-parse", "HEAD"], cwd=worktree).stdout.decode().strip()
    committed_paths_after = _changed_paths(worktree, "diff", f"{exp['baseline_commit']}..{commit}")
    blocked_committed_after = _mutable_blocked_paths(exp, committed_paths_after)
    if blocked_committed_after:
        rolled_back_commit = commit if created_commit else None
        if created_commit:
            run_cmd(["git", "reset", "--mixed", "HEAD^"], cwd=worktree, check=False)
        return _record_scope_violation_run(
            req,
            project,
            exp,
            cfg,
            run_id=run_id,
            commit=commit,
            reason=_mutable_scope_reason(blocked_committed_after, "committed changes"),
            violation_paths=blocked_committed_after,
            rolled_back_commit=rolled_back_commit,
        )
    if not running_record_inserted:
        _insert_running_run_record(req, project, exp, cfg, run_id=run_id, commit=commit)
    elif commit != head_before:
        with Database(req.globals.home).tx() as conn:
            conn.execute("UPDATE runs SET commit_sha = ? WHERE run_id = ?", (commit, run_id))

    _project_root, repo_git, artifact_store = _project_paths(req.globals.home, project["project_id"])
    operation_dir = req.globals.home.tmp_path / project["project_id"] / run_id
    workspace = operation_dir / "workspace"
    run_dir = operation_dir / "run"
    hidden_dir = operation_dir / "hidden"

    def adapter_resolver(ref: str) -> dict[str, Any]:
        conn = require_home(req.globals.home)
        try:
            return _resolve_runner_adapter_ref(conn, ref)
        finally:
            conn.close()

    try:
        clean_copy_from_git(repo_git, commit, workspace)
        result = run_configured_runner(
            config=cfg,
            workspace=workspace,
            run_dir=run_dir,
            operation_id=run_id,
            secrets=secrets_map,
            project_id=project["project_id"],
            exp_id=exp["exp_id"],
            config_version=exp["bound_config_version"],
            hidden_dir=hidden_dir,
            cache_dir=req.globals.home.cache_path / "skydiscover-python-envs",
            adapter_resolver=adapter_resolver,
        )
        preview_limit = _global_preview_bytes(req.globals.home)
        stdout_rel, stdout_size, stdout_stored, stdout_hash, stdout_preview, stdout_trunc = store_log_file(
            artifact_store,
            project["project_id"],
            run_id,
            "stdout",
            result.stdout,
            cfg.logs.stdout_limit_bytes,
            preview_limit,
        )
        stderr_rel, stderr_size, stderr_stored, stderr_hash, stderr_preview, stderr_trunc = store_log_file(
            artifact_store,
            project["project_id"],
            run_id,
            "stderr",
            result.stderr,
            cfg.logs.stderr_limit_bytes,
            preview_limit,
        )
        log_records = [
            ("stdout", stdout_rel, stdout_size, stdout_stored, stdout_hash, stdout_preview, stdout_trunc, 0),
            ("stderr", stderr_rel, stderr_size, stderr_stored, stderr_hash, stderr_preview, stderr_trunc, 0),
        ]
        for stream, data, limit in [
            ("hidden_stdout", result.hidden_stdout, cfg.logs.stdout_limit_bytes),
            ("hidden_stderr", result.hidden_stderr, cfg.logs.stderr_limit_bytes),
        ]:
            if not data:
                continue
            rel, size, stored, digest, preview, trunc = store_log_file(artifact_store, project["project_id"], run_id, stream, data, limit, preview_limit)
            log_records.append((stream, rel, size, stored, digest, preview, trunc, 1))
        artifacts = capture_artifacts(config=cfg, workspace=workspace, run_dir=run_dir, artifact_store=artifact_store, project_id=project["project_id"], exp_id=exp["exp_id"], run_id=run_id, validation_id=None)
        warning_codes = _merge_warnings(result.warning_codes or [], _artifact_capture_warning_codes(artifacts))
        ended = utc_now()
        failure_reason = _runner_failure_reason(result.status, result.exit_code, result.reward_parse_status, result.failure_reason)
        with Database(req.globals.home).tx() as conn:
            _record_runner_cache(conn, result, project["project_id"])
            record_json = _execution_record_object_json(
                config_hash_value=_config_hash_for_version(conn, project["project_id"], exp["bound_config_version"]),
                runner_type=cfg.runner.type,
                reward_type=cfg.reward.type,
                reward_value=result.reward,
                metrics=result.metrics,
                warnings=warning_codes,
                failure=failure_reason,
                timeout=result.status == "timeout",
                adapter_feedback=result.adapter_feedback,
            )
            conn.execute(
                "UPDATE runs SET commit_sha = ?, status = ?, exit_code = ?, reward_value = ?, reward_parse_status = ?, ended_at = ?, record_json = ? WHERE run_id = ?",
                (commit, result.status, result.exit_code, result.reward, result.reward_parse_status, ended, record_json, run_id),
            )
            conn.execute("UPDATE experiments SET latest_run_id = ?, latest_commit = ?, updated_at = ? WHERE exp_id = ?", (run_id, commit, ended, exp["exp_id"]))
            for stream, rel, size, stored, digest, preview, trunc, hidden in log_records:
                conn.execute(
                    """
                    INSERT INTO log_streams(log_id, project_id, exp_id, run_id, validation_id, stream, size_bytes,
                      stored_bytes, content_hash, truncated, hidden, archive_status, file_path, preview_text, created_at)
                    VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                    """,
                    (new_id("log", stream), project["project_id"], exp["exp_id"], run_id, stream, size, stored, digest, 1 if trunc else 0, hidden, rel, preview, ended),
                )
            for artifact in artifacts:
                conn.execute(
                    """
                    INSERT INTO artifacts(artifact_id, project_id, exp_id, run_id, validation_id, root, relative_path,
                      size_bytes, content_hash, status, archive_status, blob_path, capture_error, created_at)
                    VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                    """,
                    (
                        artifact["artifact_id"],
                        project["project_id"],
                        exp["exp_id"],
                        run_id,
                        artifact["root"],
                        artifact["relative_path"],
                        artifact["size_bytes"],
                        artifact["content_hash"],
                        artifact["status"],
                        artifact["blob_path"],
                        artifact["capture_error"],
                        ended,
                    ),
                )
            return RunExecutionSummary(
                run_id=run_id,
                commit=commit,
                created_commit=created_commit,
                status=result.status,
                reward=result.reward,
                reward_parse_status=result.reward_parse_status,
                exit_code=result.exit_code,
                stdout_preview=stdout_preview,
                stderr_preview=stderr_preview,
                artifact_count=len(artifacts),
                failure_reason=failure_reason,
                warning_codes=warning_codes,
            )
    finally:
        try:
            run_cmd(["git", f"--git-dir={repo_git}", "worktree", "remove", "--force", str(workspace)], check=False)
        except Exception:
            pass
        shutil.rmtree(operation_dir, ignore_errors=True)


def cmd_run(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--message",))
    require_options_at_most_once(args, ("--message",))
    message = command_arg(args, "--message", required=True)
    _assert_utf8_max_bytes("run message", message, 300)
    require_positional_count(args, 0, "run accepts no positional arguments")
    project, exp, _actor, _cfg, _secrets_map = _require_experiment_context(req)
    if project["status"] == "archived":
        raise AlabError("PROJECT_ARCHIVED", "project is archived")
    if exp["status"] != "open":
        raise AlabError("EXPERIMENT_CLOSED", "experiment is not open")
    if exp["worktree_state"] != "active":
        raise AlabError("SCOPE_VIOLATION", "experiment worktree is removed")
    operation_lock = _acquire_experiment_run_submit_lock(req.globals.home, project_id=project["project_id"], exp_id=exp["exp_id"])
    try:
        summary = _run_experiment(req, message)
    finally:
        _release_experiment_run_submit_lock(req.globals.home, operation_lock)
    next_action = "alab submit --message <message> --summary <text> --feedback <text> --ref none"
    fields: list[tuple[str, Any]] = [
        ("run id", summary.run_id),
        ("exp id", req.context.exp_id if req.context else None),
        ("commit", summary.commit),
        ("created commit", summary.created_commit),
        ("run status", summary.status),
        ("exit code", summary.exit_code),
        ("reward", summary.reward),
        ("reward parse status", summary.reward_parse_status),
        ("stdout preview", summary.stdout_preview),
        ("stderr preview", summary.stderr_preview),
        ("artifact count", summary.artifact_count),
        ("warning code", summary.warning_codes),
    ]
    failure_fields = _run_failure_fields(summary, next_action)
    if failure_fields:
        fields.extend(failure_fields)
    else:
        fields.append(("next", next_action))
    return [ResultBlock("run", fields)]


def cmd_submit(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--message",
            "--rerun",
            "--summary",
            "--summary-file",
            "--summary-stdin",
            "--feedback",
            "--feedback-file",
            "--feedback-stdin",
            "--ref",
        ),
    )
    require_options_at_most_once(args, ("--message", "--rerun", "--summary-stdin", "--feedback-stdin"))
    message = command_arg(args, "--message", required=True)
    _assert_utf8_max_bytes("submit message", message, 300)
    for unsupported in ("--summary-stdin", "--feedback-stdin"):
        if flag(args, unsupported):
            raise AlabError("CONFIG_INVALID", f"{unsupported} is not supported; use direct text or file input")
    require_exactly_one_option_pair(args, "--summary", "--summary-file", "submit requires exactly one of --summary or --summary-file")
    require_exactly_one_option_pair(args, "--feedback", "--feedback-file", "submit requires exactly one of --feedback or --feedback-file")
    summary_arg = command_arg(args, "--summary")
    summary_file = command_arg(args, "--summary-file")
    feedback_arg = command_arg(args, "--feedback")
    feedback_file = command_arg(args, "--feedback-file")
    refs = command_args(args, "--ref")
    if not refs:
        raise AlabError("CONFIG_INVALID", "submit requires at least one --ref")
    if any(ref.startswith("--") for ref in refs):
        raise AlabError("CONFIG_INVALID", "--ref requires a value")
    deduped_refs: list[str] = []
    seen_refs: set[str] = set()
    for ref in refs:
        if ref not in seen_refs:
            deduped_refs.append(ref)
            seen_refs.add(ref)
    refs = deduped_refs
    if "none" in refs and len(refs) > 1:
        raise AlabError("CONFIG_INVALID", "--ref none conflicts with experiment refs")
    require_positional_count(args, 0, "submit accepts no positional arguments")
    summary = _read_text_input_file(summary_file, "submit summary") if summary_file else summary_arg or ""
    feedback = _read_text_input_file(feedback_file, "submit feedback") if feedback_file else feedback_arg or ""
    _assert_utf8_max_bytes("submit summary", summary, 65536)
    _assert_utf8_max_bytes("submit feedback", feedback, 65536)
    project, exp, actor, _cfg, _secrets_map = _require_experiment_context(req)
    if project["status"] == "archived":
        raise AlabError("PROJECT_ARCHIVED", "project is archived")
    if exp["status"] != "open":
        raise AlabError("EXPERIMENT_CLOSED", "experiment is not open")
    if exp["worktree_state"] != "active":
        raise AlabError("SCOPE_VIOLATION", "experiment worktree is removed")
    operation_lock = _acquire_experiment_run_submit_lock(req.globals.home, project_id=project["project_id"], exp_id=exp["exp_id"])
    try:
        with Database(req.globals.home).tx() as conn:
            _interrupt_stale_running_records(conn, project_id=project["project_id"], exp_id=exp["exp_id"])
            _assert_text_has_no_secret(conn, project["project_id"], exp["exp_id"], summary, "submit summary")
            _assert_text_has_no_secret(conn, project["project_id"], exp["exp_id"], feedback, "submit feedback")
            for ref in refs:
                if ref == "none":
                    continue
                ref_id = _complete_id_or_missing(ref, prefix="exp", code="EXPERIMENT_NOT_FOUND", label="ref experiment id")
                ref_row = one(conn, "SELECT exp_id FROM experiments WHERE project_id = ? AND exp_id = ?", (project["project_id"], ref_id))
                if ref_row is None or not _exp_visible(conn, project["project_id"], actor, ref_id):
                    raise AlabError("SCOPE_VIOLATION", "ref experiment is not visible or not found")
        worktree = Path(exp["worktree_path"])
        dirty_paths = _dirty_paths(worktree)
        head = run_cmd(["git", "rev-parse", "HEAD"], cwd=worktree).stdout.decode().strip()
        final_run_id: str | None = None
        final_commit = head
        if dirty_paths or flag(args, "--rerun"):
            run_summary = _run_experiment(req, message)
            final_run_id = run_summary.run_id
            final_commit = run_summary.commit
            if run_summary.status != "passed":
                failure = dict(_run_failure_fields(run_summary, "fix the experiment and rerun alab submit --rerun"))
                reason = f"final run {run_summary.run_id} status is {run_summary.status}"
                if failure.get("reason"):
                    reason = f"{reason}: {failure['reason']}"
                return [_submission_failure_block(exp["exp_id"], refs, str(failure["error code"]), reason, str(failure["next"]))]
        else:
            conn = require_home(req.globals.home)
            try:
                row = one(
                    conn,
                    "SELECT * FROM runs WHERE exp_id = ? AND commit_sha = ? AND config_version = ? AND status = 'passed' ORDER BY ended_at DESC LIMIT 1",
                    (exp["exp_id"], head, exp["bound_config_version"]),
                )
                if row is None:
                    return [
                        _submission_failure_block(
                            exp["exp_id"],
                            refs,
                            "RUNNER_FAILED",
                            "no reusable passed run for current HEAD",
                            "alab submit --rerun ...",
                        )
                    ]
                final_run_id = row["run_id"]
            finally:
                conn.close()
        db = Database(req.globals.home)
        with db.tx() as conn:
            now = utc_now()
            submission_id = new_id("sub", "submission")
            conn.execute(
                """
                INSERT INTO experiment_submissions(submission_id, project_id, exp_id, final_run_id, final_commit,
                  message, summary, feedback, refs_json, created_at, created_by_credential_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission_id,
                    project["project_id"],
                    exp["exp_id"],
                    final_run_id,
                    final_commit,
                    message,
                    summary,
                    feedback,
                    canonical_json(submission_refs_json_obj(canonical_json({"schema_version": 1, "refs": refs}))),
                    now,
                    actor.credential_id,
                ),
            )
            conn.execute(
                "UPDATE experiments SET status = 'closed', final_run_id = ?, final_commit = ?, closed_at = ?, updated_at = ? WHERE exp_id = ?",
                (final_run_id, final_commit, now, now, exp["exp_id"]),
            )
        return [
            ResultBlock(
                "submission",
                [
                    ("exp id", exp["exp_id"]),
                    ("submit accepted", True),
                    ("final run id", final_run_id),
                    ("final commit", final_commit),
                    ("experiment status", "closed"),
                    ("summary stored", True),
                    ("feedback stored", True),
                    ("ref", refs),
                ],
            )
        ]
    finally:
        _release_experiment_run_submit_lock(req.globals.home, operation_lock)


def _parse_limit_offset(args: list[str]) -> tuple[int, int]:
    require_options_at_most_once(args, ("--limit", "--offset"))
    try:
        limit = int(command_arg(args, "--limit", default="50") or "50")
        offset = int(command_arg(args, "--offset", default="0") or "0")
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", "--limit and --offset must be integers") from exc
    if limit < 1 or limit > 500:
        raise AlabError("CONFIG_INVALID", "--limit must be between 1 and 500")
    if offset < 0:
        raise AlabError("CONFIG_INVALID", "--offset must be zero or greater")
    return limit, offset


def _parse_audit_limit_offset(args: list[str]) -> tuple[int, int]:
    require_options_at_most_once(args, ("--limit", "--offset"))
    try:
        limit = int(command_arg(args, "--limit", default="50") or "50")
        offset = int(command_arg(args, "--offset", default="0") or "0")
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", "--limit and --offset must be integers") from exc
    if limit < 1 or limit > 1000:
        raise AlabError("CONFIG_INVALID", "invalid audit pagination")
    if offset < 0:
        raise AlabError("CONFIG_INVALID", "invalid audit pagination")
    return limit, offset


def _parse_float_option(args: list[str], name: str) -> float | None:
    require_options_at_most_once(args, (name,))
    value = command_arg(args, name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", f"{name} must be numeric") from exc


def _parse_int_option(args: list[str], name: str) -> int | None:
    require_options_at_most_once(args, (name,))
    value = command_arg(args, name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", f"{name} must be an integer") from exc


def _parse_non_negative_int_option(args: list[str], name: str) -> int | None:
    value = _parse_int_option(args, name)
    if value is not None and value < 0:
        raise AlabError("CONFIG_INVALID", f"{name} must be zero or greater")
    return value


def _parse_positive_int_option(args: list[str], name: str) -> int | None:
    value = _parse_int_option(args, name)
    if value is not None and value < 1:
        raise AlabError("CONFIG_INVALID", f"{name} must be a positive integer")
    return value


def _require_ordered_range(
    min_value: int | float | None,
    max_value: int | float | None,
    min_name: str,
    max_name: str,
) -> None:
    if min_value is not None and max_value is not None and min_value > max_value:
        raise AlabError("CONFIG_INVALID", f"{min_name} must be less than or equal to {max_name}")


def _require_option_choice(value: str | None, name: str, choices: set[str]) -> str | None:
    if value is None:
        return None
    if value not in choices:
        raise AlabError("CONFIG_INVALID", f"{name} must be one of {', '.join(sorted(choices))}")
    return value


def _commit_sha_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if not _is_commit_sha_selector(value):
        raise AlabError("CONFIG_INVALID", "--commit must be a commit SHA")
    return value.lower()


def _exp_commit_selector_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if value in {"latest", "final", "best"}:
        return value
    if not _is_commit_sha_selector(value):
        raise AlabError("CONFIG_INVALID", "commit selector must be latest, final, best, or a commit SHA")
    return value.lower()


def _full_commit_sha_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) != 40 or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise AlabError("CONFIG_INVALID", "--commit requires a full commit SHA")
    return value.lower()


def _content_hash_filter(value: str | None) -> str | None:
    if value is None:
        return None
    prefix = "sha256:"
    digest = value.removeprefix(prefix)
    if not value.startswith(prefix) or len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
        raise AlabError("CONFIG_INVALID", "--content-hash must be sha256:<64-hex>")
    return prefix + digest.lower()


def _parse_bool_option(args: list[str], name: str) -> bool | None:
    require_options_at_most_once(args, (name,))
    value = command_arg(args, name)
    if value is None:
        return None
    if value.lower() in {"true", "1", "yes"}:
        return True
    if value.lower() in {"false", "0", "no"}:
        return False
    raise AlabError("CONFIG_INVALID", f"{name} must be true or false")


def _append_time_filter(args: list[str], clauses: list[str], params: list[Any], option: str, column: str, op: str) -> None:
    require_options_at_most_once(args, (option,))
    value = command_arg(args, option)
    if value:
        clauses.append(f"{column} {op} ?")
        params.append(parse_rfc3339_utc(value))


def _require_ordered_time_range(args: list[str], after_option: str, before_option: str) -> None:
    require_options_at_most_once(args, (after_option, before_option))
    after_value = command_arg(args, after_option)
    before_value = command_arg(args, before_option)
    if after_value and before_value and parse_rfc3339_utc(after_value) > parse_rfc3339_utc(before_value):
        raise AlabError("CONFIG_INVALID", f"{after_option} must be less than or equal to {before_option}")


def _paginate_rows(args: list[str], rows: list[Any]) -> list[Any]:
    limit, offset = _parse_limit_offset(args)
    return rows[offset : offset + limit]


def _sort_rows(
    args: list[str],
    rows: list[Any],
    *,
    default: str,
    allowed: dict[str, Any],
    subject: str,
) -> list[Any]:
    require_options_at_most_once(args, ("--sort",))
    sort_text = command_arg(args, "--sort", default=default) or default
    field, sep, direction = sort_text.partition(":")
    if not field:
        raise AlabError("CONFIG_INVALID", "--sort field is required")
    if not sep:
        direction = "desc"
    if direction not in {"asc", "desc"}:
        raise AlabError("CONFIG_INVALID", "--sort direction must be asc or desc")
    if field not in allowed:
        raise AlabError("CONFIG_INVALID", f"--sort field is not supported for {subject}")
    nulls: list[Any] = []
    values: list[tuple[Any, Any]] = []
    for row in rows:
        value = allowed[field](row)
        if value is None:
            nulls.append(row)
            continue
        if isinstance(value, str):
            value = value.casefold()
        elif isinstance(value, bool):
            value = int(value)
        values.append((value, row))
    values.sort(key=lambda item: item[0], reverse=direction == "desc")
    return [row for _value, row in values] + nulls


def _reward_identity_from_config_json(config_json: dict[str, Any]) -> str:
    reward = config_json.get("reward") or {}
    comparable = {
        "schema_version": 1,
        "type": reward.get("type"),
        "direction": reward.get("direction", "maximize"),
        "primary_metric": reward.get("primary_metric", "reward"),
        "path": reward.get("path"),
        "pattern": reward.get("pattern"),
    }
    return canonical_json(comparable)


def _reward_direction_from_config_json(config_json: dict[str, Any]) -> str:
    reward = config_json.get("reward") or {}
    direction = reward.get("direction", "maximize")
    if direction not in {"maximize", "minimize"}:
        raise AlabError("CONFIG_INVALID", "invalid reward direction in config")
    return direction


def _config_json_for_version(conn, project_id: str, version: int) -> dict[str, Any]:
    row = one(
        conn,
        "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?",
        (project_id, version),
    )
    if row is None:
        raise AlabError("CONFIG_INVALID", "config version not found")
    return project_config_json_obj(row["canonical_config_json"])


def _current_visibility_policy(conn, project: Any) -> dict[str, Any]:
    version = project["latest_attempted_config_version"] or project["active_valid_config_version"]
    if not version:
        return {"scope": "none", "experiment_ids": []}
    config_json = _config_json_for_version(conn, project["project_id"], int(version))
    return config_json.get("visibility") or {"scope": "none", "experiment_ids": []}


def _intersect_visibility(current: dict[str, Any], upper_bound: dict[str, Any]) -> tuple[str, set[str]]:
    current_scope = current.get("scope", "none")
    upper_scope = upper_bound.get("scope", "none")
    if "none" in {current_scope, upper_scope}:
        return "none", set()
    if current_scope == "same_project" and upper_scope == "same_project":
        return "same_project", set()
    if current_scope == "explicit" and upper_scope == "explicit":
        return "explicit", set(current.get("experiment_ids") or []) & set(upper_bound.get("experiment_ids") or [])
    if current_scope == "explicit":
        return "explicit", set(current.get("experiment_ids") or [])
    if upper_scope == "explicit":
        return "explicit", set(upper_bound.get("experiment_ids") or [])
    return "none", set()


def _public_from_exp_visible(conn, project: Any, source_exp: Any) -> bool:
    if source_exp["status"] not in {"open", "closed"}:
        return False
    upper_bound = experiment_policy_json_obj(source_exp["policy_json"]).get("visibility_upper_bound") or {"scope": "none", "experiment_ids": []}
    scope, explicit_ids = _intersect_visibility(_current_visibility_policy(conn, project), upper_bound)
    if scope == "same_project":
        return True
    if scope == "explicit":
        return source_exp["exp_id"] in explicit_ids
    return False


def _visible_exp_ids(conn, project_id: str, actor: Actor) -> set[str] | None:
    if actor.actor_type in {"root", "admin"}:
        return None
    if not actor.exp_id:
        return set()
    project = _project_row(conn, project_id)
    source_exp = _exp_row(conn, project_id, actor.exp_id)
    policy = experiment_policy_json_obj(source_exp["policy_json"]).get("visibility_upper_bound") or {"scope": "none", "experiment_ids": []}
    scope, explicit_ids = _intersect_visibility(_current_visibility_policy(conn, project), policy)
    visible = {actor.exp_id}
    if scope == "same_project":
        visible.update(row["exp_id"] for row in all_rows(conn, "SELECT exp_id FROM experiments WHERE project_id = ?", (project_id,)))
    elif scope == "explicit":
        visible.update(explicit_ids)
    return visible


def _append_visible_exp_clause(conn, project_id: str, actor: Actor, clauses: list[str], params: list[Any], *, column: str = "exp_id") -> None:
    visible = _visible_exp_ids(conn, project_id, actor)
    if visible is None:
        return
    if not visible:
        clauses.append("1 = 0")
        return
    placeholders = ", ".join("?" for _ in visible)
    clauses.append(f"{column} IN ({placeholders})")
    params.extend(sorted(visible))


def _exp_visible(conn, project_id: str, actor: Actor, exp_id: str | None) -> bool:
    if actor.actor_type in {"root", "admin"}:
        return True
    if not exp_id:
        return False
    visible = _visible_exp_ids(conn, project_id, actor)
    return exp_id in (visible or set())


def _best_context(conn, project: Any, args: list[str]) -> tuple[int | None, str | None, str]:
    explicit_version = _parse_positive_int_option(args, "--config-version")
    if explicit_version is not None:
        config_json = _config_json_for_version(conn, project["project_id"], explicit_version)
        return explicit_version, None, _reward_direction_from_config_json(config_json)
    active = project["active_valid_config_version"]
    if active is None:
        raise AlabError("PROJECT_INVALID", "best requires an active valid config or explicit --config-version")
    config_json = _config_json_for_version(conn, project["project_id"], int(active))
    return None, _reward_identity_from_config_json(config_json), _reward_direction_from_config_json(config_json)


def _optional_best_context(conn, project: Any) -> tuple[str | None, str]:
    active = project["active_valid_config_version"]
    if active is None:
        return None, "maximize"
    config_json = _config_json_for_version(conn, project["project_id"], int(active))
    return _reward_identity_from_config_json(config_json), _reward_direction_from_config_json(config_json)


def _best_run_for_experiment(
    conn,
    *,
    project_id: str,
    exp_id: str,
    direction: str,
    config_version: int | None = None,
    reward_identity: str | None = None,
    include_archived_runs: bool = False,
) -> tuple[Any | None, int]:
    clauses = [
        "project_id = ?",
        "exp_id = ?",
        "status = 'passed'",
        "reward_parse_status = 'parsed'",
        "reward_value IS NOT NULL",
    ]
    params: list[Any] = [project_id, exp_id]
    if config_version is not None:
        clauses.append("config_version = ?")
        params.append(config_version)
    if not include_archived_runs:
        clauses.append("archive_status = 'active'")
    rows = all_rows(conn, f"SELECT * FROM runs WHERE {' AND '.join(clauses)}", tuple(params))
    identity_cache: dict[int, str] = {}
    comparable: list[Any] = []
    excluded = 0
    for row in rows:
        if reward_identity is not None:
            version = int(row["config_version"])
            if version not in identity_cache:
                identity_cache[version] = _reward_identity_from_config_json(_config_json_for_version(conn, project_id, version))
            if identity_cache[version] != reward_identity:
                excluded += 1
                continue
        comparable.append(row)
    comparable.sort(key=lambda row: row["exp_id"])
    comparable.sort(key=lambda row: row["ended_at"] or "", reverse=True)
    comparable.sort(key=lambda row: float(row["reward_value"]), reverse=direction == "maximize")
    return (comparable[0] if comparable else None), excluded


def _experiment_result_block(
    conn,
    row: Any,
    *,
    best_run: Any | None = None,
    reward_parse_status: str | None = None,
) -> ResultBlock:
    meta = experiment_metadata_obj(row["metadata_json"])
    source = one(conn, "SELECT source_ref FROM sources WHERE source_id = ?", (row["source_id"],))
    tags = _tag_values(conn, row["exp_id"])
    if best_run is None and row["latest_run_id"]:
        best_run = one(conn, "SELECT * FROM runs WHERE run_id = ?", (row["latest_run_id"],))
    return ResultBlock(
        "experiment",
        [
            ("project id", row["project_id"]),
            ("exp id", row["exp_id"]),
            ("experiment name", meta.get("name")),
            ("experiment status", row["status"]),
            ("source id", row["source_id"]),
            ("source ref", source["source_ref"] if source else None),
            ("tag", tags),
            ("latest run id", row["latest_run_id"]),
            ("latest commit", row["latest_commit"]),
            ("final run id", row["final_run_id"]),
            ("final commit", row["final_commit"]),
            ("best run id", best_run["run_id"] if best_run else None),
            ("reward", best_run["reward_value"] if best_run else None),
            ("reward parse status", (best_run["reward_parse_status"] if best_run else reward_parse_status) or "none"),
            ("created at", row["created_at"]),
            ("updated at", row["updated_at"]),
            ("closed at", row["closed_at"]),
            ("archived at", row["archived_at"]),
        ],
    )


def _experiment_rows(conn, project_id: str, actor: Actor, args: list[str]) -> list[Any]:
    require_options_at_most_once(args, ("--include-archived", "--status", "--name-query"))
    clauses = ["project_id = ?"]
    params: list[Any] = [project_id]
    _append_visible_exp_clause(conn, project_id, actor, clauses, params)
    if not flag(args, "--include-archived"):
        clauses.append("status != 'archived'")
    status = _require_option_choice(command_arg(args, "--status"), "--status", EXPERIMENT_STATUSES)
    if status:
        clauses.append("status = ?")
        params.append(status)
    source_id_filter = _complete_id_option(args, "--source-id", "src")
    if source_id_filter:
        clauses.append("source_id = ?")
        params.append(source_id_filter)
    config_version_filter = _parse_positive_int_option(args, "--config-version")
    if config_version_filter is not None:
        clauses.append("bound_config_version = ?")
        params.append(config_version_filter)
    _require_ordered_time_range(args, "--created-after", "--created-before")
    _require_ordered_time_range(args, "--updated-after", "--updated-before")
    for name, column in [("--created-after", "created_at"), ("--created-before", "created_at"), ("--updated-after", "updated_at"), ("--updated-before", "updated_at")]:
        value = command_arg(args, name)
        if value:
            clauses.append(f"{column} {'>=' if name.endswith('after') else '<='} ?")
            params.append(parse_rfc3339_utc(value))
    rows = [dict(row) for row in all_rows(conn, f"SELECT * FROM experiments WHERE {' AND '.join(clauses)}", tuple(params))]
    tags = command_args(args, "--tag")
    if tags:
        wanted = {_tag_slug(tag) for tag in tags}
        rows = [row for row in rows if wanted.issubset(set(_tag_values(conn, row["exp_id"])))]
    name_query = (command_arg(args, "--name-query") or "").casefold()
    if name_query:
        rows = [row for row in rows if name_query in str(experiment_metadata_obj(row["metadata_json"]).get("name") or "").casefold()]
    return rows


def _require_experiment_query_options_at_most_once(args: list[str], *, allow_sort: bool) -> None:
    options = [
        "--include-archived",
        "--status",
        "--name-query",
        "--source-id",
        "--config-version",
        "--created-after",
        "--created-before",
        "--updated-after",
        "--updated-before",
        "--reward-min",
        "--reward-max",
        "--limit",
        "--offset",
    ]
    if allow_sort:
        options.append("--sort")
    require_options_at_most_once(args, tuple(options))


def _experiment_search_corpus(conn, project_id: str, row: Any, actor: Actor, visible_exp_ids: set[str] | None) -> str:
    meta = experiment_metadata_obj(row["metadata_json"])
    parts = [str(meta.get("name") or ""), str(meta.get("goal") or "")]
    try:
        config_json = _config_json_for_version(conn, project_id, int(row["bound_config_version"]))
        project_config = config_json.get("project") or {}
        parts.extend([str(project_config.get("name") or ""), str(project_config.get("task") or ""), str(project_config.get("goal") or "")])
    except AlabError:
        pass
    parts.extend(_tag_values(conn, row["exp_id"]))
    submission = one(conn, "SELECT summary, feedback FROM experiment_submissions WHERE exp_id = ?", (row["exp_id"],))
    if submission:
        parts.extend([submission["summary"], submission["feedback"]])
    ann_rows = all_rows(
        conn,
        """
        SELECT a.*, ar.body
        FROM annotations a
        JOIN annotation_revisions ar ON ar.annotation_id = a.annotation_id AND ar.revision = a.current_revision
        WHERE a.project_id = ? AND a.status = 'active' AND (a.target_id = ? OR json_extract(a.target_json, '$.exp_id') = ?)
        """,
        (project_id, row["exp_id"], row["exp_id"]),
    )
    parts.extend(ann["body"] for ann in ann_rows if _annotation_visible(ann, actor, visible_exp_ids))
    return "\n".join(part for part in parts if part)


def _sort_experiment_blocks(rows_with_best: list[tuple[Any, Any | None]], args: list[str], *, default: str) -> list[tuple[Any, Any | None]]:
    require_options_at_most_once(args, ("--sort",))
    sort_text = command_arg(args, "--sort", default=default) or default
    field, sep, direction = sort_text.partition(":")
    if not sep:
        direction = "desc"
    if direction not in {"asc", "desc"}:
        raise AlabError("CONFIG_INVALID", "--sort direction must be asc or desc")
    allowed = {"created", "updated", "name", "status", "reward"}
    if field not in allowed:
        raise AlabError("CONFIG_INVALID", "--sort field is not supported for experiments")
    concrete: list[tuple[Any, tuple[Any, Any | None]]] = []
    nulls: list[tuple[Any, Any | None]] = []
    for item in rows_with_best:
        row, best = item
        meta = experiment_metadata_obj(row["metadata_json"])
        if field == "created":
            value = row["created_at"]
        elif field == "updated":
            value = row["updated_at"]
        elif field == "name":
            value = str(meta.get("name") or "").casefold()
        elif field == "status":
            value = row["status"]
        else:
            value = best["reward_value"] if best else None
        if value is None:
            nulls.append(item)
            continue
        concrete.append((float(value) if field == "reward" else value, item))

    concrete.sort(key=lambda pair: pair[0], reverse=direction == "desc")
    return [item for _value, item in concrete] + nulls


def cmd_exp_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--include-archived",
            "--status",
            "--name-query",
            "--source-id",
            "--config-version",
            "--created-after",
            "--created-before",
            "--updated-after",
            "--updated-before",
            "--tag",
            "--reward-min",
            "--reward-max",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    _require_experiment_query_options_at_most_once(args, allow_sort=True)
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    require_positional_count(args, 0, "exp list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        identity, direction = _optional_best_context(conn, project)
        reward_min = _parse_float_option(args, "--reward-min")
        reward_max = _parse_float_option(args, "--reward-max")
        _require_ordered_range(reward_min, reward_max, "--reward-min", "--reward-max")
        rows_with_best: list[tuple[Any, Any | None]] = []
        for row in _experiment_rows(conn, project_id, actor, args):
            best, _excluded = _best_run_for_experiment(conn, project_id=project_id, exp_id=row["exp_id"], direction=direction, reward_identity=identity)
            if reward_min is not None and (best is None or float(best["reward_value"]) < reward_min):
                continue
            if reward_max is not None and (best is None or float(best["reward_value"]) > reward_max):
                continue
            rows_with_best.append((row, best))
        rows_with_best = _sort_experiment_blocks(rows_with_best, args, default="updated:desc")
        limit, offset = _parse_limit_offset(args)
        return [_experiment_result_block(conn, row, best_run=best) for row, best in rows_with_best[offset : offset + limit]]
    finally:
        conn.close()


def _exp_row(conn, project_id: str, exp_id: str | None) -> Any:
    exp_id = _complete_id_or_missing(exp_id, prefix="exp", code="EXPERIMENT_NOT_FOUND", label="experiment id")
    row = one(conn, "SELECT * FROM experiments WHERE project_id = ? AND exp_id = ?", (project_id, exp_id))
    if row is None:
        raise AlabError("EXPERIMENT_NOT_FOUND", "experiment not found")
    return row


def cmd_exp_search(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--query",
            "--include-archived",
            "--status",
            "--name-query",
            "--source-id",
            "--config-version",
            "--created-after",
            "--created-before",
            "--updated-after",
            "--updated-before",
            "--tag",
            "--reward-min",
            "--reward-max",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    require_options_at_most_once(args, ("--query",))
    _require_experiment_query_options_at_most_once(args, allow_sort=True)
    query = command_arg(args, "--query", required=True).casefold()
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    require_positional_count(args, 0, "exp search accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        identity, direction = _optional_best_context(conn, project)
        reward_min = _parse_float_option(args, "--reward-min")
        reward_max = _parse_float_option(args, "--reward-max")
        _require_ordered_range(reward_min, reward_max, "--reward-min", "--reward-max")
        visible_exp_ids = _visible_exp_ids(conn, project_id, actor)
        rows_with_best: list[tuple[Any, Any | None]] = []
        for row in _experiment_rows(conn, project_id, actor, args):
            if query not in _experiment_search_corpus(conn, project_id, row, actor, visible_exp_ids).casefold():
                continue
            best, _excluded = _best_run_for_experiment(conn, project_id=project_id, exp_id=row["exp_id"], direction=direction, reward_identity=identity)
            if reward_min is not None and (best is None or float(best["reward_value"]) < reward_min):
                continue
            if reward_max is not None and (best is None or float(best["reward_value"]) > reward_max):
                continue
            rows_with_best.append((row, best))
        rows_with_best = _sort_experiment_blocks(rows_with_best, args, default="updated:desc")
        limit, offset = _parse_limit_offset(args)
        return [_experiment_result_block(conn, row, best_run=best) for row, best in rows_with_best[offset : offset + limit]]
    finally:
        conn.close()


def cmd_exp_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--include-archived"))
    require_options_at_most_once(args, ("--include-archived",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    exp_id = optional_positional_selector(args, "exp show accepts exactly one experiment id")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        exp_id = _complete_id_or_missing(exp_id, prefix="exp", code="EXPERIMENT_NOT_FOUND", label="experiment id")
        exp = one(conn, "SELECT * FROM experiments WHERE project_id = ? AND exp_id = ?", (project_id, exp_id))
        if exp is None:
            if actor.actor_type == "token":
                raise AlabError("SCOPE_VIOLATION", "experiment is not visible or not found")
            raise AlabError("EXPERIMENT_NOT_FOUND", "experiment not found")
        if not _exp_visible(conn, project_id, actor, exp["exp_id"]):
            raise AlabError("SCOPE_VIOLATION", "experiment is not visible or not found")
        identity, direction = _optional_best_context(conn, project)
        best, _excluded = _best_run_for_experiment(conn, project_id=project_id, exp_id=exp["exp_id"], direction=direction, reward_identity=identity, include_archived_runs=flag(args, "--include-archived"))
        return [_experiment_result_block(conn, exp, best_run=best)]
    finally:
        conn.close()


def cmd_exp_best(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--include-archived",
            "--status",
            "--name-query",
            "--source-id",
            "--config-version",
            "--created-after",
            "--created-before",
            "--updated-after",
            "--updated-before",
            "--tag",
            "--reward-min",
            "--reward-max",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    _require_experiment_query_options_at_most_once(args, allow_sort=False)
    require_options_at_most_once(args, ("--sort",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    if command_arg(args, "--sort") is not None:
        raise AlabError("CONFIG_INVALID", "--sort is not supported for experiment best")
    require_positional_count(args, 0, "exp best accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        project = _project_row(conn, project_id)
        config_version, identity, direction = _best_context(conn, project, args)
        reward_min = _parse_float_option(args, "--reward-min")
        reward_max = _parse_float_option(args, "--reward-max")
        _require_ordered_range(reward_min, reward_max, "--reward-min", "--reward-max")
        rows_with_best: list[tuple[Any, Any | None]] = []
        excluded_count = 0
        for row in _experiment_rows(conn, project_id, actor, args):
            best, excluded = _best_run_for_experiment(
                conn,
                project_id=project_id,
                exp_id=row["exp_id"],
                direction=direction,
                config_version=config_version,
                reward_identity=identity,
                include_archived_runs=flag(args, "--include-archived"),
            )
            excluded_count += excluded
            if best is None:
                continue
            reward = float(best["reward_value"])
            if reward_min is not None and reward < reward_min:
                continue
            if reward_max is not None and reward > reward_max:
                continue
            rows_with_best.append((row, best))
        rows_with_best.sort(key=lambda item: item[0]["exp_id"])
        rows_with_best.sort(key=lambda item: item[1]["ended_at"] if item[1] else "", reverse=True)
        rows_with_best.sort(key=lambda item: float(item[1]["reward_value"]) if item[1] else float("inf"), reverse=direction == "maximize")
        limit, offset = _parse_limit_offset(args)
        blocks = [_experiment_result_block(conn, row, best_run=best) for row, best in rows_with_best[offset : offset + limit]]
        if excluded_count:
            blocks.append(
                ResultBlock(
                    "warning",
                    [
                        ("warning code", "BEST_INCOMPARABLE_RUNS_EXCLUDED"),
                        ("warning reason", "runs with incompatible reward policy identity were excluded"),
                        ("excluded count", excluded_count),
                    ],
                )
            )
        return blocks
    finally:
        conn.close()


def cmd_exp_archive(args: list[str], req: Request) -> list[ResultBlock]:
    for removed_flag in ("--remove-worktree", "--force-remove-worktree"):
        if flag(args, removed_flag):
            raise AlabError("CONFIG_INVALID", f"{removed_flag} was removed from exp archive; use exp worktree remove explicitly")
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


def _artifact_log_filesystem_targets(conn, home: Home, project_id: str, *, artifact_rows: list[Any] | None = None, log_rows: list[Any] | None = None) -> list[FilesystemRemovalTarget]:
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
        refs = all_rows(conn, "SELECT artifact_id FROM artifacts WHERE project_id = ? AND blob_path = ?", (project_id, blob_path))
        if any(ref["artifact_id"] not in artifact_ids for ref in refs):
            continue
        targets.append(FilesystemRemovalTarget("artifact", row["artifact_id"], _stored_relative_path(artifact_store, blob_path) or artifact_store / blob_path))

    for row in log_rows:
        file_path = row["file_path"]
        if not file_path:
            continue
        key = ("log", file_path)
        if key in seen:
            continue
        seen.add(key)
        refs = all_rows(conn, "SELECT log_id FROM log_streams WHERE project_id = ? AND file_path = ?", (project_id, file_path))
        if any(ref["log_id"] not in log_ids for ref in refs):
            continue
        targets.append(FilesystemRemovalTarget("log", row["log_id"], _stored_relative_path(artifact_store, file_path) or artifact_store / file_path))
    return targets


def _experiment_remove_filesystem_targets(conn, home: Home, project_id: str, exp_id: str) -> list[FilesystemRemovalTarget]:
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
        object_id = row["token_id"] if row["context_type"] == "inspection" and row["token_id"] else row["path_registry_id"]
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
    require_known_options(args, ("--project", "--dry-run", "--cascade", "--force", "--confirm", "--reason"))
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
            "runs": one(conn, "SELECT count(*) AS c FROM runs WHERE exp_id = ?", (exp["exp_id"],))["c"],
            "artifacts": one(conn, "SELECT count(*) AS c FROM artifacts WHERE exp_id = ?", (exp["exp_id"],))["c"],
            "logs": one(conn, "SELECT count(*) AS c FROM log_streams WHERE exp_id = ?", (exp["exp_id"],))["c"],
            "annotations": one(conn, "SELECT count(*) AS c FROM annotations WHERE project_id = ? AND target_id = ?", (project["project_id"], exp["exp_id"]))["c"],
            "tags": one(conn, "SELECT count(*) AS c FROM experiment_tags WHERE exp_id = ?", (exp["exp_id"],))["c"],
            "submissions": one(conn, "SELECT count(*) AS c FROM experiment_submissions WHERE exp_id = ?", (exp["exp_id"],))["c"],
        }
        filesystem_targets = _experiment_remove_filesystem_targets(conn, req.globals.home, project["project_id"], exp["exp_id"])
        _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project["project_id"])
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
                    ("planned trash move", [_trash_plan(req.globals.home, target.path) for target in filesystem_targets]),
                ],
            )
        ]
    require_force_confirm(args, exp["exp_id"], "experiment remove requires --force and matching --confirm")
    if not cascade:
        raise AlabError("CONFIG_INVALID", "experiment remove requires --cascade")
    if blockers:
        raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
    _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project["project_id"])
    audit_id = new_id("aud", "remove")
    stages = _stage_targets_to_trash(req.globals.home, filesystem_targets, audit_id)
    branch_deletion: GitRefDeletion | None = None
    try:
        branch_deletion = _delete_experiment_branch_ref(repo_git, exp["branch_name"])
        with Database(req.globals.home).tx() as tx:
            now = utc_now()
            tx.execute("UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE exp_id = ? AND credential_type = 'token' AND status = 'active'", (now, exp["exp_id"]))
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
                            "original_path_hash": path_hash(stage.original_path) if stage.original_path else None,
                            "already_absent": stage.already_absent,
                        }
                        for target, stage in zip(filesystem_targets, stages, strict=False)
                    ],
                },
            )
            tx.execute("DELETE FROM annotation_revisions WHERE annotation_id IN (SELECT annotation_id FROM annotations WHERE project_id = ? AND target_id = ?)", (project["project_id"], exp["exp_id"]))
            tx.execute("DELETE FROM annotations WHERE project_id = ? AND target_id = ?", (project["project_id"], exp["exp_id"]))
            for table in ["experiment_tags", "experiment_submissions", "runs", "artifacts", "log_streams"]:
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
            raise AlabError("STORAGE_ERROR", f"database update failed and branch restore failed: {branch_restore_exc}", "alab context repair") from branch_restore_exc
        _raise_after_staged_trash_transaction_failure(exc, stages)
    _prune_missing_git_worktrees(repo_git)
    trash_cleanup_pending = _finalize_staged_trashes(req.globals.home, stages, project["project_id"])
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
                ("branch ref existed", not branch_deletion.already_absent if branch_deletion else branch_ref_exists),
                ("deleted filesystem paths", len(filesystem_targets)),
                ("trash cleanup pending", trash_cleanup_pending),
            ],
        )
    ]


def _authorize_tag(req: Request, project_id: str, exp_id: str) -> Actor:
    raw = req.globals.key
    if raw:
        conn = require_home(req.globals.home)
        try:
            return verify_raw_credential(conn, raw, required=("root", "admin"), project_id=project_id)
        finally:
            conn.close()
    if req.context and req.context.context_type == "experiment" and req.context.project_id == project_id and req.context.exp_id == exp_id:
        conn = require_home(req.globals.home)
        try:
            token = read_token(req.context.path)
            return verify_raw_credential(conn, token, required="token", project_id=project_id, exp_id=exp_id, token_mode="worktree", path_hash=req.context.path_hash)
        finally:
            conn.close()
    raise AlabError("AUTH_REQUIRED", "tag command requires admin/root key or owning experiment token context")


def _tag_values(conn, exp_id: str) -> list[str]:
    return [row["tag_slug"] for row in all_rows(conn, "SELECT tag_slug FROM experiment_tags WHERE exp_id = ? ORDER BY tag_slug", (exp_id,))]


def cmd_exp_tag_add(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    pos = require_positional_count(args, 2, "exp tag add requires exp id and tag")
    exp_id, tag = pos[0], pos[1]
    project_id = _project_id_from_request(args, req)
    conn = require_home(req.globals.home)
    try:
        _exp_row(conn, project_id, exp_id)
    finally:
        conn.close()
    actor = _authorize_tag(req, project_id, exp_id)
    tag_slug = _tag_slug(tag)
    with Database(req.globals.home).tx() as tx:
        tx.execute(
            "INSERT OR IGNORE INTO experiment_tags(project_id, exp_id, tag_slug, created_by_type, created_by_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, exp_id, tag_slug, actor.actor_type, actor.credential_id, utc_now()),
        )
        tags = _tag_values(tx, exp_id)
    return [ResultBlock("tag", [("exp id", exp_id), ("tag", tag_slug), ("action", "add"), ("tags", tags)])]


def cmd_exp_tag_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    pos = require_positional_count(args, 2, "exp tag remove requires exp id and tag")
    exp_id, tag = pos[0], pos[1]
    project_id = _project_id_from_request(args, req)
    conn = require_home(req.globals.home)
    try:
        _exp_row(conn, project_id, exp_id)
    finally:
        conn.close()
    _authorize_tag(req, project_id, exp_id)
    tag_slug = _tag_slug(tag)
    with Database(req.globals.home).tx() as tx:
        tx.execute("DELETE FROM experiment_tags WHERE exp_id = ? AND tag_slug = ?", (exp_id, tag_slug))
        tags = _tag_values(tx, exp_id)
    return [ResultBlock("tag", [("exp id", exp_id), ("tag", tag_slug), ("action", "remove"), ("tags", tags)])]


def cmd_exp_tag_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    exp_id = optional_positional_selector(args, "exp tag list accepts at most one experiment id") or (req.context.exp_id if req.context else None)
    project_id = _project_id_from_request(args, req)
    conn = require_home(req.globals.home)
    try:
        _exp_row(conn, project_id, exp_id)
    finally:
        conn.close()
    _authorize_tag(req, project_id, exp_id)
    conn = require_home(req.globals.home)
    try:
        tags = _tag_values(conn, exp_id)
    finally:
        conn.close()
    return [ResultBlock("tag", [("exp id", exp_id), ("tag", None), ("action", "list"), ("tags", tags)])]


def _resolve_exp_commit(
    conn,
    home: Home,
    project_id: str,
    exp: Any,
    selector: str | None,
    *,
    allow_head_alias: bool = False,
) -> str:
    selector = selector or "latest"
    _project_root, repo_git, _artifact_store = _project_paths(home, project_id)
    branch_ref = f"refs/heads/{exp['branch_name']}"
    if selector == "latest" or (allow_head_alias and selector in {"HEAD", "head"}):
        if exp["latest_commit"]:
            commit = exp["latest_commit"]
        else:
            commit = (
                run_cmd(["git", f"--git-dir={repo_git}", "rev-parse", f"{branch_ref}^{{commit}}"])
                .stdout.decode("utf-8", errors="replace")
                .strip()
            )
    elif selector == "final":
        commit = exp["final_commit"]
        if not commit:
            raise AlabError("CONFIG_INVALID", "experiment has no final commit")
    elif selector == "best":
        project = _project_row(conn, project_id)
        reward_identity, direction = _optional_best_context(conn, project)
        row, _excluded = _best_run_for_experiment(
            conn,
            project_id=project_id,
            exp_id=exp["exp_id"],
            direction=direction,
            reward_identity=reward_identity,
        )
        if row is None:
            raise AlabError("CONFIG_INVALID", "experiment has no qualifying best run")
        commit = row["commit_sha"]
    else:
        if not _is_commit_sha_selector(selector):
            raise AlabError("CONFIG_INVALID", "commit selector must be latest, final, best, or a commit SHA")
        commit = _resolve_commit_sha_selector(repo_git, selector)
        reachable = run_cmd(
            ["git", f"--git-dir={repo_git}", "merge-base", "--is-ancestor", commit, branch_ref],
            check=False,
        )
        if reachable.returncode != 0:
            raise AlabError("CONFIG_INVALID", "commit is not reachable from the source experiment branch")
    if not commit:
        raise AlabError("CONFIG_INVALID", "commit selector did not resolve")
    return commit


def _is_commit_sha_selector(selector: str) -> bool:
    return 4 <= len(selector) <= 40 and all(char in "0123456789abcdefABCDEF" for char in selector)


def _resolve_commit_sha_selector(repo_git: Path, selector: str) -> str:
    prefix = selector.lower()
    candidates = run_cmd(
        ["git", f"--git-dir={repo_git}", "rev-parse", f"--disambiguate={prefix}"],
        check=False,
    )
    if candidates.returncode != 0:
        raise AlabError("CONFIG_INVALID", "commit selector did not resolve")
    object_ids = [line.strip() for line in candidates.stdout.decode("utf-8", errors="replace").splitlines() if line.strip()]
    if len(object_ids) != 1:
        if object_ids:
            raise AlabError("CONFIG_INVALID", "commit selector is ambiguous")
        raise AlabError("CONFIG_INVALID", "commit selector did not resolve")
    resolved = run_cmd(
        ["git", f"--git-dir={repo_git}", "rev-parse", f"{object_ids[0]}^{{commit}}"],
        check=False,
    )
    if resolved.returncode != 0:
        raise AlabError("CONFIG_INVALID", "commit selector did not resolve")
    commit = resolved.stdout.decode("utf-8", errors="replace").strip()
    if not commit:
        raise AlabError("CONFIG_INVALID", "commit selector did not resolve")
    return commit


def _path_registry_row_for_token(conn, token_id: str) -> Any | None:
    return one(conn, "SELECT * FROM path_registry WHERE token_id = ? AND status = 'active'", (token_id,))


def _token_path_status(conn, token_id: str) -> str:
    row = _path_registry_row_for_token(conn, token_id)
    if row is None:
        return "removed"
    return "present" if Path(row["path"]).exists() else "missing"


def _active_worktree_token(conn, exp_id: str) -> Any | None:
    return one(
        conn,
        "SELECT * FROM credentials WHERE exp_id = ? AND credential_type = 'token' AND token_mode = 'worktree' AND status = 'active'",
        (exp_id,),
    )


def _source_branch_ref(source_ref: str) -> str:
    if not source_ref.startswith("alab/source/src-"):
        raise AlabError("GIT_ERROR", "refusing to delete unexpected source branch")
    return f"refs/heads/{source_ref}"


def _experiment_branch_ref(branch_name: str) -> str:
    if not branch_name.startswith("alab/exp/"):
        raise AlabError("GIT_ERROR", "refusing to delete unexpected experiment branch")
    return f"refs/heads/{branch_name}"


def _git_ref_commit(repo_git: Path, branch_ref: str) -> str | None:
    result = run_cmd(["git", f"--git-dir={repo_git}", "rev-parse", "--verify", f"{branch_ref}^{{commit}}"], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip() or None


def _delete_experiment_branch_ref(repo_git: Path, branch_name: str) -> GitRefDeletion:
    branch_ref = _experiment_branch_ref(branch_name)
    commit = _git_ref_commit(repo_git, branch_ref)
    if commit is None:
        return GitRefDeletion(branch_ref, None, False, True)
    result = run_cmd(["git", f"--git-dir={repo_git}", "update-ref", "-d", branch_ref], check=False)
    if result.returncode != 0:
        reason = result.stderr.decode("utf-8", errors="replace").strip() or "failed to delete experiment branch ref"
        raise AlabError("GIT_ERROR", reason)
    return GitRefDeletion(branch_ref, commit, True, False)


def _delete_source_ref(repo_git: Path, source_ref: str) -> GitRefDeletion:
    branch_ref = _source_branch_ref(source_ref)
    commit = _git_ref_commit(repo_git, branch_ref)
    if commit is None:
        return GitRefDeletion(branch_ref, None, False, True)
    result = run_cmd(["git", f"--git-dir={repo_git}", "update-ref", "-d", branch_ref], check=False)
    if result.returncode != 0:
        reason = result.stderr.decode("utf-8", errors="replace").strip() or "failed to delete source branch ref"
        raise AlabError("GIT_ERROR", reason)
    return GitRefDeletion(branch_ref, commit, True, False)


def _restore_experiment_branch_ref(repo_git: Path, deletion: GitRefDeletion | None) -> None:
    if deletion is None or not deletion.deleted or deletion.commit is None:
        return
    result = run_cmd(["git", f"--git-dir={repo_git}", "update-ref", deletion.branch_ref, deletion.commit], check=False)
    if result.returncode != 0:
        reason = result.stderr.decode("utf-8", errors="replace").strip() or "failed to restore experiment branch ref"
        raise AlabError("GIT_ERROR", reason)


def _restore_source_ref(repo_git: Path, deletion: GitRefDeletion | None) -> None:
    if deletion is None or not deletion.deleted or deletion.commit is None:
        return
    result = run_cmd(["git", f"--git-dir={repo_git}", "update-ref", deletion.branch_ref, deletion.commit], check=False)
    if result.returncode != 0:
        reason = result.stderr.decode("utf-8", errors="replace").strip() or "failed to restore source branch ref"
        raise AlabError("GIT_ERROR", reason)


def _prune_missing_git_worktrees(repo_git: Path) -> None:
    run_cmd(["git", f"--git-dir={repo_git}", "worktree", "prune"], check=False)


def cmd_exp_worktree_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--force", "--confirm", "--reason"))
    require_options_at_most_once(args, ("--dry-run", "--reason"))
    require_dry_run_unforced(args)
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(args, "exp worktree remove accepts exactly one experiment id")
    dry_run = flag(args, "--dry-run")
    conn = require_home(req.globals.home)
    try:
        exp = dict(_exp_row(conn, project["project_id"], exp_id))
        path_row = one(conn, "SELECT * FROM path_registry WHERE exp_id = ? AND context_type = 'experiment' AND status = 'active'", (exp["exp_id"],))
        token = _active_worktree_token(conn, exp["exp_id"])
        old_path = path_row["path"] if path_row else exp["worktree_path"]
        dirty_state = _worktree_dirty_state(old_path)
        token_revoked = bool(token)
        token_id = token["credential_id"] if token else None
    finally:
        conn.close()
    reason = _lifecycle_reason(args)
    if dry_run:
        return [
            ResultBlock(
                "worktree",
                [
                    ("exp id", exp["exp_id"]),
                    ("old worktree path", old_path),
                    ("worktree state", exp["worktree_state"]),
                    ("dry run", True),
                    ("removed", False),
                    ("path exists", _path_present(Path(old_path)) if old_path else False),
                    ("dirty state", dirty_state),
                    ("token revocation target", token_id),
                    ("token revoked", token_revoked),
                    ("planned trash move", _trash_plan(req.globals.home, old_path)),
                    ("audit id", None),
                ],
            )
        ]
    require_force_confirm(args, exp["exp_id"], "exp worktree remove requires --force and matching --confirm")
    _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project["project_id"])
    audit_id = new_id("aud", "remove")
    stage = _stage_path_to_trash(req.globals.home, old_path, audit_id)
    try:
        with Database(req.globals.home).tx() as tx:
            now = utc_now()
            if token:
                tx.execute("UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?", (now, token["credential_id"]))
            tx.execute(
                "UPDATE path_registry SET status = 'removed', removed_at = ?, removed_by_credential_id = ?, updated_at = ? WHERE exp_id = ? AND context_type = 'experiment' AND status = 'active'",
                (now, actor.credential_id, now, exp["exp_id"]),
            )
            tx.execute(
                "UPDATE experiments SET worktree_state = 'removed', worktree_path = NULL, worktree_path_hash = NULL, updated_at = ? WHERE exp_id = ?",
                (now, exp["exp_id"]),
            )
            audit(
                tx,
                action="remove",
                object_type="worktree",
                object_id=exp["exp_id"],
                actor=actor,
                audit_id=audit_id,
                project_id=project["project_id"],
                exp_id=exp["exp_id"],
                reason=reason,
                metadata={
                    "schema_version": 1,
                    "filesystem_path_already_absent": stage.already_absent,
                    "dirty_state": dirty_state,
                    "token_revocation_target": token_id,
                    "trash": {
                        "mode": stage.mode,
                        "label": stage.audit_label,
                        "original_path_hash": path_hash(stage.original_path) if stage.original_path else None,
                    },
                },
            )
    except Exception as exc:
        _raise_after_staged_trash_transaction_failure(exc, [stage])
    _prune_missing_git_worktrees(repo_git)
    trash_cleanup_pending = _finalize_staged_trash(req.globals.home, stage, project["project_id"])
    return [
        ResultBlock(
            "worktree",
            [
                ("exp id", exp["exp_id"]),
                ("old worktree path", old_path),
                ("worktree state", "removed"),
                ("dry run", False),
                ("removed", True),
                ("path existed", not stage.already_absent),
                ("dirty state", dirty_state),
                ("token revocation target", token_id),
                ("token revoked", token_revoked),
                ("trash path", stage.audit_label),
                ("trash cleanup pending", trash_cleanup_pending),
                ("audit id", audit_id),
            ],
        )
    ]


def cmd_exp_worktree_restore(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--path"))
    require_options_at_most_once(args, ("--path",))
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(args, "exp worktree restore accepts exactly one experiment id")
    restore_path = Path(command_arg(args, "--path", required=True)).expanduser().resolve()
    conn = require_home(req.globals.home)
    try:
        _assert_new_context_path(conn, target=restore_path, project_id=project["project_id"], context_type="experiment", label="restore")
        exp = dict(_exp_row(conn, project["project_id"], exp_id))
        if exp["worktree_state"] == "active":
            raise AlabError("RESOURCE_BUSY", "experiment already has an active worktree")
        old_token = _active_worktree_token(conn, exp["exp_id"])
        home_id = one(conn, "SELECT home_id FROM homes LIMIT 1")["home_id"]
    finally:
        conn.close()
    _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project["project_id"])
    run_cmd(["git", f"--git-dir={repo_git}", "worktree", "add", str(restore_path), exp["branch_name"]])
    restore_path_hash = path_hash(restore_path)
    with Database(req.globals.home).tx() as tx:
        now = utc_now()
        revoked_token_id = None
        if old_token:
            revoked_token_id = old_token["credential_id"]
            tx.execute("UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?", (now, revoked_token_id))
        token_id, raw_token = create_credential(
            tx,
            credential_type="token",
            project_id=project["project_id"],
            exp_id=exp["exp_id"],
            token_mode="worktree",
            registered_path_hash=restore_path_hash,
            metadata={"schema_version": 1, "token_mode": "worktree", "created_for_path_hash": restore_path_hash},
        )
        write_marker(
            restore_path,
            {
                "marker_version": 1,
                "home_id": home_id,
                "context_type": "experiment",
                "project_id": project["project_id"],
                "exp_id": exp["exp_id"],
                "token_id": token_id,
                "created_at": now,
            },
        )
        write_token(restore_path, raw_token)
        _write_git_exclude(restore_path)
        path_registry_id = new_id("path", "experiment")
        tx.execute(
            """
            INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id,
              exp_id, token_id, status, created_at, updated_at)
            VALUES (?, ?, ?, 'experiment', ?, ?, ?, ?, 'active', ?, ?)
            """,
            (path_registry_id, restore_path_hash, str(restore_path), home_id, project["project_id"], exp["exp_id"], token_id, now, now),
        )
        tx.execute(
            "UPDATE experiments SET worktree_path = ?, worktree_path_hash = ?, worktree_state = 'active', updated_at = ? WHERE exp_id = ?",
            (str(restore_path), restore_path_hash, now, exp["exp_id"]),
        )
        audit(
            tx,
            action="restore",
            object_type="worktree",
            object_id=exp["exp_id"],
            actor=actor,
            project_id=project["project_id"],
            exp_id=exp["exp_id"],
            metadata={
                "schema_version": 1,
                "branch": exp["branch_name"],
                "worktree_state": "active",
                "restored_path_hash": restore_path_hash,
                "path_registry_id": path_registry_id,
                "revoked_token_id": revoked_token_id,
                "created_token_id": token_id,
                "token_mode": "worktree",
            },
        )
    return [
        ResultBlock(
            "worktree",
            [
                ("exp id", exp["exp_id"]),
                ("branch", exp["branch_name"]),
                ("worktree path", str(restore_path)),
                ("worktree state", "active"),
                ("token path", str(restore_path / ".alab" / "token")),
                ("revoked token id", revoked_token_id),
                ("new token id", token_id),
            ],
        )
    ]


def _credential_selector_sql(args: list[str], exp_id: str) -> tuple[str, tuple[Any, ...]]:
    require_options_at_most_once(args, ("--token-id", "--mode", "--all"))
    token_id = _complete_id_option(args, "--token-id", "cred")
    raw_mode = command_arg(args, "--mode")
    all_flag = flag(args, "--all")
    if all_flag and (token_id or raw_mode):
        raise AlabError("CONFIG_INVALID", "--all conflicts with --token-id or --mode")
    mode = _require_option_choice(raw_mode, "--mode", TOKEN_MODES)
    if token_id:
        return "exp_id = ? AND credential_id = ? AND credential_type = 'token'", (exp_id, token_id)
    if mode:
        return "exp_id = ? AND token_mode = ? AND credential_type = 'token'", (exp_id, mode)
    if all_flag:
        return "exp_id = ? AND credential_type = 'token'", (exp_id,)
    return "exp_id = ? AND token_mode = 'worktree' AND credential_type = 'token'", (exp_id,)


def cmd_exp_token_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--token-id", "--mode", "--all"))
    require_options_at_most_once(args, ("--token-id", "--mode", "--all"))
    project, _actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(args, "exp token list accepts exactly one experiment id")
    conn = require_home(req.globals.home)
    try:
        _exp_row(conn, project["project_id"], exp_id)
        where, params = _credential_selector_sql(args, exp_id)
        rows = all_rows(conn, f"SELECT * FROM credentials WHERE {where} ORDER BY created_at", params)
        return [
            ResultBlock(
                "credential",
                [
                    ("project id", project["project_id"]),
                    ("exp id", row["exp_id"]),
                    ("token id", row["credential_id"]),
                    ("token mode", row["token_mode"]),
                    ("status", row["status"]),
                    ("path status", _token_path_status(conn, row["credential_id"])),
                    ("created at", row["created_at"]),
                    ("revoked at", row["revoked_at"]),
                ],
            )
            for row in rows
        ]
    finally:
        conn.close()


def cmd_exp_token_revoke(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--token-id", "--mode", "--all"))
    require_options_at_most_once(args, ("--token-id", "--mode", "--all"))
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(args, "exp token revoke accepts exactly one experiment id")
    with Database(req.globals.home).tx() as conn:
        _exp_row(conn, project["project_id"], exp_id)
        where, params = _credential_selector_sql(args, exp_id)
        rows = all_rows(conn, f"SELECT * FROM credentials WHERE {where} AND status = 'active'", params)
        if not rows:
            raise AlabError("CREDENTIAL_NOT_FOUND", "active token not found")
        now = utc_now()
        blocks: list[ResultBlock] = []
        for row in rows:
            conn.execute("UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?", (now, row["credential_id"]))
            audit(
                conn,
                action="revoke",
                object_type="credential",
                object_id=row["credential_id"],
                actor=actor,
                project_id=project["project_id"],
                exp_id=exp_id,
                metadata={
                    "schema_version": 1,
                    "credential_type": row["credential_type"],
                    "token_mode": row["token_mode"],
                    "previous_status": row["status"],
                    "credential_status": "revoked",
                    "revoked_at": now,
                    "registered_path_hash": row["registered_path_hash"],
                },
            )
            blocks.append(
                ResultBlock(
                    "credential",
                    [
                        ("project id", project["project_id"]),
                        ("exp id", exp_id),
                        ("token id", row["credential_id"]),
                        ("token mode", row["token_mode"]),
                        ("status", "revoked"),
                        ("revoked at", now),
                    ],
                )
            )
        return blocks


def cmd_exp_token_regenerate(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--token-id", "--mode", "--all"))
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(args, "exp token regenerate accepts exactly one experiment id")
    require_options_at_most_once(args, ("--token-id", "--mode", "--all"))
    raw_mode = command_arg(args, "--mode", default="worktree")
    if command_arg(args, "--token-id") or flag(args, "--all"):
        raise AlabError("CONFIG_INVALID", "regenerate selects one token mode only")
    mode = _require_option_choice(raw_mode, "--mode", TOKEN_MODES)
    with Database(req.globals.home).tx() as conn:
        _exp_row(conn, project["project_id"], exp_id)
        old = one(conn, "SELECT * FROM credentials WHERE exp_id = ? AND token_mode = ? AND credential_type = 'token' AND status = 'active' ORDER BY created_at DESC LIMIT 1", (exp_id, mode))
        if old is None:
            raise AlabError("CREDENTIAL_NOT_FOUND", "active token not found")
        path_row = _path_registry_row_for_token(conn, old["credential_id"])
        if path_row is None:
            raise AlabError("CONTEXT_NOT_FOUND", "active token has no active registered path")
        now = utc_now()
        conn.execute("UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?", (now, old["credential_id"]))
        new_token_id, raw_token = create_credential(
            conn,
            credential_type="token",
            project_id=project["project_id"],
            exp_id=exp_id,
            token_mode=mode,
            registered_path_hash=path_row["path_hash"],
            metadata={"schema_version": 1, "token_mode": mode, "created_for_path_hash": path_row["path_hash"]},
        )
        conn.execute("UPDATE path_registry SET token_id = ?, updated_at = ? WHERE path_registry_id = ?", (new_token_id, now, path_row["path_registry_id"]))
        path = Path(path_row["path"])
        write_token(path, raw_token)
        marker = context_marker_obj((path / ".alab" / "context.json").read_text(encoding="utf-8"))
        marker["token_id"] = new_token_id
        write_marker(path, marker)
        _write_git_exclude(path)
        audit(
            conn,
            action="regenerate",
            object_type="credential",
            object_id=new_token_id,
            actor=actor,
            project_id=project["project_id"],
            exp_id=exp_id,
            metadata={
                "schema_version": 1,
                "credential_type": "token",
                "token_mode": mode,
                "revoked_credential_id": old["credential_id"],
                "created_credential_id": new_token_id,
                "revoked_at": now,
                "registered_path_hash": path_row["path_hash"],
            },
        )
    return [
        ResultBlock(
            "credential",
            [
                ("project id", project["project_id"]),
                ("exp id", exp_id),
                ("revoked token id", old["credential_id"]),
                ("new token id", new_token_id),
                ("token mode", mode),
                ("token path", str(path / ".alab" / "token")),
                ("created at", now),
            ],
        )
    ]


def cmd_exp_checkout(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--path", "--commit"))
    require_options_at_most_once(args, ("--path", "--commit"))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    exp_id = optional_positional_selector(args, "exp checkout accepts exactly one experiment id")
    commit_selector = _exp_commit_selector_filter(command_arg(args, "--commit"))
    checkout_path = Path(command_arg(args, "--path", required=True)).expanduser().resolve()
    conn = require_home(req.globals.home)
    try:
        _project_row(conn, project_id)
        _assert_new_context_path(conn, target=checkout_path, project_id=project_id, context_type="inspection", label="inspection checkout")
        exp = _exp_row(conn, project_id, exp_id)
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, exp["exp_id"]):
            raise AlabError("SCOPE_VIOLATION", "experiment is not visible to this token")
        commit = _resolve_exp_commit(conn, req.globals.home, project_id, exp, commit_selector)
        home_id = one(conn, "SELECT home_id FROM homes LIMIT 1")["home_id"]
    finally:
        conn.close()
    _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project_id)
    run_cmd(["git", f"--git-dir={repo_git}", "worktree", "add", "--detach", str(checkout_path), commit])
    with Database(req.globals.home).tx() as tx:
        now = utc_now()
        checkout_path_hash = path_hash(checkout_path)
        path_registry_id = new_id("path", "inspection")
        token_id, raw_token = create_credential(
            tx,
            credential_type="token",
            project_id=project_id,
            exp_id=exp["exp_id"],
            token_mode="inspection",
            registered_path_hash=checkout_path_hash,
            metadata={
                "schema_version": 1,
                "token_mode": "inspection",
                "created_for_path_hash": checkout_path_hash,
            },
        )
        write_marker(
            checkout_path,
            {
                "marker_version": 1,
                "home_id": home_id,
                "context_type": "inspection",
                "project_id": project_id,
                "exp_id": exp["exp_id"],
                "token_id": token_id,
                "inspection_commit": commit,
                "created_at": now,
            },
        )
        write_token(checkout_path, raw_token)
        _write_git_exclude(checkout_path)
        tx.execute(
            """
            INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id,
              exp_id, token_id, status, created_at, updated_at)
            VALUES (?, ?, ?, 'inspection', ?, ?, ?, ?, 'active', ?, ?)
            """,
            (path_registry_id, checkout_path_hash, str(checkout_path), home_id, project_id, exp["exp_id"], token_id, now, now),
        )
        audit(
            tx,
            action="add",
            object_type="inspection_checkout",
            object_id=token_id,
            actor=actor,
            project_id=project_id,
            exp_id=exp["exp_id"],
            metadata={
                "schema_version": 1,
                "credential_type": "token",
                "token_mode": "inspection",
                "created_token_id": token_id,
                "inspection_commit": commit,
                "path_registry_id": path_registry_id,
                "created_for_path_hash": checkout_path_hash,
            },
        )
    return [
        ResultBlock(
            "inspection_checkout",
            [
                ("exp id", exp["exp_id"]),
                ("inspection path", str(checkout_path)),
                ("inspection commit", commit),
                ("token path", str(checkout_path / ".alab" / "token")),
                ("token id", token_id),
                ("next", f"cd {checkout_path} && alab status"),
            ],
        )
    ]


def _authorize_checkout_remove(req: Request, project_id: str, path_row: Any) -> Actor:
    raw = req.globals.key
    if raw:
        conn = require_home(req.globals.home)
        try:
            return verify_raw_credential(conn, raw, required=("root", "admin"), project_id=project_id)
        finally:
            conn.close()
    if req.context and req.context.context_type == "inspection" and req.context.token_id == path_row["token_id"]:
        conn = require_home(req.globals.home)
        try:
            token = read_token(req.context.path)
            return verify_raw_credential(conn, token, required="token", project_id=project_id, exp_id=path_row["exp_id"], token_mode="inspection", path_hash=req.context.path_hash)
        finally:
            conn.close()
    raise AlabError("AUTH_REQUIRED", "checkout remove requires admin/root key or matching inspection token context")


def cmd_exp_checkout_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--token-id", "--path", "--dry-run", "--force", "--confirm", "--reason"))
    require_options_at_most_once(args, ("--dry-run", "--reason"))
    require_dry_run_unforced(args)
    project_id = _project_id_from_request(args, req)
    require_exactly_one_option_pair(args, "--token-id", "--path", "checkout remove requires exactly one of --token-id or --path")
    token_id = _complete_id_option(args, "--token-id", "cred")
    path_arg = command_arg(args, "--path")
    require_positional_count(args, 0, "exp checkout remove accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        if token_id:
            path_row = one(conn, "SELECT * FROM path_registry WHERE project_id = ? AND token_id = ? AND context_type = 'inspection' AND status = 'active'", (project_id, token_id))
        else:
            ph = path_hash(Path(path_arg).expanduser().resolve())
            path_row = one(conn, "SELECT * FROM path_registry WHERE project_id = ? AND path_hash = ? AND context_type = 'inspection' AND status = 'active'", (project_id, ph))
        if path_row is None:
            raise AlabError("CONTEXT_NOT_FOUND", "inspection checkout not found")
        actor = _authorize_checkout_remove(req, project_id, path_row)
    finally:
        conn.close()
    dry_run = flag(args, "--dry-run")
    expected_confirm = path_row["token_id"] if token_id else path_row["path_hash"]
    reason = _lifecycle_reason(args)
    if dry_run:
        return [
            ResultBlock(
                "inspection_checkout",
                [
                    ("exp id", path_row["exp_id"]),
                    ("inspection path", path_row["path"]),
                    ("token id", path_row["token_id"]),
                    ("dry run", True),
                    ("removed", False),
                    ("path exists", _path_present(Path(path_row["path"]))),
                    ("token revocation target", path_row["token_id"]),
                    ("token revoked", True),
                    ("planned trash move", _trash_plan(req.globals.home, path_row["path"])),
                    ("audit id", None),
                ],
            )
        ]
    require_force_confirm(args, expected_confirm, "checkout remove requires --force and matching --confirm")
    _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project_id)
    audit_id = new_id("aud", "remove")
    stage = _stage_path_to_trash(req.globals.home, path_row["path"], audit_id)
    try:
        with Database(req.globals.home).tx() as tx:
            now = utc_now()
            tx.execute("UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?", (now, path_row["token_id"]))
            tx.execute(
                "UPDATE path_registry SET status = 'removed', removed_at = ?, removed_by_credential_id = ?, updated_at = ? WHERE path_registry_id = ?",
                (now, actor.credential_id, now, path_row["path_registry_id"]),
            )
            audit(
                tx,
                action="remove",
                object_type="inspection_checkout",
                object_id=path_row["token_id"],
                actor=actor,
                audit_id=audit_id,
                project_id=project_id,
                exp_id=path_row["exp_id"],
                reason=reason,
                metadata={
                    "schema_version": 1,
                    "filesystem_path_already_absent": stage.already_absent,
                    "token_revocation_target": path_row["token_id"],
                    "trash": {
                        "mode": stage.mode,
                        "label": stage.audit_label,
                        "original_path_hash": path_hash(stage.original_path) if stage.original_path else None,
                    },
                },
            )
    except Exception as exc:
        _raise_after_staged_trash_transaction_failure(exc, [stage])
    _prune_missing_git_worktrees(repo_git)
    trash_cleanup_pending = _finalize_staged_trash(req.globals.home, stage, project_id)
    return [
        ResultBlock(
            "inspection_checkout",
            [
                ("exp id", path_row["exp_id"]),
                ("inspection path", path_row["path"]),
                ("token id", path_row["token_id"]),
                ("dry run", False),
                ("removed", True),
                ("path existed", not stage.already_absent),
                ("token revocation target", path_row["token_id"]),
                ("token revoked", True),
                ("trash path", stage.audit_label),
                ("trash cleanup pending", trash_cleanup_pending),
                ("audit id", audit_id),
            ],
        )
    ]


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
        rows = all_rows(conn, f"SELECT * FROM runs WHERE {' AND '.join(clauses)} ORDER BY started_at DESC", tuple(params))
        runner_type = _require_option_choice(command_arg(args, "--runner-type"), "--runner-type", RUNNER_TYPES)
        failure_query = (command_arg(args, "--failure-reason-query") or "").casefold()
        if runner_type or failure_query:
            filtered = []
            for row in rows:
                record = execution_record_json_obj(row["record_json"])
                if runner_type and (record.get("runner") or {}).get("type") != runner_type:
                    continue
                if failure_query and failure_query not in str(record.get("failure") or "").casefold():
                    continue
                filtered.append(row)
            rows = filtered
        rows = _sort_rows(
            args,
            list(rows),
            default="started:desc",
            subject="runs",
            allowed={
                "started": lambda row: row["started_at"],
                "ended": lambda row: row["ended_at"],
                "reward": lambda row: row["reward_value"],
                "status": lambda row: row["status"],
                "config-version": lambda row: row["config_version"],
                "exit-code": lambda row: row["exit_code"],
            },
        )
        return [_run_result_block(conn, row) for row in _paginate_rows(args, list(rows))]
    finally:
        conn.close()


def _authorize_observe(req: Request, project_id: str | None, *, admin_required: bool = False) -> Actor:
    if project_id is None:
        raise AlabError("CONTEXT_NOT_FOUND", "project id is required")
    project_id = require_complete_id(project_id, "proj")
    if admin_required:
        return require_actor(req, ("root", "admin"), project_id=project_id)
    raw = req.globals.key
    if raw:
        conn = require_home(req.globals.home)
        try:
            return verify_raw_credential(conn, raw, required=("root", "admin", "token"), project_id=project_id)
        finally:
            conn.close()
    if req.context and req.context.project_id == project_id and req.context.context_type in {"experiment", "inspection"}:
        conn = require_home(req.globals.home)
        try:
            token = read_token(req.context.path)
            return verify_raw_credential(
                conn,
                token,
                required="token",
                project_id=project_id,
                exp_id=req.context.exp_id,
                token_mode="worktree" if req.context.context_type == "experiment" else "inspection",
                path_hash=req.context.path_hash,
            )
        finally:
            conn.close()
    raise AlabError("AUTH_REQUIRED", "observe command requires a project admin/root key or experiment/inspection token context")


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
        rows = all_rows(conn, f"SELECT * FROM artifacts WHERE {' AND '.join(clauses)} ORDER BY created_at DESC", tuple(params))
        rows = _sort_rows(
            args,
            list(rows),
            default="created:desc",
            subject="artifacts",
            allowed={
                "created": lambda row: row["created_at"],
                "path": lambda row: row["relative_path"],
                "size": lambda row: row["size_bytes"],
                "status": lambda row: row["status"],
                "content-hash": lambda row: row["content_hash"],
            },
        )
        return [_artifact_block(row) for row in _paginate_rows(args, list(rows))]
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
        rows = all_rows(conn, f"SELECT * FROM log_streams WHERE {' AND '.join(clauses)} ORDER BY created_at DESC", tuple(params))
        rows = _sort_rows(
            args,
            list(rows),
            default="created:desc",
            subject="logs",
            allowed={
                "created": lambda row: row["created_at"],
                "stream": lambda row: row["stream"],
                "size": lambda row: row["size_bytes"],
                "stored-bytes": lambda row: row["stored_bytes"],
                "hidden": lambda row: bool(row["hidden"]),
                "truncated": lambda row: bool(row["truncated"]),
            },
        )
        return [_log_block(row) for row in _paginate_rows(args, list(rows))]
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


def _read_annotation_body(args: list[str]) -> str:
    if flag(args, "--body-stdin"):
        raise AlabError("CONFIG_INVALID", "--body-stdin is not supported; use direct text or file input")
    require_exactly_one_option_pair(args, "--body", "--body-file", "annotation requires exactly one of --body or --body-file")
    body = command_arg(args, "--body")
    body_file = command_arg(args, "--body-file")
    text = _read_text_input_file(body_file, "annotation body") if body_file else body or ""
    _assert_utf8_max_bytes("annotation body", text, 65536)
    return text


def _authorize_annotation_actor(req: Request, project_id: str) -> Actor:
    raw = req.globals.key
    if raw:
        conn = require_home(req.globals.home)
        try:
            return verify_raw_credential(conn, raw, required=("root", "admin"), project_id=project_id)
        finally:
            conn.close()
    if req.context and req.context.context_type == "experiment" and req.context.project_id == project_id:
        conn = require_home(req.globals.home)
        try:
            token = read_token(req.context.path)
            return verify_raw_credential(conn, token, required="token", project_id=project_id, exp_id=req.context.exp_id, token_mode="worktree", path_hash=req.context.path_hash)
        finally:
            conn.close()
    if req.context and req.context.context_type == "inspection":
        raise AlabError("SCOPE_VIOLATION", "inspection tokens cannot mutate annotations")
    raise AlabError("AUTH_REQUIRED", "annotation command requires admin/root key or experiment token context")


def _annotation_private_exp_selector(args: list[str], actor: Actor) -> str | None:
    private_to_exp = command_arg(args, "--private-to-exp")
    if actor.actor_type == "token":
        if private_to_exp:
            raise AlabError("CONFIG_INVALID", "--private-to-exp is only valid with admin/root")
        return actor.exp_id if flag(args, "--private") else None
    if flag(args, "--private") and not private_to_exp:
        raise AlabError("CONFIG_INVALID", "--private requires --private-to-exp for admin/root")
    return require_complete_id(private_to_exp, "exp") if private_to_exp else None


def _validate_annotation_target_selector_ids(args: list[str]) -> None:
    raw_target = command_arg(args, "--target", required=True)
    if raw_target.startswith("exp:"):
        require_complete_id(raw_target[4:], "exp")
        return
    if raw_target.startswith("run:"):
        require_complete_id(raw_target[4:], "run")
        return
    if raw_target.startswith("artifact:"):
        require_complete_id(raw_target[9:], "art")
        return
    if raw_target.startswith("path:") or raw_target.startswith("lines:"):
        _target_kind, _sep, rest = raw_target.partition(":")
        if "@" in rest and ":" in rest:
            exp_part, _rest_after_exp = rest.split(":", 1)
            exp_id, _at, _commitish = exp_part.partition("@")
            require_complete_id(exp_id, "exp")


def _assert_clean_worktree(path: Path) -> None:
    status = run_cmd(["git", "status", "--porcelain"], cwd=path, check=False).stdout.decode("utf-8", errors="replace")
    visible_changes = [line for line in status.splitlines() if ".alab/" not in line]
    if visible_changes:
        raise AlabError("GIT_STATE_INVALID", "path/line annotation shorthand requires a clean experiment worktree")


def _git_object_type_at_commit(home: Home, project_id: str, commit: str, repo_path: str) -> str:
    _project_root, repo_git, _artifact_store = _project_paths(home, project_id)
    result = run_cmd(["git", f"--git-dir={repo_git}", "cat-file", "-t", f"{commit}:{repo_path}"], check=False)
    if result.returncode != 0:
        raise AlabError("CONFIG_INVALID", "annotation target path does not exist at resolved commit")
    object_type = result.stdout.decode("utf-8", errors="replace").strip()
    if object_type not in {"blob", "tree"}:
        raise AlabError("CONFIG_INVALID", "annotation target path is not a file or directory")
    return object_type


def _git_blob_bytes_at_commit(home: Home, project_id: str, commit: str, repo_path: str) -> bytes:
    _project_root, repo_git, _artifact_store = _project_paths(home, project_id)
    result = run_cmd(["git", f"--git-dir={repo_git}", "cat-file", "-p", f"{commit}:{repo_path}"], check=False)
    if result.returncode != 0:
        raise AlabError("CONFIG_INVALID", "annotation target file cannot be read at resolved commit")
    return result.stdout


def _assert_annotation_path_target(home: Home, project_id: str, commit: str, repo_path: str, line_range: dict[str, int] | None) -> None:
    object_type = _git_object_type_at_commit(home, project_id, commit, repo_path)
    if line_range is None:
        return
    if object_type != "blob":
        raise AlabError("CONFIG_INVALID", "line annotation target must be a file")
    data = _git_blob_bytes_at_commit(home, project_id, commit, repo_path)
    line_count = len(data.splitlines())
    if line_range["end"] > line_count:
        raise AlabError("CONFIG_INVALID", "line range exceeds target file length")


def _assert_annotation_repo_path(value: Any, *, label: str, code: str) -> None:
    if not isinstance(value, str) or not value:
        raise AlabError(code, f"{label} must be relative")
    if "\0" in value or "\n" in value or "\r" in value or "\\" in value:
        raise AlabError(code, f"{label} must be relative")
    if len(value) >= 3 and value[1] == ":" and value[2] == "/":
        raise AlabError(code, f"{label} must be relative")
    if value.startswith("/"):
        raise AlabError(code, f"{label} must be relative")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise AlabError(code, f"{label} must be relative")


def annotation_target_json_obj(text: str) -> dict[str, Any]:
    target = contract_json_obj(
        text,
        label="annotations.target_json",
        allowed_keys={"schema_version", "target_type", "target_id", "exp_id", "commit", "repo_path", "line_range"},
        required_keys={"target_type", "target_id"},
    )
    target_type = target["target_type"]
    if target_type not in ANNOTATION_TARGET_TYPES:
        raise AlabError("STORAGE_ERROR", "annotations.target_json target_type is invalid")
    if not isinstance(target["target_id"], str) or not target["target_id"]:
        raise AlabError("STORAGE_ERROR", "annotations.target_json target_id must be a non-empty string")
    target_id = target["target_id"]
    exp_id = target.get("exp_id")
    if exp_id is not None:
        if not isinstance(exp_id, str):
            raise AlabError("STORAGE_ERROR", "annotations.target_json exp_id must be a string")
        try:
            require_complete_id(exp_id, "exp")
        except AlabError as exc:
            raise AlabError("STORAGE_ERROR", "annotations.target_json exp_id must be a complete experiment id") from exc
    commit = target.get("commit")
    if commit is not None and not isinstance(commit, str):
        raise AlabError("STORAGE_ERROR", "annotations.target_json commit must be a string or null")
    repo_path = target.get("repo_path")
    if repo_path is not None:
        _assert_annotation_repo_path(repo_path, label="annotations.target_json repo_path", code="STORAGE_ERROR")
    line_range = target.get("line_range")
    if line_range is not None:
        if not isinstance(line_range, dict):
            raise AlabError("STORAGE_ERROR", "annotations.target_json line_range must be a JSON object")
        allowed_line_keys = {"start", "end"}
        unknown = sorted(set(line_range) - allowed_line_keys)
        missing = sorted(allowed_line_keys - set(line_range))
        if missing:
            raise AlabError("STORAGE_ERROR", f"annotations.target_json line_range missing JSON keys: {', '.join(missing)}")
        if unknown:
            raise AlabError("STORAGE_ERROR", f"annotations.target_json line_range contains unknown JSON keys: {', '.join(unknown)}")
        if (
            not isinstance(line_range["start"], int)
            or isinstance(line_range["start"], bool)
            or not isinstance(line_range["end"], int)
            or isinstance(line_range["end"], bool)
        ):
            raise AlabError("STORAGE_ERROR", "annotations.target_json line_range start/end must be integers")
        if line_range["start"] < 1 or line_range["end"] < line_range["start"]:
            raise AlabError("STORAGE_ERROR", "annotations.target_json line_range is invalid")
    if target_type in {"path", "lines"}:
        if not exp_id or not commit or not repo_path:
            raise AlabError("STORAGE_ERROR", "annotations.target_json path targets require exp_id, commit, and repo_path")
        if target_id != f"{exp_id}:{commit}:{repo_path}":
            raise AlabError("STORAGE_ERROR", "annotations.target_json path target_id must match exp_id, commit, and repo_path")
        if target_type == "lines" and line_range is None:
            raise AlabError("STORAGE_ERROR", "annotations.target_json lines target requires line_range")
        if target_type == "path" and line_range is not None:
            raise AlabError("STORAGE_ERROR", "annotations.target_json path target must not include line_range")
    else:
        prefix = ANNOTATION_TARGET_ID_PREFIXES[target_type]
        try:
            require_complete_id(target_id, prefix)
        except AlabError as exc:
            raise AlabError("STORAGE_ERROR", f"annotations.target_json target_id must be a complete {target_type} id") from exc
        if not exp_id:
            raise AlabError("STORAGE_ERROR", "annotations.target_json object targets require exp_id")
        if target_type == "experiment" and target_id != exp_id:
            raise AlabError("STORAGE_ERROR", "annotations.target_json experiment target_id must match exp_id")
        if line_range is not None or repo_path is not None:
            raise AlabError("STORAGE_ERROR", "annotations.target_json non-path target must not include repo_path or line_range")
    return target


def annotation_visibility_json_obj(text: str) -> dict[str, Any]:
    visibility = contract_json_obj(
        text,
        label="annotations.visibility_json",
        allowed_keys={"schema_version", "scope", "creator_exp_id", "constraints"},
        required_keys={"scope", "constraints"},
    )
    scope = visibility["scope"]
    if scope not in {"project", "private"}:
        raise AlabError("STORAGE_ERROR", "annotations.visibility_json scope is invalid")
    constraints = visibility["constraints"]
    if not isinstance(constraints, dict):
        raise AlabError("STORAGE_ERROR", "annotations.visibility_json constraints must be a JSON object")
    creator_exp_id = visibility.get("creator_exp_id")
    if scope == "private":
        if not isinstance(creator_exp_id, str):
            raise AlabError("STORAGE_ERROR", "annotations.visibility_json private scope requires creator_exp_id")
        try:
            require_complete_id(creator_exp_id, "exp")
        except AlabError as exc:
            raise AlabError("STORAGE_ERROR", "annotations.visibility_json creator_exp_id must be a complete experiment id") from exc
    elif creator_exp_id is not None:
        raise AlabError("STORAGE_ERROR", "annotations.visibility_json project scope must not include creator_exp_id")
    return visibility


def _resolve_annotation_target(args: list[str], req: Request, conn, project_id: str, actor: Actor) -> dict[str, Any]:
    require_options_at_most_once(args, ("--target",))
    raw_target = command_arg(args, "--target", required=True)
    if raw_target.startswith("exp:"):
        exp_id = require_complete_id(raw_target[4:], "exp")
        exp = _exp_row(conn, project_id, exp_id)
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, exp_id):
            raise AlabError("SCOPE_VIOLATION", "target experiment is not visible to this token")
        commit = exp["latest_commit"] or exp["final_commit"] or exp["baseline_commit"]
        return {"schema_version": 1, "target_type": "experiment", "target_id": exp_id, "exp_id": exp_id, "commit": commit}
    if raw_target.startswith("run:"):
        run_id = require_complete_id(raw_target[4:], "run")
        row = one(conn, "SELECT * FROM runs WHERE project_id = ? AND run_id = ?", (project_id, run_id))
        if row is None:
            raise AlabError("RUN_NOT_FOUND", "target run not found")
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, row["exp_id"]):
            raise AlabError("SCOPE_VIOLATION", "target run is not visible to this token")
        return {"schema_version": 1, "target_type": "run", "target_id": run_id, "exp_id": row["exp_id"], "commit": row["commit_sha"]}
    if raw_target.startswith("artifact:"):
        artifact_id = require_complete_id(raw_target[9:], "art")
        row = one(conn, "SELECT * FROM artifacts WHERE project_id = ? AND artifact_id = ?", (project_id, artifact_id))
        if row is None:
            raise AlabError("ARTIFACT_NOT_FOUND", "target artifact not found")
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, row["exp_id"]):
            raise AlabError("SCOPE_VIOLATION", "target artifact is not visible to this token")
        return {"schema_version": 1, "target_type": "artifact", "target_id": artifact_id, "exp_id": row["exp_id"], "commit": None}
    if raw_target.startswith("path:") or raw_target.startswith("lines:"):
        target_kind, _, rest = raw_target.partition(":")
        if "@" in rest and ":" in rest:
            exp_part, rest_after_exp = rest.split(":", 1)
            exp_id, _at, commitish = exp_part.partition("@")
            exp = _exp_row(conn, project_id, exp_id)
            commit = _resolve_exp_commit(
                conn,
                req.globals.home,
                project_id,
                exp,
                commitish or "latest",
                allow_head_alias=True,
            )
            repo_part = rest_after_exp
        else:
            if not req.context or req.context.context_type != "experiment":
                raise AlabError("CONFIG_INVALID", "path/lines shorthand requires an experiment context")
            exp_id = req.context.exp_id
            exp = _exp_row(conn, project_id, exp_id)
            _assert_clean_worktree(req.context.path)
            commit = run_cmd(["git", "rev-parse", "HEAD"], cwd=req.context.path).stdout.decode("utf-8", errors="replace").strip()
            repo_part = rest
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, exp_id):
            raise AlabError("SCOPE_VIOLATION", "target path is not visible to this token")
        line_range = None
        repo_path = repo_part
        if target_kind == "lines":
            repo_path, _sep, range_text = repo_part.rpartition(":")
            start_text, _dash, end_text = range_text.partition("-")
            try:
                start = int(start_text)
                end = int(end_text)
            except ValueError as exc:
                raise AlabError("CONFIG_INVALID", "line target requires start-end") from exc
            if start < 1 or end < start:
                raise AlabError("CONFIG_INVALID", "invalid line range")
            line_range = {"start": start, "end": end}
        _assert_annotation_repo_path(repo_path, label="annotation repo path", code="CONFIG_INVALID")
        _assert_annotation_path_target(req.globals.home, project_id, commit, repo_path, line_range)
        target_id = f"{exp_id}:{commit}:{repo_path}"
        data = {"schema_version": 1, "target_type": target_kind, "target_id": target_id, "exp_id": exp_id, "commit": commit, "repo_path": repo_path}
        if line_range:
            data["line_range"] = line_range
        return data
    raise AlabError("CONFIG_INVALID", "invalid annotation target")


def _annotation_visible(row: Any, actor: Actor, visible_exp_ids: set[str] | None = None) -> bool:
    visibility = annotation_visibility_json_obj(row["visibility_json"])
    if actor.actor_type in {"root", "admin"}:
        return True
    target = annotation_target_json_obj(row["target_json"])
    target_visible = _annotation_target_visible(target, actor, visible_exp_ids)
    if visibility.get("scope") == "private":
        return visibility.get("creator_exp_id") == actor.exp_id and target_visible
    return target_visible


def _annotation_target_visible(target: dict[str, Any], actor: Actor, visible_exp_ids: set[str] | None = None) -> bool:
    if actor.actor_type in {"root", "admin"}:
        return True
    exp_id = target.get("exp_id")
    if not exp_id:
        return False
    if visible_exp_ids is None:
        return exp_id == actor.exp_id
    return exp_id in visible_exp_ids


def _annotation_editable(row: Any, actor: Actor, visible_exp_ids: set[str] | None = None) -> bool:
    if actor.actor_type in {"root", "admin"}:
        return True
    target = annotation_target_json_obj(row["target_json"])
    if not _annotation_target_visible(target, actor, visible_exp_ids):
        return False
    visibility = annotation_visibility_json_obj(row["visibility_json"])
    if visibility.get("scope") == "private":
        return visibility.get("creator_exp_id") == actor.exp_id
    return row["created_by_type"] == "token" and row["created_by_id"] == actor.exp_id


def _assert_annotation_scope(row: Any, actor: Actor, *, edit: bool = False, visible_exp_ids: set[str] | None = None) -> None:
    allowed = _annotation_editable(row, actor, visible_exp_ids) if edit else _annotation_visible(row, actor, visible_exp_ids)
    if not allowed:
        raise AlabError("SCOPE_VIOLATION", "annotation is not visible in this context")


def _annotation_target_exp_id(target: dict[str, Any]) -> str:
    exp_id = target.get("exp_id")
    if not exp_id:
        raise AlabError("CONFIG_INVALID", "annotation target must resolve to exactly one experiment")
    return exp_id


def _assert_text_has_no_secret(conn, project_id: str, exp_id: str | None, value: str, label: str) -> None:
    if not exp_id:
        return
    exp = one(conn, "SELECT * FROM experiments WHERE project_id = ? AND exp_id = ?", (project_id, exp_id))
    if exp is None:
        return
    _cfg, secrets_map, _cfg_json = _load_config_and_secrets(conn, project_id, exp["bound_config_version"])
    for secret_value in secrets_map.values():
        if secret_value and secret_value in value:
            raise AlabError("CONFIG_INVALID", f"{label} contains an active secret value")


def _annotation_block(conn, row: Any, *, history: bool = False) -> ResultBlock:
    revision = one(conn, "SELECT * FROM annotation_revisions WHERE annotation_id = ? AND revision = ?", (row["annotation_id"], row["current_revision"]))
    visibility = annotation_visibility_json_obj(row["visibility_json"])
    revisions: list[str] = []
    if history:
        revisions = [
            f"{rev['revision']}:{rev['created_at']}"
            for rev in all_rows(conn, "SELECT * FROM annotation_revisions WHERE annotation_id = ? ORDER BY revision", (row["annotation_id"],))
        ]
    return ResultBlock(
        "annotation",
        [
            ("annotation id", row["annotation_id"]),
            ("target type", row["target_type"]),
            ("target id", row["target_id"]),
            ("resolved commit", row["resolved_commit"]),
            ("status", row["status"]),
            ("current revision", row["current_revision"]),
            ("visibility", visibility.get("scope")),
            ("author", revision["author_label"] if revision else None),
            ("body", multiline_text(revision["body"] if revision else None)),
            ("created at", row["created_at"]),
            ("updated at", row["updated_at"]),
            ("revision", revisions),
        ],
    )


def cmd_annotate_add(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--target", "--body", "--body-file", "--body-stdin", "--author", "--private", "--private-to-exp"))
    require_options_at_most_once(args, ("--target", "--body", "--body-file", "--body-stdin", "--author", "--private", "--private-to-exp"))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_annotation_actor(req, project_id)
    private_exp = _annotation_private_exp_selector(args, actor)
    require_positional_count(args, 0, "annotate add accepts no positional arguments")
    _validate_annotation_target_selector_ids(args)
    body = _read_annotation_body(args)
    conn = require_home(req.globals.home)
    try:
        _project_row(conn, project_id)
        target = _resolve_annotation_target(args, req, conn, project_id, actor)
        if private_exp:
            _exp_row(conn, project_id, private_exp)
        target_exp_id = _annotation_target_exp_id(target)
        _assert_text_has_no_secret(conn, project_id, target_exp_id, body, "annotation body")
    finally:
        conn.close()
    visibility = {"schema_version": 1, "scope": "private" if private_exp else "project", "constraints": {}}
    if private_exp:
        visibility["creator_exp_id"] = private_exp
    target_json = canonical_json(annotation_target_json_obj(canonical_json(target)))
    visibility_json = canonical_json(annotation_visibility_json_obj(canonical_json(visibility)))
    with Database(req.globals.home).tx() as tx:
        now = utc_now()
        annotation_id = new_id("ann", target["target_type"])
        creator_id = actor.exp_id if actor.actor_type == "token" else actor.credential_id
        tx.execute(
            """
            INSERT INTO annotations(annotation_id, project_id, target_type, target_id, target_json,
              resolved_commit, current_revision, visibility_json, status, created_by_type, created_by_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, 'active', ?, ?, ?, ?)
            """,
            (
                annotation_id,
                project_id,
                target["target_type"],
                target["target_id"],
                target_json,
                target.get("commit"),
                visibility_json,
                actor.actor_type,
                creator_id,
                now,
                now,
            ),
        )
        tx.execute(
            """
            INSERT INTO annotation_revisions(annotation_id, revision, body, author_label, created_at, created_by_type, created_by_id)
            VALUES (?, 1, ?, ?, ?, ?, ?)
            """,
            (annotation_id, body, command_arg(args, "--author"), now, actor.actor_type, creator_id),
        )
    return [
        ResultBlock(
            "annotation",
            [
                ("annotation id", annotation_id),
                ("target type", target["target_type"]),
                ("target id", target["target_id"]),
                ("resolved commit", target.get("commit")),
                ("revision", 1),
                ("visibility", visibility["scope"]),
                ("created at", now),
            ],
        )
    ]


def _annotation_row(conn, project_id: str, annotation_id: str | None, actor: Actor | None = None) -> Any:
    annotation_id = _complete_id_or_missing(annotation_id, prefix="ann", code="ANNOTATION_NOT_FOUND", label="annotation id")
    row = one(conn, "SELECT * FROM annotations WHERE project_id = ? AND annotation_id = ?", (project_id, annotation_id))
    if row is None:
        if actor and actor.actor_type == "token":
            raise AlabError("SCOPE_VIOLATION", "annotation is not visible or not found")
        raise AlabError("ANNOTATION_NOT_FOUND", "annotation not found")
    return row


def cmd_annotate_edit(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--body", "--body-file", "--body-stdin", "--author"))
    require_options_at_most_once(args, ("--body", "--body-file", "--body-stdin", "--author"))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_annotation_actor(req, project_id)
    annotation_id = optional_positional_selector(args, "annotate edit accepts exactly one annotation id")
    body = _read_annotation_body(args)
    with Database(req.globals.home).tx() as conn:
        row = _annotation_row(conn, project_id, annotation_id, actor)
        _assert_annotation_scope(row, actor, edit=True, visible_exp_ids=_visible_exp_ids(conn, project_id, actor))
        target = annotation_target_json_obj(row["target_json"])
        _assert_text_has_no_secret(conn, project_id, target.get("exp_id"), body, "annotation body")
        revision = int(row["current_revision"]) + 1
        now = utc_now()
        creator_id = actor.exp_id if actor.actor_type == "token" else actor.credential_id
        conn.execute(
            "INSERT INTO annotation_revisions(annotation_id, revision, body, author_label, created_at, created_by_type, created_by_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row["annotation_id"], revision, body, command_arg(args, "--author"), now, actor.actor_type, creator_id),
        )
        conn.execute("UPDATE annotations SET current_revision = ?, updated_at = ? WHERE annotation_id = ?", (revision, now, row["annotation_id"]))
    return [ResultBlock("annotation", [("annotation id", annotation_id), ("revision", revision), ("updated at", now)])]


def _set_annotation_status(args: list[str], req: Request, status: str) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_annotation_actor(req, project_id)
    annotation_id = optional_positional_selector(args, "annotation status accepts exactly one annotation id")
    with Database(req.globals.home).tx() as conn:
        row = _annotation_row(conn, project_id, annotation_id, actor)
        _assert_annotation_scope(row, actor, edit=True, visible_exp_ids=_visible_exp_ids(conn, project_id, actor))
        previous = row["status"]
        now = utc_now() if previous != status else None
        if previous != status:
            conn.execute("UPDATE annotations SET status = ?, updated_at = ? WHERE annotation_id = ?", (status, now, row["annotation_id"]))
            audit(
                conn,
                action="archive" if status == "archived" else "unarchive",
                object_type="annotation",
                object_id=row["annotation_id"],
                actor=actor,
                project_id=project_id,
                exp_id=annotation_target_json_obj(row["target_json"]).get("exp_id"),
                metadata={
                    "schema_version": 1,
                    "previous_status": previous,
                    "annotation_status": status,
                    "archived_at" if status == "archived" else "unarchived_at": now,
                },
            )
        return [
            ResultBlock(
                "annotation",
                [
                    ("annotation id", row["annotation_id"]),
                    ("previous status", previous),
                    ("annotation status", status),
                    ("archived at" if status == "archived" else "unarchived at", now),
                ],
            )
        ]


def cmd_annotate_archive(args: list[str], req: Request) -> list[ResultBlock]:
    return _set_annotation_status(args, req, "archived")


def cmd_annotate_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    return _set_annotation_status(args, req, "active")


def cmd_annotate_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--force", "--confirm", "--reason"))
    require_options_at_most_once(args, ("--dry-run", "--reason"))
    require_dry_run_unforced(args)
    project_id = _project_id_from_request(args, req)
    actor = _authorize_annotation_actor(req, project_id)
    annotation_id = optional_positional_selector(args, "annotate remove accepts exactly one annotation id")
    dry_run = flag(args, "--dry-run")
    with Database(req.globals.home).tx() as conn:
        row = _annotation_row(conn, project_id, annotation_id, actor)
        _assert_annotation_scope(row, actor, edit=True, visible_exp_ids=_visible_exp_ids(conn, project_id, actor))
        blockers = [] if row["status"] == "archived" else ["target_not_archived"]
        revision_count = one(conn, "SELECT count(*) AS c FROM annotation_revisions WHERE annotation_id = ?", (row["annotation_id"],))["c"]
        reason = _lifecycle_reason(args)
        if dry_run:
            return [
                ResultBlock(
                    "annotation",
                    [
                        ("annotation id", row["annotation_id"]),
                        ("dry run", True),
                        ("removed", False),
                        ("audit id", None),
                        ("blocker", blockers),
                        ("deleted revisions", revision_count),
                        ("deleted filesystem paths", 0),
                    ],
                )
            ]
        require_force_confirm(args, row["annotation_id"], "annotation remove requires --force and matching --confirm")
        if blockers:
            raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
        audit_id = audit(
            conn,
            action="remove",
            object_type="annotation",
            object_id=row["annotation_id"],
            actor=actor,
            project_id=project_id,
            exp_id=annotation_target_json_obj(row["target_json"]).get("exp_id"),
            reason=reason,
            metadata={
                "schema_version": 1,
                "deleted_revision_count": revision_count,
                "filesystem_target_count": 0,
                "filesystem_absent_count": 0,
                "trash": [],
            },
        )
        conn.execute("DELETE FROM annotation_revisions WHERE annotation_id = ?", (row["annotation_id"],))
        conn.execute("DELETE FROM annotations WHERE annotation_id = ?", (row["annotation_id"],))
    return [
        ResultBlock(
            "annotation",
            [
                ("annotation id", annotation_id),
                ("dry run", False),
                ("removed", True),
                ("audit id", audit_id),
                ("blocker", []),
                ("deleted revisions", revision_count),
                ("deleted filesystem paths", 0),
                ("trash cleanup pending", False),
            ],
        )
    ]


def cmd_observe_annotations_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--include-archived",
            "--target-type",
            "--target-id",
            "--target",
            "--created-by",
            "--private",
            "--author",
            "--query",
            "--history",
            "--created-after",
            "--created-before",
            "--updated-after",
            "--updated-before",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    require_options_at_most_once(
        args,
        (
            "--include-archived",
            "--target-type",
            "--target-id",
            "--target",
            "--created-by",
            "--private",
            "--author",
            "--query",
            "--history",
            "--created-after",
            "--created-before",
            "--updated-after",
            "--updated-before",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    require_positional_count(args, 0, "annotations list accepts no positional arguments")
    if command_arg(args, "--target-id") and command_arg(args, "--target"):
        raise AlabError("CONFIG_INVALID", "annotations list accepts only one of --target-id or --target")
    conn = require_home(req.globals.home)
    try:
        clauses = ["project_id = ?"]
        params: list[Any] = [project_id]
        if not flag(args, "--include-archived"):
            clauses.append("status = 'active'")
        target_type = _require_option_choice(command_arg(args, "--target-type"), "--target-type", ANNOTATION_TARGET_TYPES)
        if target_type:
            clauses.append("target_type = ?")
            params.append(target_type)
        target_id = _annotation_target_id_filter(target_type, command_arg(args, "--target-id") or command_arg(args, "--target"))
        if target_id:
            clauses.append("target_id = ?")
            params.append(target_id)
        created_by = _annotation_created_by_filter(command_arg(args, "--created-by"))
        if created_by:
            clauses.append("created_by_id = ?")
            params.append(created_by)
        _require_ordered_time_range(args, "--created-after", "--created-before")
        _require_ordered_time_range(args, "--updated-after", "--updated-before")
        for option, column, op in [
            ("--created-after", "created_at", ">="),
            ("--created-before", "created_at", "<="),
            ("--updated-after", "updated_at", ">="),
            ("--updated-before", "updated_at", "<="),
        ]:
            _append_time_filter(args, clauses, params, option, column, op)
        rows = all_rows(conn, f"SELECT * FROM annotations WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC", tuple(params))
        visible_ids = _visible_exp_ids(conn, project_id, actor)
        filtered = [row for row in rows if _annotation_visible(row, actor, visible_ids)]
        if flag(args, "--private"):
            filtered = [row for row in filtered if annotation_visibility_json_obj(row["visibility_json"]).get("scope") == "private"]
        author = command_arg(args, "--author")
        query = (command_arg(args, "--query") or "").casefold()
        if author or query:
            next_rows = []
            for row in filtered:
                revision = one(conn, "SELECT * FROM annotation_revisions WHERE annotation_id = ? AND revision = ?", (row["annotation_id"], row["current_revision"]))
                if author and (revision is None or revision["author_label"] != author):
                    continue
                if query and (revision is None or query not in revision["body"].casefold()):
                    continue
                next_rows.append(row)
            filtered = next_rows
        filtered = _sort_rows(
            args,
            filtered,
            default="updated:desc",
            subject="annotations",
            allowed={
                "created": lambda row: row["created_at"],
                "updated": lambda row: row["updated_at"],
                "target-type": lambda row: row["target_type"],
                "target-id": lambda row: row["target_id"],
                "status": lambda row: row["status"],
                "created-by": lambda row: row["created_by_id"],
            },
        )
        return [_annotation_block(conn, row, history=flag(args, "--history")) for row in _paginate_rows(args, filtered)]
    finally:
        conn.close()


def cmd_observe_annotations_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--history"))
    require_options_at_most_once(args, ("--history",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    annotation_id = optional_positional_selector(args, "annotations show accepts exactly one annotation id")
    conn = require_home(req.globals.home)
    try:
        row = _annotation_row(conn, project_id, annotation_id, actor)
        if not _annotation_visible(row, actor, _visible_exp_ids(conn, project_id, actor)):
            raise AlabError("SCOPE_VIOLATION", "annotation is not visible or not found")
        return [_annotation_block(conn, row, history=flag(args, "--history"))]
    finally:
        conn.close()


def cmd_audit_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--object-type",
            "--object-id",
            "--action",
            "--actor",
            "--created-after",
            "--created-before",
            "--limit",
            "--offset",
        ),
    )
    require_options_at_most_once(
        args,
        (
            "--project",
            "--object-type",
            "--object-id",
            "--action",
            "--actor",
            "--created-after",
            "--created-before",
            "--limit",
            "--offset",
        ),
    )
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    if project_id:
        project_id = require_complete_id(project_id, "proj")
    if project_id:
        require_actor(req, ("root", "admin"), project_id=project_id)
    else:
        require_actor(req, "root")
    require_positional_count(args, 0, "audit list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        clauses: list[str] = []
        params: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        actor_filter = _complete_id_option(args, "--actor", "cred")
        object_type_filter = _require_option_choice(command_arg(args, "--object-type"), "--object-type", AUDIT_OBJECT_TYPES)
        object_id_filter = _audit_object_id_filter(object_type_filter, command_arg(args, "--object-id"))
        action_filter = _require_option_choice(command_arg(args, "--action"), "--action", AUDIT_ACTIONS)
        if action_filter:
            clauses.append("action = ?")
            params.append(action_filter)
        if object_type_filter:
            clauses.append("object_type = ?")
            params.append(object_type_filter)
        if object_id_filter:
            clauses.append("object_id = ?")
            params.append(object_id_filter)
        if actor_filter:
            clauses.append("actor_credential_id = ?")
            params.append(actor_filter)
        _require_ordered_time_range(args, "--created-after", "--created-before")
        _append_time_filter(args, clauses, params, "--created-after", "created_at", ">=")
        _append_time_filter(args, clauses, params, "--created-before", "created_at", "<=")
        limit, offset = _parse_audit_limit_offset(args)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = all_rows(conn, f"SELECT * FROM audit_events{where} ORDER BY created_at DESC LIMIT ? OFFSET ?", tuple(params + [limit, offset]))
        return [
            ResultBlock(
                "audit",
                [
                    ("audit id", row["audit_id"]),
                    ("project id", row["project_id"]),
                    ("exp id", row["exp_id"]),
                    ("actor type", row["actor_type"]),
                    ("actor credential id", row["actor_credential_id"]),
                    ("action", row["action"]),
                    ("object type", row["object_type"]),
                    ("object id", row["object_id"]),
                    ("cascade", bool(row["cascade"])),
                    ("reason", row["reason"]),
                    ("created at", row["created_at"]),
                ],
            )
            for row in rows
        ]
    finally:
        conn.close()


def cmd_audit_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    require_options_at_most_once(args, ("--project",))
    audit_id = optional_positional_selector(args, "audit show accepts exactly one audit id")
    audit_id = _complete_id_or_missing(audit_id, prefix="aud", code="AUDIT_NOT_FOUND", label="audit id")
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    if project_id:
        project_id = require_complete_id(project_id, "proj")
    if project_id:
        require_actor(req, ("root", "admin"), project_id=project_id)
    else:
        require_actor(req, "root")
    conn = require_home(req.globals.home)
    try:
        if project_id:
            row = one(conn, "SELECT * FROM audit_events WHERE audit_id = ? AND project_id = ?", (audit_id, project_id))
        else:
            row = one(conn, "SELECT * FROM audit_events WHERE audit_id = ?", (audit_id,))
        if row is None:
            raise AlabError("AUDIT_NOT_FOUND", "audit event not found")
        deleted_ids_json = canonical_json(audit_deleted_ids_json_obj(row["deleted_ids_json"]))
        metadata_json = canonical_json(audit_metadata_json_obj(row["metadata_json"]))
        return [
            ResultBlock(
                "audit",
                [
                    ("audit id", row["audit_id"]),
                    ("project id", row["project_id"]),
                    ("exp id", row["exp_id"]),
                    ("actor type", row["actor_type"]),
                    ("actor credential id", row["actor_credential_id"]),
                    ("action", row["action"]),
                    ("object type", row["object_type"]),
                    ("object id", row["object_id"]),
                    ("cascade", bool(row["cascade"])),
                    ("reason", row["reason"]),
                    ("deleted ids", deleted_ids_json),
                    ("sanitized metadata", metadata_json),
                    ("created at", row["created_at"]),
                ],
            )
        ]
    finally:
        conn.close()
