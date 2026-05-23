from __future__ import annotations

import json
import os
import subprocess

import pytest

from alab.configs import ProjectConfig
from alab.errors import AlabError
from alab.runner import _parse_harbor_reward, load_harbor_task, run_configured_runner


def _harbor_config(ref: str, *, env: dict[str, str] | None = None, working_directory: str = ".") -> ProjectConfig:
    payload = {
        "schema_version": 1,
        "project": {"name": "Harbor Project", "task": "Run Harbor verifier"},
        "runner": {
            "type": "harbor",
            "timeout_seconds": 30,
            "working_directory": working_directory,
            "harbor_task_ref": ref,
        },
        "reward": {"type": "harbor", "direction": "maximize", "primary_metric": "reward"},
    }
    if env is not None:
        payload["env"] = env
    return ProjectConfig.model_validate(payload)


def _resolver(task_dir):
    return lambda ref: {
        "ref": ref,
        "relative_path": task_dir.name,
        "target_kind": "harbor_task",
        "pinned_commit": "",
        "target_path": str(task_dir),
    }


def _write_harbor_task(task_dir, task_toml: str) -> None:
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(task_toml.strip() + "\n", encoding="utf-8")


def test_harbor_adapter_resolver_failures_do_not_create_runtime_dirs(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    task_dir = tmp_path / "harbor-task"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    _write_harbor_task(
        task_dir,
        """
[environment]
image = "harbor-env:latest"
""",
    )
    cases = [
        ("no_resolver", _harbor_config("task"), None, "Harbor task resolver is unavailable"),
        (
            "incomplete_resolver",
            _harbor_config("task"),
            lambda _ref: {"target_kind": "harbor_task"},
            "Harbor task resolver returned incomplete data",
        ),
        (
            "wrong_kind",
            _harbor_config("task"),
            lambda ref: {
                "ref": ref,
                "relative_path": "benchmarks/demo",
                "target_kind": "skydiscover_python_evaluator",
                "pinned_commit": "a" * 40,
                "target_path": str(task_dir),
            },
            "runner.harbor_task_ref must resolve to a Harbor task",
        ),
        ("missing_working_dir", _harbor_config("task", working_directory="missing"), _resolver(task_dir), "runner.working_directory does not exist"),
    ]

    for case_name, config, resolver, expected_reason in cases:
        run_dir = tmp_path / f"run-{case_name}"
        hidden_dir = tmp_path / f"hidden-{case_name}"
        result = run_configured_runner(
            config=config,
            workspace=workspace,
            run_dir=run_dir,
            operation_id=f"harbor-{case_name}",
            secrets={},
            hidden_dir=hidden_dir,
            adapter_resolver=resolver,
        )

        assert result.status == "error"
        assert result.failure_reason == expected_reason
        assert expected_reason.encode() in result.stderr
        assert not run_dir.exists()
        assert not hidden_dir.exists()
        assert (workspace / "main.py").read_text(encoding="utf-8") == "print('candidate')\n"


def test_harbor_timeout_removes_named_container_and_keeps_output_hidden(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    task_dir = tmp_path / "harbor-task"
    workspace.mkdir()
    _write_harbor_task(
        task_dir,
        """
[environment]
image = "harbor-env:latest"
""",
    )
    calls: list[list[str]] = []

    def fake_docker(args, *, timeout=None):
        calls.append(args)
        if args[:2] == ["image", "inspect"]:
            return subprocess.CompletedProcess(["docker", *args], 0, b"", b"")
        if args and args[0] == "run":
            raise subprocess.TimeoutExpired(["docker", *args], timeout or 1, output=b"harbor-secret stdout", stderr=b"harbor-secret stderr")
        if args[:2] == ["rm", "-f"]:
            return subprocess.CompletedProcess(["docker", *args], 0, b"", b"")
        raise AssertionError(args)

    monkeypatch.setattr("alab.runner._run_docker_cli", fake_docker)
    result = run_configured_runner(
        config=_harbor_config("task"),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="harbor-timeout",
        secrets={"SECRET": "harbor-secret"},
        hidden_dir=hidden_dir,
        adapter_resolver=_resolver(task_dir),
    )

    assert result.status == "timeout"
    assert result.failure_reason == "runner timed out"
    assert b"Harbor verifier timed out" in result.stderr
    assert b"harbor-secret" not in result.hidden_stdout
    assert b"harbor-secret" not in result.hidden_stderr
    assert b"[REDACTED]" in result.hidden_stdout
    assert b"[REDACTED]" in result.hidden_stderr
    assert ["rm", "-f", "alab-harbor-timeout"] in calls


def test_harbor_shared_verifier_runs_with_hidden_logs_and_secret_redaction(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    task_dir = tmp_path / "harbor-task"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-calls.jsonl"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    monkeypatch.setenv("HOST_ONLY_VALUE", "host-only")
    monkeypatch.setenv("ALAB_KEY", "host-root-key")
    monkeypatch.setenv("ALAB_TOKEN", "host-token")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        """
[environment]
image = "harbor-env:latest"
allow_internet = false
cpus = 2
memory_mb = 256

[environment.env]
HARBOR_SECRET = "task-secret"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    print("[]")
    raise SystemExit(0)
if args and args[0] == "run":
    run_mount = next(args[index + 1] for index, arg in enumerate(args) if arg == "-v" and args[index + 1].endswith(":/logs/alab"))
    run_dir = Path(run_mount.split(":", 1)[0])
    reward_dir = run_dir / "logs" / "verifier"
    reward_dir.mkdir(parents=True, exist_ok=True)
    (reward_dir / "reward.json").write_text(json.dumps({"reward": 5.5, "checks": 3}), encoding="utf-8")
    print("hidden task-secret verifier stdout")
    print("hidden task-secret external-secret verifier stderr", file=sys.stderr)
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))

    result = run_configured_runner(
        config=_harbor_config(
            "harbor-fixture",
            env={
                "ALAB_PROJECT_ID": "user-project",
                "ALAB_EXP_ID": "user-exp",
                "ALAB_RUN_ID": "user-run",
                "ALAB_CONFIG_VERSION": "user-version",
                "ALAB_WORKSPACE": "/user-workspace",
                "ALAB_RUN_DIR": "/user-run-dir",
                "ALAB_HARBOR_TASK_DIR": "/user-harbor",
                "VISIBLE": "1",
            },
        ),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-harbor",
        secrets={"SECRET": "external-secret"},
        project_id="proj-harbor",
        exp_id="exp-harbor",
        config_version=9,
        hidden_dir=hidden_dir,
        adapter_resolver=_resolver(task_dir),
    )

    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    run_call = next(call for call in calls if call and call[0] == "run")
    bundle = hidden_dir / "harbor-task"
    assert result.status == "passed"
    assert result.reward == 5.5
    assert result.metrics["checks"] == 3
    assert result.adapter_feedback["verifier_mode"] == "shared"
    assert b"Harbor verifier completed" in result.stdout
    assert b"task-secret" not in result.hidden_stdout
    assert b"external-secret" not in result.hidden_stderr
    assert b"[REDACTED]" in result.hidden_stdout
    assert b"[REDACTED]" in result.hidden_stderr
    assert (bundle / "tests" / "test.sh").is_file()
    assert f"{bundle.resolve()}:/alab/harbor:ro" in run_call
    assert "--network" in run_call
    assert "none" in run_call
    assert "--cpus" in run_call
    assert "--memory" in run_call
    env_values = [run_call[index + 1] for index, item in enumerate(run_call[:-1]) if item == "--env"]
    assert "HARBOR_SECRET=task-secret" in env_values
    assert "SECRET=external-secret" in env_values
    assert "VISIBLE=1" in env_values
    assert "ALAB_PROJECT_ID=proj-harbor" in env_values
    assert "ALAB_EXP_ID=exp-harbor" in env_values
    assert "ALAB_RUN_ID=run-harbor" in env_values
    assert "ALAB_CONFIG_VERSION=9" in env_values
    assert "ALAB_WORKSPACE=/workspace" in env_values
    assert "ALAB_RUN_DIR=/logs/alab" in env_values
    assert "ALAB_HARBOR_TASK_DIR=/alab/harbor" in env_values
    assert "HOST_ONLY_VALUE=host-only" not in env_values
    assert "ALAB_KEY=host-root-key" not in env_values
    assert "ALAB_TOKEN=host-token" not in env_values
    assert "ALAB_PROJECT_ID=user-project" not in env_values
    assert "ALAB_EXP_ID=user-exp" not in env_values
    assert "ALAB_RUN_ID=user-run" not in env_values
    assert "ALAB_CONFIG_VERSION=user-version" not in env_values
    assert "ALAB_WORKSPACE=/user-workspace" not in env_values
    assert "ALAB_RUN_DIR=/user-run-dir" not in env_values
    assert "ALAB_HARBOR_TASK_DIR=/user-harbor" not in env_values


def test_harbor_runner_reports_invalid_reward_metrics_without_storage_error(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    task_dir = tmp_path / "harbor-invalid-reward-task"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    _write_harbor_task(
        task_dir,
        """
[environment]
image = "harbor-env:latest"
""",
    )

    def fake_docker(args, timeout=None):
        if args[:2] == ["image", "inspect"]:
            return subprocess.CompletedProcess(["docker", *args], 0, b"", b"")
        if args and args[0] == "run":
            reward_dir = run_dir / "logs" / "verifier"
            reward_dir.mkdir(parents=True, exist_ok=True)
            (reward_dir / "reward.json").write_text(json.dumps({"reward": 1.0, "details": []}), encoding="utf-8")
            return subprocess.CompletedProcess(["docker", *args], 0, b"", b"")
        raise AssertionError(args)

    monkeypatch.setattr("alab.runner._run_docker_cli", fake_docker)
    result = run_configured_runner(
        config=_harbor_config("harbor-invalid-reward"),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-harbor-invalid-reward",
        secrets={},
        hidden_dir=hidden_dir,
        adapter_resolver=_resolver(task_dir),
    )

    assert result.status == "error"
    assert result.exit_code == 0
    assert result.reward is None
    assert result.reward_parse_status == "invalid"
    assert result.failure_reason == "Harbor reward metrics invalid"
    assert result.metrics == {}


def test_harbor_separate_verifier_image_runs_with_hidden_logs(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    task_dir = tmp_path / "harbor-separate-image-task"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-calls.jsonl"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        """
[environment]
allow_internet = false

[environment.env]
HARBOR_SECRET = "separate-image-secret"

[verifier]
image = "harbor-verifier:latest"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    raise SystemExit(0 if args[2] == "harbor-verifier:latest" else 1)
if args and args[0] == "run":
    run_mount = next(args[index + 1] for index, arg in enumerate(args) if arg == "-v" and args[index + 1].endswith(":/logs/alab"))
    run_dir = Path(run_mount.split(":", 1)[0])
    reward_dir = run_dir / "logs" / "verifier"
    reward_dir.mkdir(parents=True, exist_ok=True)
    (reward_dir / "reward.txt").write_text("6.25", encoding="utf-8")
    print("hidden separate-image-secret verifier stdout")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))

    result = run_configured_runner(
        config=_harbor_config("harbor-separate-image"),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-harbor-separate-image",
        secrets={},
        hidden_dir=hidden_dir,
        adapter_resolver=_resolver(task_dir),
    )

    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    run_call = next(call for call in calls if call and call[0] == "run")
    bundle = hidden_dir / "harbor-task"
    assert result.status == "passed"
    assert result.reward == 6.25
    assert result.adapter_feedback["verifier_mode"] == "separate"
    assert result.cache_metadata is None
    assert b"verifier mode: separate" in result.stdout
    assert b"separate-image-secret" not in result.hidden_stdout
    assert b"[REDACTED]" in result.hidden_stdout
    assert (bundle / "tests" / "test.sh").is_file()
    assert "harbor-verifier:latest" in run_call
    assert f"{bundle.resolve()}:/alab/harbor:ro" in run_call
    assert "--network" in run_call
    assert "none" in run_call
    assert "ALAB_HARBOR_TASK_DIR=/alab/harbor" in run_call
    assert "HARBOR_SECRET=separate-image-secret" in run_call


def test_harbor_separate_tests_dockerfile_builds_image_cache(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    task_dir = tmp_path / "harbor-tests-dockerfile-task"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-calls.jsonl"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "Dockerfile").write_text("FROM verifier-base:latest\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        """
[environment]
allow_internet = false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    raise SystemExit(1)
if args and args[0] == "build":
    print("built harbor tests Dockerfile")
    raise SystemExit(0)
if args and args[0] == "run":
    run_mount = next(args[index + 1] for index, arg in enumerate(args) if arg == "-v" and args[index + 1].endswith(":/logs/alab"))
    run_dir = Path(run_mount.split(":", 1)[0])
    reward_dir = run_dir / "logs" / "verifier"
    reward_dir.mkdir(parents=True, exist_ok=True)
    (reward_dir / "reward.json").write_text(json.dumps({"reward": 7.5, "checks": 4}), encoding="utf-8")
    print("hidden tests Dockerfile verifier stdout")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))

    result = run_configured_runner(
        config=_harbor_config("harbor-tests-dockerfile"),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-harbor-tests-dockerfile",
        secrets={},
        hidden_dir=hidden_dir,
        adapter_resolver=_resolver(task_dir),
    )

    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    build_call = next(call for call in calls if call and call[0] == "build")
    run_call = next(call for call in calls if call and call[0] == "run")
    bundle = hidden_dir / "harbor-task"
    assert result.status == "passed"
    assert result.reward == 7.5
    assert result.metrics["checks"] == 4
    assert result.adapter_feedback["verifier_mode"] == "separate"
    assert result.cache_metadata is not None
    assert result.cache_metadata["cache_kind"] == "docker_image"
    assert result.cache_metadata["adapter"] == "harbor"
    assert result.cache_metadata["verifier_mode"] == "separate"
    assert result.cache_metadata["status"] == "built"
    assert b"verifier mode: separate" in result.stdout
    assert b"built harbor tests Dockerfile" in result.hidden_stdout
    assert b"hidden tests Dockerfile verifier stdout" in result.hidden_stdout
    assert (bundle / "tests" / "Dockerfile").is_file()
    assert (bundle / "tests" / "test.sh").is_file()
    assert "-f" in build_call
    assert str(bundle / "tests" / "Dockerfile") in build_call
    assert str(bundle) in build_call
    assert result.cache_metadata["docker_tag"] in run_call
    assert f"{bundle.resolve()}:/alab/harbor:ro" in run_call
    assert "--network" in run_call
    assert "none" in run_call


def test_harbor_reward_parser_handles_json_text_missing_and_invalid_values(tmp_path) -> None:
    config = _harbor_config("harbor-reward")

    def write_reward(case_name: str, file_name: str | None, content: str | None):
        run_dir = tmp_path / case_name
        reward_dir = run_dir / "logs" / "verifier"
        reward_dir.mkdir(parents=True)
        if file_name and content is not None:
            (reward_dir / file_name).write_text(content, encoding="utf-8")
        return _parse_harbor_reward(config, run_dir)

    assert write_reward("json-parsed", "reward.json", '{"reward": 5.5, "checks": 3}') == (
        5.5,
        "parsed",
        {"reward": 5.5, "checks": 3},
    )
    assert write_reward("json-missing-primary", "reward.json", '{"checks": 3}') == (
        None,
        "missing",
        {"checks": 3},
    )
    assert write_reward("json-nonnumeric-primary", "reward.json", '{"reward": "bad"}') == (
        None,
        "invalid",
        {},
    )
    number, status, metrics = write_reward("json-nonfinite-primary", "reward.json", '{"reward": NaN}')
    assert number is None
    assert status == "invalid"
    assert metrics == {}
    assert write_reward("json-non-object", "reward.json", "[5]") == (None, "invalid", {})
    assert write_reward("json-bool-metric", "reward.json", '{"reward": true}') == (None, "invalid", {})
    assert write_reward("json-array-metric", "reward.json", '{"reward": 1, "cases": []}') == (None, "invalid", {})
    assert write_reward("json-object-metric", "reward.json", '{"reward": 1, "cases": {}}') == (None, "invalid", {})
    assert write_reward("text-parsed", "reward.txt", "6.25\n") == (6.25, "parsed", {"reward": 6.25})
    assert write_reward("text-nonfinite", "reward.txt", "Infinity\n") == (None, "invalid", {})
    assert write_reward("text-nonnumeric", "reward.txt", "not-a-number\n") == (None, "invalid", {})
    assert write_reward("missing-file", None, None) == (None, "missing", {})


@pytest.mark.parametrize(
    ("case_name", "task_toml", "expected_reason"),
    [
        (
            "multi_step",
            """
steps = ["first", "second"]

[environment]
image = "example:latest"
""",
            "unsupported Harbor task field: steps",
        ),
        (
            "non_linux_os",
            """
os = "windows"

[environment]
image = "example:latest"
""",
            "Harbor non-Linux tasks are not supported",
        ),
        (
            "non_linux_platform",
            """
[environment]
image = "example:latest"
platform = "windows/amd64"
""",
            "Harbor non-Linux platforms are not supported",
        ),
        (
            "gpu",
            """
[environment]
image = "example:latest"
gpu = true
""",
            "unsupported Harbor task field: gpu",
        ),
        (
            "gpu_types",
            """
[environment]
image = "example:latest"
gpu_types = ["a100"]
""",
            "unsupported Harbor task field: gpu_types",
        ),
        (
            "storage_mb",
            """
[environment]
image = "example:latest"
storage_mb = 2048
""",
            "unsupported Harbor task field: storage_mb",
        ),
        (
            "mcp_servers",
            """
mcp_servers = ["tool"]

[environment]
image = "example:latest"
""",
            "unsupported Harbor task field: mcp_servers",
        ),
        (
            "healthcheck",
            """
[environment]
image = "example:latest"

[environment.healthcheck]
command = "curl http://localhost"
""",
            "unsupported Harbor task field: healthcheck",
        ),
        (
            "custom_scheduling",
            """
scheduling = "preemptible"

[environment]
image = "example:latest"
""",
            "unsupported Harbor task field: scheduling",
        ),
        (
            "external_services",
            """
services = ["postgres"]

[environment]
image = "example:latest"
""",
            "Harbor external services are not supported",
        ),
        (
            "docker_compose",
            """
docker_compose = "compose.yaml"

[environment]
image = "example:latest"
""",
            "unsupported Harbor task field: docker_compose",
        ),
        (
            "host_env_placeholder",
            """
[environment]
image = "example:latest"

[env]
TOKEN = "${TOKEN}"
""",
            "Harbor task placeholder values are not supported",
        ),
        (
            "raw_docker_args",
            """
raw_docker_args = ["--privileged"]

[environment]
image = "example:latest"
""",
            "unsupported Harbor task field: raw_docker_args",
        ),
        (
            "host_mounts",
            """
host_mounts = ["/tmp:/tmp"]

[environment]
image = "example:latest"
""",
            "unsupported Harbor task field: host_mounts",
        ),
    ],
)
def test_harbor_task_rejects_unsupported_fields(case_name, task_toml, expected_reason, tmp_path) -> None:
    task_dir = tmp_path / case_name
    _write_harbor_task(task_dir, task_toml)

    with pytest.raises(AlabError) as exc:
        load_harbor_task(task_dir, _harbor_config(str(task_dir)))

    assert exc.value.code == "CONFIG_INVALID"
    assert expected_reason in exc.value.reason
