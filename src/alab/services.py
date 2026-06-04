from __future__ import annotations

import fnmatch
import hashlib
import hmac
import json
import os
import secrets
import shutil
import socket
import sqlite3
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from . import service_args as _service_args
from . import service_contracts as _service_contracts
from .auth import (
    Actor,
    create_credential,
    credential_metadata_obj,
    read_token,
    verify_raw_credential,
    write_token,
)
from .catalog import _resolve_harbor_task_ref, _resolve_runner_adapter_ref
from .configs import (
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
    one,
)
from .docker_platform import normalize_docker_platform
from .errors import AlabError, error_exit_code
from .home import DEFAULT_CONFIG, Home, ensure_layout, is_initialized
from .ids import new_id, require_complete_id, slugify
from .proc import run_cmd
from .removal import (
    _delete_trash_path,  # noqa: F401 - compatibility export for legacy alab.services callers
    _finalize_staged_trash,  # noqa: F401 - compatibility export for legacy alab.services callers
    _finalize_staged_trashes,
    _path_present,  # noqa: F401 - compatibility export for legacy alab.services callers
    _raise_after_staged_trash_transaction_failure,
    _record_pending_trash_cleanup,  # noqa: F401 - compatibility export for legacy alab.services callers
    _remove_path_if_safe,  # noqa: F401 - compatibility export for legacy alab.services callers
    _remove_trash_cache_path,  # noqa: F401 - compatibility export for legacy alab.services callers
    _restore_staged_trash,  # noqa: F401 - compatibility export for legacy alab.services callers
    _restore_staged_trashes,  # noqa: F401 - compatibility export for legacy alab.services callers
    _stage_path_to_trash,  # noqa: F401 - compatibility export for legacy alab.services callers
    _stage_targets_to_trash,
    _trash_plan,
    _worktree_dirty_state,  # noqa: F401 - compatibility export for legacy alab.services callers
)
from .rendering import ResultBlock, multiline_text
from .runner import (
    DOCKER_CAPABILITY_KEYS,
    capture_artifacts,
    clean_copy_from_git,
    docker_runtime_fingerprint,
    load_harbor_task,
    probe_docker_capabilities,
    run_configured_runner,
    store_log_file,
)
from .service_args import (
    _exp_commit_selector_filter,
    _require_option_choice,
    command_arg,
    command_args,
    flag,
    option_count,
    optional_positional_selector,
    require_dry_run_unforced,
    require_exactly_one_option_pair,
    require_force_confirm,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_audit import audit
from .service_auth import _actor_is_project_admin_or_root, require_actor, require_home
from .service_contracts import (
    cache_metadata_json_obj,
    execution_record_json_obj,
    experiment_metadata_obj,
    experiment_policy_json_obj,
    runtime_capability_details_json_obj,
    source_origin_metadata_obj,
    submission_refs_json_obj,
)
from .service_models import (
    DEFAULT_SOURCE_IMPORT_LIMITS,
    VISIBILITY_SCOPES,
    AdapterDerivedSource,
    ExperimentOperationLock,
    FilesystemRemovalTarget,
    GitRefDeletion,
    PreparedSource,
    Request,
    RunExecutionSummary,
    SourceImportLimits,
    SourceImportResult,
    TrashStage,  # noqa: F401 - compatibility export for legacy alab.services callers
)
from .service_models import (
    ResolvedRemovalTarget as _ResolvedRemovalTarget,
)
from .service_text import (
    _assert_display_name,
    _assert_non_empty_text,
    _assert_utf8_max_bytes,
    _lifecycle_reason,
    _read_text_input_file,
)
from .source_import import (
    canonical_tree_hash,
    copy_filtered_source,
    init_snapshot_repo,
    reject_gitlinks,
)
from .timeutil import utc_now

EMPTY_COMMAND_VALUE_ALLOWED = _service_args.EMPTY_COMMAND_VALUE_ALLOWED
OPTIONS_WITH_VALUES = _service_args.OPTIONS_WITH_VALUES
audit_deleted_ids_json_obj = _service_contracts.audit_deleted_ids_json_obj
audit_metadata_json_obj = _service_contracts.audit_metadata_json_obj
annotation_target_json_obj = _service_contracts.annotation_target_json_obj
annotation_visibility_json_obj = _service_contracts.annotation_visibility_json_obj
catalog_metadata_json_obj = _service_contracts.catalog_metadata_json_obj


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


def cmd_help(args: list[str], req: Request) -> list[ResultBlock]:
    raise AlabError("CONFIG_INVALID", "help is handled by the CLI help renderer")


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


def _capability_next_action(capability: dict[str, Any]) -> str:
    if capability["status"] == "supported":
        return "none"
    details = capability.get("details", {})
    summary = str(details.get("safe_summary") or "inspect local runtime")
    code = details.get("error_code")
    key = str(capability.get("capability_key") or "")
    refresh = "run alab config validate --refresh-capabilities after fixing the runtime"
    if code == "DOCKER_NOT_FOUND":
        return f"{summary}; install Docker or add docker to PATH, then {refresh}"
    if code == "DOCKER_PROBE_TIMEOUT":
        return f"{summary}; start Docker or retry when it is responsive, then {refresh}"
    if key.startswith("docker.platform."):
        return f"{summary}; enable the required Docker platform or choose a supported runner platform, then {refresh}"
    if key.startswith("docker.resource."):
        return f"{summary}; remove the related runner resource requirement or use a Docker version that reports the flag, then {refresh}"
    return f"{summary}; {refresh}"


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
        blocks.append(
            ResultBlock(
                "capability",
                [
                    ("capability", capability["capability_key"]),
                    ("fingerprint", capability["fingerprint"]),
                    ("status", capability["status"]),
                    ("checked at", capability["checked_at"]),
                    ("next", _capability_next_action(capability)),
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
    if config.runner.skydiscover_task_ref:
        resolved = _resolve_runner_adapter_ref(conn, config.runner.skydiscover_task_ref)
        if config.runner.type == "skydiscover_docker" and resolved["target_kind"] != "skydiscover_docker_evaluator":
            raise AlabError("CONFIG_INVALID", "runner.skydiscover_task_ref must resolve to a Docker evaluator")
        if config.runner.type == "skydiscover_python" and resolved["target_kind"] != "skydiscover_python_evaluator":
            raise AlabError("CONFIG_INVALID", "runner.skydiscover_task_ref must resolve to a Python evaluator")


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


def _runner_sandbox_summary(*args: Any, **kwargs: Any) -> Any:
    from .project_config import _runner_sandbox_summary as _impl

    return _impl(*args, **kwargs)


def _exportable_config_json(*args: Any, **kwargs: Any) -> Any:
    from .project_config import _exportable_config_json as _impl

    return _impl(*args, **kwargs)


RUNTIME_CONFIG_KEYS = {"source", "runner", "reward", "artifacts", "logs", "env", "secret_env"}


def _runtime_signature(*args: Any, **kwargs: Any) -> Any:
    from .project_config import _runtime_signature as _impl

    return _impl(*args, **kwargs)


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


def _secret_marker_summary(*args: Any, **kwargs: Any) -> Any:
    from .project_config import _secret_marker_summary as _impl

    return _impl(*args, **kwargs)


def _validate_env_name(*args: Any, **kwargs: Any) -> Any:
    from .project_config import _validate_env_name as _impl

    return _impl(*args, **kwargs)


def _apply_project_config(*args: Any, **kwargs: Any) -> Any:
    from .project_config import _apply_project_config as _impl

    return _impl(*args, **kwargs)


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
    from .project_config import cmd_project_config_show as _impl

    return _impl(args, req)


def cmd_project_config_export(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_config import cmd_project_config_export as _impl

    return _impl(args, req)


def cmd_project_config_import(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_config import cmd_project_config_import as _impl

    return _impl(args, req)


def cmd_project_config_set(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_config import cmd_project_config_set as _impl

    return _impl(args, req)


def cmd_project_env_list(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_config import cmd_project_env_list as _impl

    return _impl(args, req)


def cmd_project_env_set(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_config import cmd_project_env_set as _impl

    return _impl(args, req)


def cmd_project_env_unset(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_config import cmd_project_env_unset as _impl

    return _impl(args, req)


def _read_secret_input(*args: Any, **kwargs: Any) -> Any:
    from .project_config import _read_secret_input as _impl

    return _impl(*args, **kwargs)


def cmd_project_secret_list(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_config import cmd_project_secret_list as _impl

    return _impl(args, req)


def cmd_project_secret_set(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_config import cmd_project_secret_set as _impl

    return _impl(args, req)


def cmd_project_secret_unset(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_config import cmd_project_secret_unset as _impl

    return _impl(args, req)


def _referenced_secret_ids(*args: Any, **kwargs: Any) -> Any:
    from .project_config import _referenced_secret_ids as _impl

    return _impl(*args, **kwargs)


def cmd_project_secret_gc(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_config import cmd_project_secret_gc as _impl

    return _impl(args, req)


def cmd_project_validate(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_validation import cmd_project_validate as _impl

    return _impl(args, req)


def _validation_row(*args: Any, **kwargs: Any) -> Any:
    from .project_validation import _validation_row as _impl

    return _impl(*args, **kwargs)


def _validation_blockers(*args: Any, **kwargs: Any) -> Any:
    from .project_validation import _validation_blockers as _impl

    return _impl(*args, **kwargs)


def cmd_project_validation_archive(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_validation import cmd_project_validation_archive as _impl

    return _impl(args, req)


def cmd_project_validation_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_validation import cmd_project_validation_unarchive as _impl

    return _impl(args, req)


def cmd_project_validation_remove(args: list[str], req: Request) -> list[ResultBlock]:
    from .project_validation import cmd_project_validation_remove as _impl

    return _impl(args, req)


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


def _reward_identity_from_config_json(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _reward_identity_from_config_json as _impl

    return _impl(*args, **kwargs)


def _reward_direction_from_config_json(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _reward_direction_from_config_json as _impl

    return _impl(*args, **kwargs)


def _config_json_for_version(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _config_json_for_version as _impl

    return _impl(*args, **kwargs)


def _current_visibility_policy(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _current_visibility_policy as _impl

    return _impl(*args, **kwargs)


def _intersect_visibility(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _intersect_visibility as _impl

    return _impl(*args, **kwargs)


def _public_from_exp_visible(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _public_from_exp_visible as _impl

    return _impl(*args, **kwargs)


def _visible_exp_ids(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _visible_exp_ids as _impl

    return _impl(*args, **kwargs)


def _append_visible_exp_clause(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _append_visible_exp_clause as _impl

    return _impl(*args, **kwargs)


def _exp_visible(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _exp_visible as _impl

    return _impl(*args, **kwargs)


def _best_context(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _best_context as _impl

    return _impl(*args, **kwargs)


def _optional_best_context(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _optional_best_context as _impl

    return _impl(*args, **kwargs)


def _best_run_for_experiment(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _best_run_for_experiment as _impl

    return _impl(*args, **kwargs)


def _sql_in_clause(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _sql_in_clause as _impl

    return _impl(*args, **kwargs)


def _reward_identity_config_versions(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _reward_identity_config_versions as _impl

    return _impl(*args, **kwargs)


def _best_run_window_order(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _best_run_window_order as _impl

    return _impl(*args, **kwargs)


def _best_run_sql_clauses(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _best_run_sql_clauses as _impl

    return _impl(*args, **kwargs)


def _append_experiment_search_clause(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _append_experiment_search_clause as _impl

    return _impl(*args, **kwargs)


def _experiment_query_clauses(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _experiment_query_clauses as _impl

    return _impl(*args, **kwargs)


def _experiment_candidate_sql(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _experiment_candidate_sql as _impl

    return _impl(*args, **kwargs)


def _experiment_requested_sort_field(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _experiment_requested_sort_field as _impl

    return _impl(*args, **kwargs)


def _experiment_order_limit_clause(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _experiment_order_limit_clause as _impl

    return _impl(*args, **kwargs)


def _best_run_from_joined_experiment_row(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _best_run_from_joined_experiment_row as _impl

    return _impl(*args, **kwargs)


def _reward_bound_sql(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _reward_bound_sql as _impl

    return _impl(*args, **kwargs)


def _best_runs_for_experiments(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _best_runs_for_experiments as _impl

    return _impl(*args, **kwargs)


def _experiment_page_rows(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _experiment_page_rows as _impl

    return _impl(*args, **kwargs)


def _experiment_rows_with_ranked_best(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _experiment_rows_with_ranked_best as _impl

    return _impl(*args, **kwargs)


def _experiment_list_search_rows_with_best(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _experiment_list_search_rows_with_best as _impl

    return _impl(*args, **kwargs)


def _incomparable_best_run_count(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _incomparable_best_run_count as _impl

    return _impl(*args, **kwargs)


def _experiment_best_rows_with_excluded_count(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _experiment_best_rows_with_excluded_count as _impl

    return _impl(*args, **kwargs)


def _experiment_result_block(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _experiment_result_block as _impl

    return _impl(*args, **kwargs)


def _require_experiment_query_options_at_most_once(*args: Any, **kwargs: Any) -> Any:
    from .experiment_query import _require_experiment_query_options_at_most_once as _impl

    return _impl(*args, **kwargs)


def cmd_exp_list(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_query import cmd_exp_list as _impl

    return _impl(args, req)


def _exp_row(conn, project_id: str, exp_id: str | None) -> Any:
    exp_id = _complete_id_or_missing(exp_id, prefix="exp", code="EXPERIMENT_NOT_FOUND", label="experiment id")
    row = one(conn, "SELECT * FROM experiments WHERE project_id = ? AND exp_id = ?", (project_id, exp_id))
    if row is None:
        raise AlabError("EXPERIMENT_NOT_FOUND", "experiment not found")
    return row


def cmd_exp_search(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_query import cmd_exp_search as _impl

    return _impl(args, req)


def cmd_exp_show(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_query import cmd_exp_show as _impl

    return _impl(args, req)


def cmd_exp_best(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_query import cmd_exp_best as _impl

    return _impl(args, req)


def cmd_exp_archive(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_lifecycle import cmd_exp_archive as _impl

    return _impl(args, req)


def cmd_exp_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_lifecycle import cmd_exp_unarchive as _impl

    return _impl(args, req)


def _stored_relative_path(*args: Any, **kwargs: Any) -> Any:
    from .experiment_lifecycle import _stored_relative_path as _impl

    return _impl(*args, **kwargs)


def _artifact_log_filesystem_targets(*args: Any, **kwargs: Any) -> Any:
    from .experiment_lifecycle import _artifact_log_filesystem_targets as _impl

    return _impl(*args, **kwargs)


def _experiment_remove_filesystem_targets(*args: Any, **kwargs: Any) -> Any:
    from .experiment_lifecycle import _experiment_remove_filesystem_targets as _impl

    return _impl(*args, **kwargs)


def cmd_exp_remove(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_lifecycle import cmd_exp_remove as _impl

    return _impl(args, req)


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


def _resolve_exp_commit(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _resolve_exp_commit as _impl

    return _impl(*args, **kwargs)


def _resolve_commit_sha_selector(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _resolve_commit_sha_selector as _impl

    return _impl(*args, **kwargs)


def _path_registry_row_for_token(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _path_registry_row_for_token as _impl

    return _impl(*args, **kwargs)


def _token_path_status(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _token_path_status as _impl

    return _impl(*args, **kwargs)


def _active_worktree_token(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _active_worktree_token as _impl

    return _impl(*args, **kwargs)


def _source_branch_ref(source_ref: str) -> str:
    if not source_ref.startswith("alab/source/src-"):
        raise AlabError("GIT_ERROR", "refusing to delete unexpected source branch")
    return f"refs/heads/{source_ref}"


def _experiment_branch_ref(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _experiment_branch_ref as _impl

    return _impl(*args, **kwargs)


def _git_ref_commit(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _git_ref_commit as _impl

    return _impl(*args, **kwargs)


def _delete_experiment_branch_ref(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _delete_experiment_branch_ref as _impl

    return _impl(*args, **kwargs)


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


def _restore_experiment_branch_ref(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _restore_experiment_branch_ref as _impl

    return _impl(*args, **kwargs)


def _restore_source_ref(repo_git: Path, deletion: GitRefDeletion | None) -> None:
    if deletion is None or not deletion.deleted or deletion.commit is None:
        return
    result = run_cmd(["git", f"--git-dir={repo_git}", "update-ref", deletion.branch_ref, deletion.commit], check=False)
    if result.returncode != 0:
        reason = result.stderr.decode("utf-8", errors="replace").strip() or "failed to restore source branch ref"
        raise AlabError("GIT_ERROR", reason)


def _prune_missing_git_worktrees(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _prune_missing_git_worktrees as _impl

    return _impl(*args, **kwargs)


def cmd_exp_worktree_remove(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_access import cmd_exp_worktree_remove as _impl

    return _impl(args, req)


def cmd_exp_worktree_restore(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_access import cmd_exp_worktree_restore as _impl

    return _impl(args, req)


def _credential_selector_sql(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _credential_selector_sql as _impl

    return _impl(*args, **kwargs)


def cmd_exp_token_list(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_access import cmd_exp_token_list as _impl

    return _impl(args, req)


def cmd_exp_token_revoke(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_access import cmd_exp_token_revoke as _impl

    return _impl(args, req)


def cmd_exp_token_regenerate(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_access import cmd_exp_token_regenerate as _impl

    return _impl(args, req)


def cmd_exp_checkout(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_access import cmd_exp_checkout as _impl

    return _impl(args, req)


def _authorize_checkout_remove(*args: Any, **kwargs: Any) -> Any:
    from .experiment_access import _authorize_checkout_remove as _impl

    return _impl(*args, **kwargs)


def cmd_exp_checkout_remove(args: list[str], req: Request) -> list[ResultBlock]:
    from .experiment_access import cmd_exp_checkout_remove as _impl

    return _impl(args, req)


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
