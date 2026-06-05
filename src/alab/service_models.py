from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .auth import Actor
from .context import Context
from .home import Home
from .rendering import ResultBlock


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
class LongRunningResult:
    blocks: list[ResultBlock]
    run: Callable[[], int]
    close: Callable[[], None] | None = None


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
class ResolvedRemovalTarget:
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

ANNOTATION_TARGET_ID_PREFIXES = {
    "artifact": "art",
    "experiment": "exp",
    "run": "run",
}
ANNOTATION_TARGET_TYPES = {"none", "artifact", "experiment", "run", "path", "lines"}

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
