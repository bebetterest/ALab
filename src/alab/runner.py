from __future__ import annotations

import fnmatch
import glob
import hashlib
import json
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .configs import ProjectConfig
from .docker_platform import normalize_docker_platform
from .errors import AlabError
from .ids import new_id
from .proc import run_cmd
from .timeutil import utc_now

DOCKER_CAPABILITY_KEYS = (
    "docker.availability",
    "docker.platform.linux",
    "docker.platform.linux/amd64",
    "docker.platform.linux/arm64",
    "docker.resource.cpus",
    "docker.resource.memory",
)
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class RunnerResult:
    status: str
    exit_code: int | None
    reward: float | None
    reward_parse_status: str
    stdout: bytes
    stderr: bytes
    started_at: str
    ended_at: str
    failure_reason: str | None = None
    warning_codes: list[str] | None = None
    cache_metadata: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    adapter_feedback: dict[str, Any] | None = None
    hidden_stdout: bytes = b""
    hidden_stderr: bytes = b""


@dataclass
class HarborTask:
    task_dir: Path
    config: dict[str, Any]
    verifier_mode: str
    image: str | None
    dockerfile: Path | None
    build_context: Path
    test_script: Path
    network: str
    cpus: float | None
    memory_mb: int | None
    env: dict[str, str]


def _redact(data: bytes, secrets: list[str]) -> bytes:
    redacted = data
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret.encode("utf-8"), b"[REDACTED]")
    return redacted


def _effective_env(
    config: ProjectConfig,
    workspace: Path,
    run_dir: Path,
    operation_id: str,
    secrets: dict[str, str],
    *,
    project_id: str = "",
    exp_id: str = "",
    config_version: int | str = "",
    workspace_value: str | None = None,
    run_dir_value: str | None = None,
) -> dict[str, str]:
    if config.runner.env_mode == "full":
        env = dict(os.environ)
    elif config.runner.env_mode == "none":
        env = {}
    else:
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "LANG", "TZ", "TMPDIR"} or k.startswith("LC_")}
        env["HOME"] = str(workspace.parent / "home")
    for key in list(env):
        if key.startswith("ALAB_"):
            env.pop(key, None)
    env.update(config.env)
    env.update(secrets)
    env.update(
        {
            "ALAB_PROJECT_ID": project_id,
            "ALAB_EXP_ID": exp_id,
            "ALAB_RUN_ID": operation_id,
            "ALAB_CONFIG_VERSION": str(config_version),
            "ALAB_WORKSPACE": workspace_value or str(workspace),
            "ALAB_RUN_DIR": run_dir_value or str(run_dir),
        }
    )
    return env


def _terminate_local_process_group(proc: subprocess.Popen[bytes]) -> tuple[bytes, bytes]:
    if hasattr(os, "killpg"):
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        proc.terminate()
    try:
        return proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            proc.kill()
        return proc.communicate()


