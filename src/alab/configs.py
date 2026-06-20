from __future__ import annotations

import hashlib
import math
import os
import re
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .db import canonical_json, contract_json_obj
from .docker_platform import normalize_docker_platform
from .errors import AlabError
from .ids import require_complete_id

ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
METRIC_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
GLOBAL_CONFIG_INT_FIELDS = {
    "output.preview_bytes",
    "storage.busy_timeout_ms",
    "locks.acquire_timeout_ms",
    "locks.heartbeat_interval_ms",
    "locks.stale_after_ms",
}
GLOBAL_CONFIG_ALLOWED_TOP_LEVEL_KEYS = {"schema_version", "output", "storage", "locks"}
GLOBAL_CONFIG_ALLOWED_SECTION_KEYS = {
    "output": {"format", "preview_bytes"},
    "storage": {"busy_timeout_ms"},
    "locks": {"acquire_timeout_ms", "heartbeat_interval_ms", "stale_after_ms"},
}
PROJECT_CONFIG_JSON_KEYS = {
    "schema_version",
    "project",
    "source",
    "public_source_import",
    "mutable",
    "visibility",
    "metrics",
    "runner",
    "reward",
    "artifacts",
    "logs",
    "git",
    "env",
    "secret_env",
}
SECRET_ENV_MARKER_KEYS = {"secret_value_id", "fingerprint"}
SECRET_ENV_INPUT_MARKER_KEYS = {"retain", "fingerprint"}


def _validate_relative_runtime_path(value: str, label: str, *, escape_target: str) -> None:
    if not value:
        raise ValueError(f"{label} is required")
    if "\0" in value:
        raise ValueError(f"{label} contains NUL")
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or WINDOWS_ABSOLUTE_RE.match(value):
        raise ValueError(f"{label} must be relative")
    parts: list[str] = []
    for part in PurePosixPath(normalized).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError(f"{label} escapes {escape_target}")
            parts.pop()
        else:
            parts.append(part)


def _validate_rooted_runtime_path(value: str, label: str, *, roots: set[str], default_root: str | None = None) -> None:
    root, sep, rel = value.partition(":")
    if sep == ":":
        if root not in roots:
            raise ValueError(f"{label} root must be one of {', '.join(sorted(roots))}")
        if not rel:
            raise ValueError(f"{label} path is required")
    else:
        if default_root is None:
            raise ValueError(f"{label} must be rooted at {' or '.join(sorted(roots))}")
        rel = value
    _validate_relative_runtime_path(rel, label, escape_target="root")


def _validate_positive_integer(value: Any, label: str) -> Any:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _validate_non_negative_integer(value: Any, label: str) -> Any:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _validate_integer_range(value: Any, label: str, *, minimum: int, maximum: int) -> Any:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def _validate_positive_number(value: Any, label: str) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value <= 0:
        raise ValueError(f"{label} must be a positive finite number")
    return value


def _validate_boolean(value: Any, label: str) -> Any:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _validate_pattern_list(value: list[str], label: str, *, allow_empty: bool) -> list[str]:
    if not value and not allow_empty:
        raise ValueError(f"{label} must contain at least one pattern")
    for pattern in value:
        if not pattern or "\n" in pattern or "\0" in pattern:
            raise ValueError(f"{label} patterns must be non-empty single-line values")
    return value


