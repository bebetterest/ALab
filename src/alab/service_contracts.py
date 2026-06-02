from __future__ import annotations

import math
from typing import Any

from .db import contract_json_obj
from .errors import AlabError
from .ids import require_complete_id
from .service_models import (
    ANNOTATION_TARGET_ID_PREFIXES,
    ANNOTATION_TARGET_TYPES,
    AUDIT_METADATA_KEYS,
    AUDIT_OBJECT_TYPES,
    SOURCE_ORIGIN_TYPES,
    VISIBILITY_SCOPES,
)
from .timeutil import parse_rfc3339_utc


def _stored_string_array(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AlabError("STORAGE_ERROR", f"{label} must be a string array")
    return list(value)


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


def _assert_annotation_repo_path(value: Any, *, label: str, code: str) -> None:
    if not isinstance(value, str) or not value:
        raise AlabError(code, f"{label} must be a non-empty string")
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
