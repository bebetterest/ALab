from __future__ import annotations

import ast
import base64
import inspect
import io
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from typer.testing import CliRunner

from alab import cli, registry, services
from alab.errors import ERROR_EXIT_CODES, AlabError, error_exit_code
from alab.home import Home, resolve_home
from alab.rendering import ResultBlock, multiline_text, render_text

_GUARDED_HELPERS = (
    "_archive_observe_record",
    "_remove_observe_record",
    "_set_annotation_status",
    "_unarchive_observe_record",
)

_POSITIONAL_VALIDATORS = {
    "optional_positional_selector",
    "require_positional_count",
}

_POSITIONAL_VALIDATION_HELPERS = _GUARDED_HELPERS

_KNOWN_FLAG_OPTIONS = {
    "--all",
    "--apply",
    "--body-stdin",
    "--cascade",
    "--docker-images",
    "--dry-run",
    "--feedback-stdin",
    "--force",
    "--history",
    "--include-archived",
    "--include-hidden",
    "--no-open",
    "--overwrite",
    "--private",
    "--refresh-capabilities",
    "--rerun",
    "--skip-baseline-test",
    "--skydiscover-envs",
    "--source-empty",
    "--summary-stdin",
    "--trash",
    "--trash-all",
    "--value-stdin",
}

_KNOWN_CREDENTIAL_SURFACES = {
    "admin",
    "none",
    "public",
    "public_or_admin",
    "root",
    "token",
    "token_or_admin",
}

_CAPABILITY_PATH_SETS = (
    cli.GLOBAL_PUBLIC,
    cli.PUBLIC_PROJECT,
    cli.PUBLIC_PROJECT_WHEN_ENABLED,
    cli.EXPERIMENT_TOKEN,
    cli.OBSERVE_READ,
    cli.OBSERVE_TOKEN_LIFECYCLE,
    cli.INSPECTION_TOKEN,
)

_LIFECYCLE_ARCHIVE_UNARCHIVE_EVIDENCE = {
    ("project", "archive"): (
        "tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash",
        "tests/test_cli_contract.py::test_project_lifecycle_success_fields_follow_cli_spec",
    ),
    ("project", "unarchive"): (
        "tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash",
        "tests/test_cli_contract.py::test_project_lifecycle_success_fields_follow_cli_spec",
    ),
    ("project", "validation", "archive"): (
        "tests/test_smoke.py::test_config_source_observe_and_tags",
        "tests/test_cli_contract.py::test_project_validation_lifecycle_success_fields_follow_cli_spec",
    ),
    ("project", "validation", "unarchive"): (
        "tests/test_smoke.py::test_config_source_observe_and_tags",
        "tests/test_cli_contract.py::test_project_validation_lifecycle_success_fields_follow_cli_spec",
    ),
    ("source", "archive"): (
        "tests/test_smoke.py::test_config_source_observe_and_tags",
        "tests/test_cli_contract.py::test_source_lifecycle_success_fields_follow_cli_spec",
    ),
    ("source", "unarchive"): (
        "tests/test_smoke.py::test_config_source_observe_and_tags",
        "tests/test_cli_contract.py::test_source_lifecycle_success_fields_follow_cli_spec",
    ),
    ("exp", "archive"): (
        "tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths",
    ),
    ("exp", "unarchive"): (
        "tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths",
    ),
    ("observe", "runs", "archive"): (
        "tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata",
    ),
    ("observe", "runs", "unarchive"): (
        "tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata",
    ),
    ("observe", "artifacts", "archive"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("observe", "artifacts", "unarchive"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("observe", "logs", "archive"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("observe", "logs", "unarchive"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("runs", "archive"): (
        "tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata",
    ),
    ("runs", "unarchive"): (
        "tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata",
    ),
    ("artifacts", "archive"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("artifacts", "unarchive"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("logs", "archive"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("logs", "unarchive"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("annotate", "archive"): (
        "tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations",
        "tests/test_cli_contract.py::test_annotation_success_fields_follow_cli_spec",
    ),
    ("annotate", "unarchive"): (
        "tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations",
        "tests/test_cli_contract.py::test_annotation_success_fields_follow_cli_spec",
    ),
}

_LIFECYCLE_REMOVE_EVIDENCE = {
    ("project", "remove"): (
        "tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash",
        "tests/test_cli_contract.py::test_project_lifecycle_success_fields_follow_cli_spec",
    ),
    ("project", "validation", "remove"): (
        "tests/test_smoke.py::test_config_source_observe_and_tags",
    ),
    ("source", "remove"): (
        "tests/test_smoke.py::test_config_source_observe_and_tags",
        "tests/test_cli_contract.py::test_source_lifecycle_success_fields_follow_cli_spec",
    ),
    ("exp", "remove"): (
        "tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths",
    ),
    ("exp", "checkout", "remove"): (
        "tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations",
    ),
    ("exp", "worktree", "remove"): (
        "tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations",
    ),
    ("observe", "runs", "remove"): (
        "tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata",
    ),
    ("observe", "artifacts", "remove"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("observe", "logs", "remove"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("runs", "remove"): (
        "tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata",
    ),
    ("artifacts", "remove"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("logs", "remove"): (
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
    ),
    ("annotate", "remove"): (
        "tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations",
        "tests/test_cli_contract.py::test_annotation_success_fields_follow_cli_spec",
    ),
    ("catalog", "skydiscover", "remove"): (
        "tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history",
    ),
}

_HOME_FILESYSTEM_EVIDENCE = {
    "home_resolution_and_layout": (
        "tests/test_smoke.py::test_auth_init_and_config_show",
        "tests/test_cli_contract.py::test_alab_home_layout_and_markers_follow_blueprint",
        "tests/test_cli_contract.py::test_home_exists_and_output_exists_render_stable_error_blocks",
        "tests/test_cli_contract.py::test_registered_commands_reject_global_option_errors_before_home_creation",
        "tests/test_cli_contract.py::test_global_repair_command_success_fields_follow_cli_spec",
    ),
    "path_registry_hashing_and_reuse": (
        "tests/test_migrations.py::test_removed_path_registry_rows_do_not_block_path_reuse",
        "tests/test_migrations.py::test_path_hash_case_normalizes_on_case_insensitive_filesystems",
        "tests/test_migrations.py::test_path_hash_detects_case_insensitive_parent_for_missing_child",
        "tests/test_migrations.py::test_path_hash_preserves_case_on_case_sensitive_filesystems",
    ),
    "context_marker_contracts_and_conflicts": (
        "tests/test_migrations.py::test_context_marker_json_contract_enforces_documented_shape",
        "tests/test_cli_contract.py::test_status_object_type_tracks_context_mode",
        "tests/test_cli_contract.py::test_context_marker_conflicts_are_strict_and_side_effect_free",
        "tests/test_cli_contract.py::test_explicit_keys_preserve_context_conflict_before_handler_effects",
    ),
    "worktree_checkout_and_repair_paths": (
        "tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations",
        "tests/test_smoke.py::test_context_self_repair_requires_registered_branch",
        "tests/test_cli_contract.py::test_cli_token_writes_use_private_permissions_and_git_exclude",
    ),
}

_SOURCE_PUBLIC_EXPERIMENT_EVIDENCE = {
    "canonical_source_storage_and_metadata": (
        "tests/test_smoke.py::test_canonical_tree_hash_manifest_matches_v1_spec",
        "tests/test_migrations.py::test_source_origin_metadata_contract_enforces_documented_shape",
        "tests/test_smoke.py::test_project_init_requires_explicit_mode_source_origin",
        "tests/test_smoke.py::test_project_init_source_ref_mismatch_cleans_staged_paths",
    ),
    "standalone_source_import_selectors_and_warnings": (
        "tests/test_cli_contract.py::test_source_import_origin_variants_success_fields_follow_cli_spec",
        "tests/test_cli_contract.py::test_source_import_warning_success_fields_follow_cli_spec",
        "tests/test_smoke.py::test_source_import_dedupes_active_sources_and_ignores_archived",
        "tests/test_smoke.py::test_source_import_respects_git_and_alab_ignore_rules",
        "tests/test_smoke.py::test_source_import_empty_after_filter_warns",
        "tests/test_smoke.py::test_standalone_source_import_limit_failure_is_atomic",
        "tests/test_smoke.py::test_source_selector_option_scope_errors_do_not_write",
    ),
    "public_inline_source_import": (
        "tests/test_smoke.py::test_public_exp_create_inline_source_import",
        "tests/test_smoke.py::test_public_inline_source_import_enforces_project_limits",
        "tests/test_smoke.py::test_public_inline_source_import_disabled_requires_admin",
        "tests/test_cli_contract.py::test_experiment_create_inline_source_variants_success_fields_follow_cli_spec",
    ),
    "public_from_exp_and_visibility": (
        "tests/test_smoke.py::test_public_exp_create_from_exp_uses_latest_commit",
        "tests/test_smoke.py::test_public_from_exp_respects_visibility_upper_bound",
        "tests/test_cli_contract.py::test_experiment_create_from_exp_success_fields_follow_cli_spec",
    ),
    "archived_source_and_source_ref": (
        "tests/test_smoke.py::test_admin_exp_create_can_bind_archived_source_ref",
        "tests/test_smoke.py::test_config_source_observe_and_tags",
        "tests/test_cli_contract.py::test_experiment_create_source_ref_success_fields_follow_cli_spec",
    ),
    "adapter_source_bootstrap": (
        "tests/test_smoke.py::test_harbor_project_init_uses_declared_source_and_excludes_private_assets",
        "tests/test_smoke.py::test_adapter_init_rejects_conflicting_explicit_source",
        "tests/test_smoke.py::test_skydiscover_project_init_uses_initial_program_metadata",
        "tests/test_smoke.py::test_skydiscover_project_init_requires_initial_program_without_explicit_source",
        "tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections",
        "tests/test_smoke.py::test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program",
        "tests/test_cli_contract.py::test_project_init_adapter_mode_variants_success_fields_follow_cli_spec",
    ),
}

_RUNNER_ADAPTER_EVIDENCE = {
    "shared_runner_contract": (
        "tests/test_runner_local.py::test_sanitized_local_runner_creates_temp_home_and_strips_alab_credentials",
        "tests/test_runner_local.py::test_full_local_runner_strips_alab_credentials_and_internal_env_overrides",
        "tests/test_runner_local.py::test_local_runner_stdin_is_closed",
        "tests/test_runner_docker.py::test_docker_runner_env_is_hostless_and_internal_env_overrides_config_env",
        "tests/test_runner_docker.py::test_docker_runner_timeout_removes_named_container_and_redacts_output",
        "tests/test_runner_harbor.py::test_harbor_adapter_resolver_failures_do_not_create_runtime_dirs",
        "tests/test_runner_skydiscover.py::test_skydiscover_adapter_resolver_failures_do_not_create_runtime_dirs",
        "tests/test_smoke.py::test_runner_workspace_is_contextless_and_stdin_closed",
        "tests/test_smoke.py::test_run_and_submit_use_experiment_operation_lock",
    ),
    "project_config_schema_and_saved_failures": (
        "tests/test_runner_local.py::test_project_config_schema_maps_runner_reward_and_env_edges",
        "tests/test_runner_local.py::test_project_config_schema_validates_secret_env_shapes",
        "tests/test_runner_local.py::test_project_config_schema_validates_policy_field_shapes",
        "tests/test_runner_docker.py::test_docker_config_paths_must_stay_inside_workspace",
        "tests/test_runner_docker.py::test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors",
        "tests/test_smoke.py::test_missing_runner_working_directory_is_saved_as_baseline_and_run_error",
        "tests/test_smoke.py::test_missing_file_reward_is_saved_as_baseline_and_run_failure",
    ),
    "local_runner_and_rewards": (
        "tests/test_runner_local.py::test_local_runner_warns_when_secret_values_and_artifact_globs_are_configured",
        "tests/test_runner_local.py::test_local_runner_timeout_terminates_child_process_group",
        "tests/test_runner_local.py::test_stdout_regex_reward_uses_redacted_and_truncated_stdout",
        "tests/test_runner_local.py::test_local_runner_shell_mode_runs_through_sh",
        "tests/test_runner_local.py::test_exit_code_reward_parses_zero_and_nonzero_exits",
        "tests/test_runner_local.py::test_file_reward_parses_json_and_enforces_limit_and_finite_values",
        "tests/test_cli_contract.py::test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit",
    ),
    "docker_runner_fake_default": (
        "tests/test_runner_docker.py::test_docker_build_cache_key_respects_dockerignore",
        "tests/test_runner_docker.py::test_docker_build_cache_key_ignores_run_time_fields",
        "tests/test_runner_docker.py::test_docker_runner_pulls_missing_image_and_uses_default_network_without_visible_setup",
        "tests/test_runner_docker.py::test_docker_runner_contract_with_fake_docker",
        "tests/test_runner_docker.py::test_docker_runner_shell_uses_container_sh",
        "tests/test_runner_docker.py::test_config_validate_refreshes_docker_capability_cache",
        "tests/test_runner_docker.py::test_project_init_rejects_unsupported_docker_resource_limit",
        "tests/test_runner_docker.py::test_project_init_records_docker_unavailable_baseline_error",
        "tests/test_runner_docker.py::test_docker_setup_pull_and_build_failures_are_saved_result_failures",
    ),
    "artifact_and_log_lifecycle": (
        "tests/test_runner_local.py::test_artifact_capture_ignores_symlink_escape_with_sibling_prefix",
        "tests/test_runner_local.py::test_artifact_capture_expands_directories_sorts_and_deduplicates",
        "tests/test_smoke.py::test_artifact_capture_errors_are_warning_codes_for_validations_and_runs",
        "tests/test_smoke.py::test_oversized_artifacts_are_skipped_without_failing_validation_or_run",
        "tests/test_smoke.py::test_artifact_bytes_not_redacted_warning_is_persisted_and_rendered",
        "tests/test_smoke.py::test_log_secret_redaction_happens_before_truncation",
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
        "tests/test_smoke.py::test_shared_log_file_reference_counting",
    ),
    "harbor_adapter_fake_default": (
        "tests/test_runner_harbor.py::test_harbor_shared_verifier_runs_with_hidden_logs_and_secret_redaction",
        "tests/test_runner_harbor.py::test_harbor_separate_verifier_image_runs_with_hidden_logs",
        "tests/test_runner_harbor.py::test_harbor_separate_tests_dockerfile_builds_image_cache",
        "tests/test_runner_harbor.py::test_harbor_timeout_removes_named_container_and_keeps_output_hidden",
        "tests/test_runner_harbor.py::test_harbor_task_rejects_unsupported_fields",
        "tests/test_smoke.py::test_harbor_project_init_uses_declared_source_and_excludes_private_assets",
        "tests/test_smoke.py::test_harbor_baseline_records_reward_and_hidden_logs",
    ),
    "skydiscover_catalog_source_and_evaluators": (
        "tests/test_smoke.py::test_skydiscover_catalog_lifecycle",
        "tests/test_smoke.py::test_skydiscover_catalog_ref_validation",
        "tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history",
        "tests/test_smoke.py::test_skydiscover_project_init_source_precedence_and_rejections",
        "tests/test_runner_skydiscover.py::test_skydiscover_docker_runner_builds_hidden_bundle_and_parses_metrics",
        "tests/test_runner_skydiscover.py::test_skydiscover_python_runner_materializes_hidden_bundle_and_metrics",
        "tests/test_runner_skydiscover.py::test_skydiscover_python_runner_env_boundary_and_redaction",
        "tests/test_runner_skydiscover.py::test_skydiscover_python_runner_reuses_uv_environment_cache",
        "tests/test_smoke.py::test_skydiscover_python_dependency_failures_are_saved_results",
        "tests/test_smoke.py::test_skydiscover_docker_baseline_records_metrics_and_hidden_logs",
    ),
    "real_environment_gates": (
        "tests/test_cli_contract.py::test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests",
        "tests/test_real_docker.py::test_real_docker_runner_mount_env_and_reward",
        "tests/test_real_docker.py::test_real_harbor_runner_shared_verifier",
        "tests/test_real_docker.py::test_real_skydiscover_docker_runner_evaluator",
        "tests/test_real_skydiscover_catalog.py::test_live_skydiscover_catalog_add_show_and_resolve_project_init",
        "tests/test_real_skydiscover_python.py::test_real_skydiscover_python_uv_dependency_install_and_cache",
    ),
}

_STORAGE_AUDIT_OBJECT_EVIDENCE = {
    "schema_index_and_json_contracts": (
        "tests/test_migrations.py::test_database_connections_use_wal_mode",
        "tests/test_migrations.py::test_database_connections_use_configured_busy_timeout",
        "tests/test_migrations.py::test_required_storage_tables_and_columns_are_created",
        "tests/test_migrations.py::test_required_storage_indexes_are_created",
        "tests/test_migrations.py::test_representative_ddl_enum_checks_are_enforced",
        "tests/test_migrations.py::test_contract_json_obj_enforces_schema_version_and_known_keys",
        "tests/test_migrations.py::test_audit_json_contracts_enforce_documented_shape",
        "tests/test_migrations.py::test_runtime_catalog_and_cache_metadata_contracts_enforce_documented_shape",
    ),
    "maintenance_and_catalog_audit_relationships": (
        "tests/test_smoke.py::test_auth_init_and_config_show",
        "tests/test_smoke.py::test_cache_prune_removes_trash_cache_entries",
        "tests/test_smoke.py::test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry",
        "tests/test_smoke.py::test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history",
        "tests/test_cli_contract.py::test_audit_success_fields_follow_cli_spec",
    ),
    "credential_token_and_context_audit_relationships": (
        "tests/test_smoke.py::test_auth_init_and_config_show",
        "tests/test_smoke.py::test_config_source_observe_and_tags",
        "tests/test_smoke.py::test_context_self_repair_requires_registered_branch",
        "tests/test_cli_contract.py::test_experiment_token_success_fields_follow_cli_spec",
        "tests/test_cli_contract.py::test_project_admin_key_authority_edges_are_scoped_and_side_effect_free",
        "tests/test_cli_contract.py::test_home_filesystem_and_path_registry_evidence_map_refs_stay_current",
    ),
    "lifecycle_remove_retained_rows_and_trash": (
        "tests/test_cli_contract.py::test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces",
        "tests/test_smoke.py::test_config_source_observe_and_tags",
        "tests/test_smoke.py::test_experiment_remove_cascades_filesystem_paths",
        "tests/test_smoke.py::test_project_remove_cascades_whole_tree_through_trash",
        "tests/test_smoke.py::test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata",
        "tests/test_smoke.py::test_artifact_and_log_remove_use_reference_counted_trash",
        "tests/test_smoke.py::test_validation_and_run_artifacts_share_blob_reference_counting",
    ),
    "annotation_and_visibility_audit_relationships": (
        "tests/test_smoke.py::test_tokens_checkout_worktree_and_annotations",
        "tests/test_smoke.py::test_experiment_search_best_and_same_project_visibility",
        "tests/test_cli_contract.py::test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit",
        "tests/test_cli_contract.py::test_annotation_authorization_matrix_blocks_peer_and_inspection_mutations",
    ),
}

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC_CLI_PATH = _REPO_ROOT / "docs" / "spec_cli.md"
_SPEC_CLI_CN_PATH = _REPO_ROOT / "docs" / "spec_cli_cn.md"
_COMPLETION_AUDIT_PATH = _REPO_ROOT / "docs" / "completion_audit.md"
_COMPLETION_AUDIT_CN_PATH = _REPO_ROOT / "docs" / "completion_audit_cn.md"
_README_PATH = _REPO_ROOT / "README.md"
_README_CN_PATH = _REPO_ROOT / "README_cn.md"
_PYPROJECT_PATH = _REPO_ROOT / "pyproject.toml"
_GITIGNORE_PATH = _REPO_ROOT / ".gitignore"
_ENV_EXAMPLE_PATH = _REPO_ROOT / ".env.example"
_TESTS_ROOT = _REPO_ROOT / "tests"
_SRC_ROOT = _REPO_ROOT / "src" / "alab"
_EXAMPLES_ROOT = _REPO_ROOT / "examples"
_PAIRED_MARKDOWN_ROOTS = (_REPO_ROOT, _REPO_ROOT / "docs")
_MARKDOWN_PAIR_EXCEPTIONS = {"潜在问题.md"}
_GLOBAL_CLI_OPTIONS = {"--home", "--key", "--key-stdin", "--output"}
_BANNED_RUNTIME_DEPENDENCY_ROOTS = {
    # Hosted services / remote web UI frameworks are outside ALab V1.
    "aiohttp",
    "dash",
    "django",
    "fastapi",
    "flask",
    "gradio",
    "gunicorn",
    "panel",
    "starlette",
    "streamlit",
    "uvicorn",
    # ORMs and remote database client stacks would violate the sqlite3/local-record boundary.
    "dataset",
    "peewee",
    "pony",
    "sqlalchemy",
    "tortoise",
    # Built-in agent, scheduler, and LLM-provider integrations are out of scope for V1.
    "airflow",
    "anthropic",
    "apscheduler",
    "celery",
    "cohere",
    "dramatiq",
    "groq",
    "langchain",
    "litellm",
    "llama_index",
    "mistralai",
    "openai",
    "prefect",
    "rq",
    "schedule",
}
_BANNED_SECURITY_DEPENDENCY_ROOTS = {
    "cryptography",
    "keyring",
    "nacl",
    "passlib",
    "pycryptodome",
    "pynacl",
}
_BANNED_SECURITY_SOURCE_PATTERNS = (
    r"\bencrypt(?:ed|ion|ing|or)?\b",
    r"\bdecrypt(?:ed|ion|ing|or)?\b",
    r"\bcipher(?:text)?\b",
    r"\bfernet\b",
    r"\bgrant(?:s)?\b",
    r"\bpublic_grant(?:s)?\b",
    r"\btoken_rewrap(?:ping)?\b",
    r"\b(?:rewrap|rewrapped|rewrapping)\b",
    r"\bper_record_dek\b",
    r"\bdek\b",
    r"\bdata_key(?:s)?\b",
)
_REQUIRED_GITIGNORE_PATTERNS = (
    "AGENTS.md",
    "AGENTS_cn.md",
    "CORE.md",
    "CORE_cn.md",
    ".env",
    ".env.*",
    "!.env.example",
)
_REQUIRED_ENV_EXAMPLE_KEYS = {
    "ALAB_DEBUG",
    "ALAB_HOME",
    "ALAB_KEY",
    "ALAB_NATIVE_SKYDISCOVER_PYTHON_MODULE",
    "ALAB_NATIVE_SKYDISCOVER_PYTHON_REQUIREMENT",
    "ALAB_RUN_LIVE_SKYDISCOVER_CATALOG",
    "ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON",
    "ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON",
    "ALAB_RUN_REAL_DOCKER",
    "ALAB_RUN_REAL_SKYDISCOVER_PYTHON",
    "PYTHONPATH",
    "UV_CACHE_DIR",
    "UV_DEFAULT_INDEX",
}
_WARNING_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]+$")
_COMMAND_OPTION_CONTRACT_PREFIXES = (
    "- Required args:",
    "- Required args：",
    "- Options:",
    "- Options：",
    "- Common options:",
    "- Common options：",
    "- Conflicts:",
    "- Conflicts：",
    "- Source conflicts:",
    "- Source conflicts：",
    "- Defaults:",
    "- Defaults：",
    "- Filters:",
    "- Filters：",
)

_SYNCED_SUCCESS_FIELD_COMMANDS = (
    "help",
    "auth init",
    "auth root regenerate",
    "config show",
    "config set",
    "config reset",
    "feedback",
    "report",
    "key create",
    "key list --root",
    "key list --project",
    "key revoke",
    "context show",
    "context repair",
    "project list",
    "project show",
    "project archive",
    "project unarchive",
    "project remove",
    "project init",
    "project config show",
    "project config export",
    "project config import",
    "project env set",
    "project env unset",
    "project env list",
    "project secret set",
    "project secret unset",
    "project secret list",
    "project secret gc",
    "project validate",
    "project validation archive",
    "project validation unarchive",
    "project validation remove",
    "project locks clear-stale",
    "backup prune",
    "cache prune",
    "audit list",
    "audit show",
    "source import",
    "source list",
    "source show",
    "source archive",
    "source unarchive",
    "source remove",
    "catalog skydiscover add",
    "catalog skydiscover show",
    "catalog skydiscover update",
    "catalog skydiscover remove",
    "exp create",
    "exp archive",
    "exp unarchive",
    "exp remove",
    "exp checkout",
    "exp checkout remove",
    "exp worktree remove",
    "exp worktree restore",
    "exp token list",
    "exp token revoke",
    "exp token regenerate",
    "exp tag add",
    "exp tag remove",
    "exp tag list",
    "run",
    "submit",
    "observe experiments list",
    "observe experiments search",
    "observe experiments show",
    "observe experiments best",
    "observe runs list",
    "observe runs show",
    "observe runs archive",
    "observe runs unarchive",
    "observe runs remove",
    "observe artifacts list",
    "observe artifacts show",
    "observe artifacts export",
    "observe artifacts archive",
    "observe artifacts unarchive",
    "observe artifacts remove",
    "observe logs list",
    "observe logs show",
    "observe logs export",
    "observe logs archive",
    "observe logs unarchive",
    "observe logs remove",
    "observe annotations list",
    "observe annotations show",
    "annotate add",
    "annotate edit",
    "annotate archive",
    "annotate unarchive",
    "annotate remove",
)

_SYNCED_SUCCESS_FIELD_OBJECTS = (
    ("help", "help_command"),
    ("config validate", "config"),
    ("config validate", "capability"),
)

_SYNCED_SUCCESS_FIELD_SCOPES = (
    ("status", "project"),
    ("status", "experiment"),
    ("status", "inspection"),
    ("status", "public-invalid"),
)

_SUCCESS_FIELD_COMMAND_VARIANTS = {
    "key list": ("key list --root", "key list --project"),
}

_SUCCESS_FIELD_OBJECT_CONTRACTS = {
    "help": ("help_command",),
    "config validate": ("config", "capability"),
}

_SUCCESS_FIELD_SCOPE_CONTRACTS = {
    "status": ("project", "experiment", "inspection", "public-invalid"),
}

_HELPER_OPTION_USAGE = {
    "_annotation_private_exp_selector": {"--private", "--private-to-exp"},
    "_credential_selector_sql": {"--all", "--mode", "--token-id"},
    "_experiment_mutable_override": {"--mutable-exclude", "--mutable-include"},
    "_experiment_visibility_override": {"--visibility-scope", "--visible-exp"},
    "_lifecycle_reason": {"--reason"},
    "_parse_audit_limit_offset": {"--limit", "--offset"},
    "_parse_limit_offset": {"--limit", "--offset"},
    "_project_id_from_request": {"--project"},
    "_read_annotation_body": {"--body", "--body-file", "--body-stdin"},
    "_read_secret_input": {"--value-file", "--value-stdin"},
    "_require_project_admin": {"--project"},
    "_sort_experiment_blocks": {"--sort"},
    "_sort_rows": {"--sort"},
    "_source_import_limits": {"--max-file-bytes", "--max-files", "--max-total-bytes"},
    "_source_origin_mode": {"--git-ref", "--source-empty", "--source-git", "--source-path", "--source-subdir"},
    "_source_origin_options": {"--git-ref", "--source-empty", "--source-git", "--source-path", "--source-ref", "--source-subdir"},
    "_prepare_source_work": {"--git-ref", "--source-empty", "--source-git", "--source-path", "--source-ref", "--source-subdir"},
    "require_dry_run_unforced": {"--confirm", "--dry-run", "--force"},
    "require_force_confirm": {"--confirm", "--force"},
}

_HELPER_KNOWN_OPTIONS = {
    "_archive_observe_record": {"--project"},
    "_remove_observe_record": {"--cascade", "--confirm", "--dry-run", "--force", "--project", "--reason"},
    "_set_annotation_status": {"--project"},
    "_unarchive_observe_record": {"--project"},
}

_VALUE_OPTION_READ_HELPER_ARG_INDEXES = {
    "_append_time_filter": 3,
    "_complete_id_option": 1,
    "_parse_bool_option": 1,
    "_parse_days": 1,
    "_parse_float_option": 1,
    "_parse_int_option": 1,
    "_parse_non_negative_int_option": 1,
    "_parse_positive_int_option": 1,
    "_parse_source_limit_arg": 1,
}

_REPEATABLE_COMMAND_OPTIONS = {
    "--mutable-exclude",
    "--mutable-include",
    "--ref",
    "--tag",
    "--visible-exp",
}

_HELPER_AT_MOST_ONCE_OPTIONS = {
    "_annotation_private_exp_selector": {"--private", "--private-to-exp"},
    "_credential_selector_sql": {"--all", "--mode", "--token-id"},
    "_experiment_visibility_override": {"--visibility-scope"},
    "_lifecycle_reason": {"--reason"},
    "_parse_audit_limit_offset": {"--limit", "--offset"},
    "_parse_limit_offset": {"--limit", "--offset"},
    "_prepare_source_work": {"--git-ref", "--source-empty", "--source-git", "--source-path", "--source-ref", "--source-subdir"},
    "_project_id_from_request": {"--project"},
    "_read_annotation_body": {"--body", "--body-file"},
    "_read_secret_input": {"--value-file", "--value-stdin"},
    "_require_experiment_query_options_at_most_once": {
        "--config-version",
        "--created-after",
        "--created-before",
        "--include-archived",
        "--limit",
        "--name-query",
        "--offset",
        "--reward-max",
        "--reward-min",
        "--sort",
        "--source-id",
        "--status",
        "--updated-after",
        "--updated-before",
    },
    "_require_project_admin": {"--project"},
    "_resolve_annotation_target": {"--target"},
    "_sort_experiment_blocks": {"--sort"},
    "_sort_rows": {"--sort"},
    "_source_import_limits": {"--max-file-bytes", "--max-files", "--max-total-bytes"},
    "_source_origin_mode": {"--git-ref", "--source-empty", "--source-git", "--source-path", "--source-subdir"},
    "_source_origin_options": {"--git-ref", "--source-empty", "--source-git", "--source-path", "--source-ref", "--source-subdir"},
    "require_dry_run_unforced": {"--confirm", "--force"},
    "require_force_confirm": {"--confirm", "--force"},
}

_DYNAMIC_SINGLETON_OPTION_HELPERS = {
    "_append_time_filter",
    "_complete_id_option",
    "_parse_bool_option",
    "_parse_days",
    "_parse_float_option",
    "_parse_int_option",
    "_parse_non_negative_int_option",
    "_parse_positive_int_option",
    "_parse_source_limit_arg",
}

_PAGINATION_INVALID_INTEGER_OPTIONS = {
    "--limit": ("not-an-integer", "--limit and --offset must be integers"),
    "--offset": ("not-an-integer", "--limit and --offset must be integers"),
}

_PAGINATION_INVALID_VALUE_OPTIONS = {
    "--limit": [
        _PAGINATION_INVALID_INTEGER_OPTIONS["--limit"],
        ("0", "--limit must be between 1 and 500"),
        ("501", "--limit must be between 1 and 500"),
    ],
    "--offset": [
        _PAGINATION_INVALID_INTEGER_OPTIONS["--offset"],
        ("-1", "--offset must be zero or greater"),
    ],
}

_AUDIT_PAGINATION_INVALID_VALUE_OPTIONS = {
    "--limit": [
        _PAGINATION_INVALID_INTEGER_OPTIONS["--limit"],
        ("0", "invalid audit pagination"),
        ("1001", "invalid audit pagination"),
    ],
    "--offset": [
        _PAGINATION_INVALID_INTEGER_OPTIONS["--offset"],
        ("-1", "invalid audit pagination"),
    ],
}

_SOURCE_LIMIT_INVALID_INTEGER_OPTIONS = {
    "--max-file-bytes": ("not-an-integer", "--max-file-bytes must be an integer"),
    "--max-files": ("not-an-integer", "--max-files must be an integer"),
    "--max-total-bytes": ("not-an-integer", "--max-total-bytes must be an integer"),
}

_SOURCE_LIMIT_INVALID_VALUE_OPTIONS = {
    "--max-file-bytes": [
        _SOURCE_LIMIT_INVALID_INTEGER_OPTIONS["--max-file-bytes"],
        ("-1", "--max-file-bytes must be non-negative"),
    ],
    "--max-files": [
        _SOURCE_LIMIT_INVALID_INTEGER_OPTIONS["--max-files"],
        ("-1", "--max-files must be non-negative"),
    ],
    "--max-total-bytes": [
        _SOURCE_LIMIT_INVALID_INTEGER_OPTIONS["--max-total-bytes"],
        ("-1", "--max-total-bytes must be non-negative"),
    ],
}

_RETENTION_INVALID_INTEGER_OPTIONS = {
    "--keep": ("not-an-integer", "--keep must be an integer"),
    "--older-than": ("not-an-integer", "--older-than must be an integer number of days"),
}

_RETENTION_INVALID_VALUE_OPTIONS = {
    "--keep": [
        _RETENTION_INVALID_INTEGER_OPTIONS["--keep"],
        ("-1", "--keep must be zero or greater"),
    ],
    "--older-than": [
        _RETENTION_INVALID_INTEGER_OPTIONS["--older-than"],
        ("-1", "--older-than must be zero or greater"),
    ],
}

_RFC3339_INVALID_TIME_OPTIONS = {
    "--created-after": ("2026-01-01 00:00:00Z", "invalid RFC 3339 timestamp"),
    "--created-before": ("2026-01-01 00:00:00Z", "invalid RFC 3339 timestamp"),
    "--ended-after": ("2026-01-01 00:00:00Z", "invalid RFC 3339 timestamp"),
    "--ended-before": ("2026-01-01 00:00:00Z", "invalid RFC 3339 timestamp"),
    "--started-after": ("2026-01-01 00:00:00Z", "invalid RFC 3339 timestamp"),
    "--started-before": ("2026-01-01 00:00:00Z", "invalid RFC 3339 timestamp"),
    "--updated-after": ("2026-01-01 00:00:00Z", "invalid RFC 3339 timestamp"),
    "--updated-before": ("2026-01-01 00:00:00Z", "invalid RFC 3339 timestamp"),
}

_EXPERIMENT_QUERY_STRUCTURED_INVALID_OPTIONS = {
    "--source-id": ("src-short", "object ids must be complete"),
    "--status": ("not-a-status", "--status must be one of archived, closed, open"),
    **{option: value for option, value in _RFC3339_INVALID_TIME_OPTIONS.items() if option in {"--created-after", "--created-before", "--updated-after", "--updated-before"}},
}

_TYPED_VALUE_HELPER_INVALID_OPTIONS = {
    "_annotation_created_by_filter": {
        "--created-by": ("exp-short", "object ids must be complete"),
    },
    "_annotation_target_id_filter": {
        "--target": ("exp-short", "object ids must be complete"),
        "--target-id": ("exp-short", "object ids must be complete"),
    },
    "_audit_object_id_filter": {
        "--object-id": ("src-short", "object ids must be complete"),
    },
    "_best_context": {
        "--config-version": [
            ("not-an-integer", "--config-version must be an integer"),
            ("0", "--config-version must be a positive integer"),
            ("-1", "--config-version must be a positive integer"),
        ],
    },
    "_commit_sha_filter": {
        "--commit": ("HEAD", "--commit must be a commit SHA"),
    },
    "_content_hash_filter": {
        "--content-hash": ("not-a-hash", "--content-hash must be sha256:<64-hex>"),
    },
    "_cache_cutoff": {
        "--older-than": _RETENTION_INVALID_VALUE_OPTIONS["--older-than"],
    },
    "_credential_selector_sql": {
        "--token-id": ("cred-short", "object ids must be complete"),
        "--mode": ("not-a-choice", "--mode must be one of inspection, worktree"),
    },
    "_full_commit_sha_filter": {
        "--commit": ("short-sha", "--commit requires a full commit SHA"),
    },
    "_experiment_visibility_override": {
        "--visibility-scope": ("not-a-choice", "--visibility-scope must be one of explicit, none, same_project"),
    },
    "_exp_commit_selector_filter": {
        "--commit": ("HEAD", "commit selector must be latest, final, best, or a commit SHA"),
        "--from-commit": ("HEAD", "commit selector must be latest, final, best, or a commit SHA"),
    },
    "_experiment_rows": {
        "--config-version": [
            ("not-an-integer", "--config-version must be an integer"),
            ("0", "--config-version must be a positive integer"),
            ("-1", "--config-version must be a positive integer"),
        ],
        **_EXPERIMENT_QUERY_STRUCTURED_INVALID_OPTIONS,
    },
    "_paginate_rows": _PAGINATION_INVALID_VALUE_OPTIONS,
    "_parse_audit_limit_offset": _AUDIT_PAGINATION_INVALID_VALUE_OPTIONS,
    "_parse_days": {
        "--older-than": _RETENTION_INVALID_VALUE_OPTIONS["--older-than"],
    },
    "_parse_limit_offset": _PAGINATION_INVALID_VALUE_OPTIONS,
    "_selected_config_row": {
        "--version": [
            ("0", "invalid config version selector"),
            ("-1", "invalid config version selector"),
        ],
    },
    "_sort_experiment_blocks": {
        "--sort": ("unsupported:desc", "--sort field is not supported for experiments"),
    },
    "_sql_order_limit_clause": _PAGINATION_INVALID_VALUE_OPTIONS,
    "_source_import_limits": _SOURCE_LIMIT_INVALID_VALUE_OPTIONS,
}

_DIRECT_TYPED_VALUE_PARSERS = {
    "_parse_bool_option": [("not-a-bool", "{option} must be true or false")],
    "_parse_days": [("not-an-integer", "{option} must be an integer number of days")],
    "_parse_float_option": [("not-a-number", "{option} must be numeric")],
    "_parse_int_option": [("not-an-integer", "{option} must be an integer")],
    "_parse_non_negative_int_option": [
        ("not-an-integer", "{option} must be an integer"),
        ("-1", "{option} must be zero or greater"),
    ],
    "_parse_positive_int_option": [
        ("not-an-integer", "{option} must be an integer"),
        ("0", "{option} must be a positive integer"),
        ("-1", "{option} must be a positive integer"),
    ],
}

_HANDLER_TYPED_VALUE_INVALID_OPTIONS = {
    "cmd_backup_prune": _RETENTION_INVALID_VALUE_OPTIONS,
}


def _called_names(obj: object) -> set[str]:
    source = inspect.getsource(obj)
    tree = ast.parse(source)
    calls: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    return calls


def _field_map(block: ResultBlock) -> dict[str, object]:
    return dict(block.fields)


def _field_labels(block: ResultBlock) -> list[str]:
    return ["object", *(label for label, _value in block.fields)]


def test_text_renderer_strict_object_blocks_follow_cli_spec() -> None:
    rendered = render_text(
        [
            ResultBlock(
                "example",
                [
                    ("nullable scalar", None),
                    ("literal none body", multiline_text("none")),
                    ("empty body", multiline_text("")),
                    ("body", multiline_text("line one\nline two")),
                    ("tag", ["alpha", "beta"]),
                ],
            ),
            ResultBlock(
                "warning",
                [
                    ("warning code", "TRACKED_SENSITIVE_SOURCE_FILE"),
                    ("path", "secret.env"),
                ],
            ),
        ]
    )

    assert rendered == (
        "object: example\n"
        "nullable scalar: none\n"
        "literal none body:\n"
        "  none\n"
        "empty body:\n"
        "  [empty]\n"
        "body:\n"
        "  line one\n"
        "  line two\n"
        "tag: alpha\n"
        "tag: beta\n"
        "\n"
        "object: warning\n"
        "warning code: TRACKED_SENSITIVE_SOURCE_FILE\n"
        "path: secret.env\n"
    )


def _output_field_labels(output: str) -> list[str]:
    labels: list[str] = []
    for line in output.splitlines():
        if not line or line.startswith("  "):
            continue
        label, _separator, _value = line.partition(":")
        labels.append(label)
    return labels


def _output_field_map(output: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in output.splitlines():
        if not line or line.startswith("  "):
            continue
        label, _separator, value = line.partition(": ")
        fields[label] = value
    return fields


def _feedback_record(output: str) -> tuple[dict[str, str], Path, dict[str, object]]:
    fields = _output_field_map(output)
    record_path = Path(fields["path"])
    metadata_path = Path(fields["metadata path"])
    body_path = Path(fields["body path"])
    assert metadata_path == record_path / "metadata.json"
    assert body_path == record_path / "body.md"
    return fields, record_path, json.loads(metadata_path.read_text(encoding="utf-8"))


def _assert_entropy_id(value: str, prefix: str) -> None:
    assert value.startswith(f"{prefix}-")
    suffix = value[len(prefix) + 1 :]
    assert len(suffix) == 22
    assert "=" not in suffix
    assert re.fullmatch(r"[A-Za-z0-9_-]{22}", suffix)
    assert len(base64.urlsafe_b64decode(suffix + "==")) == 16


def _error_field_labels() -> list[str]:
    return ["object", "message", "error code", "exit code", "reason", "next"]


def _literal_option_values(node: ast.AST) -> list[str]:
    if not isinstance(node, ast.Tuple | ast.List | ast.Set):
        return []
    values: list[str] = []
    for item in node.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str) or not item.value.startswith("--"):
            return []
        values.append(item.value)
    return values


def _literal_string_values(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        value = getattr(services, node.id, None)
        if isinstance(value, tuple | list | set) and all(isinstance(item, str) for item in value):
            return list(value)
    if not isinstance(node, ast.Tuple | ast.List | ast.Set):
        return []
    values: list[str] = []
    for item in node.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            return []
        values.append(item.value)
    return values


def _split_markdown_table_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    in_code = False
    for char in text:
        if char == "`":
            in_code = not in_code
            current.append(char)
        elif char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def _markdown_table_rows_after_heading(markdown_path: Path, heading: str) -> list[list[str]]:
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    seen_heading = False
    in_table = False
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not seen_heading:
            if stripped == heading:
                seen_heading = True
            continue
        if stripped.startswith("#") and in_table:
            break
        if not line.startswith("|"):
            if in_table and rows:
                break
            continue
        in_table = True
        cells = _split_markdown_table_row(line)
        if not cells or cells[0].startswith("---"):
            continue
        if cells[0] in {"Gate", "Blueprint area", "Requirement group from `docs/spec_tests.md`", "Spec area"}:
            continue
        rows.append(cells)
    return rows


def _expand_command_pattern(pattern: str) -> list[tuple[str, ...]]:
    if pattern in {"alab", "--help"} or pattern.startswith("--"):
        return []
    words = pattern.split()
    pipe_index = next((index for index, word in enumerate(words) if "|" in word), None)
    if pipe_index is None:
        return [tuple(words)]
    return [
        tuple([*words[:pipe_index], option, *words[pipe_index + 1 :]])
        for option in words[pipe_index].split("|")
    ]


def _documented_heading_paths(code_span: str) -> set[tuple[str, ...]]:
    words = [
        word
        for word in code_span.split()[1:]
        if word != "..."
        and "[" not in word
        and "]" not in word
        and not word.startswith("<")
        and "<" not in word
        and not word.startswith("(")
    ]
    paths = {tuple(word for word in words if "|" not in word)}
    paths.update(_expand_command_pattern(" ".join(words)))
    command_words: list[str] = []
    for word in words:
        if word.startswith("--"):
            break
        command_words.append(word)
    paths.add(tuple(word for word in command_words if "|" not in word))
    paths.update(_expand_command_pattern(" ".join(command_words)))
    return {path for path in paths if path}


def _markdown_command_heading_spans(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("- "):
        stripped = stripped[2:].lstrip()
        code_spans = [code_span for code_span in re.findall(r"`([^`]+)`", stripped) if code_span.startswith("alab ")]
        if len(code_spans) != 1 or stripped != f"`{code_spans[0]}`":
            return []
        return code_spans
    if not stripped.startswith("`alab "):
        return []
    return [code_span for code_span in re.findall(r"`([^`]+)`", stripped) if code_span.startswith("alab ")]


def _declared_pytest_markers() -> list[str]:
    config = tomllib.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))
    marker_entries = config["tool"]["pytest"]["ini_options"]["markers"]
    return [entry.split(":", 1)[0].strip() for entry in marker_entries]


def _readme_pytest_marker_commands(readme_path: Path) -> list[str]:
    text = readme_path.read_text(encoding="utf-8")
    return re.findall(r"\buv run pytest -m ([a-z][a-z0-9_]*)\b", text)


def _readme_environment_assignment_names(readme_path: Path) -> set[str]:
    text = readme_path.read_text(encoding="utf-8")
    return set(re.findall(r"\b([A-Z][A-Z0-9_]*)=", text))


def _readme_repository_tree_paths(readme_path: Path) -> list[str]:
    lines = readme_path.read_text(encoding="utf-8").splitlines()
    try:
        heading_index = lines.index("## Repository Structure")
    except ValueError:
        return []
    try:
        block_start = next(index for index in range(heading_index + 1, len(lines)) if lines[index].strip() == "```text")
        block_end = next(index for index in range(block_start + 1, len(lines)) if lines[index].strip() == "```")
    except StopIteration:
        return []

    paths: list[str] = []
    stack: list[str] = []
    for line in lines[block_start + 1 : block_end]:
        if line.strip() in {"", "."}:
            continue
        connector_index = max(line.find("├──"), line.find("└──"))
        if connector_index < 0:
            continue
        depth = connector_index // 4
        name = line[connector_index + 3 :].strip().rstrip("/")
        stack = [*stack[:depth], name]
        paths.append("/".join(stack))
    return paths


def _used_declared_pytest_markers() -> set[str]:
    declared = set(_declared_pytest_markers())
    used: set[str] = set()
    for test_path in sorted(_TESTS_ROOT.glob("test_*.py")):
        text = test_path.read_text(encoding="utf-8")
        used.update(marker for marker in re.findall(r"\bpytest\.mark\.([A-Za-z_][A-Za-z0-9_]*)\b", text) if marker in declared)
    return used


def _project_markdown_pair_gaps() -> tuple[list[str], list[str]]:
    missing_chinese: list[str] = []
    orphan_chinese: list[str] = []
    for root in _PAIRED_MARKDOWN_ROOTS:
        for path in sorted(root.glob("*.md")):
            rel = path.relative_to(_REPO_ROOT).as_posix()
            if rel in _MARKDOWN_PAIR_EXCEPTIONS:
                continue
            if path.stem.endswith("_cn"):
                english = path.with_name(path.stem.removesuffix("_cn") + path.suffix)
                if not english.is_file():
                    orphan_chinese.append(rel)
            else:
                chinese = path.with_name(path.stem + "_cn" + path.suffix)
                if not chinese.is_file():
                    missing_chinese.append(rel)
    return missing_chinese, orphan_chinese


def _gitignore_patterns() -> list[str]:
    return [
        line.strip()
        for line in _GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _env_example_keys() -> list[str]:
    keys: list[str] = []
    for line in _ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=.*", stripped)
        if match:
            keys.append(match.group(1))
    return keys


def _pyproject_dependency_roots() -> set[str]:
    config = tomllib.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))
    dependencies = config["project"].get("dependencies", [])
    roots: set[str] = set()
    for dependency in dependencies:
        match = re.match(r"\s*([A-Za-z0-9_.-]+)", dependency)
        if match:
            roots.add(match.group(1).lower().replace("-", "_"))
    return roots


def _runtime_import_roots() -> set[str]:
    roots: set[str] = set()
    for source_path in sorted(_SRC_ROOT.glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    roots.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".", 1)[0])
    return roots


def _implementation_security_boundary_files() -> list[Path]:
    return [
        *sorted(_SRC_ROOT.glob("*.py")),
        *sorted((_SRC_ROOT / "migrations").glob("*.sql")),
    ]


def _documented_primary_object_types(spec_path: Path) -> tuple[dict[tuple[str, ...], str], list[str]]:
    expected: dict[tuple[str, ...], str] = {}
    duplicate_assignments: list[str] = []
    in_table = False

    for line in spec_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("Primary object types"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            if expected:
                break
            continue
        if line.startswith("| ---") or line.startswith("| Command pattern"):
            continue
        cells = _split_markdown_table_row(line)
        if len(cells) != 2 or "repeated" in cells[0]:
            continue
        object_types = re.findall(r"`([^`]+)`", cells[1])
        if len(object_types) != 1:
            continue
        object_type = object_types[0]
        for pattern in re.findall(r"`([^`]+)`", cells[0]):
            if pattern == "status" and object_type != "project":
                continue
            for path in _expand_command_pattern(pattern):
                previous = expected.setdefault(path, object_type)
                if previous != object_type:
                    duplicate_assignments.append(f"{' '.join(path)}: {previous} / {object_type}")

    return expected, duplicate_assignments


def _documented_error_exit_mapping(spec_path: Path) -> dict[str, int]:
    expected: dict[str, int] = {}
    in_table = False

    for line in spec_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("Stable error-code exit mapping"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            if expected:
                break
            continue
        if line.startswith("| ---") or line.startswith("| Error code"):
            continue
        cells = _split_markdown_table_row(line)
        if len(cells) != 2:
            continue
        code_match = re.fullmatch(r"`([^`]+)`", cells[0])
        exit_match = re.search(r"\b([0-5])\b", cells[1])
        if code_match and exit_match:
            expected[code_match.group(1)] = int(exit_match.group(1))

    return expected


def _documented_stable_error_codes(spec_path: Path) -> set[str]:
    codes: set[str] = set()
    in_list = False

    for line in spec_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("Stable error codes"):
            in_list = True
            continue
        if not in_list:
            continue
        if stripped.startswith("Numeric exit codes"):
            break
        if stripped.startswith("- "):
            codes.update(re.findall(r"`([A-Z0-9_]+)`", stripped))

    return codes


def _documented_numeric_exit_codes(spec_path: Path) -> dict[int, str]:
    expected: dict[int, str] = {}
    in_table = False

    for line in spec_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("Numeric exit codes"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            if expected:
                break
            continue
        if line.startswith("| ---") or line.startswith("| Exit code"):
            continue
        cells = _split_markdown_table_row(line)
        if len(cells) < 2:
            continue
        if re.fullmatch(r"[0-5]", cells[0]):
            expected[int(cells[0])] = cells[1].lower()

    return expected


def _documented_warning_codes(spec_path: Path) -> set[str]:
    codes: set[str] = set()
    in_list = False

    for line in spec_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("V1 warning codes"):
            in_list = True
            continue
        if not in_list:
            continue
        if stripped.startswith("Stable error codes") or stripped.startswith("## 5."):
            break
        if stripped.startswith("- "):
            codes.update(re.findall(r"`([A-Z0-9_]+)`", stripped))

    return codes


def _implemented_warning_codes() -> set[str]:
    source_paths = [
        Path(__file__).resolve().parents[1] / "src" / "alab" / name
        for name in ("auth.py", "cli.py", "services.py", "runner.py", "source_import.py")
    ]
    codes: set[str] = set()

    def collect(node: ast.AST) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str) and _WARNING_CODE_RE.fullmatch(child.value):
                if child.value not in ERROR_EXIT_CODES:
                    codes.add(child.value)

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if "warning" in node.name:
                collect(node)
            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            if any(isinstance(target, ast.Name) and target.id in {"warnings", "warning_codes"} for target in node.targets):
                collect(node.value)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if isinstance(node.target, ast.Name) and node.target.id in {"warnings", "warning_codes"} and node.value is not None:
                collect(node.value)
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in {"add", "append", "extend"}
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"warnings", "warning_codes"}
            ):
                for arg in node.args:
                    collect(arg)
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "ResultBlock"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "warning"
            ):
                for arg in node.args[1:]:
                    collect(arg)
            self.generic_visit(node)

    for source_path in source_paths:
        Visitor().visit(ast.parse(source_path.read_text(encoding="utf-8")))
    return codes


def _markdown_command_blocks(spec_path: Path) -> list[tuple[str, set[tuple[str, ...]], str]]:
    lines = spec_path.read_text(encoding="utf-8").splitlines()
    blocks: list[tuple[str, set[tuple[str, ...]], str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        headings = _markdown_command_heading_spans(line)
        if not headings:
            index += 1
            continue
        block_lines = [line]
        index += 1
        while index < len(lines):
            next_line = lines[index]
            if _markdown_command_heading_spans(next_line) or next_line.startswith("### "):
                break
            block_lines.append(next_line)
            index += 1
        registry_paths = set(registry.COMMANDS_BY_PATH)
        block_text = "\n".join(block_lines)
        for heading in headings:
            paths = {path for path in _documented_heading_paths(heading) if path in registry_paths}
            blocks.append((heading, paths, block_text))
    return blocks


def _option_names(text: str) -> set[str]:
    return set(re.findall(r"(?<![A-Za-z0-9_-])--[A-Za-z][A-Za-z0-9-]*", text))


def _documented_option_contract_text(heading: str, block_text: str, grouped: bool) -> str:
    if grouped:
        return heading
    lines = [heading]
    lines.extend(
        line.strip()
        for line in block_text.splitlines()[1:]
        if line.strip().startswith(_COMMAND_OPTION_CONTRACT_PREFIXES)
    )
    return "\n".join(lines)


def _documented_command_options(spec_path: Path) -> dict[tuple[str, ...], set[str]]:
    documented: dict[tuple[str, ...], set[str]] = {}
    for heading, paths, block_text in _markdown_command_blocks(spec_path):
        if not paths:
            continue
        grouped = len(paths) > 1
        option_text = _documented_option_contract_text(heading, block_text, grouped)
        options = _option_names(option_text)
        if "explicit project" in block_text or "explicit project selection" in block_text:
            options.add("--project")
        options -= _GLOBAL_CLI_OPTIONS
        for path in paths:
            documented.setdefault(path, set()).update(options)
    return documented


def _documented_conflict_options(spec_path: Path) -> dict[tuple[str, ...], set[str]]:
    documented: dict[tuple[str, ...], set[str]] = {}
    for _heading, paths, block_text in _markdown_command_blocks(spec_path):
        if not paths:
            continue
        conflict_text = "\n".join(
            line.strip()
            for line in block_text.splitlines()[1:]
            if line.strip().startswith(("- Conflicts:", "- Conflicts：", "- Source conflicts:", "- Source conflicts："))
        )
        options = _option_names(conflict_text) - _GLOBAL_CLI_OPTIONS
        if not options:
            continue
        for path in paths:
            documented.setdefault(path, set()).update(options)
    return documented


def _documented_mixed_remove_mode_conflict_failures(spec_path: Path) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    registry_paths = set(registry.COMMANDS_BY_PATH)
    for heading, paths, block_text in _markdown_command_blocks(spec_path):
        if "--dry-run|--force --confirm" not in heading and "--dry-run|--force --confirm" not in block_text:
            continue
        remove_paths = sorted(path for path in paths if path in registry_paths and path[-1:] == ("remove",))
        if not remove_paths:
            continue
        conflict_lines = [
            line.strip()
            for line in block_text.splitlines()
            if line.strip().startswith(("- Conflicts:", "- Conflicts："))
        ]
        conflict_options = _option_names("\n".join(conflict_lines))
        if not {"--dry-run", "--force", "--confirm"} <= conflict_options:
            failures.append(
                {
                    "heading": heading,
                    "commands": [" ".join(path) for path in remove_paths],
                    "spec": spec_path.name,
                    "conflicts": conflict_lines,
                }
            )
    return failures


def _documented_command_heading_paths(spec_path: Path) -> set[tuple[str, ...]]:
    return {path for _heading, paths, _block_text in _markdown_command_blocks(spec_path) for path in paths}


def _documented_registered_command_mentions(spec_path: Path) -> set[tuple[str, ...]]:
    registry_paths = set(registry.COMMANDS_BY_PATH)
    mentions: set[tuple[str, ...]] = set()
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        for code_span in re.findall(r"`([^`]+)`", line):
            if code_span.startswith("alab "):
                mentions.update(path for path in _documented_heading_paths(code_span) if path in registry_paths)
    return mentions


def _documented_command_surface_paths(spec_path: Path) -> set[tuple[str, ...]]:
    primary_object_paths, _duplicates = _documented_primary_object_types(spec_path)
    return _documented_command_heading_paths(spec_path) | set(primary_object_paths) | _documented_registered_command_mentions(spec_path)


def _known_options_by_function() -> dict[str, set[str]]:
    tree = ast.parse(inspect.getsource(services))
    options_by_function: dict[str, set[str]] = defaultdict(set)

    class Visitor(ast.NodeVisitor):
        current_function = "<module>"

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            previous = self.current_function
            self.current_function = node.name
            self.generic_visit(node)
            self.current_function = previous

        def visit_Call(self, node: ast.Call) -> None:
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "require_known_options"
                and len(node.args) >= 2
            ):
                options_by_function[self.current_function].update(_literal_option_values(node.args[1]))
            self.generic_visit(node)

    Visitor().visit(tree)
    return options_by_function


def _declared_options_for_spec(spec: registry.CommandSpec) -> set[str]:
    options_by_function = _known_options_by_function()
    handler_name = spec.handler.__name__
    declared = set(options_by_function.get(handler_name, set()))
    called = _called_names(spec.handler)
    for helper_name in _GUARDED_HELPERS:
        if helper_name in called:
            declared.update(options_by_function.get(helper_name, set()))
    return declared


def _documented_success_fields(command: str, *, spec_path: Path = _SPEC_CLI_PATH) -> list[str]:
    target = tuple(command.split())
    in_section = False
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        heading_spans = _markdown_command_heading_spans(line)
        if heading_spans:
            in_section = any(target in _documented_heading_paths(code_span) for code_span in heading_spans)
            continue
        if in_section and line.startswith("### "):
            break
        if in_section and line.startswith("- Success and exit follow "):
            referenced = line.removeprefix("- Success and exit follow ").removesuffix(".")
            if referenced == "config import":
                return _documented_success_fields("project config import", spec_path=spec_path)
        if in_section and line.startswith("- Success fields"):
            _prefix, _separator, field_text = line.partition(":")
            if not _separator:
                _prefix, _separator, field_text = line.partition("：")
            selector_match = re.search(r" for `([^`]+)`", _prefix)
            if selector_match and target[-1] not in selector_match.group(1).split("|"):
                continue
            fields = re.findall(r"`([^`]+)`", field_text or line)
            if not fields:
                break
            return fields
    raise AssertionError(f"missing documented success fields for {command}")


def _documented_success_fields_for_object(command: str, object_type: str, *, spec_path: Path = _SPEC_CLI_PATH) -> list[str]:
    target = tuple(command.split())
    object_marker = f"object `{object_type}`"
    per_object_marker = f"per `{object_type}`"
    in_section = False
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        heading_spans = _markdown_command_heading_spans(line)
        if heading_spans:
            in_section = any(target in _documented_heading_paths(code_span) for code_span in heading_spans)
            continue
        if in_section and line.startswith("### "):
            break
        if in_section and line.startswith("- Success fields"):
            prefix, _separator, field_text = line.partition(":")
            if not _separator:
                prefix, _separator, field_text = line.partition("：")
            if object_marker not in prefix and per_object_marker not in prefix:
                continue
            fields = re.findall(r"`([^`]+)`", field_text)
            if not fields:
                break
            return fields
    raise AssertionError(f"missing documented {object_type} success fields for {command}")


def _documented_success_fields_for_scope(command: str, scope: str, *, spec_path: Path = _SPEC_CLI_PATH) -> list[str]:
    target = tuple(command.split())
    in_section = False
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        heading_spans = _markdown_command_heading_spans(line)
        if heading_spans:
            in_section = any(target in _documented_heading_paths(code_span) for code_span in heading_spans)
            continue
        if in_section and line.startswith("### "):
            break
        if in_section and line.startswith("- Success fields"):
            prefix, _separator, field_text = line.partition(":")
            if not _separator:
                prefix, _separator, field_text = line.partition("：")
            scope_match = re.search(r"scope `([^`]+)`", prefix)
            if not scope_match or scope not in scope_match.group(1).split("|"):
                continue
            fields = re.findall(r"`([^`]+)`", field_text)
            if not fields:
                break
            return fields
    raise AssertionError(f"missing documented {scope} success fields for {command}")


def _documented_success_labels(command: str, *, omit: set[str] | None = None) -> list[str]:
    omitted = omit or set()
    return ["object", *[field for field in _documented_success_fields(command) if field not in omitted]]


def _documented_success_labels_for_object(command: str, object_type: str) -> list[str]:
    return ["object", *_documented_success_fields_for_object(command, object_type)]


def _documented_success_labels_for_scope(command: str, scope: str) -> list[str]:
    return ["object", *_documented_success_fields_for_scope(command, scope)]


def _documented_success_labels_with_repeats(
    command: str,
    *,
    repeats: dict[str, int],
    omit: set[str] | None = None,
) -> list[str]:
    omitted = omit or set()
    labels = ["object"]
    for field in _documented_success_fields(command):
        if field in omitted:
            continue
        labels.extend([field] * repeats.get(field, 1))
    return labels


def _success_field_contracts_for_command(
    command: str,
    *,
    spec_path: Path,
) -> list[tuple[str, str, tuple[str, ...]]]:
    contracts: list[tuple[str, str, tuple[str, ...]]] = []
    command_variants = _SUCCESS_FIELD_COMMAND_VARIANTS.get(command, (command,))
    for variant in command_variants:
        try:
            contracts.append(("command", variant, tuple(_documented_success_fields(variant, spec_path=spec_path))))
        except AssertionError:
            pass

    for object_type in _SUCCESS_FIELD_OBJECT_CONTRACTS.get(command, ()):
        try:
            contracts.append(
                (
                    "object",
                    object_type,
                    tuple(_documented_success_fields_for_object(command, object_type, spec_path=spec_path)),
                )
            )
        except AssertionError:
            pass

    for scope in _SUCCESS_FIELD_SCOPE_CONTRACTS.get(command, ()):
        try:
            contracts.append(("scope", scope, tuple(_documented_success_fields_for_scope(command, scope, spec_path=spec_path))))
        except AssertionError:
            pass

    return contracts


def _success_field_contracts_for_spec(
    spec: registry.CommandSpec,
    *,
    spec_path: Path,
) -> list[tuple[str, str, tuple[str, ...]]]:
    command = " ".join(spec.path)
    contracts = _success_field_contracts_for_command(command, spec_path=spec_path)
    if contracts:
        return contracts

    for candidate in registry.COMMANDS:
        if candidate is spec or candidate.handler is not spec.handler:
            continue
        alias_contracts = _success_field_contracts_for_command(" ".join(candidate.path), spec_path=spec_path)
        if alias_contracts:
            return [("alias", f"{' '.join(candidate.path)}:{kind}:{selector}", fields) for kind, selector, fields in alias_contracts]

    return []


def _output_blocks(output: str) -> list[str]:
    return [block for block in output.strip().split("\n\n") if block]


def _output_object_type(output: str) -> str | None:
    blocks = _output_blocks(output)
    if not blocks:
        return None
    return _output_field_map(blocks[0]).get("object")


def _known_option_calls() -> tuple[list[tuple[str, int, list[str]]], list[str]]:
    tree = ast.parse(inspect.getsource(services))
    calls: list[tuple[str, int, list[str]]] = []
    non_literal: list[str] = []

    class Visitor(ast.NodeVisitor):
        current_function = "<module>"

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            previous = self.current_function
            self.current_function = node.name
            self.generic_visit(node)
            self.current_function = previous

        def visit_Call(self, node: ast.Call) -> None:
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "require_known_options"
                and len(node.args) >= 2
            ):
                option_arg = node.args[1]
                if isinstance(option_arg, ast.Tuple) and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in option_arg.elts):
                    calls.append((self.current_function, node.lineno, [item.value for item in option_arg.elts]))
                else:
                    non_literal.append(f"{self.current_function}:{node.lineno}")
            self.generic_visit(node)

    Visitor().visit(tree)
    return calls, non_literal


def _known_option_declarations_and_usage() -> list[tuple[str, list[str], list[str]]]:
    tree = ast.parse(inspect.getsource(services))
    rows: list[tuple[str, list[str], list[str]]] = []

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        declared: set[str] = set()
        used: set[str] = set()
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            function_name = child.func.id if isinstance(child.func, ast.Name) else ""
            if function_name == "require_known_options" and len(child.args) >= 2:
                declared.update(_literal_option_values(child.args[1]))
            if (
                function_name in {"command_arg", "command_args", "flag", "option_count"}
                and len(child.args) >= 2
                and isinstance(child.args[1], ast.Constant)
                and isinstance(child.args[1].value, str)
                and child.args[1].value.startswith("--")
            ):
                used.add(child.args[1].value)
            if function_name in _VALUE_OPTION_READ_HELPER_ARG_INDEXES:
                option_arg_index = _VALUE_OPTION_READ_HELPER_ARG_INDEXES[function_name]
                if len(child.args) > option_arg_index:
                    option = _constant_option_arg(child.args[option_arg_index])
                    if option:
                        used.add(option)
            if function_name == "require_options_at_most_once" and len(child.args) >= 2:
                used.update(_literal_option_values(child.args[1]))
            if function_name in _HELPER_OPTION_USAGE:
                used.update(_HELPER_OPTION_USAGE[function_name])
            for keyword in child.keywords:
                if keyword.arg == "options_with_values":
                    used.update(_literal_option_values(keyword.value))
        if declared:
            rows.append((node.name, sorted(declared), sorted(used)))

    return rows


def _literal_value_option_reads() -> list[tuple[str, int, str, str]]:
    tree = ast.parse(inspect.getsource(services))
    rows: list[tuple[str, int, str, str]] = []

    class Visitor(ast.NodeVisitor):
        current_function = "<module>"

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            previous = self.current_function
            self.current_function = node.name
            self.generic_visit(node)
            self.current_function = previous

        def visit_Call(self, node: ast.Call) -> None:
            function_name = node.func.id if isinstance(node.func, ast.Name) else ""
            if function_name in {"command_arg", "command_args"} and len(node.args) >= 2:
                option = _constant_option_arg(node.args[1])
                if option:
                    rows.append((self.current_function, node.lineno, function_name, option))
            if function_name in _VALUE_OPTION_READ_HELPER_ARG_INDEXES:
                option_arg_index = _VALUE_OPTION_READ_HELPER_ARG_INDEXES[function_name]
                if len(node.args) > option_arg_index:
                    option = _constant_option_arg(node.args[option_arg_index])
                    if option:
                        rows.append((self.current_function, node.lineno, function_name, option))
            self.generic_visit(node)

    Visitor().visit(tree)
    return rows


def _constant_option_arg(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("--"):
        return node.value
    return None


def _singleton_option_declarations_and_guards() -> list[tuple[str, list[str], list[str], list[str]]]:
    tree = ast.parse(inspect.getsource(services))
    rows: list[tuple[str, list[str], list[str], list[str]]] = []

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        declared: set[str] = set()
        guarded: set[str] = set()
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            function_name = child.func.id if isinstance(child.func, ast.Name) else ""
            if function_name == "require_known_options" and len(child.args) >= 2:
                declared.update(_literal_option_values(child.args[1]))
            if function_name == "require_options_at_most_once" and len(child.args) >= 2:
                guarded.update(_literal_option_values(child.args[1]))
            if function_name == "require_exactly_one_option_pair" and len(child.args) >= 3:
                first = _constant_option_arg(child.args[1])
                second = _constant_option_arg(child.args[2])
                if first and second:
                    guarded.update((first, second))
            if function_name in _HELPER_AT_MOST_ONCE_OPTIONS:
                guarded.update(_HELPER_AT_MOST_ONCE_OPTIONS[function_name])
            if function_name in _DYNAMIC_SINGLETON_OPTION_HELPERS and len(child.args) >= 2:
                option = _constant_option_arg(child.args[1])
                if option:
                    guarded.add(option)
        if declared:
            rows.append((node.name, sorted(declared), sorted(guarded), sorted(declared & _REPEATABLE_COMMAND_OPTIONS)))

    return rows


def _zero_positional_message(handler: object) -> str | None:
    tree = ast.parse(inspect.getsource(handler))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = node.func.id if isinstance(node.func, ast.Name) else ""
        if function_name != "require_positional_count" or len(node.args) < 3:
            continue
        count_arg = node.args[1]
        message_arg = node.args[2]
        if (
            isinstance(count_arg, ast.Constant)
            and count_arg.value == 0
            and isinstance(message_arg, ast.Constant)
            and isinstance(message_arg.value, str)
        ):
            return message_arg.value
    return None


def _optional_positional_message(handler: object) -> str | None:
    tree = ast.parse(inspect.getsource(handler))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = node.func.id if isinstance(node.func, ast.Name) else ""
        if function_name != "optional_positional_selector" or len(node.args) < 2:
            continue
        message_arg = node.args[1]
        if isinstance(message_arg, ast.Constant) and isinstance(message_arg.value, str):
            return message_arg.value
    return None


def _single_selector_message_for_spec(spec: registry.CommandSpec) -> str | None:
    direct = _optional_positional_message(spec.handler)
    if direct is not None:
        return direct
    calls = _called_names(spec.handler)
    if "_archive_observe_record" in calls:
        return f"{spec.object_type} archive accepts exactly one object id"
    if "_unarchive_observe_record" in calls:
        return f"{spec.object_type} unarchive accepts exactly one object id"
    if "_remove_observe_record" in calls:
        return f"{spec.object_type} remove accepts exactly one object id"
    if "_set_annotation_status" in calls:
        return "annotation status accepts exactly one annotation id"
    return None


def _fixed_positional_message(handler: object) -> str | None:
    tree = ast.parse(inspect.getsource(handler))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = node.func.id if isinstance(node.func, ast.Name) else ""
        if function_name != "require_positional_count" or len(node.args) < 3:
            continue
        count_arg = node.args[1]
        message_arg = node.args[2]
        if (
            isinstance(count_arg, ast.Constant)
            and isinstance(count_arg.value, int)
            and count_arg.value > 0
            and isinstance(message_arg, ast.Constant)
            and isinstance(message_arg.value, str)
        ):
            return message_arg.value
    return None


def _handler_known_options(handler: object) -> set[str]:
    tree = ast.parse(inspect.getsource(handler))
    options: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = node.func.id if isinstance(node.func, ast.Name) else ""
        if function_name == "require_known_options" and len(node.args) >= 2:
            options.update(_literal_option_values(node.args[1]))
        if function_name in _HELPER_KNOWN_OPTIONS:
            options.update(_HELPER_KNOWN_OPTIONS[function_name])
    return options


def _handler_flag_options(handler: object) -> set[str]:
    tree = ast.parse(inspect.getsource(handler))
    options: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = node.func.id if isinstance(node.func, ast.Name) else ""
        if function_name == "flag" and len(node.args) >= 2:
            option = _constant_option_arg(node.args[1])
            if option:
                options.add(option)
    return options


def _command_local_value_options(spec: registry.CommandSpec) -> list[str]:
    value_options = (_handler_known_options(spec.handler) & services.OPTIONS_WITH_VALUES) - _GLOBAL_CLI_OPTIONS
    return sorted(value_options - _handler_flag_options(spec.handler))


def _typed_value_case_items(options: dict[str, object]) -> set[tuple[str, str, str]]:
    cases: set[tuple[str, str, str]] = set()
    for option, invalid in options.items():
        if isinstance(invalid, tuple):
            invalid_cases = [invalid]
        else:
            invalid_cases = list(invalid)
        for value, reason in invalid_cases:
            cases.add((option, value, reason))
    return cases


def _typed_value_invalid_options(spec: registry.CommandSpec) -> list[tuple[str, str, str]]:
    tree = ast.parse(inspect.getsource(spec.handler))
    cases: set[tuple[str, str, str]] = _typed_value_case_items(_HANDLER_TYPED_VALUE_INVALID_OPTIONS.get(spec.handler.__name__, {}))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = node.func.id if isinstance(node.func, ast.Name) else ""
        if function_name == "_append_time_filter" and len(node.args) >= 4:
            option = _constant_option_arg(node.args[3])
            if option:
                value, reason = _RFC3339_INVALID_TIME_OPTIONS[option]
                cases.add((option, value, reason))
        if function_name in _DIRECT_TYPED_VALUE_PARSERS and len(node.args) >= 2:
            option = _constant_option_arg(node.args[1])
            if option:
                for value, reason_template in _DIRECT_TYPED_VALUE_PARSERS[function_name]:
                    cases.add((option, value, reason_template.format(option=option)))
        if function_name == "_require_option_choice" and len(node.args) >= 3:
            option = _constant_option_arg(node.args[1])
            choices = _literal_string_values(node.args[2])
            if option and choices:
                cases.add((option, "not-a-choice", f"{option} must be one of {', '.join(sorted(choices))}"))
        if function_name == "_complete_id_option" and len(node.args) >= 3:
            option = _constant_option_arg(node.args[1])
            prefix_arg = node.args[2]
            prefix = prefix_arg.value if isinstance(prefix_arg, ast.Constant) and isinstance(prefix_arg.value, str) else None
            if option and prefix:
                cases.add((option, f"{prefix}-short", "object ids must be complete"))
        if function_name == "_sort_rows":
            subject = next(
                (keyword.value.value for keyword in node.keywords if keyword.arg == "subject" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str)),
                None,
            )
            if subject:
                cases.add(("--sort", "unsupported:desc", f"--sort field is not supported for {subject}"))
        if function_name == "_sql_order_limit_clause":
            subject = next(
                (keyword.value.value for keyword in node.keywords if keyword.arg == "subject" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str)),
                None,
            )
            if subject:
                cases.add(("--sort", "unsupported:desc", f"--sort field is not supported for {subject}"))
        if function_name in _TYPED_VALUE_HELPER_INVALID_OPTIONS:
            cases.update(_typed_value_case_items(_TYPED_VALUE_HELPER_INVALID_OPTIONS[function_name]))

    value_options = set(_command_local_value_options(spec))
    return sorted(case for case in cases if case[0] in value_options)


def _command_local_singleton_options(spec: registry.CommandSpec) -> list[str]:
    return sorted(_handler_known_options(spec.handler) - _REPEATABLE_COMMAND_OPTIONS)


def _init_capability_project(tmp_path: Path, capsys) -> tuple[Path, str, str, str]:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    source.mkdir()
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Capability Contract Project"
task = "Exercise capability contract surfaces"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
            ]
        )
        == 0
    )
    project_fields = _output_field_map(capsys.readouterr().out)
    return home, root_key, project_fields["project id"], project_fields["admin key"]


def _init_run_result_failure_project(
    tmp_path: Path,
    capsys,
    *,
    name: str,
    source_files: dict[str, str],
    runner_command: list[str],
    working_directory: str = ".",
    timeout_seconds: int = 30,
) -> tuple[Path, str, str, Path]:
    home = tmp_path / f"home-{name}"
    source = tmp_path / f"source-{name}"
    config = tmp_path / f"alab.{name}.toml"
    worktree_path = tmp_path / f"worktree-{name}"
    source.mkdir()
    for relative_path, content in source_files.items():
        path = source / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Run Result Failure {name}"
task = "Exercise saved run result failures"

[runner]
type = "local"
timeout_seconds = {timeout_seconds}
working_directory = {json.dumps(working_directory)}
command = {json.dumps(runner_command)}

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
            ]
        )
        == 0
    )
    project_fields = _output_field_map(capsys.readouterr().out)
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                project_fields["admin key"],
                "exp",
                "create",
                "--project",
                project_fields["project id"],
                "--name",
                f"Result Failure {name}",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    return home, project_fields["admin key"], project_fields["project id"], worktree_path


def _init_validation_result_failure_project(
    tmp_path: Path,
    capsys,
    *,
    name: str,
    config_mutations: list[tuple[str, str]],
) -> tuple[Path, str, str]:
    home = tmp_path / f"home-validation-{name}"
    source = tmp_path / f"source-validation-{name}"
    config = tmp_path / f"alab.validation.{name}.toml"
    source.mkdir()
    (source / "main.py").write_text("print('baseline')\n", encoding="utf-8")
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Validation Result Failure {name}"
task = "Exercise saved validation result failures"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
            ]
        )
        == 0
    )
    project_fields = _output_field_map(capsys.readouterr().out)
    for field, value in config_mutations:
        assert (
            cli.run(
                [
                    "--home",
                    str(home),
                    "--key",
                    project_fields["admin key"],
                    "project",
                    "config",
                    "set",
                    field,
                    value,
                    "--project",
                    project_fields["project id"],
                    "--skip-baseline-test",
                ]
            )
            == 0
        )
        mutation_fields = _output_field_map(capsys.readouterr().out)
        assert mutation_fields["validation status"] == "skipped"
        assert mutation_fields["project status"] == "invalid"
    return home, project_fields["admin key"], project_fields["project id"]


def _baseline_result_failure_cases() -> list[dict[str, object]]:
    return [
        {
            "name": "failed",
            "runner": {
                "command": [sys.executable, "-c", "import sys; sys.exit(7)"],
                "working_directory": ".",
                "timeout_seconds": 30,
            },
            "validation status": "failed",
            "runner exit code": 7,
            "reward parse status": "parsed",
            "failure": "runner exited with code 7",
        },
        {
            "name": "timeout",
            "runner": {
                "command": [sys.executable, "-c", "import time; time.sleep(5)"],
                "working_directory": ".",
                "timeout_seconds": 1,
            },
            "validation status": "timeout",
            "runner exit code": None,
            "reward parse status": "not_attempted",
            "failure": "runner timed out",
        },
        {
            "name": "error",
            "runner": {
                "command": [sys.executable, "main.py"],
                "working_directory": "missing",
                "timeout_seconds": 30,
            },
            "validation status": "error",
            "runner exit code": None,
            "reward parse status": "not_attempted",
            "failure": "runner working directory does not exist",
        },
    ]


def test_saved_result_failure_tails_have_stable_cli_shape() -> None:
    def summary(
        *,
        status: str,
        exit_code: int | None,
        reward_parse_status: str,
        failure_reason: str | None = None,
    ) -> services.RunExecutionSummary:
        return services.RunExecutionSummary(
            run_id="run-tail",
            commit="a" * 40,
            created_commit=False,
            status=status,
            reward=None,
            reward_parse_status=reward_parse_status,
            exit_code=exit_code,
            stdout_preview="",
            stderr_preview="",
            artifact_count=0,
            failure_reason=failure_reason,
            warning_codes=[],
        )

    next_action = "fix and retry"
    expected_baseline_tails = {
        "passed": [],
        "skipped": [],
        "inherited": [],
        "dry-run": [],
        "failed": [
            ("error code", "BASELINE_VALIDATION_FAILED"),
            ("exit code", 1),
            ("reason", "baseline validation status is failed"),
            ("next", next_action),
        ],
        "timeout": [
            ("error code", "BASELINE_VALIDATION_FAILED"),
            ("exit code", 1),
            ("reason", "baseline validation status is timeout"),
            ("next", next_action),
        ],
        "error": [
            ("error code", "BASELINE_VALIDATION_FAILED"),
            ("exit code", 1),
            ("reason", "baseline validation status is error"),
            ("next", next_action),
        ],
    }
    observed_baseline_tails = {
        status: services._baseline_failure_fields(status, next_action)
        for status in expected_baseline_tails
    }

    run_cases = {
        "passed": (summary(status="passed", exit_code=0, reward_parse_status="parsed"), []),
        "failed": (
            summary(status="failed", exit_code=7, reward_parse_status="parsed"),
            [
                ("error code", "RUNNER_FAILED"),
                ("exit code", 1),
                ("reason", "runner exited with code 7"),
                ("next", next_action),
            ],
        ),
        "timeout": (
            summary(status="timeout", exit_code=None, reward_parse_status="not_attempted"),
            [
                ("error code", "RUNNER_TIMEOUT"),
                ("exit code", 1),
                ("reason", "runner timed out"),
                ("next", next_action),
            ],
        ),
        "runner-error": (
            summary(status="error", exit_code=None, reward_parse_status="not_attempted"),
            [
                ("error code", "RUNNER_ERROR"),
                ("exit code", 1),
                ("reason", "runner recorded an error"),
                ("next", next_action),
            ],
        ),
        "reward-missing": (
            summary(status="error", exit_code=0, reward_parse_status="missing"),
            [
                ("error code", "REWARD_PARSE_ERROR"),
                ("exit code", 1),
                ("reason", "reward parse status is missing"),
                ("next", next_action),
            ],
        ),
        "reward-invalid": (
            summary(status="error", exit_code=0, reward_parse_status="invalid"),
            [
                ("error code", "REWARD_PARSE_ERROR"),
                ("exit code", 1),
                ("reason", "reward parse status is invalid"),
                ("next", next_action),
            ],
        ),
        "reward-error": (
            summary(status="error", exit_code=0, reward_parse_status="error"),
            [
                ("error code", "REWARD_PARSE_ERROR"),
                ("exit code", 1),
                ("reason", "reward parse status is error"),
                ("next", next_action),
            ],
        ),
        "explicit-failure-reason": (
            summary(status="error", exit_code=125, reward_parse_status="parsed", failure_reason="docker run failed"),
            [
                ("error code", "RUNNER_ERROR"),
                ("exit code", 1),
                ("reason", "docker run failed"),
                ("next", next_action),
            ],
        ),
    }
    observed_run_tails = {
        name: services._run_failure_fields(run_summary, next_action)
        for name, (run_summary, _expected) in run_cases.items()
    }
    expected_run_tails = {name: expected for name, (_run_summary, expected) in run_cases.items()}

    submission_block = services._submission_failure_block(
        "exp-tail",
        ["none"],
        "RUNNER_ERROR",
        "final run failed",
        next_action,
    )
    submission_fields = dict(submission_block.fields)

    assert {
        "baseline tails": observed_baseline_tails,
        "run tails": observed_run_tails,
        "tail extractor": services._result_failure_tail([("run id", "run-tail"), *expected_run_tails["reward-error"]]),
        "submission object": submission_block.object_type,
        "submission labels": _field_labels(submission_block),
        "submission tail": {label: submission_fields[label] for label in ("error code", "exit code", "reason", "next")},
        "error exits": {
            code: error_exit_code(code)
            for code in {
                "BASELINE_VALIDATION_FAILED",
                "RUNNER_FAILED",
                "RUNNER_TIMEOUT",
                "RUNNER_ERROR",
                "REWARD_PARSE_ERROR",
            }
        },
    } == {
        "baseline tails": expected_baseline_tails,
        "run tails": expected_run_tails,
        "tail extractor": expected_run_tails["reward-error"],
        "submission object": "submission",
        "submission labels": [
            "object",
            "exp id",
            "submit accepted",
            "final run id",
            "final commit",
            "experiment status",
            "summary stored",
            "feedback stored",
            "ref",
            "error code",
            "exit code",
            "reason",
            "next",
        ],
        "submission tail": {
            "error code": "RUNNER_ERROR",
            "exit code": 1,
            "reason": "final run failed",
            "next": next_action,
        },
        "error exits": {
            "BASELINE_VALIDATION_FAILED": 1,
            "RUNNER_FAILED": 1,
            "RUNNER_TIMEOUT": 1,
            "RUNNER_ERROR": 1,
            "REWARD_PARSE_ERROR": 1,
        },
    }


def _write_local_project_config(
    path: Path,
    *,
    name: str,
    runner_command: list[str],
    working_directory: str = ".",
    timeout_seconds: int = 30,
) -> None:
    path.write_text(
        f"""
schema_version = 1

[project]
name = {json.dumps(name)}
task = "Exercise baseline result failures"

[runner]
type = "local"
timeout_seconds = {timeout_seconds}
working_directory = {json.dumps(working_directory)}
command = {json.dumps(runner_command)}

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _database_table_counts(home: Path) -> dict[str, int]:
    with sqlite3.connect(home / "alab.db") as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}


def _database_snapshot(home: Path) -> dict[str, list[tuple[object, ...]]]:
    with sqlite3.connect(home / "alab.db") as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        return {table: sorted(conn.execute(f"SELECT * FROM {table}").fetchall(), key=repr) for table in tables}


def _relative_tree(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def _tree_snapshot(root: Path) -> tuple[bool, list[str]]:
    return root.exists(), _relative_tree(root)


def _text_file_snapshot(paths: list[Path]) -> dict[Path, str | None]:
    return {path: path.read_text(encoding="utf-8") if path.exists() else None for path in paths}


def _unknown_option_invocation(
    spec: registry.CommandSpec,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
) -> tuple[list[str], Path | None]:
    args = ["--home", str(home)]
    cwd: Path | None = None
    if spec.credential == "root":
        args.extend(["--key", root_key])
    elif spec.credential in {"admin", "public_or_admin", "token_or_admin"}:
        args.extend(["--key", admin_key])
    elif spec.credential == "token":
        cwd = exp_path

    command_args = [*spec.path]
    if spec.credential in {"admin", "public_or_admin", "token_or_admin"} or spec.path == ("status",):
        command_args.extend(["--project", project_id])
    command_args.append("--definitely-unsupported")
    return [*args, *command_args], cwd


def _trailing_global_unknown_option_invocation(
    spec: registry.CommandSpec,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _unknown_option_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
    )
    trailing_globals: list[str] = []
    command_args: list[str] = []
    idx = 0
    while idx < len(args):
        item = args[idx]
        if item in {"--home", "--key"}:
            trailing_globals.extend(args[idx : idx + 2])
            idx += 2
            continue
        command_args.append(item)
        idx += 1
    return [*command_args, *trailing_globals, "--output", "text"], cwd


def _sentinel_extra_positional_invocation(
    spec: registry.CommandSpec,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    project_marker_path: Path,
    project_config_path: Path,
    catalog_upstream: Path,
    export_path: Path,
    extra_worktree_path: Path,
    source_path: Path,
    secret_file_path: Path,
    ignored_home: Path,
) -> tuple[list[str], Path | None]:
    sentinel_globals = ["--", "--home", str(ignored_home), "--output", "json", "--key-stdin"]
    if _zero_positional_message(spec.handler) is not None:
        args, cwd = _extra_positional_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
            project_marker_path=project_marker_path,
            project_config_path=project_config_path,
            catalog_upstream=catalog_upstream,
            export_path=export_path,
            extra_worktree_path=extra_worktree_path,
        )
        return [*args[:-1], *sentinel_globals, args[-1]], cwd
    if _single_selector_message_for_spec(spec) is not None:
        args, cwd = _single_selector_extra_positional_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
        )
        return [*args[:-2], *sentinel_globals, *args[-2:]], cwd
    if _fixed_positional_message(spec.handler) is not None:
        args, cwd = _fixed_positional_base_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
            project_config_path=project_config_path,
            source_path=source_path,
            secret_file_path=secret_file_path,
        )
        return [*args, *sentinel_globals, "unexpected-positional"], cwd
    raise AssertionError(f"missing positional validator for {' '.join(spec.path)}")


def _extra_positional_invocation(
    spec: registry.CommandSpec,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    project_marker_path: Path,
    project_config_path: Path,
    catalog_upstream: Path,
    export_path: Path,
    extra_worktree_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _unknown_option_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
    )
    args = args[:-1]
    extras: dict[tuple[str, ...], list[str]] = {
        ("context", "repair"): ["--path", str(project_marker_path.parent)],
        ("project", "config", "export"): ["--out", str(export_path)],
        ("project", "config", "import"): ["--config", str(project_config_path)],
        ("source", "import"): ["--source-empty"],
        ("exp", "create"): ["--name", "Extra Positional Matrix", "--path", str(extra_worktree_path)],
        ("exp", "search"): ["--query", "matrix"],
        ("observe", "experiments", "search"): ["--query", "matrix"],
        ("exp", "checkout", "remove"): ["--token-id", "cred-token-AAAAAAAAAAAAAAAAAAAAAA"],
        ("run",): ["--message", "extra positional matrix"],
        (
            "submit",
        ): ["--message", "extra positional matrix", "--summary", "summary", "--feedback", "feedback", "--ref", "none"],
        ("backup", "prune"): ["--keep", "0"],
        ("cache", "prune"): ["--all"],
        ("catalog", "skydiscover", "add"): ["--origin-url", str(catalog_upstream), "--ref", "main"],
        ("catalog", "skydiscover", "update"): ["--origin-url", str(catalog_upstream), "--ref", "main"],
        ("catalog", "skydiscover", "remove"): ["--force", "--confirm", "skydiscover"],
    }
    return [*args, *extras.get(spec.path, []), "unexpected-positional"], cwd


def _single_selector_extra_positional_invocation(
    spec: registry.CommandSpec,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _unknown_option_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
    )
    return [*args[:-1], "unexpected-selector-one", "unexpected-selector-two"], cwd


def _missing_single_selector_error_for_spec(spec: registry.CommandSpec) -> tuple[str, str] | None:
    if _single_selector_message_for_spec(spec) is None:
        return None
    optional_context_selectors = {
        ("config", "reset"),
        ("exp", "tag", "list"),
    }
    if spec.path in optional_context_selectors:
        return None
    if spec.path == ("key", "revoke"):
        return "CREDENTIAL_NOT_FOUND", "key id is required"
    if spec.path == ("audit", "show"):
        return "AUDIT_NOT_FOUND", "audit id is required"
    if spec.path[:2] == ("project", "validation"):
        return "VALIDATION_NOT_FOUND", "validation id is required"
    if spec.path and spec.path[0] == "source":
        return "SOURCE_NOT_FOUND", "source id is required"
    if spec.path and spec.path[0] == "exp":
        return "EXPERIMENT_NOT_FOUND", "experiment id is required"
    if len(spec.path) >= 2 and spec.path[:2] == ("observe", "experiments"):
        return "EXPERIMENT_NOT_FOUND", "experiment id is required"
    if spec.path and spec.path[0] == "runs":
        return "RUN_NOT_FOUND", "object id is required" if spec.path[-1] in {"archive", "unarchive", "remove"} else "run id is required"
    if len(spec.path) >= 2 and spec.path[:2] == ("observe", "runs"):
        return "RUN_NOT_FOUND", "object id is required" if spec.path[-1] in {"archive", "unarchive", "remove"} else "run id is required"
    if spec.path and spec.path[0] == "artifacts":
        return "ARTIFACT_NOT_FOUND", "object id is required" if spec.path[-1] in {"archive", "unarchive", "remove"} else "artifact id is required"
    if len(spec.path) >= 2 and spec.path[:2] == ("observe", "artifacts"):
        return "ARTIFACT_NOT_FOUND", "object id is required" if spec.path[-1] in {"archive", "unarchive", "remove"} else "artifact id is required"
    if spec.path and spec.path[0] == "logs":
        return "LOG_NOT_FOUND", "object id is required" if spec.path[-1] in {"archive", "unarchive", "remove"} else "log id is required"
    if len(spec.path) >= 2 and spec.path[:2] == ("observe", "logs"):
        return "LOG_NOT_FOUND", "object id is required" if spec.path[-1] in {"archive", "unarchive", "remove"} else "log id is required"
    if spec.object_type == "annotation":
        return "ANNOTATION_NOT_FOUND", "annotation id is required"
    raise AssertionError(f"missing single-selector error mapping for {' '.join(spec.path)}")


def _single_selector_missing_positional_invocation(
    spec: registry.CommandSpec,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    export_path: Path,
    extra_checkout_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _unknown_option_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
    )
    args = args[:-1]
    extras: dict[tuple[str, ...], list[str]] = {
        ("exp", "checkout"): ["--path", str(extra_checkout_path)],
        ("exp", "worktree", "restore"): ["--path", str(extra_checkout_path)],
        ("observe", "artifacts", "export"): ["--out", str(export_path)],
        ("artifacts", "export"): ["--out", str(export_path)],
        ("observe", "logs", "export"): ["--out", str(export_path)],
        ("logs", "export"): ["--out", str(export_path)],
        ("annotate", "edit"): ["--body", "missing selector edit"],
    }
    return [*args, *extras.get(spec.path, [])], cwd


def _fixed_positional_extra_positional_invocation(
    spec: registry.CommandSpec,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    project_config_path: Path,
    source_path: Path,
    secret_file_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _unknown_option_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
    )
    args = args[:-1]
    extras: dict[tuple[str, ...], list[str]] = {
        ("config", "set"): ["output.preview_bytes", "2048", "unexpected-positional"],
        ("project", "init"): [
            "local",
            "unexpected-positional",
            "--config",
            str(project_config_path),
            "--source-path",
            str(source_path),
        ],
        ("project", "config", "set"): ["project.goal", '"unchanged"', "unexpected-positional"],
        ("project", "env", "set"): ["ALAB_FIXED_POSITIONAL", "value", "unexpected-positional"],
        ("project", "env", "unset"): ["ALAB_FIXED_POSITIONAL", "unexpected-positional"],
        ("project", "secret", "set"): ["ALAB_FIXED_SECRET", "unexpected-positional", "--value-file", str(secret_file_path)],
        ("project", "secret", "unset"): ["ALAB_FIXED_SECRET", "unexpected-positional"],
        ("exp", "tag", "add"): ["unexpected-exp", "tag", "unexpected-positional"],
        ("exp", "tag", "remove"): ["unexpected-exp", "tag", "unexpected-positional"],
    }
    return [*args, *extras[spec.path]], cwd


def _fixed_positional_base_invocation(
    spec: registry.CommandSpec,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    project_config_path: Path,
    source_path: Path,
    secret_file_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _unknown_option_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
    )
    args = args[:-1]
    extras: dict[tuple[str, ...], list[str]] = {
        ("config", "set"): ["output.preview_bytes", "2048"],
        ("project", "init"): ["local", "--config", str(project_config_path), "--source-path", str(source_path)],
        ("project", "config", "set"): ["project.goal", '"unchanged"'],
        ("project", "env", "set"): ["ALAB_VALUE_OPTION", "value"],
        ("project", "env", "unset"): ["ALAB_VALUE_OPTION"],
        ("project", "secret", "set"): ["ALAB_VALUE_OPTION_SECRET", "--value-file", str(secret_file_path)],
        ("project", "secret", "unset"): ["ALAB_VALUE_OPTION_SECRET"],
        ("exp", "tag", "add"): ["unexpected-exp", "tag"],
        ("exp", "tag", "remove"): ["unexpected-exp", "tag"],
    }
    return [*args, *extras[spec.path]], cwd


def _fixed_positional_missing_positional_invocation(
    spec: registry.CommandSpec,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    project_config_path: Path,
    source_path: Path,
    secret_file_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _unknown_option_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
    )
    args = args[:-1]
    extras: dict[tuple[str, ...], list[str]] = {
        ("project", "init"): ["--config", str(project_config_path), "--source-path", str(source_path)],
        ("project", "secret", "set"): ["--value-file", str(secret_file_path)],
    }
    return [*args, *extras.get(spec.path, [])], cwd


def _remove_command_option(args: list[str], option: str) -> list[str]:
    cleaned: list[str] = []
    idx = 0
    while idx < len(args):
        item = args[idx]
        if item == option:
            idx += 1
            if idx < len(args) and not args[idx].startswith("--"):
                idx += 1
            continue
        cleaned.append(item)
        idx += 1
    return cleaned


def _prepare_missing_value_args(args: list[str], option: str) -> list[str]:
    cleaned = _remove_command_option(args, option)
    exclusive_groups = (
        ("--source-empty", "--source-git", "--source-path", "--source-ref", "--from-exp"),
        ("--token-id", "--path"),
        ("--summary", "--summary-file"),
        ("--feedback", "--feedback-file"),
        ("--keep", "--older-than"),
        ("--ref", "--commit"),
    )
    for group in exclusive_groups:
        if option in group:
            for other in group:
                if other != option:
                    cleaned = _remove_command_option(cleaned, other)
    return [*cleaned, option]


def _prepare_invalid_value_args(args: list[str], option: str, value: str, *, spec: registry.CommandSpec) -> list[str]:
    cleaned = _remove_command_option(args, option)
    exclusive_groups = (
        ("--source-empty", "--source-git", "--source-path", "--source-ref", "--from-exp"),
        ("--token-id", "--path"),
        ("--summary", "--summary-file"),
        ("--feedback", "--feedback-file"),
        ("--keep", "--older-than"),
        ("--ref", "--commit"),
    )
    for group in exclusive_groups:
        if option in group:
            for other in group:
                if other != option:
                    cleaned = _remove_command_option(cleaned, other)
    if spec.path == ("cache", "prune") and option == "--older-than":
        for selector in ("--all", "--docker-images", "--skydiscover-envs", "--trash", "--trash-all"):
            cleaned = _remove_command_option(cleaned, selector)
        cleaned.append("--trash")
    return [*cleaned, option, value]


def _contract_base_invocation(
    spec: registry.CommandSpec,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    project_marker_path: Path,
    project_config_path: Path,
    catalog_upstream: Path,
    export_path: Path,
    extra_worktree_path: Path,
    source_path: Path,
    secret_file_path: Path,
) -> tuple[list[str], Path | None]:
    if _zero_positional_message(spec.handler) is not None:
        args, cwd = _extra_positional_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
            project_marker_path=project_marker_path,
            project_config_path=project_config_path,
            catalog_upstream=catalog_upstream,
            export_path=export_path,
            extra_worktree_path=extra_worktree_path,
        )
        args = args[:-1]
    elif _single_selector_message_for_spec(spec) is not None:
        args, cwd = _single_selector_extra_positional_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
        )
        args = args[:-1]
    elif _fixed_positional_message(spec.handler) is not None:
        args, cwd = _fixed_positional_base_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
            project_config_path=project_config_path,
            source_path=source_path,
            secret_file_path=secret_file_path,
        )
    else:
        args, cwd = _unknown_option_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
        )
        args = args[:-1]
    return args, cwd


def _value_option_missing_value_invocation(
    spec: registry.CommandSpec,
    option: str,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    project_marker_path: Path,
    project_config_path: Path,
    catalog_upstream: Path,
    export_path: Path,
    extra_worktree_path: Path,
    source_path: Path,
    secret_file_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _contract_base_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
        project_marker_path=project_marker_path,
        project_config_path=project_config_path,
        catalog_upstream=catalog_upstream,
        export_path=export_path,
        extra_worktree_path=extra_worktree_path,
        source_path=source_path,
        secret_file_path=secret_file_path,
    )
    return _prepare_missing_value_args(args, option), cwd


def _value_option_empty_value_invocation(
    spec: registry.CommandSpec,
    option: str,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    project_marker_path: Path,
    project_config_path: Path,
    catalog_upstream: Path,
    export_path: Path,
    extra_worktree_path: Path,
    source_path: Path,
    secret_file_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _contract_base_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
        project_marker_path=project_marker_path,
        project_config_path=project_config_path,
        catalog_upstream=catalog_upstream,
        export_path=export_path,
        extra_worktree_path=extra_worktree_path,
        source_path=source_path,
        secret_file_path=secret_file_path,
    )
    if spec.path in {("exp", "token", "list"), ("exp", "token", "revoke")} and option in {"--token-id", "--mode"}:
        exp_marker = json.loads((exp_path / ".alab" / "context.json").read_text(encoding="utf-8"))
        args = [exp_marker["exp_id"] if item == "unexpected-selector-one" else item for item in args]
    if spec.path == ("exp", "create") and option == "--from-commit":
        exp_marker = json.loads((exp_path / ".alab" / "context.json").read_text(encoding="utf-8"))
        args.extend(["--from-exp", exp_marker["exp_id"]])
    if spec.path == ("exp", "checkout") and option == "--commit":
        exp_marker = json.loads((exp_path / ".alab" / "context.json").read_text(encoding="utf-8"))
        args = [exp_marker["exp_id"] if item == "unexpected-selector-one" else item for item in args]
        if "--path" not in args:
            args.extend(["--path", str(extra_worktree_path)])
    return _prepare_invalid_value_args(args, option, "", spec=spec), cwd


def _typed_value_invalid_invocation(
    spec: registry.CommandSpec,
    option: str,
    value: str,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    project_marker_path: Path,
    project_config_path: Path,
    catalog_upstream: Path,
    export_path: Path,
    extra_worktree_path: Path,
    source_path: Path,
    secret_file_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _contract_base_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
        project_marker_path=project_marker_path,
        project_config_path=project_config_path,
        catalog_upstream=catalog_upstream,
        export_path=export_path,
        extra_worktree_path=extra_worktree_path,
        source_path=source_path,
        secret_file_path=secret_file_path,
    )
    if spec.path in {("exp", "token", "list"), ("exp", "token", "revoke")} and option in {"--token-id", "--mode"}:
        exp_marker = json.loads((exp_path / ".alab" / "context.json").read_text(encoding="utf-8"))
        args = [exp_marker["exp_id"] if item == "unexpected-selector-one" else item for item in args]
    if spec.path == ("exp", "create") and option == "--from-commit":
        exp_marker = json.loads((exp_path / ".alab" / "context.json").read_text(encoding="utf-8"))
        args.extend(["--from-exp", exp_marker["exp_id"]])
    if spec.path == ("exp", "checkout") and option == "--commit":
        exp_marker = json.loads((exp_path / ".alab" / "context.json").read_text(encoding="utf-8"))
        args = [exp_marker["exp_id"] if item == "unexpected-selector-one" else item for item in args]
        if "--path" not in args:
            args.extend(["--path", str(extra_worktree_path)])
    if spec.path == ("feedback",) and option == "--kind":
        args.extend(["--body", "typed value feedback"])
    return _prepare_invalid_value_args(args, option, value, spec=spec), cwd


def _duplicate_option_value(
    option: str,
    *,
    project_id: str,
    project_config_path: Path,
    source_path: Path,
    secret_file_path: Path,
    catalog_upstream: Path,
    export_path: Path,
    extra_worktree_path: Path,
) -> str:
    option_values = {
        "--project": project_id,
        "--config": str(project_config_path),
        "--source-path": str(source_path),
        "--source-git": str(catalog_upstream),
        "--source-ref": "src-missing-" + "D" * 22,
        "--from-exp": "exp-missing-" + "D" * 22,
        "--path": str(extra_worktree_path),
        "--out": str(export_path),
        "--value-file": str(secret_file_path),
        "--origin-url": str(catalog_upstream),
        "--mode": "worktree",
        "--version": "latest-attempted",
        "--confirm": "duplicate-confirm",
        "--ref": "none",
        "--role": "admin",
        "--visibility-scope": "same_project",
        "--status": "active",
        "--sort": "created_at:desc",
        "--truncated": "false",
        "--private-to-exp": "exp-missing-" + "D" * 22,
        "--target": "exp:exp-missing-" + "D" * 22,
        "--target-type": "experiment",
        "--target-id": "exp-missing-" + "D" * 22,
        "--created-by": "token",
        "--object-type": "project",
        "--object-id": project_id,
        "--action": "archive",
        "--actor": "root",
        "--keep": "0",
        "--older-than": "1",
        "--commit": "HEAD",
        "--root": "artifacts",
        "--stream": "stdout",
    }
    if option in option_values:
        return option_values[option]
    if option.endswith("-after") or option.endswith("-before"):
        return "2024-01-01T00:00:00Z"
    if option in {
        "--limit",
        "--offset",
        "--max-files",
        "--max-total-bytes",
        "--max-file-bytes",
        "--reward-min",
        "--reward-max",
        "--exit-code",
        "--size-min",
        "--size-max",
        "--config-version",
    }:
        return "1"
    return "duplicate"


def _prepare_duplicate_option_args(
    args: list[str],
    option: str,
    *,
    value: str | None,
) -> list[str]:
    cleaned = _remove_command_option(args, option)
    exclusive_groups = (
        ("--source-empty", "--source-git", "--source-path", "--source-ref", "--from-exp"),
        ("--token-id", "--path"),
        ("--summary", "--summary-file"),
        ("--feedback", "--feedback-file"),
        ("--keep", "--older-than"),
    )
    for group in exclusive_groups:
        if option in group:
            for other in group:
                if other != option:
                    cleaned = _remove_command_option(cleaned, other)
    duplicate = [option] if value is None else [option, value]
    return [*cleaned, *duplicate, *duplicate]


def _duplicate_option_invocation(
    spec: registry.CommandSpec,
    option: str,
    *,
    home: Path,
    root_key: str,
    admin_key: str,
    project_id: str,
    exp_path: Path,
    project_marker_path: Path,
    project_config_path: Path,
    catalog_upstream: Path,
    export_path: Path,
    extra_worktree_path: Path,
    source_path: Path,
    secret_file_path: Path,
) -> tuple[list[str], Path | None]:
    args, cwd = _contract_base_invocation(
        spec,
        home=home,
        root_key=root_key,
        admin_key=admin_key,
        project_id=project_id,
        exp_path=exp_path,
        project_marker_path=project_marker_path,
        project_config_path=project_config_path,
        catalog_upstream=catalog_upstream,
        export_path=export_path,
        extra_worktree_path=extra_worktree_path,
        source_path=source_path,
        secret_file_path=secret_file_path,
    )
    value = (
        _duplicate_option_value(
            option,
            project_id=project_id,
            project_config_path=project_config_path,
            source_path=source_path,
            secret_file_path=secret_file_path,
            catalog_upstream=catalog_upstream,
            export_path=export_path,
            extra_worktree_path=extra_worktree_path,
        )
        if option in _command_local_value_options(spec)
        else None
    )
    return _prepare_duplicate_option_args(args, option, value=value), cwd


def _git(args: list[str], cwd: Path) -> str:
    return services.run_cmd(["git", *args], cwd=cwd).stdout.decode("utf-8", errors="replace").strip()


def _unique_commit_prefix(repo_git: Path, commit: str, cwd: Path) -> str:
    for length in range(4, len(commit) + 1):
        prefix = commit[:length]
        matches = _git(["--git-dir", str(repo_git), "rev-parse", f"--disambiguate={prefix}"], cwd).splitlines()
        if matches == [commit]:
            return prefix
    raise AssertionError(f"could not find a unique prefix for commit {commit}")


def _git_exclude_path(worktree: Path) -> Path:
    resolved = services.run_cmd(["git", "rev-parse", "--git-dir"], cwd=worktree).stdout.decode(
        "utf-8",
        errors="replace",
    ).strip()
    path = Path(resolved)
    git_dir = path if path.is_absolute() else worktree / path
    return git_dir / "info" / "exclude"


def _token_file_mode(worktree: Path) -> str:
    return oct((worktree / ".alab" / "token").stat().st_mode & 0o777)


def _init_catalog_upstream(path: Path) -> str:
    path.mkdir()
    _git(["init"], path)
    _git(["config", "user.name", "ALab Contract"], path)
    _git(["config", "user.email", "alab-contract@example.test"], path)
    _git(["config", "commit.gpgsign", "false"], path)
    (path / "README.md").write_text("one\n", encoding="utf-8")
    _git(["add", "README.md"], path)
    _git(["commit", "-m", "one"], path)
    _git(["branch", "-M", "main"], path)
    return _git(["rev-parse", "HEAD"], path)


def test_registered_command_handlers_gate_unknown_options() -> None:
    helper_guard_gaps = [
        helper_name
        for helper_name in _GUARDED_HELPERS
        if "require_known_options" not in _called_names(getattr(services, helper_name))
    ]
    assert helper_guard_gaps == []

    guarded_helpers = set(_GUARDED_HELPERS)
    missing: list[str] = []
    for spec in registry.COMMANDS:
        if spec.handler is services.cmd_help:
            continue
        calls = _called_names(spec.handler)
        if "require_known_options" in calls or calls & guarded_helpers:
            continue
        missing.append(f"{' '.join(spec.path)} -> {spec.handler.__name__}")

    assert missing == []


def test_registered_command_handlers_validate_positional_arguments() -> None:
    helper_gaps = [
        helper_name
        for helper_name in _POSITIONAL_VALIDATION_HELPERS
        if not (_called_names(getattr(services, helper_name)) & _POSITIONAL_VALIDATORS)
    ]
    assert helper_gaps == []

    validation_helpers = set(_POSITIONAL_VALIDATION_HELPERS)
    missing: list[str] = []
    for spec in registry.COMMANDS:
        if spec.handler is services.cmd_help:
            continue
        calls = _called_names(spec.handler)
        if calls & _POSITIONAL_VALIDATORS or calls & validation_helpers:
            continue
        missing.append(f"{' '.join(spec.path)} -> {spec.handler.__name__}")

    assert missing == []


def test_command_registry_paths_aliases_and_matcher_are_stable() -> None:
    paths = [spec.path for spec in registry.COMMANDS]
    assert len(paths) == len(set(paths))
    assert registry.COMMANDS_BY_PATH == {spec.path: spec for spec in registry.COMMANDS}

    malformed = [
        " ".join(spec.path)
        for spec in registry.COMMANDS
        if not spec.path or not spec.object_type or not spec.summary or spec.credential not in _KNOWN_CREDENTIAL_SURFACES
    ]
    assert malformed == []

    matcher_failures = []
    prefix_failures = []
    for spec in registry.COMMANDS:
        matched, rest = registry.match_command([*spec.path, "__arg__"])
        if matched is not spec or rest != ["__arg__"]:
            matcher_failures.append(" ".join(spec.path))
        if len(spec.path) > 1 and spec.path[:-1] not in registry.COMMANDS_BY_PATH:
            prefix_match, prefix_rest = registry.match_command(list(spec.path[:-1]))
            if prefix_match is not None or prefix_rest != list(spec.path[:-1]):
                prefix_failures.append(" ".join(spec.path))

    assert matcher_failures == []
    assert prefix_failures == []

    by_handler: defaultdict[object, list[registry.CommandSpec]] = defaultdict(list)
    for spec in registry.COMMANDS:
        by_handler[spec.handler].append(spec)

    alias_contract_failures = []
    for specs in by_handler.values():
        if len(specs) <= 1:
            continue
        object_types = {spec.object_type for spec in specs}
        credentials = {spec.credential for spec in specs}
        if len(object_types) != 1 or len(credentials) != 1:
            alias_contract_failures.append([f"{' '.join(spec.path)}:{spec.object_type}:{spec.credential}" for spec in specs])

    assert alias_contract_failures == []


def test_registered_alias_groups_are_limited_to_covered_observe_surfaces() -> None:
    by_handler: defaultdict[object, list[registry.CommandSpec]] = defaultdict(list)
    for spec in registry.COMMANDS:
        by_handler[spec.handler].append(spec)

    observed = {
        tuple(sorted(" ".join(spec.path) for spec in specs))
        for specs in by_handler.values()
        if len(specs) > 1
    }
    expected = {
        ("exp best", "observe experiments best"),
        ("exp list", "observe experiments list"),
        ("exp search", "observe experiments search"),
        ("exp show", "observe experiments show"),
        ("annotations list", "observe annotations list"),
        ("annotations show", "observe annotations show"),
        ("artifacts archive", "observe artifacts archive"),
        ("artifacts export", "observe artifacts export"),
        ("artifacts list", "observe artifacts list"),
        ("artifacts remove", "observe artifacts remove"),
        ("artifacts show", "observe artifacts show"),
        ("artifacts unarchive", "observe artifacts unarchive"),
        ("logs archive", "observe logs archive"),
        ("logs export", "observe logs export"),
        ("logs list", "observe logs list"),
        ("logs remove", "observe logs remove"),
        ("logs show", "observe logs show"),
        ("logs unarchive", "observe logs unarchive"),
        ("observe runs archive", "runs archive"),
        ("observe runs list", "runs list"),
        ("observe runs remove", "runs remove"),
        ("observe runs show", "runs show"),
        ("observe runs unarchive", "runs unarchive"),
    }
    assert observed == expected


def _assert_evidence_refs_exist(refs: Iterable[str]) -> None:
    refs_by_file: defaultdict[str, set[str]] = defaultdict(set)
    for ref in refs:
        file_name, delimiter, test_name = ref.partition("::")
        assert delimiter == "::" and test_name.startswith("test_"), ref
        refs_by_file[file_name].add(test_name)

    missing_refs: list[str] = []
    for file_name, expected_tests in refs_by_file.items():
        module = ast.parse((_REPO_ROOT / file_name).read_text(encoding="utf-8"))
        actual_tests = {
            node.name
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        }
        missing_refs.extend(
            f"{file_name}::{test_name}"
            for test_name in sorted(expected_tests - actual_tests)
        )
    assert missing_refs == []


def test_lifecycle_archive_unarchive_and_remove_evidence_maps_cover_registered_surfaces() -> None:
    archive_unarchive_paths = {
        spec.path
        for spec in registry.COMMANDS
        if spec.path[-1] in {"archive", "unarchive"}
    }
    remove_paths = {
        spec.path
        for spec in registry.COMMANDS
        if spec.path[-1] == "remove" and spec.path != ("exp", "tag", "remove")
    }

    assert set(_LIFECYCLE_ARCHIVE_UNARCHIVE_EVIDENCE) == archive_unarchive_paths
    assert set(_LIFECYCLE_REMOVE_EVIDENCE) == remove_paths
    assert ("exp", "tag", "remove") in registry.COMMANDS_BY_PATH

    for evidence_map in (_LIFECYCLE_ARCHIVE_UNARCHIVE_EVIDENCE, _LIFECYCLE_REMOVE_EVIDENCE):
        for path, refs in evidence_map.items():
            assert refs, path
    _assert_evidence_refs_exist(
        ref
        for evidence_map in (_LIFECYCLE_ARCHIVE_UNARCHIVE_EVIDENCE, _LIFECYCLE_REMOVE_EVIDENCE)
        for refs in evidence_map.values()
        for ref in refs
    )


def test_home_filesystem_and_path_registry_evidence_map_refs_stay_current() -> None:
    assert set(_HOME_FILESYSTEM_EVIDENCE) == {
        "home_resolution_and_layout",
        "path_registry_hashing_and_reuse",
        "context_marker_contracts_and_conflicts",
        "worktree_checkout_and_repair_paths",
    }
    assert all(refs for refs in _HOME_FILESYSTEM_EVIDENCE.values())
    _assert_evidence_refs_exist(
        ref
        for refs in _HOME_FILESYSTEM_EVIDENCE.values()
        for ref in refs
    )


def test_source_public_experiment_evidence_map_refs_stay_current() -> None:
    assert set(_SOURCE_PUBLIC_EXPERIMENT_EVIDENCE) == {
        "canonical_source_storage_and_metadata",
        "standalone_source_import_selectors_and_warnings",
        "public_inline_source_import",
        "public_from_exp_and_visibility",
        "archived_source_and_source_ref",
        "adapter_source_bootstrap",
    }
    assert all(refs for refs in _SOURCE_PUBLIC_EXPERIMENT_EVIDENCE.values())
    _assert_evidence_refs_exist(
        ref
        for refs in _SOURCE_PUBLIC_EXPERIMENT_EVIDENCE.values()
        for ref in refs
    )


def test_runner_adapter_evidence_map_refs_stay_current() -> None:
    assert set(_RUNNER_ADAPTER_EVIDENCE) == {
        "shared_runner_contract",
        "project_config_schema_and_saved_failures",
        "local_runner_and_rewards",
        "docker_runner_fake_default",
        "artifact_and_log_lifecycle",
        "harbor_adapter_fake_default",
        "skydiscover_catalog_source_and_evaluators",
        "real_environment_gates",
    }
    assert all(refs for refs in _RUNNER_ADAPTER_EVIDENCE.values())
    _assert_evidence_refs_exist(
        ref
        for refs in _RUNNER_ADAPTER_EVIDENCE.values()
        for ref in refs
    )


def test_storage_audit_object_evidence_map_refs_stay_current() -> None:
    assert set(_STORAGE_AUDIT_OBJECT_EVIDENCE) == {
        "schema_index_and_json_contracts",
        "maintenance_and_catalog_audit_relationships",
        "credential_token_and_context_audit_relationships",
        "lifecycle_remove_retained_rows_and_trash",
        "annotation_and_visibility_audit_relationships",
    }
    assert all(refs for refs in _STORAGE_AUDIT_OBJECT_EVIDENCE.values())
    _assert_evidence_refs_exist(
        ref
        for refs in _STORAGE_AUDIT_OBJECT_EVIDENCE.values()
        for ref in refs
    )


def test_completion_audit_cli_evidence_rows_are_not_stale() -> None:
    def check(path: Path, p0_heading: str, cli_heading: str) -> list[dict[str, str]]:
        mismatches: list[dict[str, str]] = []
        p0_rows = _markdown_table_rows_after_heading(path, p0_heading)
        product_rows = _markdown_table_rows_after_heading(path, "## Blueprint Product Invariants Evidence")
        cli_rows = _markdown_table_rows_after_heading(path, cli_heading)
        long_tail_rows = _markdown_table_rows_after_heading(path, "### CLI Long-Tail Requirement Evidence")

        guarded_rows = [
            *[row for row in p0_rows if row and row[0].startswith("CLI golden")],
            *[row for row in product_rows if row and row[0].startswith("CLI/output contract")],
            *[row for row in cli_rows if row and row[0].startswith("Primary object types")],
            *long_tail_rows,
        ]
        for row in guarded_rows:
            status = row[1] if len(row) > 1 else ""
            if "`PROVED`" not in status or any(marker in status for marker in ("`PARTIAL`", "`PENDING`", "`ENV-GATED`")):
                mismatches.append({"file": path.name, "row": row[0] if row else "", "status": status})
        return mismatches

    assert check(_COMPLETION_AUDIT_PATH, "## P0 Completion Gates", "## CLI Contract Evidence") == []
    assert check(_COMPLETION_AUDIT_CN_PATH, "## P0 完成门槛", "## CLI Contract 证据") == []


def test_command_registry_object_types_follow_cli_contract_table() -> None:
    expected, duplicate_assignments = _documented_primary_object_types(_SPEC_CLI_PATH)

    registry_paths = set(registry.COMMANDS_BY_PATH)
    documented_handlers = {
        registry.COMMANDS_BY_PATH[path].handler
        for path in expected
        if path in registry.COMMANDS_BY_PATH
    }
    mismatches = [
        f"{' '.join(path)}: registry={registry.COMMANDS_BY_PATH[path].object_type} expected={object_type}"
        for path, object_type in sorted(expected.items())
        if path in registry.COMMANDS_BY_PATH and registry.COMMANDS_BY_PATH[path].object_type != object_type
    ]
    undocumented_unaliased = [
        " ".join(spec.path)
        for spec in registry.COMMANDS
        if spec.path not in expected and spec.handler not in documented_handlers
    ]

    assert {
        "duplicate_assignments": duplicate_assignments,
        "undocumented_unaliased": undocumented_unaliased,
        "unknown_expectations": [" ".join(path) for path in sorted(set(expected) - registry_paths)],
        "mismatches": mismatches,
    } == {
        "duplicate_assignments": [],
        "undocumented_unaliased": [],
        "unknown_expectations": [],
        "mismatches": [],
    }


def test_cli_primary_object_type_tables_are_synchronized() -> None:
    english, english_duplicates = _documented_primary_object_types(_SPEC_CLI_PATH)
    chinese, chinese_duplicates = _documented_primary_object_types(_SPEC_CLI_CN_PATH)

    assert {
        "english_duplicates": english_duplicates,
        "chinese_duplicates": chinese_duplicates,
        "english_only": [" ".join(path) for path in sorted(set(english) - set(chinese))],
        "chinese_only": [" ".join(path) for path in sorted(set(chinese) - set(english))],
        "mismatches": [
            f"{' '.join(path)}: en={english[path]} cn={chinese[path]}"
            for path in sorted(set(english) & set(chinese))
            if english[path] != chinese[path]
        ],
    } == {
        "english_duplicates": [],
        "chinese_duplicates": [],
        "english_only": [],
        "chinese_only": [],
        "mismatches": [],
    }


def _documented_command_option_acceptance_failures(spec_path: Path) -> list[dict[str, object]]:
    documented = _documented_command_options(spec_path)
    failures = []
    for spec in registry.COMMANDS:
        if spec.handler is services.cmd_help:
            continue
        expected = documented.get(spec.path, set())
        if not expected:
            continue
        declared = _declared_options_for_spec(spec)
        missing = sorted(expected - declared)
        if missing:
            failures.append(
                {
                    "command": " ".join(spec.path),
                    "handler": spec.handler.__name__,
                    "spec": spec_path.name,
                    "documented options": sorted(expected),
                    "declared options": sorted(declared),
                    "missing": missing,
                }
            )
    return failures


def test_documented_command_options_are_accepted_by_registered_handlers() -> None:
    assert _documented_command_option_acceptance_failures(_SPEC_CLI_PATH) == []
    assert _documented_command_option_acceptance_failures(_SPEC_CLI_CN_PATH) == []


def test_english_and_chinese_command_surface_coverage_is_synchronized() -> None:
    english = _documented_command_surface_paths(_SPEC_CLI_PATH)
    chinese = _documented_command_surface_paths(_SPEC_CLI_CN_PATH)
    registered = set(registry.COMMANDS_BY_PATH)

    assert {
        "english missing registry paths": [" ".join(path) for path in sorted(registered - english)],
        "chinese missing registry paths": [" ".join(path) for path in sorted(registered - chinese)],
        "english-only documented paths": [" ".join(path) for path in sorted(english - chinese)],
        "chinese-only documented paths": [" ".join(path) for path in sorted(chinese - english)],
        "english unknown paths": [" ".join(path) for path in sorted(english - registered)],
        "chinese unknown paths": [" ".join(path) for path in sorted(chinese - registered)],
    } == {
        "english missing registry paths": [],
        "chinese missing registry paths": [],
        "english-only documented paths": [],
        "chinese-only documented paths": [],
        "english unknown paths": [],
        "chinese unknown paths": [],
    }


def test_english_and_chinese_command_option_contracts_are_synchronized() -> None:
    english = _documented_command_options(_SPEC_CLI_PATH)
    chinese = _documented_command_options(_SPEC_CLI_CN_PATH)
    differences = []
    for path in sorted(set(english) | set(chinese)):
        english_options = english.get(path, set())
        chinese_options = chinese.get(path, set())
        if english_options != chinese_options:
            differences.append(
                {
                    "command": " ".join(path),
                    "english options": sorted(english_options),
                    "chinese options": sorted(chinese_options),
                }
            )

    assert differences == []


def test_english_and_chinese_conflict_option_contracts_are_synchronized() -> None:
    english = _documented_conflict_options(_SPEC_CLI_PATH)
    chinese = _documented_conflict_options(_SPEC_CLI_CN_PATH)
    differences = []
    for path in sorted(set(english) | set(chinese)):
        english_options = english.get(path, set())
        chinese_options = chinese.get(path, set())
        if english_options != chinese_options:
            differences.append(
                {
                    "command": " ".join(path),
                    "english conflict options": sorted(english_options),
                    "chinese conflict options": sorted(chinese_options),
                }
            )

    assert differences == []


def test_dry_run_force_confirm_remove_docs_declare_mixed_mode_conflict() -> None:
    assert _documented_mixed_remove_mode_conflict_failures(_SPEC_CLI_PATH) == []
    assert _documented_mixed_remove_mode_conflict_failures(_SPEC_CLI_CN_PATH) == []


def test_selected_english_and_chinese_success_fields_are_synchronized() -> None:
    differences = []
    for command in _SYNCED_SUCCESS_FIELD_COMMANDS:
        english_fields = _documented_success_fields(command, spec_path=_SPEC_CLI_PATH)
        chinese_fields = _documented_success_fields(command, spec_path=_SPEC_CLI_CN_PATH)
        if english_fields != chinese_fields:
            differences.append(
                {
                    "command": command,
                    "english fields": english_fields,
                    "chinese fields": chinese_fields,
                }
            )

    for command, object_type in _SYNCED_SUCCESS_FIELD_OBJECTS:
        english_fields = _documented_success_fields_for_object(
            command,
            object_type,
            spec_path=_SPEC_CLI_PATH,
        )
        chinese_fields = _documented_success_fields_for_object(
            command,
            object_type,
            spec_path=_SPEC_CLI_CN_PATH,
        )
        if english_fields != chinese_fields:
            differences.append(
                {
                    "command": f"{command} object {object_type}",
                    "english fields": english_fields,
                    "chinese fields": chinese_fields,
                }
            )

    for command, scope in _SYNCED_SUCCESS_FIELD_SCOPES:
        english_fields = _documented_success_fields_for_scope(command, scope, spec_path=_SPEC_CLI_PATH)
        chinese_fields = _documented_success_fields_for_scope(command, scope, spec_path=_SPEC_CLI_CN_PATH)
        if english_fields != chinese_fields:
            differences.append(
                {
                    "command": f"{command} scope {scope}",
                    "english fields": english_fields,
                    "chinese fields": chinese_fields,
                }
            )

    assert differences == []


def test_registered_commands_have_success_field_contracts_in_cli_specs() -> None:
    missing = [
        " ".join(spec.path)
        for spec in registry.COMMANDS
        if not _success_field_contracts_for_spec(spec, spec_path=_SPEC_CLI_PATH)
    ]

    assert missing == []


def test_registered_command_success_field_contracts_are_synchronized() -> None:
    differences = []
    for spec in registry.COMMANDS:
        english_contracts = _success_field_contracts_for_spec(spec, spec_path=_SPEC_CLI_PATH)
        chinese_contracts = _success_field_contracts_for_spec(spec, spec_path=_SPEC_CLI_CN_PATH)
        if english_contracts != chinese_contracts:
            differences.append(
                {
                    "command": " ".join(spec.path),
                    "english contracts": english_contracts,
                    "chinese contracts": chinese_contracts,
                }
            )

    assert differences == []


def test_error_exit_code_mapping_follows_cli_contract_tables() -> None:
    english = _documented_error_exit_mapping(_SPEC_CLI_PATH)
    chinese = _documented_error_exit_mapping(_SPEC_CLI_CN_PATH)

    assert {
        "english only": sorted(set(english) - set(chinese)),
        "chinese only": sorted(set(chinese) - set(english)),
        "mismatches": [
            f"{code}: en={english[code]} cn={chinese[code]}"
            for code in sorted(set(english) & set(chinese))
            if english[code] != chinese[code]
        ],
        "implementation": ERROR_EXIT_CODES,
        "documented": english,
        "runtime lookup": {code: error_exit_code(code) for code in sorted(english)},
        "future not found": (
            error_exit_code("FUTURE_NOT_FOUND"),
            AlabError("FUTURE_NOT_FOUND", "future selector not found").exit_code,
        ),
        "unknown system": error_exit_code("FUTURE_INTERNAL_ERROR"),
    } == {
        "english only": [],
        "chinese only": [],
        "mismatches": [],
        "implementation": english,
        "documented": english,
        "runtime lookup": {code: english[code] for code in sorted(english)},
        "future not found": (2, 2),
        "unknown system": 5,
    }


def test_error_code_catalog_and_numeric_exit_tables_follow_cli_contracts() -> None:
    english_codes = _documented_stable_error_codes(_SPEC_CLI_PATH)
    chinese_codes = _documented_stable_error_codes(_SPEC_CLI_CN_PATH)
    english_mapping = _documented_error_exit_mapping(_SPEC_CLI_PATH)
    chinese_mapping = _documented_error_exit_mapping(_SPEC_CLI_CN_PATH)
    english_exits = _documented_numeric_exit_codes(_SPEC_CLI_PATH)
    chinese_exits = _documented_numeric_exit_codes(_SPEC_CLI_CN_PATH)

    assert {
        "english code list only": sorted(english_codes - chinese_codes),
        "chinese code list only": sorted(chinese_codes - english_codes),
        "english list without mapping": sorted(english_codes - set(english_mapping)),
        "english mapping without list": sorted(set(english_mapping) - english_codes),
        "chinese list without mapping": sorted(chinese_codes - set(chinese_mapping)),
        "chinese mapping without list": sorted(set(chinese_mapping) - chinese_codes),
        "implementation without english list": sorted(set(ERROR_EXIT_CODES) - english_codes),
        "english list without implementation": sorted(english_codes - set(ERROR_EXIT_CODES)),
        "english numeric exits": english_exits,
        "chinese numeric exits": chinese_exits,
        "implementation exit values": sorted(set(ERROR_EXIT_CODES.values())),
        "documented mapping exit values": sorted(set(english_mapping.values())),
    } == {
        "english code list only": [],
        "chinese code list only": [],
        "english list without mapping": [],
        "english mapping without list": [],
        "chinese list without mapping": [],
        "chinese mapping without list": [],
        "implementation without english list": [],
        "english list without implementation": [],
        "english numeric exits": {
            0: "success",
            1: "result failed",
            2: "usage/config",
            3: "auth",
            4: "context/scope",
            5: "system/internal",
        },
        "chinese numeric exits": {
            0: "success",
            1: "result failed",
            2: "usage/config",
            3: "auth",
            4: "context/scope",
            5: "system/internal",
        },
        "implementation exit values": [1, 2, 3, 4, 5],
        "documented mapping exit values": [1, 2, 3, 4, 5],
    }


def test_warning_code_catalogs_cover_implemented_warning_codes() -> None:
    english_codes = _documented_warning_codes(_SPEC_CLI_PATH)
    chinese_codes = _documented_warning_codes(_SPEC_CLI_CN_PATH)
    implemented_codes = _implemented_warning_codes()
    expected_v1_codes = {
        "TOKEN_FILE_PERMISSIONS",
        "TRACKED_SENSITIVE_SOURCE_FILE",
        "SOURCE_EMPTY_AFTER_FILTER",
        "SOURCE_DEDUPED_NAME_IGNORED",
        "PUBLIC_GIT_CREDENTIAL_HELPER_USED",
        "ENV_MODE_FULL_UNREDACTED_HOST_ENV",
        "ARTIFACT_BYTES_NOT_REDACTED",
        "ARTIFACT_CAPTURE_ERROR",
        "DOCKER_SETUP_OUTPUT_CAPTURED",
        "BEST_INCOMPARABLE_RUNS_EXCLUDED",
        "DOCKER_CACHE_PRUNE_FAILED",
    }
    assert {
        "english warning codes": sorted(english_codes),
        "chinese warning codes": sorted(chinese_codes),
        "implemented warning codes": sorted(implemented_codes),
        "implemented without english docs": sorted(implemented_codes - english_codes),
    } == {
        "english warning codes": sorted(expected_v1_codes),
        "chinese warning codes": sorted(expected_v1_codes),
        "implemented warning codes": sorted(expected_v1_codes),
        "implemented without english docs": [],
    }


def test_global_repair_command_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    cases = [
        ("auth init", ["auth", "init"]),
        ("config show", ["config", "show"]),
        ("config set", ["config", "set", "output.preview_bytes", "8192"]),
        ("config reset", ["config", "reset", "output.preview_bytes"]),
    ]

    failures = []
    for index, (command, args) in enumerate(cases):
        home = tmp_path / f"home-{index}"
        code = cli.run(["--home", str(home), *args])
        captured = capsys.readouterr()
        expected_labels = _documented_success_labels(command)
        labels = _output_field_labels(captured.out)
        if code != 0 or captured.err or labels != expected_labels:
            failures.append(
                {
                    "command": command,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "labels": labels,
                    "expected": expected_labels,
                }
            )

    assert failures == []


def test_output_rich_is_single_command_and_non_persistent(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"

    assert cli.run(["--home", str(home), "config", "show"]) == 0
    text_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--output", "rich", "config", "show"]) == 0
    prefix_rich_out = capsys.readouterr()

    assert cli.run(["config", "show", "--home", str(home), "--output", "rich"]) == 0
    trailing_rich_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "config", "show"]) == 0
    after_rich_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "config", "set", "output.format", '"rich"']) == 2
    persistent_rich_err = capsys.readouterr()

    config_text = (home / "config.toml").read_text(encoding="utf-8")

    assert {
        "text": (text_out.err, _output_field_labels(text_out.out), _output_field_map(text_out.out).get("output format")),
        "prefix rich": (
            prefix_rich_out.err,
            prefix_rich_out.out == text_out.out,
            _output_field_map(prefix_rich_out.out).get("output format"),
        ),
        "trailing rich": (
            trailing_rich_out.err,
            trailing_rich_out.out == text_out.out,
            _output_field_map(trailing_rich_out.out).get("output format"),
        ),
        "after rich": (
            after_rich_out.err,
            after_rich_out.out == text_out.out,
            _output_field_map(after_rich_out.out).get("output format"),
        ),
        "persistent rich": (
            persistent_rich_err.out,
            _output_field_labels(persistent_rich_err.err),
            "error code: CONFIG_INVALID" in persistent_rich_err.err,
            'output.format may only be "text"' in persistent_rich_err.err,
            'format = "text"' in config_text,
            'format = "rich"' in config_text,
        ),
    } == {
        "text": ("", _documented_success_labels("config show"), "text"),
        "prefix rich": ("", True, "text"),
        "trailing rich": ("", True, "text"),
        "after rich": ("", True, "text"),
        "persistent rich": ("", _error_field_labels(), True, True, True, False),
    }


def test_key_stdin_input_validation_is_strict_global_contract(tmp_path: Path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]

    invalid_values = [
        "",
        "\n",
        "not-a-single-line-key\nwith-extra-line\n",
        "not-a\0key",
        "key-with-extra-newline\n\n",
    ]
    invalid_failures = []
    for value in invalid_values:
        monkeypatch.setattr(sys, "stdin", io.StringIO(value))
        code = cli.run(["--home", str(home), "--key-stdin", "config", "show"])
        captured = capsys.readouterr()
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or "error code: CONFIG_INVALID" not in captured.err
            or "--key-stdin requires a non-empty single-line value" not in captured.err
        ):
            invalid_failures.append({"value": repr(value), "code": code, "stdout": captured.out, "stderr": captured.err})

    conflict_cases = [
        ("duplicate key stdin", ["--key-stdin", "--key-stdin", "config", "show"]),
        ("key stdin then key", ["--key-stdin", "--key", root_key, "config", "show"]),
        ("key then key stdin", ["--key", root_key, "--key-stdin", "config", "show"]),
    ]
    conflict_failures = []
    for name, args in conflict_cases:
        monkeypatch.setattr(sys, "stdin", io.StringIO(root_key + "\n"))
        code = cli.run(["--home", str(home), *args])
        captured = capsys.readouterr()
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or "error code: CONFIG_INVALID" not in captured.err
            or "--key conflicts with --key-stdin" not in captured.err
        ):
            conflict_failures.append({"case": name, "code": code, "stdout": captured.out, "stderr": captured.err})

    monkeypatch.setattr(sys, "stdin", io.StringIO(root_key + "\n"))
    valid_code = cli.run(["--home", str(home), "--key-stdin", "key", "list", "--root"])
    valid_out = capsys.readouterr()

    assert {
        "invalid failures": invalid_failures,
        "conflict failures": conflict_failures,
        "valid trailing newline": (
            valid_code,
            valid_out.err,
            _output_field_labels(valid_out.out),
            _output_field_map(valid_out.out).get("credential type"),
            _output_field_map(valid_out.out).get("status"),
        ),
    } == {
        "invalid failures": [],
        "conflict failures": [],
        "valid trailing newline": (0, "", _documented_success_labels("key list --root"), "root", "active"),
    }


def test_empty_ambient_alab_key_behaves_like_absent_credential(tmp_path: Path, monkeypatch, capsys) -> None:
    home, _root_key, project_id, _admin_key = _init_capability_project(tmp_path, capsys)
    control_path = home / "project-workspaces" / project_id
    command = ["--home", str(home), "context", "repair", "--path", str(control_path)]

    before_empty = _database_snapshot(home)
    monkeypatch.setenv("ALAB_KEY", "")
    empty_code = cli.run(command)
    empty_err = capsys.readouterr()
    empty_snapshot = _database_snapshot(home)

    monkeypatch.delenv("ALAB_KEY", raising=False)
    before_absent = _database_snapshot(home)
    absent_code = cli.run(command)
    absent_err = capsys.readouterr()
    absent_snapshot = _database_snapshot(home)
    reason = "context repair requires admin/root key or matching self token"

    assert {
        "empty": (
            empty_code,
            empty_err.out,
            _output_field_labels(empty_err.err),
            _output_field_map(empty_err.err).get("error code"),
            _output_field_map(empty_err.err).get("exit code"),
            _output_field_map(empty_err.err).get("reason"),
            empty_snapshot == before_empty,
        ),
        "absent": (
            absent_code,
            absent_err.out,
            _output_field_labels(absent_err.err),
            _output_field_map(absent_err.err).get("error code"),
            _output_field_map(absent_err.err).get("exit code"),
            _output_field_map(absent_err.err).get("reason"),
            absent_snapshot == before_absent,
        ),
        "same stderr": empty_err.err == absent_err.err,
    } == {
        "empty": (3, "", _error_field_labels(), "AUTH_REQUIRED", "3", reason, True),
        "absent": (3, "", _error_field_labels(), "AUTH_REQUIRED", "3", reason, True),
        "same stderr": True,
    }


def test_registered_commands_reject_global_option_errors_before_home_creation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    failures = []
    for command_index, spec in enumerate(registry.COMMANDS):
        command = [*spec.path]
        home_a = tmp_path / f"global-option-{command_index}-a"
        home_b = tmp_path / f"global-option-{command_index}-b"
        cases = [
            (
                "duplicate home",
                ["--home", str(home_a), *command, "--home", str(home_b)],
                None,
                "duplicate global option --home",
                [home_a, home_b],
            ),
            (
                "duplicate output",
                ["--home", str(home_a), "--output", "text", *command, "--output", "rich"],
                None,
                "duplicate global option --output",
                [home_a],
            ),
            (
                "duplicate key",
                ["--home", str(home_a), "--key", "first-key", *command, "--key", "second-key"],
                None,
                "duplicate global option --key",
                [home_a],
            ),
            (
                "missing home value",
                [*command, "--home"],
                None,
                "--home requires a value",
                [],
            ),
            (
                "empty home value",
                [*command, "--home", ""],
                None,
                "--home requires a non-empty value",
                [],
            ),
            (
                "missing output value",
                ["--home", str(home_a), *command, "--output"],
                None,
                "--output requires a value",
                [home_a],
            ),
            (
                "empty output value",
                ["--home", str(home_a), *command, "--output", ""],
                None,
                "--output requires a non-empty value",
                [home_a],
            ),
            (
                "missing key value",
                ["--home", str(home_a), *command, "--key"],
                None,
                "--key requires a value",
                [home_a],
            ),
            (
                "empty key value",
                ["--home", str(home_a), *command, "--key", ""],
                None,
                "--key requires a non-empty value",
                [home_a],
            ),
            (
                "invalid output value",
                ["--home", str(home_a), *command, "--output", "json"],
                None,
                "--output must be text or rich",
                [home_a],
            ),
            (
                "duplicate key stdin",
                ["--home", str(home_a), "--key-stdin", *command, "--key-stdin"],
                "stdin-key\n",
                "--key conflicts with --key-stdin",
                [home_a],
            ),
            (
                "key stdin then key",
                ["--home", str(home_a), "--key-stdin", *command, "--key", "second-key"],
                "stdin-key\n",
                "--key conflicts with --key-stdin",
                [home_a],
            ),
            (
                "key then key stdin",
                ["--home", str(home_a), "--key", "first-key", *command, "--key-stdin"],
                "stdin-key\n",
                "--key conflicts with --key-stdin",
                [home_a],
            ),
        ]
        for case_name, args, stdin, reason, watched_paths in cases:
            if stdin is not None:
                monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
            code = cli.run(args)
            captured = capsys.readouterr()
            fields = _output_field_map(captured.err) if captured.err else {}
            expected_fields = {
                "object": "error",
                "message": "Command failed.",
                "error code": "CONFIG_INVALID",
                "exit code": "2",
                "reason": reason,
                "next": "none",
            }
            if (
                code != 2
                or captured.out
                or _output_field_labels(captured.err) != _error_field_labels()
                or fields != expected_fields
                or any(path.exists() for path in watched_paths)
            ):
                failures.append(
                    {
                        "command": " ".join(spec.path),
                        "case": case_name,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "fields": fields,
                        "args": args,
                        "watched paths": [str(path) for path in watched_paths],
                    }
                )

    assert failures == [], json.dumps(failures, indent=2)


def test_object_specific_not_found_errors_stay_precise_for_root_admin_selectors(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)

    def missing_id(prefix: str) -> str:
        return f"{prefix}-missing-{'A' * 22}"

    documented_not_found_codes = {
        "PROJECT_NOT_FOUND",
        "SOURCE_NOT_FOUND",
        "EXPERIMENT_NOT_FOUND",
        "RUN_NOT_FOUND",
        "VALIDATION_NOT_FOUND",
        "ARTIFACT_NOT_FOUND",
        "LOG_NOT_FOUND",
        "ANNOTATION_NOT_FOUND",
        "CREDENTIAL_NOT_FOUND",
        "AUDIT_NOT_FOUND",
        "CATALOG_NOT_FOUND",
        "CACHE_NOT_FOUND",
    }
    runtime_cases = [
        (
            "project",
            ["--home", str(home), "--key", root_key, "project", "show", "--project", missing_id("proj")],
            "PROJECT_NOT_FOUND",
            "project not found",
        ),
        (
            "source",
            ["--home", str(home), "--key", admin_key, "source", "show", missing_id("src"), "--project", project_id],
            "SOURCE_NOT_FOUND",
            "source not found",
        ),
        (
            "experiment",
            ["--home", str(home), "--key", admin_key, "exp", "show", missing_id("exp"), "--project", project_id],
            "EXPERIMENT_NOT_FOUND",
            "experiment not found",
        ),
        (
            "run",
            ["--home", str(home), "--key", admin_key, "runs", "show", missing_id("run"), "--project", project_id],
            "RUN_NOT_FOUND",
            "run not found",
        ),
        (
            "validation",
            ["--home", str(home), "--key", admin_key, "project", "validation", "archive", missing_id("val"), "--project", project_id],
            "VALIDATION_NOT_FOUND",
            "validation not found",
        ),
        (
            "artifact",
            ["--home", str(home), "--key", admin_key, "artifacts", "show", missing_id("art"), "--project", project_id],
            "ARTIFACT_NOT_FOUND",
            "artifact not found",
        ),
        (
            "log",
            ["--home", str(home), "--key", admin_key, "logs", "show", missing_id("log"), "--project", project_id],
            "LOG_NOT_FOUND",
            "log not found",
        ),
        (
            "annotation",
            ["--home", str(home), "--key", admin_key, "annotations", "show", missing_id("ann"), "--project", project_id],
            "ANNOTATION_NOT_FOUND",
            "annotation not found",
        ),
        (
            "credential",
            ["--home", str(home), "--key", root_key, "key", "revoke", missing_id("cred"), "--project", project_id],
            "CREDENTIAL_NOT_FOUND",
            "credential not found",
        ),
        (
            "audit",
            ["--home", str(home), "--key", root_key, "audit", "show", missing_id("aud")],
            "AUDIT_NOT_FOUND",
            "audit event not found",
        ),
        (
            "catalog",
            ["--home", str(home), "--key", root_key, "catalog", "skydiscover", "show"],
            "CATALOG_NOT_FOUND",
            "active SkyDiscover catalog not found",
        ),
    ]
    runtime_not_found_codes = {expected_code for _name, _args, expected_code, _expected_reason in runtime_cases}
    assert runtime_not_found_codes == documented_not_found_codes - {"CACHE_NOT_FOUND"}

    runtime_failures = []
    for name, args, expected_code, expected_reason in runtime_cases:
        db_before = _database_snapshot(home)
        config_before = (home / "config.toml").read_text(encoding="utf-8")
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err)
        db_after = _database_snapshot(home)
        config_after = (home / "config.toml").read_text(encoding="utf-8")
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != expected_code
            or fields.get("exit code") != "2"
            or expected_reason not in captured.err
            or db_after != db_before
            or config_after != config_before
        ):
            runtime_failures.append(
                {
                    "case": name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "expected code": expected_code,
                    "expected reason": expected_reason,
                    "db changed": db_after != db_before,
                    "config changed": config_after != config_before,
                }
            )

    assert {
        "runtime failures": runtime_failures,
        "exit mapping": {code: error_exit_code(code) for code in sorted(documented_not_found_codes)},
    } == {
        "runtime failures": [],
        "exit mapping": {code: 2 for code in sorted(documented_not_found_codes)},
    }


def test_alab_object_selectors_require_complete_ids(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)

    cases = [
        ("project", ["--home", str(home), "--key", root_key, "project", "show", "--project", "proj-short"]),
        ("source", ["--home", str(home), "--key", admin_key, "source", "show", "src-short", "--project", project_id]),
        ("experiment", ["--home", str(home), "--key", admin_key, "exp", "show", "exp-short", "--project", project_id]),
        ("validation", ["--home", str(home), "--key", admin_key, "project", "validation", "archive", "val-short", "--project", project_id]),
        ("run", ["--home", str(home), "--key", admin_key, "runs", "show", "run-short", "--project", project_id]),
        ("artifact", ["--home", str(home), "--key", admin_key, "artifacts", "show", "art-short", "--project", project_id]),
        ("log", ["--home", str(home), "--key", admin_key, "logs", "show", "log-short", "--project", project_id]),
        ("annotation", ["--home", str(home), "--key", admin_key, "annotations", "show", "ann-short", "--project", project_id]),
        ("credential", ["--home", str(home), "--key", root_key, "key", "revoke", "cred-short", "--project", project_id]),
        ("audit", ["--home", str(home), "--key", root_key, "audit", "show", "aud-short"]),
    ]

    failures = []
    for name, args in cases:
        db_before = _database_snapshot(home)
        config_before = (home / "config.toml").read_text(encoding="utf-8")
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err)
        db_after = _database_snapshot(home)
        config_after = (home / "config.toml").read_text(encoding="utf-8")
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "CONFIG_INVALID"
            or fields.get("exit code") != "2"
            or "object ids must be complete" not in captured.err
            or db_after != db_before
            or config_after != config_before
        ):
            failures.append(
                {
                    "case": name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "db changed": db_after != db_before,
                    "config changed": config_after != config_before,
                }
            )

    assert failures == []


def test_annotate_add_rejects_incomplete_target_ids_before_body_file_reads(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    admin_args = ["--home", str(home), "--key", admin_key]
    exp_path = tmp_path / "annotation-id-preflight-exp"
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Annotation Id Preflight",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]

    missing_body_path = tmp_path / "missing-annotation-preflight-body.txt"
    cases = [
        (
            "missing target",
            [*admin_args, "annotate", "add", "--project", project_id, "--body-file", str(missing_body_path)],
            "missing required option --target",
        ),
        (
            "experiment target id",
            [*admin_args, "annotate", "add", "--project", project_id, "--target", "exp:exp-short", "--body-file", str(missing_body_path)],
            "object ids must be complete",
        ),
        (
            "run target id",
            [*admin_args, "annotate", "add", "--project", project_id, "--target", "run:run-short", "--body-file", str(missing_body_path)],
            "object ids must be complete",
        ),
        (
            "artifact target id",
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                "artifact:art-short",
                "--body-file",
                str(missing_body_path),
            ],
            "object ids must be complete",
        ),
        (
            "path target experiment id",
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                "path:exp-short@HEAD:main.py",
                "--body-file",
                str(missing_body_path),
            ],
            "object ids must be complete",
        ),
        (
            "private target experiment id",
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                f"exp:{exp_id}",
                "--private-to-exp",
                "exp-short",
                "--body-file",
                str(missing_body_path),
            ],
            "object ids must be complete",
        ),
    ]
    project_marker_path = home / "project-workspaces" / project_id / ".alab" / "context.json"
    watched_files = [
        home / "config.toml",
        project_marker_path,
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
    ]
    failures = []

    for name, args, expected_reason in cases:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
        body_file_absent = not missing_body_path.exists()
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "CONFIG_INVALID"
            or fields.get("exit code") != "2"
            or fields.get("reason") != expected_reason
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
            or not body_file_absent
        ):
            failures.append(
                {
                    "case": name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "args": args,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                    "body file absent": body_file_absent,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_git_commit_sha_selectors_accept_unambiguous_abbreviations_and_reject_ambiguity(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    admin_args = ["--home", str(home), "--key", admin_key]
    parent_path = tmp_path / "sha-selector-parent"
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "SHA Selector Parent",
                "--path",
                str(parent_path),
            ]
        )
        == 0
    )
    parent_id = _output_field_map(capsys.readouterr().out)["exp id"]
    repo_git = home / "projects" / project_id / "repo.git"
    with sqlite3.connect(home / "alab.db") as conn:
        baseline_commit = conn.execute("SELECT baseline_commit FROM experiments WHERE exp_id = ?", (parent_id,)).fetchone()[0]
    commit_prefix = _unique_commit_prefix(repo_git, baseline_commit, home)
    assert len(commit_prefix) < len(baseline_commit)

    child_path = tmp_path / "sha-prefix-child"
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "SHA Prefix Child",
                "--from-exp",
                parent_id,
                "--from-commit",
                commit_prefix,
                "--path",
                str(child_path),
            ]
        )
        == 0
    )
    child_fields = _output_field_map(capsys.readouterr().out)
    child_id = child_fields["exp id"]
    with sqlite3.connect(home / "alab.db") as conn:
        child_row = conn.execute("SELECT baseline_commit, metadata_json FROM experiments WHERE exp_id = ?", (child_id,)).fetchone()
    child_metadata = json.loads(child_row[1])
    assert child_row[0] == baseline_commit
    assert child_metadata["creation_origin"]["from_commit"] == commit_prefix
    assert child_metadata["creation_origin"]["resolved_commit"] == baseline_commit

    inspection_path = tmp_path / "sha-prefix-inspection"
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "checkout",
                parent_id,
                "--project",
                project_id,
                "--path",
                str(inspection_path),
                "--commit",
                commit_prefix.upper(),
            ]
        )
        == 0
    )
    checkout_fields = _output_field_map(capsys.readouterr().out)
    assert checkout_fields["inspection commit"] == baseline_commit

    assert (
        cli.run(
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                f"path:{parent_id}@{commit_prefix}:main.py",
                "--body",
                "path target by abbreviated commit",
            ]
        )
        == 0
    )
    path_annotation_fields = _output_field_map(capsys.readouterr().out)
    assert path_annotation_fields["resolved commit"] == baseline_commit

    assert (
        cli.run(
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                f"lines:{parent_id}@{commit_prefix.upper()}:main.py:1-1",
                "--body",
                "line target by abbreviated commit",
            ]
        )
        == 0
    )
    line_annotation_fields = _output_field_map(capsys.readouterr().out)
    assert line_annotation_fields["resolved commit"] == baseline_commit

    original_run_cmd = services.run_cmd
    ambiguous_other = "f" * 40

    def fake_run_cmd(args, *, cwd=None, env=None, input_bytes=None, timeout=None, check=True):
        command = list(args)
        if command == ["git", f"--git-dir={repo_git}", "rev-parse", "--disambiguate=abcd"]:
            return subprocess.CompletedProcess(command, 0, stdout=f"{baseline_commit}\n{ambiguous_other}\n".encode(), stderr=b"")
        return original_run_cmd(args, cwd=cwd, env=env, input_bytes=input_bytes, timeout=timeout, check=check)

    monkeypatch.setattr(services, "run_cmd", fake_run_cmd)

    ambiguous_child_path = tmp_path / "ambiguous-sha-child"
    db_before = _database_snapshot(home)
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Ambiguous SHA Child",
                "--from-exp",
                parent_id,
                "--from-commit",
                "abcd",
                "--path",
                str(ambiguous_child_path),
            ]
        )
        == 2
    )
    ambiguous_child_err = capsys.readouterr().err
    assert _output_field_labels(ambiguous_child_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in ambiguous_child_err
    assert "reason: commit selector is ambiguous" in ambiguous_child_err
    assert _database_snapshot(home) == db_before
    assert not ambiguous_child_path.exists()

    ambiguous_checkout_path = tmp_path / "ambiguous-sha-checkout"
    db_before = _database_snapshot(home)
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "checkout",
                parent_id,
                "--project",
                project_id,
                "--path",
                str(ambiguous_checkout_path),
                "--commit",
                "abcd",
            ]
        )
        == 2
    )
    ambiguous_checkout_err = capsys.readouterr().err
    assert _output_field_labels(ambiguous_checkout_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in ambiguous_checkout_err
    assert "reason: commit selector is ambiguous" in ambiguous_checkout_err
    assert _database_snapshot(home) == db_before
    assert not ambiguous_checkout_path.exists()

    db_before = _database_snapshot(home)
    assert (
        cli.run(
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                f"path:{parent_id}@abcd:main.py",
                "--body",
                "ambiguous target",
            ]
        )
        == 2
    )
    ambiguous_annotation_err = capsys.readouterr().err
    assert _output_field_labels(ambiguous_annotation_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in ambiguous_annotation_err
    assert "reason: commit selector is ambiguous" in ambiguous_annotation_err
    assert _database_snapshot(home) == db_before


def test_rfc3339_time_filters_require_explicit_offsets(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)

    filter_cases = [
        ("audit created after", ["--home", str(home), "--key", root_key, "audit", "list"], "--created-after"),
        ("audit created before", ["--home", str(home), "--key", root_key, "audit", "list"], "--created-before"),
        ("exp created after", ["--home", str(home), "--key", admin_key, "exp", "list", "--project", project_id], "--created-after"),
        ("exp created before", ["--home", str(home), "--key", admin_key, "exp", "list", "--project", project_id], "--created-before"),
        ("exp updated after", ["--home", str(home), "--key", admin_key, "exp", "list", "--project", project_id], "--updated-after"),
        ("exp updated before", ["--home", str(home), "--key", admin_key, "exp", "list", "--project", project_id], "--updated-before"),
        ("runs started after", ["--home", str(home), "--key", admin_key, "runs", "list", "--project", project_id], "--started-after"),
        ("runs started before", ["--home", str(home), "--key", admin_key, "runs", "list", "--project", project_id], "--started-before"),
        ("runs ended after", ["--home", str(home), "--key", admin_key, "runs", "list", "--project", project_id], "--ended-after"),
        ("runs ended before", ["--home", str(home), "--key", admin_key, "runs", "list", "--project", project_id], "--ended-before"),
        ("artifacts created after", ["--home", str(home), "--key", admin_key, "artifacts", "list", "--project", project_id], "--created-after"),
        ("artifacts created before", ["--home", str(home), "--key", admin_key, "artifacts", "list", "--project", project_id], "--created-before"),
        ("logs created after", ["--home", str(home), "--key", admin_key, "logs", "list", "--project", project_id], "--created-after"),
        ("logs created before", ["--home", str(home), "--key", admin_key, "logs", "list", "--project", project_id], "--created-before"),
        ("annotations created after", ["--home", str(home), "--key", admin_key, "annotations", "list", "--project", project_id], "--created-after"),
        ("annotations created before", ["--home", str(home), "--key", admin_key, "annotations", "list", "--project", project_id], "--created-before"),
        ("annotations updated after", ["--home", str(home), "--key", admin_key, "annotations", "list", "--project", project_id], "--updated-after"),
        ("annotations updated before", ["--home", str(home), "--key", admin_key, "annotations", "list", "--project", project_id], "--updated-before"),
    ]

    missing_offset_failures = []
    malformed_failures = []
    valid_offset_failures = []
    inverted_range_failures = []
    for name, base_args, option in filter_cases:
        db_before_missing_offset = _database_snapshot(home)
        config_before_missing_offset = (home / "config.toml").read_text(encoding="utf-8")
        missing_offset_code = cli.run([*base_args, option, "2026-01-01T00:00:00"])
        missing_offset = capsys.readouterr()
        missing_offset_fields = _output_field_map(missing_offset.err)
        db_after_missing_offset = _database_snapshot(home)
        config_after_missing_offset = (home / "config.toml").read_text(encoding="utf-8")
        if (
            missing_offset_code != 2
            or missing_offset.out
            or _output_field_labels(missing_offset.err) != _error_field_labels()
            or missing_offset_fields.get("error code") != "CONFIG_INVALID"
            or missing_offset_fields.get("exit code") != "2"
            or "timestamps must include Z or a numeric offset" not in missing_offset.err
            or db_after_missing_offset != db_before_missing_offset
            or config_after_missing_offset != config_before_missing_offset
        ):
            missing_offset_failures.append(
                {
                    "case": name,
                    "option": option,
                    "code": missing_offset_code,
                    "stdout": missing_offset.out,
                    "stderr": missing_offset.err,
                    "fields": missing_offset_fields,
                    "db changed": db_after_missing_offset != db_before_missing_offset,
                    "config changed": config_after_missing_offset != config_before_missing_offset,
                }
            )

        db_before_malformed = _database_snapshot(home)
        config_before_malformed = (home / "config.toml").read_text(encoding="utf-8")
        malformed_code = cli.run([*base_args, option, "2026-01-01 00:00:00Z"])
        malformed = capsys.readouterr()
        malformed_fields = _output_field_map(malformed.err)
        db_after_malformed = _database_snapshot(home)
        config_after_malformed = (home / "config.toml").read_text(encoding="utf-8")
        if (
            malformed_code != 2
            or malformed.out
            or _output_field_labels(malformed.err) != _error_field_labels()
            or malformed_fields.get("error code") != "CONFIG_INVALID"
            or malformed_fields.get("exit code") != "2"
            or "invalid RFC 3339 timestamp" not in malformed.err
            or db_after_malformed != db_before_malformed
            or config_after_malformed != config_before_malformed
        ):
            malformed_failures.append(
                {
                    "case": name,
                    "option": option,
                    "code": malformed_code,
                    "stdout": malformed.out,
                    "stderr": malformed.err,
                    "fields": malformed_fields,
                    "db changed": db_after_malformed != db_before_malformed,
                    "config changed": config_after_malformed != config_before_malformed,
                }
            )

        valid_offset_code = cli.run([*base_args, option, "2000-01-01T00:00:00+08:00"])
        valid_offset = capsys.readouterr()
        if valid_offset_code != 0 or valid_offset.err:
            valid_offset_failures.append(
                {
                    "case": name,
                    "option": option,
                    "code": valid_offset_code,
                    "stdout": valid_offset.out,
                    "stderr": valid_offset.err,
                }
            )

    range_cases = [
        (
            "audit created",
            ["--home", str(home), "--key", root_key, "audit", "list"],
            "--created-after",
            "--created-before",
        ),
        (
            "exp created",
            ["--home", str(home), "--key", admin_key, "exp", "list", "--project", project_id],
            "--created-after",
            "--created-before",
        ),
        (
            "exp updated",
            ["--home", str(home), "--key", admin_key, "exp", "list", "--project", project_id],
            "--updated-after",
            "--updated-before",
        ),
        (
            "runs started",
            ["--home", str(home), "--key", admin_key, "runs", "list", "--project", project_id],
            "--started-after",
            "--started-before",
        ),
        (
            "runs ended",
            ["--home", str(home), "--key", admin_key, "runs", "list", "--project", project_id],
            "--ended-after",
            "--ended-before",
        ),
        (
            "artifacts created",
            ["--home", str(home), "--key", admin_key, "artifacts", "list", "--project", project_id],
            "--created-after",
            "--created-before",
        ),
        (
            "logs created",
            ["--home", str(home), "--key", admin_key, "logs", "list", "--project", project_id],
            "--created-after",
            "--created-before",
        ),
        (
            "annotations created",
            ["--home", str(home), "--key", admin_key, "annotations", "list", "--project", project_id],
            "--created-after",
            "--created-before",
        ),
        (
            "annotations updated",
            ["--home", str(home), "--key", admin_key, "annotations", "list", "--project", project_id],
            "--updated-after",
            "--updated-before",
        ),
    ]
    for name, base_args, after_option, before_option in range_cases:
        db_before_range = _database_snapshot(home)
        config_before_range = (home / "config.toml").read_text(encoding="utf-8")
        inverted_code = cli.run(
            [
                *base_args,
                after_option,
                "2999-01-01T00:00:00Z",
                before_option,
                "2000-01-01T00:00:00Z",
            ]
        )
        inverted = capsys.readouterr()
        inverted_fields = _output_field_map(inverted.err)
        db_after_range = _database_snapshot(home)
        config_after_range = (home / "config.toml").read_text(encoding="utf-8")
        if (
            inverted_code != 2
            or inverted.out
            or _output_field_labels(inverted.err) != _error_field_labels()
            or inverted_fields.get("error code") != "CONFIG_INVALID"
            or inverted_fields.get("exit code") != "2"
            or f"{after_option} must be less than or equal to {before_option}" not in inverted.err
            or db_after_range != db_before_range
            or config_after_range != config_before_range
        ):
            inverted_range_failures.append(
                {
                    "case": name,
                    "after option": after_option,
                    "before option": before_option,
                    "code": inverted_code,
                    "stdout": inverted.out,
                    "stderr": inverted.err,
                    "fields": inverted_fields,
                    "db changed": db_after_range != db_before_range,
                    "config changed": config_after_range != config_before_range,
                }
            )

    assert {
        "missing offset failures": missing_offset_failures,
        "malformed failures": malformed_failures,
        "valid offset failures": valid_offset_failures,
        "inverted range failures": inverted_range_failures,
    } == {
        "missing offset failures": [],
        "malformed failures": [],
        "valid offset failures": [],
        "inverted range failures": [],
    }


def test_debug_mode_traces_only_internal_system_failures(tmp_path: Path, monkeypatch, capsys) -> None:
    original_build_request = cli.build_request
    local_secret_value = "debug-local-secret-should-not-render"
    env_secret_value = "debug-env-secret-should-not-render"

    def broken_build_request(_parsed: cli.ParsedGlobals) -> cli.Request:
        hidden_local = local_secret_value
        assert hidden_local
        raise RuntimeError("debug contract boom")

    monkeypatch.setenv("ALAB_KEY", env_secret_value)
    monkeypatch.setattr(cli, "build_request", broken_build_request)

    assert cli.run(["config", "show"]) == 5
    normal_err = capsys.readouterr().err

    monkeypatch.setenv("ALAB_DEBUG", "1")
    assert cli.run(["config", "show"]) == 5
    debug_err = capsys.readouterr().err

    monkeypatch.setattr(cli, "build_request", original_build_request)
    home = tmp_path / "home"
    assert cli.run(["--home", str(home), "config", "set", "output.format", '"rich"']) == 2
    config_err = capsys.readouterr().err

    assert {
        "normal": (
            normal_err.startswith("object: error\nmessage: Command failed.\nerror code: STORAGE_ERROR\nexit code: 5\n"),
            "reason: debug contract boom" in normal_err,
            "Traceback" in normal_err,
            "RuntimeError" in normal_err,
            local_secret_value in normal_err,
            env_secret_value in normal_err,
            "hidden_local" in normal_err,
        ),
        "debug": (
            debug_err.startswith("object: error\nmessage: Command failed.\nerror code: STORAGE_ERROR\nexit code: 5\n"),
            "reason: debug contract boom" in debug_err,
            "Traceback" in debug_err,
            "RuntimeError: debug contract boom" in debug_err,
            local_secret_value in debug_err,
            env_secret_value in debug_err,
            "hidden_local" in debug_err,
        ),
        "config invalid": (
            _output_field_labels(config_err),
            "error code: CONFIG_INVALID" in config_err,
            "Traceback" in config_err,
            "RuntimeError" in config_err,
            env_secret_value in config_err,
        ),
    } == {
        "normal": (True, True, False, False, False, False, False),
        "debug": (True, True, True, True, False, False, False),
        "config invalid": (_error_field_labels(), True, False, False, False),
    }


def test_home_exists_and_output_exists_render_stable_error_blocks(tmp_path: Path, monkeypatch, capsys) -> None:
    def assert_error(captured, *, expected_code: str, expected_reason: str) -> dict[str, str]:
        fields = _output_field_map(captured.err)
        assert captured.out == ""
        assert _output_field_labels(captured.err) == _error_field_labels()
        assert fields["error code"] == expected_code
        assert fields["exit code"] == "2"
        assert expected_reason in captured.err
        return fields

    nonempty_home = tmp_path / "nonempty-home"
    nonempty_home.mkdir()
    (nonempty_home / "unrelated.txt").write_text("not an ALab home\n", encoding="utf-8")
    assert cli.run(["--home", str(nonempty_home), "auth", "init"]) == 2
    nonempty_home_err = assert_error(capsys.readouterr(), expected_code="HOME_EXISTS", expected_reason="home exists and is not an initialized ALab home")
    nonempty_home_entries = sorted(path.name for path in nonempty_home.iterdir())

    initialized_home = tmp_path / "initialized-home"
    assert cli.run(["--home", str(initialized_home), "auth", "init"]) == 0
    capsys.readouterr()
    initialized_db_before = _database_snapshot(initialized_home)
    initialized_config_before = (initialized_home / "config.toml").read_text(encoding="utf-8")
    assert cli.run(["--home", str(initialized_home), "auth", "init"]) == 2
    initialized_home_err = assert_error(capsys.readouterr(), expected_code="HOME_EXISTS", expected_reason="ALab home is already initialized")
    initialized_db_after = _database_snapshot(initialized_home)
    initialized_config_after = (initialized_home / "config.toml").read_text(encoding="utf-8")

    home, _root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(tmp_path, capsys, worktree_name="worktree")
    admin_args = ["--home", str(home), "--key", admin_key]
    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "output exists contract"]) == 0
    run_fields = _output_field_map(capsys.readouterr().out)
    run_id = run_fields["run id"]

    assert cli.run([*admin_args, "artifacts", "list", "--project", project_id, "--run", run_id]) == 0
    artifact_id = _output_field_map(capsys.readouterr().out)["artifact id"]
    assert cli.run([*admin_args, "logs", "list", "--project", project_id, "--run", run_id, "--stream", "stdout"]) == 0
    log_id = _output_field_map(capsys.readouterr().out)["log id"]

    export_cases = [
        (
            "config",
            [*admin_args, "project", "config", "export", "--project", project_id],
            tmp_path / "config-export.toml",
        ),
        (
            "artifact",
            [*admin_args, "artifacts", "export", artifact_id, "--project", project_id],
            tmp_path / "artifact-export.txt",
        ),
        (
            "log",
            [*admin_args, "logs", "export", log_id, "--project", project_id],
            tmp_path / "log-export.txt",
        ),
    ]

    output_exists_failures = []
    missing_parent_failures = []
    directory_output_failures = []
    for name, base_args, output_path in export_cases:
        output_path.write_text(f"preserve {name}\n", encoding="utf-8")
        db_before = _database_snapshot(home)
        config_before = (home / "config.toml").read_text(encoding="utf-8")
        code = cli.run([*base_args, "--out", str(output_path)])
        captured = capsys.readouterr()
        fields = assert_error(captured, expected_code="OUTPUT_EXISTS", expected_reason="output path already exists")
        db_after = _database_snapshot(home)
        config_after = (home / "config.toml").read_text(encoding="utf-8")
        if (
            code != 2
            or output_path.read_text(encoding="utf-8") != f"preserve {name}\n"
            or db_after != db_before
            or config_after != config_before
        ):
            output_exists_failures.append(
                {
                    "case": name,
                    "fields": fields,
                    "content": output_path.read_text(encoding="utf-8"),
                    "db changed": db_after != db_before,
                    "config changed": config_after != config_before,
                }
            )

        assert cli.run([*base_args, "--out", str(output_path), "--overwrite"]) == 0
        overwrite_out = capsys.readouterr()
        if overwrite_out.err or output_path.read_text(encoding="utf-8") == f"preserve {name}\n":
            output_exists_failures.append({"case": f"{name} overwrite", "stdout": overwrite_out.out, "stderr": overwrite_out.err})

        directory_output_path = tmp_path / f"directory-output-{name}"
        directory_output_path.mkdir()
        db_before_directory = _database_snapshot(home)
        config_before_directory = (home / "config.toml").read_text(encoding="utf-8")
        directory_code = cli.run([*base_args, "--out", str(directory_output_path), "--overwrite"])
        directory = capsys.readouterr()
        directory_fields = assert_error(directory, expected_code="OUTPUT_EXISTS", expected_reason="output path already exists")
        db_after_directory = _database_snapshot(home)
        config_after_directory = (home / "config.toml").read_text(encoding="utf-8")
        if (
            directory_code != 2
            or not directory_output_path.is_dir()
            or any(directory_output_path.iterdir())
            or db_after_directory != db_before_directory
            or config_after_directory != config_before_directory
        ):
            directory_output_failures.append(
                {
                    "case": name,
                    "fields": directory_fields,
                    "is directory": directory_output_path.is_dir(),
                    "entries": sorted(path.name for path in directory_output_path.iterdir()) if directory_output_path.is_dir() else None,
                    "db changed": db_after_directory != db_before_directory,
                    "config changed": config_after_directory != config_before_directory,
                }
            )

    for name, base_args, _existing_output_path in export_cases:
        if name not in {"artifact", "log"}:
            continue
        output_path = tmp_path / f"missing-parent-{name}" / "export.out"
        db_before = _database_snapshot(home)
        config_before = (home / "config.toml").read_text(encoding="utf-8")
        code = cli.run([*base_args, "--out", str(output_path)])
        captured = capsys.readouterr()
        fields = assert_error(captured, expected_code="CONFIG_INVALID", expected_reason="output parent directory does not exist")
        db_after = _database_snapshot(home)
        config_after = (home / "config.toml").read_text(encoding="utf-8")
        if (
            code != 2
            or output_path.exists()
            or output_path.parent.exists()
            or db_after != db_before
            or config_after != config_before
        ):
            missing_parent_failures.append(
                {
                    "case": name,
                    "fields": fields,
                    "output exists": output_path.exists(),
                    "parent exists": output_path.parent.exists(),
                    "db changed": db_after != db_before,
                    "config changed": config_after != config_before,
                }
            )

    assert {
        "nonempty home": nonempty_home_err,
        "nonempty home entries": nonempty_home_entries,
        "initialized home db changed": initialized_db_after != initialized_db_before,
        "initialized home config changed": initialized_config_after != initialized_config_before,
        "initialized home": initialized_home_err,
        "output exists failures": output_exists_failures,
        "missing parent failures": missing_parent_failures,
        "directory output failures": directory_output_failures,
    } == {
        "nonempty home": {
            "object": "error",
            "message": "Command failed.",
            "error code": "HOME_EXISTS",
            "exit code": "2",
            "reason": "home exists and is not an initialized ALab home",
            "next": "none",
        },
        "nonempty home entries": ["unrelated.txt"],
        "initialized home db changed": False,
        "initialized home config changed": False,
        "initialized home": {
            "object": "error",
            "message": "Command failed.",
            "error code": "HOME_EXISTS",
            "exit code": "2",
            "reason": "ALab home is already initialized",
            "next": "none",
        },
        "output exists failures": [],
        "missing parent failures": [],
        "directory output failures": [],
    }


def test_alab_home_layout_and_markers_follow_blueprint(tmp_path: Path, monkeypatch, capsys) -> None:
    env_home = tmp_path / "env-home"
    explicit_home = tmp_path / "explicit-home"
    fake_user_home = tmp_path / "fake-user-home"
    monkeypatch.delenv("ALAB_HOME", raising=False)
    monkeypatch.setenv("HOME", str(fake_user_home))

    assert resolve_home().path == (fake_user_home / ".ALab").resolve()

    monkeypatch.setenv("ALAB_HOME", str(env_home))

    assert cli.run(["auth", "init"]) == 0
    env_fields = _output_field_map(capsys.readouterr().out)
    assert Path(env_fields["home"]) == env_home.resolve()

    assert cli.run(["--home", str(explicit_home), "auth", "init"]) == 0
    explicit_fields = _output_field_map(capsys.readouterr().out)
    root_key = explicit_fields["root key"]
    assert Path(explicit_fields["home"]) == explicit_home.resolve()

    for home, home_id in ((env_home, env_fields["home id"]), (explicit_home, explicit_fields["home id"])):
        _assert_entropy_id(home_id, "home")
        assert (home / "alab.db").is_file()
        assert (home / "config.toml").is_file()
        assert (home / "backups").is_dir()
        assert (home / "project-workspaces").is_dir()
        assert (home / "projects").is_dir()
        assert (home / "sources" / "skydiscover").is_dir()
        assert (home / "cache" / "docker-images").is_dir()
        assert (home / "cache" / "skydiscover-python-envs").is_dir()
        assert (home / "feedback").is_dir()
        assert (home / "tmp").is_dir()
        assert not (home / "records").exists()
        with sqlite3.connect(home / "alab.db") as conn:
            assert conn.execute("SELECT home_id FROM homes").fetchone()[0] == home_id

    assert env_fields["home id"] != explicit_fields["home id"]

    source = tmp_path / "layout-source"
    source.mkdir()
    (source / "main.py").write_text("print('layout source')\n", encoding="utf-8")
    config = tmp_path / "layout.toml"
    _write_local_project_config(
        config,
        name="Home Layout Contract",
        runner_command=[sys.executable, "-c", "print('layout baseline')"],
    )

    assert (
        cli.run(
            [
                "--home",
                str(explicit_home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
            ]
        )
        == 0
    )
    project_fields = _output_field_map(capsys.readouterr().out)
    project_id = project_fields["project id"]
    admin_key = project_fields["admin key"]

    project_root = explicit_home / "projects" / project_id
    assert (project_root / "repo.git").is_dir()
    assert (project_root / "artifacts" / "blobs").is_dir()
    assert (project_root / "artifacts" / "logs").is_dir()

    control_path = explicit_home / "project-workspaces" / project_id
    project_marker = json.loads((control_path / ".alab" / "context.json").read_text(encoding="utf-8"))
    assert project_marker["home_id"] == explicit_fields["home id"]
    assert project_marker["context_type"] == "project"
    assert project_marker["project_id"] == project_id
    assert not (control_path / "main.py").exists()

    experiment_cwd = tmp_path / "experiment-cwd"
    experiment_cwd.mkdir()
    monkeypatch.chdir(experiment_cwd)
    assert (
        cli.run(
            [
                "--home",
                str(explicit_home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "layout default path",
            ]
        )
        == 0
    )
    exp_fields = _output_field_map(capsys.readouterr().out)
    exp_id = exp_fields["exp id"]
    default_worktree = experiment_cwd / f"{project_id}_{exp_id}"
    exp_marker = json.loads((default_worktree / ".alab" / "context.json").read_text(encoding="utf-8"))
    assert exp_marker["home_id"] == explicit_fields["home id"]
    assert exp_marker["context_type"] == "experiment"
    assert exp_marker["project_id"] == project_id
    assert exp_marker["exp_id"] == exp_id
    assert not (explicit_home / f"{project_id}_{exp_id}").exists()


def test_feedback_submission_writes_file_record_with_session_and_git_metadata(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init"], repo)
    _git(["config", "user.name", "ALab Contract"], repo)
    _git(["config", "user.email", "alab-contract@example.test"], repo)
    _git(["config", "commit.gpgsign", "false"], repo)
    (repo / "tracked.txt").write_text("one\n", encoding="utf-8")
    _git(["add", "tracked.txt"], repo)
    _git(["commit", "-m", "initial"], repo)
    commit = _git(["rev-parse", "HEAD"], repo)
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("ALAB_SESSION_ID", "alab-session")
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "feedback",
                "--kind",
                "bug",
                "--title",
                "Bug report",
                "--body",
                "body text",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    fields, record_path, metadata = _feedback_record(captured.out)

    assert captured.err == ""
    assert _output_field_labels(captured.out) == [
        "object",
        "feedback id",
        "kind",
        "title",
        "created at",
        "role",
        "session id",
        "commit",
        "path",
        "metadata path",
        "body path",
    ]
    _assert_entropy_id(fields["feedback id"], "fb-bug")
    assert fields["kind"] == "bug"
    assert fields["title"] == "Bug report"
    assert fields["role"] == "none"
    assert fields["session id"] == "alab-session"
    assert fields["commit"] == commit
    assert record_path.parent == home / "feedback"
    assert (record_path / "body.md").read_text(encoding="utf-8") == "body text"
    assert metadata == {
        "schema_version": 1,
        "feedback_id": fields["feedback id"],
        "kind": "bug",
        "title": "Bug report",
        "created_at": fields["created at"],
        "role": "none",
        "actor_type": None,
        "actor_credential_id": None,
        "actor_project_id": None,
        "actor_exp_id": None,
        "token_mode": None,
        "context_type": None,
        "context_project_id": None,
        "context_exp_id": None,
        "context_token_id": None,
        "cwd": str(repo),
        "session_id": "alab-session",
        "session_source": "ALAB_SESSION_ID",
        "git_commit": commit,
        "git_dirty": True,
        "git_commit_source": "cwd",
        "alab_home": str(home.resolve()),
        "body_path": str(record_path / "body.md"),
    }


def test_feedback_body_file_non_git_and_missing_session_are_recorded_as_null(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    non_git = tmp_path / "non-git"
    non_git.mkdir()
    body_path = non_git / "feedback.md"
    body_path.write_text("file body\n", encoding="utf-8")
    for key in services.FEEDBACK_SESSION_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(non_git)

    assert cli.run(["--home", str(home), "feedback", "--body-file", "feedback.md"]) == 0
    captured = capsys.readouterr()
    fields, record_path, metadata = _feedback_record(captured.out)

    assert captured.err == ""
    assert fields["kind"] == "suggestion"
    assert fields["title"] == "none"
    assert fields["session id"] == "none"
    assert fields["commit"] == "none"
    assert (record_path / "body.md").read_text(encoding="utf-8") == "file body\n"
    assert metadata["session_id"] is None
    assert metadata["session_source"] is None
    assert metadata["git_commit"] is None
    assert metadata["git_dirty"] is None
    assert metadata["git_commit_source"] is None
    assert metadata["cwd"] == str(non_git)


def test_feedback_only_requires_initialized_home_not_valid_global_config(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    capsys.readouterr()
    (home / "config.toml").write_text("schema_version = 'not-an-int'\n", encoding="utf-8")
    monkeypatch.chdir(cwd)

    assert cli.run(["--home", str(home), "feedback", "--body", "config is broken"]) == 0
    captured = capsys.readouterr()
    fields, record_path, metadata = _feedback_record(captured.out)

    assert captured.err == ""
    assert fields["feedback id"] == metadata["feedback_id"]
    assert metadata["role"] == "none"
    assert metadata["cwd"] == str(cwd)
    assert (record_path / "body.md").read_text(encoding="utf-8") == "config is broken"


def test_feedback_experiment_context_does_not_require_token_file(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, _admin_key = _init_capability_project(tmp_path, capsys)
    project_path = home / "project-workspaces" / project_id
    monkeypatch.chdir(project_path)
    assert cli.run(["--home", str(home), "exp", "create", "--name", "tokenless feedback"]) == 0
    exp_fields = _output_field_map(capsys.readouterr().out)
    exp_id = exp_fields["exp id"]
    worktree_path = Path(exp_fields["worktree path"])
    (worktree_path / ".alab" / "token").unlink()
    monkeypatch.chdir(worktree_path)

    assert cli.run(["--home", str(home), "feedback", "--body", "missing token is allowed"]) == 0
    captured = capsys.readouterr()
    fields, record_path, metadata = _feedback_record(captured.out)

    assert captured.err == ""
    assert fields["role"] == "experiment"
    assert metadata["context_type"] == "experiment"
    assert metadata["context_project_id"] == project_id
    assert metadata["context_exp_id"] == exp_id
    assert metadata["actor_type"] is None
    assert (record_path / "body.md").read_text(encoding="utf-8") == "missing token is allowed"


def test_feedback_is_executable_from_all_context_roles(tmp_path: Path, monkeypatch, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.chdir(scratch)

    variants: list[tuple[str, list[str], str, dict[str, object | None]]] = [
        ("global", ["feedback", "--body", "global"], "none", {"context_type": None, "actor_type": None}),
        ("root", ["--key", root_key, "feedback", "--body", "root"], "root", {"context_type": None, "actor_type": "root"}),
        ("admin", ["--key", admin_key, "feedback", "--body", "admin"], "admin", {"context_type": None, "actor_type": "admin"}),
    ]
    project_path = home / "project-workspaces" / project_id
    monkeypatch.chdir(project_path)
    variants.append(("project", ["feedback", "--body", "project"], "project", {"context_type": "project", "actor_type": None}))

    assert cli.run(["--home", str(home), "exp", "create", "--name", "feedback role"]) == 0
    exp_fields = _output_field_map(capsys.readouterr().out)
    exp_id = exp_fields["exp id"]
    worktree_path = Path(exp_fields["worktree path"])
    worktree_token = (worktree_path / ".alab" / "token").read_text(encoding="utf-8").rstrip("\n")
    variants.append(
        (
            "token",
            ["--key", worktree_token, "feedback", "--body", "token"],
            "token:worktree",
            {"context_type": None, "actor_type": "token", "actor_exp_id": exp_id, "token_mode": "worktree"},
        )
    )
    monkeypatch.chdir(worktree_path)
    variants.append(
        (
            "experiment",
            ["feedback", "--body", "experiment"],
            "experiment",
            {"context_type": "experiment", "context_exp_id": exp_id, "actor_type": None},
        )
    )

    inspection_path = tmp_path / "feedback-inspection"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "checkout",
                exp_id,
                "--project",
                project_id,
                "--path",
                str(inspection_path),
                "--commit",
                "latest",
            ]
        )
        == 0
    )
    capsys.readouterr()
    monkeypatch.chdir(inspection_path)
    variants.append(
        (
            "inspection",
            ["feedback", "--body", "inspection"],
            "inspection",
            {"context_type": "inspection", "context_exp_id": exp_id, "actor_type": None},
        )
    )

    failures = []
    for variant_name, args, expected_role, expected_metadata in variants:
        if variant_name in {"global", "root", "admin", "token"}:
            monkeypatch.chdir(scratch)
        elif variant_name == "project":
            monkeypatch.chdir(project_path)
        elif variant_name == "experiment":
            monkeypatch.chdir(worktree_path)
        else:
            monkeypatch.chdir(inspection_path)
        assert cli.run(["--home", str(home), *args]) == 0
        captured = capsys.readouterr()
        fields, _record_path, metadata = _feedback_record(captured.out)
        observed = {
            "role": fields["role"],
            "context_type": metadata["context_type"],
            "context_project_id": metadata["context_project_id"],
            "context_exp_id": metadata["context_exp_id"],
            "actor_type": metadata["actor_type"],
            "actor_exp_id": metadata["actor_exp_id"],
            "token_mode": metadata["token_mode"],
        }
        expected = {
            "role": expected_role,
            "context_type": expected_metadata.get("context_type"),
            "context_project_id": project_id if expected_metadata.get("context_type") else None,
            "context_exp_id": expected_metadata.get("context_exp_id"),
            "actor_type": expected_metadata.get("actor_type"),
            "actor_exp_id": expected_metadata.get("actor_exp_id"),
            "token_mode": expected_metadata.get("token_mode"),
        }
        if captured.err or observed != expected:
            failures.append(
                {
                    "variant": variant_name,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "observed": observed,
                    "expected": expected,
                }
            )

    assert failures == []


def test_feedback_invalid_inputs_are_side_effect_free(tmp_path: Path, monkeypatch, capsys) -> None:
    uninitialized_home = tmp_path / "uninitialized-home"
    assert cli.run(["--home", str(uninitialized_home), "feedback", "--body", "before init"]) == 2
    uninitialized = capsys.readouterr()
    assert uninitialized.out == ""
    assert "error code: CONTEXT_NOT_FOUND" in uninitialized.err
    assert not uninitialized_home.exists()

    home = tmp_path / "home"
    sandbox = tmp_path / "feedback-inputs"
    sandbox.mkdir()
    body_file = sandbox / "body.txt"
    body_file.write_text("body\n", encoding="utf-8")
    bad_utf8 = sandbox / "bad.bin"
    bad_utf8.write_bytes(b"\xff")
    missing_file = sandbox / "missing.txt"
    long_body = "x" * 65537
    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(sandbox)

    cases = [
        (["feedback"], "feedback requires exactly one of --body or --body-file"),
        (["feedback", "--body", "x", "--body-file", "body.txt"], "feedback requires exactly one of --body or --body-file"),
        (["feedback", "--body", "x", "--body", "y"], "--body may be provided once"),
        (["feedback", "--body", ""], "feedback body must be non-empty"),
        (["feedback", "--body", long_body], "feedback body exceeds 65536 bytes"),
        (["feedback", "--body-file", str(missing_file)], "feedback body file not found"),
        (["feedback", "--body-file", str(sandbox)], "feedback body file is a directory"),
        (["feedback", "--body-file", str(bad_utf8)], "feedback body file must be UTF-8"),
        (["feedback", "--body", "x", "--kind", "invalid"], "--kind must be one of bug, other, question, suggestion"),
        (["feedback", "--body", "x", "--title", ""], "--title requires a non-empty value"),
        (["feedback", "--body", "x", "--unknown"], "unsupported option --unknown"),
        (["feedback", "extra", "--body", "x"], "feedback accepts no positional arguments"),
    ]
    failures = []
    for args, expected_reason in cases:
        before = sorted(path.name for path in (home / "feedback").iterdir())
        code = cli.run(["--home", str(home), *args])
        captured = capsys.readouterr()
        after = sorted(path.name for path in (home / "feedback").iterdir())
        if code != 2 or captured.out or expected_reason not in captured.err or before != after:
            failures.append(
                {
                    "args": args,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "before": before,
                    "after": after,
                }
            )

    assert failures == []


def test_context_marker_conflicts_are_strict_and_side_effect_free(tmp_path: Path, monkeypatch, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    control_path = home / "project-workspaces" / project_id
    marker_path = control_path / ".alab" / "context.json"
    original_marker_text = marker_path.read_text(encoding="utf-8")

    exp_path = tmp_path / "marker-conflict-exp"
    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "create", "--project", project_id, "--name", "marker conflict", "--path", str(exp_path)]) == 0
    capsys.readouterr()
    experiment_marker_text = (exp_path / ".alab" / "context.json").read_text(encoding="utf-8")

    def snapshot() -> tuple[list[tuple[str, str, str, str]], int]:
        with sqlite3.connect(home / "alab.db") as conn:
            registry_rows = conn.execute(
                """
                SELECT context_type, path, status, path_hash
                FROM path_registry
                WHERE project_id = ?
                ORDER BY context_type, path
                """,
                (project_id,),
            ).fetchall()
            repair_audits = conn.execute(
                "SELECT COUNT(*) FROM audit_events WHERE project_id = ? AND action = 'repair'",
                (project_id,),
            ).fetchone()[0]
        return registry_rows, repair_audits

    unchanged = snapshot()

    def assert_error(args: list[str], error_code: str, reason: str) -> None:
        assert cli.run(args) == error_exit_code(error_code)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert _output_field_labels(captured.err) == _error_field_labels()
        assert f"error code: {error_code}" in captured.err
        assert reason in captured.err
        assert snapshot() == unchanged

    symlink_path = tmp_path / "project-context-symlink"
    symlink_path.symlink_to(control_path, target_is_directory=True)
    assert cli.run(["--home", str(home), "context", "show", "--path", str(symlink_path)]) == 0
    symlink_show = capsys.readouterr()
    symlink_fields = _output_field_map(symlink_show.out)
    assert symlink_show.err == ""
    assert symlink_fields["resolved path"] == str(control_path)
    assert symlink_fields["registered"] == "true"
    assert symlink_fields["path status"] == "present"
    assert snapshot() == unchanged

    missing_marker = marker_path.with_suffix(".missing")
    marker_path.rename(missing_marker)
    assert_error(["--home", str(home), "context", "show", "--path", str(control_path)], "CONTEXT_NOT_FOUND", "context marker not found")
    assert_error(["--home", str(home), "--key", admin_key, "context", "repair", "--path", str(control_path)], "CONTEXT_NOT_FOUND", "context marker not found at --path")
    missing_marker.rename(marker_path)

    wrong_home_marker = json.loads(original_marker_text)
    wrong_home_marker["home_id"] = "home-other"
    marker_path.write_text(json.dumps(wrong_home_marker, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    assert_error(["--home", str(home), "context", "show", "--path", str(control_path)], "CONTEXT_CONFLICT", "context marker belongs to a different ALab home")
    assert_error(["--home", str(home), "--key", admin_key, "context", "repair", "--path", str(control_path)], "CONTEXT_CONFLICT", "context marker belongs to a different ALab home")
    marker_path.write_text(original_marker_text, encoding="utf-8")

    marker_path.write_text("{not json\n", encoding="utf-8")
    monkeypatch.chdir(control_path)
    assert_error(["--home", str(home), "status"], "CONTEXT_CONFLICT", "context marker is invalid JSON")
    monkeypatch.chdir(tmp_path)
    marker_path.write_text(original_marker_text, encoding="utf-8")

    marker_path.write_text(experiment_marker_text, encoding="utf-8")
    monkeypatch.chdir(control_path)
    assert_error(["--home", str(home), "status"], "CONTEXT_CONFLICT", "context marker and registry disagree")
    monkeypatch.chdir(tmp_path)
    marker_path.write_text(original_marker_text, encoding="utf-8")

    assert snapshot() == unchanged


def test_config_validate_object_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"

    assert cli.run(["--home", str(home), "config", "validate"]) == 0
    captured = capsys.readouterr()
    blocks = _output_blocks(captured.out)

    assert {
        "stderr": captured.err,
        "object types": [_output_field_map(block).get("object") for block in blocks],
        "config labels": _output_field_labels(blocks[0]) if blocks else [],
        "capability labels": _output_field_labels(blocks[1]) if len(blocks) > 1 else [],
    } == {
        "stderr": "",
        "object types": ["config", "capability"],
        "config labels": _documented_success_labels_for_object("config validate", "config"),
        "capability labels": _documented_success_labels_for_object("config validate", "capability"),
    }


def test_auth_root_regenerate_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    init_fields = _output_field_map(capsys.readouterr().out)
    old_root_key = init_fields["root key"]

    assert cli.run(["--home", str(home), "--key", old_root_key, "auth", "root", "regenerate"]) == 0
    regenerated = capsys.readouterr()
    regenerated_fields = _output_field_map(regenerated.out)
    new_root_key = regenerated_fields["root key"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                new_root_key,
                "audit",
                "list",
                "--object-type",
                "credential",
                "--object-id",
                regenerated_fields["created key id"],
                "--action",
                "regenerate",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", new_root_key, "audit", "show", audit_id]) == 0
    audit_out = capsys.readouterr()
    audit_fields = _output_field_map(audit_out.out)
    audit_metadata = json.loads(audit_fields["sanitized metadata"])

    assert {
        "stderr": regenerated.err,
        "labels": _output_field_labels(regenerated.out),
        "old raw key hidden": old_root_key not in regenerated.out,
        "new raw key changed": new_root_key != old_root_key,
        "new raw key count": regenerated.out.count(new_root_key),
        "revoked key id rendered": regenerated_fields.get("revoked key id", "").startswith("cred-"),
        "audit": (
            audit_out.err,
            _output_field_labels(audit_out.out),
            audit_fields.get("audit id"),
            audit_fields.get("action"),
            audit_fields.get("object type"),
            audit_fields.get("object id"),
            audit_metadata,
        ),
    } == {
        "stderr": "",
        "labels": _documented_success_labels("auth root regenerate"),
        "old raw key hidden": True,
        "new raw key changed": True,
        "new raw key count": 1,
        "revoked key id rendered": True,
        "audit": (
            "",
            _documented_success_labels("audit show"),
            audit_id,
            "regenerate",
            "credential",
            regenerated_fields["created key id"],
            {
                "created_credential_id": regenerated_fields["created key id"],
                "credential_type": "root",
                "revoked_at": audit_metadata["revoked_at"],
                "revoked_credential_id": regenerated_fields["revoked key id"],
                "schema_version": 1,
            },
        ),
    }


def test_one_time_raw_key_outputs_follow_cli_secret_rules(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    source.mkdir()
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Raw Key Contract"
task = "Keep raw credential output constrained"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    auth_init = capsys.readouterr()
    root_key = _output_field_map(auth_init.out)["root key"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    project_init = capsys.readouterr()
    project_fields = _output_field_map(project_init.out)
    project_id = project_fields["project id"]
    initial_admin_key = project_fields["admin key"]

    assert cli.run(["--home", str(home), "--key", root_key, "key", "create", "--project", project_id]) == 0
    key_create = capsys.readouterr()
    created_admin_key = _output_field_map(key_create.out)["admin key"]

    assert {
        "auth init root key count": auth_init.out.count(root_key),
        "project init admin key count": project_init.out.count(initial_admin_key),
        "project init root key hidden": root_key not in project_init.out,
        "key create admin key count": key_create.out.count(created_admin_key),
        "key create root key hidden": root_key not in key_create.out,
        "key create prior admin key hidden": initial_admin_key not in key_create.out,
        "distinct admin keys": created_admin_key != initial_admin_key,
    } == {
        "auth init root key count": 1,
        "project init admin key count": 1,
        "project init root key hidden": True,
        "key create admin key count": 1,
        "key create root key hidden": True,
        "key create prior admin key hidden": True,
        "distinct admin keys": True,
    }


def test_project_read_command_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    source.mkdir()
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Project Field Contract"
task = "Exercise project success-field contracts"
goal = "Keep project read output aligned with the CLI spec"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[env]
ALAB_CONTRACT_ENV = "visible"

[secret_env]
ALAB_CONTRACT_SECRET = "abcd"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    init_out = capsys.readouterr()
    init_fields = _output_field_map(init_out.out)
    project_id = init_fields["project id"]
    admin_key = init_fields["admin key"]
    source_id = init_fields["source id"]
    control_path = home / "project-workspaces" / project_id

    assert cli.run(["--home", str(home), "--key", root_key, "project", "list", "--include-archived"]) == 0
    list_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", root_key, "project", "show", "--project", project_id]) == 0
    show_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "project", "config", "show", "--project", project_id]) == 0
    config_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "source", "list", "--project", project_id]) == 0
    source_list_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "source", "show", source_id, "--project", project_id]) == 0
    source_show_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "context", "show", "--path", str(control_path)]) == 0
    context_show_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "context", "repair", "--path", str(control_path)]) == 0
    context_repair_out = capsys.readouterr()

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "project",
                "--object-id",
                project_id,
                "--action",
                "repair",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    context_repair_audit_list_out = capsys.readouterr()
    context_repair_audit_id = _output_field_map(context_repair_audit_list_out.out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", context_repair_audit_id, "--project", project_id]) == 0
    context_repair_audit_show_out = capsys.readouterr()
    context_repair_audit_fields = _output_field_map(context_repair_audit_show_out.out)
    context_repair_audit_metadata = json.loads(context_repair_audit_fields["sanitized metadata"])

    assert {
        "project init": (init_out.err, _output_field_labels(init_out.out), _documented_success_labels("project init", omit={"warning code"})),
        "project list": (list_out.err, _output_field_labels(list_out.out), _documented_success_labels("project list")),
        "project show": (show_out.err, _output_field_labels(show_out.out), _documented_success_labels("project show")),
        "project config show": (config_out.err, _output_field_labels(config_out.out), _documented_success_labels("project config show")),
        "source list": (source_list_out.err, _output_field_labels(source_list_out.out), _documented_success_labels("source list")),
        "source show": (source_show_out.err, _output_field_labels(source_show_out.out), _documented_success_labels("source show")),
        "context show": (context_show_out.err, _output_field_labels(context_show_out.out), _documented_success_labels("context show")),
        "context repair": (context_repair_out.err, _output_field_labels(context_repair_out.out), _documented_success_labels("context repair")),
        "context repair audit list": (
            context_repair_audit_list_out.err,
            _output_field_labels(context_repair_audit_list_out.out),
            _documented_success_labels("audit list"),
            _output_field_map(context_repair_audit_list_out.out).get("action"),
            _output_field_map(context_repair_audit_list_out.out).get("object type"),
            _output_field_map(context_repair_audit_list_out.out).get("object id"),
        ),
        "context repair audit show": (
            context_repair_audit_show_out.err,
            _output_field_labels(context_repair_audit_show_out.out),
            _documented_success_labels("audit show"),
            context_repair_audit_fields.get("audit id"),
            context_repair_audit_fields.get("action"),
            context_repair_audit_fields.get("object type"),
            context_repair_audit_fields.get("object id"),
            str(control_path) in context_repair_audit_show_out.out,
            root_key in context_repair_audit_show_out.out,
            admin_key in context_repair_audit_show_out.out,
            context_repair_audit_metadata["previous_path_hash"] == context_repair_audit_metadata["repaired_path_hash"],
            context_repair_audit_metadata,
        ),
    } == {
        "project init": ("", _documented_success_labels("project init", omit={"warning code"}), _documented_success_labels("project init", omit={"warning code"})),
        "project list": ("", _documented_success_labels("project list"), _documented_success_labels("project list")),
        "project show": ("", _documented_success_labels("project show"), _documented_success_labels("project show")),
        "project config show": ("", _documented_success_labels("project config show"), _documented_success_labels("project config show")),
        "source list": ("", _documented_success_labels("source list"), _documented_success_labels("source list")),
        "source show": ("", _documented_success_labels("source show"), _documented_success_labels("source show")),
        "context show": ("", _documented_success_labels("context show"), _documented_success_labels("context show")),
        "context repair": ("", _documented_success_labels("context repair"), _documented_success_labels("context repair")),
        "context repair audit list": (
            "",
            _documented_success_labels("audit list"),
            _documented_success_labels("audit list"),
            "repair",
            "project",
            project_id,
        ),
        "context repair audit show": (
            "",
            _documented_success_labels("audit show"),
            _documented_success_labels("audit show"),
            context_repair_audit_id,
            "repair",
            "project",
            project_id,
            False,
            False,
            False,
            True,
            {
                "context_type": "project",
                "created_registry_row": False,
                "path_registry_id": context_repair_audit_metadata["path_registry_id"],
                "previous_path_hash": context_repair_audit_metadata["previous_path_hash"],
                "repair_mode": "admin",
                "repaired_at": context_repair_audit_metadata["repaired_at"],
                "repaired_path_hash": context_repair_audit_metadata["repaired_path_hash"],
                "schema_version": 1,
            },
        ),
    }


def test_project_context_repair_accepts_ambient_admin_key(tmp_path: Path, monkeypatch, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    control_path = home / "project-workspaces" / project_id

    monkeypatch.setenv("ALAB_KEY", admin_key)
    assert cli.run(["--home", str(home), "context", "repair", "--path", str(control_path)]) == 0
    repair_out = capsys.readouterr().out
    repair_fields = _output_field_map(repair_out)

    with sqlite3.connect(home / "alab.db") as conn:
        audit_row = conn.execute(
            """
            SELECT actor_type, metadata_json
            FROM audit_events
            WHERE action = 'repair' AND object_type = 'project' AND object_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
    audit_metadata = json.loads(audit_row[1]) if audit_row else {}

    assert {
        "labels": _output_field_labels(repair_out),
        "repair mode": repair_fields.get("repair mode"),
        "actor type": audit_row[0] if audit_row else None,
        "audit repair mode": audit_metadata.get("repair_mode"),
        "context type": audit_metadata.get("context_type"),
    } == {
        "labels": _documented_success_labels("context repair"),
        "repair mode": "admin",
        "actor type": "admin",
        "audit repair mode": "admin",
        "context type": "project",
    }


def test_project_init_mode_variants_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    git_source = tmp_path / "git-source"
    _init_catalog_upstream(git_source)

    def write_config(path: Path, name: str) -> None:
        path.write_text(
            f"""
schema_version = 1

[project]
name = {json.dumps(name)}
task = "Exercise project init mode contracts"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
            + "\n",
            encoding="utf-8",
        )

    empty_config = tmp_path / "empty.project.toml"
    git_config = tmp_path / "git.project.toml"
    write_config(empty_config, "Empty Init Contract")
    write_config(git_config, "Git Init Contract")

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "empty",
                "--config",
                str(empty_config),
                "--source-empty",
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    empty_out = capsys.readouterr()
    empty_fields = _output_field_map(empty_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "git",
                "--config",
                str(git_config),
                "--source-git",
                str(git_source),
                "--git-ref",
                "main",
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    git_out = capsys.readouterr()
    git_fields = _output_field_map(git_out.out)

    expected_labels = _documented_success_labels("project init", omit={"warning code"})
    assert {
        "empty": (
            empty_out.err,
            _output_field_labels(empty_out.out),
            empty_fields.get("project name"),
            empty_fields.get("validation status"),
            empty_out.out.count(empty_fields["admin key"]),
            root_key in empty_out.out,
        ),
        "git": (
            git_out.err,
            _output_field_labels(git_out.out),
            git_fields.get("project name"),
            git_fields.get("validation status"),
            git_out.out.count(git_fields["admin key"]),
            root_key in git_out.out,
        ),
    } == {
        "empty": ("", expected_labels, "Empty Init Contract", "skipped", 1, False),
        "git": ("", expected_labels, "Git Init Contract", "skipped", 1, False),
    }


def test_project_init_adapter_mode_variants_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    harbor_task = tmp_path / "harbor-task"
    harbor_starter = harbor_task / "starter"
    harbor_starter.mkdir(parents=True)
    (harbor_starter / "main.py").write_text("print('harbor starter')\n", encoding="utf-8")
    (harbor_task / "tests").mkdir()
    (harbor_task / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (harbor_task / "instruction.md").write_text("Adapter init contract\n", encoding="utf-8")
    (harbor_task / "task.toml").write_text(
        """
source = "starter"

[environment]
image = "harbor-env:latest"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    skydiscover_upstream = tmp_path / "skydiscover-upstream"
    benchmark = skydiscover_upstream / "benchmarks" / "contract-demo"
    skydiscover_starter = benchmark / "starter"
    skydiscover_starter.mkdir(parents=True)
    (skydiscover_starter / "main.py").write_text("print('skydiscover starter')\n", encoding="utf-8")
    (benchmark / "evaluator.py").write_text("def evaluate(program_path):\n    return {'combined_score': 1}\n", encoding="utf-8")
    (benchmark / "benchmark.toml").write_text('initial_program = "starter"\n', encoding="utf-8")
    _git(["init"], skydiscover_upstream)
    _git(["config", "user.name", "ALab Contract"], skydiscover_upstream)
    _git(["config", "user.email", "alab-contract@example.test"], skydiscover_upstream)
    _git(["config", "commit.gpgsign", "false"], skydiscover_upstream)
    _git(["add", "."], skydiscover_upstream)
    _git(["commit", "-m", "catalog"], skydiscover_upstream)
    _git(["branch", "-M", "main"], skydiscover_upstream)

    harbor_config = tmp_path / "harbor.project.toml"
    harbor_config.write_text(
        f"""
schema_version = 1

[project]
name = "Harbor Init Contract"
task = ""

[runner]
type = "harbor"
timeout_seconds = 30
working_directory = "."
harbor_task_ref = {json.dumps(str(harbor_task))}

[reward]
type = "harbor"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    skydiscover_config = tmp_path / "skydiscover.project.toml"
    skydiscover_config.write_text(
        """
schema_version = 1

[project]
name = "SkyDiscover Init Contract"
task = "Import initial program"

[runner]
type = "skydiscover_python"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/contract-demo"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "harbor",
                "--config",
                str(harbor_config),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    harbor_out = capsys.readouterr()
    harbor_fields = _output_field_map(harbor_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "catalog",
                "skydiscover",
                "add",
                "--origin-url",
                str(skydiscover_upstream),
                "--ref",
                "main",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "skydiscover",
                "--config",
                str(skydiscover_config),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    skydiscover_out = capsys.readouterr()
    skydiscover_fields = _output_field_map(skydiscover_out.out)

    expected_labels = _documented_success_labels("project init", omit={"warning code"})
    assert {
        "harbor": (
            harbor_out.err,
            _output_field_labels(harbor_out.out),
            harbor_fields.get("project name"),
            harbor_fields.get("validation status"),
            harbor_out.out.count(harbor_fields["admin key"]),
            root_key in harbor_out.out,
        ),
        "skydiscover": (
            skydiscover_out.err,
            _output_field_labels(skydiscover_out.out),
            skydiscover_fields.get("project name"),
            skydiscover_fields.get("validation status"),
            skydiscover_out.out.count(skydiscover_fields["admin key"]),
            root_key in skydiscover_out.out,
        ),
    } == {
        "harbor": ("", expected_labels, "Harbor Init Contract", "skipped", 1, False),
        "skydiscover": ("", expected_labels, "SkyDiscover Init Contract", "skipped", 1, False),
    }


def test_project_init_skydiscover_accepts_local_evaluator_ref_without_catalog(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    evaluator = tmp_path / "evaluator"
    source.mkdir()
    evaluator.mkdir()
    (source / "solution.py").write_text("def build_route(cities):\n    return list(range(len(cities)))\n", encoding="utf-8")
    (evaluator / "evaluator.py").write_text(
        "def evaluate(program_path):\n    return {'combined_score': 1.0}\n",
        encoding="utf-8",
    )
    config = tmp_path / "skydiscover-local-evaluator.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "SkyDiscover Local Evaluator Init Contract"
task = "Use a local evaluator ref"

[runner]
type = "skydiscover_python"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = {json.dumps(str(evaluator))}
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "skydiscover",
                "--config",
                str(config),
                "--source-path",
                str(source),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    out = capsys.readouterr()
    fields = _output_field_map(out.out)

    assert out.err == ""
    assert fields["project name"] == "SkyDiscover Local Evaluator Init Contract"
    assert fields["validation status"] == "skipped"


def test_project_config_show_export_never_render_raw_secret_values(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    export_path = tmp_path / "exported-retain.toml"
    raw_secret = "contract-secret-value"
    source.mkdir()
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Config Secret Contract"
task = "Keep project config reads secret-safe"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[env]
VISIBLE_ENV = "visible"

[secret_env]
CONTRACT_SECRET = {json.dumps(raw_secret)}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    project_fields = _output_field_map(capsys.readouterr().out)
    project_id = project_fields["project id"]
    admin_key = project_fields["admin key"]

    assert cli.run(["--home", str(home), "--key", admin_key, "project", "config", "show", "--project", project_id]) == 0
    show_out = capsys.readouterr()

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "config",
                "export",
                "--project",
                project_id,
                "--out",
                str(export_path),
            ]
        )
        == 0
    )
    export_out = capsys.readouterr()
    export_text = export_path.read_text(encoding="utf-8")

    assert {
        "show labels": _output_field_labels(show_out.out),
        "export labels": _output_field_labels(export_out.out),
        "show raw secret hidden": raw_secret not in show_out.out,
        "export stdout raw secret hidden": raw_secret not in export_out.out,
        "export file raw secret hidden": raw_secret not in export_text,
        "secret name visible": "secret name: CONTRACT_SECRET" in show_out.out,
        "fingerprint visible": "secret fingerprint: hmac-sha256:" in show_out.out,
        "retain marker exported": "retain = true" in export_text,
        "fingerprint exported": "fingerprint = \"hmac-sha256:" in export_text,
    } == {
        "show labels": _documented_success_labels("project config show"),
        "export labels": _documented_success_labels("project config export"),
        "show raw secret hidden": True,
        "export stdout raw secret hidden": True,
        "export file raw secret hidden": True,
        "secret name visible": True,
        "fingerprint visible": True,
        "retain marker exported": True,
        "fingerprint exported": True,
    }


def test_project_lifecycle_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)

    assert cli.run(["--home", str(home), "--key", admin_key, "project", "archive", "--project", project_id]) == 0
    archive_out = capsys.readouterr()
    archive_fields = _output_field_map(archive_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "project",
                "--object-id",
                project_id,
                "--action",
                "archive",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    archive_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", archive_audit_id, "--project", project_id]) == 0
    archive_audit_out = capsys.readouterr()
    archive_audit_fields = _output_field_map(archive_audit_out.out)
    archive_audit_meta = json.loads(archive_audit_fields["sanitized metadata"])

    assert cli.run(["--home", str(home), "--key", admin_key, "project", "unarchive", "--project", project_id]) == 0
    unarchive_out = capsys.readouterr()
    unarchive_fields = _output_field_map(unarchive_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "project",
                "--object-id",
                project_id,
                "--action",
                "unarchive",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    unarchive_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", unarchive_audit_id, "--project", project_id]) == 0
    unarchive_audit_out = capsys.readouterr()
    unarchive_audit_fields = _output_field_map(unarchive_audit_out.out)
    unarchive_audit_meta = json.loads(unarchive_audit_fields["sanitized metadata"])

    assert cli.run(["--home", str(home), "--key", admin_key, "project", "archive", "--project", project_id]) == 0
    capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--dry-run", "--cascade"]) == 0
    dry_run_out = capsys.readouterr()
    dry_run_fields = _output_field_map(dry_run_out.out)
    filesystem_path_count = int(dry_run_fields["deleted filesystem paths"])

    assert {
        "archive": (
            archive_out.err,
            _output_field_labels(archive_out.out),
            archive_fields.get("project id"),
            archive_fields.get("previous status"),
            archive_fields.get("project status"),
            archive_fields.get("archived at") == "none",
        ),
        "unarchive": (
            unarchive_out.err,
            _output_field_labels(unarchive_out.out),
            unarchive_fields.get("project id"),
            unarchive_fields.get("previous status"),
            unarchive_fields.get("project status"),
            unarchive_fields.get("unarchived at") == "none",
        ),
        "dry-run remove": (
            dry_run_out.err,
            _output_field_labels(dry_run_out.out),
            dry_run_fields.get("project id"),
            dry_run_fields.get("dry run"),
            dry_run_fields.get("removed"),
            dry_run_fields.get("cascade"),
            dry_run_fields.get("audit id"),
            dry_run_fields.get("deleted sources"),
        ),
        "archive audit": (
            archive_audit_out.err,
            _output_field_labels(archive_audit_out.out),
            archive_audit_fields.get("audit id"),
            archive_audit_fields.get("action"),
            archive_audit_fields.get("object type"),
            archive_audit_fields.get("object id"),
            archive_audit_fields.get("cascade"),
            archive_audit_fields.get("reason"),
            archive_audit_meta,
        ),
        "unarchive audit": (
            unarchive_audit_out.err,
            _output_field_labels(unarchive_audit_out.out),
            unarchive_audit_fields.get("audit id"),
            unarchive_audit_fields.get("action"),
            unarchive_audit_fields.get("object type"),
            unarchive_audit_fields.get("object id"),
            unarchive_audit_fields.get("cascade"),
            unarchive_audit_fields.get("reason"),
            unarchive_audit_meta,
        ),
    } == {
        "archive": (
            "",
            _documented_success_labels("project archive"),
            project_id,
            "valid",
            "archived",
            False,
        ),
        "unarchive": (
            "",
            _documented_success_labels("project unarchive"),
            project_id,
            "archived",
            "valid",
            False,
        ),
        "dry-run remove": (
            "",
            _documented_success_labels_with_repeats(
                "project remove",
                repeats={"filesystem path": filesystem_path_count, "planned trash move": filesystem_path_count},
                omit={"blocker", "trash cleanup pending"},
            ),
            project_id,
            "true",
            "false",
            "true",
            "none",
            "1",
        ),
        "archive audit": (
            "",
            _documented_success_labels("audit show"),
            archive_audit_id,
            "archive",
            "project",
            project_id,
            "false",
            "none",
            {
                "archived_at": archive_fields["archived at"],
                "previous_status": "valid",
                "project_status": "archived",
                "schema_version": 1,
            },
        ),
        "unarchive audit": (
            "",
            _documented_success_labels("audit show"),
            unarchive_audit_id,
            "unarchive",
            "project",
            project_id,
            "false",
            "none",
            {
                "previous_status": "archived",
                "project_status": "valid",
                "schema_version": 1,
                "unarchived_at": unarchive_fields["unarchived at"],
            },
        ),
    }


def test_source_lifecycle_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "source",
                "import",
                "--project",
                project_id,
                "--source-empty",
                "--name",
                "contract-empty-source",
            ]
        )
        == 0
    )
    import_out = capsys.readouterr()
    import_fields = _output_field_map(import_out.out)
    source_id = import_fields["source id"]
    source_ref = import_fields["source ref"]

    assert cli.run(["--home", str(home), "--key", admin_key, "source", "archive", source_id, "--project", project_id]) == 0
    archive_out = capsys.readouterr()
    archive_fields = _output_field_map(archive_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "source",
                "--object-id",
                source_id,
                "--action",
                "archive",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    archive_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", archive_audit_id, "--project", project_id]) == 0
    archive_audit_out = capsys.readouterr()
    archive_audit_fields = _output_field_map(archive_audit_out.out)
    archive_audit_metadata = json.loads(archive_audit_fields["sanitized metadata"])

    assert cli.run(["--home", str(home), "--key", admin_key, "source", "unarchive", source_id, "--project", project_id]) == 0
    unarchive_out = capsys.readouterr()
    unarchive_fields = _output_field_map(unarchive_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "source",
                "--object-id",
                source_id,
                "--action",
                "unarchive",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    unarchive_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", unarchive_audit_id, "--project", project_id]) == 0
    unarchive_audit_out = capsys.readouterr()
    unarchive_audit_fields = _output_field_map(unarchive_audit_out.out)
    unarchive_audit_metadata = json.loads(unarchive_audit_fields["sanitized metadata"])

    assert cli.run(["--home", str(home), "--key", admin_key, "source", "archive", source_id, "--project", project_id]) == 0
    capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--dry-run"]) == 0
    remove_out = capsys.readouterr()
    remove_fields = _output_field_map(remove_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "source",
                "remove",
                source_id,
                "--project",
                project_id,
                "--force",
                "--confirm",
                source_id,
            ]
        )
        == 0
    )
    actual_remove_out = capsys.readouterr()
    actual_remove_fields = _output_field_map(actual_remove_out.out)
    with sqlite3.connect(home / "alab.db") as conn:
        remaining_sources = conn.execute("SELECT COUNT(*) FROM sources WHERE source_id = ?", (source_id,)).fetchone()[0]

    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", actual_remove_fields["audit id"], "--project", project_id]) == 0
    audit_out = capsys.readouterr()
    audit_fields = _output_field_map(audit_out.out)

    assert {
        "source import": (
            import_out.err,
            _output_field_labels(import_out.out),
        ),
        "source archive": (
            archive_out.err,
            _output_field_labels(archive_out.out),
            archive_fields.get("previous status"),
            archive_fields.get("source status"),
            archive_fields.get("archived at") == "none",
        ),
        "source unarchive": (
            unarchive_out.err,
            _output_field_labels(unarchive_out.out),
            unarchive_fields.get("previous status"),
            unarchive_fields.get("source status"),
            unarchive_fields.get("unarchived at") == "none",
        ),
        "source archive audit": (
            archive_audit_out.err,
            _output_field_labels(archive_audit_out.out),
            archive_audit_fields.get("audit id"),
            archive_audit_fields.get("action"),
            archive_audit_fields.get("object type"),
            archive_audit_fields.get("object id"),
            archive_audit_metadata,
        ),
        "source unarchive audit": (
            unarchive_audit_out.err,
            _output_field_labels(unarchive_audit_out.out),
            unarchive_audit_fields.get("audit id"),
            unarchive_audit_fields.get("action"),
            unarchive_audit_fields.get("object type"),
            unarchive_audit_fields.get("object id"),
            unarchive_audit_metadata,
        ),
        "source remove": (
            remove_out.err,
            _output_field_labels(remove_out.out),
            remove_fields.get("dry run"),
            remove_fields.get("removed"),
            remove_fields.get("cascade"),
            remove_fields.get("audit id"),
        ),
        "source actual remove": (
            actual_remove_out.err,
            _output_field_labels(actual_remove_out.out),
            actual_remove_fields.get("dry run"),
            actual_remove_fields.get("removed"),
            actual_remove_fields.get("cascade"),
            actual_remove_fields.get("audit id") == "none",
            remaining_sources,
        ),
        "source remove audit": (
            audit_out.err,
            _output_field_labels(audit_out.out),
            audit_fields.get("audit id"),
            audit_fields.get("action"),
            audit_fields.get("object type"),
            audit_fields.get("object id"),
            audit_fields.get("cascade"),
            audit_fields.get("reason"),
            source_ref in audit_fields.get("sanitized metadata", ""),
            "branch_ref_commit" in audit_fields.get("sanitized metadata", ""),
            "branch_ref_deleted" in audit_fields.get("sanitized metadata", ""),
        ),
    } == {
        "source import": (
            "",
            _documented_success_labels("source import", omit={"warning"}),
        ),
        "source archive": (
            "",
            _documented_success_labels("source archive"),
            "active",
            "archived",
            False,
        ),
        "source unarchive": (
            "",
            _documented_success_labels("source unarchive"),
            "archived",
            "active",
            False,
        ),
        "source archive audit": (
            "",
            _documented_success_labels("audit show"),
            archive_audit_id,
            "archive",
            "source",
            source_id,
            {
                "archived_at": archive_fields["archived at"],
                "previous_status": "active",
                "schema_version": 1,
                "source_status": "archived",
            },
        ),
        "source unarchive audit": (
            "",
            _documented_success_labels("audit show"),
            unarchive_audit_id,
            "unarchive",
            "source",
            source_id,
            {
                "previous_status": "archived",
                "schema_version": 1,
                "source_status": "active",
                "unarchived_at": unarchive_fields["unarchived at"],
            },
        ),
        "source remove": (
            "",
            _documented_success_labels("source remove", omit={"blocker"}),
            "true",
            "false",
            "false",
            "none",
        ),
        "source actual remove": (
            "",
            _documented_success_labels("source remove", omit={"blocker"}),
            "false",
            "true",
            "false",
            False,
            0,
        ),
        "source remove audit": (
            "",
            _documented_success_labels("audit show"),
            actual_remove_fields["audit id"],
            "remove",
            "source",
            source_id,
            "false",
            "none",
            True,
            True,
            True,
        ),
    }


def test_source_import_origin_variants_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    local_source = tmp_path / "local-source"
    local_source.mkdir()
    (local_source / "local.py").write_text("print('local source')\n", encoding="utf-8")
    git_source = tmp_path / "git-source"
    _init_catalog_upstream(git_source)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "source",
                "import",
                "--project",
                project_id,
                "--source-path",
                str(local_source),
                "--name",
                "contract-local-source",
            ]
        )
        == 0
    )
    local_out = capsys.readouterr()
    local_fields = _output_field_map(local_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "source",
                "import",
                "--project",
                project_id,
                "--source-git",
                str(git_source),
                "--git-ref",
                "main",
                "--name",
                "contract-git-source",
            ]
        )
        == 0
    )
    git_out = capsys.readouterr()
    git_fields = _output_field_map(git_out.out)

    expected_labels = _documented_success_labels("source import", omit={"warning"})
    assert {
        "local": (
            local_out.err,
            _output_field_labels(local_out.out),
            local_fields.get("project id"),
            local_fields.get("source name"),
            local_fields.get("source ref", "").startswith("alab/source/"),
            local_fields.get("deduped"),
        ),
        "git": (
            git_out.err,
            _output_field_labels(git_out.out),
            git_fields.get("project id"),
            git_fields.get("source name"),
            git_fields.get("source ref", "").startswith("alab/source/"),
            git_fields.get("deduped"),
        ),
    } == {
        "local": ("", expected_labels, project_id, "contract-local-source", True, "false"),
        "git": ("", expected_labels, project_id, "contract-git-source", True, "false"),
    }


def test_source_import_warning_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    filtered_source = tmp_path / "filtered-source"
    filtered_source.mkdir()
    (filtered_source / ".env").write_text("SECRET=filtered\n", encoding="utf-8")

    tracked_sensitive_source = tmp_path / "tracked-sensitive-source"
    tracked_sensitive_source.mkdir()
    _git(["init"], tracked_sensitive_source)
    _git(["config", "user.name", "ALab Contract"], tracked_sensitive_source)
    _git(["config", "user.email", "alab-contract@example.test"], tracked_sensitive_source)
    _git(["config", "commit.gpgsign", "false"], tracked_sensitive_source)
    (tracked_sensitive_source / ".env").write_text("SECRET=tracked\n", encoding="utf-8")
    _git(["add", ".env"], tracked_sensitive_source)
    _git(["commit", "-m", "tracked-sensitive"], tracked_sensitive_source)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "source",
                "import",
                "--project",
                project_id,
                "--source-path",
                str(filtered_source),
                "--name",
                "contract-filtered-source",
            ]
        )
        == 0
    )
    filtered_out = capsys.readouterr()
    filtered_fields = _output_field_map(filtered_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "source",
                "import",
                "--project",
                project_id,
                "--source-path",
                str(tracked_sensitive_source),
                "--name",
                "contract-tracked-sensitive-source",
            ]
        )
        == 0
    )
    tracked_out = capsys.readouterr()
    tracked_fields = _output_field_map(tracked_out.out)

    expected_labels = _documented_success_labels("source import")
    assert {
        "filtered": (
            filtered_out.err,
            _output_field_labels(filtered_out.out),
            filtered_fields.get("source name"),
            filtered_fields.get("deduped"),
            filtered_fields.get("warning"),
        ),
        "tracked": (
            tracked_out.err,
            _output_field_labels(tracked_out.out),
            tracked_fields.get("source name"),
            tracked_fields.get("deduped"),
            tracked_fields.get("warning"),
        ),
    } == {
        "filtered": ("", expected_labels, "contract-filtered-source", "false", "SOURCE_EMPTY_AFTER_FILTER"),
        "tracked": ("", expected_labels, "contract-tracked-sensitive-source", "false", "TRACKED_SENSITIVE_SOURCE_FILE"),
    }


def test_catalog_skydiscover_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    first_commit = _init_catalog_upstream(upstream)

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "catalog",
                "skydiscover",
                "add",
                "--origin-url",
                str(upstream),
                "--ref",
                "main",
            ]
        )
        == 0
    )
    add_out = capsys.readouterr()
    add_fields = _output_field_map(add_out.out)

    assert cli.run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "show"]) == 0
    show_out = capsys.readouterr()
    show_fields = _output_field_map(show_out.out)

    (upstream / "README.md").write_text("two\n", encoding="utf-8")
    _git(["add", "README.md"], upstream)
    _git(["commit", "-m", "two"], upstream)
    second_commit = _git(["rev-parse", "HEAD"], upstream)

    assert cli.run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "update", "--ref", "main"]) == 0
    update_out = capsys.readouterr()
    update_fields = _output_field_map(update_out.out)
    with sqlite3.connect(home / "alab.db") as conn:
        catalog_metadata = json.loads(
            conn.execute(
                "SELECT metadata_json FROM catalogs WHERE catalog_key = 'skydiscover'",
            ).fetchone()[0]
        )

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "catalog",
                "skydiscover",
                "remove",
                "--force",
                "--confirm",
                "skydiscover",
            ]
        )
        == 0
    )
    remove_out = capsys.readouterr()
    remove_fields = _output_field_map(remove_out.out)

    assert {
        "catalog add": (
            add_out.err,
            _output_field_labels(add_out.out),
            add_fields.get("catalog"),
            add_fields.get("origin url"),
            add_fields.get("requested ref"),
            add_fields.get("pinned commit"),
            add_fields.get("status"),
            add_fields.get("audit id") == "none",
        ),
        "catalog show": (
            show_out.err,
            _output_field_labels(show_out.out),
            show_fields.get("catalog"),
            show_fields.get("origin url"),
            show_fields.get("pinned commit"),
            show_fields.get("status"),
        ),
        "catalog update": (
            update_out.err,
            _output_field_labels(update_out.out),
            update_fields.get("catalog"),
            update_fields.get("requested ref"),
            update_fields.get("pinned commit"),
            update_fields.get("status"),
            update_fields.get("audit id") == "none",
            catalog_metadata,
        ),
        "catalog remove": (
            remove_out.err,
            _output_field_labels(remove_out.out),
            remove_fields.get("catalog"),
            remove_fields.get("removed"),
            remove_fields.get("audit id") == "none",
        ),
    } == {
        "catalog add": (
            "",
            _documented_success_labels("catalog skydiscover add"),
            "skydiscover",
            str(upstream),
            "main",
            first_commit,
            "active",
            False,
        ),
        "catalog show": (
            "",
            _documented_success_labels("catalog skydiscover show"),
            "skydiscover",
            str(upstream),
            first_commit,
            "active",
        ),
        "catalog update": (
            "",
            _documented_success_labels("catalog skydiscover update"),
            "skydiscover",
            "main",
            second_commit,
            "active",
            False,
            {
                "schema_version": 1,
                "safe_summary": f"SkyDiscover catalog pinned at {second_commit[:12]}",
                "task_refs": [],
                "evaluator_refs": [],
                "warnings": [],
            },
        ),
        "catalog remove": (
            "",
            _documented_success_labels("catalog skydiscover remove"),
            "skydiscover",
            "true",
            False,
        ),
    }


def test_key_command_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, _admin_key = _init_capability_project(tmp_path, capsys)

    assert cli.run(["--home", str(home), "--key", root_key, "key", "list", "--root"]) == 0
    root_list_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", root_key, "key", "list", "--project", project_id]) == 0
    project_list_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", root_key, "key", "create", "--project", project_id]) == 0
    create_out = capsys.readouterr()
    key_id = _output_field_map(create_out.out)["key id"]

    assert cli.run(["--home", str(home), "--key", root_key, "key", "revoke", key_id, "--project", project_id]) == 0
    revoke_out = capsys.readouterr()
    revoke_fields = _output_field_map(revoke_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "credential",
                "--object-id",
                key_id,
                "--action",
                "revoke",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    revoke_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", revoke_audit_id, "--project", project_id]) == 0
    revoke_audit_out = capsys.readouterr()
    revoke_audit_fields = _output_field_map(revoke_audit_out.out)
    revoke_audit_metadata = json.loads(revoke_audit_fields["sanitized metadata"])

    assert {
        "key list --root": (root_list_out.err, _output_field_labels(root_list_out.out), _documented_success_labels("key list --root")),
        "key list --project": (project_list_out.err, _output_field_labels(project_list_out.out), _documented_success_labels("key list --project")),
        "key create": (create_out.err, _output_field_labels(create_out.out), _documented_success_labels("key create --project")),
        "key revoke": (revoke_out.err, _output_field_labels(revoke_out.out), _documented_success_labels("key revoke")),
        "key revoke audit": (
            revoke_audit_out.err,
            _output_field_labels(revoke_audit_out.out),
            revoke_audit_fields.get("audit id"),
            revoke_audit_fields.get("action"),
            revoke_audit_fields.get("object type"),
            revoke_audit_fields.get("object id"),
            revoke_audit_metadata,
        ),
    } == {
        "key list --root": ("", _documented_success_labels("key list --root"), _documented_success_labels("key list --root")),
        "key list --project": ("", _documented_success_labels("key list --project"), _documented_success_labels("key list --project")),
        "key create": ("", _documented_success_labels("key create --project"), _documented_success_labels("key create --project")),
        "key revoke": ("", _documented_success_labels("key revoke"), _documented_success_labels("key revoke")),
        "key revoke audit": (
            "",
            _documented_success_labels("audit show"),
            revoke_audit_id,
            "revoke",
            "credential",
            key_id,
            {
                "credential_status": "revoked",
                "credential_type": "admin",
                "previous_status": "active",
                "revoked_at": revoke_fields["revoked at"],
                "schema_version": 1,
                "token_mode": None,
            },
        ),
    }


def test_project_admin_key_authority_edges_are_scoped_and_side_effect_free(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    other_source = tmp_path / "other-source"
    other_config = tmp_path / "other.project.toml"
    other_source.mkdir()
    (other_source / "main.py").write_text("print('other')\n", encoding="utf-8")
    other_config.write_text(
        f"""
schema_version = 1

[project]
name = "Other Admin Scope Project"
task = "Exercise project admin scope boundaries"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(other_config),
                "--source-path",
                str(other_source),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    other_project_id = _output_field_map(capsys.readouterr().out)["project id"]

    assert cli.run(["--home", str(home), "--key", admin_key, "key", "list", "--project", project_id]) == 0
    own_list = capsys.readouterr()
    assert own_list.err == ""
    assert project_id in own_list.out
    assert other_project_id not in own_list.out

    before = _database_snapshot(home)
    denied_cases = [
        (["key", "list", "--root"], "AUTH_DENIED", "invalid credential"),
        (["key", "list", "--project", other_project_id], "COMMAND_UNAVAILABLE", "command is not available in the current context"),
        (["key", "create", "--project", project_id], "COMMAND_UNAVAILABLE", "command is not available in the current context"),
        (
            ["key", "revoke", "cred-missing-AAAAAAAAAAAAAAAAAAAAAA", "--project", project_id],
            "COMMAND_UNAVAILABLE",
            "command is not available in the current context",
        ),
    ]

    failures: list[dict[str, object]] = []
    for args, error_code, reason in denied_cases:
        code = cli.run(["--home", str(home), "--key", admin_key, *args])
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        database_unchanged = _database_snapshot(home) == before
        if (
            code != error_exit_code(error_code)
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != error_code
            or fields.get("reason") != reason
            or not database_unchanged
        ):
            failures.append(
                {
                    "args": args,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "database unchanged": database_unchanged,
                }
            )

    assert failures == []


def test_project_secret_gc_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    orphan_secret_id = "sec-orphan-CONTRACTSECRET0001"
    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute(
            """
            INSERT INTO secret_values(secret_value_id, project_id, name, value, fingerprint,
              created_at, created_by_credential_id, replaced_at)
            VALUES (?, ?, 'CONTRACT_ORPHAN', 'contract-secret',
              'hmac-sha256:0000000000000000000000000000000000000000000000000000000000000000',
              '2026-05-20T00:00:00Z', NULL, NULL)
            """,
            (orphan_secret_id, project_id),
        )

    expected_labels = _documented_success_labels("project secret gc")
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "secret",
                "gc",
                "--project",
                project_id,
                "--dry-run",
            ]
        )
        == 0
    )
    dry_run_out = capsys.readouterr()
    dry_run_fields = _output_field_map(dry_run_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "secret",
                "gc",
                "--project",
                project_id,
                "--apply",
            ]
        )
        == 0
    )
    apply_out = capsys.readouterr()
    apply_fields = _output_field_map(apply_out.out)
    audit_id = apply_fields["audit id"]

    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", audit_id, "--project", project_id]) == 0
    audit_out = capsys.readouterr()
    audit_fields = _output_field_map(audit_out.out)

    with sqlite3.connect(home / "alab.db") as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM secret_values WHERE secret_value_id = ?",
            (orphan_secret_id,),
        ).fetchone()[0]

    assert {
        "dry-run": (
            dry_run_out.err,
            _output_field_labels(dry_run_out.out),
            dry_run_fields.get("dry run"),
            dry_run_fields.get("deleted count"),
            dry_run_fields.get("secret value id"),
            "CONTRACT_ORPHAN" in dry_run_out.out,
            "contract-secret" in dry_run_out.out,
        ),
        "apply": (
            apply_out.err,
            _output_field_labels(apply_out.out),
            apply_fields.get("dry run"),
            apply_fields.get("deleted count"),
            apply_fields.get("secret value id"),
            apply_fields.get("audit id") == "none",
            remaining,
        ),
        "audit": (
            audit_out.err,
            _output_field_labels(audit_out.out),
            audit_fields.get("audit id"),
            audit_fields.get("action"),
            audit_fields.get("object type"),
            "deleted_count" in audit_fields.get("sanitized metadata", ""),
            "CONTRACT_ORPHAN" in audit_out.out,
            "contract-secret" in audit_out.out,
        ),
    } == {
        "dry-run": ("", expected_labels, "true", "1", orphan_secret_id, False, False),
        "apply": ("", expected_labels, "false", "1", orphan_secret_id, False, 0),
        "audit": (
            "",
            _documented_success_labels("audit show"),
            audit_id,
            "gc",
            "secret_value",
            True,
            False,
            False,
        ),
    }


def test_project_secret_success_fields_follow_cli_spec(tmp_path: Path, monkeypatch, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    raw_secret = "contract-secret-value"
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw_secret + "\n"))

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "secret",
                "set",
                "CONTRACT_SECRET",
                "--value-stdin",
                "--project",
                project_id,
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    set_out = capsys.readouterr()
    set_fields = _output_field_map(set_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "secret",
                "list",
                "--project",
                project_id,
            ]
        )
        == 0
    )
    list_out = capsys.readouterr()
    list_fields = _output_field_map(list_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "secret",
                "unset",
                "CONTRACT_SECRET",
                "--project",
                project_id,
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    unset_out = capsys.readouterr()
    unset_fields = _output_field_map(unset_out.out)

    assert {
        "set": (
            set_out.err,
            _output_field_labels(set_out.out),
            _documented_success_labels("project secret set"),
            set_fields.get("secret name"),
            set_fields.get("action"),
            set_fields.get("secret fingerprint", "").startswith("hmac-sha256:"),
            raw_secret in set_out.out,
        ),
        "list": (
            list_out.err,
            _output_field_labels(list_out.out),
            _documented_success_labels("project secret list"),
            list_fields.get("secret name"),
            list_fields.get("secret fingerprint"),
            list_fields.get("referenced"),
            raw_secret in list_out.out,
        ),
        "unset": (
            unset_out.err,
            _output_field_labels(unset_out.out),
            _documented_success_labels("project secret unset"),
            unset_fields.get("secret name"),
            unset_fields.get("action"),
            unset_fields.get("secret fingerprint"),
            raw_secret in unset_out.out,
        ),
    } == {
        "set": (
            "",
            _documented_success_labels("project secret set"),
            _documented_success_labels("project secret set"),
            "CONTRACT_SECRET",
            "set",
            True,
            False,
        ),
        "list": (
            "",
            _documented_success_labels("project secret list"),
            _documented_success_labels("project secret list"),
            "CONTRACT_SECRET",
            set_fields.get("secret fingerprint"),
            "true",
            False,
        ),
        "unset": (
            "",
            _documented_success_labels("project secret unset"),
            _documented_success_labels("project secret unset"),
            "CONTRACT_SECRET",
            "unset",
            set_fields.get("secret fingerprint"),
            False,
        ),
    }


def test_project_env_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "env",
                "set",
                "CONTRACT_ENV",
                "visible-value",
                "--project",
                project_id,
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    set_out = capsys.readouterr()

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "env",
                "list",
                "--project",
                project_id,
            ]
        )
        == 0
    )
    list_out = capsys.readouterr()
    list_fields = _output_field_map(list_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "env",
                "unset",
                "CONTRACT_ENV",
                "--project",
                project_id,
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    unset_out = capsys.readouterr()

    assert {
        "set": (
            set_out.err,
            _output_field_labels(set_out.out),
            _documented_success_labels("project env set"),
        ),
        "list": (
            list_out.err,
            _output_field_labels(list_out.out),
            _documented_success_labels("project env list"),
            list_fields.get("env name"),
            list_fields.get("value"),
        ),
        "unset": (
            unset_out.err,
            _output_field_labels(unset_out.out),
            _documented_success_labels("project env unset"),
        ),
    } == {
        "set": (
            "",
            _documented_success_labels("project env set"),
            _documented_success_labels("project env set"),
        ),
        "list": (
            "",
            _documented_success_labels("project env list"),
            _documented_success_labels("project env list"),
            "CONTRACT_ENV",
            "visible-value",
        ),
        "unset": (
            "",
            _documented_success_labels("project env unset"),
            _documented_success_labels("project env unset"),
        ),
    }


def test_project_config_mutation_and_validate_success_fields_follow_cli_spec(
    tmp_path: Path,
    capsys,
) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    export_path = tmp_path / "exported-config.toml"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "config",
                "export",
                "--project",
                project_id,
                "--out",
                str(export_path),
            ]
        )
        == 0
    )
    export_out = capsys.readouterr()

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "config",
                "import",
                "--project",
                project_id,
                "--config",
                str(export_path),
                "--dry-run",
            ]
        )
        == 0
    )
    import_out = capsys.readouterr()

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "config",
                "set",
                "project.goal",
                json.dumps("Contract dry-run goal"),
                "--project",
                project_id,
                "--dry-run",
            ]
        )
        == 0
    )
    set_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "project", "validate", "--project", project_id]) == 0
    validate_out = capsys.readouterr()

    assert {
        "config export": (
            export_out.err,
            _output_field_labels(export_out.out),
            _documented_success_labels("project config export"),
        ),
        "config import": (
            import_out.err,
            _output_field_labels(import_out.out),
            _documented_success_labels("project config import", omit={"warning code"}),
        ),
        "config set": (
            set_out.err,
            _output_field_labels(set_out.out),
            _documented_success_labels("project config set", omit={"warning code"}),
        ),
        "project validate": (
            validate_out.err,
            _output_field_labels(validate_out.out),
            _documented_success_labels("project validate", omit={"warning code"}),
        ),
    } == {
        "config export": (
            "",
            _documented_success_labels("project config export"),
            _documented_success_labels("project config export"),
        ),
        "config import": (
            "",
            _documented_success_labels("project config import", omit={"warning code"}),
            _documented_success_labels("project config import", omit={"warning code"}),
        ),
        "config set": (
            "",
            _documented_success_labels("project config set", omit={"warning code"}),
            _documented_success_labels("project config set", omit={"warning code"}),
        ),
        "project validate": (
            "",
            _documented_success_labels("project validate", omit={"warning code"}),
            _documented_success_labels("project validate", omit={"warning code"}),
        ),
    }


def test_project_validation_lifecycle_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    validation_id = services.new_id("val", "contract-validation")
    with sqlite3.connect(home / "alab.db") as conn:
        project_row = conn.execute(
            "SELECT active_valid_config_version FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        source_row = conn.execute(
            "SELECT source_ref, source_commit FROM sources WHERE project_id = ? ORDER BY created_at LIMIT 1",
            (project_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO project_validations(validation_id, project_id, config_version, source_ref, source_commit,
              status, exit_code, reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
            VALUES (?, ?, ?, ?, ?, 'passed', 0, 0, 'parsed', 'active',
              '2026-05-20T00:00:00Z', '2026-05-20T00:00:00Z', '{"schema_version":1}')
            """,
            (validation_id, project_id, project_row[0], source_row[0], source_row[1]),
        )

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "validation",
                "archive",
                validation_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    archive_out = capsys.readouterr()
    archive_fields = _output_field_map(archive_out.out)
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", archive_fields["audit id"], "--project", project_id]) == 0
    archive_audit_out = capsys.readouterr()
    archive_audit_fields = _output_field_map(archive_audit_out.out)
    archive_audit_metadata = json.loads(archive_audit_fields["sanitized metadata"])

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "validation",
                "unarchive",
                validation_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    unarchive_out = capsys.readouterr()
    unarchive_fields = _output_field_map(unarchive_out.out)
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", unarchive_fields["audit id"], "--project", project_id]) == 0
    unarchive_audit_out = capsys.readouterr()
    unarchive_audit_fields = _output_field_map(unarchive_audit_out.out)
    unarchive_audit_metadata = json.loads(unarchive_audit_fields["sanitized metadata"])

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "validation",
                "archive",
                validation_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "validation",
                "remove",
                validation_id,
                "--project",
                project_id,
                "--dry-run",
            ]
        )
        == 0
    )
    dry_run_out = capsys.readouterr()
    dry_run_fields = _output_field_map(dry_run_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "validation",
                "remove",
                validation_id,
                "--project",
                project_id,
                "--force",
                "--confirm",
                validation_id,
            ]
        )
        == 0
    )
    remove_out = capsys.readouterr()
    remove_fields = _output_field_map(remove_out.out)
    with sqlite3.connect(home / "alab.db") as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM project_validations WHERE validation_id = ?",
            (validation_id,),
        ).fetchone()[0]

    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", remove_fields["audit id"], "--project", project_id]) == 0
    audit_out = capsys.readouterr()
    audit_fields = _output_field_map(audit_out.out)

    assert {
        "archive": (
            archive_out.err,
            _output_field_labels(archive_out.out),
            archive_fields.get("validation id"),
            archive_fields.get("previous archive status"),
            archive_fields.get("archive status"),
            archive_fields.get("audit id") == "none",
        ),
        "unarchive": (
            unarchive_out.err,
            _output_field_labels(unarchive_out.out),
            unarchive_fields.get("validation id"),
            unarchive_fields.get("previous archive status"),
            unarchive_fields.get("archive status"),
            unarchive_fields.get("audit id") == "none",
        ),
        "archive audit": (
            archive_audit_out.err,
            _output_field_labels(archive_audit_out.out),
            archive_audit_fields.get("audit id"),
            archive_audit_fields.get("action"),
            archive_audit_fields.get("object type"),
            archive_audit_fields.get("object id"),
            archive_audit_metadata,
        ),
        "unarchive audit": (
            unarchive_audit_out.err,
            _output_field_labels(unarchive_audit_out.out),
            unarchive_audit_fields.get("audit id"),
            unarchive_audit_fields.get("action"),
            unarchive_audit_fields.get("object type"),
            unarchive_audit_fields.get("object id"),
            unarchive_audit_metadata,
        ),
        "dry-run": (
            dry_run_out.err,
            _output_field_labels(dry_run_out.out),
            dry_run_fields.get("dry run"),
            dry_run_fields.get("removed"),
            dry_run_fields.get("audit id"),
            dry_run_fields.get("deleted artifacts"),
            dry_run_fields.get("deleted logs"),
        ),
        "remove": (
            remove_out.err,
            _output_field_labels(remove_out.out),
            remove_fields.get("dry run"),
            remove_fields.get("removed"),
            remove_fields.get("audit id") == "none",
            remove_fields.get("trash cleanup pending"),
            remaining,
        ),
        "remove audit": (
            audit_out.err,
            _output_field_labels(audit_out.out),
            audit_fields.get("audit id"),
            audit_fields.get("action"),
            audit_fields.get("object type"),
            audit_fields.get("object id"),
            audit_fields.get("cascade"),
            audit_fields.get("reason"),
            "deleted_artifact_count" in audit_fields.get("sanitized metadata", ""),
            "deleted_log_count" in audit_fields.get("sanitized metadata", ""),
            "filesystem_target_count" in audit_fields.get("sanitized metadata", ""),
        ),
    } == {
        "archive": (
            "",
            _documented_success_labels("project validation archive"),
            validation_id,
            "active",
            "archived",
            False,
        ),
        "unarchive": (
            "",
            _documented_success_labels("project validation unarchive"),
            validation_id,
            "archived",
            "active",
            False,
        ),
        "archive audit": (
            "",
            _documented_success_labels("audit show"),
            archive_fields["audit id"],
            "archive",
            "validation",
            validation_id,
            {
                "archive_status": "archived",
                "archived_at": archive_fields["archived at"],
                "previous_archive_status": "active",
                "schema_version": 1,
            },
        ),
        "unarchive audit": (
            "",
            _documented_success_labels("audit show"),
            unarchive_fields["audit id"],
            "unarchive",
            "validation",
            validation_id,
            {
                "archive_status": "active",
                "previous_archive_status": "archived",
                "schema_version": 1,
                "unarchived_at": unarchive_fields["unarchived at"],
            },
        ),
        "dry-run": (
            "",
            _documented_success_labels(
                "project validation remove",
                omit={"blocker", "filesystem path", "planned trash move", "trash cleanup pending"},
            ),
            "true",
            "false",
            "none",
            "0",
            "0",
        ),
        "remove": (
            "",
            _documented_success_labels("project validation remove", omit={"blocker", "filesystem path", "planned trash move"}),
            "false",
            "true",
            False,
            "false",
            0,
        ),
        "remove audit": (
            "",
            _documented_success_labels("audit show"),
            remove_fields["audit id"],
            "remove",
            "validation",
            validation_id,
            "false",
            "none",
            True,
            True,
            True,
        ),
    }


def test_project_lock_clear_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "locks",
                "clear-stale",
                "--project",
                project_id,
            ]
        )
        == 0
    )
    empty_out = capsys.readouterr()
    empty_fields = _output_field_map(empty_out.out)

    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute(
            """
            INSERT INTO locks(lock_name, owner_operation_id, owner_host, owner_pid, project_id,
              exp_id, acquired_at, heartbeat_at, expires_at)
            VALUES ('lock-contract-stale', 'op-contract', 'test-host', 123, ?, NULL,
              '2026-05-20T00:00:00Z', '2026-05-20T00:00:00Z', '2000-01-01T00:00:00Z')
            """,
            (project_id,),
        )

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "locks",
                "clear-stale",
                "--project",
                project_id,
            ]
        )
        == 0
    )
    stale_out = capsys.readouterr()
    stale_fields = _output_field_map(stale_out.out)

    with sqlite3.connect(home / "alab.db") as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM locks WHERE lock_name = 'lock-contract-stale'",
        ).fetchone()[0]

    assert {
        "empty": (
            empty_out.err,
            _output_field_labels(empty_out.out),
            empty_fields.get("cleared count"),
            empty_fields.get("audit id"),
        ),
        "stale": (
            stale_out.err,
            _output_field_labels(stale_out.out),
            stale_fields.get("cleared count"),
            stale_fields.get("lock name"),
            stale_fields.get("audit id") == "none",
            remaining,
        ),
    } == {
        "empty": (
            "",
            _documented_success_labels("project locks clear-stale", omit={"lock name"}),
            "0",
            "none",
        ),
        "stale": (
            "",
            _documented_success_labels("project locks clear-stale"),
            "1",
            "lock-contract-stale",
            False,
            0,
        ),
    }


def test_maintenance_prune_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]

    backup_path = Home(home).backups_path / "contract-backup.db"
    backup_path.write_text("backup bytes\n", encoding="utf-8")

    assert cli.run(["--home", str(home), "--key", root_key, "backup", "prune", "--keep", "0"]) == 0
    backup_out = capsys.readouterr()
    backup_fields = _output_field_map(backup_out.out)

    env_cache_path = Home(home).cache_path / "contract-env"
    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute(
            """
            INSERT INTO cache_entries(cache_id, cache_kind, cache_key, project_id, path, docker_tag,
              size_bytes, status, metadata_json, created_at, last_used_at, removed_at)
            VALUES ('cache-contract-skydiscover-env', 'skydiscover_python_env', 'contract-env',
              NULL, ?, NULL, NULL, 'active', '{"schema_version":1}',
              '2026-05-20T00:00:00Z', '2026-05-20T00:00:00Z', NULL)
            """,
            (str(env_cache_path),),
        )

    assert cli.run(["--home", str(home), "--key", root_key, "cache", "prune", "--skydiscover-envs"]) == 0
    cache_out = capsys.readouterr()
    cache_fields = _output_field_map(cache_out.out)
    with sqlite3.connect(home / "alab.db") as conn:
        remaining_cache = conn.execute(
            """
            SELECT COUNT(*) FROM cache_entries
            WHERE cache_id = 'cache-contract-skydiscover-env' AND status = 'active'
            """
        ).fetchone()[0]

    assert {
        "backup prune": (
            backup_out.err,
            _output_field_labels(backup_out.out),
            backup_fields.get("backup pruned count"),
            backup_fields.get("backup path"),
            backup_fields.get("audit id") == "none",
            backup_path.exists(),
        ),
        "cache prune": (
            cache_out.err,
            _output_field_labels(cache_out.out),
            cache_fields.get("cache pruned count"),
            cache_fields.get("cache kind"),
            cache_fields.get("audit id") == "none",
            remaining_cache,
        ),
    } == {
        "backup prune": (
            "",
            _documented_success_labels("backup prune"),
            "1",
            str(backup_path),
            False,
            False,
        ),
        "cache prune": (
            "",
            _documented_success_labels("cache prune"),
            "1",
            "skydiscover_python_env",
            False,
            0,
        ),
    }


def test_audit_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]

    backup_path = Home(home).backups_path / "audit-contract-backup.db"
    backup_path.write_text("backup bytes\n", encoding="utf-8")
    assert cli.run(["--home", str(home), "--key", root_key, "backup", "prune", "--keep", "0"]) == 0
    prune_out = capsys.readouterr()
    audit_id = _output_field_map(prune_out.out)["audit id"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--object-type",
                "backup",
                "--object-id",
                "backups",
                "--action",
                "prune",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    list_out = capsys.readouterr()
    list_fields = _output_field_map(list_out.out)

    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", audit_id]) == 0
    show_out = capsys.readouterr()
    show_fields = _output_field_map(show_out.out)

    assert {
        "audit list": (
            list_out.err,
            _output_field_labels(list_out.out),
            list_fields.get("audit id"),
            list_fields.get("action"),
            list_fields.get("object type"),
            list_fields.get("object id"),
        ),
        "audit show": (
            show_out.err,
            _output_field_labels(show_out.out),
            show_fields.get("audit id"),
            show_fields.get("action"),
            show_fields.get("object type"),
            show_fields.get("object id"),
            '"pruned_count":1' in show_fields.get("sanitized metadata", ""),
        ),
    } == {
        "audit list": (
            "",
            _documented_success_labels("audit list"),
            audit_id,
            "prune",
            "backup",
            "backups",
        ),
        "audit show": (
            "",
            _documented_success_labels("audit show"),
            audit_id,
            "prune",
            "backup",
            "backups",
            True,
        ),
    }


def test_experiment_observe_success_fields_follow_cli_spec(tmp_path: Path, monkeypatch, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "exp-field-worktree"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Experiment Field Contract",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    create_out = capsys.readouterr()
    create_fields = _output_field_map(create_out.out)
    exp_id = create_fields["exp id"]
    create_raw_token = (worktree_path / ".alab" / "token").read_text(encoding="utf-8").rstrip("\n")

    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "tag", "add", exp_id, "docs", "--project", project_id]) == 0
    tag_add_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "tag", "add", exp_id, "scratch", "--project", project_id]) == 0
    capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "tag", "remove", exp_id, "scratch", "--project", project_id]) == 0
    tag_remove_out = capsys.readouterr()
    tag_remove_fields = _output_field_map(tag_remove_out.out)

    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "tag", "list", exp_id, "--project", project_id]) == 0
    tag_list_out = capsys.readouterr()

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "experiment observe best contract"]) == 0
    capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "observe", "experiments", "list", "--project", project_id]) == 0
    list_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "observe", "experiments", "search", "--project", project_id, "--query", "Experiment Field"]) == 0
    search_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "observe", "experiments", "show", exp_id, "--project", project_id]) == 0
    show_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "observe", "experiments", "best", "--project", project_id]) == 0
    best_out = capsys.readouterr()

    assert {
        "exp create": (
            create_out.err,
            _output_field_labels(create_out.out),
            _documented_success_labels("exp create", omit={"warning"}),
            create_fields.get("token path"),
            create_raw_token in create_out.out,
        ),
        "observe experiments list": (list_out.err, _output_field_labels(list_out.out), _documented_success_labels("observe experiments list")),
        "observe experiments search": (search_out.err, _output_field_labels(search_out.out), _documented_success_labels("observe experiments search")),
        "observe experiments show": (show_out.err, _output_field_labels(show_out.out), _documented_success_labels("observe experiments show")),
        "observe experiments best": (best_out.err, _output_field_labels(best_out.out), _documented_success_labels("observe experiments best")),
        "exp tag add": (tag_add_out.err, _output_field_labels(tag_add_out.out), _documented_success_labels("exp tag add")),
        "exp tag remove": (
            tag_remove_out.err,
            _output_field_labels(tag_remove_out.out),
            _documented_success_labels("exp tag remove"),
            tag_remove_fields.get("tag"),
            tag_remove_fields.get("action"),
        ),
        "exp tag list": (tag_list_out.err, _output_field_labels(tag_list_out.out), _documented_success_labels("exp tag list")),
    } == {
        "exp create": (
            "",
            _documented_success_labels("exp create", omit={"warning"}),
            _documented_success_labels("exp create", omit={"warning"}),
            str(worktree_path / ".alab" / "token"),
            False,
        ),
        "observe experiments list": ("", _documented_success_labels("observe experiments list"), _documented_success_labels("observe experiments list")),
        "observe experiments search": ("", _documented_success_labels("observe experiments search"), _documented_success_labels("observe experiments search")),
        "observe experiments show": ("", _documented_success_labels("observe experiments show"), _documented_success_labels("observe experiments show")),
        "observe experiments best": ("", _documented_success_labels("observe experiments best"), _documented_success_labels("observe experiments best")),
        "exp tag add": ("", _documented_success_labels("exp tag add"), _documented_success_labels("exp tag add")),
        "exp tag remove": ("", _documented_success_labels("exp tag remove"), _documented_success_labels("exp tag remove"), "scratch", "remove"),
        "exp tag list": ("", _documented_success_labels("exp tag list"), _documented_success_labels("exp tag list")),
    }


def test_experiment_create_inline_source_variants_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    local_source = tmp_path / "inline-local-source"
    local_source.mkdir()
    (local_source / "local.py").write_text("print('inline local')\n", encoding="utf-8")
    git_source = tmp_path / "inline-git-source"
    _init_catalog_upstream(git_source)

    variants = [
        (
            "local",
            [
                "--source-path",
                str(local_source),
            ],
            tmp_path / "inline-local-worktree",
            "Inline Local Contract",
        ),
        (
            "git",
            [
                "--source-git",
                str(git_source),
                "--git-ref",
                "main",
            ],
            tmp_path / "inline-git-worktree",
            "Inline Git Contract",
        ),
        (
            "empty",
            [
                "--source-empty",
            ],
            tmp_path / "inline-empty-worktree",
            "Inline Empty Contract",
        ),
    ]
    observed = {}
    expected_labels = _documented_success_labels("exp create", omit={"warning"})

    for variant, source_args, worktree_path, name in variants:
        assert (
            cli.run(
                [
                    "--home",
                    str(home),
                    "--key",
                    admin_key,
                    "exp",
                    "create",
                    "--project",
                    project_id,
                    "--name",
                    name,
                    *source_args,
                    "--path",
                    str(worktree_path),
                ]
            )
            == 0
        )
        create_out = capsys.readouterr()
        create_fields = _output_field_map(create_out.out)
        raw_token = (worktree_path / ".alab" / "token").read_text(encoding="utf-8").rstrip("\n")
        observed[variant] = (
            create_out.err,
            _output_field_labels(create_out.out),
            create_fields.get("project id"),
            create_fields.get("experiment name"),
            create_fields.get("source id", "").startswith("src-"),
            create_fields.get("worktree path"),
            create_fields.get("token path"),
            raw_token in create_out.out,
        )

    assert observed == {
        "local": (
            "",
            expected_labels,
            project_id,
            "Inline Local Contract",
            True,
            str(tmp_path / "inline-local-worktree"),
            str(tmp_path / "inline-local-worktree" / ".alab" / "token"),
            False,
        ),
        "git": (
            "",
            expected_labels,
            project_id,
            "Inline Git Contract",
            True,
            str(tmp_path / "inline-git-worktree"),
            str(tmp_path / "inline-git-worktree" / ".alab" / "token"),
            False,
        ),
        "empty": (
            "",
            expected_labels,
            project_id,
            "Inline Empty Contract",
            True,
            str(tmp_path / "inline-empty-worktree"),
            str(tmp_path / "inline-empty-worktree" / ".alab" / "token"),
            False,
        ),
    }


def test_experiment_create_default_worktree_path_must_be_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    fixed_exp_id = "exp-default-worktree-ABCDEFGHIJKLMNOPQRSTUV"
    original_new_id = services.new_id

    def deterministic_exp_id(prefix: str, name: str | None = None) -> str:
        if prefix == "exp":
            return fixed_exp_id
        return original_new_id(prefix, name)

    command_cwd = tmp_path / "command-cwd"
    command_cwd.mkdir()
    default_path = command_cwd / f"{project_id}_{fixed_exp_id}"
    default_path.mkdir()
    before_snapshot = _database_snapshot(home)

    monkeypatch.setattr(services, "new_id", deterministic_exp_id)
    monkeypatch.chdir(command_cwd)
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Default Worktree Exists",
            ]
        )
        == 2
    )
    blocked = capsys.readouterr()
    blocked_fields = _output_field_map(blocked.err)
    assert blocked.out == ""
    assert _output_field_labels(blocked.err) == _error_field_labels()
    assert blocked_fields["error code"] == "OUTPUT_EXISTS"
    assert blocked_fields["reason"] == "default experiment worktree path already exists"
    assert blocked_fields["next"] == "pass --path <dir> to choose a custom worktree location"
    assert default_path.is_dir()
    assert list(default_path.iterdir()) == []
    assert _database_snapshot(home) == before_snapshot

    custom_path = command_cwd / "custom-empty-worktree"
    custom_path.mkdir()
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Default Worktree Exists",
                "--path",
                str(custom_path),
            ]
        )
        == 0
    )
    created = capsys.readouterr()
    created_fields = _output_field_map(created.out)
    assert created.err == ""
    assert created_fields["exp id"] == fixed_exp_id
    assert created_fields["worktree path"] == str(custom_path)
    assert (custom_path / ".alab" / "context.json").is_file()


def test_experiment_create_from_exp_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    parent_path = tmp_path / "from-exp-parent-worktree"
    child_path = tmp_path / "from-exp-child-worktree"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "From Exp Parent Contract",
                "--path",
                str(parent_path),
            ]
        )
        == 0
    )
    parent_out = capsys.readouterr()
    parent_fields = _output_field_map(parent_out.out)
    parent_exp_id = parent_fields["exp id"]
    parent_source_id = parent_fields["source id"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "From Exp Child Contract",
                "--from-exp",
                parent_exp_id,
                "--path",
                str(child_path),
            ]
        )
        == 0
    )
    child_out = capsys.readouterr()
    child_fields = _output_field_map(child_out.out)
    raw_child_token = (child_path / ".alab" / "token").read_text(encoding="utf-8").rstrip("\n")

    with sqlite3.connect(home / "alab.db") as conn:
        source_count = conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
        child_row = conn.execute(
            "SELECT source_id, metadata_json FROM experiments WHERE exp_id = ?",
            (child_fields["exp id"],),
        ).fetchone()
    child_metadata = json.loads(child_row[1])
    creation_origin = child_metadata["creation_origin"]

    assert {
        "child": (
            child_out.err,
            _output_field_labels(child_out.out),
            child_fields.get("project id"),
            child_fields.get("experiment name"),
            child_fields.get("source id"),
            child_fields.get("worktree path"),
            child_fields.get("token path"),
            raw_child_token in child_out.out,
        ),
        "lineage": (
            source_count,
            child_row[0],
            creation_origin.get("kind"),
            creation_origin.get("source_exp_id"),
            creation_origin.get("from_commit"),
            creation_origin.get("source_id"),
        ),
    } == {
        "child": (
            "",
            _documented_success_labels("exp create", omit={"warning"}),
            project_id,
            "From Exp Child Contract",
            parent_source_id,
            str(child_path),
            str(child_path / ".alab" / "token"),
            False,
        ),
        "lineage": (
            1,
            parent_source_id,
            "from_exp",
            parent_exp_id,
            "latest",
            parent_source_id,
        ),
    }


def test_experiment_create_source_ref_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    source_path = tmp_path / "explicit-ref-source"
    source_path.mkdir()
    (source_path / "main.py").write_text("print('explicit source ref')\n", encoding="utf-8")
    worktree_path = tmp_path / "explicit-ref-worktree"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "source",
                "import",
                "--project",
                project_id,
                "--source-path",
                str(source_path),
                "--name",
                "contract-explicit-ref-source",
            ]
        )
        == 0
    )
    import_fields = _output_field_map(capsys.readouterr().out)
    source_id = import_fields["source id"]
    source_ref = import_fields["source ref"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Explicit Source Ref Contract",
                "--source-ref",
                source_ref,
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    create_out = capsys.readouterr()
    create_fields = _output_field_map(create_out.out)
    raw_token = (worktree_path / ".alab" / "token").read_text(encoding="utf-8").rstrip("\n")

    with sqlite3.connect(home / "alab.db") as conn:
        source_count = conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
        exp_row = conn.execute(
            "SELECT source_id, metadata_json FROM experiments WHERE exp_id = ?",
            (create_fields["exp id"],),
        ).fetchone()
    metadata = json.loads(exp_row[1])
    creation_origin = metadata["creation_origin"]

    assert {
        "create": (
            create_out.err,
            _output_field_labels(create_out.out),
            create_fields.get("project id"),
            create_fields.get("experiment name"),
            create_fields.get("source id"),
            create_fields.get("worktree path"),
            create_fields.get("token path"),
            raw_token in create_out.out,
        ),
        "lineage": (
            source_count,
            exp_row[0],
            creation_origin.get("kind"),
            creation_origin.get("source_id"),
            metadata.get("source_selector"),
        ),
    } == {
        "create": (
            "",
            _documented_success_labels("exp create", omit={"warning"}),
            project_id,
            "Explicit Source Ref Contract",
            source_id,
            str(worktree_path),
            str(worktree_path / ".alab" / "token"),
            False,
        ),
        "lineage": (
            2,
            source_id,
            "source",
            source_id,
            source_ref,
        ),
    }


def test_experiment_lifecycle_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "exp-lifecycle-worktree"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Lifecycle Contract Experiment",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    create_fields = _output_field_map(capsys.readouterr().out)
    exp_id = create_fields["exp id"]

    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "archive", exp_id, "--project", project_id]) == 0
    archive_out = capsys.readouterr()
    archive_fields = _output_field_map(archive_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "experiment",
                "--object-id",
                exp_id,
                "--action",
                "archive",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    archive_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", archive_audit_id, "--project", project_id]) == 0
    archive_audit_out = capsys.readouterr()
    archive_audit_fields = _output_field_map(archive_audit_out.out)
    archive_audit_meta = json.loads(archive_audit_fields["sanitized metadata"])

    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "unarchive", exp_id, "--project", project_id]) == 0
    unarchive_out = capsys.readouterr()
    unarchive_fields = _output_field_map(unarchive_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "experiment",
                "--object-id",
                exp_id,
                "--action",
                "unarchive",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    unarchive_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", unarchive_audit_id, "--project", project_id]) == 0
    unarchive_audit_out = capsys.readouterr()
    unarchive_audit_fields = _output_field_map(unarchive_audit_out.out)
    unarchive_audit_meta = json.loads(unarchive_audit_fields["sanitized metadata"])

    assert {
        "archive": (
            archive_out.err,
            _output_field_labels(archive_out.out),
            archive_fields.get("exp id"),
            archive_fields.get("previous status"),
            archive_fields.get("experiment status"),
            archive_fields.get("archived at") == "none",
        ),
        "unarchive": (
            unarchive_out.err,
            _output_field_labels(unarchive_out.out),
            unarchive_fields.get("exp id"),
            unarchive_fields.get("previous status"),
            unarchive_fields.get("experiment status"),
            unarchive_fields.get("unarchived at") == "none",
        ),
        "archive audit": (
            archive_audit_out.err,
            _output_field_labels(archive_audit_out.out),
            archive_audit_fields.get("audit id"),
            archive_audit_fields.get("action"),
            archive_audit_fields.get("object type"),
            archive_audit_fields.get("object id"),
            archive_audit_fields.get("cascade"),
            archive_audit_fields.get("reason"),
            archive_audit_meta,
        ),
        "unarchive audit": (
            unarchive_audit_out.err,
            _output_field_labels(unarchive_audit_out.out),
            unarchive_audit_fields.get("audit id"),
            unarchive_audit_fields.get("action"),
            unarchive_audit_fields.get("object type"),
            unarchive_audit_fields.get("object id"),
            unarchive_audit_fields.get("cascade"),
            unarchive_audit_fields.get("reason"),
            unarchive_audit_meta,
        ),
    } == {
        "archive": (
            "",
            _documented_success_labels("exp archive"),
            exp_id,
            "open",
            "archived",
            False,
        ),
        "unarchive": (
            "",
            _documented_success_labels("exp unarchive"),
            exp_id,
            "archived",
            "open",
            False,
        ),
        "archive audit": (
            "",
            _documented_success_labels("audit show"),
            archive_audit_id,
            "archive",
            "experiment",
            exp_id,
            "false",
            "none",
            {
                "archived_at": archive_fields["archived at"],
                "experiment_status": "archived",
                "previous_status": "open",
                "schema_version": 1,
            },
        ),
        "unarchive audit": (
            "",
            _documented_success_labels("audit show"),
            unarchive_audit_id,
            "unarchive",
            "experiment",
            exp_id,
            "false",
            "none",
            {
                "experiment_status": "open",
                "previous_status": "archived",
                "schema_version": 1,
                "unarchived_at": unarchive_fields["unarchived at"],
            },
        ),
    }


def test_experiment_remove_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "exp-remove-worktree"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Remove Contract Experiment",
                "--path",
                str(worktree_path),
                "--tag",
                "remove-contract",
            ]
        )
        == 0
    )
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]

    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "archive", exp_id, "--project", project_id]) == 0
    capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "remove", exp_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    dry_run_out = capsys.readouterr()
    dry_run_fields = _output_field_map(dry_run_out.out)
    filesystem_path_count = int(dry_run_fields["deleted filesystem paths"])

    assert {
        "dry-run remove": (
            dry_run_out.err,
            _output_field_labels(dry_run_out.out),
            dry_run_fields.get("exp id"),
            dry_run_fields.get("dry run"),
            dry_run_fields.get("removed"),
            dry_run_fields.get("cascade"),
            dry_run_fields.get("audit id"),
            dry_run_fields.get("deleted runs"),
            dry_run_fields.get("deleted artifacts"),
            dry_run_fields.get("deleted logs"),
            dry_run_fields.get("deleted annotations"),
            dry_run_fields.get("deleted tags"),
            dry_run_fields.get("deleted submissions"),
            dry_run_fields.get("branch ref exists"),
        ),
    } == {
        "dry-run remove": (
            "",
            _documented_success_labels_with_repeats(
                "exp remove",
                repeats={"filesystem path": filesystem_path_count, "planned trash move": filesystem_path_count},
                omit={"blocker", "deleted branch ref", "branch ref existed", "trash cleanup pending"},
            ),
            exp_id,
            "true",
            "false",
            "true",
            "none",
            "0",
            "0",
            "0",
            "0",
            "1",
            "0",
            "true",
        ),
    }


def test_experiment_worktree_lifecycle_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "worktree-lifecycle-active"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Worktree Lifecycle Contract",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    exp_create_fields = _output_field_map(capsys.readouterr().out)
    exp_id = exp_create_fields["exp id"]
    old_raw_token = (worktree_path / ".alab" / "token").read_text(encoding="utf-8").rstrip("\n")

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "worktree",
                "remove",
                exp_id,
                "--project",
                project_id,
                "--dry-run",
            ]
        )
        == 0
    )
    dry_run_out = capsys.readouterr()
    dry_run_fields = _output_field_map(dry_run_out.out)
    dry_run_path_exists = worktree_path.exists()

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "worktree",
                "remove",
                exp_id,
                "--project",
                project_id,
                "--force",
                "--confirm",
                exp_id,
            ]
        )
        == 0
    )
    remove_out = capsys.readouterr()
    remove_fields = _output_field_map(remove_out.out)
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", remove_fields["audit id"], "--project", project_id]) == 0
    remove_audit_out = capsys.readouterr()
    remove_audit_fields = _output_field_map(remove_audit_out.out)
    remove_audit_metadata = json.loads(remove_audit_fields["sanitized metadata"])

    restored_path = tmp_path / "worktree-lifecycle-restored"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "worktree",
                "restore",
                exp_id,
                "--project",
                project_id,
                "--path",
                str(restored_path),
            ]
        )
        == 0
    )
    restore_out = capsys.readouterr()
    restore_fields = _output_field_map(restore_out.out)
    restored_raw_token = (restored_path / ".alab" / "token").read_text(encoding="utf-8").rstrip("\n")
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "worktree",
                "--object-id",
                exp_id,
                "--action",
                "restore",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    restore_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", restore_audit_id, "--project", project_id]) == 0
    restore_audit_out = capsys.readouterr()
    restore_audit_fields = _output_field_map(restore_audit_out.out)
    restore_audit_metadata = json.loads(restore_audit_fields["sanitized metadata"])

    assert {
        "dry-run remove": (
            dry_run_out.err,
            _output_field_labels(dry_run_out.out),
            dry_run_fields.get("exp id"),
            dry_run_fields.get("old worktree path"),
            dry_run_fields.get("worktree state"),
            dry_run_fields.get("dry run"),
            dry_run_fields.get("removed"),
            dry_run_fields.get("path exists"),
            dry_run_fields.get("dirty state"),
            dry_run_fields.get("token revoked"),
            dry_run_fields.get("audit id"),
            dry_run_path_exists,
        ),
        "remove": (
            remove_out.err,
            _output_field_labels(remove_out.out),
            remove_fields.get("exp id"),
            remove_fields.get("old worktree path"),
            remove_fields.get("worktree state"),
            remove_fields.get("dry run"),
            remove_fields.get("removed"),
            remove_fields.get("path existed"),
            remove_fields.get("token revoked"),
            remove_fields.get("trash cleanup pending"),
            remove_fields.get("audit id") == "none",
            worktree_path.exists(),
        ),
        "remove audit": (
            remove_audit_out.err,
            _output_field_labels(remove_audit_out.out),
            remove_audit_fields.get("audit id"),
            remove_audit_fields.get("action"),
            remove_audit_fields.get("object type"),
            remove_audit_fields.get("object id"),
            old_raw_token in remove_audit_out.out,
            str(worktree_path) in remove_audit_out.out,
            remove_audit_metadata.get("dirty_state"),
            remove_audit_metadata.get("filesystem_path_already_absent"),
            remove_audit_metadata.get("token_revocation_target"),
            bool(remove_audit_metadata.get("trash", {}).get("original_path_hash")),
        ),
        "restore": (
            restore_out.err,
            _output_field_labels(restore_out.out),
            restore_fields.get("exp id"),
            restore_fields.get("worktree path"),
            restore_fields.get("worktree state"),
            restore_fields.get("token path"),
            restore_fields.get("revoked token id"),
            restore_fields.get("new token id") == "none",
            old_raw_token == restored_raw_token,
            old_raw_token in restore_out.out,
            restored_raw_token in restore_out.out,
            restored_path.exists(),
        ),
        "restore audit": (
            restore_audit_out.err,
            _output_field_labels(restore_audit_out.out),
            restore_audit_fields.get("audit id"),
            restore_audit_fields.get("action"),
            restore_audit_fields.get("object type"),
            restore_audit_fields.get("object id"),
            old_raw_token in restore_audit_out.out,
            restored_raw_token in restore_audit_out.out,
            str(restored_path) in restore_audit_out.out,
            bool(restore_audit_metadata.get("restored_path_hash")),
            bool(restore_audit_metadata.get("path_registry_id")),
            restore_audit_metadata,
        ),
    } == {
        "dry-run remove": (
            "",
            _documented_success_labels(
                "exp worktree remove",
                omit={"path existed", "trash path", "trash cleanup pending"},
            ),
            exp_id,
            str(worktree_path),
            "active",
            "true",
            "false",
            "true",
            "dirty",
            "true",
            "none",
            True,
        ),
        "remove": (
            "",
            _documented_success_labels(
                "exp worktree remove",
                omit={"path exists", "planned trash move"},
            ),
            exp_id,
            str(worktree_path),
            "removed",
            "false",
            "true",
            "true",
            "true",
            "false",
            False,
            False,
        ),
        "remove audit": (
            "",
            _documented_success_labels("audit show"),
            remove_fields["audit id"],
            "remove",
            "worktree",
            exp_id,
            False,
            False,
            "dirty",
            False,
            dry_run_fields["token revocation target"],
            True,
        ),
        "restore": (
            "",
            _documented_success_labels("exp worktree restore"),
            exp_id,
            str(restored_path),
            "active",
            str(restored_path / ".alab" / "token"),
            "none",
            False,
            False,
            False,
            False,
            True,
        ),
        "restore audit": (
            "",
            _documented_success_labels("audit show"),
            restore_audit_id,
            "restore",
            "worktree",
            exp_id,
            False,
            False,
            False,
            True,
            True,
            {
                "branch": restore_audit_metadata["branch"],
                "created_token_id": restore_fields["new token id"],
                "path_registry_id": restore_audit_metadata["path_registry_id"],
                "restored_path_hash": restore_audit_metadata["restored_path_hash"],
                "revoked_token_id": None,
                "schema_version": 1,
                "token_mode": "worktree",
                "worktree_state": "active",
            },
        ),
    }


def test_experiment_checkout_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "checkout-source-worktree"
    checkout_path = tmp_path / "inspection-checkout"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Checkout Contract Experiment",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "checkout",
                exp_id,
                "--project",
                project_id,
                "--path",
                str(checkout_path),
                "--commit",
                "latest",
            ]
        )
        == 0
    )
    checkout_out = capsys.readouterr()
    checkout_fields = _output_field_map(checkout_out.out)
    token_id = checkout_fields["token id"]
    raw_token = (checkout_path / ".alab" / "token").read_text(encoding="utf-8").rstrip("\n")

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "inspection_checkout",
                "--object-id",
                token_id,
                "--action",
                "add",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    add_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", add_audit_id, "--project", project_id]) == 0
    add_audit_out = capsys.readouterr()
    add_audit_fields = _output_field_map(add_audit_out.out)
    add_audit_metadata = json.loads(add_audit_fields["sanitized metadata"])

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "checkout",
                "remove",
                "--project",
                project_id,
                "--token-id",
                token_id,
                "--dry-run",
            ]
        )
        == 0
    )
    dry_run_out = capsys.readouterr()
    dry_run_fields = _output_field_map(dry_run_out.out)
    dry_run_path_exists = checkout_path.exists()

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "checkout",
                "remove",
                "--project",
                project_id,
                "--token-id",
                token_id,
                "--force",
                "--confirm",
                token_id,
            ]
        )
        == 0
    )
    remove_out = capsys.readouterr()
    remove_fields = _output_field_map(remove_out.out)
    audit_id = remove_fields["audit id"]

    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", audit_id, "--project", project_id]) == 0
    audit_out = capsys.readouterr()
    audit_fields = _output_field_map(audit_out.out)

    assert {
        "checkout": (
            checkout_out.err,
            _output_field_labels(checkout_out.out),
            checkout_fields.get("exp id"),
            checkout_fields.get("inspection path"),
            checkout_fields.get("token path"),
            raw_token in checkout_out.out,
        ),
        "checkout add audit": (
            add_audit_out.err,
            _output_field_labels(add_audit_out.out),
            add_audit_fields.get("audit id"),
            add_audit_fields.get("action"),
            add_audit_fields.get("object type"),
            add_audit_fields.get("object id"),
            raw_token in add_audit_out.out,
            str(checkout_path) in add_audit_out.out,
            bool(add_audit_metadata.get("path_registry_id")),
            bool(add_audit_metadata.get("created_for_path_hash")),
            add_audit_metadata,
        ),
        "dry-run remove": (
            dry_run_out.err,
            _output_field_labels(dry_run_out.out),
            dry_run_fields.get("exp id"),
            dry_run_fields.get("inspection path"),
            dry_run_fields.get("token id"),
            dry_run_fields.get("dry run"),
            dry_run_fields.get("removed"),
            dry_run_fields.get("path exists"),
            dry_run_fields.get("token revoked"),
            dry_run_fields.get("audit id"),
            raw_token in dry_run_out.out,
            dry_run_path_exists,
        ),
        "remove": (
            remove_out.err,
            _output_field_labels(remove_out.out),
            remove_fields.get("exp id"),
            remove_fields.get("inspection path"),
            remove_fields.get("token id"),
            remove_fields.get("dry run"),
            remove_fields.get("removed"),
            remove_fields.get("path existed"),
            remove_fields.get("token revoked"),
            remove_fields.get("trash cleanup pending"),
            remove_fields.get("audit id") == "none",
            raw_token in remove_out.out,
            checkout_path.exists(),
        ),
        "remove audit": (
            audit_out.err,
            _output_field_labels(audit_out.out),
            audit_fields.get("audit id"),
            audit_fields.get("action"),
            audit_fields.get("object type"),
            audit_fields.get("object id"),
            "token_revocation_target" in audit_fields.get("sanitized metadata", ""),
            "original_path_hash" in audit_fields.get("sanitized metadata", ""),
            raw_token in audit_out.out,
            str(checkout_path) in audit_out.out,
        ),
    } == {
        "checkout": (
            "",
            _documented_success_labels("exp checkout"),
            exp_id,
            str(checkout_path),
            str(checkout_path / ".alab" / "token"),
            False,
        ),
        "checkout add audit": (
            "",
            _documented_success_labels("audit show"),
            add_audit_id,
            "add",
            "inspection_checkout",
            token_id,
            False,
            False,
            True,
            True,
            {
                "created_for_path_hash": add_audit_metadata["created_for_path_hash"],
                "created_token_id": token_id,
                "credential_type": "token",
                "inspection_commit": checkout_fields["inspection commit"],
                "path_registry_id": add_audit_metadata["path_registry_id"],
                "schema_version": 1,
                "token_mode": "inspection",
            },
        ),
        "dry-run remove": (
            "",
            _documented_success_labels(
                "exp checkout remove",
                omit={"path existed", "trash path", "trash cleanup pending"},
            ),
            exp_id,
            str(checkout_path),
            token_id,
            "true",
            "false",
            "true",
            "true",
            "none",
            False,
            True,
        ),
        "remove": (
            "",
            _documented_success_labels(
                "exp checkout remove",
                omit={"path exists", "planned trash move"},
            ),
            exp_id,
            str(checkout_path),
            token_id,
            "false",
            "true",
            "true",
            "true",
            "false",
            False,
            False,
            False,
        ),
        "remove audit": (
            "",
            _documented_success_labels("audit show"),
            audit_id,
            "remove",
            "inspection_checkout",
            token_id,
            True,
            True,
            False,
            False,
        ),
    }


def test_experiment_token_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "exp-token-worktree"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Token Contract Experiment",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    create_fields = _output_field_map(capsys.readouterr().out)
    exp_id = create_fields["exp id"]
    old_raw_token = (worktree_path / ".alab" / "token").read_text(encoding="utf-8")

    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "token", "list", exp_id, "--project", project_id]) == 0
    list_out = capsys.readouterr()
    list_fields = _output_field_map(list_out.out)
    old_token_id = list_fields["token id"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "token",
                "regenerate",
                exp_id,
                "--project",
                project_id,
                "--mode",
                "worktree",
            ]
        )
        == 0
    )
    regenerate_out = capsys.readouterr()
    regenerate_fields = _output_field_map(regenerate_out.out)
    new_token_id = regenerate_fields["new token id"]
    new_raw_token = (worktree_path / ".alab" / "token").read_text(encoding="utf-8")

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "credential",
                "--object-id",
                new_token_id,
                "--action",
                "regenerate",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    regenerate_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", regenerate_audit_id, "--project", project_id]) == 0
    regenerate_audit_out = capsys.readouterr()
    regenerate_audit_fields = _output_field_map(regenerate_audit_out.out)
    regenerate_audit_metadata = json.loads(regenerate_audit_fields["sanitized metadata"])

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "token",
                "revoke",
                exp_id,
                "--project",
                project_id,
                "--token-id",
                new_token_id,
            ]
        )
        == 0
    )
    revoke_out = capsys.readouterr()
    revoke_fields = _output_field_map(revoke_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "credential",
                "--object-id",
                new_token_id,
                "--action",
                "revoke",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    revoke_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", revoke_audit_id, "--project", project_id]) == 0
    revoke_audit_out = capsys.readouterr()
    revoke_audit_fields = _output_field_map(revoke_audit_out.out)
    revoke_audit_metadata = json.loads(revoke_audit_fields["sanitized metadata"])

    assert {
        "list": (
            list_out.err,
            _output_field_labels(list_out.out),
            list_fields.get("project id"),
            list_fields.get("exp id"),
            list_fields.get("token mode"),
            list_fields.get("status"),
            old_raw_token in list_out.out,
        ),
        "regenerate": (
            regenerate_out.err,
            _output_field_labels(regenerate_out.out),
            regenerate_fields.get("project id"),
            regenerate_fields.get("exp id"),
            regenerate_fields.get("revoked token id"),
            regenerate_fields.get("new token id") == "none",
            regenerate_fields.get("token mode"),
            regenerate_fields.get("token path"),
            old_raw_token == new_raw_token,
            old_raw_token in regenerate_out.out,
            new_raw_token in regenerate_out.out,
        ),
        "regenerate audit": (
            regenerate_audit_out.err,
            _output_field_labels(regenerate_audit_out.out),
            regenerate_audit_fields.get("audit id"),
            regenerate_audit_fields.get("action"),
            regenerate_audit_fields.get("object type"),
            regenerate_audit_fields.get("object id"),
            old_raw_token in regenerate_audit_out.out,
            new_raw_token in regenerate_audit_out.out,
            bool(regenerate_audit_metadata.get("registered_path_hash")),
            regenerate_audit_metadata,
        ),
        "revoke": (
            revoke_out.err,
            _output_field_labels(revoke_out.out),
            revoke_fields.get("project id"),
            revoke_fields.get("exp id"),
            revoke_fields.get("token id"),
            revoke_fields.get("token mode"),
            revoke_fields.get("status"),
            new_raw_token in revoke_out.out,
        ),
        "revoke audit": (
            revoke_audit_out.err,
            _output_field_labels(revoke_audit_out.out),
            revoke_audit_fields.get("audit id"),
            revoke_audit_fields.get("action"),
            revoke_audit_fields.get("object type"),
            revoke_audit_fields.get("object id"),
            new_raw_token in revoke_audit_out.out,
            bool(revoke_audit_metadata.get("registered_path_hash")),
            revoke_audit_metadata,
        ),
    } == {
        "list": (
            "",
            _documented_success_labels("exp token list"),
            project_id,
            exp_id,
            "worktree",
            "active",
            False,
        ),
        "regenerate": (
            "",
            _documented_success_labels("exp token regenerate"),
            project_id,
            exp_id,
            old_token_id,
            False,
            "worktree",
            str(worktree_path / ".alab" / "token"),
            False,
            False,
            False,
        ),
        "regenerate audit": (
            "",
            _documented_success_labels("audit show"),
            regenerate_audit_id,
            "regenerate",
            "credential",
            new_token_id,
            False,
            False,
            True,
            {
                "created_credential_id": new_token_id,
                "credential_type": "token",
                "registered_path_hash": regenerate_audit_metadata["registered_path_hash"],
                "revoked_at": regenerate_fields["created at"],
                "revoked_credential_id": old_token_id,
                "schema_version": 1,
                "token_mode": "worktree",
            },
        ),
        "revoke": (
            "",
            _documented_success_labels("exp token revoke"),
            project_id,
            exp_id,
            new_token_id,
            "worktree",
            "revoked",
            False,
        ),
        "revoke audit": (
            "",
            _documented_success_labels("audit show"),
            revoke_audit_id,
            "revoke",
            "credential",
            new_token_id,
            False,
            True,
            {
                "credential_status": "revoked",
                "credential_type": "token",
                "previous_status": "active",
                "registered_path_hash": revoke_audit_metadata["registered_path_hash"],
                "revoked_at": revoke_fields["revoked at"],
                "schema_version": 1,
                "token_mode": "worktree",
            },
        ),
    }


def test_regenerated_worktree_token_keeps_private_annotation_visibility_and_edit_rights(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "regenerated-private-annotation"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Regenerated Private Annotation",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]
    old_marker = json.loads((worktree_path / ".alab" / "context.json").read_text(encoding="utf-8"))
    old_token_id = old_marker["token_id"]
    old_raw_token = (worktree_path / ".alab" / "token").read_text(encoding="utf-8")

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body", "private first", "--private"]) == 0
    add_out = capsys.readouterr()
    add_fields = _output_field_map(add_out.out)
    annotation_id = add_fields["annotation id"]
    assert add_fields["visibility"] == "private"

    monkeypatch.chdir(tmp_path)
    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "token", "regenerate", exp_id, "--project", project_id]) == 0
    regenerate_out = capsys.readouterr()
    regenerate_fields = _output_field_map(regenerate_out.out)
    new_token_id = regenerate_fields["new token id"]
    new_raw_token = (worktree_path / ".alab" / "token").read_text(encoding="utf-8")
    new_marker = json.loads((worktree_path / ".alab" / "context.json").read_text(encoding="utf-8"))

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "annotations", "show", annotation_id, "--history"]) == 0
    show_out = capsys.readouterr()
    assert "body:\n  private first" in show_out.out
    assert cli.run(["--home", str(home), "annotate", "edit", annotation_id, "--body", "private after regeneration", "--author", "regenerated"]) == 0
    edit_out = capsys.readouterr()
    edit_fields = _output_field_map(edit_out.out)
    assert cli.run(["--home", str(home), "annotations", "show", annotation_id, "--history"]) == 0
    edited_show_out = capsys.readouterr()

    with sqlite3.connect(home / "alab.db") as conn:
        token_rows = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT credential_id, status FROM credentials WHERE credential_id IN (?, ?)",
                (old_token_id, new_token_id),
            ).fetchall()
        }
        annotation_row = conn.execute(
            "SELECT visibility_json, current_revision FROM annotations WHERE annotation_id = ?",
            (annotation_id,),
        ).fetchone()
        revision_creators = conn.execute(
            "SELECT revision, created_by_type, created_by_id FROM annotation_revisions WHERE annotation_id = ? ORDER BY revision",
            (annotation_id,),
        ).fetchall()

    assert {
        "add labels": _output_field_labels(add_out.out),
        "regenerate labels": _output_field_labels(regenerate_out.out),
        "show labels": _output_field_labels(show_out.out),
        "edit labels": _output_field_labels(edit_out.out),
        "edit revision": edit_fields["revision"],
        "edited show labels": _output_field_labels(edited_show_out.out),
        "edited body visible": "body:\n  private after regeneration" in edited_show_out.out,
        "history revision 1": "revision: 1:" in edited_show_out.out,
        "history revision 2": "revision: 2:" in edited_show_out.out,
        "old token status": token_rows[old_token_id],
        "new token status": token_rows[new_token_id],
        "marker token id": new_marker["token_id"],
        "raw token changed": old_raw_token != new_raw_token,
        "visibility": json.loads(annotation_row[0]),
        "current revision": annotation_row[1],
        "revision creators": revision_creators,
    } == {
        "add labels": _documented_success_labels("annotate add"),
        "regenerate labels": _documented_success_labels("exp token regenerate"),
        "show labels": _documented_success_labels_with_repeats("observe annotations show", repeats={"revision": 1}),
        "edit labels": _documented_success_labels("annotate edit"),
        "edit revision": "2",
        "edited show labels": _documented_success_labels_with_repeats("observe annotations show", repeats={"revision": 2}),
        "edited body visible": True,
        "history revision 1": True,
        "history revision 2": True,
        "old token status": "revoked",
        "new token status": "active",
        "marker token id": new_token_id,
        "raw token changed": True,
        "visibility": {"schema_version": 1, "scope": "private", "creator_exp_id": exp_id, "constraints": {}},
        "current revision": 2,
        "revision creators": [(1, "token", exp_id), (2, "token", exp_id)],
    }


def test_admin_private_to_exp_annotation_binds_creator_exp_and_remove_audit(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    admin_args = ["--home", str(home), "--key", admin_key]
    audit_args = ["--home", str(home), "--key", root_key]
    creator_path = tmp_path / "private-to-exp-creator"
    target_path = tmp_path / "private-to-exp-target"

    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Private Creator",
                "--path",
                str(creator_path),
            ]
        )
        == 0
    )
    creator_exp_id = _output_field_map(capsys.readouterr().out)["exp id"]
    creator_token_id = json.loads((creator_path / ".alab" / "context.json").read_text(encoding="utf-8"))["token_id"]
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Private Target",
                "--path",
                str(target_path),
            ]
        )
        == 0
    )
    target_exp_id = _output_field_map(capsys.readouterr().out)["exp id"]

    assert (
        cli.run(
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                f"exp:{target_exp_id}",
                "--private-to-exp",
                creator_exp_id,
                "--body",
                "admin-created private note",
            ]
        )
        == 0
    )
    add_out = capsys.readouterr()
    add_fields = _output_field_map(add_out.out)
    annotation_id = add_fields["annotation id"]

    monkeypatch.chdir(target_path)
    assert cli.run(["--home", str(home), "annotations", "show", annotation_id]) == 4
    target_show_err = capsys.readouterr()
    assert cli.run(["--home", str(home), "annotate", "edit", annotation_id, "--body", "target edit should fail"]) == 4
    target_edit_err = capsys.readouterr()

    with sqlite3.connect(home / "alab.db") as conn:
        admin_credential_id = conn.execute(
            """
            SELECT credential_id FROM credentials
            WHERE credential_type = 'admin' AND project_id = ? AND status = 'active'
            """,
            (project_id,),
        ).fetchone()[0]
        annotation_before_creator_edit = conn.execute(
            """
            SELECT visibility_json, created_by_type, created_by_id, target_id, current_revision
            FROM annotations
            WHERE annotation_id = ?
            """,
            (annotation_id,),
        ).fetchone()
        revisions_before_creator_edit = conn.execute(
            """
            SELECT revision, created_by_type, created_by_id
            FROM annotation_revisions
            WHERE annotation_id = ?
            ORDER BY revision
            """,
            (annotation_id,),
        ).fetchall()

    monkeypatch.chdir(creator_path)
    assert cli.run(["--home", str(home), "annotations", "show", annotation_id, "--history"]) == 0
    creator_show_out = capsys.readouterr()
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "annotate",
                "edit",
                annotation_id,
                "--body",
                "creator experiment token edit",
                "--author",
                "creator-token",
            ]
        )
        == 0
    )
    creator_edit_out = capsys.readouterr()

    with sqlite3.connect(home / "alab.db") as conn:
        annotation_after_creator_edit = conn.execute(
            """
            SELECT visibility_json, created_by_type, created_by_id, target_id, current_revision
            FROM annotations
            WHERE annotation_id = ?
            """,
            (annotation_id,),
        ).fetchone()
        revisions_after_creator_edit = conn.execute(
            """
            SELECT revision, created_by_type, created_by_id
            FROM annotation_revisions
            WHERE annotation_id = ?
            ORDER BY revision
            """,
            (annotation_id,),
        ).fetchall()

    monkeypatch.chdir(target_path)
    assert cli.run(["--home", str(home), "annotate", "archive", annotation_id]) == 4
    target_archive_err = capsys.readouterr()

    monkeypatch.chdir(creator_path)
    assert cli.run(["--home", str(home), "annotate", "archive", annotation_id]) == 0
    archive_out = capsys.readouterr()
    assert cli.run(["--home", str(home), "annotate", "remove", annotation_id, "--dry-run"]) == 0
    remove_dry_run_out = capsys.readouterr()
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "annotate",
                "remove",
                annotation_id,
                "--force",
                "--confirm",
                annotation_id,
                "--reason",
                "private complete",
            ]
        )
        == 0
    )
    remove_out = capsys.readouterr()
    remove_fields = _output_field_map(remove_out.out)
    remove_audit_id = remove_fields["audit id"]

    assert cli.run([*audit_args, "audit", "show", remove_audit_id, "--project", project_id]) == 0
    remove_audit_out = capsys.readouterr()
    remove_audit_fields = _output_field_map(remove_audit_out.out)
    remove_audit_metadata = json.loads(remove_audit_fields["sanitized metadata"])

    with sqlite3.connect(home / "alab.db") as conn:
        deleted_annotation_count = conn.execute(
            "SELECT COUNT(*) FROM annotations WHERE annotation_id = ?",
            (annotation_id,),
        ).fetchone()[0]
        deleted_revision_count = conn.execute(
            "SELECT COUNT(*) FROM annotation_revisions WHERE annotation_id = ?",
            (annotation_id,),
        ).fetchone()[0]
        remove_audit_row = conn.execute(
            """
            SELECT actor_type, actor_credential_id, exp_id
            FROM audit_events
            WHERE audit_id = ?
            """,
            (remove_audit_id,),
        ).fetchone()

    assert {
        "add labels": _output_field_labels(add_out.out),
        "add visibility": add_fields.get("visibility"),
        "target show": (
            target_show_err.out,
            _output_field_labels(target_show_err.err),
            "annotation is not visible or not found" in target_show_err.err,
        ),
        "target edit": (
            target_edit_err.out,
            _output_field_labels(target_edit_err.err),
            "annotation is not visible in this context" in target_edit_err.err,
        ),
        "creator show labels": _output_field_labels(creator_show_out.out),
        "creator show body": "body:\n  admin-created private note" in creator_show_out.out,
        "creator edit": (
            creator_edit_out.err,
            _output_field_labels(creator_edit_out.out),
            _output_field_map(creator_edit_out.out).get("revision"),
        ),
        "target archive": (
            target_archive_err.out,
            _output_field_labels(target_archive_err.err),
            "annotation is not visible in this context" in target_archive_err.err,
        ),
        "archive labels": _output_field_labels(archive_out.out),
        "dry-run labels": _output_field_labels(remove_dry_run_out.out),
        "dry-run deleted revisions": _output_field_map(remove_dry_run_out.out).get("deleted revisions"),
        "remove labels": _output_field_labels(remove_out.out),
        "remove deleted revisions": remove_fields.get("deleted revisions"),
        "annotation before creator edit": (
            json.loads(annotation_before_creator_edit[0]),
            annotation_before_creator_edit[1:],
            revisions_before_creator_edit,
        ),
        "annotation after creator edit": (
            json.loads(annotation_after_creator_edit[0]),
            annotation_after_creator_edit[1:],
            revisions_after_creator_edit,
        ),
        "remove audit": (
            remove_audit_out.err,
            _output_field_labels(remove_audit_out.out),
            remove_audit_fields.get("action"),
            remove_audit_fields.get("object type"),
            remove_audit_fields.get("object id"),
            remove_audit_metadata,
        ),
        "admin credential id": admin_credential_id.startswith("cred-"),
        "deleted annotation rows": deleted_annotation_count,
        "deleted revision rows": deleted_revision_count,
        "remove audit actor": remove_audit_row,
    } == {
        "add labels": _documented_success_labels("annotate add"),
        "add visibility": "private",
        "target show": ("", _error_field_labels(), True),
        "target edit": ("", _error_field_labels(), True),
        "creator show labels": _documented_success_labels_with_repeats("observe annotations show", repeats={"revision": 1}),
        "creator show body": True,
        "creator edit": ("", _documented_success_labels("annotate edit"), "2"),
        "target archive": ("", _error_field_labels(), True),
        "archive labels": _documented_success_labels("annotate archive"),
        "dry-run labels": _documented_success_labels("annotate remove", omit={"blocker", "trash cleanup pending"}),
        "dry-run deleted revisions": "2",
        "remove labels": _documented_success_labels("annotate remove", omit={"blocker"}),
        "remove deleted revisions": "2",
        "annotation before creator edit": (
            {"schema_version": 1, "scope": "private", "creator_exp_id": creator_exp_id, "constraints": {}},
            ("admin", admin_credential_id, target_exp_id, 1),
            [(1, "admin", admin_credential_id)],
        ),
        "annotation after creator edit": (
            {"schema_version": 1, "scope": "private", "creator_exp_id": creator_exp_id, "constraints": {}},
            ("admin", admin_credential_id, target_exp_id, 2),
            [(1, "admin", admin_credential_id), (2, "token", creator_exp_id)],
        ),
        "remove audit": (
            "",
            _documented_success_labels("audit show"),
            "remove",
            "annotation",
            annotation_id,
            {
                "deleted_revision_count": 2,
                "filesystem_absent_count": 0,
                "filesystem_target_count": 0,
                "schema_version": 1,
                "trash": [],
            },
        ),
        "admin credential id": True,
        "deleted annotation rows": 0,
        "deleted revision rows": 0,
        "remove audit actor": ("token", creator_token_id, target_exp_id),
    }
    assert admin_credential_id != creator_exp_id


def test_annotation_authorization_matrix_blocks_peer_and_inspection_mutations(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    admin_args = ["--home", str(home), "--key", admin_key]
    creator_path = tmp_path / "annotation-creator"
    target_path = tmp_path / "annotation-target"
    inspection_path = tmp_path / "annotation-inspection"

    def annotation_state(annotation_id: str) -> dict[str, object]:
        with sqlite3.connect(home / "alab.db") as conn:
            row = conn.execute(
                "SELECT status, current_revision FROM annotations WHERE annotation_id = ?",
                (annotation_id,),
            ).fetchone()
            return {
                "row": row,
                "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
                "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
                "annotation revisions": conn.execute(
                    "SELECT COUNT(*) FROM annotation_revisions WHERE annotation_id = ?",
                    (annotation_id,),
                ).fetchone()[0],
                "audits": conn.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE object_type = 'annotation' AND object_id = ?",
                    (annotation_id,),
                ).fetchone()[0],
            }

    assert cli.run([*admin_args, "project", "config", "set", "visibility.scope", '"same_project"', "--project", project_id]) == 0
    capsys.readouterr()
    assert cli.run([*admin_args, "exp", "create", "--project", project_id, "--name", "Annotation Creator", "--path", str(creator_path)]) == 0
    creator_exp_id = _output_field_map(capsys.readouterr().out)["exp id"]
    assert cli.run([*admin_args, "exp", "create", "--project", project_id, "--name", "Annotation Target", "--path", str(target_path)]) == 0
    target_exp_id = _output_field_map(capsys.readouterr().out)["exp id"]

    monkeypatch.chdir(creator_path)
    assert cli.run(["--home", str(home), "annotate", "add", "--target", f"exp:{target_exp_id}", "--body", "project peer note"]) == 0
    project_add_out = capsys.readouterr()
    project_annotation_id = _output_field_map(project_add_out.out)["annotation id"]
    assert _output_field_labels(project_add_out.out) == _documented_success_labels("annotate add")
    assert _output_field_map(project_add_out.out)["visibility"] == "project"

    monkeypatch.chdir(target_path)
    assert cli.run(["--home", str(home), "annotations", "show", project_annotation_id]) == 0
    target_show_project = capsys.readouterr()
    assert _output_field_labels(target_show_project.out) == _documented_success_labels("observe annotations show", omit={"revision"})
    assert "body:\n  project peer note" in target_show_project.out

    peer_blocked_state = annotation_state(project_annotation_id)
    for args in [
        ["annotate", "edit", project_annotation_id, "--body", "target cannot edit project note"],
        ["annotate", "archive", project_annotation_id],
        ["annotate", "unarchive", project_annotation_id],
        ["annotate", "remove", project_annotation_id, "--dry-run"],
    ]:
        assert cli.run(["--home", str(home), *args]) == 4
        blocked_err = capsys.readouterr()
        assert blocked_err.out == ""
        assert _output_field_labels(blocked_err.err) == _error_field_labels()
        assert "error code: SCOPE_VIOLATION" in blocked_err.err
        assert "annotation is not visible in this context" in blocked_err.err
        assert annotation_state(project_annotation_id) == peer_blocked_state

    monkeypatch.chdir(creator_path)
    assert cli.run(["--home", str(home), "annotate", "archive", project_annotation_id]) == 0
    project_archive_out = capsys.readouterr()
    assert _output_field_labels(project_archive_out.out) == _documented_success_labels("annotate archive")
    assert cli.run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-id", target_exp_id, "--query", "project peer note"]) == 0
    archived_default_list = capsys.readouterr()
    assert _output_field_labels(archived_default_list.out) == []
    assert project_annotation_id not in archived_default_list.out
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "annotations",
                "list",
                "--target-type",
                "experiment",
                "--target-id",
                target_exp_id,
                "--query",
                "project peer note",
                "--include-archived",
            ]
        )
        == 0
    )
    archived_included_list = capsys.readouterr()
    assert _output_field_labels(archived_included_list.out) == _documented_success_labels("observe annotations list", omit={"revision"})
    assert f"annotation id: {project_annotation_id}" in archived_included_list.out
    assert "status: archived" in archived_included_list.out

    monkeypatch.chdir(target_path)
    assert cli.run(["--home", str(home), "annotations", "show", project_annotation_id]) == 0
    target_archived_show = capsys.readouterr()
    assert "status: archived" in target_archived_show.out
    archived_peer_blocked_state = annotation_state(project_annotation_id)
    for args in [
        ["annotate", "unarchive", project_annotation_id],
        ["annotate", "remove", project_annotation_id, "--dry-run"],
    ]:
        assert cli.run(["--home", str(home), *args]) == 4
        archived_peer_err = capsys.readouterr()
        assert archived_peer_err.out == ""
        assert _output_field_labels(archived_peer_err.err) == _error_field_labels()
        assert "error code: SCOPE_VIOLATION" in archived_peer_err.err
        assert annotation_state(project_annotation_id) == archived_peer_blocked_state

    monkeypatch.chdir(creator_path)
    assert cli.run(["--home", str(home), "annotate", "unarchive", project_annotation_id]) == 0
    assert _output_field_labels(capsys.readouterr().out) == _documented_success_labels("annotate unarchive")

    monkeypatch.chdir(tmp_path)
    assert cli.run([*admin_args, "project", "config", "set", "visibility.scope", '"none"', "--project", project_id]) == 0
    capsys.readouterr()
    monkeypatch.chdir(creator_path)
    assert cli.run(["--home", str(home), "annotations", "show", project_annotation_id]) == 4
    target_capped_err = capsys.readouterr()
    assert target_capped_err.out == ""
    assert _output_field_labels(target_capped_err.err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in target_capped_err.err
    assert "annotation is not visible or not found" in target_capped_err.err
    assert annotation_state(project_annotation_id)["row"] == ("active", 1)

    monkeypatch.chdir(tmp_path)
    assert cli.run([*admin_args, "project", "config", "set", "visibility.scope", '"same_project"', "--project", project_id]) == 0
    capsys.readouterr()
    monkeypatch.chdir(creator_path)
    assert cli.run(["--home", str(home), "annotate", "add", "--target", f"exp:{target_exp_id}", "--body", "private peer note", "--private"]) == 0
    private_add_out = capsys.readouterr()
    private_annotation_id = _output_field_map(private_add_out.out)["annotation id"]
    assert _output_field_map(private_add_out.out)["visibility"] == "private"
    with sqlite3.connect(home / "alab.db") as conn:
        private_visibility_json = conn.execute(
            "SELECT visibility_json FROM annotations WHERE annotation_id = ?",
            (private_annotation_id,),
        ).fetchone()[0]
    assert json.loads(private_visibility_json) == {
        "schema_version": 1,
        "scope": "private",
        "creator_exp_id": creator_exp_id,
        "constraints": {},
    }
    assert cli.run(["--home", str(home), "annotate", "archive", private_annotation_id]) == 0
    assert _output_field_labels(capsys.readouterr().out) == _documented_success_labels("annotate archive")

    monkeypatch.chdir(target_path)
    private_peer_blocked_state = annotation_state(private_annotation_id)
    for args in [
        ["annotations", "show", private_annotation_id],
        ["annotate", "edit", private_annotation_id, "--body", "target cannot edit private note"],
        ["annotate", "archive", private_annotation_id],
        ["annotate", "unarchive", private_annotation_id],
        ["annotate", "remove", private_annotation_id, "--dry-run"],
    ]:
        assert cli.run(["--home", str(home), *args]) == 4
        private_peer_err = capsys.readouterr()
        assert private_peer_err.out == ""
        assert _output_field_labels(private_peer_err.err) == _error_field_labels()
        assert "error code: SCOPE_VIOLATION" in private_peer_err.err
        assert annotation_state(private_annotation_id) == private_peer_blocked_state

    monkeypatch.chdir(tmp_path)
    assert cli.run([*admin_args, "exp", "checkout", target_exp_id, "--project", project_id, "--path", str(inspection_path), "--commit", "latest"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(inspection_path)
    assert cli.run(["--home", str(home), "annotations", "show", project_annotation_id]) == 0
    inspection_show = capsys.readouterr()
    assert "body:\n  project peer note" in inspection_show.out

    inspection_blocked_state = annotation_state(project_annotation_id)
    for args in [
        ["annotate", "add", "--target", f"exp:{target_exp_id}", "--body", "inspection cannot add"],
        ["annotate", "edit", project_annotation_id, "--body", "inspection cannot edit"],
        ["annotate", "archive", project_annotation_id],
        ["annotate", "unarchive", project_annotation_id],
        ["annotate", "remove", project_annotation_id, "--dry-run"],
    ]:
        assert cli.run(["--home", str(home), *args]) == 4
        inspection_err = capsys.readouterr()
        assert inspection_err.out == ""
        assert _output_field_labels(inspection_err.err) == _error_field_labels()
        assert "error code: COMMAND_UNAVAILABLE" in inspection_err.err
        assert annotation_state(project_annotation_id) == inspection_blocked_state


def test_run_observe_success_fields_follow_cli_spec(tmp_path: Path, monkeypatch, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "run-field-worktree"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Run Field Contract",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "field contract"]) == 0
    run_out = capsys.readouterr()
    run_id = _output_field_map(run_out.out)["run id"]

    assert cli.run(["--home", str(home), "--key", admin_key, "observe", "runs", "list", "--project", project_id]) == 0
    list_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "observe", "runs", "show", run_id, "--project", project_id]) == 0
    show_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "--key", admin_key, "observe", "runs", "archive", run_id, "--project", project_id]) == 0
    archive_out = capsys.readouterr()
    archive_fields = _output_field_map(archive_out.out)
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", archive_fields["audit id"], "--project", project_id]) == 0
    archive_audit_out = capsys.readouterr()
    archive_audit_fields = _output_field_map(archive_audit_out.out)
    archive_audit_metadata = json.loads(archive_audit_fields["sanitized metadata"])

    assert cli.run(["--home", str(home), "--key", admin_key, "observe", "runs", "unarchive", run_id, "--project", project_id]) == 0
    unarchive_out = capsys.readouterr()
    unarchive_fields = _output_field_map(unarchive_out.out)
    assert cli.run(["--home", str(home), "--key", root_key, "audit", "show", unarchive_fields["audit id"], "--project", project_id]) == 0
    unarchive_audit_out = capsys.readouterr()
    unarchive_audit_fields = _output_field_map(unarchive_audit_out.out)
    unarchive_audit_metadata = json.loads(unarchive_audit_fields["sanitized metadata"])

    assert {
        "run": (run_out.err, _output_field_labels(run_out.out), _documented_success_labels("run --message", omit={"warning code"})),
        "observe runs list": (list_out.err, _output_field_labels(list_out.out), _documented_success_labels("observe runs list", omit={"warning code"})),
        "observe runs show": (show_out.err, _output_field_labels(show_out.out), _documented_success_labels("observe runs show", omit={"warning code"})),
        "observe runs archive": (
            archive_out.err,
            _output_field_labels(archive_out.out),
            archive_fields.get("archive status"),
        ),
        "observe runs unarchive": (
            unarchive_out.err,
            _output_field_labels(unarchive_out.out),
            unarchive_fields.get("archive status"),
        ),
        "observe runs archive audit": (
            archive_audit_out.err,
            _output_field_labels(archive_audit_out.out),
            archive_audit_fields.get("audit id"),
            archive_audit_fields.get("action"),
            archive_audit_fields.get("object type"),
            archive_audit_fields.get("object id"),
            archive_audit_metadata,
        ),
        "observe runs unarchive audit": (
            unarchive_audit_out.err,
            _output_field_labels(unarchive_audit_out.out),
            unarchive_audit_fields.get("audit id"),
            unarchive_audit_fields.get("action"),
            unarchive_audit_fields.get("object type"),
            unarchive_audit_fields.get("object id"),
            unarchive_audit_metadata,
        ),
    } == {
        "run": ("", _documented_success_labels("run --message", omit={"warning code"}), _documented_success_labels("run --message", omit={"warning code"})),
        "observe runs list": ("", _documented_success_labels("observe runs list", omit={"warning code"}), _documented_success_labels("observe runs list", omit={"warning code"})),
        "observe runs show": ("", _documented_success_labels("observe runs show", omit={"warning code"}), _documented_success_labels("observe runs show", omit={"warning code"})),
        "observe runs archive": (
            "",
            _documented_success_labels("observe runs archive"),
            "archived",
        ),
        "observe runs unarchive": (
            "",
            _documented_success_labels("observe runs unarchive"),
            "active",
        ),
        "observe runs archive audit": (
            "",
            _documented_success_labels("audit show"),
            archive_fields["audit id"],
            "archive",
            "run",
            run_id,
            {
                "archive_status": "archived",
                "archived_at": archive_fields["archived at"],
                "previous_archive_status": "active",
                "schema_version": 1,
            },
        ),
        "observe runs unarchive audit": (
            "",
            _documented_success_labels("audit show"),
            unarchive_fields["audit id"],
            "unarchive",
            "run",
            run_id,
            {
                "archive_status": "active",
                "previous_archive_status": "archived",
                "schema_version": 1,
                "unarchived_at": unarchive_fields["unarchived at"],
            },
        ),
    }


def test_project_baseline_result_failures_follow_cli_spec(tmp_path: Path, monkeypatch, capsys) -> None:
    project_init_failure_labels = [
        *_documented_success_labels("project init", omit={"next", "warning code"}),
        "error code",
        "exit code",
        "reason",
        "next",
    ]
    config_set_failure_labels = [
        *_documented_success_labels("project config set", omit={"next", "warning code"}),
        "error code",
        "exit code",
        "reason",
        "next",
    ]
    config_import_failure_labels = [
        *_documented_success_labels("project config import", omit={"next", "warning code"}),
        "error code",
        "exit code",
        "reason",
        "next",
    ]
    monkeypatch.setenv("ALAB_DEBUG", "1")

    for case in _baseline_result_failure_cases():
        runner = case["runner"]
        case_name = str(case["name"])
        case_dir = tmp_path / f"project-init-{case_name}"
        case_dir.mkdir()
        home = case_dir / "home"
        source = case_dir / "source"
        source.mkdir()
        (source / "main.py").write_text("print('baseline')\n", encoding="utf-8")
        config = case_dir / "alab.project.toml"
        _write_local_project_config(
            config,
            name=f"Project Init Result Failure {case_name}",
            runner_command=runner["command"],
            working_directory=str(runner["working_directory"]),
            timeout_seconds=int(runner["timeout_seconds"]),
        )

        assert cli.run(["--home", str(home), "auth", "init"]) == 0
        root_key = _output_field_map(capsys.readouterr().out)["root key"]
        assert (
            cli.run(
                [
                    "--home",
                    str(home),
                    "--key",
                    root_key,
                    "project",
                    "init",
                    "local",
                    "--config",
                    str(config),
                    "--source-path",
                    str(source),
                ]
            )
            == 1
        )
        init_out = capsys.readouterr()
        init_fields = _output_field_map(init_out.out)
        project_id = init_fields["project id"]
        validation_id = init_fields["validation id"]

        assert {
            "stderr": init_out.err,
            "traceback": "Traceback" in init_out.out,
            "labels": _output_field_labels(init_out.out),
            "project status": init_fields.get("project status"),
            "validation status": init_fields.get("validation status"),
            "admin key rendered": init_fields.get("admin key") not in {None, "none"},
            "error code": init_fields.get("error code"),
            "exit code lines": re.findall(r"^exit code: (.+)$", init_out.out, re.MULTILINE),
            "reason": init_fields.get("reason"),
        } == {
            "stderr": "",
            "traceback": False,
            "labels": project_init_failure_labels,
            "project status": "invalid",
            "validation status": case["validation status"],
            "admin key rendered": True,
            "error code": "BASELINE_VALIDATION_FAILED",
            "exit code lines": ["1"],
            "reason": f"baseline validation status is {case['validation status']}",
        }

        with sqlite3.connect(home / "alab.db") as conn:
            project_row = conn.execute(
                "SELECT status, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            config_row = conn.execute(
                "SELECT validation_status FROM project_config_versions WHERE project_id = ? AND version = 1",
                (project_id,),
            ).fetchone()
            validation_row = conn.execute(
                """
                SELECT status, exit_code, reward_parse_status, record_json
                FROM project_validations
                WHERE validation_id = ?
                """,
                (validation_id,),
            ).fetchone()
        assert validation_row is not None
        record_json = json.loads(validation_row[3])
        assert {
            "project": project_row,
            "config validation": config_row[0],
            "validation status": validation_row[0],
            "exit code": validation_row[1],
            "reward parse status": validation_row[2],
            "failure": record_json["failure"],
        } == {
            "project": ("invalid", None, None),
            "config validation": case["validation status"],
            "validation status": case["validation status"],
            "exit code": case["runner exit code"],
            "reward parse status": case["reward parse status"],
            "failure": case["failure"],
        }

    for command_name, expected_labels in [
        ("project config set", config_set_failure_labels),
        ("project config import", config_import_failure_labels),
    ]:
        for case in _baseline_result_failure_cases():
            runner = case["runner"]
            case_name = str(case["name"])
            case_dir = tmp_path / f"{command_name.replace(' ', '-')}-{case_name}"
            case_dir.mkdir()
            home, _root_key, project_id, admin_key = _init_capability_project(case_dir, capsys)
            if command_name == "project config set" and case_name == "timeout":
                assert (
                    cli.run(
                        [
                            "--home",
                            str(home),
                            "--key",
                            admin_key,
                            "project",
                            "config",
                            "set",
                            "runner.timeout_seconds",
                            "1",
                            "--project",
                            project_id,
                        ]
                    )
                    == 0
                )
                capsys.readouterr()

            with sqlite3.connect(home / "alab.db") as conn:
                project_before = conn.execute(
                    """
                    SELECT status, latest_attempted_config_version, active_valid_config_version,
                      active_validation_id
                    FROM projects
                    WHERE project_id = ?
                    """,
                    (project_id,),
                ).fetchone()
                validation_count_before = conn.execute(
                    "SELECT COUNT(*) FROM project_validations WHERE project_id = ?",
                    (project_id,),
                ).fetchone()[0]
                current_config = json.loads(
                    conn.execute(
                        """
                        SELECT canonical_config_json
                        FROM project_config_versions
                        WHERE project_id = ? AND version = ?
                        """,
                        (project_id, project_before[1]),
                    ).fetchone()[0]
                )

            if command_name == "project config set":
                if case_name == "error":
                    command_args = ["project", "config", "set", "runner.working_directory", json.dumps(runner["working_directory"])]
                else:
                    command_args = ["project", "config", "set", "runner.command", json.dumps(runner["command"])]
            else:
                current_config["runner"]["command"] = runner["command"]
                current_config["runner"]["working_directory"] = runner["working_directory"]
                current_config["runner"]["timeout_seconds"] = runner["timeout_seconds"]
                import_config = case_dir / "import.toml"
                import_config.write_text(services.dumps_toml(current_config), encoding="utf-8")
                command_args = ["project", "config", "import", "--config", str(import_config)]

            assert cli.run(["--home", str(home), "--key", admin_key, *command_args, "--project", project_id]) == 1
            config_out = capsys.readouterr()
            config_fields = _output_field_map(config_out.out)
            latest_attempted = int(config_fields["latest attempted config version"])

            assert {
                "stderr": config_out.err,
                "traceback": "Traceback" in config_out.out,
                "labels": _output_field_labels(config_out.out),
                "previous active": config_fields.get("previous active config version"),
                "latest attempted": latest_attempted,
                "runtime affecting": config_fields.get("runtime affecting"),
                "validation status": config_fields.get("validation status"),
                "project status": config_fields.get("project status"),
                "error code": config_fields.get("error code"),
                "exit code lines": re.findall(r"^exit code: (.+)$", config_out.out, re.MULTILINE),
                "reason": config_fields.get("reason"),
                "next": config_fields.get("next"),
            } == {
                "stderr": "",
                "traceback": False,
                "labels": expected_labels,
                "previous active": str(project_before[2]),
                "latest attempted": project_before[1] + 1,
                "runtime affecting": "true",
                "validation status": case["validation status"],
                "project status": "invalid",
                "error code": "BASELINE_VALIDATION_FAILED",
                "exit code lines": ["1"],
                "reason": f"baseline validation status is {case['validation status']}",
                "next": "alab project validate",
            }

            with sqlite3.connect(home / "alab.db") as conn:
                project_after = conn.execute(
                    """
                    SELECT status, latest_attempted_config_version, active_valid_config_version,
                      active_validation_id
                    FROM projects
                    WHERE project_id = ?
                    """,
                    (project_id,),
                ).fetchone()
                validation_count_after = conn.execute(
                    "SELECT COUNT(*) FROM project_validations WHERE project_id = ?",
                    (project_id,),
                ).fetchone()[0]
                config_row = conn.execute(
                    """
                    SELECT validation_status
                    FROM project_config_versions
                    WHERE project_id = ? AND version = ?
                    """,
                    (project_id, latest_attempted),
                ).fetchone()
                validation_row = conn.execute(
                    """
                    SELECT status, exit_code, reward_parse_status, record_json
                    FROM project_validations
                    WHERE project_id = ? AND config_version = ?
                    """,
                    (project_id, latest_attempted),
                ).fetchone()
            assert validation_row is not None
            record_json = json.loads(validation_row[3])
            assert {
                "project": project_after,
                "config validation": config_row[0],
                "validation count delta": validation_count_after - validation_count_before,
                "validation status": validation_row[0],
                "exit code": validation_row[1],
                "reward parse status": validation_row[2],
                "failure": record_json["failure"],
            } == {
                "project": ("invalid", latest_attempted, project_before[2], project_before[3]),
                "config validation": case["validation status"],
                "validation count delta": 1,
                "validation status": case["validation status"],
                "exit code": case["runner exit code"],
                "reward parse status": case["reward parse status"],
                "failure": case["failure"],
            }


def test_project_env_secret_baseline_result_failures_follow_cli_spec(tmp_path: Path, monkeypatch, capsys) -> None:
    def failure_labels(command: str) -> list[str]:
        return [
            *_documented_success_labels(command),
            "error code",
            "exit code",
            "reason",
            "next",
        ]

    def apply_failing_runner_config(home: Path, admin_key: str, project_id: str, runner: dict[str, object]) -> None:
        mutations: list[tuple[str, str]] = []
        if runner["timeout_seconds"] != 30:
            mutations.append(("runner.timeout_seconds", str(runner["timeout_seconds"])))
        if runner["working_directory"] != ".":
            mutations.append(("runner.working_directory", json.dumps(runner["working_directory"])))
        if runner["command"] != [sys.executable, "-c", "print('ok')"]:
            mutations.append(("runner.command", json.dumps(runner["command"])))
        for field, value in mutations:
            assert (
                cli.run(
                    [
                        "--home",
                        str(home),
                        "--key",
                        admin_key,
                        "project",
                        "config",
                        "set",
                        field,
                        value,
                        "--project",
                        project_id,
                        "--skip-baseline-test",
                    ]
                )
                == 0
            )
            capsys.readouterr()

    command_specs = [
        {
            "command": "project env set",
            "args": ["project", "env", "set", "CONTRACT_ENV", "visible-value"],
            "seed": None,
            "object type": "project_env",
            "name field": "env name",
            "expected name": "CONTRACT_ENV",
            "action": "set",
            "raw secret": None,
        },
        {
            "command": "project env unset",
            "args": ["project", "env", "unset", "CONTRACT_ENV"],
            "seed": "env",
            "object type": "project_env",
            "name field": "env name",
            "expected name": "CONTRACT_ENV",
            "action": "unset",
            "raw secret": None,
        },
        {
            "command": "project secret set",
            "args": ["project", "secret", "set", "CONTRACT_SECRET", "--value-stdin"],
            "seed": None,
            "object type": "project_secret",
            "name field": "secret name",
            "expected name": "CONTRACT_SECRET",
            "action": "set",
            "raw secret": "contract-secret-value",
        },
        {
            "command": "project secret unset",
            "args": ["project", "secret", "unset", "CONTRACT_SECRET"],
            "seed": "secret",
            "object type": "project_secret",
            "name field": "secret name",
            "expected name": "CONTRACT_SECRET",
            "action": "unset",
            "raw secret": "contract-secret-value",
        },
    ]
    monkeypatch.setenv("ALAB_DEBUG", "1")

    for command_spec in command_specs:
        for case in _baseline_result_failure_cases():
            runner = case["runner"]
            command_name = str(command_spec["command"])
            case_name = str(case["name"])
            case_dir = tmp_path / f"{command_name.replace(' ', '-')}-{case_name}"
            case_dir.mkdir()
            home, _root_key, project_id, admin_key = _init_capability_project(case_dir, capsys)

            if command_spec["seed"] == "env":
                assert (
                    cli.run(
                        [
                            "--home",
                            str(home),
                            "--key",
                            admin_key,
                            "project",
                            "env",
                            "set",
                            "CONTRACT_ENV",
                            "visible-value",
                            "--project",
                            project_id,
                            "--skip-baseline-test",
                        ]
                    )
                    == 0
                )
                capsys.readouterr()
            elif command_spec["seed"] == "secret":
                monkeypatch.setattr(sys, "stdin", io.StringIO("contract-secret-value\n"))
                assert (
                    cli.run(
                        [
                            "--home",
                            str(home),
                            "--key",
                            admin_key,
                            "project",
                            "secret",
                            "set",
                            "CONTRACT_SECRET",
                            "--value-stdin",
                            "--project",
                            project_id,
                            "--skip-baseline-test",
                        ]
                    )
                    == 0
                )
                capsys.readouterr()

            apply_failing_runner_config(home, admin_key, project_id, runner)
            with sqlite3.connect(home / "alab.db") as conn:
                project_before = conn.execute(
                    """
                    SELECT status, latest_attempted_config_version, active_valid_config_version,
                      active_validation_id
                    FROM projects
                    WHERE project_id = ?
                    """,
                    (project_id,),
                ).fetchone()
                validation_count_before = conn.execute(
                    "SELECT COUNT(*) FROM project_validations WHERE project_id = ?",
                    (project_id,),
                ).fetchone()[0]

            if command_spec["raw secret"] and command_spec["action"] == "set":
                monkeypatch.setattr(sys, "stdin", io.StringIO(f"{command_spec['raw secret']}\n"))
            assert (
                cli.run(
                    [
                        "--home",
                        str(home),
                        "--key",
                        admin_key,
                        *command_spec["args"],
                        "--project",
                        project_id,
                    ]
                )
                == 1
            )
            mutation_out = capsys.readouterr()
            fields = _output_field_map(mutation_out.out)
            latest_attempted = int(fields["config version"])

            assert {
                "stderr": mutation_out.err,
                "traceback": "Traceback" in mutation_out.out,
                "labels": _output_field_labels(mutation_out.out),
                "object type": _output_object_type(mutation_out.out),
                "project id": fields.get("project id"),
                "config version": latest_attempted,
                "name": fields.get(str(command_spec["name field"])),
                "action": fields.get("action"),
                "runtime affecting": fields.get("runtime affecting"),
                "validation status": fields.get("validation status"),
                "error code": fields.get("error code"),
                "exit code": fields.get("exit code"),
                "reason": fields.get("reason"),
                "next": fields.get("next"),
                "raw secret leaked": bool(command_spec["raw secret"] and str(command_spec["raw secret"]) in mutation_out.out),
            } == {
                "stderr": "",
                "traceback": False,
                "labels": failure_labels(command_name),
                "object type": command_spec["object type"],
                "project id": project_id,
                "config version": project_before[1] + 1,
                "name": command_spec["expected name"],
                "action": command_spec["action"],
                "runtime affecting": "true",
                "validation status": case["validation status"],
                "error code": "BASELINE_VALIDATION_FAILED",
                "exit code": "1",
                "reason": f"baseline validation status is {case['validation status']}",
                "next": "alab project validate",
                "raw secret leaked": False,
            }

            with sqlite3.connect(home / "alab.db") as conn:
                project_after = conn.execute(
                    """
                    SELECT status, latest_attempted_config_version, active_valid_config_version,
                      active_validation_id
                    FROM projects
                    WHERE project_id = ?
                    """,
                    (project_id,),
                ).fetchone()
                validation_count_after = conn.execute(
                    "SELECT COUNT(*) FROM project_validations WHERE project_id = ?",
                    (project_id,),
                ).fetchone()[0]
                config_row = conn.execute(
                    """
                    SELECT validation_status
                    FROM project_config_versions
                    WHERE project_id = ? AND version = ?
                    """,
                    (project_id, latest_attempted),
                ).fetchone()
                validation_row = conn.execute(
                    """
                    SELECT status, exit_code, reward_parse_status, record_json
                    FROM project_validations
                    WHERE project_id = ? AND config_version = ?
                    """,
                    (project_id, latest_attempted),
                ).fetchone()
            assert validation_row is not None
            record_json = json.loads(validation_row[3])
            assert {
                "project": project_after,
                "config validation": config_row[0],
                "validation count delta": validation_count_after - validation_count_before,
                "validation status": validation_row[0],
                "exit code": validation_row[1],
                "reward parse status": validation_row[2],
                "failure": record_json["failure"],
            } == {
                "project": ("invalid", latest_attempted, project_before[2], project_before[3]),
                "config validation": case["validation status"],
                "validation count delta": 1,
                "validation status": case["validation status"],
                "exit code": case["runner exit code"],
                "reward parse status": case["reward parse status"],
                "failure": case["failure"],
            }


def test_run_result_failures_follow_cli_spec(tmp_path: Path, monkeypatch, capsys) -> None:
    expected_run_failure_labels = [
        *_documented_success_labels("run --message", omit={"warning code", "next"}),
        "error code",
        "exit code",
        "reason",
        "next",
    ]
    cases = [
        {
            "name": "failed",
            "source_files": {"main.py": "print('baseline')\n"},
            "runner_command": [sys.executable, "main.py"],
            "working_directory": ".",
            "timeout_seconds": 30,
            "mutation": "exit",
            "run status": "failed",
            "runner exit code": "7",
            "db exit code": 7,
            "reward parse status": "parsed",
            "error code": "RUNNER_FAILED",
            "reason": "runner exited with code 7",
        },
        {
            "name": "timeout",
            "source_files": {"main.py": "print('baseline')\n"},
            "runner_command": [sys.executable, "main.py"],
            "working_directory": ".",
            "timeout_seconds": 1,
            "mutation": "sleep",
            "run status": "timeout",
            "runner exit code": "none",
            "db exit code": None,
            "reward parse status": "not_attempted",
            "error code": "RUNNER_TIMEOUT",
            "reason": "runner timed out",
        },
        {
            "name": "error",
            "source_files": {"work/main.py": "print('baseline')\n"},
            "runner_command": [sys.executable, "main.py"],
            "working_directory": "work",
            "timeout_seconds": 30,
            "mutation": "remove-working-directory",
            "run status": "error",
            "runner exit code": "none",
            "db exit code": None,
            "reward parse status": "not_attempted",
            "error code": "RUNNER_ERROR",
            "reason": "runner working directory does not exist",
        },
    ]
    monkeypatch.setenv("ALAB_DEBUG", "1")

    for case in cases:
        monkeypatch.chdir(tmp_path)
        home, admin_key, project_id, worktree_path = _init_run_result_failure_project(
            tmp_path,
            capsys,
            name=str(case["name"]),
            source_files=case["source_files"],
            runner_command=case["runner_command"],
            working_directory=str(case["working_directory"]),
            timeout_seconds=int(case["timeout_seconds"]),
        )
        if case["mutation"] == "exit":
            (worktree_path / "main.py").write_text("import sys\nsys.exit(7)\n", encoding="utf-8")
        elif case["mutation"] == "sleep":
            (worktree_path / "main.py").write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
        elif case["mutation"] == "remove-working-directory":
            (worktree_path / "work" / "main.py").unlink()
            (worktree_path / "work").rmdir()

        monkeypatch.chdir(worktree_path)
        assert cli.run(["--home", str(home), "run", "--message", f"{case['name']} result failure"]) == 1
        run_out = capsys.readouterr()
        run_fields = _output_field_map(run_out.out)
        run_id = run_fields["run id"]

        assert {
            "stderr": run_out.err,
            "traceback": "Traceback" in run_out.out,
            "labels": _output_field_labels(run_out.out),
            "status": run_fields.get("run status"),
            "reward parse": run_fields.get("reward parse status"),
            "error code": run_fields.get("error code"),
            "reason": run_fields.get("reason"),
            "exit code lines": re.findall(r"^exit code: (.+)$", run_out.out, re.MULTILINE),
        } == {
            "stderr": "",
            "traceback": False,
            "labels": expected_run_failure_labels,
            "status": case["run status"],
            "reward parse": case["reward parse status"],
            "error code": case["error code"],
            "reason": case["reason"],
            "exit code lines": [case["runner exit code"], "1"],
        }

        with sqlite3.connect(home / "alab.db") as conn:
            row = conn.execute("SELECT status, exit_code, reward_parse_status, record_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        assert row is not None
        record_json = json.loads(row[3])
        assert {
            "status": row[0],
            "exit code": row[1],
            "reward parse status": row[2],
            "failure": record_json["failure"],
        } == {
            "status": case["run status"],
            "exit code": case["db exit code"],
            "reward parse status": case["reward parse status"],
            "failure": case["reason"],
        }

        assert cli.run(["--home", str(home), "--key", admin_key, "observe", "runs", "show", run_id, "--project", project_id]) == 0
        show_out = capsys.readouterr()
        show_fields = _output_field_map(show_out.out)
        assert {
            "stderr": show_out.err,
            "labels": _output_field_labels(show_out.out),
            "status": show_fields.get("run status"),
            "reward parse": show_fields.get("reward parse status"),
            "exit code": show_fields.get("exit code"),
        } == {
            "stderr": "",
            "labels": _documented_success_labels("observe runs show", omit={"warning code"}),
            "status": case["run status"],
            "reward parse": case["reward parse status"],
            "exit code": case["runner exit code"],
        }


def test_run_reward_parse_failures_cover_nonfinite_and_nonzero_exit(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home-reward-parse-matrix"
    source = tmp_path / "source-reward-parse-matrix"
    config = tmp_path / "alab.reward-parse-matrix.toml"
    worktree_path = tmp_path / "worktree-reward-parse-matrix"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

Path(os.environ["ALAB_RUN_DIR"], "reward.txt").write_text("1.0", encoding="utf-8")
print("baseline reward")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Reward Parse Matrix"
task = "Exercise saved reward parse failures"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "file"
direction = "maximize"
primary_metric = "reward"
path = "run:reward.txt"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]
    assert cli.run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_fields = _output_field_map(capsys.readouterr().out)
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                project_fields["admin key"],
                "exp",
                "create",
                "--project",
                project_fields["project id"],
                "--name",
                "Reward Parse Matrix",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    expected_run_failure_labels = [
        *_documented_success_labels("run --message", omit={"warning code", "next"}),
        "error code",
        "exit code",
        "reason",
        "next",
    ]
    cases = [
        ("nan-zero", "NaN", 0, "error", "REWARD_PARSE_ERROR", "reward parse status is invalid"),
        ("infinity-zero", "Infinity", 0, "error", "REWARD_PARSE_ERROR", "reward parse status is invalid"),
        ("empty-zero", "", 0, "error", "REWARD_PARSE_ERROR", "reward parse status is invalid"),
        ("nonnumeric-zero", "not-a-number", 0, "error", "REWARD_PARSE_ERROR", "reward parse status is invalid"),
        ("nan-nonzero", "NaN", 7, "failed", "RUNNER_FAILED", "runner exited with code 7"),
    ]
    monkeypatch.setenv("ALAB_DEBUG", "1")

    for name, reward_text, runner_exit_code, run_status, error_code, reason in cases:
        monkeypatch.chdir(worktree_path)
        (worktree_path / "main.py").write_text(
            f"""
import os
import sys
from pathlib import Path

Path(os.environ["ALAB_RUN_DIR"], "reward.txt").write_text({json.dumps(reward_text)}, encoding="utf-8")
print({json.dumps(name)})
sys.exit({runner_exit_code})
""".strip()
            + "\n",
            encoding="utf-8",
        )

        assert cli.run(["--home", str(home), "run", "--message", f"{name} reward parse failure"]) == 1
        run_out = capsys.readouterr()
        run_fields = _output_field_map(run_out.out)
        run_id = run_fields["run id"]

        assert {
            "stderr": run_out.err,
            "traceback": "Traceback" in run_out.out,
            "labels": _output_field_labels(run_out.out),
            "run status": run_fields.get("run status"),
            "reward parse": run_fields.get("reward parse status"),
            "error code": run_fields.get("error code"),
            "reason": run_fields.get("reason"),
            "exit code lines": re.findall(r"^exit code: (.+)$", run_out.out, re.MULTILINE),
        } == {
            "stderr": "",
            "traceback": False,
            "labels": expected_run_failure_labels,
            "run status": run_status,
            "reward parse": "invalid",
            "error code": error_code,
            "reason": reason,
            "exit code lines": [str(runner_exit_code), "1"],
        }

        with sqlite3.connect(home / "alab.db") as conn:
            row = conn.execute(
                """
                SELECT status, exit_code, reward_value, reward_parse_status, record_json
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        assert row is not None
        record_json = json.loads(row[4])
        assert {
            "status": row[0],
            "exit code": row[1],
            "reward value": row[2],
            "reward parse status": row[3],
            "reward record": record_json["reward"],
            "failure": record_json["failure"],
        } == {
            "status": run_status,
            "exit code": runner_exit_code,
            "reward value": None,
            "reward parse status": "invalid",
            "reward record": {"type": "file", "value": None},
            "failure": reason,
        }

    before_submit_counts = _database_table_counts(home)
    monkeypatch.chdir(worktree_path)
    (worktree_path / "main.py").write_text(
        """
print("missing submit reward")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "submit",
                "--message",
                "missing file reward submit",
                "--summary",
                "done",
                "--feedback",
                "ok",
                "--ref",
                "none",
                "--rerun",
            ]
        )
        == 1
    )
    submit_out = capsys.readouterr()
    submit_fields = _output_field_map(submit_out.out)
    submit_reason = submit_fields["reason"]
    submit_run_match = re.match(r"final run (run-[^ ]+) (.+)$", submit_reason)
    assert submit_run_match is not None
    submit_run_id = submit_run_match.group(1)

    assert {
        "stderr": submit_out.err,
        "traceback": "Traceback" in submit_out.out,
        "labels": _output_field_labels(submit_out.out),
        "accepted": submit_fields.get("submit accepted"),
        "final run id": submit_fields.get("final run id"),
        "experiment status": submit_fields.get("experiment status"),
        "summary stored": submit_fields.get("summary stored"),
        "feedback stored": submit_fields.get("feedback stored"),
        "ref": submit_fields.get("ref"),
        "error code": submit_fields.get("error code"),
        "exit code": submit_fields.get("exit code"),
        "reason suffix": submit_run_match.group(2),
        "next": submit_fields.get("next"),
    } == {
        "stderr": "",
        "traceback": False,
        "labels": [*_documented_success_labels("submit"), "error code", "exit code", "reason", "next"],
        "accepted": "false",
        "final run id": "none",
        "experiment status": "open",
        "summary stored": "false",
        "feedback stored": "false",
        "ref": "none",
        "error code": "REWARD_PARSE_ERROR",
        "exit code": "1",
        "reason suffix": "status is error: reward parse status is invalid",
        "next": "fix the experiment and rerun alab submit --rerun",
    }

    with sqlite3.connect(home / "alab.db") as conn:
        exp_id = submit_fields["exp id"]
        experiment_row = conn.execute(
            "SELECT status, final_run_id, final_commit FROM experiments WHERE exp_id = ?",
            (exp_id,),
        ).fetchone()
        submission_count = conn.execute(
            "SELECT COUNT(*) FROM experiment_submissions WHERE exp_id = ?",
            (exp_id,),
        ).fetchone()[0]
        submit_run_row = conn.execute(
            """
            SELECT status, exit_code, reward_value, reward_parse_status, record_json
            FROM runs
            WHERE run_id = ?
            """,
            (submit_run_id,),
        ).fetchone()
    assert experiment_row == ("open", None, None)
    assert submission_count == 0
    assert submit_run_row is not None
    submit_record_json = json.loads(submit_run_row[4])
    assert {
        "status": submit_run_row[0],
        "exit code": submit_run_row[1],
        "reward value": submit_run_row[2],
        "reward parse status": submit_run_row[3],
        "reward record": submit_record_json["reward"],
        "failure": submit_record_json["failure"],
        "submission delta": _database_table_counts(home)["experiment_submissions"] - before_submit_counts["experiment_submissions"],
    } == {
        "status": "error",
        "exit code": 0,
        "reward value": None,
        "reward parse status": "invalid",
        "reward record": {"type": "file", "value": None},
        "failure": "reward parse status is invalid",
        "submission delta": 0,
    }


def test_project_validate_result_failures_follow_cli_spec(tmp_path: Path, monkeypatch, capsys) -> None:
    expected_validation_failure_labels = [
        *_documented_success_labels("project validate", omit={"next", "warning code"}),
        "error code",
        "exit code",
        "reason",
        "next",
    ]
    cases = [
        {
            "name": "failed",
            "mutations": [("runner.command", json.dumps([sys.executable, "-c", "import sys; sys.exit(7)"]))],
            "validation status": "failed",
            "runner exit code": "7",
            "db exit code": 7,
            "reward parse status": "parsed",
            "failure": "runner exited with code 7",
        },
        {
            "name": "timeout",
            "mutations": [
                ("runner.timeout_seconds", "1"),
                ("runner.command", json.dumps([sys.executable, "-c", "import time; time.sleep(5)"])),
            ],
            "validation status": "timeout",
            "runner exit code": "none",
            "db exit code": None,
            "reward parse status": "not_attempted",
            "failure": "runner timed out",
        },
        {
            "name": "error",
            "mutations": [("runner.working_directory", json.dumps("missing"))],
            "validation status": "error",
            "runner exit code": "none",
            "db exit code": None,
            "reward parse status": "not_attempted",
            "failure": "runner working directory does not exist",
        },
    ]
    monkeypatch.setenv("ALAB_DEBUG", "1")

    for case in cases:
        monkeypatch.chdir(tmp_path)
        home, admin_key, project_id = _init_validation_result_failure_project(
            tmp_path,
            capsys,
            name=str(case["name"]),
            config_mutations=case["mutations"],
        )
        with sqlite3.connect(home / "alab.db") as conn:
            project_before = conn.execute(
                "SELECT status, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            validation_count_before = conn.execute(
                "SELECT COUNT(*) FROM project_validations WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]

        assert cli.run(["--home", str(home), "--key", admin_key, "project", "validate", "--project", project_id]) == 1
        validate_out = capsys.readouterr()
        validate_fields = _output_field_map(validate_out.out)
        validation_id = validate_fields["validation id"]

        assert {
            "stderr": validate_out.err,
            "traceback": "Traceback" in validate_out.out,
            "labels": _output_field_labels(validate_out.out),
            "status": validate_fields.get("validation status"),
            "project status": validate_fields.get("project status"),
            "reward parse": validate_fields.get("reward parse status"),
            "error code": validate_fields.get("error code"),
            "reason": validate_fields.get("reason"),
            "exit code lines": re.findall(r"^exit code: (.+)$", validate_out.out, re.MULTILINE),
        } == {
            "stderr": "",
            "traceback": False,
            "labels": expected_validation_failure_labels,
            "status": case["validation status"],
            "project status": "invalid",
            "reward parse": case["reward parse status"],
            "error code": "BASELINE_VALIDATION_FAILED",
            "reason": f"baseline validation status is {case['validation status']}",
            "exit code lines": [case["runner exit code"], "1"],
        }

        with sqlite3.connect(home / "alab.db") as conn:
            validation_row = conn.execute(
                """
                SELECT status, exit_code, reward_parse_status, record_json
                FROM project_validations
                WHERE validation_id = ?
                """,
                (validation_id,),
            ).fetchone()
            project_after = conn.execute(
                "SELECT status, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            validation_count_after = conn.execute(
                "SELECT COUNT(*) FROM project_validations WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]

        assert validation_row is not None
        record_json = json.loads(validation_row[3])
        assert {
            "status": validation_row[0],
            "exit code": validation_row[1],
            "reward parse status": validation_row[2],
            "failure": record_json["failure"],
            "project": project_after,
            "validation count delta": validation_count_after - validation_count_before,
        } == {
            "status": case["validation status"],
            "exit code": case["db exit code"],
            "reward parse status": case["reward parse status"],
            "failure": case["failure"],
            "project": project_before,
            "validation count delta": 1,
        }


def test_submit_result_failures_follow_cli_spec(tmp_path: Path, monkeypatch, capsys) -> None:
    expected_submit_failure_labels = [
        *_documented_success_labels("submit"),
        "error code",
        "exit code",
        "reason",
        "next",
    ]
    cases = [
        {
            "name": "failed",
            "source_files": {"main.py": "print('baseline')\n"},
            "runner_command": [sys.executable, "main.py"],
            "working_directory": ".",
            "timeout_seconds": 30,
            "mutation": "exit",
            "rerun": True,
            "run status": "failed",
            "runner exit code": 7,
            "reward parse status": "parsed",
            "error code": "RUNNER_FAILED",
            "failure": "runner exited with code 7",
            "reason suffix": "status is failed: runner exited with code 7",
            "next": "fix the experiment and rerun alab submit --rerun",
        },
        {
            "name": "timeout",
            "source_files": {"main.py": "print('baseline')\n"},
            "runner_command": [sys.executable, "main.py"],
            "working_directory": ".",
            "timeout_seconds": 1,
            "mutation": "sleep",
            "rerun": True,
            "run status": "timeout",
            "runner exit code": None,
            "reward parse status": "not_attempted",
            "error code": "RUNNER_TIMEOUT",
            "failure": "runner timed out",
            "reason suffix": "status is timeout: runner timed out",
            "next": "fix the experiment and rerun alab submit --rerun",
        },
        {
            "name": "error",
            "source_files": {"work/main.py": "print('baseline')\n"},
            "runner_command": [sys.executable, "main.py"],
            "working_directory": "work",
            "timeout_seconds": 30,
            "mutation": "remove-working-directory",
            "rerun": True,
            "run status": "error",
            "runner exit code": None,
            "reward parse status": "not_attempted",
            "error code": "RUNNER_ERROR",
            "failure": "runner working directory does not exist",
            "reason suffix": "status is error: runner working directory does not exist",
            "next": "fix the experiment and rerun alab submit --rerun",
        },
        {
            "name": "missing-reusable",
            "source_files": {"main.py": "print('baseline')\n"},
            "runner_command": [sys.executable, "main.py"],
            "working_directory": ".",
            "timeout_seconds": 30,
            "mutation": "none",
            "rerun": False,
            "run status": None,
            "runner exit code": None,
            "reward parse status": None,
            "error code": "RUNNER_FAILED",
            "failure": None,
            "reason suffix": "no reusable passed run for current HEAD",
            "next": "alab submit --rerun ...",
        },
    ]
    monkeypatch.setenv("ALAB_DEBUG", "1")

    for case in cases:
        monkeypatch.chdir(tmp_path)
        home, _admin_key, project_id, worktree_path = _init_run_result_failure_project(
            tmp_path,
            capsys,
            name=f"submit-{case['name']}",
            source_files=case["source_files"],
            runner_command=case["runner_command"],
            working_directory=str(case["working_directory"]),
            timeout_seconds=int(case["timeout_seconds"]),
        )
        with sqlite3.connect(home / "alab.db") as conn:
            exp_id = conn.execute(
                "SELECT exp_id FROM experiments WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]

        if case["mutation"] == "exit":
            (worktree_path / "main.py").write_text("import sys\nsys.exit(7)\n", encoding="utf-8")
        elif case["mutation"] == "sleep":
            (worktree_path / "main.py").write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
        elif case["mutation"] == "remove-working-directory":
            (worktree_path / "work" / "main.py").unlink()
            (worktree_path / "work").rmdir()

        submit_args = [
            "--home",
            str(home),
            "submit",
            "--message",
            f"{case['name']} submit result failure",
            "--summary",
            "done",
            "--feedback",
            "ok",
            "--ref",
            "none",
        ]
        if case["rerun"]:
            submit_args.append("--rerun")
        monkeypatch.chdir(worktree_path)
        assert cli.run(submit_args) == 1
        submit_out = capsys.readouterr()
        submit_fields = _output_field_map(submit_out.out)
        reason = submit_fields["reason"]
        run_match = re.match(r"final run (run-[^ ]+) (.+)$", reason)
        run_id = run_match.group(1) if run_match else None

        assert {
            "stderr": submit_out.err,
            "traceback": "Traceback" in submit_out.out,
            "labels": _output_field_labels(submit_out.out),
            "exp id": submit_fields.get("exp id"),
            "accepted": submit_fields.get("submit accepted"),
            "final run id": submit_fields.get("final run id"),
            "final commit": submit_fields.get("final commit"),
            "experiment status": submit_fields.get("experiment status"),
            "summary stored": submit_fields.get("summary stored"),
            "feedback stored": submit_fields.get("feedback stored"),
            "ref": submit_fields.get("ref"),
            "error code": submit_fields.get("error code"),
            "exit code": submit_fields.get("exit code"),
            "next": submit_fields.get("next"),
            "reason suffix": run_match.group(2) if run_match else reason,
        } == {
            "stderr": "",
            "traceback": False,
            "labels": expected_submit_failure_labels,
            "exp id": exp_id,
            "accepted": "false",
            "final run id": "none",
            "final commit": "none",
            "experiment status": "open",
            "summary stored": "false",
            "feedback stored": "false",
            "ref": "none",
            "error code": case["error code"],
            "exit code": "1",
            "next": case["next"],
            "reason suffix": case["reason suffix"],
        }

        with sqlite3.connect(home / "alab.db") as conn:
            experiment_row = conn.execute(
                "SELECT status, final_run_id, final_commit FROM experiments WHERE exp_id = ?",
                (exp_id,),
            ).fetchone()
            submission_count = conn.execute(
                "SELECT COUNT(*) FROM experiment_submissions WHERE exp_id = ?",
                (exp_id,),
            ).fetchone()[0]
            run_count = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE exp_id = ?",
                (exp_id,),
            ).fetchone()[0]
            run_row = (
                conn.execute(
                    "SELECT status, exit_code, reward_parse_status, record_json FROM runs WHERE run_id = ?",
                    (run_id,),
                ).fetchone()
                if run_id
                else None
            )

        assert {
            "experiment": experiment_row,
            "submissions": submission_count,
            "runs": run_count,
        } == {
            "experiment": ("open", None, None),
            "submissions": 0,
            "runs": 1 if case["rerun"] else 0,
        }
        if case["rerun"]:
            assert run_row is not None
            record_json = json.loads(run_row[3])
            assert {
                "status": run_row[0],
                "exit code": run_row[1],
                "reward parse status": run_row[2],
                "failure": record_json["failure"],
            } == {
                "status": case["run status"],
                "exit code": case["runner exit code"],
                "reward parse status": case["reward parse status"],
                "failure": case["failure"],
            }
        else:
            assert run_id is None


def test_submit_success_fields_follow_cli_spec(tmp_path: Path, monkeypatch, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "submit-field-worktree"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Submit Field Contract",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    create_out = capsys.readouterr()
    exp_id = _output_field_map(create_out.out)["exp id"]

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "submit reusable run"]) == 0
    run_out = capsys.readouterr()
    run_fields = _output_field_map(run_out.out)

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "submit",
                "--message",
                "submit field contract",
                "--summary",
                "done",
                "--feedback",
                "ok",
                "--ref",
                "none",
            ]
        )
        == 0
    )
    submit_out = capsys.readouterr()
    submit_fields = _output_field_map(submit_out.out)

    assert {
        "submit err": submit_out.err,
        "submit labels": _output_field_labels(submit_out.out),
        "expected labels": _documented_success_labels("submit"),
        "exp id": submit_fields.get("exp id"),
        "accepted": submit_fields.get("submit accepted"),
        "final run id": submit_fields.get("final run id"),
        "final commit": submit_fields.get("final commit"),
        "experiment status": submit_fields.get("experiment status"),
        "summary stored": submit_fields.get("summary stored"),
        "feedback stored": submit_fields.get("feedback stored"),
        "ref": submit_fields.get("ref"),
    } == {
        "submit err": "",
        "submit labels": _documented_success_labels("submit"),
        "expected labels": _documented_success_labels("submit"),
        "exp id": exp_id,
        "accepted": "true",
        "final run id": run_fields["run id"],
        "final commit": run_fields["commit"],
        "experiment status": "closed",
        "summary stored": "true",
        "feedback stored": "true",
        "ref": "none",
    }


def _init_observable_asset_contract_project(
    tmp_path: Path,
    capsys,
    *,
    worktree_name: str,
) -> tuple[Path, str, str, str, Path]:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    worktree_path = tmp_path / worktree_name
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
import sys
from pathlib import Path

print("contract stdout")
print("contract stderr", file=sys.stderr)
Path(os.environ["ALAB_RUN_DIR"], "artifact.txt").write_text("artifact bytes\\n", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Observable Asset Contract"
task = "Exercise observable asset field contracts"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "full"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
            ]
        )
        == 0
    )
    project_fields = _output_field_map(capsys.readouterr().out)
    project_id = project_fields["project id"]
    admin_key = project_fields["admin key"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Observable Asset Contract",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    return home, root_key, project_id, admin_key, worktree_path


def test_observe_read_aliases_render_equivalent_outputs(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="alias-contract-worktree",
    )
    admin_args = ["--home", str(home), "--key", admin_key]

    def run_ok(args: list[str]) -> str:
        assert cli.run(args) == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        return captured.out

    monkeypatch.chdir(worktree_path)
    run_out = run_ok(["--home", str(home), "run", "--message", "alias contract run"])
    run_fields = _output_field_map(run_out)
    run_id = run_fields["run id"]
    exp_id = run_fields["exp id"]

    annotation_out = run_ok(
        [
            *admin_args,
            "annotate",
            "add",
            "--project",
            project_id,
            "--target",
            f"exp:{exp_id}",
            "--body",
            "alias contract annotation",
        ]
    )
    annotation_id = _output_field_map(annotation_out)["annotation id"]

    observe_artifacts_list = run_ok([*admin_args, "observe", "artifacts", "list", "--project", project_id, "--run", run_id])
    artifacts_list = run_ok([*admin_args, "artifacts", "list", "--project", project_id, "--run", run_id])
    artifact_id = _output_field_map(observe_artifacts_list)["artifact id"]

    observe_logs_list = run_ok([*admin_args, "observe", "logs", "list", "--project", project_id, "--run", run_id, "--stream", "stdout"])
    logs_list = run_ok([*admin_args, "logs", "list", "--project", project_id, "--run", run_id, "--stream", "stdout"])
    log_id = _output_field_map(observe_logs_list)["log id"]

    artifact_export_path = tmp_path / "alias-artifact.txt"
    observe_artifact_export = run_ok(
        [
            *admin_args,
            "observe",
            "artifacts",
            "export",
            artifact_id,
            "--project",
            project_id,
            "--out",
            str(artifact_export_path),
        ]
    )
    artifacts_export = run_ok(
        [
            *admin_args,
            "artifacts",
            "export",
            artifact_id,
            "--project",
            project_id,
            "--out",
            str(artifact_export_path),
            "--overwrite",
        ]
    )

    log_export_path = tmp_path / "alias-stdout.log"
    observe_log_export = run_ok(
        [
            *admin_args,
            "observe",
            "logs",
            "export",
            log_id,
            "--project",
            project_id,
            "--out",
            str(log_export_path),
        ]
    )
    logs_export = run_ok(
        [
            *admin_args,
            "logs",
            "export",
            log_id,
            "--project",
            project_id,
            "--out",
            str(log_export_path),
            "--overwrite",
        ]
    )

    alias_pairs = {
        "experiments list": (
            run_ok([*admin_args, "observe", "experiments", "list", "--project", project_id]),
            run_ok([*admin_args, "exp", "list", "--project", project_id]),
        ),
        "experiments search": (
            run_ok([*admin_args, "observe", "experiments", "search", "--project", project_id, "--query", "alias"]),
            run_ok([*admin_args, "exp", "search", "--project", project_id, "--query", "alias"]),
        ),
        "experiments show": (
            run_ok([*admin_args, "observe", "experiments", "show", exp_id, "--project", project_id]),
            run_ok([*admin_args, "exp", "show", exp_id, "--project", project_id]),
        ),
        "experiments best": (
            run_ok([*admin_args, "observe", "experiments", "best", "--project", project_id, "--limit", "1"]),
            run_ok([*admin_args, "exp", "best", "--project", project_id, "--limit", "1"]),
        ),
        "runs list": (
            run_ok([*admin_args, "observe", "runs", "list", "--project", project_id, "--exp", exp_id]),
            run_ok([*admin_args, "runs", "list", "--project", project_id, "--exp", exp_id]),
        ),
        "runs show": (
            run_ok([*admin_args, "observe", "runs", "show", run_id, "--project", project_id]),
            run_ok([*admin_args, "runs", "show", run_id, "--project", project_id]),
        ),
        "artifacts list": (observe_artifacts_list, artifacts_list),
        "artifacts show": (
            run_ok([*admin_args, "observe", "artifacts", "show", artifact_id, "--project", project_id]),
            run_ok([*admin_args, "artifacts", "show", artifact_id, "--project", project_id]),
        ),
        "artifacts export": (observe_artifact_export, artifacts_export),
        "logs list": (observe_logs_list, logs_list),
        "logs show": (
            run_ok([*admin_args, "observe", "logs", "show", log_id, "--project", project_id]),
            run_ok([*admin_args, "logs", "show", log_id, "--project", project_id]),
        ),
        "logs export": (observe_log_export, logs_export),
        "annotations list": (
            run_ok([*admin_args, "observe", "annotations", "list", "--project", project_id, "--target-type", "experiment", "--target-id", exp_id]),
            run_ok([*admin_args, "annotations", "list", "--project", project_id, "--target-type", "experiment", "--target-id", exp_id]),
        ),
        "annotations show": (
            run_ok([*admin_args, "observe", "annotations", "show", annotation_id, "--project", project_id]),
            run_ok([*admin_args, "annotations", "show", annotation_id, "--project", project_id]),
        ),
    }

    assert {name: observed == alias for name, (observed, alias) in alias_pairs.items()} == {name: True for name in alias_pairs}
    assert artifact_export_path.read_text(encoding="utf-8") == "artifact bytes\n"
    assert log_export_path.read_text(encoding="utf-8") == "contract stdout\n"


def test_observe_lifecycle_aliases_render_canonical_shapes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="lifecycle-alias-contract-worktree",
    )
    admin_args = ["--home", str(home), "--key", admin_key]

    def run_ok(args: list[str]) -> str:
        assert cli.run(args) == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        return captured.out

    monkeypatch.chdir(worktree_path)
    run_out = run_ok(["--home", str(home), "run", "--message", "lifecycle alias contract run"])
    run_id = _output_field_map(run_out)["run id"]

    artifact_list = run_ok([*admin_args, "observe", "artifacts", "list", "--project", project_id, "--run", run_id])
    artifact_id = _output_field_map(artifact_list)["artifact id"]
    log_list = run_ok([*admin_args, "observe", "logs", "list", "--project", project_id, "--run", run_id, "--stream", "stdout"])
    log_id = _output_field_map(log_list)["log id"]

    dry_run_pairs = {
        "runs remove": (
            run_ok([*admin_args, "observe", "runs", "remove", run_id, "--project", project_id, "--dry-run"]),
            run_ok([*admin_args, "runs", "remove", run_id, "--project", project_id, "--dry-run"]),
        ),
        "artifacts remove": (
            run_ok([*admin_args, "observe", "artifacts", "remove", artifact_id, "--project", project_id, "--dry-run"]),
            run_ok([*admin_args, "artifacts", "remove", artifact_id, "--project", project_id, "--dry-run"]),
        ),
        "logs remove": (
            run_ok([*admin_args, "observe", "logs", "remove", log_id, "--project", project_id, "--dry-run"]),
            run_ok([*admin_args, "logs", "remove", log_id, "--project", project_id, "--dry-run"]),
        ),
    }

    alias_shape_cases = [
        (
            "runs archive",
            [*admin_args, "runs", "archive", run_id, "--project", project_id],
            _documented_success_labels("observe runs archive"),
        ),
        (
            "runs unarchive",
            [*admin_args, "runs", "unarchive", run_id, "--project", project_id],
            _documented_success_labels("observe runs unarchive"),
        ),
        (
            "artifacts archive",
            [*admin_args, "artifacts", "archive", artifact_id, "--project", project_id],
            _documented_success_labels("observe artifacts archive"),
        ),
        (
            "artifacts unarchive",
            [*admin_args, "artifacts", "unarchive", artifact_id, "--project", project_id],
            _documented_success_labels("observe artifacts unarchive"),
        ),
        (
            "logs archive",
            [*admin_args, "logs", "archive", log_id, "--project", project_id],
            _documented_success_labels("observe logs archive"),
        ),
        (
            "logs unarchive",
            [*admin_args, "logs", "unarchive", log_id, "--project", project_id],
            _documented_success_labels("observe logs unarchive"),
        ),
    ]

    observed_shapes = {name: _output_field_labels(run_ok(args)) for name, args, _labels in alias_shape_cases}
    expected_shapes = {name: labels for name, _args, labels in alias_shape_cases}

    assert {name: observed == alias for name, (observed, alias) in dry_run_pairs.items()} == {name: True for name in dry_run_pairs}
    assert observed_shapes == expected_shapes


def test_global_options_work_before_and_after_commands_and_aliases(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    config_home = tmp_path / "config-home"
    other_home = tmp_path / "other-home"

    assert cli.run(["--home", str(config_home), "config", "show"]) == 0
    prefix_config_out = capsys.readouterr()

    assert cli.run(["config", "show", "--home", str(config_home)]) == 0
    trailing_config_out = capsys.readouterr()

    assert cli.run(["--home", str(config_home), "config", "show", "--", "--home", str(other_home)]) == 0
    stopped_config_out = capsys.readouterr()

    home, _root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="global-alias-worktree",
    )
    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "global alias contract"]) == 0
    run_fields = _output_field_map(capsys.readouterr().out)
    run_id = run_fields["run id"]
    exp_id = run_fields["exp id"]

    prefix_alias_args = ["--home", str(home), "--key", admin_key, "runs", "list", "--project", project_id, "--exp", exp_id]
    trailing_alias_args = ["runs", "list", "--project", project_id, "--exp", exp_id, "--home", str(home), "--key", admin_key]
    assert cli.run(prefix_alias_args) == 0
    prefix_alias_out = capsys.readouterr()
    assert cli.run(trailing_alias_args) == 0
    trailing_alias_out = capsys.readouterr()

    assert {
        "config prefix": (
            prefix_config_out.err,
            _output_field_labels(prefix_config_out.out),
            _output_field_map(prefix_config_out.out).get("home"),
        ),
        "config trailing": (
            trailing_config_out.err,
            trailing_config_out.out == prefix_config_out.out,
        ),
        "sentinel": (
            stopped_config_out.err,
            stopped_config_out.out == prefix_config_out.out,
            str(other_home.resolve()) in stopped_config_out.out,
        ),
        "alias trailing": (
            prefix_alias_out.err,
            trailing_alias_out.err,
            trailing_alias_out.out == prefix_alias_out.out,
            _output_field_map(prefix_alias_out.out).get("run id"),
        ),
    } == {
        "config prefix": ("", _documented_success_labels("config show"), str(config_home.resolve())),
        "config trailing": ("", True),
        "sentinel": ("", True, False),
        "alias trailing": ("", "", True, run_id),
    }


def test_observe_artifact_log_success_fields_follow_cli_spec(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    worktree_path = tmp_path / "asset-log-field-worktree"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
import sys
from pathlib import Path

print("contract stdout")
print("contract stderr", file=sys.stderr)
Path(os.environ["ALAB_RUN_DIR"], "artifact.txt").write_text("artifact bytes\\n", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Artifact Log Field Contract"
task = "Exercise observable asset field contracts"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "full"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
            ]
        )
        == 0
    )
    project_fields = _output_field_map(capsys.readouterr().out)
    project_id = project_fields["project id"]
    admin_key = project_fields["admin key"]
    admin_args = ["--home", str(home), "--key", admin_key]
    audit_args = ["--home", str(home), "--key", root_key]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Artifact Log Field Contract",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "asset log field contract"]) == 0
    run_out = capsys.readouterr()
    run_id = _output_field_map(run_out.out)["run id"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "observe",
                "artifacts",
                "list",
                "--project",
                project_id,
                "--run",
                run_id,
            ]
        )
        == 0
    )
    artifacts_list_out = capsys.readouterr()
    artifact_id = _output_field_map(artifacts_list_out.out)["artifact id"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "observe",
                "artifacts",
                "show",
                artifact_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    artifact_show_out = capsys.readouterr()

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "observe",
                "logs",
                "list",
                "--project",
                project_id,
                "--run",
                run_id,
                "--stream",
                "stdout",
            ]
        )
        == 0
    )
    logs_list_out = capsys.readouterr()
    log_id = _output_field_map(logs_list_out.out)["log id"]

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "observe",
                "logs",
                "show",
                log_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    log_show_out = capsys.readouterr()

    artifact_export_path = tmp_path / "contract-artifact.txt"
    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "artifacts",
                "export",
                artifact_id,
                "--project",
                project_id,
                "--out",
                str(artifact_export_path),
            ]
        )
        == 0
    )
    artifact_export_out = capsys.readouterr()

    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "artifacts",
                "archive",
                artifact_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    artifact_archive_out = capsys.readouterr()
    artifact_archive_fields = _output_field_map(artifact_archive_out.out)
    assert cli.run([*audit_args, "audit", "show", artifact_archive_fields["audit id"], "--project", project_id]) == 0
    artifact_archive_audit_out = capsys.readouterr()
    artifact_archive_audit_fields = _output_field_map(artifact_archive_audit_out.out)
    artifact_archive_audit_metadata = json.loads(artifact_archive_audit_fields["sanitized metadata"])

    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "artifacts",
                "unarchive",
                artifact_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    artifact_unarchive_out = capsys.readouterr()
    artifact_unarchive_fields = _output_field_map(artifact_unarchive_out.out)
    assert cli.run([*audit_args, "audit", "show", artifact_unarchive_fields["audit id"], "--project", project_id]) == 0
    artifact_unarchive_audit_out = capsys.readouterr()
    artifact_unarchive_audit_fields = _output_field_map(artifact_unarchive_audit_out.out)
    artifact_unarchive_audit_metadata = json.loads(artifact_unarchive_audit_fields["sanitized metadata"])

    log_export_path = tmp_path / "contract-stdout.log"
    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "logs",
                "export",
                log_id,
                "--project",
                project_id,
                "--out",
                str(log_export_path),
            ]
        )
        == 0
    )
    log_export_out = capsys.readouterr()

    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "logs",
                "archive",
                log_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    log_archive_out = capsys.readouterr()
    log_archive_fields = _output_field_map(log_archive_out.out)
    assert cli.run([*audit_args, "audit", "show", log_archive_fields["audit id"], "--project", project_id]) == 0
    log_archive_audit_out = capsys.readouterr()
    log_archive_audit_fields = _output_field_map(log_archive_audit_out.out)
    log_archive_audit_metadata = json.loads(log_archive_audit_fields["sanitized metadata"])

    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "logs",
                "unarchive",
                log_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    log_unarchive_out = capsys.readouterr()
    log_unarchive_fields = _output_field_map(log_unarchive_out.out)
    assert cli.run([*audit_args, "audit", "show", log_unarchive_fields["audit id"], "--project", project_id]) == 0
    log_unarchive_audit_out = capsys.readouterr()
    log_unarchive_audit_fields = _output_field_map(log_unarchive_audit_out.out)
    log_unarchive_audit_metadata = json.loads(log_unarchive_audit_fields["sanitized metadata"])

    assert {
        "run err": run_out.err,
        "artifacts list": (
            artifacts_list_out.err,
            _output_field_labels(artifacts_list_out.out),
            _documented_success_labels("observe artifacts list"),
        ),
        "artifacts show": (
            artifact_show_out.err,
            _output_field_labels(artifact_show_out.out),
            _documented_success_labels("observe artifacts show"),
        ),
        "logs list": (
            logs_list_out.err,
            _output_field_labels(logs_list_out.out),
            _documented_success_labels("observe logs list"),
        ),
        "logs show": (
            log_show_out.err,
            _output_field_labels(log_show_out.out),
            _documented_success_labels("observe logs show"),
        ),
        "artifacts export": (
            artifact_export_out.err,
            _output_field_labels(artifact_export_out.out),
            _output_field_map(artifact_export_out.out).get("out"),
            artifact_export_path.read_text(encoding="utf-8"),
        ),
        "artifacts archive": (
            artifact_archive_out.err,
            _output_field_labels(artifact_archive_out.out),
            artifact_archive_fields.get("archive status"),
        ),
        "artifacts unarchive": (
            artifact_unarchive_out.err,
            _output_field_labels(artifact_unarchive_out.out),
            artifact_unarchive_fields.get("archive status"),
        ),
        "logs export": (
            log_export_out.err,
            _output_field_labels(log_export_out.out),
            _output_field_map(log_export_out.out).get("out"),
            log_export_path.read_text(encoding="utf-8"),
        ),
        "logs archive": (
            log_archive_out.err,
            _output_field_labels(log_archive_out.out),
            log_archive_fields.get("archive status"),
        ),
        "logs unarchive": (
            log_unarchive_out.err,
            _output_field_labels(log_unarchive_out.out),
            log_unarchive_fields.get("archive status"),
        ),
        "artifacts archive audit": (
            artifact_archive_audit_out.err,
            _output_field_labels(artifact_archive_audit_out.out),
            artifact_archive_audit_fields.get("audit id"),
            artifact_archive_audit_fields.get("action"),
            artifact_archive_audit_fields.get("object type"),
            artifact_archive_audit_fields.get("object id"),
            artifact_archive_audit_metadata,
        ),
        "artifacts unarchive audit": (
            artifact_unarchive_audit_out.err,
            _output_field_labels(artifact_unarchive_audit_out.out),
            artifact_unarchive_audit_fields.get("audit id"),
            artifact_unarchive_audit_fields.get("action"),
            artifact_unarchive_audit_fields.get("object type"),
            artifact_unarchive_audit_fields.get("object id"),
            artifact_unarchive_audit_metadata,
        ),
        "logs archive audit": (
            log_archive_audit_out.err,
            _output_field_labels(log_archive_audit_out.out),
            log_archive_audit_fields.get("audit id"),
            log_archive_audit_fields.get("action"),
            log_archive_audit_fields.get("object type"),
            log_archive_audit_fields.get("object id"),
            log_archive_audit_metadata,
        ),
        "logs unarchive audit": (
            log_unarchive_audit_out.err,
            _output_field_labels(log_unarchive_audit_out.out),
            log_unarchive_audit_fields.get("audit id"),
            log_unarchive_audit_fields.get("action"),
            log_unarchive_audit_fields.get("object type"),
            log_unarchive_audit_fields.get("object id"),
            log_unarchive_audit_metadata,
        ),
    } == {
        "run err": "",
        "artifacts list": (
            "",
            _documented_success_labels("observe artifacts list"),
            _documented_success_labels("observe artifacts list"),
        ),
        "artifacts show": (
            "",
            _documented_success_labels("observe artifacts show"),
            _documented_success_labels("observe artifacts show"),
        ),
        "logs list": (
            "",
            _documented_success_labels("observe logs list"),
            _documented_success_labels("observe logs list"),
        ),
        "logs show": (
            "",
            _documented_success_labels("observe logs show"),
            _documented_success_labels("observe logs show"),
        ),
        "artifacts export": (
            "",
            _documented_success_labels("observe artifacts export"),
            str(artifact_export_path),
            "artifact bytes\n",
        ),
        "artifacts archive": (
            "",
            _documented_success_labels("observe artifacts archive"),
            "archived",
        ),
        "artifacts unarchive": (
            "",
            _documented_success_labels("observe artifacts unarchive"),
            "active",
        ),
        "logs export": (
            "",
            _documented_success_labels("observe logs export"),
            str(log_export_path),
            "contract stdout\n",
        ),
        "logs archive": (
            "",
            _documented_success_labels("observe logs archive"),
            "archived",
        ),
        "logs unarchive": (
            "",
            _documented_success_labels("observe logs unarchive"),
            "active",
        ),
        "artifacts archive audit": (
            "",
            _documented_success_labels("audit show"),
            artifact_archive_fields["audit id"],
            "archive",
            "artifact",
            artifact_id,
            {
                "archive_status": "archived",
                "archived_at": artifact_archive_fields["archived at"],
                "previous_archive_status": "active",
                "schema_version": 1,
            },
        ),
        "artifacts unarchive audit": (
            "",
            _documented_success_labels("audit show"),
            artifact_unarchive_fields["audit id"],
            "unarchive",
            "artifact",
            artifact_id,
            {
                "archive_status": "active",
                "previous_archive_status": "archived",
                "schema_version": 1,
                "unarchived_at": artifact_unarchive_fields["unarchived at"],
            },
        ),
        "logs archive audit": (
            "",
            _documented_success_labels("audit show"),
            log_archive_fields["audit id"],
            "archive",
            "log",
            log_id,
            {
                "archive_status": "archived",
                "archived_at": log_archive_fields["archived at"],
                "previous_archive_status": "active",
                "schema_version": 1,
            },
        ),
        "logs unarchive audit": (
            "",
            _documented_success_labels("audit show"),
            log_unarchive_fields["audit id"],
            "unarchive",
            "log",
            log_id,
            {
                "archive_status": "active",
                "previous_archive_status": "archived",
                "schema_version": 1,
                "unarchived_at": log_unarchive_fields["unarchived at"],
            },
        ),
    }


def test_observe_remove_success_fields_follow_cli_spec(tmp_path: Path, monkeypatch, capsys) -> None:
    home, root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="remove-field-worktree",
    )
    admin_args = ["--home", str(home), "--key", admin_key]
    audit_args = ["--home", str(home), "--key", root_key]

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "remove field contract"]) == 0
    run_out = capsys.readouterr()
    run_id = _output_field_map(run_out.out)["run id"]

    assert cli.run([*admin_args, "observe", "artifacts", "list", "--project", project_id, "--run", run_id]) == 0
    artifacts_list_out = capsys.readouterr()
    artifact_id = _output_field_map(artifacts_list_out.out)["artifact id"]

    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "logs",
                "list",
                "--project",
                project_id,
                "--run",
                run_id,
                "--stream",
                "stdout",
            ]
        )
        == 0
    )
    stdout_log_out = capsys.readouterr()
    stdout_log_id = _output_field_map(stdout_log_out.out)["log id"]

    assert cli.run([*admin_args, "observe", "artifacts", "remove", artifact_id, "--project", project_id, "--dry-run"]) == 0
    artifact_active_dry_run = capsys.readouterr()
    artifact_active_fields = _output_field_map(artifact_active_dry_run.out)
    artifact_path_count = int(artifact_active_fields["deleted filesystem paths"])

    assert cli.run([*admin_args, "observe", "artifacts", "archive", artifact_id, "--project", project_id]) == 0
    capsys.readouterr()

    assert cli.run([*admin_args, "observe", "artifacts", "remove", artifact_id, "--project", project_id, "--dry-run"]) == 0
    artifact_archived_dry_run = capsys.readouterr()

    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "artifacts",
                "remove",
                artifact_id,
                "--project",
                project_id,
                "--force",
                "--confirm",
                artifact_id,
            ]
        )
        == 0
    )
    artifact_remove = capsys.readouterr()
    artifact_remove_fields = _output_field_map(artifact_remove.out)
    assert cli.run([*audit_args, "audit", "show", artifact_remove_fields["audit id"], "--project", project_id]) == 0
    artifact_audit_out = capsys.readouterr()
    artifact_audit_fields = _output_field_map(artifact_audit_out.out)
    artifact_audit_metadata = json.loads(artifact_audit_fields["sanitized metadata"])

    assert cli.run([*admin_args, "observe", "logs", "remove", stdout_log_id, "--project", project_id, "--dry-run"]) == 0
    log_active_dry_run = capsys.readouterr()
    log_active_fields = _output_field_map(log_active_dry_run.out)
    log_path_count = int(log_active_fields["deleted filesystem paths"])

    assert cli.run([*admin_args, "observe", "logs", "archive", stdout_log_id, "--project", project_id]) == 0
    capsys.readouterr()

    assert cli.run([*admin_args, "observe", "logs", "remove", stdout_log_id, "--project", project_id, "--dry-run"]) == 0
    log_archived_dry_run = capsys.readouterr()

    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "logs",
                "remove",
                stdout_log_id,
                "--project",
                project_id,
                "--force",
                "--confirm",
                stdout_log_id,
            ]
        )
        == 0
    )
    log_remove = capsys.readouterr()
    log_remove_fields = _output_field_map(log_remove.out)
    assert cli.run([*audit_args, "audit", "show", log_remove_fields["audit id"], "--project", project_id]) == 0
    log_audit_out = capsys.readouterr()
    log_audit_fields = _output_field_map(log_audit_out.out)
    log_audit_metadata = json.loads(log_audit_fields["sanitized metadata"])

    assert cli.run([*admin_args, "observe", "logs", "list", "--project", project_id, "--run", run_id]) == 0
    remaining_logs_out = capsys.readouterr()
    remaining_log_ids = [_output_field_map(block)["log id"] for block in _output_blocks(remaining_logs_out.out)]
    assert remaining_log_ids

    for remaining_log_id in remaining_log_ids:
        assert cli.run([*admin_args, "observe", "logs", "archive", remaining_log_id, "--project", project_id]) == 0
        capsys.readouterr()

    assert cli.run([*admin_args, "observe", "runs", "archive", run_id, "--project", project_id]) == 0
    capsys.readouterr()

    assert cli.run([*admin_args, "observe", "runs", "remove", run_id, "--project", project_id, "--cascade", "--dry-run"]) == 0
    run_dry_run = capsys.readouterr()
    run_dry_run_fields = _output_field_map(run_dry_run.out)
    run_path_count = int(run_dry_run_fields["deleted filesystem paths"])

    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "runs",
                "remove",
                run_id,
                "--project",
                project_id,
                "--cascade",
                "--force",
                "--confirm",
                run_id,
            ]
        )
        == 0
    )
    run_remove = capsys.readouterr()
    run_remove_fields = _output_field_map(run_remove.out)
    assert cli.run([*audit_args, "audit", "show", run_remove_fields["audit id"], "--project", project_id]) == 0
    run_audit_out = capsys.readouterr()
    run_audit_fields = _output_field_map(run_audit_out.out)
    run_audit_metadata = json.loads(run_audit_fields["sanitized metadata"])

    assert {
        "artifact active dry-run": (
            artifact_active_dry_run.err,
            _output_field_labels(artifact_active_dry_run.out),
            artifact_active_fields.get("blocker"),
            artifact_active_fields.get("removed"),
        ),
        "artifact archived dry-run": (
            artifact_archived_dry_run.err,
            _output_field_labels(artifact_archived_dry_run.out),
        ),
        "artifact remove": (
            artifact_remove.err,
            _output_field_labels(artifact_remove.out),
            artifact_remove_fields.get("removed"),
            artifact_remove_fields.get("trash cleanup pending"),
        ),
        "log active dry-run": (
            log_active_dry_run.err,
            _output_field_labels(log_active_dry_run.out),
            log_active_fields.get("blocker"),
            log_active_fields.get("removed"),
        ),
        "log archived dry-run": (
            log_archived_dry_run.err,
            _output_field_labels(log_archived_dry_run.out),
        ),
        "log remove": (
            log_remove.err,
            _output_field_labels(log_remove.out),
            log_remove_fields.get("removed"),
            log_remove_fields.get("trash cleanup pending"),
        ),
        "run dry-run": (
            run_dry_run.err,
            _output_field_labels(run_dry_run.out),
            run_dry_run_fields.get("cascade"),
            run_dry_run_fields.get("deleted artifacts"),
            run_dry_run_fields.get("deleted logs"),
            run_dry_run_fields.get("active dependent artifacts"),
            run_dry_run_fields.get("active dependent logs"),
        ),
        "run remove": (
            run_remove.err,
            _output_field_labels(run_remove.out),
            run_remove_fields.get("removed"),
            run_remove_fields.get("cascade"),
            run_remove_fields.get("deleted artifacts"),
            run_remove_fields.get("deleted logs"),
            run_remove_fields.get("active dependent artifacts"),
            run_remove_fields.get("active dependent logs"),
            run_remove_fields.get("trash cleanup pending"),
        ),
        "artifact remove audit": (
            artifact_audit_out.err,
            _output_field_labels(artifact_audit_out.out),
            artifact_audit_fields.get("audit id"),
            artifact_audit_fields.get("action"),
            artifact_audit_fields.get("object type"),
            artifact_audit_fields.get("object id"),
            artifact_audit_fields.get("cascade"),
            artifact_audit_fields.get("reason"),
            artifact_audit_metadata.get("filesystem_target_count"),
            artifact_audit_metadata.get("filesystem_absent_count"),
            [
                (entry.get("kind"), entry.get("object_id"), entry.get("already_absent"), bool(entry.get("original_path_hash")))
                for entry in artifact_audit_metadata.get("trash", [])
            ],
        ),
        "log remove audit": (
            log_audit_out.err,
            _output_field_labels(log_audit_out.out),
            log_audit_fields.get("audit id"),
            log_audit_fields.get("action"),
            log_audit_fields.get("object type"),
            log_audit_fields.get("object id"),
            log_audit_fields.get("cascade"),
            log_audit_fields.get("reason"),
            log_audit_metadata.get("filesystem_target_count"),
            log_audit_metadata.get("filesystem_absent_count"),
            [
                (entry.get("kind"), entry.get("object_id"), entry.get("already_absent"), bool(entry.get("original_path_hash")))
                for entry in log_audit_metadata.get("trash", [])
            ],
        ),
        "run remove audit": (
            run_audit_out.err,
            _output_field_labels(run_audit_out.out),
            run_audit_fields.get("audit id"),
            run_audit_fields.get("action"),
            run_audit_fields.get("object type"),
            run_audit_fields.get("object id"),
            run_audit_fields.get("cascade"),
            run_audit_fields.get("reason"),
            run_audit_metadata.get("deleted_artifact_count"),
            run_audit_metadata.get("deleted_log_count"),
            run_audit_metadata.get("active_dependent_artifact_count"),
            run_audit_metadata.get("active_dependent_log_count"),
            run_audit_metadata.get("filesystem_target_count"),
            run_audit_metadata.get("filesystem_absent_count"),
            run_audit_metadata.get("latest_run_id_before"),
            run_audit_metadata.get("latest_run_id_after"),
            run_audit_metadata.get("final_run_removed"),
            [
                (entry.get("kind"), entry.get("object_id"), entry.get("already_absent"), bool(entry.get("original_path_hash")))
                for entry in run_audit_metadata.get("trash", [])
            ],
        ),
    } == {
        "artifact active dry-run": (
            "",
            _documented_success_labels_with_repeats(
                "observe artifacts remove",
                repeats={"filesystem path": artifact_path_count, "planned trash move": artifact_path_count},
                omit={"trash cleanup pending"},
            ),
            "target_not_archived",
            "false",
        ),
        "artifact archived dry-run": (
            "",
            _documented_success_labels_with_repeats(
                "observe artifacts remove",
                repeats={"filesystem path": artifact_path_count, "planned trash move": artifact_path_count},
                omit={"blocker", "trash cleanup pending"},
            ),
        ),
        "artifact remove": (
            "",
            _documented_success_labels("observe artifacts remove", omit={"blocker", "filesystem path", "planned trash move"}),
            "true",
            "false",
        ),
        "log active dry-run": (
            "",
            _documented_success_labels_with_repeats(
                "observe logs remove",
                repeats={"filesystem path": log_path_count, "planned trash move": log_path_count},
                omit={"trash cleanup pending"},
            ),
            "target_not_archived",
            "false",
        ),
        "log archived dry-run": (
            "",
            _documented_success_labels_with_repeats(
                "observe logs remove",
                repeats={"filesystem path": log_path_count, "planned trash move": log_path_count},
                omit={"blocker", "trash cleanup pending"},
            ),
        ),
        "log remove": (
            "",
            _documented_success_labels("observe logs remove", omit={"blocker", "filesystem path", "planned trash move"}),
            "true",
            "false",
        ),
        "run dry-run": (
            "",
            _documented_success_labels_with_repeats(
                "observe runs remove",
                repeats={"filesystem path": run_path_count, "planned trash move": run_path_count},
                omit={"blocker", "trash cleanup pending"},
            ),
            "true",
            "0",
            str(len(remaining_log_ids)),
            "0",
            "0",
        ),
        "run remove": (
            "",
            _documented_success_labels("observe runs remove", omit={"blocker", "filesystem path", "planned trash move"}),
            "true",
            "true",
            "0",
            str(len(remaining_log_ids)),
            "0",
            "0",
            "false",
        ),
        "artifact remove audit": (
            "",
            _documented_success_labels("audit show"),
            artifact_remove_fields["audit id"],
            "remove",
            "artifact",
            artifact_id,
            "false",
            "none",
            artifact_path_count,
            0,
            [("artifact", artifact_id, False, True)] if artifact_path_count else [],
        ),
        "log remove audit": (
            "",
            _documented_success_labels("audit show"),
            log_remove_fields["audit id"],
            "remove",
            "log",
            stdout_log_id,
            "false",
            "none",
            log_path_count,
            0,
            [("log", stdout_log_id, False, True)] if log_path_count else [],
        ),
        "run remove audit": (
            "",
            _documented_success_labels("audit show"),
            run_remove_fields["audit id"],
            "remove",
            "run",
            run_id,
            "true",
            "none",
            0,
            len(remaining_log_ids),
            0,
            0,
            run_path_count,
            0,
            run_id,
            None,
            False,
            [("log", log_id, False, True) for log_id in remaining_log_ids],
        ),
    }


def test_annotation_success_fields_follow_cli_spec(tmp_path: Path, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "annotation-field-worktree"
    admin_args = ["--home", str(home), "--key", admin_key]
    audit_args = ["--home", str(home), "--key", root_key]

    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Annotation Field Contract",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    create_out = capsys.readouterr()
    exp_id = _output_field_map(create_out.out)["exp id"]

    assert (
        cli.run(
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                f"exp:{exp_id}",
                "--body",
                "first note",
                "--author",
                "agent",
            ]
        )
        == 0
    )
    add_out = capsys.readouterr()
    add_fields = _output_field_map(add_out.out)
    annotation_id = add_fields["annotation id"]

    assert (
        cli.run(
            [
                *admin_args,
                "annotate",
                "edit",
                annotation_id,
                "--project",
                project_id,
                "--body",
                "second note",
                "--author",
                "agent",
            ]
        )
        == 0
    )
    edit_out = capsys.readouterr()

    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "annotations",
                "list",
                "--project",
                project_id,
                "--target-type",
                "experiment",
                "--target-id",
                exp_id,
                "--history",
            ]
        )
        == 0
    )
    list_out = capsys.readouterr()

    assert (
        cli.run(
            [
                *admin_args,
                "observe",
                "annotations",
                "show",
                annotation_id,
                "--project",
                project_id,
                "--history",
            ]
        )
        == 0
    )
    show_out = capsys.readouterr()

    assert cli.run([*admin_args, "annotate", "remove", annotation_id, "--project", project_id, "--dry-run"]) == 0
    active_remove_dry_run_out = capsys.readouterr()

    assert cli.run([*admin_args, "annotate", "archive", annotation_id, "--project", project_id]) == 0
    archive_out = capsys.readouterr()
    archive_fields = _output_field_map(archive_out.out)
    assert (
        cli.run(
            [
                *audit_args,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "annotation",
                "--object-id",
                annotation_id,
                "--action",
                "archive",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    archive_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run([*audit_args, "audit", "show", archive_audit_id, "--project", project_id]) == 0
    archive_audit_out = capsys.readouterr()
    archive_audit_fields = _output_field_map(archive_audit_out.out)
    archive_audit_metadata = json.loads(archive_audit_fields["sanitized metadata"])

    assert cli.run([*admin_args, "annotate", "unarchive", annotation_id, "--project", project_id]) == 0
    unarchive_out = capsys.readouterr()
    unarchive_fields = _output_field_map(unarchive_out.out)
    assert (
        cli.run(
            [
                *audit_args,
                "audit",
                "list",
                "--project",
                project_id,
                "--object-type",
                "annotation",
                "--object-id",
                annotation_id,
                "--action",
                "unarchive",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    unarchive_audit_id = _output_field_map(capsys.readouterr().out)["audit id"]
    assert cli.run([*audit_args, "audit", "show", unarchive_audit_id, "--project", project_id]) == 0
    unarchive_audit_out = capsys.readouterr()
    unarchive_audit_fields = _output_field_map(unarchive_audit_out.out)
    unarchive_audit_metadata = json.loads(unarchive_audit_fields["sanitized metadata"])

    assert cli.run([*admin_args, "annotate", "archive", annotation_id, "--project", project_id]) == 0
    archive_again_out = capsys.readouterr()

    assert cli.run([*admin_args, "annotate", "remove", annotation_id, "--project", project_id, "--dry-run"]) == 0
    archived_remove_dry_run_out = capsys.readouterr()

    assert (
        cli.run(
            [
                *admin_args,
                "annotate",
                "remove",
                annotation_id,
                "--project",
                project_id,
                "--force",
                "--confirm",
                annotation_id,
            ]
        )
        == 0
    )
    remove_out = capsys.readouterr()
    remove_fields = _output_field_map(remove_out.out)

    annotation_history_labels = _documented_success_labels_with_repeats(
        "observe annotations show",
        repeats={"revision": 2},
    )
    assert {
        "add": (
            add_out.err,
            _output_field_labels(add_out.out),
            add_fields.get("target type"),
            add_fields.get("target id"),
            add_fields.get("revision"),
            add_fields.get("visibility"),
        ),
        "edit": (
            edit_out.err,
            _output_field_labels(edit_out.out),
            _output_field_map(edit_out.out).get("revision"),
        ),
        "list": (list_out.err, _output_field_labels(list_out.out)),
        "show": (show_out.err, _output_field_labels(show_out.out)),
        "active remove dry-run": (
            active_remove_dry_run_out.err,
            _output_field_labels(active_remove_dry_run_out.out),
            _output_field_map(active_remove_dry_run_out.out).get("blocker"),
        ),
        "archive": (archive_out.err, _output_field_labels(archive_out.out)),
        "unarchive": (unarchive_out.err, _output_field_labels(unarchive_out.out)),
        "archive audit": (
            archive_audit_out.err,
            _output_field_labels(archive_audit_out.out),
            archive_audit_fields.get("audit id"),
            archive_audit_fields.get("action"),
            archive_audit_fields.get("object type"),
            archive_audit_fields.get("object id"),
            archive_audit_metadata,
        ),
        "unarchive audit": (
            unarchive_audit_out.err,
            _output_field_labels(unarchive_audit_out.out),
            unarchive_audit_fields.get("audit id"),
            unarchive_audit_fields.get("action"),
            unarchive_audit_fields.get("object type"),
            unarchive_audit_fields.get("object id"),
            unarchive_audit_metadata,
        ),
        "archive again": (archive_again_out.err, _output_field_labels(archive_again_out.out)),
        "archived remove dry-run": (archived_remove_dry_run_out.err, _output_field_labels(archived_remove_dry_run_out.out)),
        "remove": (
            remove_out.err,
            _output_field_labels(remove_out.out),
            remove_fields.get("removed"),
            remove_fields.get("deleted revisions"),
            remove_fields.get("deleted filesystem paths"),
            remove_fields.get("trash cleanup pending"),
        ),
    } == {
        "add": (
            "",
            _documented_success_labels("annotate add"),
            "experiment",
            exp_id,
            "1",
            "project",
        ),
        "edit": ("", _documented_success_labels("annotate edit"), "2"),
        "list": ("", annotation_history_labels),
        "show": ("", annotation_history_labels),
        "active remove dry-run": (
            "",
            _documented_success_labels("annotate remove", omit={"trash cleanup pending"}),
            "target_not_archived",
        ),
        "archive": ("", _documented_success_labels("annotate archive")),
        "unarchive": ("", _documented_success_labels("annotate unarchive")),
        "archive audit": (
            "",
            _documented_success_labels("audit show"),
            archive_audit_id,
            "archive",
            "annotation",
            annotation_id,
            {
                "annotation_status": "archived",
                "archived_at": archive_fields["archived at"],
                "previous_status": "active",
                "schema_version": 1,
            },
        ),
        "unarchive audit": (
            "",
            _documented_success_labels("audit show"),
            unarchive_audit_id,
            "unarchive",
            "annotation",
            annotation_id,
            {
                "annotation_status": "active",
                "previous_status": "archived",
                "schema_version": 1,
                "unarchived_at": unarchive_fields["unarchived at"],
            },
        ),
        "archive again": ("", _documented_success_labels("annotate archive")),
        "archived remove dry-run": ("", _documented_success_labels("annotate remove", omit={"blocker", "trash cleanup pending"})),
        "remove": (
            "",
            _documented_success_labels("annotate remove", omit={"blocker"}),
            "true",
            "2",
            "0",
            "false",
        ),
    }


def test_capability_surfaces_reference_registered_commands_with_expected_credentials() -> None:
    missing_paths = [
        " ".join(path)
        for path_set in _CAPABILITY_PATH_SETS
        for path in path_set
        if path not in registry.COMMANDS_BY_PATH
    ]
    assert missing_paths == []

    global_public_credentials = {
        " ".join(path): registry.COMMANDS_BY_PATH[path].credential
        for path in cli.GLOBAL_PUBLIC
        if registry.COMMANDS_BY_PATH[path].credential != "none"
    }
    assert global_public_credentials == {}

    observe_read_credentials = {
        " ".join(path): registry.COMMANDS_BY_PATH[path].credential
        for path in cli.OBSERVE_READ
        if registry.COMMANDS_BY_PATH[path].credential != "token_or_admin"
    }
    assert observe_read_credentials == {}

    observe_lifecycle_credentials = {
        " ".join(path): registry.COMMANDS_BY_PATH[path].credential
        for path in cli.OBSERVE_TOKEN_LIFECYCLE
        if registry.COMMANDS_BY_PATH[path].credential != "token_or_admin"
    }
    assert observe_lifecycle_credentials == {}

    assert registry.COMMANDS_BY_PATH[("status",)].credential == "public"
    assert registry.COMMANDS_BY_PATH[("exp", "create")].credential == "public_or_admin"
    assert registry.COMMANDS_BY_PATH[("run",)].credential == "token"
    assert registry.COMMANDS_BY_PATH[("submit",)].credential == "token"


def test_locked_commands_fail_in_preflight_without_context_key_or_home(tmp_path: Path, capsys) -> None:
    failures = []
    locked_specs = [spec for spec in registry.COMMANDS if spec.path not in cli.GLOBAL_PUBLIC]
    assert locked_specs

    for index, spec in enumerate(locked_specs):
        home = tmp_path / f"home-{index}"
        code = cli.run(["--home", str(home), *spec.path])
        captured = capsys.readouterr()
        if (
            code != 4
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or "error code: COMMAND_UNAVAILABLE" not in captured.err
            or home.exists()
        ):
            failures.append(
                {
                    "command": " ".join(spec.path),
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "home_exists": home.exists(),
                }
            )

    assert failures == []


def test_locked_commands_preflight_before_handler_argument_effects(tmp_path: Path, capsys) -> None:
    failures = []
    locked_specs = [spec for spec in registry.COMMANDS if spec.path not in cli.GLOBAL_PUBLIC]
    payloads = [
        ("unsupported", ["--definitely-unsupported"]),
        ("value-file", ["--value-file", "missing-value.txt"]),
        ("body-file", ["--body-file", "missing-body.txt"]),
        ("submit-files", ["--summary-file", "missing-summary.txt", "--feedback-file", "missing-feedback.txt"]),
        ("config", ["--config", "missing-config.toml"]),
        ("out", ["--out", "should-not-exist.out"]),
        ("out-missing-parent", ["--out", "missing-output-parent/should-not-exist.out"]),
    ]
    assert locked_specs

    for command_index, spec in enumerate(locked_specs):
        for payload_index, (payload_name, payload_args) in enumerate(payloads):
            home = tmp_path / f"locked-home-{command_index}-{payload_index}"
            sandbox = tmp_path / f"locked-files-{command_index}-{payload_index}"
            sandbox.mkdir()
            args = [str((sandbox / item).resolve()) if item.startswith("missing-") or item.startswith("should-not-exist") else item for item in payload_args]
            touched_paths = [Path(item) for item in args if item.startswith(str(sandbox))]
            touched_parents = [path.parent for path in touched_paths if payload_name == "out-missing-parent"]
            code = cli.run(["--home", str(home), *spec.path, *args])
            captured = capsys.readouterr()
            existing_touched_paths = [str(path) for path in touched_paths if path.exists()]
            existing_touched_parents = [str(path) for path in touched_parents if path.exists()]
            if (
                code != 4
                or captured.out
                or _output_field_labels(captured.err) != _error_field_labels()
                or "error code: COMMAND_UNAVAILABLE" not in captured.err
                or home.exists()
                or existing_touched_paths
                or existing_touched_parents
            ):
                failures.append(
                    {
                        "command": " ".join(spec.path),
                        "payload": payload_name,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "home_exists": home.exists(),
                        "existing_paths": existing_touched_paths,
                        "existing_parent_paths": existing_touched_parents,
                    }
                )

    assert failures == []


def test_nested_help_uses_same_locked_preflight_with_handler_payloads(tmp_path: Path, capsys) -> None:
    failures = []
    locked_specs = [spec for spec in registry.COMMANDS if spec.path not in cli.GLOBAL_PUBLIC]
    payloads = [
        ("unsupported", ["--definitely-unsupported"]),
        ("value-file", ["--value-file", "missing-value.txt"]),
        ("body-file", ["--body-file", "missing-body.txt"]),
        ("submit-files", ["--summary-file", "missing-summary.txt", "--feedback-file", "missing-feedback.txt"]),
        ("config", ["--config", "missing-config.toml"]),
        ("out", ["--out", "should-not-exist.out"]),
        ("out-missing-parent", ["--out", "missing-output-parent/should-not-exist.out"]),
    ]
    assert locked_specs

    for command_index, spec in enumerate(locked_specs):
        for payload_index, (payload_name, payload_args) in enumerate(payloads):
            home = tmp_path / f"payload-help-home-{command_index}-{payload_index}"
            sandbox = tmp_path / f"payload-help-files-{command_index}-{payload_index}"
            sandbox.mkdir()
            args = [str((sandbox / item).resolve()) if item.startswith("missing-") or item.startswith("should-not-exist") else item for item in payload_args]
            touched_paths = [Path(item) for item in args if item.startswith(str(sandbox))]
            touched_parents = [path.parent for path in touched_paths if payload_name == "out-missing-parent"]
            code = cli.run(["--home", str(home), *spec.path, *args, "--help", "--explain"])
            captured = capsys.readouterr()
            blocks = _output_blocks(captured.out)
            fields = _output_field_map(blocks[1]) if len(blocks) == 2 else {}
            existing_touched_paths = [str(path) for path in touched_paths if path.exists()]
            existing_touched_parents = [str(path) for path in touched_parents if path.exists()]
            if (
                code != 0
                or captured.err
                or len(blocks) != 2
                or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
                or _output_field_labels(blocks[1]) != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
                or fields.get("command") != " ".join(spec.path)
                or fields.get("available") != "false"
                or fields.get("locked reason") != "project, experiment, inspection, or explicit credential required"
                or fields.get("unlock hint") != "use alab help --all or pass an explicit key"
                or fields.get("capability source") != "use alab help --all or pass an explicit key"
                or fields.get("summary") != spec.summary
                or home.exists()
                or existing_touched_paths
                or existing_touched_parents
            ):
                failures.append(
                    {
                        "command": " ".join(spec.path),
                        "payload": payload_name,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "home_exists": home.exists(),
                        "existing_paths": existing_touched_paths,
                        "existing_parent_paths": existing_touched_parents,
                    }
                )

    assert failures == []


def test_nested_help_runtime_covers_every_registered_command(tmp_path: Path, capsys) -> None:
    failures = []
    for index, spec in enumerate(registry.COMMANDS):
        if spec.handler is services.cmd_help:
            continue
        expected_available = spec.path in cli.GLOBAL_PUBLIC
        expected_locked_reason = "none" if expected_available else "project, experiment, inspection, or explicit credential required"
        expected_unlock_hint = "none" if expected_available else "use alab help --all or pass an explicit key"
        variants = [
            (["--help"], "none"),
            (["--help", "--explain"], "global" if expected_available else expected_unlock_hint),
        ]
        for variant_index, (help_args, expected_capability_source) in enumerate(variants):
            home = tmp_path / f"help-home-{index}-{variant_index}"
            code = cli.run(["--home", str(home), *spec.path, *help_args])
            captured = capsys.readouterr()
            blocks = _output_blocks(captured.out)
            fields = _output_field_map(blocks[1]) if len(blocks) == 2 else {}
            if (
                code != 0
                or captured.err
                or len(blocks) != 2
                or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
                or _output_field_labels(blocks[1]) != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
                or fields.get("command") != " ".join(spec.path)
                or fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != spec.summary
                or home.exists()
            ):
                failures.append(
                    {
                        "command": " ".join(spec.path),
                        "help_args": help_args,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "home_exists": home.exists(),
                    }
                )

    assert failures == []


def test_all_commands_help_covers_registry_with_stable_schema(tmp_path: Path) -> None:
    req = services.Request(services.GlobalOptions(Home(tmp_path / "home")), context=None)
    blocks = cli.help_blocks(req, all_commands=True, explain=True)
    expected_help_labels = _documented_success_labels("help")
    expected_help_command_labels = _documented_success_labels_for_object("help", "help_command")

    assert blocks[0].object_type == "help"
    assert _field_labels(blocks[0]) == expected_help_labels

    command_blocks = blocks[1:]
    assert len(command_blocks) == len(registry.COMMANDS)
    assert all(block.object_type == "help_command" for block in command_blocks)
    assert all(_field_labels(block) == expected_help_command_labels for block in command_blocks)

    registry_by_command = {" ".join(spec.path): spec for spec in registry.COMMANDS}
    help_by_command = {_field_map(block)["command"]: _field_map(block) for block in command_blocks}
    assert set(help_by_command) == set(registry_by_command)

    summary_mismatches = [
        command
        for command, fields in help_by_command.items()
        if fields["summary"] != registry_by_command[command].summary
    ]
    assert summary_mismatches == []


def test_top_level_all_help_runtime_covers_registry_and_availability(tmp_path: Path, capsys) -> None:
    failures = []
    registry_by_command = {" ".join(spec.path): spec for spec in registry.COMMANDS}
    expected_available_commands = {" ".join(path) for path in cli.GLOBAL_PUBLIC}
    expected_help_labels = _documented_success_labels("help")
    expected_help_command_labels = _documented_success_labels_for_object("help", "help_command")
    expected_command_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.path in cli.GLOBAL_PUBLIC],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.path not in cli.GLOBAL_PUBLIC],
    ]
    variants = [
        ["help", "--all", "--explain"],
        ["--help", "--all", "--explain"],
    ]

    for index, help_args in enumerate(variants):
        home = tmp_path / f"all-help-home-{index}"
        code = cli.run(["--home", str(home), *help_args])
        captured = capsys.readouterr()
        blocks = _output_blocks(captured.out)
        command_fields = [_output_field_map(block) for block in blocks[1:]]
        command_order = [fields.get("command") for fields in command_fields]
        help_by_command = {fields.get("command"): fields for fields in command_fields}
        malformed_commands = [
            fields
            for fields in command_fields
            if _output_field_labels("\n".join(f"{key}: {value}" for key, value in fields.items()))
            != expected_help_command_labels
        ]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(registry.COMMANDS) + 1
            or _output_field_labels(blocks[0]) != expected_help_labels
            or set(help_by_command) != set(registry_by_command)
            or command_order != expected_command_order
            or malformed_commands
            or home.exists()
        ):
            failures.append(
                {
                    "help_args": help_args,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "home_exists": home.exists(),
                }
            )
            continue

        for command, spec in registry_by_command.items():
            fields = help_by_command[command]
            expected_available = command in expected_available_commands
            expected_locked_reason = "none" if expected_available else "project, experiment, inspection, or explicit credential required"
            expected_unlock_hint = "none" if expected_available else "use alab help --all or pass an explicit key"
            expected_capability_source = "global" if expected_available else expected_unlock_hint
            if (
                fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != spec.summary
            ):
                failures.append({"help_args": help_args, "command": command, "fields": fields})

    assert failures == []


def test_default_help_runtime_hides_locked_commands_without_creating_home(tmp_path: Path, capsys) -> None:
    failures = []
    registry_by_command = {" ".join(spec.path): spec for spec in registry.COMMANDS}
    expected_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.path in cli.GLOBAL_PUBLIC]
    expected_help_labels = _documented_success_labels("help")
    expected_help_command_labels = _documented_success_labels_for_object("help", "help_command")
    variants = [
        [],
        ["help"],
        ["--help"],
    ]

    for index, help_args in enumerate(variants):
        home = tmp_path / f"default-help-home-{index}"
        code = cli.run(["--home", str(home), *help_args])
        captured = capsys.readouterr()
        blocks = _output_blocks(captured.out)
        command_fields = [_output_field_map(block) for block in blocks[1:]]
        command_order = [fields.get("command") for fields in command_fields]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(expected_commands) + 1
            or _output_field_labels(blocks[0]) != expected_help_labels
            or command_order != expected_commands
            or home.exists()
        ):
            failures.append(
                {
                    "help_args": help_args,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "home_exists": home.exists(),
                }
            )
            continue

        for fields in command_fields:
            command = fields.get("command")
            if (
                _output_field_labels("\n".join(f"{key}: {value}" for key, value in fields.items()))
                != expected_help_command_labels
                or fields.get("available") != "true"
                or fields.get("locked reason") != "none"
                or fields.get("unlock hint") != "none"
                or fields.get("capability source") != "none"
                or fields.get("summary") != registry_by_command[command].summary
            ):
                failures.append({"help_args": help_args, "command": command, "fields": fields})

    assert failures == []


def test_ambient_key_does_not_broaden_help_capability_display(tmp_path: Path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]
    monkeypatch.setenv("ALAB_KEY", root_key)

    failures = []
    registry_by_command = {" ".join(spec.path): spec for spec in registry.COMMANDS}
    expected_available_commands = {" ".join(path) for path in cli.GLOBAL_PUBLIC}
    expected_default_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.path in cli.GLOBAL_PUBLIC]
    expected_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.path in cli.GLOBAL_PUBLIC],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.path not in cli.GLOBAL_PUBLIC],
    ]

    for help_args in ([], ["help"], ["--help"]):
        code = cli.run(["--home", str(home), *help_args])
        captured = capsys.readouterr()
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(expected_default_commands) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("credential source") != "none"
            or header.get("credential scope") != "none"
            or [fields.get("command") for fields in command_fields] != expected_default_commands
            or [
                block
                for block in command_blocks
                if _output_field_labels(block) != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
            ]
        ):
            failures.append({"help_args": help_args, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for fields in command_fields:
            command = fields.get("command")
            if (
                fields.get("available") != "true"
                or fields.get("locked reason") != "none"
                or fields.get("unlock hint") != "none"
                or fields.get("capability source") != "none"
                or fields.get("summary") != registry_by_command[command].summary
            ):
                failures.append({"help_args": help_args, "command": command, "fields": fields})

    for help_args in (["help", "--all", "--explain"], ["--help", "--all", "--explain"]):
        code = cli.run(["--home", str(home), *help_args])
        captured = capsys.readouterr()
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(registry.COMMANDS) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("credential source") != "none"
            or header.get("credential scope") != "none"
            or [fields.get("command") for fields in command_fields] != expected_all_order
            or [
                block
                for block in command_blocks
                if _output_field_labels(block) != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
            ]
        ):
            failures.append({"help_args": help_args, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for fields in command_fields:
            command = fields.get("command")
            expected_available = command in expected_available_commands
            expected_locked_reason = "none" if expected_available else "project, experiment, inspection, or explicit credential required"
            expected_unlock_hint = "none" if expected_available else "use alab help --all or pass an explicit key"
            expected_capability_source = "global" if expected_available else expected_unlock_hint
            if (
                fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != registry_by_command[command].summary
            ):
                failures.append({"help_args": help_args, "command": command, "fields": fields})

    missing_secret_file = tmp_path / "missing-secret.txt"
    selected_args = [
        "project",
        "secret",
        "set",
        "BLOCKED_SECRET",
        "--value-file",
        str(missing_secret_file),
        "--help",
        "--explain",
    ]
    assert cli.run(["--home", str(home), *selected_args]) == 0
    selected_out = capsys.readouterr().out
    selected_blocks = _output_blocks(selected_out)
    selected_header = _output_field_map(selected_blocks[0]) if selected_blocks else {}
    selected_fields = _output_field_map(selected_blocks[1]) if len(selected_blocks) == 2 else {}
    if (
        len(selected_blocks) != 2
        or selected_header.get("credential source") != "none"
        or selected_header.get("credential scope") != "none"
        or selected_fields.get("command") != "project secret set"
        or selected_fields.get("available") != "false"
        or selected_fields.get("locked reason") != "project, experiment, inspection, or explicit credential required"
        or selected_fields.get("unlock hint") != "use alab help --all or pass an explicit key"
        or selected_fields.get("capability source") != "use alab help --all or pass an explicit key"
        or missing_secret_file.exists()
    ):
        failures.append({"help_args": selected_args, "stdout": selected_out, "file_exists": missing_secret_file.exists()})

    assert cli.run(["--home", str(home), "--key", root_key, *selected_args]) == 0
    explicit_blocks = _output_blocks(capsys.readouterr().out)
    explicit_header = _output_field_map(explicit_blocks[0]) if explicit_blocks else {}
    explicit_fields = _output_field_map(explicit_blocks[1]) if len(explicit_blocks) == 2 else {}
    if (
        len(explicit_blocks) != 2
        or explicit_header.get("credential source") != "explicit-root"
        or explicit_header.get("credential scope") != "root"
        or explicit_fields.get("command") != "project secret set"
        or explicit_fields.get("available") != "true"
        or explicit_fields.get("capability source") != "root"
        or missing_secret_file.exists()
    ):
        failures.append({"help_args": ["--key", "<root>", *selected_args], "fields": explicit_fields, "header": explicit_header})

    assert failures == []


def test_explicit_root_key_help_capability_display_follows_registry_credentials(tmp_path: Path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]

    failures = []
    registry_by_command = {" ".join(spec.path): spec for spec in registry.COMMANDS}
    expected_default_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.credential != "token"]
    expected_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential != "token"],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential == "token"],
    ]

    def run_help(args: list[str], stdin_value: str | None = None):
        if stdin_value is not None:
            monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_value))
        code = cli.run(["--home", str(home), *args])
        return code, capsys.readouterr()

    default_variants = [
        ("key-no-command", ["--key", root_key], None),
        ("key-help", ["--key", root_key, "help"], None),
        ("key-stdin-help", ["--key-stdin", "--help"], root_key + "\n"),
    ]
    for variant_name, help_args, stdin_value in default_variants:
        code, captured = run_help(help_args, stdin_value)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(expected_default_commands) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("credential source") != "explicit-root"
            or header.get("credential scope") != "root"
            or [fields.get("command") for fields in command_fields] != expected_default_commands
            or [
                block
                for block in command_blocks
                if _output_field_labels(block) != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
            ]
        ):
            failures.append({"variant": variant_name, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for fields in command_fields:
            command = fields.get("command")
            if (
                fields.get("available") != "true"
                or fields.get("locked reason") != "none"
                or fields.get("unlock hint") != "none"
                or fields.get("capability source") != "none"
                or fields.get("summary") != registry_by_command[command].summary
            ):
                failures.append({"variant": variant_name, "command": command, "fields": fields})

    all_variants = [
        ("key-all", ["--key", root_key, "help", "--all", "--explain"], None),
        ("key-stdin-all", ["--key-stdin", "--help", "--all", "--explain"], root_key + "\n"),
    ]
    for variant_name, help_args, stdin_value in all_variants:
        code, captured = run_help(help_args, stdin_value)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(registry.COMMANDS) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("credential source") != "explicit-root"
            or header.get("credential scope") != "root"
            or [fields.get("command") for fields in command_fields] != expected_all_order
            or [
                block
                for block in command_blocks
                if _output_field_labels(block) != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
            ]
        ):
            failures.append({"variant": variant_name, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for command, spec in registry_by_command.items():
            fields = next(item for item in command_fields if item.get("command") == command)
            expected_available = spec.credential != "token"
            expected_locked_reason = "none" if expected_available else "experiment worktree token context required"
            expected_unlock_hint = "none" if expected_available else "run from an experiment worktree"
            expected_capability_source = "root" if expected_available else expected_unlock_hint
            if (
                fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != spec.summary
            ):
                failures.append({"variant": variant_name, "command": command, "fields": fields})

    assert failures == []


def test_explicit_admin_key_help_capability_display_is_project_scoped(tmp_path: Path, monkeypatch, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)

    failures = []
    registry_by_command = {" ".join(spec.path): spec for spec in registry.COMMANDS}
    expected_default_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.credential not in {"root", "token"}]
    expected_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential not in {"root", "token"}],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential in {"root", "token"}],
    ]

    def run_help(args: list[str], stdin_value: str | None = None):
        if stdin_value is not None:
            monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_value))
        code = cli.run(["--home", str(home), *args])
        return code, capsys.readouterr()

    default_variants = [
        ("key-no-command", ["--key", admin_key], None),
        ("key-help", ["--key", admin_key, "help"], None),
        ("key-stdin-help", ["--key-stdin", "--help"], admin_key + "\n"),
    ]
    for variant_name, help_args, stdin_value in default_variants:
        code, captured = run_help(help_args, stdin_value)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(expected_default_commands) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("credential source") != "explicit-admin"
            or header.get("credential scope") != "admin"
            or [fields.get("command") for fields in command_fields] != expected_default_commands
            or [
                block
                for block in command_blocks
                if _output_field_labels(block) != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
            ]
        ):
            failures.append({"variant": variant_name, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for fields in command_fields:
            command = fields.get("command")
            if (
                fields.get("available") != "true"
                or fields.get("locked reason") != "none"
                or fields.get("unlock hint") != "none"
                or fields.get("capability source") != "none"
                or fields.get("summary") != registry_by_command[command].summary
            ):
                failures.append({"variant": variant_name, "command": command, "fields": fields})

    all_variants = [
        ("key-all", ["--key", admin_key, "help", "--all", "--explain"], None),
        ("key-stdin-all", ["--key-stdin", "--help", "--all", "--explain"], admin_key + "\n"),
    ]
    for variant_name, help_args, stdin_value in all_variants:
        code, captured = run_help(help_args, stdin_value)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(registry.COMMANDS) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("credential source") != "explicit-admin"
            or header.get("credential scope") != "admin"
            or [fields.get("command") for fields in command_fields] != expected_all_order
            or [
                block
                for block in command_blocks
                if _output_field_labels(block) != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
            ]
        ):
            failures.append({"variant": variant_name, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for command, spec in registry_by_command.items():
            fields = next(item for item in command_fields if item.get("command") == command)
            expected_available = spec.credential not in {"root", "token"}
            expected_locked_reason = "none" if expected_available else ("root credential required" if spec.credential == "root" else "experiment worktree token context required")
            expected_unlock_hint = "none" if expected_available else ("use a root key" if spec.credential == "root" else "run from an experiment worktree")
            expected_capability_source = "project-admin" if expected_available else expected_unlock_hint
            if (
                fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != spec.summary
            ):
                failures.append({"variant": variant_name, "command": command, "fields": fields})

    same_project_help = ["--key", admin_key, "project", "config", "show", "--project", project_id, "--help", "--explain"]
    assert cli.run(["--home", str(home), *same_project_help]) == 0
    same_blocks = _output_blocks(capsys.readouterr().out)
    same_header = _output_field_map(same_blocks[0]) if same_blocks else {}
    same_fields = _output_field_map(same_blocks[1]) if len(same_blocks) == 2 else {}
    if (
        len(same_blocks) != 2
        or same_header.get("credential source") != "explicit-admin"
        or same_fields.get("command") != "project config show"
        or same_fields.get("available") != "true"
        or same_fields.get("capability source") != "project-admin"
    ):
        failures.append({"variant": "same-project-selected", "header": same_header, "fields": same_fields})

    other_project_id = f"{project_id}-other"
    cross_project_help = ["--key", admin_key, "project", "config", "show", "--project", other_project_id, "--help", "--explain"]
    assert cli.run(["--home", str(home), *cross_project_help]) == 0
    cross_blocks = _output_blocks(capsys.readouterr().out)
    cross_header = _output_field_map(cross_blocks[0]) if cross_blocks else {}
    cross_fields = _output_field_map(cross_blocks[1]) if len(cross_blocks) == 2 else {}
    if (
        len(cross_blocks) != 2
        or cross_header.get("credential source") != "explicit-admin"
        or cross_fields.get("command") != "project config show"
        or cross_fields.get("available") != "false"
        or cross_fields.get("locked reason") != "project admin credential does not match requested project"
        or cross_fields.get("unlock hint") != "use a matching project admin key or root key"
        or cross_fields.get("capability source") != "use a matching project admin key or root key"
    ):
        failures.append({"variant": "cross-project-selected", "header": cross_header, "fields": cross_fields})

    assert cli.run(["--home", str(home), "--key", admin_key, "project", "config", "show", "--project", other_project_id]) == 4
    cross_preflight = capsys.readouterr()
    if (
        cross_preflight.out
        or _output_field_labels(cross_preflight.err) != _error_field_labels()
        or "error code: COMMAND_UNAVAILABLE" not in cross_preflight.err
    ):
        failures.append({"variant": "cross-project-preflight", "stdout": cross_preflight.out, "stderr": cross_preflight.err})

    assert failures == []


def test_explicit_credentials_unavailable_commands_preflight_before_handler_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    cwd = tmp_path / "explicit-preflight-cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    variants = [
        ("root-key", ["--key", root_key], None, lambda spec: spec.credential == "token"),
        ("root-stdin", ["--key-stdin"], root_key + "\n", lambda spec: spec.credential == "token"),
        ("admin-key", ["--key", admin_key], None, lambda spec: spec.credential in {"root", "token"}),
        ("admin-stdin", ["--key-stdin"], admin_key + "\n", lambda spec: spec.credential in {"root", "token"}),
    ]
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
    ]
    payloads = [
        ("unsupported", ["--definitely-unsupported"]),
        ("value-file", ["--value-file", "missing-value.txt"]),
        ("body-file", ["--body-file", "missing-body.txt"]),
        ("submit-files", ["--summary-file", "missing-summary.txt", "--feedback-file", "missing-feedback.txt"]),
        ("config", ["--config", "missing-config.toml"]),
        ("out", ["--out", "should-not-exist.out"]),
        ("out-missing-parent", ["--out", "missing-output-parent/should-not-exist.out"]),
    ]
    failures = []

    for variant_name, credential_args, stdin_value, is_unavailable in variants:
        unavailable_specs = [spec for spec in registry.COMMANDS if is_unavailable(spec)]
        assert unavailable_specs
        for command_index, spec in enumerate(unavailable_specs):
            for payload_index, (payload_name, payload_args) in enumerate(payloads):
                sandbox = tmp_path / f"explicit-preflight-files-{variant_name}-{command_index}-{payload_index}"
                sandbox.mkdir()
                args = [
                    str((sandbox / item).resolve())
                    if item.startswith("missing-") or item.startswith("should-not-exist")
                    else item
                    for item in payload_args
                ]
                touched_paths = [Path(item) for item in args if item.startswith(str(sandbox))]
                touched_parents = [path.parent for path in touched_paths if payload_name == "out-missing-parent"]
                before_snapshot = _database_snapshot(home)
                watched_file_contents = _text_file_snapshot(watched_files)
                watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
                with monkeypatch.context() as context:
                    if stdin_value is not None:
                        context.setattr(sys, "stdin", io.StringIO(stdin_value))
                    code = cli.run(["--home", str(home), *credential_args, *spec.path, *args])
                captured = capsys.readouterr()
                fields = _output_field_map(captured.err) if captured.err else {}
                db_unchanged = _database_snapshot(home) == before_snapshot
                files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
                trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
                existing_touched_paths = [str(path) for path in touched_paths if path.exists()]
                existing_touched_parents = [str(path) for path in touched_parents if path.exists()]
                if (
                    code != 4
                    or captured.out
                    or _output_field_labels(captured.err) != _error_field_labels()
                    or fields.get("error code") != "COMMAND_UNAVAILABLE"
                    or fields.get("exit code") != "4"
                    or fields.get("reason") != "command is not available in the current context"
                    or fields.get("next") != "none"
                    or not db_unchanged
                    or not files_unchanged
                    or not trees_unchanged
                    or existing_touched_paths
                    or existing_touched_parents
                ):
                    failures.append(
                        {
                            "variant": variant_name,
                            "command": " ".join(spec.path),
                            "payload": payload_name,
                            "code": code,
                            "stdout": captured.out,
                            "stderr": captured.err,
                            "fields": fields,
                            "existing paths": existing_touched_paths,
                            "existing parent paths": existing_touched_parents,
                            "db unchanged": db_unchanged,
                            "files unchanged": files_unchanged,
                            "trees unchanged": trees_unchanged,
                        }
                    )

    assert failures == [], json.dumps(failures, indent=2)


def test_invalid_explicit_credentials_fail_before_handler_payloads_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, _admin_key = _init_capability_project(tmp_path, capsys)

    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
    ]
    variants = [
        ("key", ["--key", "not-a-valid-key"], None),
        ("key-stdin", ["--key-stdin"], "not-a-valid-key\n"),
    ]
    failures = []

    for variant_name, credential_args, stdin_value in variants:
        for command_index, spec in enumerate(registry.COMMANDS):
            sandbox = tmp_path / f"invalid-credential-files-{variant_name}-{command_index}"
            sandbox.mkdir()
            output_path = sandbox / "missing-output-parent" / "should-not-exist.txt"
            touched_paths = [
                sandbox / "missing-config.toml",
                sandbox / "missing-secret.txt",
                sandbox / "missing-body.txt",
                sandbox / "missing-summary.txt",
                sandbox / "missing-feedback.txt",
                output_path,
            ]
            payload_args = [
                "--config",
                str(touched_paths[0]),
                "--value-file",
                str(touched_paths[1]),
                "--body-file",
                str(touched_paths[2]),
                "--summary-file",
                str(touched_paths[3]),
                "--feedback-file",
                str(touched_paths[4]),
                "--out",
                str(output_path),
                "--definitely-unsupported",
            ]
            before_snapshot = _database_snapshot(home)
            watched_file_contents = _text_file_snapshot(watched_files)
            watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
            with monkeypatch.context() as context:
                if stdin_value is not None:
                    context.setattr(sys, "stdin", io.StringIO(stdin_value))
                code = cli.run(["--home", str(home), *credential_args, *spec.path, *payload_args])
            captured = capsys.readouterr()
            fields = _output_field_map(captured.err) if captured.err else {}
            db_unchanged = _database_snapshot(home) == before_snapshot
            files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
            trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
            existing_touched_paths = [str(path) for path in touched_paths if path.exists()]
            existing_touched_parents = [str(output_path.parent)] if output_path.parent.exists() else []
            if (
                code != 3
                or captured.out
                or _output_field_labels(captured.err) != _error_field_labels()
                or fields.get("error code") != "AUTH_DENIED"
                or fields.get("exit code") != "3"
                or fields.get("reason") != "invalid credential"
                or fields.get("next") != "none"
                or not db_unchanged
                or not files_unchanged
                or not trees_unchanged
                or existing_touched_paths
                or existing_touched_parents
            ):
                failures.append(
                    {
                        "variant": variant_name,
                        "command": " ".join(spec.path),
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "fields": fields,
                        "existing paths": existing_touched_paths,
                        "existing parent paths": existing_touched_parents,
                        "db unchanged": db_unchanged,
                        "files unchanged": files_unchanged,
                        "trees unchanged": trees_unchanged,
                    }
                )

    assert failures == [], json.dumps(failures, indent=2)


def test_text_file_payloads_reject_bad_files_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    admin_args = ["--home", str(home), "--key", admin_key]
    init_source = tmp_path / "payload-init-source"
    exp_path = tmp_path / "payload-exp"
    init_source.mkdir()
    (init_source / "main.py").write_text("print('payload init')\n", encoding="utf-8")

    assert cli.run([*admin_args, "exp", "create", "--project", project_id, "--name", "payload", "--path", str(exp_path)]) == 0
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]
    assert cli.run([*admin_args, "annotate", "add", "--project", project_id, "--target", f"exp:{exp_id}", "--body", "initial body"]) == 0
    annotation_id = _output_field_map(capsys.readouterr().out)["annotation id"]

    invalid_utf8 = tmp_path / "payload-invalid-utf8.txt"
    invalid_utf8.write_bytes(b"\xff\xfe")
    payload_dir = tmp_path / "payload-directory"
    payload_dir.mkdir()
    unreadable = tmp_path / "payload-unreadable.txt"
    unreadable.write_text("unreadable payload\n", encoding="utf-8")
    unreadable.chmod(0)

    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
    ]

    def command_cases(path: Path, suffix: str) -> list[tuple[str, list[str], Path | None, str]]:
        return [
            (
                "project init --config",
                [
                    "--home",
                    str(home),
                    "--key",
                    root_key,
                    "project",
                    "init",
                    "local",
                    "--config",
                    str(path),
                    "--source-path",
                    str(init_source),
                ],
                None,
                f"config file {suffix}",
            ),
            (
                "project config import --config",
                [*admin_args, "project", "config", "import", "--project", project_id, "--config", str(path)],
                None,
                f"config file {suffix}",
            ),
            (
                "project secret set --value-file",
                [*admin_args, "project", "secret", "set", "BAD_PAYLOAD_SECRET", "--project", project_id, "--value-file", str(path)],
                None,
                f"secret value file {suffix}",
            ),
            (
                "submit --summary-file",
                [
                    "--home",
                    str(home),
                    "submit",
                    "--message",
                    "bad payload summary",
                    "--summary-file",
                    str(path),
                    "--feedback",
                    "feedback",
                    "--ref",
                    "none",
                ],
                exp_path,
                f"submit summary file {suffix}",
            ),
            (
                "submit --feedback-file",
                [
                    "--home",
                    str(home),
                    "submit",
                    "--message",
                    "bad payload feedback",
                    "--summary",
                    "summary",
                    "--feedback-file",
                    str(path),
                    "--ref",
                    "none",
                ],
                exp_path,
                f"submit feedback file {suffix}",
            ),
            (
                "annotate add --body-file",
                [*admin_args, "annotate", "add", "--project", project_id, "--target", f"exp:{exp_id}", "--body-file", str(path)],
                None,
                f"annotation body file {suffix}",
            ),
            (
                "annotate edit --body-file",
                [*admin_args, "annotate", "edit", annotation_id, "--project", project_id, "--body-file", str(path)],
                None,
                f"annotation body file {suffix}",
            ),
        ]

    payloads: list[tuple[str, Path, str]] = [
        ("invalid utf8", invalid_utf8, "must be UTF-8"),
        ("directory", payload_dir, "is a directory"),
    ]
    try:
        try:
            unreadable.read_text(encoding="utf-8")
        except OSError:
            payloads.append(("unreadable", unreadable, "cannot be read"))

        failures = []
        for payload_name, payload_path, suffix in payloads:
            for command_name, args, cwd, reason_fragment in command_cases(payload_path, suffix):
                db_before = _database_snapshot(home)
                watched_file_contents = _text_file_snapshot(watched_files)
                watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
                with monkeypatch.context() as context:
                    if cwd is not None:
                        context.chdir(cwd)
                    code = cli.run(args)
                captured = capsys.readouterr()
                fields = _output_field_map(captured.err) if captured.err else {}
                db_unchanged = _database_snapshot(home) == db_before
                files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
                trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
                if (
                    code != 2
                    or captured.out
                    or _output_field_labels(captured.err) != _error_field_labels()
                    or fields.get("error code") != "CONFIG_INVALID"
                    or fields.get("exit code") != "2"
                    or reason_fragment not in fields.get("reason", "")
                    or fields.get("next") != "none"
                    or not db_unchanged
                    or not files_unchanged
                    or not trees_unchanged
                ):
                    failures.append(
                        {
                            "payload": payload_name,
                            "command": command_name,
                            "code": code,
                            "stdout": captured.out,
                            "stderr": captured.err,
                            "fields": fields,
                            "reason fragment": reason_fragment,
                            "db unchanged": db_unchanged,
                            "files unchanged": files_unchanged,
                            "trees unchanged": trees_unchanged,
                        }
                    )
    finally:
        unreadable.chmod(0o600)

    assert failures == [], json.dumps(failures, indent=2)


def test_project_context_help_capability_display_uses_context_and_explicit_credentials(tmp_path: Path, monkeypatch, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    monkeypatch.chdir(home / "project-workspaces" / project_id)

    failures = []
    registry_by_command = {" ".join(spec.path): spec for spec in registry.COMMANDS}
    public_paths = cli.GLOBAL_PUBLIC | cli.PUBLIC_PROJECT | cli.PUBLIC_PROJECT_WHEN_ENABLED
    expected_public_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.path in public_paths]
    expected_public_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.path in public_paths],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.path not in public_paths],
    ]
    expected_admin_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.credential not in {"root", "token"}]
    expected_admin_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential not in {"root", "token"}],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential in {"root", "token"}],
    ]
    expected_root_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.credential != "token"]
    expected_root_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential != "token"],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential == "token"],
    ]

    def run_help(args: list[str]):
        code = cli.run(["--home", str(home), *args])
        return code, capsys.readouterr()

    public_default_variants = [
        ("public-no-command", []),
        ("public-help", ["help"]),
        ("public-top-help", ["--help"]),
    ]
    for variant_name, help_args in public_default_variants:
        code, captured = run_help(help_args)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(expected_public_commands) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("context type") != "project"
            or header.get("credential source") != "public"
            or header.get("credential scope") != "none"
            or header.get("project id") != project_id
            or [fields.get("command") for fields in command_fields] != expected_public_commands
        ):
            failures.append({"variant": variant_name, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for fields in command_fields:
            command = fields.get("command")
            if (
                _output_field_labels("\n".join(f"{key}: {value}" for key, value in fields.items()))
                != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
                or fields.get("available") != "true"
                or fields.get("locked reason") != "none"
                or fields.get("unlock hint") != "none"
                or fields.get("capability source") != "none"
                or fields.get("summary") != registry_by_command[command].summary
            ):
                failures.append({"variant": variant_name, "command": command, "fields": fields})

    public_all_variants = [
        ("public-help-all", ["help", "--all", "--explain"]),
        ("public-top-help-all", ["--help", "--all", "--explain"]),
    ]
    for variant_name, help_args in public_all_variants:
        code, captured = run_help(help_args)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(registry.COMMANDS) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("context type") != "project"
            or header.get("credential source") != "public"
            or header.get("credential scope") != "none"
            or header.get("project id") != project_id
            or [fields.get("command") for fields in command_fields] != expected_public_all_order
        ):
            failures.append({"variant": variant_name, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for command, spec in registry_by_command.items():
            fields = next(item for item in command_fields if item.get("command") == command)
            expected_available = spec.path in public_paths
            expected_locked_reason = "none" if expected_available else "project admin or root credential required"
            expected_unlock_hint = "none" if expected_available else "pass --key or --key-stdin"
            if spec.path in cli.GLOBAL_PUBLIC:
                expected_capability_source = "global"
            elif spec.path in cli.PUBLIC_PROJECT or spec.path in cli.PUBLIC_PROJECT_WHEN_ENABLED:
                expected_capability_source = "public-project"
            else:
                expected_capability_source = expected_unlock_hint
            if (
                fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != spec.summary
            ):
                failures.append({"variant": variant_name, "command": command, "fields": fields})

    explicit_variants = [
        (
            "admin",
            ["--key", admin_key, "help", "--all", "--explain"],
            "explicit-admin",
            "admin",
            expected_admin_all_order,
            expected_admin_commands,
            lambda spec: spec.credential not in {"root", "token"},
            lambda spec: "root credential required" if spec.credential == "root" else "experiment worktree token context required",
            lambda spec: "use a root key" if spec.credential == "root" else "run from an experiment worktree",
            "project-admin",
        ),
        (
            "root",
            ["--key", root_key, "help", "--all", "--explain"],
            "explicit-root",
            "root",
            expected_root_all_order,
            expected_root_commands,
            lambda spec: spec.credential != "token",
            lambda _spec: "experiment worktree token context required",
            lambda _spec: "run from an experiment worktree",
            "root",
        ),
    ]
    for (
        variant_name,
        help_args,
        expected_credential_source,
        expected_credential_scope,
        expected_all_order,
        expected_default_commands,
        is_available,
        locked_reason,
        unlock_hint,
        available_capability_source,
    ) in explicit_variants:
        code, captured = run_help(help_args)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(registry.COMMANDS) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("context type") != "project"
            or header.get("credential source") != expected_credential_source
            or header.get("credential scope") != expected_credential_scope
            or header.get("project id") != project_id
            or [fields.get("command") for fields in command_fields] != expected_all_order
        ):
            failures.append({"variant": f"{variant_name}-all", "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for command, spec in registry_by_command.items():
            fields = next(item for item in command_fields if item.get("command") == command)
            expected_available = is_available(spec)
            expected_locked_reason = "none" if expected_available else locked_reason(spec)
            expected_unlock_hint = "none" if expected_available else unlock_hint(spec)
            expected_capability_source = available_capability_source if expected_available else expected_unlock_hint
            if (
                fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != spec.summary
            ):
                failures.append({"variant": f"{variant_name}-all", "command": command, "fields": fields})

        code, captured = run_help(["--key", admin_key if variant_name == "admin" else root_key, "help"])
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_fields = [_output_field_map(block) for block in blocks[1:]]
        if (
            code != 0
            or captured.err
            or header.get("context type") != "project"
            or header.get("credential source") != expected_credential_source
            or [fields.get("command") for fields in command_fields] != expected_default_commands
        ):
            failures.append({"variant": f"{variant_name}-default", "code": code, "stdout": captured.out, "stderr": captured.err})

    assert failures == []


def test_project_context_unavailable_commands_preflight_before_handler_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, _admin_key = _init_capability_project(tmp_path, capsys)
    project_path = home / "project-workspaces" / project_id
    monkeypatch.chdir(project_path)

    public_paths = cli.GLOBAL_PUBLIC | cli.PUBLIC_PROJECT | cli.PUBLIC_PROJECT_WHEN_ENABLED
    unavailable_specs = [spec for spec in registry.COMMANDS if spec.path not in public_paths]
    assert unavailable_specs

    watched_files = [
        home / "config.toml",
        project_path / ".alab" / "context.json",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
    ]
    payloads = [
        ("unsupported", ["--definitely-unsupported"]),
        ("value-file", ["--value-file", "missing-value.txt"]),
        ("body-file", ["--body-file", "missing-body.txt"]),
        ("submit-files", ["--summary-file", "missing-summary.txt", "--feedback-file", "missing-feedback.txt"]),
        ("config", ["--config", "missing-config.toml"]),
        ("out", ["--out", "should-not-exist.out"]),
        ("out-missing-parent", ["--out", "missing-output-parent/should-not-exist.out"]),
    ]
    failures = []

    for command_index, spec in enumerate(unavailable_specs):
        for payload_index, (payload_name, payload_args) in enumerate(payloads):
            sandbox = tmp_path / f"project-preflight-files-{command_index}-{payload_index}"
            sandbox.mkdir()
            args = [
                str((sandbox / item).resolve())
                if item.startswith("missing-") or item.startswith("should-not-exist")
                else item
                for item in payload_args
            ]
            touched_paths = [Path(item) for item in args if item.startswith(str(sandbox))]
            touched_parents = [path.parent for path in touched_paths if payload_name == "out-missing-parent"]
            before_snapshot = _database_snapshot(home)
            watched_file_contents = _text_file_snapshot(watched_files)
            watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
            code = cli.run(["--home", str(home), *spec.path, *args])
            captured = capsys.readouterr()
            fields = _output_field_map(captured.err) if captured.err else {}
            db_unchanged = _database_snapshot(home) == before_snapshot
            files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
            trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
            existing_touched_paths = [str(path) for path in touched_paths if path.exists()]
            existing_touched_parents = [str(path) for path in touched_parents if path.exists()]
            if (
                code != 4
                or captured.out
                or _output_field_labels(captured.err) != _error_field_labels()
                or fields.get("error code") != "COMMAND_UNAVAILABLE"
                or fields.get("exit code") != "4"
                or fields.get("reason") != "command is not available in the current context"
                or fields.get("next") != "none"
                or not db_unchanged
                or not files_unchanged
                or not trees_unchanged
                or existing_touched_paths
                or existing_touched_parents
            ):
                failures.append(
                    {
                        "command": " ".join(spec.path),
                        "payload": payload_name,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "fields": fields,
                        "existing paths": existing_touched_paths,
                        "existing parent paths": existing_touched_parents,
                        "db unchanged": db_unchanged,
                        "files unchanged": files_unchanged,
                        "trees unchanged": trees_unchanged,
                    }
                )

    assert failures == [], json.dumps(failures, indent=2)


def test_experiment_context_help_capability_display_uses_worktree_token_and_explicit_credentials(tmp_path: Path, monkeypatch, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    monkeypatch.chdir(home / "project-workspaces" / project_id)
    assert cli.run(["--home", str(home), "exp", "create", "--name", "cap-exp"]) == 0
    exp_fields = _output_field_map(capsys.readouterr().out)
    exp_id = exp_fields["exp id"]
    worktree_path = Path(exp_fields["worktree path"])
    monkeypatch.chdir(worktree_path)

    failures = []
    registry_by_command = {" ".join(spec.path): spec for spec in registry.COMMANDS}
    token_paths = cli.GLOBAL_PUBLIC | cli.EXPERIMENT_TOKEN | cli.OBSERVE_READ | cli.OBSERVE_TOKEN_LIFECYCLE | cli.PUBLIC_PROJECT_WHEN_ENABLED
    expected_token_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.path in token_paths]
    expected_token_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.path in token_paths],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.path not in token_paths],
    ]
    expected_admin_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.credential != "root"]
    expected_admin_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential != "root"],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential == "root"],
    ]
    expected_root_commands = [" ".join(spec.path) for spec in registry.COMMANDS]

    def run_help(args: list[str]):
        code = cli.run(["--home", str(home), *args])
        return code, capsys.readouterr()

    for variant_name, help_args in [
        ("token-no-command", []),
        ("token-help", ["help"]),
        ("token-top-help", ["--help"]),
    ]:
        code, captured = run_help(help_args)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(expected_token_commands) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("context type") != "experiment"
            or header.get("credential source") != "context-token"
            or header.get("credential scope") != "token:worktree"
            or header.get("project id") != project_id
            or header.get("exp id") != exp_id
            or [fields.get("command") for fields in command_fields] != expected_token_commands
        ):
            failures.append({"variant": variant_name, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for fields in command_fields:
            command = fields.get("command")
            if (
                _output_field_labels("\n".join(f"{key}: {value}" for key, value in fields.items()))
                != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
                or fields.get("available") != "true"
                or fields.get("locked reason") != "none"
                or fields.get("unlock hint") != "none"
                or fields.get("capability source") != "none"
                or fields.get("summary") != registry_by_command[command].summary
            ):
                failures.append({"variant": variant_name, "command": command, "fields": fields})

    for variant_name, help_args in [
        ("token-help-all", ["help", "--all", "--explain"]),
        ("token-top-help-all", ["--help", "--all", "--explain"]),
    ]:
        code, captured = run_help(help_args)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(registry.COMMANDS) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("context type") != "experiment"
            or header.get("credential source") != "context-token"
            or header.get("credential scope") != "token:worktree"
            or header.get("project id") != project_id
            or header.get("exp id") != exp_id
            or [fields.get("command") for fields in command_fields] != expected_token_all_order
        ):
            failures.append({"variant": variant_name, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for command, spec in registry_by_command.items():
            fields = next(item for item in command_fields if item.get("command") == command)
            expected_available = spec.path in token_paths
            expected_locked_reason = "none" if expected_available else "command is not exposed to experiment tokens"
            expected_unlock_hint = "none" if expected_available else "pass an explicit project admin/root key when appropriate"
            expected_capability_source = (
                "global"
                if spec.path in cli.GLOBAL_PUBLIC
                else "public-project"
                if spec.path in cli.PUBLIC_PROJECT_WHEN_ENABLED
                else "worktree-token"
                if expected_available
                else expected_unlock_hint
            )
            if (
                fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != spec.summary
            ):
                failures.append({"variant": variant_name, "command": command, "fields": fields})

    blocked_worktree = tmp_path / "blocked-nested-exp"
    selected_exp_create = ["exp", "create", "--name", "blocked", "--path", str(blocked_worktree), "--help", "--explain"]
    assert cli.run(["--home", str(home), *selected_exp_create]) == 0
    selected_blocks = _output_blocks(capsys.readouterr().out)
    selected_fields = _output_field_map(selected_blocks[1]) if len(selected_blocks) == 2 else {}
    if (
        len(selected_blocks) != 2
        or selected_fields.get("command") != "exp create"
        or selected_fields.get("available") != "true"
        or selected_fields.get("locked reason") != "none"
        or selected_fields.get("unlock hint") != "none"
        or selected_fields.get("capability source") != "public-project"
        or blocked_worktree.exists()
    ):
        failures.append({"variant": "token-selected-exp-create", "fields": selected_fields, "path_exists": blocked_worktree.exists()})

    explicit_variants = [
        (
            "admin",
            ["--key", admin_key, "help", "--all", "--explain"],
            "explicit-admin",
            "admin",
            expected_admin_all_order,
            expected_admin_commands,
            lambda spec: spec.credential != "root",
            lambda _spec: "root credential required",
            lambda _spec: "use a root key",
            lambda spec: "worktree-token" if spec.credential == "token" else "project-admin",
        ),
        (
            "root",
            ["--key", root_key, "help", "--all", "--explain"],
            "explicit-root",
            "root",
            expected_root_commands,
            expected_root_commands,
            lambda _spec: True,
            lambda _spec: "none",
            lambda _spec: "none",
            lambda spec: "worktree-token" if spec.credential == "token" else "root",
        ),
    ]
    for (
        variant_name,
        help_args,
        expected_credential_source,
        expected_credential_scope,
        expected_all_order,
        expected_default_commands,
        is_available,
        locked_reason,
        unlock_hint,
        capability_source,
    ) in explicit_variants:
        code, captured = run_help(help_args)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(registry.COMMANDS) + 1
            or header.get("context type") != "experiment"
            or header.get("credential source") != expected_credential_source
            or header.get("credential scope") != expected_credential_scope
            or header.get("project id") != project_id
            or header.get("exp id") != exp_id
            or [fields.get("command") for fields in command_fields] != expected_all_order
        ):
            failures.append({"variant": f"{variant_name}-all", "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for command, spec in registry_by_command.items():
            fields = next(item for item in command_fields if item.get("command") == command)
            expected_available = is_available(spec)
            expected_locked_reason = "none" if expected_available else locked_reason(spec)
            expected_unlock_hint = "none" if expected_available else unlock_hint(spec)
            expected_capability_source = capability_source(spec) if expected_available else expected_unlock_hint
            if (
                fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != spec.summary
            ):
                failures.append({"variant": f"{variant_name}-all", "command": command, "fields": fields})

        code, captured = run_help(["--key", admin_key if variant_name == "admin" else root_key, "help"])
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_fields = [_output_field_map(block) for block in blocks[1:]]
        if (
            code != 0
            or captured.err
            or header.get("context type") != "experiment"
            or header.get("credential source") != expected_credential_source
            or [fields.get("command") for fields in command_fields] != expected_default_commands
        ):
            failures.append({"variant": f"{variant_name}-default", "code": code, "stdout": captured.out, "stderr": captured.err})

    assert failures == []


def test_experiment_context_unavailable_commands_preflight_before_handler_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, _admin_key = _init_capability_project(tmp_path, capsys)
    monkeypatch.chdir(home / "project-workspaces" / project_id)
    assert cli.run(["--home", str(home), "exp", "create", "--name", "experiment-preflight-parent"]) == 0
    exp_fields = _output_field_map(capsys.readouterr().out)
    exp_path = Path(exp_fields["worktree path"])
    monkeypatch.chdir(exp_path)

    token_paths = (
        cli.GLOBAL_PUBLIC
        | cli.EXPERIMENT_TOKEN
        | cli.OBSERVE_READ
        | cli.OBSERVE_TOKEN_LIFECYCLE
        | cli.PUBLIC_PROJECT_WHEN_ENABLED
    )
    unavailable_specs = [spec for spec in registry.COMMANDS if spec.path not in token_paths]
    assert unavailable_specs

    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
    ]
    payloads = [
        ("unsupported", ["--definitely-unsupported"]),
        ("value-file", ["--value-file", "missing-value.txt"]),
        ("body-file", ["--body-file", "missing-body.txt"]),
        ("submit-files", ["--summary-file", "missing-summary.txt", "--feedback-file", "missing-feedback.txt"]),
        ("config", ["--config", "missing-config.toml"]),
        ("out", ["--out", "should-not-exist.out"]),
        ("out-missing-parent", ["--out", "missing-output-parent/should-not-exist.out"]),
    ]
    failures = []

    for command_index, spec in enumerate(unavailable_specs):
        for payload_index, (payload_name, payload_args) in enumerate(payloads):
            sandbox = tmp_path / f"experiment-preflight-files-{command_index}-{payload_index}"
            sandbox.mkdir()
            args = [
                str((sandbox / item).resolve())
                if item.startswith("missing-") or item.startswith("should-not-exist")
                else item
                for item in payload_args
            ]
            touched_paths = [Path(item) for item in args if item.startswith(str(sandbox))]
            touched_parents = [path.parent for path in touched_paths if payload_name == "out-missing-parent"]
            before_snapshot = _database_snapshot(home)
            watched_file_contents = _text_file_snapshot(watched_files)
            watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
            code = cli.run(["--home", str(home), *spec.path, *args])
            captured = capsys.readouterr()
            fields = _output_field_map(captured.err) if captured.err else {}
            db_unchanged = _database_snapshot(home) == before_snapshot
            files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
            trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
            existing_touched_paths = [str(path) for path in touched_paths if path.exists()]
            existing_touched_parents = [str(path) for path in touched_parents if path.exists()]
            if (
                code != 4
                or captured.out
                or _output_field_labels(captured.err) != _error_field_labels()
                or fields.get("error code") != "COMMAND_UNAVAILABLE"
                or fields.get("exit code") != "4"
                or fields.get("reason") != "command is not available in the current context"
                or fields.get("next") != "none"
                or not db_unchanged
                or not files_unchanged
                or not trees_unchanged
                or existing_touched_paths
                or existing_touched_parents
            ):
                failures.append(
                    {
                        "command": " ".join(spec.path),
                        "payload": payload_name,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "fields": fields,
                        "existing paths": existing_touched_paths,
                        "existing parent paths": existing_touched_parents,
                        "db unchanged": db_unchanged,
                        "files unchanged": files_unchanged,
                        "trees unchanged": trees_unchanged,
                    }
                )

    assert failures == [], json.dumps(failures, indent=2)


def test_inspection_context_help_capability_display_uses_inspection_token_and_explicit_credentials(tmp_path: Path, monkeypatch, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    monkeypatch.chdir(home / "project-workspaces" / project_id)
    assert cli.run(["--home", str(home), "exp", "create", "--name", "cap-inspect-parent"]) == 0
    exp_fields = _output_field_map(capsys.readouterr().out)
    exp_id = exp_fields["exp id"]
    inspection_path = tmp_path / "inspection"
    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(inspection_path), "--commit", "latest"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(inspection_path)

    failures = []
    registry_by_command = {" ".join(spec.path): spec for spec in registry.COMMANDS}
    token_paths = cli.GLOBAL_PUBLIC | cli.INSPECTION_TOKEN | cli.OBSERVE_READ
    expected_token_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.path in token_paths]
    expected_token_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.path in token_paths],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.path not in token_paths],
    ]
    expected_admin_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.credential not in {"root", "token"}]
    expected_admin_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential not in {"root", "token"}],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential in {"root", "token"}],
    ]
    expected_root_commands = [" ".join(spec.path) for spec in registry.COMMANDS if spec.credential != "token"]
    expected_root_all_order = [
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential != "token"],
        *[" ".join(spec.path) for spec in registry.COMMANDS if spec.credential == "token"],
    ]

    def run_help(args: list[str]):
        code = cli.run(["--home", str(home), *args])
        return code, capsys.readouterr()

    for variant_name, help_args in [
        ("inspection-no-command", []),
        ("inspection-help", ["help"]),
        ("inspection-top-help", ["--help"]),
    ]:
        code, captured = run_help(help_args)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(expected_token_commands) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("context type") != "inspection"
            or header.get("credential source") != "context-token"
            or header.get("credential scope") != "token:inspection"
            or header.get("project id") != project_id
            or header.get("exp id") != exp_id
            or [fields.get("command") for fields in command_fields] != expected_token_commands
        ):
            failures.append({"variant": variant_name, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for fields in command_fields:
            command = fields.get("command")
            if (
                _output_field_labels("\n".join(f"{key}: {value}" for key, value in fields.items()))
                != ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"]
                or fields.get("available") != "true"
                or fields.get("locked reason") != "none"
                or fields.get("unlock hint") != "none"
                or fields.get("capability source") != "none"
                or fields.get("summary") != registry_by_command[command].summary
            ):
                failures.append({"variant": variant_name, "command": command, "fields": fields})

    for variant_name, help_args in [
        ("inspection-help-all", ["help", "--all", "--explain"]),
        ("inspection-top-help-all", ["--help", "--all", "--explain"]),
    ]:
        code, captured = run_help(help_args)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(registry.COMMANDS) + 1
            or _output_field_labels(blocks[0]) != ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"]
            or header.get("context type") != "inspection"
            or header.get("credential source") != "context-token"
            or header.get("credential scope") != "token:inspection"
            or header.get("project id") != project_id
            or header.get("exp id") != exp_id
            or [fields.get("command") for fields in command_fields] != expected_token_all_order
        ):
            failures.append({"variant": variant_name, "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for command, spec in registry_by_command.items():
            fields = next(item for item in command_fields if item.get("command") == command)
            expected_available = spec.path in token_paths
            expected_locked_reason = "none" if expected_available else "command is not exposed to inspection tokens"
            expected_unlock_hint = "none" if expected_available else "pass an explicit project admin/root key when appropriate"
            expected_capability_source = "global" if spec.path in cli.GLOBAL_PUBLIC else "inspection-token" if expected_available else expected_unlock_hint
            if (
                fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != spec.summary
            ):
                failures.append({"variant": variant_name, "command": command, "fields": fields})

    selected_submit = ["submit", "--message", "blocked", "--summary-file", str(tmp_path / "missing-summary.txt"), "--feedback-file", str(tmp_path / "missing-feedback.txt"), "--help", "--explain"]
    assert cli.run(["--home", str(home), *selected_submit]) == 0
    selected_blocks = _output_blocks(capsys.readouterr().out)
    selected_fields = _output_field_map(selected_blocks[1]) if len(selected_blocks) == 2 else {}
    if (
        len(selected_blocks) != 2
        or selected_fields.get("command") != "submit"
        or selected_fields.get("available") != "false"
        or selected_fields.get("locked reason") != "command is not exposed to inspection tokens"
        or selected_fields.get("unlock hint") != "pass an explicit project admin/root key when appropriate"
        or selected_fields.get("capability source") != "pass an explicit project admin/root key when appropriate"
    ):
        failures.append({"variant": "inspection-selected-submit", "fields": selected_fields})

    assert cli.run(["--home", str(home), "submit", "--message", "blocked", "--summary-file", str(tmp_path / "missing-summary.txt"), "--feedback-file", str(tmp_path / "missing-feedback.txt")]) == 4
    blocked_preflight = capsys.readouterr()
    if (
        blocked_preflight.out
        or _output_field_labels(blocked_preflight.err) != _error_field_labels()
        or "error code: COMMAND_UNAVAILABLE" not in blocked_preflight.err
    ):
        failures.append({"variant": "inspection-submit-preflight", "stdout": blocked_preflight.out, "stderr": blocked_preflight.err})

    explicit_variants = [
        (
            "admin",
            ["--key", admin_key, "help", "--all", "--explain"],
            "explicit-admin",
            "admin",
            expected_admin_all_order,
            expected_admin_commands,
            lambda spec: spec.credential not in {"root", "token"},
            lambda spec: "root credential required" if spec.credential == "root" else "experiment worktree token context required",
            lambda spec: "use a root key" if spec.credential == "root" else "run from an experiment worktree",
            lambda _spec: "project-admin",
        ),
        (
            "root",
            ["--key", root_key, "help", "--all", "--explain"],
            "explicit-root",
            "root",
            expected_root_all_order,
            expected_root_commands,
            lambda spec: spec.credential != "token",
            lambda _spec: "experiment worktree token context required",
            lambda _spec: "run from an experiment worktree",
            lambda _spec: "root",
        ),
    ]
    for (
        variant_name,
        help_args,
        expected_credential_source,
        expected_credential_scope,
        expected_all_order,
        expected_default_commands,
        is_available,
        locked_reason,
        unlock_hint,
        capability_source,
    ) in explicit_variants:
        code, captured = run_help(help_args)
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_blocks = blocks[1:]
        command_fields = [_output_field_map(block) for block in command_blocks]
        if (
            code != 0
            or captured.err
            or len(blocks) != len(registry.COMMANDS) + 1
            or header.get("context type") != "inspection"
            or header.get("credential source") != expected_credential_source
            or header.get("credential scope") != expected_credential_scope
            or header.get("project id") != project_id
            or header.get("exp id") != exp_id
            or [fields.get("command") for fields in command_fields] != expected_all_order
        ):
            failures.append({"variant": f"{variant_name}-all", "code": code, "stdout": captured.out, "stderr": captured.err})
            continue

        for command, spec in registry_by_command.items():
            fields = next(item for item in command_fields if item.get("command") == command)
            expected_available = is_available(spec)
            expected_locked_reason = "none" if expected_available else locked_reason(spec)
            expected_unlock_hint = "none" if expected_available else unlock_hint(spec)
            expected_capability_source = capability_source(spec) if expected_available else expected_unlock_hint
            if (
                fields.get("available") != ("true" if expected_available else "false")
                or fields.get("locked reason") != expected_locked_reason
                or fields.get("unlock hint") != expected_unlock_hint
                or fields.get("capability source") != expected_capability_source
                or fields.get("summary") != spec.summary
            ):
                failures.append({"variant": f"{variant_name}-all", "command": command, "fields": fields})

        code, captured = run_help(["--key", admin_key if variant_name == "admin" else root_key, "help"])
        blocks = _output_blocks(captured.out)
        header = _output_field_map(blocks[0]) if blocks else {}
        command_fields = [_output_field_map(block) for block in blocks[1:]]
        if (
            code != 0
            or captured.err
            or header.get("context type") != "inspection"
            or header.get("credential source") != expected_credential_source
            or [fields.get("command") for fields in command_fields] != expected_default_commands
        ):
            failures.append({"variant": f"{variant_name}-default", "code": code, "stdout": captured.out, "stderr": captured.err})

    assert failures == []


def test_inspection_context_unavailable_commands_preflight_before_handler_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    monkeypatch.chdir(home / "project-workspaces" / project_id)
    assert cli.run(["--home", str(home), "exp", "create", "--name", "inspection-preflight-parent"]) == 0
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]
    inspection_path = tmp_path / "inspection-preflight"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "checkout",
                exp_id,
                "--project",
                project_id,
                "--path",
                str(inspection_path),
                "--commit",
                "latest",
            ]
        )
        == 0
    )
    capsys.readouterr()
    monkeypatch.chdir(inspection_path)

    token_paths = cli.GLOBAL_PUBLIC | cli.INSPECTION_TOKEN | cli.OBSERVE_READ
    unavailable_specs = [spec for spec in registry.COMMANDS if spec.path not in token_paths]
    assert unavailable_specs

    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        inspection_path / ".alab" / "context.json",
        inspection_path / ".alab" / "token",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        inspection_path,
    ]
    payloads = [
        ("unsupported", ["--definitely-unsupported"]),
        ("value-file", ["--value-file", "missing-value.txt"]),
        ("body-file", ["--body-file", "missing-body.txt"]),
        ("submit-files", ["--summary-file", "missing-summary.txt", "--feedback-file", "missing-feedback.txt"]),
        ("config", ["--config", "missing-config.toml"]),
        ("out", ["--out", "should-not-exist.out"]),
        ("out-missing-parent", ["--out", "missing-output-parent/should-not-exist.out"]),
    ]
    failures = []

    for command_index, spec in enumerate(unavailable_specs):
        for payload_index, (payload_name, payload_args) in enumerate(payloads):
            sandbox = tmp_path / f"inspection-preflight-files-{command_index}-{payload_index}"
            sandbox.mkdir()
            args = [
                str((sandbox / item).resolve())
                if item.startswith("missing-") or item.startswith("should-not-exist")
                else item
                for item in payload_args
            ]
            touched_paths = [Path(item) for item in args if item.startswith(str(sandbox))]
            touched_parents = [path.parent for path in touched_paths if payload_name == "out-missing-parent"]
            before_snapshot = _database_snapshot(home)
            watched_file_contents = _text_file_snapshot(watched_files)
            watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
            code = cli.run(["--home", str(home), *spec.path, *args])
            captured = capsys.readouterr()
            fields = _output_field_map(captured.err) if captured.err else {}
            db_unchanged = _database_snapshot(home) == before_snapshot
            files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
            trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
            existing_touched_paths = [str(path) for path in touched_paths if path.exists()]
            existing_touched_parents = [str(path) for path in touched_parents if path.exists()]
            if (
                code != 4
                or captured.out
                or _output_field_labels(captured.err) != _error_field_labels()
                or fields.get("error code") != "COMMAND_UNAVAILABLE"
                or fields.get("exit code") != "4"
                or fields.get("reason") != "command is not available in the current context"
                or fields.get("next") != "none"
                or not db_unchanged
                or not files_unchanged
                or not trees_unchanged
                or existing_touched_paths
                or existing_touched_parents
            ):
                failures.append(
                    {
                        "command": " ".join(spec.path),
                        "payload": payload_name,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "fields": fields,
                        "existing paths": existing_touched_paths,
                        "existing parent paths": existing_touched_parents,
                        "db unchanged": db_unchanged,
                        "files unchanged": files_unchanged,
                        "trees unchanged": trees_unchanged,
                    }
                )

    assert failures == [], json.dumps(failures, indent=2)


def test_explicit_keys_preserve_context_conflict_before_handler_effects(tmp_path: Path, monkeypatch, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    monkeypatch.chdir(home / "project-workspaces" / project_id)
    assert cli.run(["--home", str(home), "exp", "create", "--name", "context-conflict-parent"]) == 0
    exp_fields = _output_field_map(capsys.readouterr().out)
    exp_path = Path(exp_fields["worktree path"])
    exp_id = exp_fields["exp id"]
    inspection_path = tmp_path / "context-conflict-inspection"
    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(inspection_path), "--commit", "latest"]) == 0
    capsys.readouterr()

    failures = []
    other_project_id = f"{project_id}-other"
    contexts = [
        ("experiment", exp_path),
        ("inspection", inspection_path),
    ]
    credentials = [
        ("admin", admin_key, "explicit-admin"),
        ("root", root_key, "explicit-root"),
    ]

    for context_name, context_path in contexts:
        monkeypatch.chdir(context_path)
        for credential_name, raw_key, expected_credential_source in credentials:
            for key_mode in ("key", "key-stdin"):
                out_path = tmp_path / f"{context_name}-{credential_name}-{key_mode}-blocked.toml"
                key_args = ["--key", raw_key] if key_mode == "key" else ["--key-stdin"]
                selected_args = [
                    *key_args,
                    "project",
                    "config",
                    "export",
                    "--project",
                    other_project_id,
                    "--out",
                    str(out_path),
                    "--help",
                    "--explain",
                ]
                if key_mode == "key-stdin":
                    monkeypatch.setattr(sys, "stdin", io.StringIO(raw_key + "\n"))
                assert cli.run(["--home", str(home), *selected_args]) == 0
                selected_blocks = _output_blocks(capsys.readouterr().out)
                selected_header = _output_field_map(selected_blocks[0]) if selected_blocks else {}
                selected_fields = _output_field_map(selected_blocks[1]) if len(selected_blocks) == 2 else {}
                if (
                    len(selected_blocks) != 2
                    or selected_header.get("context type") != context_name
                    or selected_header.get("credential source") != expected_credential_source
                    or selected_header.get("project id") != project_id
                    or selected_header.get("exp id") != exp_id
                    or selected_fields.get("command") != "project config export"
                    or selected_fields.get("available") != "false"
                    or selected_fields.get("locked reason") != "explicit project conflicts with current context"
                    or selected_fields.get("unlock hint") != "leave the context or use the matching project id"
                    or selected_fields.get("capability source") != "leave the context or use the matching project id"
                    or out_path.exists()
                ):
                    failures.append(
                        {
                            "variant": f"{context_name}-{credential_name}-{key_mode}-selected",
                            "header": selected_header,
                            "fields": selected_fields,
                            "out_exists": out_path.exists(),
                        }
                    )

                if key_mode == "key-stdin":
                    monkeypatch.setattr(sys, "stdin", io.StringIO(raw_key + "\n"))
                assert cli.run(["--home", str(home), *selected_args[:-2]]) == 4
                direct = capsys.readouterr()
                if (
                    direct.out
                    or _output_field_labels(direct.err) != _error_field_labels()
                    or "error code: CONTEXT_CONFLICT" not in direct.err
                    or "explicit --project conflicts with current ALab context" not in direct.err
                    or out_path.exists()
                ):
                    failures.append(
                        {
                            "variant": f"{context_name}-{credential_name}-{key_mode}-direct",
                            "stdout": direct.out,
                            "stderr": direct.err,
                            "out_exists": out_path.exists(),
                        }
                    )

    assert failures == []


def test_context_help_treats_key_stdin_like_explicit_key(tmp_path: Path, monkeypatch, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    project_path = home / "project-workspaces" / project_id
    monkeypatch.chdir(project_path)
    assert cli.run(["--home", str(home), "exp", "create", "--name", "stdin-equivalence"]) == 0
    exp_fields = _output_field_map(capsys.readouterr().out)
    exp_path = Path(exp_fields["worktree path"])
    exp_id = exp_fields["exp id"]
    inspection_path = tmp_path / "stdin-equivalence-inspection"
    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(inspection_path), "--commit", "latest"]) == 0
    capsys.readouterr()

    failures = []
    contexts = [
        ("project", project_path),
        ("experiment", exp_path),
        ("inspection", inspection_path),
    ]
    credentials = [
        ("admin", admin_key, "explicit-admin"),
        ("root", root_key, "explicit-root"),
    ]
    help_variants = [
        ["help"],
        ["help", "--all", "--explain"],
        ["--help", "--all", "--explain"],
    ]

    for context_name, context_path in contexts:
        monkeypatch.chdir(context_path)
        for credential_name, raw_key, expected_credential_source in credentials:
            for help_args in help_variants:
                assert cli.run(["--home", str(home), "--key", raw_key, *help_args]) == 0
                key_out = capsys.readouterr()
                monkeypatch.setattr(sys, "stdin", io.StringIO(raw_key + "\n"))
                assert cli.run(["--home", str(home), "--key-stdin", *help_args]) == 0
                stdin_out = capsys.readouterr()
                header = _output_field_map(_output_blocks(stdin_out.out)[0]) if stdin_out.out else {}
                if (
                    key_out.err
                    or stdin_out.err
                    or key_out.out != stdin_out.out
                    or header.get("context type") != context_name
                    or header.get("credential source") != expected_credential_source
                ):
                    failures.append(
                        {
                            "context": context_name,
                            "credential": credential_name,
                            "help_args": help_args,
                            "key_stdout": key_out.out,
                            "key_stderr": key_out.err,
                            "stdin_stdout": stdin_out.out,
                            "stdin_stderr": stdin_out.err,
                        }
                    )

    assert failures == []


def test_context_read_commands_treat_key_stdin_like_explicit_key(tmp_path: Path, monkeypatch, capsys) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    project_path = home / "project-workspaces" / project_id
    monkeypatch.chdir(project_path)
    assert cli.run(["--home", str(home), "exp", "create", "--name", "stdin-read-equivalence"]) == 0
    exp_fields = _output_field_map(capsys.readouterr().out)
    exp_path = Path(exp_fields["worktree path"])
    inspection_path = tmp_path / "stdin-read-equivalence-inspection"
    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_fields["exp id"], "--project", project_id, "--path", str(inspection_path), "--commit", "latest"]) == 0
    capsys.readouterr()

    failures = []
    contexts = [
        ("project", project_path),
        ("experiment", exp_path),
        ("inspection", inspection_path),
    ]
    credentials = [
        ("admin", admin_key),
        ("root", root_key),
    ]
    commands = [
        ["project", "show"],
        ["project", "config", "show"],
        ["project", "show", "--project", project_id],
        ["project", "config", "show", "--project", project_id],
    ]

    for context_name, context_path in contexts:
        monkeypatch.chdir(context_path)
        for credential_name, raw_key in credentials:
            for command in commands:
                assert cli.run(["--home", str(home), "--key", raw_key, *command]) == 0
                key_result = capsys.readouterr()
                monkeypatch.setattr(sys, "stdin", io.StringIO(raw_key + "\n"))
                assert cli.run(["--home", str(home), "--key-stdin", *command]) == 0
                stdin_result = capsys.readouterr()
                if key_result.out != stdin_result.out or key_result.err != stdin_result.err:
                    failures.append(
                        {
                            "context": context_name,
                            "credential": credential_name,
                            "command": command,
                            "key_stdout": key_result.out,
                            "key_stderr": key_result.err,
                            "stdin_stdout": stdin_result.out,
                            "stdin_stderr": stdin_result.err,
                        }
                    )

    assert failures == []


def test_status_object_type_tracks_context_mode(tmp_path: Path, monkeypatch, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    project_path = home / "project-workspaces" / project_id
    monkeypatch.chdir(project_path)

    assert cli.run(["--home", str(home), "status"]) == 0
    project_out = capsys.readouterr()

    assert cli.run(["--home", str(home), "exp", "create", "--name", "status-mode"]) == 0
    exp_fields = _output_field_map(capsys.readouterr().out)
    exp_id = exp_fields["exp id"]
    exp_path = Path(exp_fields["worktree path"])
    monkeypatch.chdir(exp_path)
    assert cli.run(["--home", str(home), "status"]) == 0
    exp_out = capsys.readouterr()

    inspection_path = tmp_path / "status-mode-inspection"
    monkeypatch.chdir(project_path)
    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(inspection_path), "--commit", "latest"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(inspection_path)
    assert cli.run(["--home", str(home), "status"]) == 0
    inspection_out = capsys.readouterr()

    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute("UPDATE projects SET status = 'invalid' WHERE project_id = ?", (project_id,))
    monkeypatch.chdir(tmp_path)
    assert cli.run(["--home", str(home), "status", "--project", project_id]) == 0
    invalid_public_out = capsys.readouterr()

    assert {
        "project": (project_out.err, _output_object_type(project_out.out), _output_field_labels(project_out.out)),
        "experiment": (exp_out.err, _output_object_type(exp_out.out), _output_field_labels(exp_out.out)),
        "inspection": (inspection_out.err, _output_object_type(inspection_out.out), _output_field_labels(inspection_out.out)),
        "invalid public": (
            invalid_public_out.err,
            _output_object_type(invalid_public_out.out),
            _output_field_labels(invalid_public_out.out),
        ),
    } == {
        "project": ("", "project", _documented_success_labels_for_scope("status", "project")),
        "experiment": ("", "experiment", _documented_success_labels_for_scope("status", "experiment")),
        "inspection": ("", "inspection_checkout", _documented_success_labels_for_scope("status", "inspection")),
        "invalid public": ("", "project", _documented_success_labels_for_scope("status", "public-invalid")),
    }


def test_public_status_excludes_private_project_history_and_runtime_fields(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    source = tmp_path / "public-status-source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
import sys
from pathlib import Path

print("PUBLIC_STATUS_RUN_STDOUT_MARKER")
print("PUBLIC_STATUS_RUN_STDERR_MARKER", file=sys.stderr)
Path(os.environ["ALAB_RUN_DIR"], "PUBLIC_STATUS_ARTIFACT_MARKER.txt").write_text(
    "PUBLIC_STATUS_ARTIFACT_BYTES_MARKER\\n",
    encoding="utf-8",
)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runner_command = [
        sys.executable,
        "-c",
        "import runpy; print('PUBLIC_STATUS_RUNNER_COMMAND_MARKER'); runpy.run_path('main.py', run_name='__main__')",
    ]
    config = tmp_path / "public-status.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Public Status Privacy"
task = "Safe public status task"
goal = "Safe public status goal"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = {json.dumps(runner_command)}

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:PUBLIC_STATUS_ARTIFACT_MARKER.txt"]

[env]
PUBLIC_STATUS_ENV_NAME = "PUBLIC_STATUS_ENV_VALUE_MARKER"

[secret_env]
PUBLIC_STATUS_SECRET_NAME = "PUBLIC_STATUS_SECRET_VALUE_MARKER"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
            ]
        )
        == 0
    )
    project_fields = _output_field_map(capsys.readouterr().out)
    project_id = project_fields["project id"]
    admin_key = project_fields["admin key"]

    exp_path = tmp_path / "public-status-exp"
    assert cli.run(["--home", str(home), "--key", admin_key, "exp", "create", "--project", project_id, "--name", "Public Status Exp", "--path", str(exp_path)]) == 0
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]
    monkeypatch.chdir(exp_path)
    assert cli.run(["--home", str(home), "run", "--message", "PUBLIC_STATUS_RUN_MESSAGE_MARKER"]) == 0
    run_fields = _output_field_map(capsys.readouterr().out)
    run_id = run_fields["run id"]
    assert cli.run(["--home", str(home), "annotate", "add", "--target", f"run:{run_id}", "--body", "PUBLIC_STATUS_ANNOTATION_MARKER"]) == 0
    annotation_id = _output_field_map(capsys.readouterr().out)["annotation id"]

    now = services.utc_now()
    hidden_log_id = services.new_id("log", "PUBLIC_STATUS_HIDDEN_LOG_MARKER")
    hidden_log_path = tmp_path / "PUBLIC_STATUS_ADAPTER_STAGING_PATH_MARKER" / "hidden.log"
    hidden_log_path.parent.mkdir(parents=True)
    hidden_log_path.write_text("PUBLIC_STATUS_HIDDEN_LOG_MARKER\n", encoding="utf-8")
    hidden_artifact_id = services.new_id("art", "PUBLIC_STATUS_HIDDEN_ASSET_MARKER")
    hidden_artifact_path = tmp_path / "PUBLIC_STATUS_HIDDEN_ASSET_MARKER" / "asset.bin"
    hidden_artifact_path.parent.mkdir(parents=True)
    hidden_artifact_path.write_text("hidden asset\n", encoding="utf-8")
    catalog_path = tmp_path / "PUBLIC_STATUS_ABSOLUTE_CATALOG_PATH_MARKER"
    cache_path = tmp_path / "PUBLIC_STATUS_ADAPTER_STAGING_CACHE_MARKER"
    with sqlite3.connect(home / "alab.db") as conn:
        artifact_ids = [
            row[0]
            for row in conn.execute(
                "SELECT artifact_id FROM artifacts WHERE project_id = ? AND run_id = ?",
                (project_id, run_id),
            ).fetchall()
        ]
        log_ids = [
            row[0]
            for row in conn.execute(
                "SELECT log_id FROM log_streams WHERE project_id = ? AND run_id = ?",
                (project_id, run_id),
            ).fetchall()
        ]
        conn.execute(
            """
            INSERT INTO log_streams(log_id, project_id, exp_id, run_id, validation_id, stream,
              size_bytes, stored_bytes, content_hash, truncated, hidden, archive_status, file_path,
              preview_text, created_at)
            VALUES (?, ?, ?, ?, NULL, 'hidden_stdout', ?, ?, ?, 0, 1, 'active', ?, ?, ?)
            """,
            (
                hidden_log_id,
                project_id,
                exp_id,
                run_id,
                len("PUBLIC_STATUS_HIDDEN_LOG_MARKER\n"),
                len("PUBLIC_STATUS_HIDDEN_LOG_MARKER\n"),
                "sha256:" + "1" * 64,
                str(hidden_log_path),
                "PUBLIC_STATUS_HIDDEN_LOG_MARKER",
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO artifacts(artifact_id, project_id, exp_id, run_id, validation_id, root,
              relative_path, size_bytes, content_hash, status, archive_status, blob_path,
              capture_error, created_at)
            VALUES (?, ?, ?, ?, NULL, 'run', ?, 12, ?, 'captured', 'active', ?, NULL, ?)
            """,
            (
                hidden_artifact_id,
                project_id,
                exp_id,
                run_id,
                "PUBLIC_STATUS_HIDDEN_ASSET_MARKER/private.txt",
                "sha256:" + "2" * 64,
                str(hidden_artifact_path),
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO catalogs(catalog_key, catalog_type, origin_url, pinned_commit, local_path,
              status, metadata_json, retrieved_at, updated_at, removed_at)
            VALUES ('skydiscover', 'skydiscover', 'https://example.invalid/catalog.git', ?, ?,
              'active', ?, ?, ?, NULL)
            """,
            (
                "a" * 40,
                str(catalog_path),
                json.dumps({"adapter_staging": "PUBLIC_STATUS_ADAPTER_STAGING_PATH_MARKER"}),
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO cache_entries(cache_id, cache_kind, cache_key, project_id, path,
              docker_tag, size_bytes, status, metadata_json, created_at, last_used_at, removed_at)
            VALUES (?, 'skydiscover_python_env', 'public-status-cache', ?, ?, NULL, 1,
              'active', ?, ?, ?, NULL)
            """,
            (
                services.new_id("cache", "PUBLIC_STATUS_ADAPTER_STAGING_CACHE_MARKER"),
                project_id,
                str(cache_path),
                json.dumps({"adapter_staging": "PUBLIC_STATUS_ADAPTER_STAGING_CACHE_MARKER"}),
                now,
                now,
            ),
        )

    monkeypatch.chdir(tmp_path)
    assert cli.run(["--home", str(home), "status", "--project", project_id]) == 0
    public_status = capsys.readouterr()

    invalid_source = tmp_path / "invalid-public-status-source"
    invalid_source.mkdir()
    (invalid_source / "main.py").write_text("print('invalid')\n", encoding="utf-8")
    invalid_config = tmp_path / "invalid-public-status.toml"
    invalid_config.write_text(
        f"""
schema_version = 1

[project]
name = "Invalid Public Status Privacy"
task = "Invalid safe public status task"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('PUBLIC_STATUS_BASELINE_FAILURE_LOG_MARKER'); import sys; sys.exit(7)"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[env]
INVALID_PUBLIC_STATUS_ENV = "INVALID_PUBLIC_STATUS_ENV_VALUE_MARKER"

[secret_env]
INVALID_PUBLIC_STATUS_SECRET_NAME = "INVALID_PUBLIC_STATUS_SECRET_VALUE_MARKER"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(invalid_config),
                "--source-path",
                str(invalid_source),
            ]
        )
        == 1
    )
    invalid_project_id = _output_field_map(capsys.readouterr().out)["project id"]
    assert cli.run(["--home", str(home), "status", "--project", invalid_project_id]) == 0
    invalid_public_status = capsys.readouterr()

    forbidden_fragments = {
        "PUBLIC_STATUS_ENV_NAME",
        "PUBLIC_STATUS_ENV_VALUE_MARKER",
        "PUBLIC_STATUS_SECRET_NAME",
        "PUBLIC_STATUS_SECRET_VALUE_MARKER",
        "PUBLIC_STATUS_RUNNER_COMMAND_MARKER",
        "PUBLIC_STATUS_RUN_STDOUT_MARKER",
        "PUBLIC_STATUS_RUN_STDERR_MARKER",
        "PUBLIC_STATUS_RUN_MESSAGE_MARKER",
        "PUBLIC_STATUS_ARTIFACT_MARKER",
        "PUBLIC_STATUS_ARTIFACT_BYTES_MARKER",
        "PUBLIC_STATUS_ANNOTATION_MARKER",
        "PUBLIC_STATUS_HIDDEN_LOG_MARKER",
        "PUBLIC_STATUS_HIDDEN_ASSET_MARKER",
        "PUBLIC_STATUS_ABSOLUTE_CATALOG_PATH_MARKER",
        "PUBLIC_STATUS_ADAPTER_STAGING_PATH_MARKER",
        "PUBLIC_STATUS_ADAPTER_STAGING_CACHE_MARKER",
        "PUBLIC_STATUS_BASELINE_FAILURE_LOG_MARKER",
        "INVALID_PUBLIC_STATUS_ENV",
        "INVALID_PUBLIC_STATUS_ENV_VALUE_MARKER",
        "INVALID_PUBLIC_STATUS_SECRET_NAME",
        "INVALID_PUBLIC_STATUS_SECRET_VALUE_MARKER",
        str(source),
        str(exp_path),
        str(hidden_log_path),
        str(hidden_artifact_path),
        str(catalog_path),
        str(cache_path),
        exp_id,
        run_id,
        annotation_id,
        hidden_log_id,
        hidden_artifact_id,
        *artifact_ids,
        *log_ids,
    }
    public_combined = public_status.out + public_status.err
    invalid_combined = invalid_public_status.out + invalid_public_status.err

    assert {
        "public stderr": public_status.err,
        "public labels": _output_field_labels(public_status.out),
        "invalid stderr": invalid_public_status.err,
        "invalid labels": _output_field_labels(invalid_public_status.out),
        "public leaks": sorted(fragment for fragment in forbidden_fragments if fragment and fragment in public_combined),
        "invalid leaks": sorted(fragment for fragment in forbidden_fragments if fragment and fragment in invalid_combined),
    } == {
        "public stderr": "",
        "public labels": _documented_success_labels_for_scope("status", "public"),
        "invalid stderr": "",
        "invalid labels": _documented_success_labels_for_scope("status", "public-invalid"),
        "public leaks": [],
        "invalid leaks": [],
    }


def test_context_token_file_permission_warning_renders_after_primary_result(tmp_path: Path, monkeypatch, capsys) -> None:
    home, _root_key, project_id, _admin_key = _init_capability_project(tmp_path, capsys)
    project_path = home / "project-workspaces" / project_id
    monkeypatch.chdir(project_path)
    assert cli.run(["--home", str(home), "exp", "create", "--name", "permission-warning"]) == 0
    create_fields = _output_field_map(capsys.readouterr().out)
    exp_path = Path(create_fields["worktree path"])
    token_path = exp_path / ".alab" / "token"
    token_path.chmod(0o644)

    monkeypatch.chdir(exp_path)
    assert cli.run(["--home", str(home), "status"]) == 0
    status_out = capsys.readouterr()
    blocks = _output_blocks(status_out.out)

    assert {
        "stderr": status_out.err,
        "block count": len(blocks),
        "primary labels": _output_field_labels(blocks[0]),
        "warning labels": _output_field_labels(blocks[1]),
        "warning fields": _output_field_map(blocks[1]),
        "token mode": oct(token_path.stat().st_mode & 0o777),
    } == {
        "stderr": "",
        "block count": 2,
        "primary labels": _documented_success_labels_for_scope("status", "experiment"),
        "warning labels": ["object", "warning code", "warning reason"],
        "warning fields": {
            "object": "warning",
            "warning code": "TOKEN_FILE_PERMISSIONS",
            "warning reason": "token file permissions are broader than 0600",
        },
        "token mode": "0o644",
    }


def test_cli_token_writes_use_private_permissions_and_git_exclude(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    worktree_path = tmp_path / "token-private-worktree"
    checkout_path = tmp_path / "token-private-checkout"
    restored_path = tmp_path / "token-private-restored"

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Token Private Contract",
                "--path",
                str(worktree_path),
            ]
        )
        == 0
    )
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]
    create_exclude_path = _git_exclude_path(worktree_path)
    create_token_mode = _token_file_mode(worktree_path)
    create_exclude_present = ".alab/" in create_exclude_path.read_text(encoding="utf-8")

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "checkout",
                exp_id,
                "--project",
                project_id,
                "--path",
                str(checkout_path),
                "--commit",
                "latest",
            ]
        )
        == 0
    )
    capsys.readouterr()
    checkout_exclude_path = _git_exclude_path(checkout_path)
    checkout_token_mode = _token_file_mode(checkout_path)
    checkout_exclude_present = ".alab/" in checkout_exclude_path.read_text(encoding="utf-8")

    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "worktree",
                "remove",
                exp_id,
                "--project",
                project_id,
                "--force",
                "--confirm",
                exp_id,
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "worktree",
                "restore",
                exp_id,
                "--project",
                project_id,
                "--path",
                str(restored_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    restored_exclude_path = _git_exclude_path(restored_path)
    restore_token_mode = _token_file_mode(restored_path)
    restore_exclude_present = ".alab/" in restored_exclude_path.read_text(encoding="utf-8")

    restored_exclude_path.write_text("# user removed ALab local ignore\n", encoding="utf-8")
    regenerate_exclude_missing_before = ".alab/" in restored_exclude_path.read_text(encoding="utf-8")
    (restored_path / ".alab" / "token").chmod(0o644)
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "token",
                "regenerate",
                exp_id,
                "--project",
                project_id,
                "--mode",
                "worktree",
            ]
        )
        == 0
    )
    regenerate_out = capsys.readouterr()

    assert {
        "create token mode": create_token_mode,
        "create exclude": create_exclude_present,
        "checkout token mode": checkout_token_mode,
        "checkout exclude": checkout_exclude_present,
        "restore token mode": restore_token_mode,
        "restore exclude": restore_exclude_present,
        "regenerate exclude before": regenerate_exclude_missing_before,
        "regenerate stderr": regenerate_out.err,
        "regenerate token mode": _token_file_mode(restored_path),
        "regenerate exclude": ".alab/" in restored_exclude_path.read_text(encoding="utf-8"),
    } == {
        "create token mode": "0o600",
        "create exclude": True,
        "checkout token mode": "0o600",
        "checkout exclude": True,
        "restore token mode": "0o600",
        "restore exclude": True,
        "regenerate exclude before": False,
        "regenerate stderr": "",
        "regenerate token mode": "0o600",
        "regenerate exclude": True,
    }


def test_logs_show_rejects_duplicate_include_hidden_before_lookup(tmp_path: Path, capsys) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    before_snapshot = _database_snapshot(home)
    config_before = (home / "config.toml").read_text(encoding="utf-8")
    missing_log_id = "log-missing-" + "H" * 22

    code = cli.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "logs",
            "show",
            missing_log_id,
            "--project",
            project_id,
            "--include-hidden",
            "--include-hidden",
        ]
    )
    captured = capsys.readouterr()

    assert {
        "code": code,
        "stdout": captured.out,
        "labels": _output_field_labels(captured.err),
        "fields": _output_field_map(captured.err),
        "db unchanged": _database_snapshot(home) == before_snapshot,
        "config unchanged": (home / "config.toml").read_text(encoding="utf-8") == config_before,
    } == {
        "code": 2,
        "stdout": "",
        "labels": _error_field_labels(),
        "fields": {
            "object": "error",
            "message": "Command failed.",
            "error code": "CONFIG_INVALID",
            "exit code": "2",
            "reason": "--include-hidden may be provided once",
            "next": "none",
        },
        "db unchanged": True,
        "config unchanged": True,
    }


def test_representative_singleton_duplicate_options_fail_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    admin_args = ["--home", str(home), "--key", admin_key]
    root_args = ["--home", str(home), "--key", root_key]
    exp_path = tmp_path / "duplicate-option-exp"
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Duplicate Option Matrix",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]

    source_a = tmp_path / "duplicate-source-a"
    source_b = tmp_path / "duplicate-source-b"
    source_a.mkdir()
    source_b.mkdir()
    (source_a / "main.py").write_text("print('a')\n", encoding="utf-8")
    (source_b / "main.py").write_text("print('b')\n", encoding="utf-8")
    missing_config = tmp_path / "missing-project-config.toml"
    missing_value_a = tmp_path / "missing-value-a.txt"
    missing_value_b = tmp_path / "missing-value-b.txt"
    missing_body_a = tmp_path / "missing-body-a.txt"
    missing_body_b = tmp_path / "missing-body-b.txt"
    missing_log_id = "log-missing-" + "D" * 22
    missing_annotation_id = "ann-missing-" + "D" * 22

    cases = [
        (
            "project init duplicate source path",
            [
                *root_args,
                "project",
                "init",
                "local",
                "--config",
                str(missing_config),
                "--source-path",
                str(source_a),
                "--source-path",
                str(source_b),
            ],
            None,
            "--source-path may be provided once",
        ),
        (
            "source import duplicate source path",
            [
                *admin_args,
                "source",
                "import",
                "--project",
                project_id,
                "--source-path",
                str(source_a),
                "--source-path",
                str(source_b),
            ],
            None,
            "--source-path may be provided once",
        ),
        (
            "exp create duplicate path",
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Duplicate Path",
                "--path",
                str(tmp_path / "duplicate-path-a"),
                "--path",
                str(tmp_path / "duplicate-path-b"),
            ],
            None,
            "--path may be provided once",
        ),
        (
            "project secret set duplicate value file",
            [
                *admin_args,
                "project",
                "secret",
                "set",
                "TOKEN",
                "--project",
                project_id,
                "--value-file",
                str(missing_value_a),
                "--value-file",
                str(missing_value_b),
            ],
            None,
            "--value-file may be provided once",
        ),
        (
            "project secret gc duplicate apply",
            [
                *admin_args,
                "project",
                "secret",
                "gc",
                "--project",
                project_id,
                "--apply",
                "--apply",
            ],
            None,
            "--apply may be provided once",
        ),
        (
            "submit duplicate summary stdin",
            [
                "--home",
                str(home),
                "submit",
                "--message",
                "duplicate option matrix",
                "--summary-stdin",
                "--summary-stdin",
                "--feedback",
                "looks good",
                "--ref",
                "none",
            ],
            exp_path,
            "--summary-stdin may be provided once",
        ),
        (
            "exp best duplicate sort",
            [
                *admin_args,
                "exp",
                "best",
                "--project",
                project_id,
                "--sort",
                "reward:desc",
                "--sort",
                "reward:asc",
            ],
            None,
            "--sort may be provided once",
        ),
        (
            "exp token list duplicate mode",
            [
                *admin_args,
                "exp",
                "token",
                "list",
                exp_id,
                "--project",
                project_id,
                "--mode",
                "worktree",
                "--mode",
                "inspection",
            ],
            None,
            "--mode may be provided once",
        ),
        (
            "exp token revoke duplicate all",
            [
                *admin_args,
                "exp",
                "token",
                "revoke",
                exp_id,
                "--project",
                project_id,
                "--all",
                "--all",
            ],
            None,
            "--all may be provided once",
        ),
        (
            "logs show duplicate include hidden",
            [
                *admin_args,
                "logs",
                "show",
                missing_log_id,
                "--project",
                project_id,
                "--include-hidden",
                "--include-hidden",
            ],
            None,
            "--include-hidden may be provided once",
        ),
        (
            "annotate add duplicate target",
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                f"exp:{exp_id}",
                "--target",
                f"exp:{exp_id}",
                "--body",
                "duplicate target",
            ],
            None,
            "--target may be provided once",
        ),
        (
            "annotate edit duplicate body file",
            [
                *admin_args,
                "annotate",
                "edit",
                missing_annotation_id,
                "--project",
                project_id,
                "--body-file",
                str(missing_body_a),
                "--body-file",
                str(missing_body_b),
            ],
            None,
            "--body-file may be provided once",
        ),
    ]

    project_marker_path = home / "project-workspaces" / project_id / ".alab" / "context.json"
    experiment_marker_path = exp_path / ".alab" / "context.json"
    token_path = exp_path / ".alab" / "token"
    untouched_missing_paths = [missing_config, missing_value_a, missing_value_b, missing_body_a, missing_body_b]

    failures = []
    for name, args, cwd, reason in cases:
        before_snapshot = _database_snapshot(home)
        config_before = (home / "config.toml").read_text(encoding="utf-8")
        project_marker_before = project_marker_path.read_text(encoding="utf-8")
        experiment_marker_before = experiment_marker_path.read_text(encoding="utf-8")
        token_before = token_path.read_text(encoding="utf-8")

        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()

        checks = {
            "code": code,
            "stdout": captured.out,
            "labels": _output_field_labels(captured.err),
            "fields": _output_field_map(captured.err) if captured.err else {},
            "db unchanged": _database_snapshot(home) == before_snapshot,
            "config unchanged": (home / "config.toml").read_text(encoding="utf-8") == config_before,
            "project marker unchanged": project_marker_path.read_text(encoding="utf-8") == project_marker_before,
            "experiment marker unchanged": experiment_marker_path.read_text(encoding="utf-8") == experiment_marker_before,
            "token unchanged": token_path.read_text(encoding="utf-8") == token_before,
            "missing paths untouched": all(not path.exists() for path in untouched_missing_paths),
        }
        expected_fields = {
            "object": "error",
            "message": "Command failed.",
            "error code": "CONFIG_INVALID",
            "exit code": "2",
            "reason": reason,
            "next": "none",
        }
        if checks != {
            "code": 2,
            "stdout": "",
            "labels": _error_field_labels(),
            "fields": expected_fields,
            "db unchanged": True,
            "config unchanged": True,
            "project marker unchanged": True,
            "experiment marker unchanged": True,
            "token unchanged": True,
            "missing paths untouched": True,
        }:
            failures.append({"case": name, "args": args, "cwd": str(cwd) if cwd else None, **checks})

    assert failures == []


def test_registered_singleton_options_reject_duplicates_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "generated-duplicate-option-exp"
    extra_worktree_path = tmp_path / "generated-duplicate-option-created"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Generated Duplicate Option Context",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    project_config_path = tmp_path / "generated-duplicate-option-config.toml"
    source_path = tmp_path / "generated-duplicate-option-source"
    secret_file_path = tmp_path / "generated-duplicate-option-secret.txt"
    catalog_upstream = tmp_path / "generated-duplicate-option-catalog"
    export_path = tmp_path / "generated-duplicate-option-export.toml"
    source_path.mkdir()
    (source_path / "main.py").write_text("print('duplicate option')\n", encoding="utf-8")
    project_config_path.write_text(
        """
schema_version = 1

[project]
name = "Generated Duplicate Option Import"
task = "Verify duplicate options fail before writes"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = ["python", "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    secret_file_path.write_text("generated-duplicate-option-secret\n", encoding="utf-8")
    _init_catalog_upstream(catalog_upstream)

    project_marker_path = home / "project-workspaces" / project_id / ".alab" / "context.json"
    watched_files = [
        home / "config.toml",
        project_marker_path,
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
        project_config_path,
        secret_file_path,
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
        source_path,
        catalog_upstream,
    ]
    command_singleton_options = {
        spec.path: _command_local_singleton_options(spec)
        for spec in registry.COMMANDS
        if _command_local_singleton_options(spec)
    }
    assert "--tag" not in command_singleton_options[("exp", "create")]
    assert "--ref" not in command_singleton_options[("submit",)]
    assert "--root" in command_singleton_options[("key", "list")]
    assert "--root" in command_singleton_options[("artifacts", "list")]
    failures = []

    for spec in registry.COMMANDS:
        for option in command_singleton_options.get(spec.path, []):
            args, cwd = _duplicate_option_invocation(
                spec,
                option,
                home=home,
                root_key=root_key,
                admin_key=admin_key,
                project_id=project_id,
                exp_path=exp_path,
                project_marker_path=project_marker_path,
                project_config_path=project_config_path,
                catalog_upstream=catalog_upstream,
                export_path=export_path,
                extra_worktree_path=extra_worktree_path,
                source_path=source_path,
                secret_file_path=secret_file_path,
            )
            before_snapshot = _database_snapshot(home)
            watched_file_contents = _text_file_snapshot(watched_files)
            watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
            with monkeypatch.context() as context:
                if cwd is not None:
                    context.chdir(cwd)
                code = cli.run(args)
            captured = capsys.readouterr()
            fields = _output_field_map(captured.err) if captured.err else {}
            db_unchanged = _database_snapshot(home) == before_snapshot
            files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
            trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
            export_absent = not export_path.exists()
            extra_worktree_absent = not extra_worktree_path.exists()
            if (
                code != 2
                or captured.out
                or _output_field_labels(captured.err) != _error_field_labels()
                or fields.get("error code") != "CONFIG_INVALID"
                or fields.get("exit code") != "2"
                or fields.get("reason") != f"{option} may be provided once"
                or fields.get("next") != "none"
                or not db_unchanged
                or not files_unchanged
                or not trees_unchanged
                or not export_absent
                or not extra_worktree_absent
            ):
                failures.append(
                    {
                        "command": " ".join(spec.path),
                        "option": option,
                        "credential": spec.credential,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "fields": fields,
                        "args": args,
                        "cwd": str(cwd) if cwd else None,
                        "db unchanged": db_unchanged,
                        "files unchanged": files_unchanged,
                        "trees unchanged": trees_unchanged,
                        "export absent": export_absent,
                        "extra worktree absent": extra_worktree_absent,
                    }
                )

    assert failures == [], json.dumps(failures, indent=2)


def test_value_options_reject_option_tokens_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    global_home = tmp_path / "global-home"
    global_cases = [
        (["--home", "--output", "text", "config", "show"], "--home requires a value"),
        (["--home", "", "config", "show"], "--home requires a non-empty value"),
        (["--home", str(global_home), "--output", "--key", "not-used", "config", "show"], "--output requires a value"),
        (["--home", str(global_home), "--output", "", "config", "show"], "--output requires a non-empty value"),
        (["--home", str(global_home), "--key", "--output", "text", "config", "show"], "--key requires a value"),
        (["--home", str(global_home), "--key", "", "config", "show"], "--key requires a non-empty value"),
    ]

    for args, reason in global_cases:
        code = cli.run(args)
        captured = capsys.readouterr()
        assert {
            "code": code,
            "stdout": captured.out,
            "fields": _output_field_map(captured.err),
            "home exists": global_home.exists(),
        } == {
            "code": 2,
            "stdout": "",
            "fields": {
                "object": "error",
                "message": "Command failed.",
                "error code": "CONFIG_INVALID",
                "exit code": "2",
                "reason": reason,
                "next": "none",
            },
            "home exists": False,
        }

    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    admin_args = ["--home", str(home), "--key", admin_key]
    root_args = ["--home", str(home), "--key", root_key]
    exp_path = tmp_path / "missing-value-exp"
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Missing Value Matrix",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]

    would_be_output = tmp_path / "--overwrite"
    would_be_worktree = tmp_path / "--goal"
    cases = [
        (
            "project config export",
            [*admin_args, "project", "config", "export", "--project", project_id, "--out", "--overwrite"],
            None,
            "--out requires a value",
        ),
        (
            "project config export empty out",
            [
                *admin_args,
                "project",
                "config",
                "export",
                "--project",
                project_id,
                "--out",
                "",
            ],
            None,
            "--out requires a non-empty value",
        ),
        (
            "source import",
            [
                *admin_args,
                "source",
                "import",
                "--project",
                project_id,
                "--source-path",
                "--name",
                "Missing Value Source",
            ],
            None,
            "--source-path requires a value",
        ),
        (
            "source import empty path",
            [
                *admin_args,
                "source",
                "import",
                "--project",
                project_id,
                "--source-path",
                "",
                "--name",
                "Empty Value Source",
            ],
            None,
            "--source-path requires a non-empty value",
        ),
        (
            "exp create path",
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Missing Value Child",
                "--path",
                "--goal",
                "missing value child",
            ],
            None,
            "--path requires a value",
        ),
        (
            "exp create empty path",
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Empty Value Child",
                "--path",
                "",
            ],
            None,
            "--path requires a non-empty value",
        ),
        (
            "exp create tag",
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Missing Tag Value",
                "--tag",
                "--path",
                str(tmp_path / "missing-tag-worktree"),
            ],
            None,
            "--tag requires a value",
        ),
        (
            "exp create empty tag",
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Empty Tag Value",
                "--tag",
                "",
                "--path",
                str(tmp_path / "empty-tag-worktree"),
            ],
            None,
            "--tag requires a non-empty value",
        ),
        (
            "exp token selector",
            [*admin_args, "exp", "token", "list", exp_id, "--project", project_id, "--mode", "--all"],
            None,
            "--mode requires a value",
        ),
        (
            "exp token empty selector",
            [
                *admin_args,
                "exp",
                "token",
                "list",
                exp_id,
                "--project",
                project_id,
                "--mode",
                "",
            ],
            None,
            "--mode requires a non-empty value",
        ),
        (
            "logs export",
            [
                *admin_args,
                "logs",
                "export",
                "log-missing-" + "V" * 22,
                "--project",
                project_id,
                "--out",
                "--overwrite",
            ],
            None,
            "--out requires a value",
        ),
        (
            "logs export empty out",
            [
                *admin_args,
                "logs",
                "export",
                "log-missing-" + "V" * 22,
                "--project",
                project_id,
                "--out",
                "",
            ],
            None,
            "--out requires a non-empty value",
        ),
        (
            "annotate add",
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                "--body",
                "missing target",
            ],
            None,
            "--target requires a value",
        ),
        (
            "annotate add empty target",
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                "",
                "--body-file",
                str(tmp_path / "missing-empty-target-body.txt"),
            ],
            None,
            "--target requires a non-empty value",
        ),
        (
            "submit summary file",
            [
                "--home",
                str(home),
                "submit",
                "--message",
                "missing value submit",
                "--summary-file",
                "--feedback",
                "feedback",
                "--ref",
                "none",
            ],
            exp_path,
            "--summary-file requires a value",
        ),
        (
            "submit empty summary file",
            [
                "--home",
                str(home),
                "submit",
                "--message",
                "empty value submit",
                "--summary-file",
                "",
                "--feedback",
                "feedback",
                "--ref",
                "none",
            ],
            exp_path,
            "--summary-file requires a non-empty value",
        ),
        (
            "catalog add",
            [
                *root_args,
                "catalog",
                "skydiscover",
                "add",
                "--origin-url",
                "--ref",
                "main",
            ],
            None,
            "--origin-url requires a value",
        ),
        (
            "catalog add empty origin",
            [
                *root_args,
                "catalog",
                "skydiscover",
                "add",
                "--origin-url",
                "",
                "--ref",
                "main",
            ],
            None,
            "--origin-url requires a non-empty value",
        ),
    ]

    project_marker_path = home / "project-workspaces" / project_id / ".alab" / "context.json"
    experiment_marker_path = exp_path / ".alab" / "context.json"
    token_path = exp_path / ".alab" / "token"
    failures = []
    for name, args, cwd, reason in cases:
        before_snapshot = _database_snapshot(home)
        config_before = (home / "config.toml").read_text(encoding="utf-8")
        project_marker_before = project_marker_path.read_text(encoding="utf-8")
        experiment_marker_before = experiment_marker_path.read_text(encoding="utf-8")
        token_before = token_path.read_text(encoding="utf-8")

        with monkeypatch.context() as context:
            context.chdir(tmp_path)
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()

        checks = {
            "code": code,
            "stdout": captured.out,
            "labels": _output_field_labels(captured.err),
            "fields": _output_field_map(captured.err) if captured.err else {},
            "db unchanged": _database_snapshot(home) == before_snapshot,
            "config unchanged": (home / "config.toml").read_text(encoding="utf-8") == config_before,
            "project marker unchanged": project_marker_path.read_text(encoding="utf-8") == project_marker_before,
            "experiment marker unchanged": experiment_marker_path.read_text(encoding="utf-8") == experiment_marker_before,
            "token unchanged": token_path.read_text(encoding="utf-8") == token_before,
            "output absent": not would_be_output.exists(),
            "worktree absent": not would_be_worktree.exists(),
        }
        expected = {
            "code": 2,
            "stdout": "",
            "labels": _error_field_labels(),
            "fields": {
                "object": "error",
                "message": "Command failed.",
                "error code": "CONFIG_INVALID",
                "exit code": "2",
                "reason": reason,
                "next": "none",
            },
            "db unchanged": True,
            "config unchanged": True,
            "project marker unchanged": True,
            "experiment marker unchanged": True,
            "token unchanged": True,
            "output absent": True,
            "worktree absent": True,
        }
        if checks != expected:
            failures.append({"case": name, "args": args, "cwd": str(cwd) if cwd else None, **checks})

    assert failures == []


def test_registered_command_value_options_reject_missing_values_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "value-option-exp"
    extra_worktree_path = tmp_path / "value-option-created"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Value Option Context",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    project_config_path = tmp_path / "value-option-config.toml"
    source_path = tmp_path / "value-option-source"
    secret_file_path = tmp_path / "value-option-secret.txt"
    catalog_upstream = tmp_path / "value-option-catalog"
    export_path = tmp_path / "value-option-export.toml"
    source_path.mkdir()
    (source_path / "main.py").write_text("print('value option')\n", encoding="utf-8")
    project_config_path.write_text(
        """
schema_version = 1

[project]
name = "Value Option Import"
task = "Verify missing value options fail before writes"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = ["python", "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    secret_file_path.write_text("value-option-secret\n", encoding="utf-8")
    _init_catalog_upstream(catalog_upstream)

    project_marker_path = home / "project-workspaces" / project_id / ".alab" / "context.json"
    watched_files = [
        home / "config.toml",
        project_marker_path,
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
        project_config_path,
        secret_file_path,
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
        source_path,
        catalog_upstream,
    ]
    command_value_options = {
        spec.path: _command_local_value_options(spec)
        for spec in registry.COMMANDS
        if _command_local_value_options(spec)
    }
    assert services.EMPTY_COMMAND_VALUE_ALLOWED <= services.OPTIONS_WITH_VALUES
    assert "--root" not in command_value_options[("key", "list")]
    assert "--root" in command_value_options[("artifacts", "list")]
    failures = []

    def check_rejected(
        spec: registry.CommandSpec,
        option: str,
        args: list[str],
        cwd: Path | None,
        reason: str,
        case: str,
    ) -> None:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        export_absent = not export_path.exists()
        extra_worktree_absent = not extra_worktree_path.exists()
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "CONFIG_INVALID"
            or fields.get("exit code") != "2"
            or fields.get("reason") != reason
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
            or not export_absent
            or not extra_worktree_absent
        ):
            failures.append(
                {
                    "case": case,
                    "command": " ".join(spec.path),
                    "option": option,
                    "credential": spec.credential,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "args": args,
                    "cwd": str(cwd) if cwd else None,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                    "export absent": export_absent,
                    "extra worktree absent": extra_worktree_absent,
                }
            )

    for spec in registry.COMMANDS:
        for option in command_value_options.get(spec.path, []):
            args, cwd = _value_option_missing_value_invocation(
                spec,
                option,
                home=home,
                root_key=root_key,
                admin_key=admin_key,
                project_id=project_id,
                exp_path=exp_path,
                project_marker_path=project_marker_path,
                project_config_path=project_config_path,
                catalog_upstream=catalog_upstream,
                export_path=export_path,
                extra_worktree_path=extra_worktree_path,
                source_path=source_path,
                secret_file_path=secret_file_path,
            )
            check_rejected(spec, option, args, cwd, f"{option} requires a value", "missing")
            if option not in services.EMPTY_COMMAND_VALUE_ALLOWED:
                args, cwd = _value_option_empty_value_invocation(
                    spec,
                    option,
                    home=home,
                    root_key=root_key,
                    admin_key=admin_key,
                    project_id=project_id,
                    exp_path=exp_path,
                    project_marker_path=project_marker_path,
                    project_config_path=project_config_path,
                    catalog_upstream=catalog_upstream,
                    export_path=export_path,
                    extra_worktree_path=extra_worktree_path,
                    source_path=source_path,
                    secret_file_path=secret_file_path,
                )
                check_rejected(spec, option, args, cwd, f"{option} requires a non-empty value", "empty")

    assert failures == [], json.dumps(failures, indent=2)


def test_registered_command_typed_value_options_reject_invalid_values_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "typed-value-option-exp"
    extra_worktree_path = tmp_path / "typed-value-option-created"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Typed Value Option Context",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    project_config_path = tmp_path / "typed-value-option-config.toml"
    source_path = tmp_path / "typed-value-option-source"
    secret_file_path = tmp_path / "typed-value-option-secret.txt"
    catalog_upstream = tmp_path / "typed-value-option-catalog"
    export_path = tmp_path / "typed-value-option-export.toml"
    source_path.mkdir()
    (source_path / "main.py").write_text("print('typed value option')\n", encoding="utf-8")
    project_config_path.write_text(
        """
schema_version = 1

[project]
name = "Typed Value Option Import"
task = "Verify typed value options fail before writes"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = ["python", "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    secret_file_path.write_text("typed-value-option-secret\n", encoding="utf-8")
    _init_catalog_upstream(catalog_upstream)

    project_marker_path = home / "project-workspaces" / project_id / ".alab" / "context.json"
    watched_files = [
        home / "config.toml",
        project_marker_path,
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
        project_config_path,
        secret_file_path,
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
        source_path,
        catalog_upstream,
    ]
    typed_value_options = {
        spec.path: _typed_value_invalid_options(spec)
        for spec in registry.COMMANDS
        if _typed_value_invalid_options(spec)
    }
    assert typed_value_options[("project", "init")] == [
        ("--max-file-bytes", "-1", "--max-file-bytes must be non-negative"),
        ("--max-file-bytes", "not-an-integer", "--max-file-bytes must be an integer"),
        ("--max-files", "-1", "--max-files must be non-negative"),
        ("--max-files", "not-an-integer", "--max-files must be an integer"),
        ("--max-total-bytes", "-1", "--max-total-bytes must be non-negative"),
        ("--max-total-bytes", "not-an-integer", "--max-total-bytes must be an integer"),
    ]
    assert ("--max-files", "-1", "--max-files must be non-negative") in typed_value_options[("source", "import")]
    assert ("--max-file-bytes", "-1", "--max-file-bytes must be non-negative") in typed_value_options[
        ("exp", "create")
    ]
    assert ("--sort", "unsupported:desc", "--sort field is not supported for experiments") in typed_value_options[
        ("exp", "list")
    ]
    assert ("--status", "not-a-status", "--status must be one of archived, closed, open") in typed_value_options[
        ("exp", "list")
    ]
    assert (
        "--status",
        "not-a-choice",
        "--status must be one of error, failed, interrupted, passed, running, timeout",
    ) in typed_value_options[("observe", "runs", "list")]
    assert ("--created-after", "2026-01-01 00:00:00Z", "invalid RFC 3339 timestamp") in typed_value_options[
        ("audit", "list")
    ]
    assert typed_value_options[("backup", "prune")] == [
        ("--keep", "-1", "--keep must be zero or greater"),
        ("--keep", "not-an-integer", "--keep must be an integer"),
        ("--older-than", "-1", "--older-than must be zero or greater"),
        ("--older-than", "not-an-integer", "--older-than must be an integer number of days"),
    ]
    assert ("--limit", "0", "--limit must be between 1 and 500") in typed_value_options[("exp", "list")]
    assert ("--limit", "501", "--limit must be between 1 and 500") in typed_value_options[("exp", "list")]
    assert ("--offset", "-1", "--offset must be zero or greater") in typed_value_options[("exp", "list")]
    assert ("--limit", "1001", "invalid audit pagination") in typed_value_options[("audit", "list")]
    assert ("--offset", "-1", "invalid audit pagination") in typed_value_options[("audit", "list")]
    assert ("--config-version", "0", "--config-version must be a positive integer") in typed_value_options[
        ("exp", "list")
    ]
    assert ("--config-version", "-1", "--config-version must be a positive integer") in typed_value_options[
        ("observe", "experiments", "best")
    ]
    assert ("--config-version", "0", "--config-version must be a positive integer") in typed_value_options[
        ("observe", "runs", "list")
    ]
    assert ("--version", "0", "invalid config version selector") in typed_value_options[("project", "config", "show")]
    assert ("--version", "-1", "invalid config version selector") in typed_value_options[
        ("project", "config", "export")
    ]
    assert ("--size-min", "-1", "--size-min must be zero or greater") in typed_value_options[
        ("observe", "artifacts", "list")
    ]
    assert ("--size-max", "-1", "--size-max must be zero or greater") in typed_value_options[
        ("observe", "artifacts", "list")
    ]
    assert ("--role", "not-a-choice", "--role must be one of admin") in typed_value_options[
        ("key", "create")
    ]
    assert ("--commit", "short-sha", "--commit requires a full commit SHA") in typed_value_options[
        ("catalog", "skydiscover", "add")
    ]
    assert ("--commit", "short-sha", "--commit requires a full commit SHA") in typed_value_options[
        ("catalog", "skydiscover", "update")
    ]
    assert ("--source-id", "src-short", "object ids must be complete") in typed_value_options[("exp", "list")]
    assert ("--token-id", "cred-short", "object ids must be complete") in typed_value_options[("exp", "token", "list")]
    assert ("--mode", "not-a-choice", "--mode must be one of inspection, worktree") in typed_value_options[
        ("exp", "token", "list")
    ]
    assert ("--mode", "not-a-choice", "--mode must be one of inspection, worktree") in typed_value_options[
        ("exp", "token", "regenerate")
    ]
    assert (
        "--visibility-scope",
        "not-a-choice",
        "--visibility-scope must be one of explicit, none, same_project",
    ) in typed_value_options[("exp", "create")]
    assert (
        "--from-commit",
        "HEAD",
        "commit selector must be latest, final, best, or a commit SHA",
    ) in typed_value_options[("exp", "create")]
    assert (
        "--commit",
        "HEAD",
        "commit selector must be latest, final, best, or a commit SHA",
    ) in typed_value_options[("exp", "checkout")]
    assert ("--exp", "exp-short", "object ids must be complete") in typed_value_options[("observe", "runs", "list")]
    assert ("--commit", "HEAD", "--commit must be a commit SHA") in typed_value_options[
        ("observe", "runs", "list")
    ]
    assert (
        "--runner-type",
        "not-a-choice",
        "--runner-type must be one of docker, harbor, local, skydiscover_docker, skydiscover_python",
    ) in typed_value_options[("observe", "runs", "list")]
    assert ("--run", "run-short", "object ids must be complete") in typed_value_options[("observe", "artifacts", "list")]
    assert (
        "--root",
        "not-a-choice",
        "--root must be one of run, workspace",
    ) in typed_value_options[("observe", "artifacts", "list")]
    assert ("--content-hash", "not-a-hash", "--content-hash must be sha256:<64-hex>") in typed_value_options[
        ("observe", "artifacts", "list")
    ]
    assert ("--validation", "val-short", "object ids must be complete") in typed_value_options[
        ("observe", "logs", "list")
    ]
    assert (
        "--stream",
        "not-a-choice",
        "--stream must be one of hidden_stderr, hidden_stdout, stderr, stdout",
    ) in typed_value_options[("observe", "logs", "list")]
    assert ("--target-id", "exp-short", "object ids must be complete") in typed_value_options[
        ("observe", "annotations", "list")
    ]
    assert ("--target", "exp-short", "object ids must be complete") in typed_value_options[
        ("observe", "annotations", "list")
    ]
    assert ("--created-by", "exp-short", "object ids must be complete") in typed_value_options[
        ("observe", "annotations", "list")
    ]
    assert (
        "--target-type",
        "not-a-choice",
        "--target-type must be one of artifact, experiment, lines, path, run",
    ) in typed_value_options[("observe", "annotations", "list")]
    assert ("--actor", "cred-short", "object ids must be complete") in typed_value_options[("audit", "list")]
    assert ("--object-id", "src-short", "object ids must be complete") in typed_value_options[("audit", "list")]
    assert (
        "--action",
        "not-a-choice",
        "--action must be one of add, archive, clear, gc, prune, regenerate, remove, repair, restore, revoke, unarchive, update",
    ) in typed_value_options[("audit", "list")]
    assert (
        "--object-type",
        "not-a-choice",
        "--object-type must be one of annotation, artifact, backup, cache, catalog, credential, experiment, inspection_checkout, lock, log, project, run, secret_value, source, validation, worktree",
    ) in typed_value_options[("audit", "list")]
    assert (
        "--older-than",
        "not-an-integer",
        "--older-than must be an integer number of days",
    ) in typed_value_options[("cache", "prune")]
    failures = []

    for spec in registry.COMMANDS:
        for option, value, expected_reason in typed_value_options.get(spec.path, []):
            args, cwd = _typed_value_invalid_invocation(
                spec,
                option,
                value,
                home=home,
                root_key=root_key,
                admin_key=admin_key,
                project_id=project_id,
                exp_path=exp_path,
                project_marker_path=project_marker_path,
                project_config_path=project_config_path,
                catalog_upstream=catalog_upstream,
                export_path=export_path,
                extra_worktree_path=extra_worktree_path,
                source_path=source_path,
                secret_file_path=secret_file_path,
            )
            before_snapshot = _database_snapshot(home)
            watched_file_contents = _text_file_snapshot(watched_files)
            watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
            with monkeypatch.context() as context:
                if cwd is not None:
                    context.chdir(cwd)
                code = cli.run(args)
            captured = capsys.readouterr()
            fields = _output_field_map(captured.err) if captured.err else {}
            db_unchanged = _database_snapshot(home) == before_snapshot
            files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
            trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
            export_absent = not export_path.exists()
            extra_worktree_absent = not extra_worktree_path.exists()
            if (
                code != 2
                or captured.out
                or _output_field_labels(captured.err) != _error_field_labels()
                or fields.get("error code") != "CONFIG_INVALID"
                or fields.get("exit code") != "2"
                or fields.get("reason") != expected_reason
                or fields.get("next") != "none"
                or not db_unchanged
                or not files_unchanged
                or not trees_unchanged
                or not export_absent
                or not extra_worktree_absent
            ):
                failures.append(
                    {
                        "command": " ".join(spec.path),
                        "option": option,
                        "value": value,
                        "credential": spec.credential,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "fields": fields,
                        "expected reason": expected_reason,
                        "args": args,
                        "cwd": str(cwd) if cwd else None,
                        "db unchanged": db_unchanged,
                        "files unchanged": files_unchanged,
                        "trees unchanged": trees_unchanged,
                        "export absent": export_absent,
                        "extra worktree absent": extra_worktree_absent,
                    }
                )

    assert failures == [], json.dumps(failures, indent=2)


def test_project_config_mutation_dry_run_skip_baseline_conflicts_before_payload_reads(
    tmp_path: Path,
    capsys,
) -> None:
    home, _root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    admin_args = ["--home", str(home), "--key", admin_key]
    missing_config_path = tmp_path / "missing-conflict-config.toml"
    missing_secret_path = tmp_path / "missing-conflict-secret.txt"
    cases = [
        (
            "project config import",
            [
                *admin_args,
                "project",
                "config",
                "import",
                "--project",
                project_id,
                "--config",
                str(missing_config_path),
                "--dry-run",
                "--skip-baseline-test",
            ],
        ),
        (
            "project config set",
            [
                *admin_args,
                "project",
                "config",
                "set",
                "runner.timeout_seconds",
                "31",
                "--project",
                project_id,
                "--dry-run",
                "--skip-baseline-test",
            ],
        ),
        (
            "project env set",
            [
                *admin_args,
                "project",
                "env",
                "set",
                "CONFLICT_ENV",
                "value",
                "--project",
                project_id,
                "--dry-run",
                "--skip-baseline-test",
            ],
        ),
        (
            "project env unset",
            [
                *admin_args,
                "project",
                "env",
                "unset",
                "CONFLICT_ENV",
                "--project",
                project_id,
                "--dry-run",
                "--skip-baseline-test",
            ],
        ),
        (
            "project secret set",
            [
                *admin_args,
                "project",
                "secret",
                "set",
                "CONFLICT_SECRET",
                "--project",
                project_id,
                "--value-file",
                str(missing_secret_path),
                "--dry-run",
                "--skip-baseline-test",
            ],
        ),
        (
            "project secret unset",
            [
                *admin_args,
                "project",
                "secret",
                "unset",
                "CONFLICT_SECRET",
                "--project",
                project_id,
                "--dry-run",
                "--skip-baseline-test",
            ],
        ),
    ]
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
    ]
    failures = []

    for name, args in cases:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        missing_files_absent = not missing_config_path.exists() and not missing_secret_path.exists()
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "CONFIG_INVALID"
            or fields.get("exit code") != "2"
            or fields.get("reason") != "--dry-run conflicts with --skip-baseline-test"
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
            or not missing_files_absent
        ):
            failures.append(
                {
                    "case": name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "args": args,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                    "missing files absent": missing_files_absent,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_non_remove_documented_conflicts_fail_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    admin_args = ["--home", str(home), "--key", admin_key]
    root_args = ["--home", str(home), "--key", root_key]
    exp_path = tmp_path / "documented-conflict-exp"
    child_path = tmp_path / "documented-conflict-child"
    missing_summary_path = tmp_path / "missing-conflict-summary.txt"
    missing_feedback_path = tmp_path / "missing-conflict-feedback.txt"
    missing_annotation_body_path = tmp_path / "missing-conflict-annotation.txt"

    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Documented Conflict Context",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    exp_id = _output_field_map(capsys.readouterr().out)["exp id"]
    with sqlite3.connect(home / "alab.db") as conn:
        source_ref = conn.execute(
            "SELECT source_ref FROM sources WHERE project_id = ? ORDER BY source_id LIMIT 1",
            (project_id,),
        ).fetchone()[0]

    cases = [
        (
            "key list root/project",
            [*root_args, "key", "list", "--root", "--project", project_id],
            None,
            "CONFIG_INVALID",
            "--root conflicts with --project",
        ),
        (
            "catalog add ref/commit",
            [
                *root_args,
                "catalog",
                "skydiscover",
                "add",
                "--ref",
                "main",
                "--commit",
                "0" * 40,
            ],
            None,
            "CONFIG_INVALID",
            "--ref conflicts with --commit",
        ),
        (
            "backup prune keep/older-than",
            [*root_args, "backup", "prune", "--keep", "1", "--older-than", "1"],
            None,
            "CONFIG_INVALID",
            "backup prune requires exactly one of --keep or --older-than",
        ),
        (
            "cache prune all/trash",
            [*root_args, "cache", "prune", "--all", "--trash"],
            None,
            "CONFIG_INVALID",
            "--all conflicts with specific cache selectors",
        ),
        (
            "cache prune trash/trash-all",
            [*root_args, "cache", "prune", "--trash", "--trash-all"],
            None,
            "CONFIG_INVALID",
            "--trash conflicts with --trash-all",
        ),
        (
            "source import empty/subdir",
            [
                *admin_args,
                "source",
                "import",
                "--project",
                project_id,
                "--source-empty",
                "--source-subdir",
                "child",
            ],
            None,
            "SOURCE_INVALID",
            "--source-subdir conflicts with --source-empty",
        ),
        (
            "source show positional/source-ref",
            [*admin_args, "source", "show", source_ref, "--project", project_id, "--source-ref", source_ref],
            None,
            "CONFIG_INVALID",
            "source show accepts only one source selector",
        ),
        (
            "exp create from-exp/source-empty",
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Documented Conflict Child",
                "--from-exp",
                exp_id,
                "--source-empty",
                "--path",
                str(child_path),
            ],
            None,
            "SOURCE_INVALID",
            "--from-exp conflicts with source selectors",
        ),
        (
            "exp create empty/subdir",
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Documented Empty Subdir Conflict",
                "--source-empty",
                "--source-subdir",
                "child",
                "--path",
                str(child_path),
            ],
            None,
            "SOURCE_INVALID",
            "--source-subdir conflicts with --source-empty",
        ),
        (
            "exp token all/mode",
            [*admin_args, "exp", "token", "list", exp_id, "--project", project_id, "--all", "--mode", "worktree"],
            None,
            "CONFIG_INVALID",
            "--all conflicts with --token-id or --mode",
        ),
        (
            "submit ref none/ref",
            [
                "--home",
                str(home),
                "submit",
                "--message",
                "documented conflict submit",
                "--summary-file",
                str(missing_summary_path),
                "--feedback-file",
                str(missing_feedback_path),
                "--ref",
                "none",
                "--ref",
                f"exp:{exp_id}",
            ],
            exp_path,
            "CONFIG_INVALID",
            "--ref none conflicts with experiment refs",
        ),
        (
            "annotate add body/body-file",
            [
                *admin_args,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                f"exp:{exp_id}",
                "--body",
                "inline body",
                "--body-file",
                str(missing_annotation_body_path),
            ],
            None,
            "CONFIG_INVALID",
            "annotation requires exactly one of --body or --body-file",
        ),
        (
            "annotations list target/target-id",
            [
                *admin_args,
                "annotations",
                "list",
                "--project",
                project_id,
                "--target",
                f"exp:{exp_id}",
                "--target-id",
                exp_id,
            ],
            None,
            "CONFIG_INVALID",
            "annotations list accepts only one of --target-id or --target",
        ),
    ]
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
    ]
    failures = []

    for name, args, cwd, error_code, reason in cases:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        unexpected_paths_absent = (
            not child_path.exists()
            and not missing_summary_path.exists()
            and not missing_feedback_path.exists()
            and not missing_annotation_body_path.exists()
        )
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != error_code
            or fields.get("exit code") != "2"
            or fields.get("reason") != reason
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
            or not unexpected_paths_absent
        ):
            failures.append(
                {
                    "case": name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "args": args,
                    "cwd": str(cwd) if cwd else None,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                    "unexpected paths absent": unexpected_paths_absent,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_global_public_commands_reject_unsupported_options_before_home_creation(tmp_path: Path, capsys) -> None:
    failures = []
    variants = [
        ["help", "--definitely-unsupported"],
        ["--help", "--definitely-unsupported"],
        *[
            [*spec.path, "--definitely-unsupported"]
            for spec in registry.COMMANDS
            if spec.path in cli.GLOBAL_PUBLIC and spec.handler is not services.cmd_help
        ],
    ]

    for index, args in enumerate(variants):
        home = tmp_path / f"global-public-home-{index}"
        code = cli.run(["--home", str(home), *args])
        captured = capsys.readouterr()
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or "error code: CONFIG_INVALID" not in captured.err
            or home.exists()
        ):
            failures.append(
                {
                    "args": args,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "home_exists": home.exists(),
                }
            )

    assert failures == []


def test_registered_commands_reject_unsupported_options_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "unknown-option-exp"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Unknown Option Matrix",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
    ]
    watched_trees = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
    ]

    failures = []
    for spec in registry.COMMANDS:
        if spec.handler is services.cmd_help:
            continue
        before_snapshot = _database_snapshot(home)
        watched_file_contents = {path: path.read_text(encoding="utf-8") for path in watched_files}
        watched_tree_contents = {root: _relative_tree(root) for root in watched_trees}
        args, cwd = _unknown_option_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
        )
        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or "error code: CONFIG_INVALID" not in captured.err
            or "unsupported option --definitely-unsupported" not in captured.err
            or _database_snapshot(home) != before_snapshot
            or any(path.read_text(encoding="utf-8") != content for path, content in watched_file_contents.items())
            or any(_relative_tree(root) != tree for root, tree in watched_tree_contents.items())
        ):
            failures.append(
                {
                    "command": " ".join(spec.path),
                    "credential": spec.credential,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "args": args,
                    "cwd": str(cwd) if cwd else None,
                    "db unchanged": _database_snapshot(home) == before_snapshot,
                    "files unchanged": all(path.read_text(encoding="utf-8") == content for path, content in watched_file_contents.items()),
                    "trees unchanged": all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items()),
                }
            )

    assert failures == []


def test_registered_commands_accept_trailing_globals_before_handler_errors_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "trailing-global-exp"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Trailing Global Matrix",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
    ]
    watched_trees = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
    ]

    failures = []
    for spec in registry.COMMANDS:
        if spec.handler is services.cmd_help:
            continue
        before_snapshot = _database_snapshot(home)
        watched_file_contents = {path: path.read_text(encoding="utf-8") for path in watched_files}
        watched_tree_contents = {root: _relative_tree(root) for root in watched_trees}
        args, cwd = _trailing_global_unknown_option_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
        )
        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "CONFIG_INVALID"
            or fields.get("exit code") != "2"
            or fields.get("reason") != "unsupported option --definitely-unsupported"
            or fields.get("next") != "none"
            or _database_snapshot(home) != before_snapshot
            or any(path.read_text(encoding="utf-8") != content for path, content in watched_file_contents.items())
            or any(_relative_tree(root) != tree for root, tree in watched_tree_contents.items())
        ):
            failures.append(
                {
                    "command": " ".join(spec.path),
                    "credential": spec.credential,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "args": args,
                    "cwd": str(cwd) if cwd else None,
                    "db unchanged": _database_snapshot(home) == before_snapshot,
                    "files unchanged": all(path.read_text(encoding="utf-8") == content for path, content in watched_file_contents.items()),
                    "trees unchanged": all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items()),
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_registered_commands_stop_global_prescan_at_standalone_separator_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "sentinel-global-exp"
    extra_worktree_path = tmp_path / "sentinel-global-created"
    ignored_home = tmp_path / "sentinel-ignored-home"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Sentinel Global Context",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    project_config_path = tmp_path / "sentinel-global-config.toml"
    source_path = tmp_path / "sentinel-global-source"
    secret_file_path = tmp_path / "sentinel-global-secret.txt"
    catalog_upstream = tmp_path / "sentinel-global-catalog"
    export_path = tmp_path / "sentinel-global-export.toml"
    source_path.mkdir()
    (source_path / "main.py").write_text("print('sentinel global')\n", encoding="utf-8")
    project_config_path.write_text(
        """
schema_version = 1

[project]
name = "Sentinel Global Import"
task = "Verify standalone separator stops global pre-scan"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = ["python", "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    secret_file_path.write_text("sentinel-global-secret\n", encoding="utf-8")
    _init_catalog_upstream(catalog_upstream)

    project_marker_path = home / "project-workspaces" / project_id / ".alab" / "context.json"
    watched_files = [
        home / "config.toml",
        project_marker_path,
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
        project_config_path,
        secret_file_path,
    ]
    watched_trees = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
        source_path,
        catalog_upstream,
    ]
    expected_reasons = {
        **{
            spec.path: message
            for spec in registry.COMMANDS
            if (message := _zero_positional_message(spec.handler)) is not None
        },
        **{
            spec.path: message
            for spec in registry.COMMANDS
            if (message := _single_selector_message_for_spec(spec)) is not None
        },
        **{
            spec.path: message
            for spec in registry.COMMANDS
            if (message := _fixed_positional_message(spec.handler)) is not None
        },
    }
    failures = []

    for spec in registry.COMMANDS:
        if spec.handler is services.cmd_help:
            continue
        expected_reason = expected_reasons.get(spec.path)
        if expected_reason is None:
            failures.append({"command": " ".join(spec.path), "missing expected reason": True})
            continue
        before_snapshot = _database_snapshot(home)
        watched_file_contents = {path: path.read_text(encoding="utf-8") for path in watched_files}
        watched_tree_contents = {root: _relative_tree(root) for root in watched_trees}
        args, cwd = _sentinel_extra_positional_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
            project_marker_path=project_marker_path,
            project_config_path=project_config_path,
            catalog_upstream=catalog_upstream,
            export_path=export_path,
            extra_worktree_path=extra_worktree_path,
            source_path=source_path,
            secret_file_path=secret_file_path,
            ignored_home=ignored_home,
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO("not-a-single-line-key\nwith-extra-line\n"))
        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "CONFIG_INVALID"
            or fields.get("exit code") != "2"
            or fields.get("reason") != expected_reason
            or fields.get("next") != "none"
            or _database_snapshot(home) != before_snapshot
            or any(path.read_text(encoding="utf-8") != content for path, content in watched_file_contents.items())
            or any(_relative_tree(root) != tree for root, tree in watched_tree_contents.items())
            or export_path.exists()
            or extra_worktree_path.exists()
            or ignored_home.exists()
        ):
            failures.append(
                {
                    "command": " ".join(spec.path),
                    "credential": spec.credential,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "expected reason": expected_reason,
                    "args": args,
                    "cwd": str(cwd) if cwd else None,
                    "db unchanged": _database_snapshot(home) == before_snapshot,
                    "files unchanged": all(path.read_text(encoding="utf-8") == content for path, content in watched_file_contents.items()),
                    "trees unchanged": all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items()),
                    "ignored home exists": ignored_home.exists(),
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_zero_positional_commands_reject_extra_positional_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "extra-positional-exp"
    extra_worktree_path = tmp_path / "extra-positional-created"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Extra Positional Context",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    project_config_path = tmp_path / "extra-positional-config.toml"
    project_config_path.write_text(
        """
schema_version = 1

[project]
name = "Extra Positional Import"
task = "Verify positional validation runs before import writes"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = ["python", "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    catalog_upstream = tmp_path / "extra-positional-catalog"
    _init_catalog_upstream(catalog_upstream)
    export_path = tmp_path / "extra-positional-export.toml"
    project_marker_path = home / "project-workspaces" / project_id / ".alab" / "context.json"
    watched_files = [
        home / "config.toml",
        project_marker_path,
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
    ]
    zero_positional = {
        spec.path: message
        for spec in registry.COMMANDS
        if (message := _zero_positional_message(spec.handler)) is not None
    }
    failures = []

    for spec in registry.COMMANDS:
        expected_reason = zero_positional.get(spec.path)
        if expected_reason is None:
            continue
        args, cwd = _extra_positional_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
            project_marker_path=project_marker_path,
            project_config_path=project_config_path,
            catalog_upstream=catalog_upstream,
            export_path=export_path,
            extra_worktree_path=extra_worktree_path,
        )
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
        export_absent = not export_path.exists()
        extra_worktree_absent = not extra_worktree_path.exists()
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "CONFIG_INVALID"
            or fields.get("exit code") != "2"
            or fields.get("reason") != expected_reason
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
            or not export_absent
            or not extra_worktree_absent
        ):
            failures.append(
                {
                    "command": " ".join(spec.path),
                    "credential": spec.credential,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "args": args,
                    "cwd": str(cwd) if cwd else None,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                    "export absent": export_absent,
                    "extra worktree absent": extra_worktree_absent,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_single_selector_commands_reject_extra_positional_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "single-selector-extra-positional-exp"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Single Selector Extra Positional Context",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
    ]
    single_selector = {
        spec.path: message
        for spec in registry.COMMANDS
        if (message := _single_selector_message_for_spec(spec)) is not None
    }
    failures = []

    for spec in registry.COMMANDS:
        expected_reason = single_selector.get(spec.path)
        if expected_reason is None:
            continue
        args, cwd = _single_selector_extra_positional_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
        )
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "CONFIG_INVALID"
            or fields.get("exit code") != "2"
            or fields.get("reason") != expected_reason
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
        ):
            failures.append(
                {
                    "command": " ".join(spec.path),
                    "credential": spec.credential,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "args": args,
                    "cwd": str(cwd) if cwd else None,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_required_single_selector_commands_reject_missing_selector_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "missing-single-selector-exp"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Missing Single Selector Context",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    export_path = tmp_path / "missing-single-selector-export.bin"
    extra_checkout_path = tmp_path / "missing-single-selector-checkout"
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
    ]
    required_single_selectors = {
        spec.path: expected
        for spec in registry.COMMANDS
        if (expected := _missing_single_selector_error_for_spec(spec)) is not None
    }
    assert ("config", "reset") not in required_single_selectors
    assert ("exp", "tag", "list") not in required_single_selectors
    failures = []

    for spec in registry.COMMANDS:
        expected = required_single_selectors.get(spec.path)
        if expected is None:
            continue
        expected_code, expected_reason = expected
        args, cwd = _single_selector_missing_positional_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
            export_path=export_path,
            extra_checkout_path=extra_checkout_path,
        )
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
        export_absent = not export_path.exists()
        checkout_absent = not extra_checkout_path.exists()
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != expected_code
            or fields.get("exit code") != "2"
            or fields.get("reason") != expected_reason
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
            or not export_absent
            or not checkout_absent
        ):
            failures.append(
                {
                    "command": " ".join(spec.path),
                    "credential": spec.credential,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "expected code": expected_code,
                    "expected reason": expected_reason,
                    "args": args,
                    "cwd": str(cwd) if cwd else None,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                    "export absent": export_absent,
                    "checkout absent": checkout_absent,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_fixed_positional_commands_reject_extra_positional_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "fixed-positional-exp"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Fixed Positional Context",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    project_config_path = tmp_path / "fixed-positional-config.toml"
    source_path = tmp_path / "fixed-positional-source"
    secret_file_path = tmp_path / "fixed-positional-secret.txt"
    source_path.mkdir()
    (source_path / "main.py").write_text("print('fixed positional')\n", encoding="utf-8")
    project_config_path.write_text(
        """
schema_version = 1

[project]
name = "Fixed Positional Init"
task = "Verify fixed positional validation runs before init writes"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = ["python", "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    secret_file_path.write_text("fixed-positional-secret\n", encoding="utf-8")
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
        secret_file_path,
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
        source_path,
    ]
    fixed_positional = {
        spec.path: message
        for spec in registry.COMMANDS
        if (message := _fixed_positional_message(spec.handler)) is not None
    }
    failures = []

    for spec in registry.COMMANDS:
        expected_reason = fixed_positional.get(spec.path)
        if expected_reason is None:
            continue
        args, cwd = _fixed_positional_extra_positional_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
            project_config_path=project_config_path,
            source_path=source_path,
            secret_file_path=secret_file_path,
        )
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "CONFIG_INVALID"
            or fields.get("exit code") != "2"
            or fields.get("reason") != expected_reason
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
        ):
            failures.append(
                {
                    "command": " ".join(spec.path),
                    "credential": spec.credential,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "args": args,
                    "cwd": str(cwd) if cwd else None,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_fixed_positional_commands_reject_missing_required_positional_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key = _init_capability_project(tmp_path, capsys)
    exp_path = tmp_path / "missing-fixed-positional-exp"
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Missing Fixed Positional Context",
                "--path",
                str(exp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    project_config_path = tmp_path / "missing-fixed-positional-config.toml"
    source_path = tmp_path / "missing-fixed-positional-source"
    secret_file_path = tmp_path / "missing-fixed-positional-secret.txt"
    source_path.mkdir()
    (source_path / "main.py").write_text("print('missing fixed positional')\n", encoding="utf-8")
    project_config_path.write_text(
        """
schema_version = 1

[project]
name = "Missing Fixed Positional Init"
task = "Verify missing fixed positional validation runs before init writes"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = ["python", "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    secret_file_path.write_text("missing-fixed-positional-secret\n", encoding="utf-8")
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        exp_path / ".alab" / "context.json",
        exp_path / ".alab" / "token",
        project_config_path,
        secret_file_path,
    ]
    watched_tree_roots = [
        home / "projects",
        home / "project-workspaces",
        home / "sources",
        home / "tmp",
        exp_path,
        source_path,
    ]
    fixed_positional = {
        spec.path: message
        for spec in registry.COMMANDS
        if (message := _fixed_positional_message(spec.handler)) is not None
    }
    failures = []

    for spec in registry.COMMANDS:
        expected_reason = fixed_positional.get(spec.path)
        if expected_reason is None:
            continue
        args, cwd = _fixed_positional_missing_positional_invocation(
            spec,
            home=home,
            root_key=root_key,
            admin_key=admin_key,
            project_id=project_id,
            exp_path=exp_path,
            project_config_path=project_config_path,
            source_path=source_path,
            secret_file_path=secret_file_path,
        )
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _relative_tree(root) for root in watched_tree_roots}
        with monkeypatch.context() as context:
            if cwd is not None:
                context.chdir(cwd)
            code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_relative_tree(root) == tree for root, tree in watched_tree_contents.items())
        if (
            code != 2
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "CONFIG_INVALID"
            or fields.get("exit code") != "2"
            or fields.get("reason") != expected_reason
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
        ):
            failures.append(
                {
                    "command": " ".join(spec.path),
                    "credential": spec.credential,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "args": args,
                    "cwd": str(cwd) if cwd else None,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_force_confirm_commands_reject_incomplete_confirmation_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="force-confirm-worktree",
    )
    admin_args = ["--home", str(home), "--key", admin_key]
    root_args = ["--home", str(home), "--key", root_key]

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "force confirm matrix"]) == 0
    run_fields = _output_field_map(capsys.readouterr().out)
    run_id = run_fields["run id"]
    exp_id = run_fields["exp id"]

    assert cli.run([*admin_args, "artifacts", "list", "--project", project_id, "--run", run_id]) == 0
    artifact_id = _output_field_map(capsys.readouterr().out)["artifact id"]
    assert cli.run([*admin_args, "logs", "list", "--project", project_id, "--run", run_id, "--stream", "stdout"]) == 0
    log_id = _output_field_map(capsys.readouterr().out)["log id"]

    assert cli.run([*admin_args, "annotate", "add", "--project", project_id, "--target", f"exp:{exp_id}", "--body", "force confirm note"]) == 0
    annotation_id = _output_field_map(capsys.readouterr().out)["annotation id"]

    checkout_path = tmp_path / "force-confirm-inspection"
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "checkout",
                exp_id,
                "--project",
                project_id,
                "--path",
                str(checkout_path),
                "--commit",
                "latest",
            ]
        )
        == 0
    )
    checkout_fields = _output_field_map(capsys.readouterr().out)
    checkout_token_id = checkout_fields["token id"]

    catalog_upstream = tmp_path / "force-confirm-catalog"
    _init_catalog_upstream(catalog_upstream)
    assert cli.run([*root_args, "catalog", "skydiscover", "add", "--origin-url", str(catalog_upstream), "--ref", "main"]) == 0
    capsys.readouterr()

    with sqlite3.connect(home / "alab.db") as conn:
        source_id = conn.execute(
            "SELECT source_id FROM sources WHERE project_id = ? ORDER BY source_id LIMIT 1",
            (project_id,),
        ).fetchone()[0]
        validation_id = conn.execute(
            "SELECT validation_id FROM project_validations WHERE project_id = ? ORDER BY validation_id LIMIT 1",
            (project_id,),
        ).fetchone()[0]

    cases = [
        (
            "catalog skydiscover remove",
            [*root_args, "catalog", "skydiscover", "remove"],
            "skydiscover",
            "catalog remove requires --force and --confirm skydiscover",
        ),
        (
            "project remove",
            [*root_args, "project", "remove", "--project", project_id, "--cascade"],
            project_id,
            "project remove requires --force and matching --confirm",
        ),
        (
            "project validation remove",
            [*admin_args, "project", "validation", "remove", validation_id, "--project", project_id, "--cascade"],
            validation_id,
            "validation remove requires --force and matching --confirm",
        ),
        (
            "source remove",
            [*admin_args, "source", "remove", source_id, "--project", project_id, "--cascade"],
            source_id,
            "source remove requires --force and matching --confirm",
        ),
        (
            "exp remove",
            [*admin_args, "exp", "remove", exp_id, "--project", project_id, "--cascade"],
            exp_id,
            "experiment remove requires --force and matching --confirm",
        ),
        (
            "exp worktree remove",
            [*admin_args, "exp", "worktree", "remove", exp_id, "--project", project_id],
            exp_id,
            "exp worktree remove requires --force and matching --confirm",
        ),
        (
            "exp checkout remove",
            [*admin_args, "exp", "checkout", "remove", "--project", project_id, "--token-id", checkout_token_id],
            checkout_token_id,
            "checkout remove requires --force and matching --confirm",
        ),
        (
            "runs remove",
            [*admin_args, "runs", "remove", run_id, "--project", project_id, "--cascade"],
            run_id,
            "run remove requires --force and matching --confirm",
        ),
        (
            "artifacts remove",
            [*admin_args, "artifacts", "remove", artifact_id, "--project", project_id],
            artifact_id,
            "artifact remove requires --force and matching --confirm",
        ),
        (
            "logs remove",
            [*admin_args, "logs", "remove", log_id, "--project", project_id],
            log_id,
            "log remove requires --force and matching --confirm",
        ),
        (
            "annotate remove",
            [*admin_args, "annotate", "remove", annotation_id, "--project", project_id],
            annotation_id,
            "annotation remove requires --force and matching --confirm",
        ),
    ]
    variants = [
        ("missing force", lambda expected: ["--confirm", expected]),
        ("missing confirm", lambda _expected: ["--force"]),
        ("wrong confirm", lambda _expected: ["--force", "--confirm", "wrong-confirm-target"]),
    ]
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        worktree_path / ".alab" / "context.json",
        worktree_path / ".alab" / "token",
        checkout_path / ".alab" / "context.json",
        checkout_path / ".alab" / "token",
    ]
    watched_dirs = [
        home / "projects" / project_id,
        home / "project-workspaces" / project_id,
        home / "sources" / "skydiscover",
        worktree_path,
        checkout_path,
    ]
    watched_tree_roots = [
        home / "projects" / project_id,
        home / "project-workspaces" / project_id,
        home / "sources",
        home / "tmp",
        worktree_path,
        checkout_path,
    ]

    failures = []
    for command_name, base_args, expected_confirm, expected_reason in cases:
        for variant_name, suffix_factory in variants:
            before_snapshot = _database_snapshot(home)
            watched_file_contents = _text_file_snapshot(watched_files)
            watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
            code = cli.run([*base_args, *suffix_factory(expected_confirm)])
            captured = capsys.readouterr()
            fields = _output_field_map(captured.err)
            db_unchanged = _database_snapshot(home) == before_snapshot
            files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
            trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
            dirs_present = all(path.exists() for path in watched_dirs)
            if (
                code != 2
                or captured.out
                or _output_field_labels(captured.err) != _error_field_labels()
                or fields.get("error code") != "CONFIG_INVALID"
                or fields.get("exit code") != "2"
                or fields.get("reason") != expected_reason
                or fields.get("next") != "none"
                or not db_unchanged
                or not files_unchanged
                or not trees_unchanged
                or not dirs_present
            ):
                failures.append(
                    {
                        "command": command_name,
                        "variant": variant_name,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "fields": fields,
                        "db unchanged": db_unchanged,
                        "files unchanged": files_unchanged,
                        "trees unchanged": trees_unchanged,
                        "dirs present": dirs_present,
                    }
                )

    assert failures == [], json.dumps(failures, indent=2)


def test_hard_remove_dry_runs_preserve_database_and_filesystem(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="dry-run-side-effect-worktree",
    )
    admin_args = ["--home", str(home), "--key", admin_key]
    root_args = ["--home", str(home), "--key", root_key]

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "dry-run side-effect matrix"]) == 0
    run_fields = _output_field_map(capsys.readouterr().out)
    run_id = run_fields["run id"]
    exp_id = run_fields["exp id"]

    assert cli.run([*admin_args, "artifacts", "list", "--project", project_id, "--run", run_id]) == 0
    artifact_id = _output_field_map(capsys.readouterr().out)["artifact id"]
    assert cli.run([*admin_args, "logs", "list", "--project", project_id, "--run", run_id, "--stream", "stdout"]) == 0
    log_id = _output_field_map(capsys.readouterr().out)["log id"]

    assert cli.run([*admin_args, "annotate", "add", "--project", project_id, "--target", f"exp:{exp_id}", "--body", "dry-run note"]) == 0
    annotation_id = _output_field_map(capsys.readouterr().out)["annotation id"]

    checkout_path = tmp_path / "dry-run-side-effect-inspection"
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "checkout",
                exp_id,
                "--project",
                project_id,
                "--path",
                str(checkout_path),
                "--commit",
                "latest",
            ]
        )
        == 0
    )
    checkout_token_id = _output_field_map(capsys.readouterr().out)["token id"]

    with sqlite3.connect(home / "alab.db") as conn:
        source_id = conn.execute(
            "SELECT source_id FROM sources WHERE project_id = ? ORDER BY source_id LIMIT 1",
            (project_id,),
        ).fetchone()[0]
        validation_id = conn.execute(
            "SELECT validation_id FROM project_validations WHERE project_id = ? ORDER BY validation_id LIMIT 1",
            (project_id,),
        ).fetchone()[0]

    cases = [
        ("project remove", [*root_args, "project", "remove", "--project", project_id, "--dry-run", "--cascade"]),
        ("project validation remove", [*admin_args, "project", "validation", "remove", validation_id, "--project", project_id, "--dry-run", "--cascade"]),
        ("source remove", [*admin_args, "source", "remove", source_id, "--project", project_id, "--dry-run", "--cascade"]),
        ("exp remove", [*admin_args, "exp", "remove", exp_id, "--project", project_id, "--dry-run", "--cascade"]),
        ("exp worktree remove", [*admin_args, "exp", "worktree", "remove", exp_id, "--project", project_id, "--dry-run"]),
        ("exp checkout remove", [*admin_args, "exp", "checkout", "remove", "--project", project_id, "--token-id", checkout_token_id, "--dry-run"]),
        ("runs remove", [*admin_args, "runs", "remove", run_id, "--project", project_id, "--cascade", "--dry-run"]),
        ("artifacts remove", [*admin_args, "artifacts", "remove", artifact_id, "--project", project_id, "--dry-run"]),
        ("logs remove", [*admin_args, "logs", "remove", log_id, "--project", project_id, "--dry-run"]),
        ("annotate remove", [*admin_args, "annotate", "remove", annotation_id, "--project", project_id, "--dry-run"]),
    ]
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        worktree_path / ".alab" / "context.json",
        worktree_path / ".alab" / "token",
        checkout_path / ".alab" / "context.json",
        checkout_path / ".alab" / "token",
    ]
    watched_dirs = [
        home / "projects" / project_id,
        home / "sources",
        home / "project-workspaces" / project_id,
        worktree_path,
        checkout_path,
    ]
    trash_root = home / "tmp" / "trash"
    watched_tree_roots = [*watched_dirs, trash_root]

    failures = []
    for command_name, args in cases:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.out)
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        dirs_present = all(path.exists() for path in watched_dirs)
        if (
            code != 0
            or captured.err
            or fields.get("dry run") != "true"
            or fields.get("removed") != "false"
            or fields.get("audit id") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
            or not dirs_present
        ):
            failures.append(
                {
                    "command": command_name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                    "dirs present": dirs_present,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_hard_remove_commands_reject_mixed_dry_run_and_force_without_side_effects(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="mixed-remove-mode-worktree",
    )
    admin_args = ["--home", str(home), "--key", admin_key]
    root_args = ["--home", str(home), "--key", root_key]

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "mixed remove mode matrix"]) == 0
    run_fields = _output_field_map(capsys.readouterr().out)
    run_id = run_fields["run id"]
    exp_id = run_fields["exp id"]

    assert cli.run([*admin_args, "artifacts", "list", "--project", project_id, "--run", run_id]) == 0
    artifact_id = _output_field_map(capsys.readouterr().out)["artifact id"]
    assert cli.run([*admin_args, "logs", "list", "--project", project_id, "--run", run_id, "--stream", "stdout"]) == 0
    log_id = _output_field_map(capsys.readouterr().out)["log id"]

    assert cli.run([*admin_args, "annotate", "add", "--project", project_id, "--target", f"exp:{exp_id}", "--body", "mixed mode note"]) == 0
    annotation_id = _output_field_map(capsys.readouterr().out)["annotation id"]

    checkout_path = tmp_path / "mixed-remove-mode-inspection"
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "checkout",
                exp_id,
                "--project",
                project_id,
                "--path",
                str(checkout_path),
                "--commit",
                "latest",
            ]
        )
        == 0
    )
    checkout_token_id = _output_field_map(capsys.readouterr().out)["token id"]

    with sqlite3.connect(home / "alab.db") as conn:
        source_id = conn.execute(
            "SELECT source_id FROM sources WHERE project_id = ? ORDER BY source_id LIMIT 1",
            (project_id,),
        ).fetchone()[0]
        validation_id = conn.execute(
            "SELECT validation_id FROM project_validations WHERE project_id = ? ORDER BY validation_id LIMIT 1",
            (project_id,),
        ).fetchone()[0]

    cases = [
        ("project remove", [*root_args, "project", "remove", "--project", project_id, "--cascade"], project_id),
        ("project validation remove", [*admin_args, "project", "validation", "remove", validation_id, "--project", project_id, "--cascade"], validation_id),
        ("source remove", [*admin_args, "source", "remove", source_id, "--project", project_id, "--cascade"], source_id),
        ("exp remove", [*admin_args, "exp", "remove", exp_id, "--project", project_id, "--cascade"], exp_id),
        ("exp worktree remove", [*admin_args, "exp", "worktree", "remove", exp_id, "--project", project_id], exp_id),
        ("exp checkout remove", [*admin_args, "exp", "checkout", "remove", "--project", project_id, "--token-id", checkout_token_id], checkout_token_id),
        ("runs remove", [*admin_args, "runs", "remove", run_id, "--project", project_id, "--cascade"], run_id),
        ("artifacts remove", [*admin_args, "artifacts", "remove", artifact_id, "--project", project_id], artifact_id),
        ("logs remove", [*admin_args, "logs", "remove", log_id, "--project", project_id], log_id),
        ("annotate remove", [*admin_args, "annotate", "remove", annotation_id, "--project", project_id], annotation_id),
    ]
    variants = [
        ("force only", lambda _expected: ["--dry-run", "--force"]),
        ("confirm only", lambda expected: ["--dry-run", "--confirm", expected]),
        ("force confirm", lambda expected: ["--dry-run", "--force", "--confirm", expected]),
    ]
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        worktree_path / ".alab" / "context.json",
        worktree_path / ".alab" / "token",
        checkout_path / ".alab" / "context.json",
        checkout_path / ".alab" / "token",
    ]
    watched_dirs = [
        home / "projects" / project_id,
        home / "sources",
        home / "project-workspaces" / project_id,
        worktree_path,
        checkout_path,
    ]
    trash_root = home / "tmp" / "trash"
    watched_tree_roots = [*watched_dirs, trash_root]

    failures = []
    for command_name, base_args, expected_confirm in cases:
        for variant_name, suffix_factory in variants:
            before_snapshot = _database_snapshot(home)
            watched_file_contents = _text_file_snapshot(watched_files)
            watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
            code = cli.run([*base_args, *suffix_factory(expected_confirm)])
            captured = capsys.readouterr()
            fields = _output_field_map(captured.err)
            db_unchanged = _database_snapshot(home) == before_snapshot
            files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
            trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
            dirs_present = all(path.exists() for path in watched_dirs)
            if (
                code != 2
                or captured.out
                or _output_field_labels(captured.err) != _error_field_labels()
                or fields.get("error code") != "CONFIG_INVALID"
                or fields.get("exit code") != "2"
                or fields.get("reason") != "--dry-run conflicts with --force/--confirm"
                or fields.get("next") != "none"
                or not db_unchanged
                or not files_unchanged
                or not trees_unchanged
                or not dirs_present
            ):
                failures.append(
                    {
                        "command": command_name,
                        "variant": variant_name,
                        "code": code,
                        "stdout": captured.out,
                        "stderr": captured.err,
                        "fields": fields,
                        "db unchanged": db_unchanged,
                        "files unchanged": files_unchanged,
                        "trees unchanged": trees_unchanged,
                        "dirs present": dirs_present,
                    }
                )

    assert failures == [], json.dumps(failures, indent=2)


def test_hard_remove_lifecycle_blockers_preserve_database_and_filesystem(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="blocked-remove-side-effect-worktree",
    )
    admin_args = ["--home", str(home), "--key", admin_key]
    root_args = ["--home", str(home), "--key", root_key]

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "blocked remove side-effect matrix"]) == 0
    run_fields = _output_field_map(capsys.readouterr().out)
    run_id = run_fields["run id"]
    exp_id = run_fields["exp id"]

    assert cli.run([*admin_args, "artifacts", "list", "--project", project_id, "--run", run_id]) == 0
    artifact_id = _output_field_map(capsys.readouterr().out)["artifact id"]
    assert cli.run([*admin_args, "logs", "list", "--project", project_id, "--run", run_id, "--stream", "stdout"]) == 0
    log_id = _output_field_map(capsys.readouterr().out)["log id"]

    assert cli.run([*admin_args, "annotate", "add", "--project", project_id, "--target", f"exp:{exp_id}", "--body", "blocked remove note"]) == 0
    annotation_id = _output_field_map(capsys.readouterr().out)["annotation id"]

    with sqlite3.connect(home / "alab.db") as conn:
        source_id = conn.execute(
            "SELECT source_id FROM sources WHERE project_id = ? ORDER BY source_id LIMIT 1",
            (project_id,),
        ).fetchone()[0]
        validation_id = conn.execute(
            "SELECT validation_id FROM project_validations WHERE project_id = ? ORDER BY validation_id LIMIT 1",
            (project_id,),
        ).fetchone()[0]

    cases = [
        (
            "project remove",
            [*root_args, "project", "remove", "--project", project_id, "--cascade", "--force", "--confirm", project_id],
            "target_not_archived",
        ),
        (
            "project validation remove",
            [*admin_args, "project", "validation", "remove", validation_id, "--project", project_id, "--cascade", "--force", "--confirm", validation_id],
            "active_validation",
        ),
        (
            "source remove",
            [*admin_args, "source", "remove", source_id, "--project", project_id, "--cascade", "--force", "--confirm", source_id],
            "target_not_archived",
        ),
        (
            "exp remove",
            [*admin_args, "exp", "remove", exp_id, "--project", project_id, "--cascade", "--force", "--confirm", exp_id],
            "target_not_archived",
        ),
        (
            "runs remove",
            [*admin_args, "runs", "remove", run_id, "--project", project_id, "--cascade", "--force", "--confirm", run_id],
            "target_not_archived",
        ),
        (
            "artifacts remove",
            [*admin_args, "artifacts", "remove", artifact_id, "--project", project_id, "--force", "--confirm", artifact_id],
            "target_not_archived",
        ),
        (
            "logs remove",
            [*admin_args, "logs", "remove", log_id, "--project", project_id, "--force", "--confirm", log_id],
            "target_not_archived",
        ),
        (
            "annotate remove",
            [*admin_args, "annotate", "remove", annotation_id, "--project", project_id, "--force", "--confirm", annotation_id],
            "target_not_archived",
        ),
    ]
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        worktree_path / ".alab" / "context.json",
        worktree_path / ".alab" / "token",
    ]
    watched_dirs = [
        home / "projects" / project_id,
        home / "sources",
        home / "project-workspaces" / project_id,
        worktree_path,
    ]
    trash_root = home / "tmp" / "trash"
    watched_tree_roots = [*watched_dirs, trash_root]

    failures = []
    for command_name, args, expected_blocker in cases:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err)
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        dirs_present = all(path.exists() for path in watched_dirs)
        if (
            code != 4
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "RESOURCE_BUSY"
            or fields.get("exit code") != "4"
            or expected_blocker not in fields.get("reason", "")
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
            or not dirs_present
        ):
            failures.append(
                {
                    "command": command_name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                    "dirs present": dirs_present,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_hard_remove_dependency_blockers_preserve_database_and_filesystem(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="dependency-blocker-worktree",
    )
    admin_args = ["--home", str(home), "--key", admin_key]
    repo_git = home / "projects" / project_id / "repo.git"

    with sqlite3.connect(home / "alab.db") as conn:
        validation_id = conn.execute(
            "SELECT validation_id FROM project_validations WHERE project_id = ? ORDER BY validation_id LIMIT 1",
            (project_id,),
        ).fetchone()[0]

    assert cli.run([*admin_args, "project", "validate", "--project", project_id]) == 0
    capsys.readouterr()
    assert cli.run([*admin_args, "project", "validation", "archive", validation_id, "--project", project_id]) == 0
    capsys.readouterr()

    monkeypatch.chdir(worktree_path)
    assert cli.run(["--home", str(home), "run", "--message", "dependency blocker matrix"]) == 0
    run_id = _output_field_map(capsys.readouterr().out)["run id"]
    assert cli.run([*admin_args, "runs", "archive", run_id, "--project", project_id]) == 0
    capsys.readouterr()

    assert cli.run([*admin_args, "source", "import", "--project", project_id, "--source-empty", "--name", "dependency-blocker-source"]) == 0
    source_fields = _output_field_map(capsys.readouterr().out)
    source_id = source_fields["source id"]
    source_ref = source_fields["source ref"]
    dependent_worktree = tmp_path / "dependency-blocker-source-exp"
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Dependency Blocker Source Experiment",
                "--source-ref",
                source_ref,
                "--path",
                str(dependent_worktree),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert cli.run([*admin_args, "source", "archive", source_id, "--project", project_id]) == 0
    capsys.readouterr()

    cases = [
        (
            "validation remove no cascade",
            [*admin_args, "project", "validation", "remove", validation_id, "--project", project_id, "--force", "--confirm", validation_id],
            "dependent_records_require_cascade",
        ),
        (
            "validation remove cascade active children",
            [*admin_args, "project", "validation", "remove", validation_id, "--project", project_id, "--cascade", "--force", "--confirm", validation_id],
            "dependent_records_not_archived",
        ),
        (
            "source remove no cascade",
            [*admin_args, "source", "remove", source_id, "--project", project_id, "--force", "--confirm", source_id],
            "dependent_records_require_cascade",
        ),
        (
            "source remove cascade active children",
            [*admin_args, "source", "remove", source_id, "--project", project_id, "--cascade", "--force", "--confirm", source_id],
            "dependent_records_not_archived",
        ),
        (
            "run remove no cascade",
            [*admin_args, "runs", "remove", run_id, "--project", project_id, "--force", "--confirm", run_id],
            "dependent_records_require_cascade",
        ),
        (
            "run remove cascade active children",
            [*admin_args, "runs", "remove", run_id, "--project", project_id, "--cascade", "--force", "--confirm", run_id],
            "dependent_records_not_archived",
        ),
    ]
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        worktree_path / ".alab" / "context.json",
        worktree_path / ".alab" / "token",
        dependent_worktree / ".alab" / "context.json",
        dependent_worktree / ".alab" / "token",
    ]
    watched_dirs = [
        home / "projects" / project_id,
        home / "sources",
        home / "project-workspaces" / project_id,
        worktree_path,
        dependent_worktree,
    ]
    trash_root = home / "tmp" / "trash"
    watched_tree_roots = [*watched_dirs, trash_root]

    def git_ref_commit(ref: str) -> str:
        result = subprocess.run(
            ["git", "--git-dir", str(repo_git), "rev-parse", "--verify", ref],
            capture_output=True,
            check=False,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    failures = []
    for command_name, args, expected_blocker in cases:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_tree_roots}
        source_ref_commit_before = git_ref_commit(f"refs/heads/{source_ref}")
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err)
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        dirs_present = all(path.exists() for path in watched_dirs)
        git_ref_unchanged = git_ref_commit(f"refs/heads/{source_ref}") == source_ref_commit_before
        if (
            code != 4
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "RESOURCE_BUSY"
            or fields.get("exit code") != "4"
            or expected_blocker not in fields.get("reason", "")
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
            or not dirs_present
            or not git_ref_unchanged
        ):
            failures.append(
                {
                    "command": command_name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                    "dirs present": dirs_present,
                    "git ref unchanged": git_ref_unchanged,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_archived_closed_and_removed_scope_errors_preserve_database_and_filesystem(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, root_key, project_id, admin_key, worktree_path = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="state-error-matrix-worktree",
    )
    admin_args = ["--home", str(home), "--key", admin_key]
    submit_args = [
        "--home",
        str(home),
        "submit",
        "--message",
        "state error matrix submit",
        "--summary",
        "done",
        "--feedback",
        "ok",
        "--ref",
        "none",
    ]
    run_args = ["--home", str(home), "run", "--message", "state error matrix run"]
    child_worktree = tmp_path / "archived-project-child"
    scope_worktree = tmp_path / "removed-scope-worktree"

    assert cli.run([*admin_args, "project", "archive", "--project", project_id]) == 0
    capsys.readouterr()

    archived_cases = [
        (
            "exp create",
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Archived Project Child",
                "--path",
                str(child_worktree),
            ],
            tmp_path,
        ),
        ("run", run_args, worktree_path),
        ("submit", submit_args, worktree_path),
    ]
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        worktree_path / ".alab" / "context.json",
        worktree_path / ".alab" / "token",
    ]
    watched_roots = [
        home / "projects" / project_id,
        home / "project-workspaces" / project_id,
        home / "tmp",
        worktree_path,
        child_worktree,
    ]

    failures = []
    for command_name, args, cwd in archived_cases:
        monkeypatch.chdir(cwd)
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_roots}
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err)
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        if (
            code != 4
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "PROJECT_ARCHIVED"
            or fields.get("exit code") != "4"
            or fields.get("reason") != "project is archived"
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
        ):
            failures.append(
                {
                    "state": "project archived",
                    "command": command_name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                }
            )

    assert cli.run([*admin_args, "project", "unarchive", "--project", project_id]) == 0
    capsys.readouterr()
    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Removed Scope Matrix",
                "--path",
                str(scope_worktree),
            ]
        )
        == 0
    )
    with sqlite3.connect(home / "alab.db") as conn:
        scope_exp_id = conn.execute(
            "SELECT exp_id FROM experiments WHERE project_id = ? AND worktree_path = ?",
            (project_id, str(scope_worktree)),
        ).fetchone()[0]
    capsys.readouterr()

    monkeypatch.chdir(worktree_path)
    assert cli.run(run_args) == 0
    capsys.readouterr()
    assert cli.run(submit_args) == 0
    capsys.readouterr()
    closed_cases = [("run", run_args), ("submit", submit_args)]
    watched_roots = [
        home / "projects" / project_id,
        home / "project-workspaces" / project_id,
        home / "tmp",
        worktree_path,
        scope_worktree,
    ]
    for command_name, args in closed_cases:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_roots}
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err)
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        if (
            code != 4
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "EXPERIMENT_CLOSED"
            or fields.get("exit code") != "4"
            or fields.get("reason") != "experiment is not open"
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
        ):
            failures.append(
                {
                    "state": "experiment closed",
                    "command": command_name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                }
            )

    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute("UPDATE experiments SET worktree_state = 'removed' WHERE exp_id = ?", (scope_exp_id,))
    monkeypatch.chdir(scope_worktree)
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        scope_worktree / ".alab" / "context.json",
        scope_worktree / ".alab" / "token",
    ]
    for command_name, args in closed_cases:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_roots}
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err)
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        if (
            code != 4
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "SCOPE_VIOLATION"
            or fields.get("exit code") != "4"
            or fields.get("reason") != "experiment worktree is removed"
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
        ):
            failures.append(
                {
                    "state": "worktree removed",
                    "command": command_name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_visibility_scope_selector_errors_are_non_disclosing_and_side_effect_free(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home, _root_key, project_id, admin_key, first_worktree = _init_observable_asset_contract_project(
        tmp_path,
        capsys,
        worktree_name="visibility-scope-first",
    )
    admin_args = ["--home", str(home), "--key", admin_key]
    peer_worktree = tmp_path / "visibility-scope-peer"

    assert (
        cli.run(
            [
                *admin_args,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Visibility Scope Peer",
                "--path",
                str(peer_worktree),
            ]
        )
        == 0
    )
    peer_exp_id = _output_field_map(capsys.readouterr().out)["exp id"]
    monkeypatch.chdir(peer_worktree)
    assert cli.run(["--home", str(home), "run", "--message", "visibility selector peer run"]) == 0
    peer_run_id = _output_field_map(capsys.readouterr().out)["run id"]
    assert cli.run(["--home", str(home), "annotate", "add", "--target", f"exp:{peer_exp_id}", "--body", "peer-only note"]) == 0
    peer_annotation_id = _output_field_map(capsys.readouterr().out)["annotation id"]

    with sqlite3.connect(home / "alab.db") as conn:
        peer_artifact_id = conn.execute(
            "SELECT artifact_id FROM artifacts WHERE run_id = ? ORDER BY artifact_id LIMIT 1",
            (peer_run_id,),
        ).fetchone()[0]
        peer_log_id = conn.execute(
            "SELECT log_id FROM log_streams WHERE run_id = ? AND stream = 'stdout' ORDER BY log_id LIMIT 1",
            (peer_run_id,),
        ).fetchone()[0]

    assert cli.run([*admin_args, "project", "config", "set", "visibility.scope", '"none"', "--project", project_id]) == 0
    capsys.readouterr()
    monkeypatch.chdir(first_worktree)

    selector_cases = [
        (
            "exp show",
            ["--home", str(home), "exp", "show", peer_exp_id],
            "experiment is not visible or not found",
            "EXPERIMENT_NOT_FOUND",
        ),
        (
            "runs show",
            ["--home", str(home), "runs", "show", peer_run_id],
            "run is not visible or not found",
            "RUN_NOT_FOUND",
        ),
        (
            "artifacts show",
            ["--home", str(home), "artifacts", "show", peer_artifact_id],
            "artifact is not visible or not found",
            "ARTIFACT_NOT_FOUND",
        ),
        (
            "logs show",
            ["--home", str(home), "logs", "show", peer_log_id],
            "log is not visible or not found",
            "LOG_NOT_FOUND",
        ),
        (
            "annotations show",
            ["--home", str(home), "annotations", "show", peer_annotation_id],
            "annotation is not visible or not found",
            "ANNOTATION_NOT_FOUND",
        ),
    ]
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
        first_worktree / ".alab" / "context.json",
        first_worktree / ".alab" / "token",
        peer_worktree / ".alab" / "context.json",
        peer_worktree / ".alab" / "token",
    ]
    watched_roots = [
        home / "projects" / project_id,
        home / "project-workspaces" / project_id,
        home / "tmp",
        first_worktree,
        peer_worktree,
    ]

    failures = []
    for command_name, args, expected_reason, forbidden_code in selector_cases:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_roots}
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err)
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        if (
            code != 4
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != "SCOPE_VIOLATION"
            or fields.get("exit code") != "4"
            or fields.get("reason") != expected_reason
            or fields.get("next") != "none"
            or forbidden_code in captured.err
            or peer_exp_id in captured.err
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
        ):
            failures.append(
                {
                    "command": command_name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_config_version_value_errors_preserve_database_and_filesystem(
    tmp_path: Path,
    capsys,
) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    source.mkdir()
    (source / "main.py").write_text("print('baseline')\n", encoding="utf-8")
    _write_local_project_config(
        config,
        name="Config Version Value Matrix",
        runner_command=[sys.executable, "-c", "print('ok')"],
    )

    assert cli.run(["--home", str(home), "auth", "init"]) == 0
    root_key = _output_field_map(capsys.readouterr().out)["root key"]
    assert (
        cli.run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(config),
                "--source-path",
                str(source),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    project_fields = _output_field_map(capsys.readouterr().out)
    project_id = project_fields["project id"]
    admin_key = project_fields["admin key"]
    admin_args = ["--home", str(home), "--key", admin_key]
    with sqlite3.connect(home / "alab.db") as conn:
        project_state = conn.execute(
            "SELECT status, latest_attempted_config_version, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert project_state == ("invalid", 1, None, None)

    active_export = tmp_path / "exports" / "active.toml"
    missing_export = tmp_path / "exports" / "missing.toml"
    bad_selector_export = tmp_path / "exports" / "bad-selector.toml"
    watched_files = [
        home / "config.toml",
        home / "project-workspaces" / project_id / ".alab" / "context.json",
    ]
    watched_roots = [
        home / "projects" / project_id,
        home / "project-workspaces" / project_id,
        home / "tmp",
        tmp_path / "exports",
    ]
    cases = [
        (
            "project config show active-valid",
            [*admin_args, "project", "config", "show", "--project", project_id, "--version", "active-valid"],
            4,
            "PROJECT_INVALID",
            "project has no active valid config",
            None,
        ),
        (
            "project config export active-valid",
            [
                *admin_args,
                "project",
                "config",
                "export",
                "--project",
                project_id,
                "--version",
                "active-valid",
                "--out",
                str(active_export),
            ],
            4,
            "PROJECT_INVALID",
            "project has no active valid config",
            active_export,
        ),
        (
            "project config show missing version",
            [*admin_args, "project", "config", "show", "--project", project_id, "--version", "99"],
            2,
            "CONFIG_INVALID",
            "config version not found",
            None,
        ),
        (
            "project config export missing version",
            [
                *admin_args,
                "project",
                "config",
                "export",
                "--project",
                project_id,
                "--version",
                "99",
                "--out",
                str(missing_export),
            ],
            2,
            "CONFIG_INVALID",
            "config version not found",
            missing_export,
        ),
        (
            "project config export bad selector",
            [
                *admin_args,
                "project",
                "config",
                "export",
                "--project",
                project_id,
                "--version",
                "not-a-version",
                "--out",
                str(bad_selector_export),
            ],
            2,
            "CONFIG_INVALID",
            "invalid config version selector",
            bad_selector_export,
        ),
        (
            "exp best missing active config",
            [*admin_args, "exp", "best", "--project", project_id],
            4,
            "PROJECT_INVALID",
            "best requires an active valid config or explicit --config-version",
            None,
        ),
        (
            "exp best missing explicit config",
            [*admin_args, "exp", "best", "--project", project_id, "--config-version", "99"],
            2,
            "CONFIG_INVALID",
            "config version not found",
            None,
        ),
    ]

    failures = []
    for command_name, args, expected_code, expected_error_code, expected_reason, absent_path in cases:
        before_snapshot = _database_snapshot(home)
        watched_file_contents = _text_file_snapshot(watched_files)
        watched_tree_contents = {root: _tree_snapshot(root) for root in watched_roots}
        code = cli.run(args)
        captured = capsys.readouterr()
        fields = _output_field_map(captured.err) if captured.err else {}
        db_unchanged = _database_snapshot(home) == before_snapshot
        files_unchanged = _text_file_snapshot(watched_files) == watched_file_contents
        trees_unchanged = all(_tree_snapshot(root) == tree for root, tree in watched_tree_contents.items())
        output_absent = absent_path is None or not absent_path.exists()
        if (
            code != expected_code
            or captured.out
            or _output_field_labels(captured.err) != _error_field_labels()
            or fields.get("error code") != expected_error_code
            or fields.get("exit code") != str(expected_code)
            or fields.get("reason") != expected_reason
            or fields.get("next") != "none"
            or not db_unchanged
            or not files_unchanged
            or not trees_unchanged
            or not output_absent
        ):
            failures.append(
                {
                    "command": command_name,
                    "code": code,
                    "stdout": captured.out,
                    "stderr": captured.err,
                    "fields": fields,
                    "db unchanged": db_unchanged,
                    "files unchanged": files_unchanged,
                    "trees unchanged": trees_unchanged,
                    "output absent": output_absent,
                }
            )

    assert failures == [], json.dumps(failures, indent=2)


def test_known_option_allowlists_use_declared_options() -> None:
    calls, non_literal = _known_option_calls()
    assert non_literal == []

    duplicated = [
        f"{function_name}:{line_number} {options}"
        for function_name, line_number, options in calls
        if len(options) != len(set(options))
    ]
    assert duplicated == []

    malformed = [
        f"{function_name}:{line_number} {option}"
        for function_name, line_number, options in calls
        for option in options
        if not option.startswith("--") or option == "--"
    ]
    assert malformed == []

    known_options = set(services.OPTIONS_WITH_VALUES) | _KNOWN_FLAG_OPTIONS
    unknown = sorted(
        {
            option
            for _function_name, _line_number, options in calls
            for option in options
            if option not in known_options
        }
    )
    assert unknown == []

    allowed_flags = {option for _function_name, _line_number, options in calls for option in options} - set(services.OPTIONS_WITH_VALUES)
    assert allowed_flags == _KNOWN_FLAG_OPTIONS


def test_known_option_allowlists_cover_literal_option_reads() -> None:
    gaps = [
        f"{function_name}: {sorted(set(used) - set(declared))}"
        for function_name, declared, used in _known_option_declarations_and_usage()
        if not set(used) <= set(declared)
    ]

    assert gaps == []


def test_literal_value_option_reads_are_registered_for_positional_parsing() -> None:
    missing = [
        f"{function_name}:{line_number} {call_name}({option})"
        for function_name, line_number, call_name, option in _literal_value_option_reads()
        if option not in services.OPTIONS_WITH_VALUES
    ]

    assert missing == []


def test_known_options_are_duplicate_guarded_or_explicitly_repeatable() -> None:
    gaps = [
        f"{function_name}: {sorted(set(declared) - set(guarded) - set(repeatable))}"
        for function_name, declared, guarded, repeatable in _singleton_option_declarations_and_guards()
        if not set(declared) <= set(guarded) | set(repeatable)
    ]

    assert gaps == []


def test_readme_opt_in_pytest_marker_commands_follow_pyproject_and_tests() -> None:
    declared_markers = _declared_pytest_markers()
    readme_markers = _readme_pytest_marker_commands(_README_PATH)
    readme_cn_markers = _readme_pytest_marker_commands(_README_CN_PATH)
    used_markers = _used_declared_pytest_markers()

    assert readme_markers == declared_markers
    assert readme_cn_markers == declared_markers
    assert len(declared_markers) == len(set(declared_markers))
    assert sorted(used_markers) == sorted(declared_markers)


def test_root_and_docs_markdown_files_have_synchronized_chinese_pairs() -> None:
    missing_chinese, orphan_chinese = _project_markdown_pair_gaps()

    assert missing_chinese == []
    assert orphan_chinese == []


def test_chinese_only_potential_issues_note_is_the_only_markdown_pair_exception() -> None:
    note = _REPO_ROOT / "潜在问题.md"

    assert _MARKDOWN_PAIR_EXCEPTIONS == {"潜在问题.md"}
    if note.is_file():
        assert "用户指定的中文单文件" in note.read_text(encoding="utf-8")


def test_examples_matrix_paths_exist_and_document_current_examples() -> None:
    expected_examples = {
        "local_agent_scoreboard",
        "docker_file_reward_artifacts",
        "harbor_verifier_minimal",
        "collaboration_observe_lifecycle",
        "dashboard_showcase",
        "skydiscover_circle_packing_codex",
        "templates",
    }
    readme = (_EXAMPLES_ROOT / "README.md").read_text(encoding="utf-8")
    readme_cn = (_EXAMPLES_ROOT / "README_cn.md").read_text(encoding="utf-8")
    actual_examples = {path.name for path in _EXAMPLES_ROOT.iterdir() if path.is_dir() and not path.name.startswith(".")}

    assert actual_examples == expected_examples
    assert "## Overview" in readme
    assert "## Example Matrix" in readme
    assert "## Suggested Path" in readme
    assert "## 总览" in readme_cn
    assert "## 示例矩阵" in readme_cn
    assert "## 建议阅读路径" in readme_cn
    assert "| Example | Demo task |" in readme
    assert "| 示例 | Demo 任务 |" in readme_cn
    for example in sorted(expected_examples):
        example_dir = _EXAMPLES_ROOT / example
        assert f"[{example}]({example}/)" in readme
        assert f"[{example}]({example}/)" in readme_cn
        assert (example_dir / ".gitignore").is_file()
        assert (example_dir / "README.md").is_file()
        assert (example_dir / "README_cn.md").is_file()
        assert (example_dir / "scripts").is_dir()
        assert ".run/" in (example_dir / ".gitignore").read_text(encoding="utf-8")


def test_examples_are_task_shaped_demos() -> None:
    required_paths = {
        "local_agent_scoreboard": ["source/solution.py", "prompts/worker.md"],
        "docker_file_reward_artifacts": [
            "source/main.py",
            "source/data/orders.json",
            "source/data/warehouses.json",
        ],
        "harbor_verifier_minimal": [
            "task/instruction.md",
            "task/starter/main.py",
            "task/tests/test.sh",
        ],
        "collaboration_observe_lifecycle": [
            "source/solver.py",
            "source/data/incidents.json",
        ],
        "dashboard_showcase": [
            "scripts/create_demo_home.py",
            "scripts/run_dashboard.sh",
        ],
        "skydiscover_circle_packing_codex": [
            "alab.project.toml",
            "prompts/worker.md",
        ],
        "templates": [
            "tsp_local/alab.project.toml",
            "tsp_local/README.md",
            "tsp_local/README_cn.md",
            "tsp_local/source/instances.json",
            "tsp_local/source/solution.py",
            "tsp_local/source/validate_tsp.py",
            "tsp_docker/alab.project.toml",
            "tsp_docker/README.md",
            "tsp_docker/README_cn.md",
            "tsp_docker/source/Dockerfile",
            "tsp_docker/source/instances.json",
            "tsp_docker/source/solution.py",
            "tsp_docker/source/validate_tsp.py",
            "tsp_harbor/alab.project.template.toml",
            "tsp_harbor/README.md",
            "tsp_harbor/README_cn.md",
            "tsp_harbor/task/task.toml",
            "tsp_harbor/task/starter/instances.json",
            "tsp_harbor/task/starter/solution.py",
            "tsp_harbor/task/tests/test.sh",
            "tsp_skydiscover_python/alab.project.template.toml",
            "tsp_skydiscover_python/README.md",
            "tsp_skydiscover_python/README_cn.md",
            "tsp_skydiscover_python/source/instances.json",
            "tsp_skydiscover_python/source/solution.py",
            "tsp_skydiscover_python/evaluator/evaluator.py",
            "tsp_skydiscover_docker/alab.project.template.toml",
            "tsp_skydiscover_docker/README.md",
            "tsp_skydiscover_docker/README_cn.md",
            "tsp_skydiscover_docker/source/instances.json",
            "tsp_skydiscover_docker/source/solution.py",
            "tsp_skydiscover_docker/evaluator/Dockerfile",
            "tsp_skydiscover_docker/evaluator/evaluate.sh",
            "tsp_skydiscover_docker/evaluator/evaluator.py",
            "reference_solution/README.md",
            "reference_solution/README_cn.md",
            "reference_solution/solution.py",
            "scripts/check_templates.sh",
        ],
    }

    for example, paths in required_paths.items():
        example_dir = _EXAMPLES_ROOT / example
        readme = (example_dir / "README.md").read_text(encoding="utf-8")
        readme_cn = (example_dir / "README_cn.md").read_text(encoding="utf-8")
        assert "## Demo Task" in readme
        assert "## Demo 任务" in readme_cn
        for path in paths:
            assert (example_dir / path).is_file()
    skydiscover = _EXAMPLES_ROOT / "skydiscover_circle_packing_codex"
    assert not (skydiscover / "prompts" / "controller.md").exists()
    assert not (skydiscover / "scripts" / "run_controller.sh").exists()


def test_tsp_templates_are_complete_and_dry_run() -> None:
    templates_root = _EXAMPLES_ROOT / "templates"
    template_names = {
        "tsp_local",
        "tsp_docker",
        "tsp_harbor",
        "tsp_skydiscover_python",
        "tsp_skydiscover_docker",
    }
    readme = (templates_root / "README.md").read_text(encoding="utf-8")
    readme_cn = (templates_root / "README_cn.md").read_text(encoding="utf-8")
    actual_templates = {path.name for path in templates_root.iterdir() if path.is_dir() and path.name.startswith("tsp_")}
    shell_scripts = [path for path in sorted(templates_root.rglob("*.sh")) if ".run" not in path.parts]

    assert actual_templates == template_names
    assert "## Template Matrix" in readme
    assert "## 模板矩阵" in readme_cn
    assert "100-city" in readme
    assert "500-city" in readme
    assert "1000-city" in readme
    assert "total_tour_length <= 2650000" in readme
    assert "100-city" in readme_cn
    assert "500-city" in readme_cn
    assert "1000-city" in readme_cn
    assert "total_tour_length <= 2650000" in readme_cn
    assert "Each `tsp_*` directory has its own short README" in readme
    assert "每个 `tsp_*` 目录都有自己的简短 README" in readme_cn
    assert "shell-quoted command string" in readme
    assert "shell-quoted command string" in readme_cn
    assert shell_scripts
    assert "not a claim of global optimality" in readme
    assert "不表示全局最优保证" in readme_cn
    assert (templates_root / "reference_solution" / "solution.py").is_file()
    assert (templates_root / "reference_solution" / "README.md").is_file()
    assert (templates_root / "reference_solution" / "README_cn.md").is_file()
    for name in sorted(template_names):
        assert f"[{name}]({name}/)" in readme
        assert f"[{name}]({name}/)" in readme_cn
        assert (templates_root / name / "README.md").is_file()
        assert (templates_root / name / "README_cn.md").is_file()
        local_readme = (templates_root / name / "README.md").read_text(encoding="utf-8")
        local_readme_cn = (templates_root / name / "README_cn.md").read_text(encoding="utf-8")
        assert "scripts/setup_project.sh --dry-run" in local_readme
        assert "scripts/run_demo.sh" in local_readme
        assert "ALAB_BIN" in local_readme
        assert "scripts/setup_project.sh --dry-run" in local_readme_cn
        assert "scripts/run_demo.sh" in local_readme_cn
        assert "ALAB_BIN" in local_readme_cn
        assert (templates_root / name / ".gitignore").read_text(encoding="utf-8").strip() == ".run/"
        assert (templates_root / name / "scripts" / "setup_project.sh").is_file()
        assert (templates_root / name / "scripts" / "run_demo.sh").is_file()

    template_sources = {
        "tsp_local": templates_root / "tsp_local" / "source",
        "tsp_docker": templates_root / "tsp_docker" / "source",
        "tsp_harbor": templates_root / "tsp_harbor" / "task" / "starter",
        "tsp_skydiscover_python": templates_root / "tsp_skydiscover_python" / "source",
        "tsp_skydiscover_docker": templates_root / "tsp_skydiscover_docker" / "source",
    }
    template_configs = {
        "tsp_local": templates_root / "tsp_local" / "alab.project.toml",
        "tsp_docker": templates_root / "tsp_docker" / "alab.project.toml",
        "tsp_harbor": templates_root / "tsp_harbor" / "alab.project.template.toml",
        "tsp_skydiscover_python": templates_root / "tsp_skydiscover_python" / "alab.project.template.toml",
        "tsp_skydiscover_docker": templates_root / "tsp_skydiscover_docker" / "alab.project.template.toml",
    }
    for name in sorted(template_names):
        source_dir = template_sources[name]
        payload = json.loads((source_dir / "instances.json").read_text(encoding="utf-8"))
        counts: dict[int, int] = defaultdict(int)
        for instance in payload["instances"]:
            counts[int(instance["city_count"])] += 1
        assert dict(counts) == {100: 5, 500: 5, 1000: 5}
        assert sum(int(instance["city_count"]) for instance in payload["instances"]) == 8000
        assert not (source_dir / "cities.json").exists()
        starter = (source_dir / "solution.py").read_text(encoding="utf-8")
        assert "IMPROVE_WITH_NEAREST_NEIGHBOR = False" in starter
        assert "return list(range(len(cities)))" in starter
        config = tomllib.loads(template_configs[name].read_text(encoding="utf-8"))
        assert config["reward"]["direction"] == "minimize"
        assert config["reward"]["primary_metric"] == "total_tour_length"

    for script in shell_scripts:
        completed = subprocess.run(
            ["bash", "-n", str(script)],
            cwd=_REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert completed.returncode == 0, f"{script}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"

    env = os.environ.copy()
    env["ALAB_REPO_ROOT"] = str(_REPO_ROOT)
    for name in sorted(template_names):
        for script_name in ("setup_project.sh", "run_demo.sh"):
            script = templates_root / name / "scripts" / script_name
            completed = subprocess.run(
                [str(script), "--dry-run"],
                cwd=templates_root / name,
                env=env,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            assert completed.returncode == 0, f"{script}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"


def test_tsp_reference_solution_meets_documented_threshold(tmp_path: Path) -> None:
    templates_root = _EXAMPLES_ROOT / "templates"

    def run_validator(source: Path, run_dir: Path) -> dict[str, float]:
        env = os.environ.copy()
        env["ALAB_RUN_DIR"] = str(run_dir)
        completed = subprocess.run(
            [sys.executable, str(source / "validate_tsp.py")],
            cwd=source,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert completed.returncode == 0, f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        return json.loads((run_dir / "reward.json").read_text(encoding="utf-8"))

    baseline_source = tmp_path / "baseline"
    shutil.copytree(templates_root / "tsp_local" / "source", baseline_source)
    baseline_metrics = run_validator(baseline_source, tmp_path / "baseline-run")

    reference_source = tmp_path / "reference"
    shutil.copytree(templates_root / "tsp_local" / "source", reference_source)
    shutil.copy2(templates_root / "reference_solution" / "solution.py", reference_source / "solution.py")
    reference_metrics = run_validator(reference_source, tmp_path / "reference-run")

    invalid_source = tmp_path / "invalid"
    shutil.copytree(templates_root / "tsp_local" / "source", invalid_source)
    (invalid_source / "solution.py").write_text(
        "def build_route(cities):\n    return [str(index) for index in range(len(cities))]\n",
        encoding="utf-8",
    )
    invalid_metrics = run_validator(invalid_source, tmp_path / "invalid-run")

    assert baseline_metrics["valid"] == 1.0
    assert baseline_metrics["instance_count"] == 15.0
    assert baseline_metrics["city_count"] == 8000.0
    assert baseline_metrics["total_tour_length"] > 40_000_000
    assert reference_metrics["valid"] == 1.0
    assert reference_metrics["instance_count"] == 15.0
    assert reference_metrics["city_count"] == 8000.0
    assert reference_metrics["total_tour_length"] <= 2_650_000
    assert invalid_metrics["valid"] == 0.0
    assert invalid_metrics["valid_instance_count"] == 0.0
    assert invalid_metrics["total_tour_length"] > 15_000_000_000


def test_tsp_local_and_skydiscover_python_templates_run_from_temp_copy(tmp_path: Path) -> None:
    templates_copy = tmp_path / "templates with spaces"
    shutil.copytree(_EXAMPLES_ROOT / "templates", templates_copy)
    alab_wrapper = tmp_path / "alab cli wrapper.py"
    alab_wrapper.write_text("from alab.cli import main\nmain()\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "ALAB_REPO_ROOT": str(_REPO_ROOT),
            "ALAB_BIN": f"{shlex.quote(sys.executable)} {shlex.quote(str(alab_wrapper))}",
            "PYTHONPYCACHEPREFIX": str(tmp_path / "pycache"),
            "PYTHONPATH": str(_REPO_ROOT / "src")
            + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""),
            "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
            "UV_DEFAULT_INDEX": "https://pypi.org/simple",
        }
    )

    for name in ("tsp_local", "tsp_skydiscover_python"):
        template_dir = templates_copy / name
        for command in (
            [str(template_dir / "scripts" / "setup_project.sh"), "--reset"],
            [str(template_dir / "scripts" / "run_demo.sh")],
        ):
            completed = subprocess.run(
                command,
                cwd=template_dir,
                env=env,
                text=True,
                capture_output=True,
                timeout=180,
                check=False,
            )
            assert completed.returncode == 0, (
                f"{name}: {' '.join(command)}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        report = template_dir / ".run" / "reports" / "report.md"
        assert "Reward value:" in report.read_text(encoding="utf-8")


def test_example_codex_launches_use_narrow_worktree_sandboxes() -> None:
    texts = {
        path.relative_to(_REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(_EXAMPLES_ROOT.rglob("*"))
        if ".run" not in path.parts
        if path.is_file() and path.suffix in {".md", ".sh"}
    }
    combined = "\n".join(texts.values())

    forbidden_fragments = [
        'codex exec -C "$REPO_ROOT"',
        "codex exec -C $REPO_ROOT",
        "--add-dir \"$RUN_DIR\"",
        "--add-dir $RUN_DIR",
        "--add-dir \"$ALAB_EXAMPLE_DIR/.run\"",
        "--add-dir \"examples/skydiscover_circle_packing_codex/.run\"",
        "--add-dir \"$SECRET_DIR\"",
        "--add-dir \"$PROJECT_ENV\"",
        "--add-dir \".run/secrets\"",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in combined

    worker_prompts = [path for path in texts if path.endswith("prompts/worker.md")]
    assert worker_prompts
    for path in worker_prompts:
        text = texts[path]
        assert "ALAB_PROJECT_KEY" not in text
        assert "ALAB_ROOT_KEY" not in text
        assert "project admin key" in text

    codex_scripts = [path for path, text in texts.items() if "codex exec" in text]
    assert codex_scripts
    for path in codex_scripts:
        text = texts[path]
        assert "--sandbox workspace-write" in text
        if "worker" in path:
            assert '-C "$WORKTREE_PATH"' in text or '-C "<worktree>"' in text


def test_readme_repository_structure_trees_are_synchronized_and_existing() -> None:
    readme_paths = _readme_repository_tree_paths(_README_PATH)
    readme_cn_paths = _readme_repository_tree_paths(_README_CN_PATH)
    missing_paths = [path for path in readme_paths if not (_REPO_ROOT / path).exists()]

    assert readme_paths
    assert readme_cn_paths == readme_paths
    assert missing_paths == []


def test_local_agent_notes_and_env_files_are_gitignored() -> None:
    patterns = _gitignore_patterns()

    assert list(_REQUIRED_GITIGNORE_PATTERNS) == [pattern for pattern in patterns if pattern in _REQUIRED_GITIGNORE_PATTERNS]
    assert ".env.example" not in patterns


def test_env_example_documents_setup_environment_variables() -> None:
    keys = _env_example_keys()
    readme_env = _readme_environment_assignment_names(_README_PATH)
    readme_cn_env = _readme_environment_assignment_names(_README_CN_PATH)

    assert _ENV_EXAMPLE_PATH.is_file()
    assert len(keys) == len(set(keys))
    assert _REQUIRED_ENV_EXAMPLE_KEYS <= set(keys)
    assert readme_env == readme_cn_env
    assert readme_env <= set(keys)


def test_runtime_stack_and_entrypoint_follow_blueprint_contract(tmp_path: Path) -> None:
    pyproject = tomllib.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))
    runtime_roots = _pyproject_dependency_roots()
    import_roots = _runtime_import_roots()
    required_runtime_roots = {"typer", "rich", "pydantic", "tomli_w", "pathspec"}

    assert pyproject["project"]["name"] == "alab-cli"
    assert pyproject["project"]["requires-python"] == ">=3.11"
    assert pyproject["project"]["scripts"] == {"alab": "alab.cli:main"}
    assert pyproject["tool"]["uv"]["package"] is True
    assert pyproject["tool"]["ruff"]["target-version"] == "py311"
    assert required_runtime_roots <= runtime_roots
    assert not {"pytest", "ruff"} & runtime_roots
    assert {"typer", "sqlite3", "pydantic"} <= import_roots
    assert "import tomli_w" in (_SRC_ROOT / "configs.py").read_text(encoding="utf-8")
    assert "import pathspec" in (_SRC_ROOT / "source_import.py").read_text(encoding="utf-8")

    runner = CliRunner()
    no_args = runner.invoke(cli.app, [])
    help_result = runner.invoke(cli.app, ["--help"])
    config_result = runner.invoke(cli.app, ["--home", str(tmp_path / "home"), "config", "show"])
    unknown_result = runner.invoke(cli.app, ["not-a-command"])

    assert no_args.exit_code == 0
    assert help_result.exit_code == 0
    assert config_result.exit_code == 0
    assert unknown_result.exit_code == 4
    assert "object: help" in no_args.stdout
    assert "object: help" in help_result.stdout
    assert "object: config" in config_result.stdout
    assert "object: error" in unknown_result.stderr
    assert "error code: COMMAND_UNAVAILABLE" in unknown_result.stderr
    assert "Usage:" not in no_args.stdout
    assert "Usage:" not in help_result.stdout


def test_host_support_policy_and_opt_in_runner_gates_are_documented() -> None:
    blueprint = (_REPO_ROOT / "docs" / "blueprint.md").read_text(encoding="utf-8")
    blueprint_cn = (_REPO_ROOT / "docs" / "blueprint_cn.md").read_text(encoding="utf-8")
    readme = _README_PATH.read_text(encoding="utf-8")
    readme_cn = _README_CN_PATH.read_text(encoding="utf-8")
    pyproject = tomllib.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))
    marker_names = {
        marker.split(":", 1)[0]
        for marker in pyproject["tool"]["pytest"]["ini_options"]["markers"]
    }

    assert sys.platform.startswith(("darwin", "linux"))
    assert "Supported hosts are macOS and Linux" in blueprint
    assert "Windows is not part of V1 acceptance testing" in blueprint
    assert "Windows host support" in blueprint
    assert "支持 host 为 macOS 和 Linux" in blueprint_cn
    assert "Windows 不进入 V1 acceptance testing" in blueprint_cn
    assert "ALAB_RUN_REAL_DOCKER=1" in readme
    assert "ALAB_RUN_REAL_DOCKER=1" in readme_cn
    assert "ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1" in readme
    assert "ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1" in readme
    assert {
        "real_docker",
        "real_skydiscover_python",
        "networked_skydiscover_python",
        "native_skydiscover_python",
        "live_skydiscover_catalog",
    } <= marker_names


def test_runtime_surface_stays_local_cli_without_server_orm_or_agent_dependencies() -> None:
    dependency_roots = _pyproject_dependency_roots()
    import_roots = _runtime_import_roots()

    assert sorted(dependency_roots & _BANNED_RUNTIME_DEPENDENCY_ROOTS) == []
    assert sorted(import_roots & _BANNED_RUNTIME_DEPENDENCY_ROOTS) == []


def test_v1_security_boundary_excludes_encryption_grants_and_rewrap_artifacts() -> None:
    dependency_roots = _pyproject_dependency_roots()
    import_roots = _runtime_import_roots()
    implementation_violations: list[str] = []

    for path in _implementation_security_boundary_files():
        relative = path.relative_to(_REPO_ROOT)
        text = path.read_text(encoding="utf-8").lower()
        for pattern in _BANNED_SECURITY_SOURCE_PATTERNS:
            if re.search(pattern, text):
                implementation_violations.append(f"{relative}: {pattern}")

    blueprint = (_REPO_ROOT / "docs" / "blueprint.md").read_text(encoding="utf-8")
    blueprint_cn = (_REPO_ROOT / "docs" / "blueprint_cn.md").read_text(encoding="utf-8")
    readme = _README_PATH.read_text(encoding="utf-8")
    readme_cn = _README_CN_PATH.read_text(encoding="utf-8")

    assert sorted(dependency_roots & _BANNED_SECURITY_DEPENDENCY_ROOTS) == []
    assert sorted(import_roots & _BANNED_SECURITY_DEPENDENCY_ROOTS) == []
    assert implementation_violations == []
    assert "Encrypted SQLite, encrypted record/blob storage" in blueprint
    assert "grant files, public grants, token rewrapping" in blueprint
    assert "Project data, task text, logs" in blueprint and "plaintext" in blueprint
    assert "Collaboration boundary, not strong local security" in readme
    assert "Secret hygiene: raw keys/tokens are not stored" in readme
    assert "加密 SQLite" in blueprint_cn and "token rewrap" in blueprint_cn
    assert "协作边界，不是本地强安全隔离" in readme_cn


def test_dry_run_force_confirm_remove_handlers_use_mixed_mode_guard() -> None:
    gaps = [
        function_name
        for function_name, function in inspect.getmembers(services, inspect.isfunction)
        if "require_force_confirm" in _called_names(function)
        and '"--dry-run"' in inspect.getsource(function)
        and "require_dry_run_unforced" not in _called_names(function)
    ]
    assert gaps == []