def _validate_secret_env_value(name: str, value: Any) -> None:
    if isinstance(value, str):
        if "\n" in value or "\0" in value or len(value.encode("utf-8")) < 4:
            raise ValueError("secret_env values must be single-line UTF-8 strings at least 4 bytes")
        return
    if not isinstance(value, dict):
        raise ValueError("secret_env entries must be strings or retain marker objects")
    unknown = sorted(set(value) - (SECRET_ENV_MARKER_KEYS | SECRET_ENV_INPUT_MARKER_KEYS))
    if unknown:
        raise ValueError(f"secret_env.{name} contains unknown marker keys: {', '.join(unknown)}")
    if "retain" in value and value["retain"] is not True:
        raise ValueError(f"secret_env.{name}.retain must be true")
    if "fingerprint" in value and (not isinstance(value["fingerprint"], str) or not value["fingerprint"].startswith("hmac-sha256:")):
        raise ValueError(f"secret_env.{name}.fingerprint must be an HMAC string")
    if "secret_value_id" in value and (not isinstance(value["secret_value_id"], str) or not value["secret_value_id"]):
        raise ValueError(f"secret_env.{name}.secret_value_id must be a non-empty string")
    if value.get("retain") is not True and "secret_value_id" not in value:
        raise ValueError(f"secret_env.{name} marker must set retain = true")


class ProjectSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    task: str
    goal: str | None = None
    allow_public_exp_create: bool = True

    @field_validator("allow_public_exp_create", mode="before")
    @classmethod
    def check_allow_public_exp_create(cls, value: Any) -> Any:
        return _validate_boolean(value, "project.allow_public_exp_create")


class SourceSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_source_ref: str | None = None


class PublicSourceImportSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    max_files: int = 100000
    max_total_bytes: int = 1073741824
    max_file_bytes: int = 104857600

    @field_validator("enabled", mode="before")
    @classmethod
    def check_enabled(cls, value: Any) -> Any:
        return _validate_boolean(value, "public_source_import.enabled")

    @field_validator("max_files", "max_total_bytes", "max_file_bytes", mode="before")
    @classmethod
    def check_limits(cls, value: Any, info: Any) -> Any:
        return _validate_non_negative_integer(value, f"public_source_import.{info.field_name}")


class MutableSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include: list[str] = Field(default_factory=lambda: ["**"])
    exclude: list[str] = Field(default_factory=list)

    @field_validator("include")
    @classmethod
    def check_include(cls, value: list[str]) -> list[str]:
        return _validate_pattern_list(value, "mutable.include", allow_empty=False)

    @field_validator("exclude")
    @classmethod
    def check_exclude(cls, value: list[str]) -> list[str]:
        return _validate_pattern_list(value, "mutable.exclude", allow_empty=True)


class VisibilitySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["none", "same_project", "explicit"] = "same_project"
    experiment_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_explicit(self) -> VisibilitySection:
        if self.scope == "explicit" and not self.experiment_ids:
            raise ValueError("visibility.experiment_ids is required for explicit scope")
        if self.scope != "explicit" and self.experiment_ids:
            raise ValueError("visibility.experiment_ids is only valid for explicit scope")
        for exp_id in self.experiment_ids:
            try:
                require_complete_id(exp_id, "exp")
            except AlabError as exc:
                raise ValueError("visibility.experiment_ids entries must be complete experiment ids") from exc
        self.experiment_ids = sorted(set(self.experiment_ids))
        return self


class RunnerSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["none", "local", "docker", "harbor", "skydiscover_docker", "skydiscover_python"] = "local"
    timeout_seconds: int = 600
    working_directory: str = "."
    env_mode: Literal["sanitized", "full", "none"] = "sanitized"
    command: list[str] | None = None
    shell: str | None = None
    image: str | None = None
    dockerfile: str | None = None
    context: str | None = None
    network: Literal["default", "none"] = "default"
    build_args: dict[str, str] = Field(default_factory=dict)
    target: str | None = None
    platform: str | None = None
    user: str | None = None
    cpus: float | None = None
    memory_mb: int | None = None
    harbor_task_ref: str | None = None
    skydiscover_task_ref: str | None = None
    program_path: str = "."

    @field_validator("timeout_seconds", mode="before")
    @classmethod
    def check_timeout(cls, value: Any) -> Any:
        return _validate_integer_range(value, "runner.timeout_seconds", minimum=1, maximum=86400)

    @field_validator("platform")
    @classmethod
    def canonicalize_platform(cls, value: str | None) -> str | None:
        normalized = normalize_docker_platform(value)
        if normalized and normalized not in {"linux", "linux/amd64", "linux/arm64"}:
            raise ValueError("runner.platform must be linux, linux/amd64, or linux/arm64")
        return normalized

    @field_validator("cpus", mode="before")
    @classmethod
    def check_cpus(cls, value: Any) -> Any:
        if value is None:
            return None
        return _validate_positive_number(value, "runner.cpus")

    @field_validator("memory_mb", mode="before")
    @classmethod
    def check_memory(cls, value: Any) -> Any:
        if value is None:
            return None
        return _validate_positive_integer(value, "runner.memory_mb")

    @field_validator("command")
    @classmethod
    def check_command(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("runner.command must not be empty")
        if any(arg == "" for arg in value):
            raise ValueError("runner.command entries must be non-empty strings")
        return value

    @field_validator("shell")
    @classmethod
    def check_shell(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("runner.shell must not be empty")
        return value

    @model_validator(mode="after")
    def check_runner(self) -> RunnerSection:
        _validate_relative_runtime_path(self.working_directory, "runner.working_directory", escape_target="repository")
        _validate_relative_runtime_path(self.program_path, "runner.program_path", escape_target="repository")
        if self.command and self.shell:
            raise ValueError("runner.command conflicts with runner.shell")
        if self.type == "none":
            disallowed = {
                "runner.timeout_seconds": self.timeout_seconds != 600,
                "runner.working_directory": self.working_directory != ".",
                "runner.env_mode": self.env_mode != "sanitized",
                "runner.command": self.command is not None,
                "runner.shell": self.shell is not None,
                "runner.image": self.image is not None,
                "runner.dockerfile": self.dockerfile is not None,
                "runner.context": self.context is not None,
                "runner.network": self.network != "default",
                "runner.build_args": bool(self.build_args),
                "runner.target": self.target is not None,
                "runner.platform": self.platform is not None,
                "runner.user": self.user is not None,
                "runner.cpus": self.cpus is not None,
                "runner.memory_mb": self.memory_mb is not None,
                "runner.harbor_task_ref": self.harbor_task_ref is not None,
                "runner.skydiscover_task_ref": self.skydiscover_task_ref is not None,
                "runner.program_path": self.program_path != ".",
            }
            invalid = [field for field, present in disallowed.items() if present]
            if invalid:
                raise ValueError(f"runner.type none does not accept executable runner fields: {', '.join(sorted(invalid))}")
        if self.type in {"harbor", "skydiscover_docker", "skydiscover_python"} and self.shell:
            raise ValueError("runner.shell is not valid for adapter runners")
        if self.type == "docker":
            if bool(self.image) == bool(self.dockerfile):
                raise ValueError("docker runner requires exactly one of runner.image or runner.dockerfile")
            if self.dockerfile and not self.context:
                raise ValueError("dockerfile runner requires runner.context")
        if self.dockerfile:
            _validate_relative_runtime_path(self.dockerfile, "runner.dockerfile", escape_target="repository")
        if self.context:
            _validate_relative_runtime_path(self.context, "runner.context", escape_target="repository")
        if self.type == "harbor" and not self.harbor_task_ref:
            raise ValueError("harbor runner requires runner.harbor_task_ref")
        if self.type.startswith("skydiscover") and not self.skydiscover_task_ref:
            raise ValueError("skydiscover runner requires runner.skydiscover_task_ref")
        return self


class RewardSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["none", "exit_code", "file", "stdout_regex", "harbor", "skydiscover"]
    direction: Literal["maximize", "minimize"] = "maximize"
    primary_metric: str = "reward"
    path: str | None = None
    pattern: str | None = None

    @model_validator(mode="after")
    def check_reward(self) -> RewardSection:
        if self.type == "none":
            if self.path:
                raise ValueError("reward.path is not valid when reward.type is none")
            if self.pattern:
                raise ValueError("reward.pattern is not valid when reward.type is none")
        if self.type == "exit_code" and self.direction != "maximize":
            raise ValueError("exit_code reward requires maximize direction")
        if self.type == "file" and not self.path:
            raise ValueError("file reward requires reward.path")
        if self.type == "file" and self.path:
            _validate_rooted_runtime_path(self.path, "reward.path", roots={"workspace", "run"})
        if self.type == "stdout_regex" and not self.pattern:
            raise ValueError("stdout_regex reward requires reward.pattern")
        if self.type == "stdout_regex" and self.pattern:
            try:
                compiled = re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"reward.pattern is invalid: {exc}") from exc
            if "reward" not in compiled.groupindex and compiled.groups < 1:
                raise ValueError("stdout_regex reward requires a named reward group or a capture group")
        return self


class ReferenceMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str | None = None
    direction: Literal["maximize", "minimize"] = "maximize"
    unit: str | None = None

    @model_validator(mode="after")
    def check_metric(self) -> ReferenceMetric:
        if not METRIC_NAME_RE.match(self.name):
            raise ValueError("metrics.reference.name must match ^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$")
        for field_name, value in (("label", self.label), ("unit", self.unit)):
            if value is not None and (not value.strip() or "\n" in value or "\0" in value):
                raise ValueError(f"metrics.reference.{field_name} must be a non-empty single-line string")
        return self


class MetricsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: list[ReferenceMetric] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_reference(self) -> MetricsSection:
        seen: set[str] = set()
        for metric in self.reference:
            if metric.name in seen:
                raise ValueError(f"metrics.reference contains duplicate metric name: {metric.name}")
            seen.add(metric.name)
        return self


class ArtifactsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    globs: list[str] = Field(default_factory=list)
    per_file_limit_bytes: int = 10485760
    per_run_limit_bytes: int = 104857600

    @field_validator("per_file_limit_bytes", "per_run_limit_bytes", mode="before")
    @classmethod
    def check_artifact_limits(cls, value: Any, info: Any) -> Any:
        return _validate_positive_integer(value, f"artifacts.{info.field_name}")

    @model_validator(mode="after")
    def check_artifacts(self) -> ArtifactsSection:
        for index, pattern in enumerate(self.globs):
            _validate_rooted_runtime_path(pattern, f"artifacts.globs[{index}]", roots={"workspace", "run"}, default_root="workspace")
        return self


class LogsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stdout_limit_bytes: int = 10485760
    stderr_limit_bytes: int = 10485760

    @field_validator("stdout_limit_bytes", "stderr_limit_bytes", mode="before")
    @classmethod
    def check_log_limits(cls, value: Any, info: Any) -> Any:
        return _validate_positive_integer(value, f"logs.{info.field_name}")


class GitSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author_name: str = "ALab"
    author_email: str = "alab@local"


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    project: ProjectSection
    source: SourceSection = Field(default_factory=SourceSection)
    public_source_import: PublicSourceImportSection = Field(default_factory=PublicSourceImportSection)
    mutable: MutableSection = Field(default_factory=MutableSection)
    visibility: VisibilitySection = Field(default_factory=VisibilitySection)
    metrics: MetricsSection = Field(default_factory=MetricsSection)
    runner: RunnerSection
    reward: RewardSection
    artifacts: ArtifactsSection = Field(default_factory=ArtifactsSection)
    logs: LogsSection = Field(default_factory=LogsSection)
    git: GitSection = Field(default_factory=GitSection)
    env: dict[str, str] = Field(default_factory=dict)
    secret_env: dict[str, Any] = Field(default_factory=dict)

    @field_validator("env", "secret_env")
    @classmethod
    def check_env_names(cls, value: dict[str, Any]) -> dict[str, Any]:
        for name in value:
            if not ENV_NAME_RE.match(name):
                raise ValueError(f"invalid environment variable name: {name}")
        return value

    @field_validator("secret_env")
    @classmethod
    def check_secret_env_values(cls, value: dict[str, Any]) -> dict[str, Any]:
        for name, secret_value in value.items():
            _validate_secret_env_value(name, secret_value)
        return value

    @model_validator(mode="after")
    def check_free_evaluation_pairing(self) -> ProjectConfig:
        runner_none = self.runner.type == "none"
        reward_none = self.reward.type == "none"
        if runner_none != reward_none:
            raise ValueError("runner.type none and reward.type none must be configured together")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def project_config_json_obj(text: str) -> dict[str, Any]:
    config_json = contract_json_obj(
        text,
        label="project_config_versions.canonical_config_json",
        allowed_keys=PROJECT_CONFIG_JSON_KEYS,
        required_keys=PROJECT_CONFIG_JSON_KEYS - {"schema_version", "metrics"},
    )
    env = config_json["env"]
    if not isinstance(env, dict) or not all(isinstance(name, str) and isinstance(value, str) for name, value in env.items()):
        raise AlabError("STORAGE_ERROR", "project_config_versions.canonical_config_json env must be a string map")
    secret_env = config_json["secret_env"]
    if not isinstance(secret_env, dict):
        raise AlabError("STORAGE_ERROR", "project_config_versions.canonical_config_json secret_env must be a JSON object")
    for name, marker in secret_env.items():
        if not isinstance(name, str) or not ENV_NAME_RE.match(name):
            raise AlabError("STORAGE_ERROR", "project_config_versions.canonical_config_json secret_env names must be valid environment names")
        if not isinstance(marker, dict):
            raise AlabError("STORAGE_ERROR", "project_config_versions.canonical_config_json secret_env entries must be stored secret marker objects")
        unknown = sorted(set(marker) - SECRET_ENV_MARKER_KEYS)
        missing = sorted(SECRET_ENV_MARKER_KEYS - set(marker))
        if missing:
            raise AlabError("STORAGE_ERROR", f"project_config_versions.canonical_config_json secret_env.{name} missing JSON keys: {', '.join(missing)}")
        if unknown:
            raise AlabError("STORAGE_ERROR", f"project_config_versions.canonical_config_json secret_env.{name} contains unknown JSON keys: {', '.join(unknown)}")
        if not isinstance(marker["secret_value_id"], str) or not marker["secret_value_id"]:
            raise AlabError("STORAGE_ERROR", "project_config_versions.canonical_config_json secret_env secret_value_id must be a non-empty string")
        if not isinstance(marker["fingerprint"], str) or not marker["fingerprint"].startswith("hmac-sha256:"):
            raise AlabError("STORAGE_ERROR", "project_config_versions.canonical_config_json secret_env fingerprint must be an HMAC string")
    try:
        config = ProjectConfig.model_validate(config_json)
    except Exception as exc:
        raise AlabError("STORAGE_ERROR", f"project_config_versions.canonical_config_json is invalid: {exc}") from exc
    return config.canonical_dict()


def load_project_config(path: Path) -> ProjectConfig:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AlabError("CONFIG_INVALID", f"config file not found: {path}") from exc
    except IsADirectoryError as exc:
        raise AlabError("CONFIG_INVALID", f"config file is a directory: {path}") from exc
    except UnicodeDecodeError as exc:
        raise AlabError("CONFIG_INVALID", f"config file must be UTF-8: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise AlabError("CONFIG_INVALID", f"invalid TOML: {exc}") from exc
    except OSError as exc:
        reason = exc.strerror or str(exc)
        raise AlabError("CONFIG_INVALID", f"config file cannot be read: {reason}") from exc
    try:
        config = ProjectConfig.model_validate(data)
    except Exception as exc:
        raise AlabError("CONFIG_INVALID", str(exc)) from exc
    for name, value in config.secret_env.items():
        if isinstance(value, dict) and value.get("secret_value_id"):
            raise AlabError("CONFIG_INVALID", f"secret_env.{name} import marker must use retain = true")
    return config


def config_hash(config: ProjectConfig | dict[str, Any]) -> str:
    data = config.canonical_dict() if isinstance(config, ProjectConfig) else config
    digest = hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def is_free_evaluation_config(config: ProjectConfig | dict[str, Any]) -> bool:
    if isinstance(config, ProjectConfig):
        return config.runner.type == "none" and config.reward.type == "none"
    return (config.get("runner") or {}).get("type") == "none" and (config.get("reward") or {}).get("type") == "none"


def write_project_config(path: Path, config_json: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_toml(config_json), encoding="utf-8")


def load_global_config(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "schema_version": 1,
            "output": {"format": "text", "preview_bytes": 4096},
            "storage": {"busy_timeout_ms": 5000},
            "locks": {
                "acquire_timeout_ms": 30000,
                "heartbeat_interval_ms": 5000,
                "stale_after_ms": 120000,
            },
        }
    except tomllib.TOMLDecodeError as exc:
        raise AlabError("CONFIG_INVALID", f"invalid global config: {exc}", "alab config reset --all") from exc
    validate_global_config_data(data)
    return data


def validate_global_config_data(data: dict[str, Any]) -> None:
    unknown_top_level = sorted(set(data) - GLOBAL_CONFIG_ALLOWED_TOP_LEVEL_KEYS)
    if unknown_top_level:
        raise AlabError("CONFIG_INVALID", f"global config contains unknown keys: {', '.join(unknown_top_level)}")
    schema_version = data.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 1:
        raise AlabError("CONFIG_INVALID", "global config schema_version must be 1")
    for section, allowed_keys in GLOBAL_CONFIG_ALLOWED_SECTION_KEYS.items():
        value = data.get(section, {})
        if not isinstance(value, dict):
            raise AlabError("CONFIG_INVALID", f"{section} must be a table")
        unknown = sorted(set(value) - allowed_keys)
        if unknown:
            raise AlabError("CONFIG_INVALID", f"{section} contains unknown keys: {', '.join(unknown)}")
    if data.get("output", {}).get("format", "text") != "text":
        raise AlabError("CONFIG_INVALID", 'output.format may only be "text"')
    for field in GLOBAL_CONFIG_INT_FIELDS:
        value = _nested_value(data, field)
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise AlabError("CONFIG_INVALID", f"{field} must be a positive integer")


def _nested_value(data: dict[str, Any], field: str) -> Any:
    current: Any = data
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def set_nested_toml_value(data: dict[str, Any], field: str, value_literal: str) -> dict[str, Any]:
    try:
        parsed = tomllib.loads("value = " + value_literal)["value"]
    except tomllib.TOMLDecodeError as exc:
        raise AlabError("CONFIG_INVALID", f"invalid TOML literal: {exc}") from exc
    parts = field.split(".")
    if not parts or any(not part for part in parts):
        raise AlabError("CONFIG_INVALID", "invalid dotted field")
    current = data
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = parsed
    return data


def env_with_alab_home(home_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["ALAB_HOME"] = str(home_path)
    return env


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _drop_none(child) for key, child in value.items() if child is not None}
    if isinstance(value, list):
        return [_drop_none(item) for item in value if item is not None]
    return value


def dumps_toml(data: dict[str, Any]) -> str:
    data = _drop_none(data)
    try:
        import tomli_w

        return tomli_w.dumps(data)
    except ModuleNotFoundError:
        lines: list[str] = []
        scalars = {k: v for k, v in data.items() if not isinstance(v, dict)}
        for key, value in scalars.items():
            lines.append(f"{key} = {_toml_value(value)}")
        for section, values in data.items():
            if not isinstance(values, dict):
                continue
            lines.append("")
            lines.append(f"[{section}]")
            for key, value in values.items():
                lines.append(f"{key} = {_toml_value(value)}")
        return "\n".join(lines) + "\n"


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, dict):
        items = ", ".join(f"{key} = {_toml_value(child)}" for key, child in sorted(value.items()))
        return "{ " + items + " }"
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if value is None:
        return '""'
    return json_escape(str(value))


def json_escape(value: str) -> str:
    import json

    return json.dumps(value)