def run_local_runner(
    *,
    config: ProjectConfig,
    workspace: Path,
    run_dir: Path,
    operation_id: str,
    secrets: dict[str, str],
    project_id: str = "",
    exp_id: str = "",
    config_version: int | str = "",
) -> RunnerResult:
    if config.runner.type != "local":
        return RunnerResult(
            status="error",
            exit_code=None,
            reward=None,
            reward_parse_status="not_attempted",
            stdout=b"",
            stderr=f"runner type {config.runner.type} cannot run through the local runner".encode(),
            started_at=utc_now(),
            ended_at=utc_now(),
            failure_reason="runner type cannot run through the local runner",
        )
    command = config.runner.command
    shell = config.runner.shell
    if not command and not shell:
        raise AlabError("CONFIG_INVALID", "local runner requires runner.command or runner.shell")
    working_dir = _resolve_inside(workspace, config.runner.working_directory, "runner.working_directory")
    if not working_dir.exists():
        return RunnerResult(
            status="error",
            exit_code=None,
            reward=None,
            reward_parse_status="not_attempted",
            stdout=b"",
            stderr=b"runner working directory does not exist",
            started_at=utc_now(),
            ended_at=utc_now(),
            failure_reason="runner working directory does not exist",
        )
    run_dir.mkdir(parents=True, exist_ok=True)
    if config.runner.env_mode == "sanitized":
        (workspace.parent / "home").mkdir(parents=True, exist_ok=True)
    started = utc_now()
    env = _effective_env(
        config,
        workspace,
        run_dir,
        operation_id,
        secrets,
        project_id=project_id,
        exp_id=exp_id,
        config_version=config_version,
    )
    try:
        proc = subprocess.Popen(
            command if command else ["/bin/sh", "-c", shell or ""],
            cwd=working_dir,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        completed_stdout, completed_stderr = proc.communicate(timeout=config.runner.timeout_seconds)
        ended = utc_now()
        stdout = _redact(completed_stdout, list(secrets.values()))
        stderr = _redact(completed_stderr, list(secrets.values()))
        returncode = proc.returncode
        if returncode is None:
            returncode = 1
        reward, parse_status = parse_reward(config, returncode, stdout, workspace, run_dir)
        if returncode == 0 and parse_status == "parsed":
            status = "passed"
        elif returncode == 0:
            status = "error"
        else:
            status = "failed"
        warnings = ["ENV_MODE_FULL_UNREDACTED_HOST_ENV"] if config.runner.env_mode == "full" else []
        if secrets and config.artifacts.globs:
            warnings.append("ARTIFACT_BYTES_NOT_REDACTED")
        return RunnerResult(status, returncode, reward, parse_status, stdout, stderr, started, ended, warning_codes=warnings)
    except subprocess.TimeoutExpired as exc:
        stdout_bytes, stderr_bytes = _terminate_local_process_group(proc)
        stdout = _redact(stdout_bytes or exc.stdout or b"", list(secrets.values()))
        stderr = _redact(stderr_bytes or exc.stderr or b"", list(secrets.values()))
        return RunnerResult("timeout", None, None, "not_attempted", stdout, stderr, started, utc_now(), "runner timed out")


def run_configured_runner(
    *,
    config: ProjectConfig,
    workspace: Path,
    run_dir: Path,
    operation_id: str,
    secrets: dict[str, str],
    project_id: str = "",
    exp_id: str = "",
    config_version: int | str = "",
    hidden_dir: Path | None = None,
    cache_dir: Path | None = None,
    adapter_resolver: Callable[[str], dict[str, str]] | None = None,
) -> RunnerResult:
    if config.runner.type == "local":
        return run_local_runner(
            config=config,
            workspace=workspace,
            run_dir=run_dir,
            operation_id=operation_id,
            secrets=secrets,
            project_id=project_id,
            exp_id=exp_id,
            config_version=config_version,
        )
    if config.runner.type == "docker":
        return run_docker_runner(
            config=config,
            workspace=workspace,
            run_dir=run_dir,
            operation_id=operation_id,
            secrets=secrets,
            project_id=project_id,
            exp_id=exp_id,
            config_version=config_version,
        )
    if config.runner.type == "harbor":
        return run_harbor_runner(
            config=config,
            workspace=workspace,
            run_dir=run_dir,
            operation_id=operation_id,
            secrets=secrets,
            project_id=project_id,
            exp_id=exp_id,
            config_version=config_version,
            hidden_dir=hidden_dir,
            adapter_resolver=adapter_resolver,
        )
    if config.runner.type == "skydiscover_python":
        return run_skydiscover_python_runner(
            config=config,
            workspace=workspace,
            run_dir=run_dir,
            operation_id=operation_id,
            secrets=secrets,
            project_id=project_id,
            exp_id=exp_id,
            config_version=config_version,
            hidden_dir=hidden_dir,
            cache_dir=cache_dir,
            adapter_resolver=adapter_resolver,
        )
    if config.runner.type == "skydiscover_docker":
        return run_skydiscover_docker_runner(
            config=config,
            workspace=workspace,
            run_dir=run_dir,
            operation_id=operation_id,
            secrets=secrets,
            project_id=project_id,
            exp_id=exp_id,
            config_version=config_version,
            hidden_dir=hidden_dir,
            adapter_resolver=adapter_resolver,
        )
    return RunnerResult(
        status="error",
        exit_code=None,
        reward=None,
        reward_parse_status="not_attempted",
        stdout=b"",
        stderr=f"runner type {config.runner.type} is not supported".encode(),
        started_at=utc_now(),
        ended_at=utc_now(),
        failure_reason="runner type is not supported",
    )


def _docker_env(
    config: ProjectConfig,
    operation_id: str,
    secrets: dict[str, str],
    project_id: str,
    exp_id: str,
    config_version: int | str,
    *,
    workspace_value: str = "/app",
    run_dir_value: str = "/logs/alab",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    env: dict[str, str] = {}
    env.update(config.env)
    env.update(secrets)
    env.update(
        {
            "ALAB_PROJECT_ID": project_id,
            "ALAB_EXP_ID": exp_id,
            "ALAB_RUN_ID": operation_id,
            "ALAB_CONFIG_VERSION": str(config_version),
            "ALAB_WORKSPACE": workspace_value,
            "ALAB_RUN_DIR": run_dir_value,
        }
    )
    if extra:
        env.update(extra)
    return env


def _result_error(reason: str, stdout: bytes = b"", stderr: bytes | None = None, started_at: str | None = None) -> RunnerResult:
    now = utc_now()
    return RunnerResult(
        status="error",
        exit_code=None,
        reward=None,
        reward_parse_status="not_attempted",
        stdout=stdout,
        stderr=stderr if stderr is not None else reason.encode("utf-8"),
        started_at=started_at or now,
        ended_at=now,
        failure_reason=reason,
    )


def _run_docker_cli(args: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["docker", *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _decode_probe(data: bytes | None) -> str:
    return (data or b"").decode("utf-8", errors="replace").strip()


def _docker_probe_command(args: list[str], timeout: int) -> dict[str, Any]:
    try:
        completed = _run_docker_cli(args, timeout=timeout)
    except FileNotFoundError:
        return {"returncode": None, "stdout": "", "stderr": "docker executable not found", "error_code": "DOCKER_NOT_FOUND"}
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "stdout": _decode_probe(exc.stdout),
            "stderr": _decode_probe(exc.stderr),
            "error_code": "DOCKER_PROBE_TIMEOUT",
        }
    return {
        "returncode": completed.returncode,
        "stdout": _decode_probe(completed.stdout),
        "stderr": _decode_probe(completed.stderr),
        "error_code": None,
    }


def _docker_probe_inputs(*, include_help: bool) -> dict[str, Any]:
    checked_at = utc_now()
    version = _docker_probe_command(["version", "--format", "{{json .}}"], 10)
    info = {"returncode": None, "stdout": "", "stderr": "not attempted", "error_code": "DOCKER_PROBE_SKIPPED"}
    help_text = {"returncode": None, "stdout": "", "stderr": "not attempted", "error_code": "DOCKER_PROBE_SKIPPED"}
    buildx = {"returncode": None, "stdout": "", "stderr": "not attempted", "error_code": "DOCKER_PROBE_SKIPPED"}
    if version["returncode"] == 0:
        info = _docker_probe_command(["info", "--format", "{{json .}}"], 10)
        buildx = _docker_probe_command(["buildx", "ls"], 10)
        if include_help:
            help_text = _docker_probe_command(["run", "--help"], 10)
    fingerprint_payload = {
        "schema_version": 1,
        "version_returncode": version["returncode"],
        "version_stdout": version["stdout"],
        "version_stderr": version["stderr"],
        "info_returncode": info["returncode"],
        "info_stdout": info["stdout"],
        "info_stderr": info["stderr"],
        "buildx_returncode": buildx["returncode"],
        "buildx_stdout": buildx["stdout"],
        "buildx_stderr": buildx["stderr"],
    }
    fingerprint = "sha256:" + hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")).hexdigest()
    return {"checked_at": checked_at, "fingerprint": fingerprint, "version": version, "info": info, "help": help_text, "buildx": buildx}


def docker_runtime_fingerprint() -> str:
    return str(_docker_probe_inputs(include_help=False)["fingerprint"])


def _parse_probe_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _docker_error_code(*commands: dict[str, Any]) -> str | None:
    for command in commands:
        if command.get("error_code") and command.get("error_code") != "DOCKER_PROBE_SKIPPED":
            return str(command["error_code"])
        if command.get("returncode") not in (0, None):
            return "DOCKER_PROBE_FAILED"
    return None


def _docker_error_summary(*commands: dict[str, Any]) -> str:
    for command in commands:
        if command.get("stderr"):
            return str(command["stderr"])[:240]
    return "docker probe failed"


def _native_linux_platform(info_json: dict[str, Any]) -> str | None:
    if info_json.get("OSType") != "linux":
        return None
    arch = str(info_json.get("Architecture") or "").lower()
    return normalize_docker_platform(f"linux/{arch}")


def _buildx_platforms(text: str) -> set[str]:
    platforms: set[str] = set()
    for match in re.findall(r"\blinux/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?\b", text):
        normalized = normalize_docker_platform(match, collapse_variant=True)
        if normalized:
            platforms.add(normalized)
    return platforms


def _docker_platform_capability(
    *,
    platform: str,
    fingerprint: str,
    checked_at: str,
    availability_supported: bool,
    platform_supported: bool,
    supported_platforms: set[str],
    info_json: dict[str, Any],
    buildx: dict[str, Any],
    availability_details: dict[str, Any],
) -> dict[str, Any]:
    supported = availability_supported and platform_supported and platform in supported_platforms
    buildx_available = buildx.get("returncode") == 0
    details: dict[str, Any] = {
        "schema_version": 1,
        "capability": f"docker.platform.{platform}",
        "safe_summary": f"{platform} containers supported" if supported else f"{platform} container platform not reported by Docker",
        "probed_values": {
            "ostype": info_json.get("OSType"),
            "architecture": info_json.get("Architecture"),
            "buildx_available": buildx_available,
            "supported_platforms": sorted(supported_platforms),
        },
    }
    if not availability_supported:
        details["error_code"] = availability_details.get("error_code", "DOCKER_UNAVAILABLE")
    elif not buildx_available and platform not in supported_platforms:
        details["error_code"] = _docker_error_code(buildx) or "DOCKER_PLATFORM_NOT_REPORTED"
    status = "supported" if supported else ("error" if not availability_supported else "unsupported")
    return {
        "capability_key": f"docker.platform.{platform}",
        "fingerprint": fingerprint,
        "status": status,
        "details": details,
        "checked_at": checked_at,
    }


def probe_docker_capabilities() -> list[dict[str, Any]]:
    inputs = _docker_probe_inputs(include_help=True)
    fingerprint = str(inputs["fingerprint"])
    checked_at = str(inputs["checked_at"])
    version = inputs["version"]
    info = inputs["info"]
    help_text = inputs["help"]
    buildx = inputs["buildx"]
    info_json = _parse_probe_json(str(info.get("stdout") or ""))
    version_json = _parse_probe_json(str(version.get("stdout") or ""))
    client_version = (version_json.get("Client") or {}).get("Version") if isinstance(version_json.get("Client"), dict) else None
    server_version = (version_json.get("Server") or {}).get("Version") if isinstance(version_json.get("Server"), dict) else None
    probed_values = {
        "client_version": client_version,
        "server_version": server_version,
        "ostype": info_json.get("OSType"),
        "architecture": info_json.get("Architecture"),
        "ncpu": info_json.get("NCPU"),
        "mem_total": info_json.get("MemTotal"),
    }
    availability_supported = version.get("returncode") == 0 and info.get("returncode") == 0
    availability_status = "supported" if availability_supported else "error"
    availability_details: dict[str, Any] = {
        "schema_version": 1,
        "capability": "docker.availability",
        "safe_summary": "docker daemon available" if availability_supported else _docker_error_summary(version, info),
        "probed_values": probed_values,
    }
    if not availability_supported:
        availability_details["error_code"] = _docker_error_code(version, info) or "DOCKER_UNAVAILABLE"

    native_platform = _native_linux_platform(info_json)
    supported_platforms = _buildx_platforms(str(buildx.get("stdout") or ""))
    if native_platform:
        supported_platforms.add(native_platform)
    platform_supported = availability_supported and info_json.get("OSType") == "linux"
    platform_details: dict[str, Any] = {
        "schema_version": 1,
        "capability": "docker.platform.linux",
        "safe_summary": "linux containers supported" if platform_supported else "linux container platform not reported by Docker",
        "probed_values": {"ostype": info_json.get("OSType"), "architecture": info_json.get("Architecture"), "supported_platforms": sorted(supported_platforms)},
    }
    if not availability_supported:
        platform_details["error_code"] = availability_details.get("error_code", "DOCKER_UNAVAILABLE")
    platform_status = "supported" if platform_supported else ("error" if not availability_supported else "unsupported")

    run_help = str(help_text.get("stdout") or "")
    help_available = help_text.get("returncode") == 0
    cpus_supported = availability_supported and help_available and "--cpus" in run_help
    memory_supported = availability_supported and help_available and "--memory" in run_help
    cpus_details: dict[str, Any] = {
        "schema_version": 1,
        "capability": "docker.resource.cpus",
        "safe_summary": "docker run supports --cpus" if cpus_supported else "docker run --cpus support not reported",
        "probed_values": {"flag": "--cpus", "help_available": help_available},
    }
    memory_details: dict[str, Any] = {
        "schema_version": 1,
        "capability": "docker.resource.memory",
        "safe_summary": "docker run supports --memory" if memory_supported else "docker run --memory support not reported",
        "probed_values": {"flag": "--memory", "help_available": help_available},
    }
    if not availability_supported:
        cpus_details["error_code"] = availability_details.get("error_code", "DOCKER_UNAVAILABLE")
        memory_details["error_code"] = availability_details.get("error_code", "DOCKER_UNAVAILABLE")
    elif not help_available:
        code = _docker_error_code(help_text) or "DOCKER_PROBE_FAILED"
        cpus_details["error_code"] = code
        memory_details["error_code"] = code
    cpus_status = "supported" if cpus_supported else ("error" if not availability_supported or not help_available else "unsupported")
    memory_status = "supported" if memory_supported else ("error" if not availability_supported or not help_available else "unsupported")

    return [
        {"capability_key": "docker.availability", "fingerprint": fingerprint, "status": availability_status, "details": availability_details, "checked_at": checked_at},
        {"capability_key": "docker.platform.linux", "fingerprint": fingerprint, "status": platform_status, "details": platform_details, "checked_at": checked_at},
        _docker_platform_capability(
            platform="linux/amd64",
            fingerprint=fingerprint,
            checked_at=checked_at,
            availability_supported=availability_supported,
            platform_supported=platform_supported,
            supported_platforms=supported_platforms,
            info_json=info_json,
            buildx=buildx,
            availability_details=availability_details,
        ),
        _docker_platform_capability(
            platform="linux/arm64",
            fingerprint=fingerprint,
            checked_at=checked_at,
            availability_supported=availability_supported,
            platform_supported=platform_supported,
            supported_platforms=supported_platforms,
            info_json=info_json,
            buildx=buildx,
            availability_details=availability_details,
        ),
        {"capability_key": "docker.resource.cpus", "fingerprint": fingerprint, "status": cpus_status, "details": cpus_details, "checked_at": checked_at},
        {"capability_key": "docker.resource.memory", "fingerprint": fingerprint, "status": memory_status, "details": memory_details, "checked_at": checked_at},
    ]


def prune_docker_image(tag: str) -> tuple[bool, str | None]:
    if not tag.startswith("alab-cache:"):
        return True, None
    try:
        completed = _run_docker_cli(["image", "rm", tag], timeout=120)
    except FileNotFoundError:
        return False, "docker executable not found"
    except subprocess.TimeoutExpired:
        return False, "docker image rm timed out"
    if completed.returncode == 0:
        return True, None
    message = (_decode_probe(completed.stderr) or _decode_probe(completed.stdout) or "docker image rm failed")[:240]
    lowered = message.lower()
    if "no such image" in lowered or "not found" in lowered:
        return True, None
    return False, "docker image rm failed: " + message


def _resolve_inside(root: Path, rel: str | None, label: str) -> Path:
    if not rel:
        raise AlabError("CONFIG_INVALID", f"{label} is required")
    root_resolved = root.resolve()
    path = (root / rel).resolve()
    if path != root_resolved and root_resolved not in path.parents:
        raise AlabError("CONFIG_INVALID", f"{label} escapes workspace")
    return path


def _workspace_relative(workspace: Path, path: Path) -> str:
    try:
        rel = path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError as exc:
        raise AlabError("CONFIG_INVALID", "path escapes workspace") from exc
    return rel


def _load_dockerignore(context: Path):
    ignore_path = context / ".dockerignore"
    lines = ignore_path.read_text(encoding="utf-8").splitlines() if ignore_path.exists() else []
    try:
        import pathspec

        if hasattr(pathspec, "GitIgnoreSpec"):
            return pathspec.GitIgnoreSpec.from_lines(lines), "\n".join(lines)
        return pathspec.PathSpec.from_lines("gitignore", lines), "\n".join(lines)
    except ModuleNotFoundError:
        patterns = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
        return patterns, "\n".join(lines)


def _dockerignore_matches(spec: Any, rel: str) -> bool:
    if hasattr(spec, "match_file"):
        return bool(spec.match_file(rel))
    for pattern in spec:
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(Path(rel).name, pattern):
            return True
    return False


def docker_build_cache_key(config: ProjectConfig, workspace: Path) -> tuple[str, Path, Path]:
    context = _resolve_inside(workspace, config.runner.context, "runner.context")
    dockerfile = _resolve_inside(workspace, config.runner.dockerfile, "runner.dockerfile")
    if not context.is_dir():
        raise AlabError("CONFIG_INVALID", "runner.context does not exist or is not a directory")
    if not dockerfile.is_file():
        raise AlabError("CONFIG_INVALID", "runner.dockerfile does not exist or is not a file")
    spec, dockerignore_text = _load_dockerignore(context)
    hasher = hashlib.sha256()
    hasher.update(b"alab-docker-cache-v1\0")
    hasher.update(_workspace_relative(workspace, dockerfile).encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(dockerfile.read_bytes())
    hasher.update(b"\0dockerignore\0")
    hasher.update(dockerignore_text.encode("utf-8"))
    hasher.update(b"\0settings\0")
    hasher.update(
        json.dumps(
            {
                "build_args": config.runner.build_args,
                "target": config.runner.target,
                "platform": config.runner.platform,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    for path in sorted(context.rglob("*")):
        rel = path.relative_to(context).as_posix()
        if _dockerignore_matches(spec, rel):
            continue
        try:
            stat = path.lstat()
        except OSError:
            continue
        if path.is_symlink():
            hasher.update(b"\0symlink\0")
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(os.readlink(path).encode("utf-8"))
        elif path.is_file():
            hasher.update(b"\0file\0")
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(str(stat.st_mode & 0o777).encode("ascii"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
    return "sha256:" + hasher.hexdigest(), context, dockerfile


def _docker_image_for_config(config: ProjectConfig, workspace: Path) -> tuple[str, dict[str, Any] | None, bytes, bytes]:
    if config.runner.image:
        try:
            inspect = _run_docker_cli(["image", "inspect", config.runner.image], timeout=30)
        except FileNotFoundError as exc:
            raise AlabError("RUNNER_ERROR", "docker executable not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise AlabError("RUNNER_ERROR", "docker image inspect timed out") from exc
        if inspect.returncode == 0:
            return config.runner.image, None, inspect.stdout, inspect.stderr
        try:
            pulled = _run_docker_cli(["pull", config.runner.image], timeout=900)
        except FileNotFoundError as exc:
            raise AlabError("RUNNER_ERROR", "docker executable not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise AlabError("RUNNER_ERROR", "docker pull timed out") from exc
        if pulled.returncode != 0:
            exc = AlabError("RUNNER_ERROR", "docker pull failed")
            exc.stdout_bytes = pulled.stdout
            exc.stderr_bytes = pulled.stderr
            raise exc
        return config.runner.image, None, pulled.stdout, pulled.stderr
    cache_key, context, dockerfile = docker_build_cache_key(config, workspace)
    digest = cache_key.removeprefix("sha256:")
    tag = f"alab-cache:{digest[:48]}"
    inspect = _run_docker_cli(["image", "inspect", tag], timeout=30)
    if inspect.returncode == 0:
        return tag, {"cache_kind": "docker_image", "cache_key": cache_key, "docker_tag": tag, "status": "hit"}, inspect.stdout, inspect.stderr
    build_args = ["build", "-t", tag, "-f", str(dockerfile)]
    if config.runner.platform:
        build_args.extend(["--platform", config.runner.platform])
    if config.runner.target:
        build_args.extend(["--target", config.runner.target])
    for key, value in sorted(config.runner.build_args.items()):
        build_args.extend(["--build-arg", f"{key}={value}"])
    build_args.append(str(context))
    built = _run_docker_cli(build_args, timeout=max(60, config.runner.timeout_seconds))
    if built.returncode != 0:
        exc = AlabError("RUNNER_ERROR", "docker build failed")
        exc.stdout_bytes = built.stdout
        exc.stderr_bytes = built.stderr
        raise exc
    return tag, {"cache_kind": "docker_image", "cache_key": cache_key, "docker_tag": tag, "status": "built"}, built.stdout, built.stderr


def skydiscover_docker_cache_key(config: ProjectConfig, bundle: Path) -> tuple[str, Path, Path]:
    bundle = bundle.resolve()
    dockerfile = bundle / "Dockerfile"
    if not bundle.is_dir():
        raise AlabError("CONFIG_INVALID", "SkyDiscover Docker evaluator bundle is not a directory")
    if not dockerfile.is_file():
        raise AlabError("CONFIG_INVALID", "SkyDiscover Docker evaluator requires Dockerfile")
    if not (bundle / "evaluate.sh").is_file():
        raise AlabError("CONFIG_INVALID", "SkyDiscover Docker evaluator requires evaluate.sh")
    spec, dockerignore_text = _load_dockerignore(bundle)
    hasher = hashlib.sha256()
    hasher.update(b"alab-skydiscover-docker-cache-v1\0")
    hasher.update(b"Dockerfile\0")
    hasher.update(dockerfile.read_bytes())
    hasher.update(b"\0dockerignore\0")
    hasher.update(dockerignore_text.encode("utf-8"))
    hasher.update(b"\0settings\0")
    hasher.update(
        json.dumps(
            {
                "build_args": config.runner.build_args,
                "target": config.runner.target,
                "platform": config.runner.platform,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    for path in sorted(bundle.rglob("*")):
        rel = path.relative_to(bundle).as_posix()
        if _dockerignore_matches(spec, rel):
            continue
        try:
            stat = path.lstat()
        except OSError:
            continue
        if path.is_symlink():
            hasher.update(b"\0symlink\0")
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(os.readlink(path).encode("utf-8"))
        elif path.is_file():
            hasher.update(b"\0file\0")
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(str(stat.st_mode & 0o777).encode("ascii"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
    return "sha256:" + hasher.hexdigest(), bundle, dockerfile


def _skydiscover_docker_image_for_bundle(config: ProjectConfig, bundle: Path) -> tuple[str, dict[str, Any], bytes, bytes]:
    cache_key, context, dockerfile = skydiscover_docker_cache_key(config, bundle)
    digest = cache_key.removeprefix("sha256:")
    tag = f"alab-cache:{digest[:48]}"
    try:
        inspect = _run_docker_cli(["image", "inspect", tag], timeout=30)
    except FileNotFoundError as exc:
        raise AlabError("RUNNER_ERROR", "docker executable not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise AlabError("RUNNER_ERROR", "docker image inspect timed out") from exc
    if inspect.returncode == 0:
        return (
            tag,
            {
                "cache_kind": "docker_image",
                "cache_key": cache_key,
                "docker_tag": tag,
                "status": "hit",
                "adapter": "skydiscover_docker",
            },
            inspect.stdout,
            inspect.stderr,
        )
    build_args = ["build", "-t", tag, "-f", str(dockerfile)]
    if config.runner.platform:
        build_args.extend(["--platform", config.runner.platform])
    if config.runner.target:
        build_args.extend(["--target", config.runner.target])
    for key, value in sorted(config.runner.build_args.items()):
        build_args.extend(["--build-arg", f"{key}={value}"])
    build_args.append(str(context))
    built = _run_docker_cli(build_args, timeout=max(60, config.runner.timeout_seconds))
    if built.returncode != 0:
        exc = AlabError("RUNNER_ERROR", "SkyDiscover Docker evaluator build failed: " + built.stderr.decode("utf-8", errors="replace").strip())
        exc.stdout_bytes = built.stdout
        exc.stderr_bytes = built.stderr
        raise exc
    return (
        tag,
        {
            "cache_kind": "docker_image",
            "cache_key": cache_key,
            "docker_tag": tag,
            "status": "built",
            "adapter": "skydiscover_docker",
        },
        built.stdout,
        built.stderr,
    )


HARBOR_UNSUPPORTED_KEYS = {
    "steps",
    "multi_step",
    "multistep",
    "gpu",
    "gpu_types",
    "storage_mb",
    "mcp",
    "mcp_servers",
    "healthcheck",
    "healthchecks",
    "external_services",
    "compose",
    "docker_compose",
    "host_mounts",
    "mounts",
    "volumes",
    "docker_args",
    "raw_docker_args",
    "extra_docker_args",
    "privileged",
    "devices",
    "scheduling",
    "scheduler",
}
HARBOR_PLACEHOLDER_RE = re.compile(r"\$\{[^}]+\}")


def _read_harbor_toml(task_dir: Path) -> dict[str, Any]:
    task_toml = task_dir / "task.toml"
    if not task_toml.is_file():
        return {}
    try:
        value = tomllib.loads(task_toml.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise AlabError("CONFIG_INVALID", f"invalid Harbor task.toml: {exc}") from exc
    return value if isinstance(value, dict) else {}


def _validate_harbor_value(value: Any, path: str = "") -> None:
    if isinstance(value, str):
        if HARBOR_PLACEHOLDER_RE.search(value):
            raise AlabError("CONFIG_INVALID", "Harbor task placeholder values are not supported")
        lowered = value.lower()
        key = path.rsplit(".", 1)[-1]
        if key in {"os", "operating_system"} and lowered not in {"", "linux"}:
            raise AlabError("CONFIG_INVALID", "Harbor non-Linux tasks are not supported")
        if key == "platform" and lowered and not lowered.startswith("linux"):
            raise AlabError("CONFIG_INVALID", "Harbor non-Linux platforms are not supported")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            lowered = key_text.lower().replace("-", "_")
            if lowered in HARBOR_UNSUPPORTED_KEYS:
                raise AlabError("CONFIG_INVALID", f"unsupported Harbor task field: {key_text}")
            _validate_harbor_value(child, f"{path}.{lowered}" if path else lowered)
        return
    if isinstance(value, list):
        if path.rsplit(".", 1)[-1] == "services" and value:
            raise AlabError("CONFIG_INVALID", "Harbor external services are not supported")
        for index, child in enumerate(value):
            _validate_harbor_value(child, f"{path}[{index}]")


def _harbor_section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise AlabError("CONFIG_INVALID", f"Harbor task {name} section must be a table")
    return value


def _harbor_task_path(task_dir: Path, rel: str | None, label: str) -> Path | None:
    if not rel:
        return None
    pure = Path(rel)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise AlabError("CONFIG_INVALID", f"Harbor {label} path must stay inside the task directory")
    target = (task_dir / pure).resolve()
    task_root = task_dir.resolve()
    if target != task_root and task_root not in target.parents:
        raise AlabError("CONFIG_INVALID", f"Harbor {label} path escapes the task directory")
    return target


def _harbor_number(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise AlabError("CONFIG_INVALID", f"Harbor {label} must be numeric")
    number = float(value)
    if number <= 0 or not math.isfinite(number):
        raise AlabError("CONFIG_INVALID", f"Harbor {label} must be greater than 0")
    return number


def _harbor_int(value: Any, label: str) -> int | None:
    number = _harbor_number(value, label)
    return int(number) if number is not None else None


def _harbor_literal_env(data: dict[str, Any], environment: dict[str, Any]) -> dict[str, str]:
    merged: dict[str, Any] = {}
    for section in (data.get("env"), environment.get("env")):
        if section is None:
            continue
        if not isinstance(section, dict):
            raise AlabError("CONFIG_INVALID", "Harbor env section must be a table")
        merged.update(section)
    env: dict[str, str] = {}
    for key, value in merged.items():
        name = str(key)
        if not ENV_NAME_RE.match(name):
            raise AlabError("CONFIG_INVALID", f"invalid Harbor environment variable name: {name}")
        if isinstance(value, dict | list):
            raise AlabError("CONFIG_INVALID", f"Harbor environment variable {name} must be literal")
        env[name] = str(value)
    return env


def load_harbor_task(task: Path, config: ProjectConfig | None = None) -> HarborTask:
    task_path = task.expanduser().resolve()
    task_dir = task_path.parent if task_path.is_file() and task_path.name == "task.toml" else task_path
    if not task_dir.is_dir():
        raise AlabError("CONFIG_INVALID", "Harbor task path does not exist")
    data = _read_harbor_toml(task_dir)
    _validate_harbor_value(data)
    environment = _harbor_section(data, "environment")
    verifier = _harbor_section(data, "verifier")
    test_script = task_dir / "tests" / "test.sh"
    if not test_script.is_file():
        raise AlabError("CONFIG_INVALID", "Harbor task requires tests/test.sh")
    network = config.runner.network if config else "default"
    if environment.get("allow_internet") is False and network == "default":
        network = "none"
    cpus = config.runner.cpus if config and config.runner.cpus is not None else _harbor_number(environment.get("cpus"), "environment.cpus")
    memory_mb = config.runner.memory_mb if config and config.runner.memory_mb is not None else _harbor_int(environment.get("memory_mb"), "environment.memory_mb")

    verifier_image = verifier.get("image")
    verifier_dockerfile = _harbor_task_path(task_dir, verifier.get("dockerfile"), "verifier.dockerfile")
    tests_dockerfile = task_dir / "tests" / "Dockerfile"
    environment_image = environment.get("image")
    environment_dockerfile = _harbor_task_path(task_dir, environment.get("dockerfile"), "environment.dockerfile") or (task_dir / "environment" / "Dockerfile" if (task_dir / "environment" / "Dockerfile").is_file() else None)
    if verifier_image is not None and not isinstance(verifier_image, str):
        raise AlabError("CONFIG_INVALID", "Harbor verifier.image must be a string")
    if environment_image is not None and not isinstance(environment_image, str):
        raise AlabError("CONFIG_INVALID", "Harbor environment.image must be a string")

    separate = verifier_image is not None or verifier_dockerfile is not None or tests_dockerfile.is_file()
    if separate:
        image = verifier_image
        dockerfile = verifier_dockerfile or (tests_dockerfile if tests_dockerfile.is_file() else None)
        if image and dockerfile:
            raise AlabError("CONFIG_INVALID", "Harbor separate verifier requires exactly one image source")
        if not image and dockerfile is None:
            raise AlabError("CONFIG_INVALID", "Harbor separate verifier requires verifier.image or tests/Dockerfile")
        mode = "separate"
    else:
        image = environment_image
        dockerfile = environment_dockerfile
        if image and dockerfile:
            raise AlabError("CONFIG_INVALID", "Harbor shared verifier requires exactly one environment image source")
        if not image and dockerfile is None:
            raise AlabError("CONFIG_INVALID", "Harbor task requires environment.image or environment/Dockerfile")
        mode = "shared"
    return HarborTask(
        task_dir=task_dir,
        config=data,
        verifier_mode=mode,
        image=image,
        dockerfile=dockerfile,
        build_context=task_dir,
        test_script=test_script,
        network=network,
        cpus=cpus,
        memory_mb=memory_mb,
        env=_harbor_literal_env(data, environment),
    )


def harbor_docker_cache_key(config: ProjectConfig, task: HarborTask) -> tuple[str, Path, Path]:
    if task.dockerfile is None:
        raise AlabError("CONFIG_INVALID", "Harbor Dockerfile cache requires a Dockerfile")
    context = task.build_context.resolve()
    dockerfile = task.dockerfile.resolve()
    if context != dockerfile and context not in dockerfile.parents:
        raise AlabError("CONFIG_INVALID", "Harbor Dockerfile path escapes the task directory")
    spec, dockerignore_text = _load_dockerignore(context)
    hasher = hashlib.sha256()
    hasher.update(b"alab-harbor-docker-cache-v1\0")
    hasher.update(dockerfile.relative_to(context).as_posix().encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(dockerfile.read_bytes())
    hasher.update(b"\0dockerignore\0")
    hasher.update(dockerignore_text.encode("utf-8"))
    hasher.update(b"\0settings\0")
    hasher.update(
        json.dumps(
            {
                "build_args": config.runner.build_args,
                "target": config.runner.target,
                "platform": config.runner.platform,
                "verifier_mode": task.verifier_mode,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    for path in sorted(context.rglob("*")):
        rel = path.relative_to(context).as_posix()
        if _dockerignore_matches(spec, rel):
            continue
        try:
            stat = path.lstat()
        except OSError:
            continue
        if path.is_symlink():
            hasher.update(b"\0symlink\0")
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(os.readlink(path).encode("utf-8"))
        elif path.is_file():
            hasher.update(b"\0file\0")
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(str(stat.st_mode & 0o777).encode("ascii"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
    return "sha256:" + hasher.hexdigest(), context, dockerfile


def _docker_image_for_harbor_task(config: ProjectConfig, task: HarborTask) -> tuple[str, dict[str, Any] | None, bytes, bytes]:
    if task.image:
        try:
            inspect = _run_docker_cli(["image", "inspect", task.image], timeout=30)
        except FileNotFoundError as exc:
            raise AlabError("RUNNER_ERROR", "docker executable not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise AlabError("RUNNER_ERROR", "docker image inspect timed out") from exc
        if inspect.returncode == 0:
            return task.image, None, inspect.stdout, inspect.stderr
        try:
            pulled = _run_docker_cli(["pull", task.image], timeout=900)
        except FileNotFoundError as exc:
            raise AlabError("RUNNER_ERROR", "docker executable not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise AlabError("RUNNER_ERROR", "docker pull timed out") from exc
        if pulled.returncode != 0:
            raise AlabError("RUNNER_ERROR", "docker pull failed: " + pulled.stderr.decode("utf-8", errors="replace").strip())
        return task.image, None, pulled.stdout, pulled.stderr
    cache_key, context, dockerfile = harbor_docker_cache_key(config, task)
    digest = cache_key.removeprefix("sha256:")
    tag = f"alab-cache:{digest[:48]}"
    inspect = _run_docker_cli(["image", "inspect", tag], timeout=30)
    if inspect.returncode == 0:
        return tag, {"cache_kind": "docker_image", "cache_key": cache_key, "docker_tag": tag, "status": "hit", "adapter": "harbor", "verifier_mode": task.verifier_mode}, inspect.stdout, inspect.stderr
    build_args = ["build", "-t", tag, "-f", str(dockerfile)]
    if config.runner.platform:
        build_args.extend(["--platform", config.runner.platform])
    if config.runner.target:
        build_args.extend(["--target", config.runner.target])
    for key, value in sorted(config.runner.build_args.items()):
        build_args.extend(["--build-arg", f"{key}={value}"])
    build_args.append(str(context))
    built = _run_docker_cli(build_args, timeout=max(60, config.runner.timeout_seconds))
    if built.returncode != 0:
        exc = AlabError("RUNNER_ERROR", "Harbor verifier build failed: " + built.stderr.decode("utf-8", errors="replace").strip())
        exc.stdout_bytes = built.stdout
        exc.stderr_bytes = built.stderr
        raise exc
    return tag, {"cache_kind": "docker_image", "cache_key": cache_key, "docker_tag": tag, "status": "built", "adapter": "harbor", "verifier_mode": task.verifier_mode}, built.stdout, built.stderr


def run_docker_runner(
    *,
    config: ProjectConfig,
    workspace: Path,
    run_dir: Path,
    operation_id: str,
    secrets: dict[str, str],
    project_id: str = "",
    exp_id: str = "",
    config_version: int | str = "",
) -> RunnerResult:
    if config.runner.type != "docker":
        return _result_error(f"runner type {config.runner.type} is not docker")
    run_dir.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    try:
        image, cache_metadata, _setup_stdout, _setup_stderr = _docker_image_for_config(config, workspace)
    except AlabError as exc:
        setup_stdout = getattr(exc, "stdout_bytes", b"")
        setup_stderr = getattr(exc, "stderr_bytes", b"")
        stderr = _redact(exc.reason.encode("utf-8"), list(secrets.values()))
        result = _result_error(exc.reason, stderr=stderr, started_at=started)
        result.hidden_stdout = _redact(setup_stdout, list(secrets.values()))
        result.hidden_stderr = _redact(setup_stderr, list(secrets.values()))
        return result
    except FileNotFoundError:
        return _result_error("docker executable not found", started_at=started)
    except subprocess.TimeoutExpired:
        return _result_error("docker command timed out", started_at=started)

    working_dir = _resolve_inside(workspace, config.runner.working_directory, "runner.working_directory")
    container_workdir = "/app" if working_dir == workspace.resolve() else "/app/" + _workspace_relative(workspace, working_dir)
    env = _docker_env(config, operation_id, secrets, project_id, exp_id, config_version)
    container_name = re.sub(r"[^a-zA-Z0-9_.-]", "-", f"alab-{operation_id}")[:63].strip(".-") or "alab-run"
    args = [
        "run",
        "--rm",
        "--name",
        container_name,
        "--workdir",
        container_workdir,
        "-v",
        f"{workspace.resolve()}:/app",
        "-v",
        f"{run_dir.resolve()}:/logs/alab",
    ]
    if config.runner.network == "none":
        args.extend(["--network", "none"])
    if config.runner.platform:
        args.extend(["--platform", config.runner.platform])
    if config.runner.user:
        args.extend(["--user", config.runner.user])
    if config.runner.cpus is not None:
        args.extend(["--cpus", str(config.runner.cpus)])
    if config.runner.memory_mb is not None:
        args.extend(["--memory", f"{config.runner.memory_mb}m"])
    for key, value in sorted(env.items()):
        args.extend(["--env", f"{key}={value}"])
    args.append(image)
    if config.runner.command:
        args.extend(config.runner.command)
    elif config.runner.shell:
        args.extend(["/bin/sh", "-c", config.runner.shell])
    try:
        completed = _run_docker_cli(args, timeout=config.runner.timeout_seconds)
        ended = utc_now()
    except subprocess.TimeoutExpired as exc:
        try:
            _run_docker_cli(["rm", "-f", container_name], timeout=30)
        except Exception:
            pass
        stdout = _redact(exc.stdout or b"", list(secrets.values()))
        stderr = _redact(exc.stderr or b"", list(secrets.values()))
        return RunnerResult(
            "timeout",
            None,
            None,
            "not_attempted",
            stdout,
            stderr,
            started,
            utc_now(),
            "runner timed out",
            cache_metadata=cache_metadata,
            hidden_stdout=_redact(_setup_stdout, list(secrets.values())),
            hidden_stderr=_redact(_setup_stderr, list(secrets.values())),
        )
    except FileNotFoundError:
        return _result_error("docker executable not found", started_at=started)

    stdout = _redact(completed.stdout, list(secrets.values()))
    stderr = _redact(completed.stderr, list(secrets.values()))
    reward, parse_status = parse_reward(config, completed.returncode, stdout, workspace, run_dir)
    if completed.returncode == 0 and parse_status == "parsed":
        status = "passed"
    elif completed.returncode == 0:
        status = "error"
    elif completed.returncode == 125:
        status = "error"
    else:
        status = "failed"
    warnings = []
    if _setup_stdout or _setup_stderr:
        warnings.append("DOCKER_SETUP_OUTPUT_CAPTURED")
    if secrets and config.artifacts.globs:
        warnings.append("ARTIFACT_BYTES_NOT_REDACTED")
    failure = None
    if status == "error" and completed.returncode == 125:
        failure = "docker runner error"
    return RunnerResult(
        status,
        completed.returncode,
        reward,
        parse_status,
        stdout,
        stderr,
        started,
        ended,
        failure,
        warnings,
        cache_metadata,
        hidden_stdout=_redact(_setup_stdout, list(secrets.values())),
        hidden_stderr=_redact(_setup_stderr, list(secrets.values())),
    )


SKYDISCOVER_WRAPPER = r"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import traceback

entry = Path(sys.argv[1]).resolve()
program_path = sys.argv[2]
captured_stdout = io.StringIO()
captured_stderr = io.StringIO()
envelope = {
    "schema_version": 1,
    "ok": False,
    "stdout": "",
    "stderr": "",
    "result": None,
    "error": None,
}
exit_code = 1
try:
    spec = importlib.util.spec_from_file_location("alab_skydiscover_evaluator", entry)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load evaluator module")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(entry.parent))
    with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
        spec.loader.exec_module(module)
        evaluate = getattr(module, "evaluate")
        result = evaluate(program_path)
    json.dumps(result)
    envelope.update({"ok": True, "result": result})
    exit_code = 0
except Exception as exc:
    envelope["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }
finally:
    envelope["stdout"] = captured_stdout.getvalue()
    envelope["stderr"] = captured_stderr.getvalue()

print(json.dumps(envelope, ensure_ascii=False, sort_keys=True))
raise SystemExit(exit_code)
"""


def _copy_skydiscover_bundle(source: Path, bundle_dir: Path) -> Path:
    source = source.resolve()
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        target = bundle_dir / source.name
        shutil.copy2(source, target)
        return target
    if not source.is_dir():
        raise AlabError("CONFIG_INVALID", "SkyDiscover evaluator ref target is not readable")
    for path in sorted(source.rglob("*")):
        resolved = path.resolve()
        if resolved != source and source not in resolved.parents:
            raise AlabError("CONFIG_INVALID", "SkyDiscover evaluator bundle contains a path escaping the catalog")
        rel = path.relative_to(source)
        target = bundle_dir / rel
        if path.is_symlink():
            if resolved.is_dir():
                raise AlabError("CONFIG_INVALID", "SkyDiscover evaluator bundle contains a directory symlink")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, target)
        elif path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return bundle_dir


def _skydiscover_python_entry(bundle: Path, source: Path) -> Path:
    if source.is_file():
        entry = bundle / source.name
        if entry.is_file():
            return entry
    for name in ("evaluator.py", "evaluate.py"):
        entry = bundle / name
        if entry.is_file():
            return entry
    py_files = sorted(path for path in bundle.glob("*.py") if path.is_file())
    if len(py_files) == 1:
        return py_files[0]
    raise AlabError("CONFIG_INVALID", "SkyDiscover Python evaluator entry is ambiguous")


def _skydiscover_dependency_files(bundle: Path) -> tuple[str | None, list[Path]]:
    pyproject = bundle / "pyproject.toml"
    uv_lock = bundle / "uv.lock"
    requirements = bundle / "requirements.txt"
    if pyproject.is_file() or uv_lock.is_file():
        files = [path for path in (pyproject, uv_lock) if path.is_file()]
        return "uv_sync", files
    if requirements.is_file():
        return "requirements", [requirements]
    return None, []


def _skydiscover_python_env_key(bundle: Path) -> tuple[str | None, dict[str, Any]]:
    mode, files = _skydiscover_dependency_files(bundle)
    if mode is None:
        return None, {"schema_version": 1, "dependency_mode": None, "dependency_files": []}
    file_hashes = []
    for path in files:
        file_hashes.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    payload = {
        "schema_version": 1,
        "dependency_mode": mode,
        "dependency_files": file_hashes,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        },
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return "sha256:" + digest, payload


def _uv_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith("ALAB_")}


def _run_uv(args: list[str], *, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["uv", *args], stdin=subprocess.DEVNULL, env=env, capture_output=True, timeout=timeout, check=False)


def _skydiscover_env_error(reason: str, stdout_parts: list[bytes], stderr_parts: list[bytes]) -> AlabError:
    exc = AlabError("RUNNER_ERROR", reason)
    exc.stdout_bytes = b"".join(stdout_parts)
    exc.stderr_bytes = b"".join(stderr_parts)
    return exc


def _prepare_skydiscover_python_env(
    *,
    bundle: Path,
    cache_dir: Path | None,
    timeout_seconds: int,
) -> tuple[Path, dict[str, Any] | None, bytes, bytes]:
    cache_key, key_payload = _skydiscover_python_env_key(bundle)
    if cache_key is None:
        return Path(sys.executable), None, b"", b""
    if cache_dir is None:
        raise AlabError("RUNNER_ERROR", "SkyDiscover Python environment cache directory is unavailable")
    digest = cache_key.removeprefix("sha256:")
    env_dir = cache_dir / digest[:48]
    python_path = env_dir / "bin" / "python"
    metadata = {
        "cache_kind": "skydiscover_python_env",
        "cache_key": cache_key,
        "path": str(env_dir),
        "status": "hit",
        "dependency": key_payload,
    }
    if python_path.is_file():
        return python_path, metadata, b"", b""
    if env_dir.exists():
        shutil.rmtree(env_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    mode, files = _skydiscover_dependency_files(bundle)
    env = _uv_env()
    stdout_parts: list[bytes] = []
    stderr_parts: list[bytes] = []
    try:
        if mode == "uv_sync":
            env["UV_PROJECT_ENVIRONMENT"] = str(env_dir)
            completed = _run_uv(["sync", "--project", str(bundle)], env=env, timeout=max(60, timeout_seconds))
            stdout_parts.append(completed.stdout)
            stderr_parts.append(completed.stderr)
            if completed.returncode != 0:
                raise _skydiscover_env_error("SkyDiscover Python dependency installation failed", stdout_parts, stderr_parts)
        else:
            completed = _run_uv(["venv", str(env_dir)], env=env, timeout=max(60, timeout_seconds))
            stdout_parts.append(completed.stdout)
            stderr_parts.append(completed.stderr)
            if completed.returncode != 0:
                raise _skydiscover_env_error("SkyDiscover Python environment creation failed", stdout_parts, stderr_parts)
            requirements = files[0]
            completed = _run_uv(
                ["pip", "install", "--python", str(python_path), "-r", str(requirements)],
                env=env,
                timeout=max(60, timeout_seconds),
            )
            stdout_parts.append(completed.stdout)
            stderr_parts.append(completed.stderr)
            if completed.returncode != 0:
                raise _skydiscover_env_error("SkyDiscover Python dependency installation failed", stdout_parts, stderr_parts)
    except FileNotFoundError as exc:
        raise AlabError("RUNNER_ERROR", "uv executable not found") from exc
    except subprocess.TimeoutExpired as exc:
        stdout_parts.append(exc.stdout or b"")
        stderr_parts.append(exc.stderr or b"")
        raise _skydiscover_env_error("SkyDiscover Python dependency installation timed out", stdout_parts, stderr_parts) from exc
    if not python_path.is_file():
        raise AlabError("RUNNER_ERROR", "SkyDiscover Python environment did not create a Python executable")
    metadata["status"] = "built"
    return python_path, metadata, b"".join(stdout_parts), b"".join(stderr_parts)


def _split_skydiscover_result(result: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(result, dict) and isinstance(result.get("metrics"), dict):
        feedback = result.get("feedback")
        if not isinstance(feedback, dict):
            feedback = {}
        if "artifacts" in result and "artifacts" not in feedback:
            feedback = {**feedback, "artifacts": result["artifacts"]}
        return dict(result["metrics"]), dict(feedback)
    if isinstance(result, dict):
        feedback = result.get("feedback") if isinstance(result.get("feedback"), dict) else {}
        if "artifacts" in result and "artifacts" not in feedback:
            feedback = {**feedback, "artifacts": result["artifacts"]}
        metrics = {key: value for key, value in result.items() if key not in {"artifacts", "feedback"}}
        return metrics, dict(feedback)
    return {}, {"result": result}


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _reward_metric_map(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    metrics: dict[str, float] = {}
    for key, metric in value.items():
        number = _finite_number(metric)
        if not isinstance(key, str) or number is None:
            return None
        metrics[key] = number
    return metrics


def _parse_text_reward_number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("reward is not finite")
    return number


def _parse_skydiscover_reward(config: ProjectConfig, metrics: dict[str, Any]) -> tuple[float | None, str]:
    primary = config.reward.primary_metric or "combined_score"
    primary_value = _finite_number(metrics.get(primary))
    if primary_value is not None:
        return primary_value, "parsed"
    if primary == "combined_score":
        values = [number for number in (_finite_number(value) for value in metrics.values()) if number is not None]
        if values:
            return sum(values) / len(values), "parsed"
    return None, "missing"


def _skydiscover_visible_stdout(*, ref: str, pinned_commit: str | None, mode: str, metrics: dict[str, Any], reward: float | None) -> bytes:
    lines = [
        f"SkyDiscover {mode.title()} evaluator completed",
        f"task ref: {ref}",
        f"pinned commit: {pinned_commit or 'unknown'}",
        f"evaluator mode: {mode}",
    ]
    if mode == "python":
        lines.append("sandbox: not-os-sandbox")
    lines.extend(
        [
            "metric names: " + (", ".join(sorted(metrics)) if metrics else "none"),
            "reward: " + ("none" if reward is None else str(reward)),
        ]
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _parse_harbor_reward(config: ProjectConfig, run_dir: Path) -> tuple[float | None, str, dict[str, Any]]:
    reward_dir = run_dir / "logs" / "verifier"
    primary = config.reward.primary_metric or "reward"
    reward_json = reward_dir / "reward.json"
    reward_txt = reward_dir / "reward.txt"
    if reward_json.is_file():
        try:
            value = json.loads(reward_json.read_text(encoding="utf-8"))
        except Exception:
            return None, "invalid", {}
        metrics = _reward_metric_map(value)
        if metrics is None:
            return None, "invalid", {}
        if primary not in metrics:
            return None, "missing", metrics
        return metrics[primary], "parsed", metrics
    if reward_txt.is_file():
        try:
            number = float(reward_txt.read_text(encoding="utf-8").strip())
        except Exception:
            return None, "invalid", {}
        if not math.isfinite(number):
            return None, "invalid", {}
        return number, "parsed", {primary: number}
    return None, "missing", {}


def _harbor_visible_stdout(*, ref: str, pinned_commit: str | None, verifier_mode: str, metrics: dict[str, Any], reward: float | None) -> bytes:
    lines = [
        "Harbor verifier completed",
        f"task ref: {ref}",
        f"pinned commit: {pinned_commit or 'none'}",
        f"verifier mode: {verifier_mode}",
        "metric names: " + (", ".join(sorted(metrics)) if metrics else "none"),
        "reward: " + ("none" if reward is None else str(reward)),
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def run_harbor_runner(
    *,
    config: ProjectConfig,
    workspace: Path,
    run_dir: Path,
    operation_id: str,
    secrets: dict[str, str],
    project_id: str = "",
    exp_id: str = "",
    config_version: int | str = "",
    hidden_dir: Path | None = None,
    adapter_resolver: Callable[[str], dict[str, str]] | None = None,
) -> RunnerResult:
    if config.runner.type != "harbor":
        return _result_error(f"runner type {config.runner.type} is not harbor")
    started = utc_now()
    task_ref = config.runner.harbor_task_ref or ""
    if adapter_resolver is None:
        return _result_error("Harbor task resolver is unavailable", started_at=started)
    try:
        resolved = adapter_resolver(task_ref)
        target = Path(resolved["target_path"])
        if resolved.get("target_kind") != "harbor_task":
            raise AlabError("CONFIG_INVALID", "runner.harbor_task_ref must resolve to a Harbor task")
        working_dir = _resolve_inside(workspace, config.runner.working_directory, "runner.working_directory")
    except (AlabError, KeyError) as exc:
        reason = exc.reason if isinstance(exc, AlabError) else "Harbor task resolver returned incomplete data"
        return _result_error(reason, started_at=started)
    if not working_dir.exists():
        return _result_error("runner.working_directory does not exist", started_at=started)
    run_dir.mkdir(parents=True, exist_ok=True)
    hidden_root = hidden_dir or run_dir.parent / "hidden"
    hidden_root.mkdir(parents=True, exist_ok=True)
    setup_stdout = b""
    setup_stderr = b""
    cache_metadata: dict[str, Any] | None = None
    try:
        bundle = hidden_root / "harbor-task"
        _copy_skydiscover_bundle(target, bundle)
        task = load_harbor_task(bundle, config)
        image, cache_metadata, setup_stdout, setup_stderr = _docker_image_for_harbor_task(config, task)
    except AlabError as exc:
        setup_stdout = getattr(exc, "stdout_bytes", setup_stdout)
        setup_stderr = getattr(exc, "stderr_bytes", setup_stderr)
        return RunnerResult(
            "error",
            None,
            None,
            "not_attempted",
            b"",
            exc.reason.encode("utf-8"),
            started,
            utc_now(),
            exc.reason,
            hidden_stdout=_redact(setup_stdout, list(secrets.values())),
            hidden_stderr=_redact(setup_stderr, list(secrets.values())),
        )
    except FileNotFoundError:
        return _result_error("docker executable not found", started_at=started)
    except subprocess.TimeoutExpired:
        return _result_error("docker command timed out", started_at=started)

    harbor_secrets = {**task.env, **secrets}
    env = _docker_env(
        config,
        operation_id,
        harbor_secrets,
        project_id,
        exp_id,
        config_version,
        workspace_value="/workspace",
        run_dir_value="/logs/alab",
        extra={"ALAB_HARBOR_TASK_DIR": "/alab/harbor"},
    )
    container_name = re.sub(r"[^a-zA-Z0-9_.-]", "-", f"alab-{operation_id}")[:63].strip(".-") or "alab-run"
    args = [
        "run",
        "--rm",
        "--name",
        container_name,
        "--workdir",
        "/workspace",
        "-v",
        f"{workspace.resolve()}:/workspace",
        "-v",
        f"{run_dir.resolve()}:/logs/alab",
        "-v",
        f"{bundle.resolve()}:/alab/harbor:ro",
        "--entrypoint",
        "/bin/sh",
    ]
    if task.network == "none":
        args.extend(["--network", "none"])
    if config.runner.platform:
        args.extend(["--platform", config.runner.platform])
    if config.runner.user:
        args.extend(["--user", config.runner.user])
    if task.cpus is not None:
        args.extend(["--cpus", str(task.cpus)])
    if task.memory_mb is not None:
        args.extend(["--memory", f"{task.memory_mb}m"])
    for key, value in sorted(env.items()):
        args.extend(["--env", f"{key}={value}"])
    args.append(image)
    args.append("/alab/harbor/tests/test.sh")
    try:
        completed = _run_docker_cli(args, timeout=config.runner.timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        try:
            _run_docker_cli(["rm", "-f", container_name], timeout=30)
        except Exception:
            pass
        return RunnerResult(
            "timeout",
            None,
            None,
            "not_attempted",
            b"",
            b"Harbor verifier timed out",
            started,
            utc_now(),
            "runner timed out",
            cache_metadata=cache_metadata,
            hidden_stdout=_redact(setup_stdout + (exc.stdout or b""), list(harbor_secrets.values())),
            hidden_stderr=_redact(setup_stderr + (exc.stderr or b""), list(harbor_secrets.values())),
        )
    except FileNotFoundError:
        return _result_error("docker executable not found", started_at=started)

    hidden_stdout = _redact(setup_stdout + completed.stdout, list(harbor_secrets.values()))
    hidden_stderr = _redact(setup_stderr + completed.stderr, list(harbor_secrets.values()))
    reward, parse_status, metrics = _parse_harbor_reward(config, run_dir)
    if completed.returncode == 0 and parse_status == "parsed":
        status = "passed"
    elif completed.returncode == 0:
        status = "error"
    else:
        status = "failed"
    failure = None
    if status == "error" and parse_status == "missing":
        failure = "Harbor reward metric missing"
    elif status == "error" and parse_status == "invalid":
        failure = "Harbor reward metrics invalid"
    stdout = _harbor_visible_stdout(
        ref=task_ref,
        pinned_commit=resolved.get("pinned_commit"),
        verifier_mode=task.verifier_mode,
        metrics=metrics,
        reward=reward,
    )
    return RunnerResult(
        status,
        completed.returncode,
        reward,
        parse_status,
        stdout,
        b"",
        started,
        utc_now(),
        failure,
        cache_metadata=cache_metadata,
        metrics=metrics,
        adapter_feedback={
            "mode": "harbor",
            "task_ref": task_ref,
            "pinned_commit": resolved.get("pinned_commit"),
            "verifier_mode": task.verifier_mode,
        },
        hidden_stdout=hidden_stdout,
        hidden_stderr=hidden_stderr,
    )


def run_skydiscover_docker_runner(
    *,
    config: ProjectConfig,
    workspace: Path,
    run_dir: Path,
    operation_id: str,
    secrets: dict[str, str],
    project_id: str = "",
    exp_id: str = "",
    config_version: int | str = "",
    hidden_dir: Path | None = None,
    adapter_resolver: Callable[[str], dict[str, str]] | None = None,
) -> RunnerResult:
    if config.runner.type != "skydiscover_docker":
        return _result_error(f"runner type {config.runner.type} is not skydiscover_docker")
    started = utc_now()
    task_ref = config.runner.skydiscover_task_ref or ""
    if adapter_resolver is None:
        return _result_error("SkyDiscover catalog resolver is unavailable", started_at=started)
    try:
        resolved = adapter_resolver(task_ref)
        target = Path(resolved["target_path"])
        if resolved.get("target_kind") != "skydiscover_docker_evaluator":
            raise AlabError("CONFIG_INVALID", "runner.skydiscover_task_ref must resolve to a Docker evaluator")
        program_path = _resolve_inside(workspace, config.runner.program_path, "runner.program_path")
    except (AlabError, KeyError) as exc:
        reason = exc.reason if isinstance(exc, AlabError) else "SkyDiscover catalog resolver returned incomplete data"
        return _result_error(reason, started_at=started)
    if not program_path.exists():
        return _result_error("runner.program_path does not exist", started_at=started)
    run_dir.mkdir(parents=True, exist_ok=True)
    hidden_root = hidden_dir or run_dir.parent / "hidden"
    hidden_root.mkdir(parents=True, exist_ok=True)
    setup_stdout = b""
    setup_stderr = b""
    cache_metadata: dict[str, Any] | None = None
    try:
        bundle = hidden_root / "skydiscover-docker-evaluator"
        _copy_skydiscover_bundle(target, bundle)
        image, cache_metadata, setup_stdout, setup_stderr = _skydiscover_docker_image_for_bundle(config, bundle)
    except AlabError as exc:
        setup_stdout = getattr(exc, "stdout_bytes", setup_stdout)
        setup_stderr = getattr(exc, "stderr_bytes", setup_stderr)
        return RunnerResult(
            "error",
            None,
            None,
            "not_attempted",
            b"",
            exc.reason.encode("utf-8"),
            started,
            utc_now(),
            exc.reason,
            hidden_stdout=_redact(setup_stdout, list(secrets.values())),
            hidden_stderr=_redact(setup_stderr, list(secrets.values())),
        )
    except FileNotFoundError:
        return _result_error("docker executable not found", started_at=started)
    except subprocess.TimeoutExpired:
        return _result_error("docker command timed out", started_at=started)

    program_rel = _workspace_relative(workspace, program_path)
    container_program_path = "/workspace" if program_rel in {"", "."} else "/workspace/" + program_rel
    env = _docker_env(
        config,
        operation_id,
        secrets,
        project_id,
        exp_id,
        config_version,
        workspace_value="/workspace",
        run_dir_value="/logs/alab",
        extra={"ALAB_PROGRAM_PATH": container_program_path},
    )
    container_name = re.sub(r"[^a-zA-Z0-9_.-]", "-", f"alab-{operation_id}")[:63].strip(".-") or "alab-run"
    args = [
        "run",
        "--rm",
        "--name",
        container_name,
        "--workdir",
        "/alab/evaluator",
        "-v",
        f"{workspace.resolve()}:/workspace",
        "-v",
        f"{run_dir.resolve()}:/logs/alab",
        "-v",
        f"{bundle.resolve()}:/alab/evaluator:ro",
        "--entrypoint",
        "/bin/sh",
    ]
    if config.runner.network == "none":
        args.extend(["--network", "none"])
    if config.runner.platform:
        args.extend(["--platform", config.runner.platform])
    if config.runner.user:
        args.extend(["--user", config.runner.user])
    if config.runner.cpus is not None:
        args.extend(["--cpus", str(config.runner.cpus)])
    if config.runner.memory_mb is not None:
        args.extend(["--memory", f"{config.runner.memory_mb}m"])
    for key, value in sorted(env.items()):
        args.extend(["--env", f"{key}={value}"])
    args.append(image)
    args.extend(["/alab/evaluator/evaluate.sh", container_program_path])
    try:
        completed = _run_docker_cli(args, timeout=config.runner.timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        try:
            _run_docker_cli(["rm", "-f", container_name], timeout=30)
        except Exception:
            pass
        return RunnerResult(
            "timeout",
            None,
            None,
            "not_attempted",
            b"",
            b"SkyDiscover Docker evaluator timed out",
            started,
            utc_now(),
            "runner timed out",
            cache_metadata=cache_metadata,
            hidden_stdout=_redact(setup_stdout + (exc.stdout or b""), list(secrets.values())),
            hidden_stderr=_redact(setup_stderr + (exc.stderr or b""), list(secrets.values())),
        )
    except FileNotFoundError:
        return _result_error("docker executable not found", started_at=started)

    hidden_stdout = _redact(setup_stdout + completed.stdout, list(secrets.values()))
    hidden_stderr = _redact(setup_stderr + completed.stderr, list(secrets.values()))
    if completed.returncode != 0:
        return RunnerResult(
            "error",
            completed.returncode,
            None,
            "not_attempted",
            b"",
            b"SkyDiscover Docker evaluator failed",
            started,
            utc_now(),
            "SkyDiscover Docker evaluator failed",
            cache_metadata=cache_metadata,
            hidden_stdout=hidden_stdout,
            hidden_stderr=hidden_stderr,
            adapter_feedback={"mode": "docker", "task_ref": task_ref, "pinned_commit": resolved.get("pinned_commit")},
        )
    try:
        parsed = json.loads(completed.stdout.decode("utf-8").strip())
    except json.JSONDecodeError:
        return RunnerResult(
            "error",
            completed.returncode,
            None,
            "error",
            b"",
            b"SkyDiscover Docker evaluator returned invalid JSON",
            started,
            utc_now(),
            "SkyDiscover Docker evaluator returned invalid JSON",
            cache_metadata=cache_metadata,
            hidden_stdout=hidden_stdout,
            hidden_stderr=hidden_stderr,
        )
    metrics, feedback = _split_skydiscover_result(parsed)
    reward, parse_status = _parse_skydiscover_reward(config, metrics)
    status = "passed" if parse_status == "parsed" else "error"
    failure = None if status == "passed" else "SkyDiscover reward metric missing"
    stdout = _skydiscover_visible_stdout(
        ref=task_ref,
        pinned_commit=resolved.get("pinned_commit"),
        mode="docker",
        metrics=metrics,
        reward=reward,
    )
    return RunnerResult(
        status,
        completed.returncode,
        reward,
        parse_status,
        stdout,
        b"",
        started,
        utc_now(),
        failure,
        cache_metadata=cache_metadata,
        metrics=metrics,
        adapter_feedback={
            "mode": "docker",
            "task_ref": task_ref,
            "pinned_commit": resolved.get("pinned_commit"),
            "feedback": feedback,
        },
        hidden_stdout=hidden_stdout,
        hidden_stderr=hidden_stderr,
    )


def run_skydiscover_python_runner(
    *,
    config: ProjectConfig,
    workspace: Path,
    run_dir: Path,
    operation_id: str,
    secrets: dict[str, str],
    project_id: str = "",
    exp_id: str = "",
    config_version: int | str = "",
    hidden_dir: Path | None = None,
    cache_dir: Path | None = None,
    adapter_resolver: Callable[[str], dict[str, str]] | None = None,
) -> RunnerResult:
    if config.runner.type != "skydiscover_python":
        return _result_error(f"runner type {config.runner.type} is not skydiscover_python")
    started = utc_now()
    task_ref = config.runner.skydiscover_task_ref or ""
    if adapter_resolver is None:
        return _result_error("SkyDiscover catalog resolver is unavailable", started_at=started)
    try:
        resolved = adapter_resolver(task_ref)
        target = Path(resolved["target_path"])
        if resolved.get("target_kind") != "skydiscover_python_evaluator":
            raise AlabError("CONFIG_INVALID", "runner.skydiscover_task_ref must resolve to a Python evaluator")
        program_path = _resolve_inside(workspace, config.runner.program_path, "runner.program_path")
    except (AlabError, KeyError) as exc:
        reason = exc.reason if isinstance(exc, AlabError) else "SkyDiscover catalog resolver returned incomplete data"
        return _result_error(reason, started_at=started)
    if not program_path.exists():
        return _result_error("runner.program_path does not exist", started_at=started)
    run_dir.mkdir(parents=True, exist_ok=True)
    hidden_root = hidden_dir or run_dir.parent / "hidden"
    hidden_root.mkdir(parents=True, exist_ok=True)
    setup_stdout = b""
    setup_stderr = b""
    try:
        bundle = hidden_root / "skydiscover-python-evaluator"
        _copy_skydiscover_bundle(target, bundle)
        entry = _skydiscover_python_entry(bundle, target)
        python_path, cache_metadata, setup_stdout, setup_stderr = _prepare_skydiscover_python_env(
            bundle=bundle,
            cache_dir=cache_dir,
            timeout_seconds=config.runner.timeout_seconds,
        )
    except AlabError as exc:
        setup_stdout = getattr(exc, "stdout_bytes", setup_stdout)
        setup_stderr = getattr(exc, "stderr_bytes", setup_stderr)
        return RunnerResult(
            "error",
            None,
            None,
            "not_attempted",
            b"",
            exc.reason.encode("utf-8"),
            started,
            utc_now(),
            exc.reason,
            hidden_stdout=_redact(setup_stdout, list(secrets.values())),
            hidden_stderr=_redact(setup_stderr, list(secrets.values())),
        )
    wrapper = hidden_root / "alab_skydiscover_python_wrapper.py"
    wrapper.write_text(SKYDISCOVER_WRAPPER, encoding="utf-8")
    env = _effective_env(
        config,
        workspace,
        run_dir,
        operation_id,
        secrets,
        project_id=project_id,
        exp_id=exp_id,
        config_version=config_version,
    )
    try:
        completed = subprocess.run(
            [str(python_path), str(wrapper), str(entry), str(program_path)],
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=config.runner.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        hidden_stdout = _redact(setup_stdout + (exc.stdout or b""), list(secrets.values()))
        hidden_stderr = _redact(setup_stderr + (exc.stderr or b""), list(secrets.values()))
        return RunnerResult(
            "timeout",
            None,
            None,
            "not_attempted",
            b"",
            b"SkyDiscover Python evaluator timed out",
            started,
            utc_now(),
            "runner timed out",
            cache_metadata=cache_metadata,
            hidden_stdout=hidden_stdout,
            hidden_stderr=hidden_stderr,
        )
    except FileNotFoundError:
        return _result_error("SkyDiscover Python executable not found", started_at=started)

    hidden_stdout = setup_stdout
    hidden_stderr = setup_stderr + completed.stderr
    try:
        envelope = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        hidden_stdout = _redact(hidden_stdout + completed.stdout, list(secrets.values()))
        hidden_stderr = _redact(hidden_stderr, list(secrets.values()))
        return RunnerResult(
            "error",
            completed.returncode,
            None,
            "error",
            b"",
            b"SkyDiscover Python evaluator returned invalid wrapper output",
            started,
            utc_now(),
            "SkyDiscover Python evaluator returned invalid wrapper output",
            cache_metadata=cache_metadata,
            hidden_stdout=hidden_stdout,
            hidden_stderr=hidden_stderr,
        )
    evaluator_stdout = str(envelope.get("stdout") or "").encode("utf-8")
    evaluator_stderr = str(envelope.get("stderr") or "").encode("utf-8")
    hidden_stdout = _redact(hidden_stdout + evaluator_stdout, list(secrets.values()))
    hidden_stderr = _redact(hidden_stderr + evaluator_stderr, list(secrets.values()))
    if completed.returncode != 0 or not envelope.get("ok"):
        error_info = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        if error_info.get("traceback"):
            hidden_stderr = _redact(hidden_stderr + str(error_info["traceback"]).encode("utf-8"), list(secrets.values()))
        return RunnerResult(
            "error",
            completed.returncode,
            None,
            "not_attempted",
            b"",
            b"SkyDiscover Python evaluator failed",
            started,
            utc_now(),
            "SkyDiscover Python evaluator failed",
            cache_metadata=cache_metadata,
            hidden_stdout=hidden_stdout,
            hidden_stderr=hidden_stderr,
            adapter_feedback={"mode": "python", "task_ref": task_ref, "pinned_commit": resolved.get("pinned_commit")},
        )
    metrics, feedback = _split_skydiscover_result(envelope.get("result"))
    reward, parse_status = _parse_skydiscover_reward(config, metrics)
    status = "passed" if parse_status == "parsed" else "error"
    failure = None if status == "passed" else "SkyDiscover reward metric missing"
    stdout = _skydiscover_visible_stdout(
        ref=task_ref,
        pinned_commit=resolved.get("pinned_commit"),
        mode="python",
        metrics=metrics,
        reward=reward,
    )
    return RunnerResult(
        status,
        completed.returncode,
        reward,
        parse_status,
        stdout,
        b"",
        started,
        utc_now(),
        failure,
        cache_metadata=cache_metadata,
        metrics=metrics,
        adapter_feedback={
            "mode": "python",
            "task_ref": task_ref,
            "pinned_commit": resolved.get("pinned_commit"),
            "feedback": feedback,
            "sandbox": "not_os_sandbox",
        },
        hidden_stdout=hidden_stdout,
        hidden_stderr=hidden_stderr,
    )


def parse_reward(config: ProjectConfig, exit_code: int, stdout: bytes, workspace: Path, run_dir: Path) -> tuple[float | None, str]:
    reward = config.reward
    try:
        if reward.type == "exit_code":
            return (1.0 if exit_code == 0 else 0.0), "parsed"
        if reward.type == "stdout_regex" and reward.pattern:
            text = stdout[: config.logs.stdout_limit_bytes].decode("utf-8", errors="replace")
            match = re.search(reward.pattern, text)
            if not match:
                return None, "missing"
            value = match.groupdict().get("reward") if "reward" in match.groupdict() else match.group(1)
            return _parse_text_reward_number(value), "parsed"
        if reward.type == "file" and reward.path:
            prefix, sep, rel = reward.path.partition(":")
            if sep != ":" or prefix not in {"workspace", "run"} or not rel:
                return None, "invalid"
            root = run_dir if prefix == "run" else workspace
            root_resolved = root.resolve()
            path = (root / rel).resolve()
            if path != root_resolved and root_resolved not in path.parents:
                return None, "invalid"
            limit = config.artifacts.per_file_limit_bytes
            if limit < 1:
                return None, "invalid"
            with path.open("rb") as fh:
                data = fh.read(limit + 1)
            if len(data) > limit:
                return None, "invalid"
            text = data.decode("utf-8").strip()
            if path.suffix.lower() == ".json":
                value = json.loads(text)
                metrics = _reward_metric_map(value)
                if metrics is None:
                    return None, "invalid"
                if reward.primary_metric not in metrics:
                    return None, "missing"
                return metrics[reward.primary_metric], "parsed"
            return _parse_text_reward_number(text), "parsed"
    except Exception:
        return None, "invalid"
    return None, "missing"


def store_log_file(
    base: Path,
    project_id: str,
    owner_id: str,
    stream: str,
    data: bytes,
    limit: int,
    preview_limit: int = 4096,
) -> tuple[str, int, int, str, str, bool]:
    stored = data[:limit]
    truncated = len(data) > limit
    digest = hashlib.sha256(stored).hexdigest()
    rel = Path("logs") / stream / digest[:2] / f"{owner_id}-{digest}.log"
    target = base / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(stored)
    preview = stored[:preview_limit].decode("utf-8", errors="replace")
    return rel.as_posix(), len(data), len(stored), "sha256:" + digest, preview, truncated


def capture_artifacts(
    *,
    config: ProjectConfig,
    workspace: Path,
    run_dir: Path,
    artifact_store: Path,
    project_id: str,
    exp_id: str | None,
    run_id: str | None,
    validation_id: str | None,
) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []
    total = 0
    seen_resolved: set[Path] = set()
    seen_skipped_resolved: set[Path] = set()

    def record(
        *,
        source_path: Path,
        root_name: str,
        relative_path: str,
        status: str,
        size: int | None,
        content_hash: str | None = None,
        blob_path: str | None = None,
        capture_error: str | None = None,
    ) -> None:
        captured.append(
            {
                "artifact_id": new_id("art", source_path.name),
                "project_id": project_id,
                "exp_id": exp_id,
                "run_id": run_id,
                "validation_id": validation_id,
                "root": root_name,
                "relative_path": relative_path,
                "size_bytes": size,
                "content_hash": content_hash,
                "status": status,
                "blob_path": blob_path,
                "capture_error": capture_error,
            }
        )

    def _matched_relative(path: Path, root: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.name

    events: list[tuple[str, str, str, Path, Path | None, str | None]] = []

    for pattern in config.artifacts.globs:
        root_name, _, rel_pattern = pattern.partition(":")
        if not rel_pattern:
            root_name = "workspace"
            rel_pattern = pattern
        if root_name not in {"workspace", "run"}:
            continue
        root = workspace if root_name == "workspace" else run_dir
        root_resolved = root.resolve()

        def enqueue(matched: Path, *, root_name: str = root_name, root: Path = root, root_resolved: Path = root_resolved) -> None:
            try:
                resolved = matched.resolve()
            except (OSError, RuntimeError) as exc:
                events.append((root_name, _matched_relative(matched, root), "error", matched, None, str(exc)))
                return
            try:
                resolved_rel = resolved.relative_to(root_resolved)
            except ValueError:
                if resolved in seen_skipped_resolved:
                    return
                seen_skipped_resolved.add(resolved)
                events.append((root_name, _matched_relative(matched, root), "skipped", matched, None, None))
                return
            if resolved.is_dir():
                for child in sorted(resolved.rglob("*")):
                    enqueue(child)
                return
            if resolved in seen_resolved:
                return
            seen_resolved.add(resolved)
            events.append((root_name, resolved_rel.as_posix(), "candidate", matched, resolved, None))

        for match in glob.glob(str(root / rel_pattern), recursive=True):
            enqueue(Path(match))
    for root_name, relative_path, kind, source_path, resolved, capture_error in sorted(events, key=lambda item: (item[0], item[1])):
        if kind == "skipped":
            record(source_path=source_path, root_name=root_name, relative_path=relative_path, status="skipped", size=None)
            continue
        if kind == "error":
            record(source_path=source_path, root_name=root_name, relative_path=relative_path, status="error", size=None, capture_error=capture_error)
            continue
        assert resolved is not None
        try:
            data = resolved.read_bytes()
            if len(data) > config.artifacts.per_file_limit_bytes or total + len(data) > config.artifacts.per_run_limit_bytes:
                record(source_path=source_path, root_name=root_name, relative_path=relative_path, status="skipped", size=len(data))
                continue
            digest = hashlib.sha256(data).hexdigest()
            blob_rel = Path("blobs") / "sha256" / digest[:2] / digest
            blob_target = artifact_store / blob_rel
            blob_target.parent.mkdir(parents=True, exist_ok=True)
            if not blob_target.exists():
                blob_target.write_bytes(data)
            total += len(data)
            record(
                source_path=source_path,
                root_name=root_name,
                relative_path=relative_path,
                status="captured",
                size=len(data),
                content_hash="sha256:" + digest,
                blob_path=blob_rel.as_posix(),
            )
        except OSError as exc:
            record(source_path=source_path, root_name=root_name, relative_path=relative_path, status="error", size=None, capture_error=str(exc))
    return captured


def clean_copy_from_git(repo_git: Path, commit: str, workspace: Path) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.parent.mkdir(parents=True, exist_ok=True)
    run_cmd(["git", f"--git-dir={repo_git}", "worktree", "add", "--detach", str(workspace), commit])
