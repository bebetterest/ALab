from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

import alab.runner as runner_mod
from alab.cli import run
from alab.configs import ProjectConfig
from alab.db import canonical_json
from alab.runner import docker_build_cache_key, run_configured_runner
from alab.timeutil import utc_now


def _docker_config(**runner_overrides) -> ProjectConfig:
    runner = {
        "type": "docker",
        "timeout_seconds": 30,
        "working_directory": ".",
        "command": ["python", "-c", "print('ok')"],
        "dockerfile": "Dockerfile",
        "context": ".",
        **runner_overrides,
    }
    return ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Docker Project", "task": "Test docker runner"},
            "runner": runner,
            "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
        }
    )


def _field(output: str, name: str) -> str:
    return next(line.split(": ", 1)[1] for line in output.splitlines() if line.startswith(f"{name}: "))


def _field_labels(output: str) -> list[str]:
    labels: list[str] = []
    for line in output.splitlines():
        if not line or line.startswith("  "):
            continue
        label, _, _value = line.partition(":")
        labels.append(label)
    return labels


def _project_init_field_labels(*, warning_count: int = 0, failure: bool = False) -> list[str]:
    labels = [
        "object",
        "project id",
        "project name",
        "project status",
        "source id",
        "source ref",
        "config version",
        "validation id",
        "validation status",
        "admin key",
    ]
    labels.extend(["warning code"] * warning_count)
    labels.extend(["error code", "exit code", "reason", "next"] if failure else ["next"])
    return labels


def _run_field_labels(*, failure: bool = False) -> list[str]:
    labels = [
        "object",
        "run id",
        "exp id",
        "commit",
        "created commit",
        "run status",
        "exit code",
        "reward",
        "reward parse status",
        "stdout preview",
        "stderr preview",
        "artifact count",
    ]
    labels.extend(["error code", "exit code", "reason", "next"] if failure else ["next"])
    return labels


def _submission_failure_field_labels() -> list[str]:
    return [
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
    ]


def _assert_project_tmp_clean(home, project_id: str) -> None:
    project_tmp = home / "tmp" / project_id
    if not project_tmp.exists():
        return
    assert sorted(path.relative_to(project_tmp).as_posix() for path in project_tmp.rglob("*")) == []


def _git(args: list[str], cwd) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)
    return completed.stdout.decode("utf-8", errors="replace").strip()


def _assert_worktree_clean(worktree) -> None:
    visible_changes = [line for line in _git(["status", "--porcelain", "--untracked-files=all"], worktree).splitlines() if ".alab/" not in line]
    assert visible_changes == []


def test_docker_build_cache_key_respects_dockerignore(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (workspace / ".dockerignore").write_text("ignored.txt\n", encoding="utf-8")
    (workspace / "main.py").write_text("print('hello')\n", encoding="utf-8")
    ignored = workspace / "ignored.txt"
    ignored.write_text("one\n", encoding="utf-8")

    first_key, context, dockerfile = docker_build_cache_key(_docker_config(), workspace)
    ignored.write_text("two\n", encoding="utf-8")
    second_key, _, _ = docker_build_cache_key(_docker_config(), workspace)
    (workspace / "main.py").write_text("print('changed')\n", encoding="utf-8")
    third_key, _, _ = docker_build_cache_key(_docker_config(), workspace)

    assert context == workspace
    assert dockerfile == workspace / "Dockerfile"
    assert first_key == second_key
    assert first_key != third_key


def test_docker_build_cache_key_ignores_run_time_fields(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (workspace / "main.py").write_text("print('hello')\n", encoding="utf-8")

    base_key, _, _ = docker_build_cache_key(_docker_config(), workspace)
    runtime_changed = _docker_config(
        timeout_seconds=120,
        working_directory=".",
        command=["python", "-c", "print('changed runtime')"],
        network="none",
        user="1000:1000",
        cpus=1.5,
        memory_mb=256,
    )
    build_changed = _docker_config(build_args={"ALAB_TEST_ARG": "1"})

    assert docker_build_cache_key(runtime_changed, workspace)[0] == base_key
    assert docker_build_cache_key(build_changed, workspace)[0] != base_key


def test_docker_runner_setup_output_is_hidden_and_warns_without_visible_merge(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-setup-calls.jsonl"
    workspace.mkdir()
    bin_dir.mkdir()
    (workspace / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    raise SystemExit(1)
if args and args[0] == "build":
    print("docker build stdout setup-secret")
    print("docker build stderr setup-secret", file=sys.stderr)
    raise SystemExit(0)
if args and args[0] == "run":
    print("runner stdout")
    print("runner stderr", file=sys.stderr)
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))

    result = run_configured_runner(
        config=_docker_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-setup-hidden",
        secrets={"SECRET": "setup-secret"},
    )

    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert any(call and call[0] == "build" for call in calls)
    assert result.status == "passed"
    assert result.stdout == b"runner stdout\n"
    assert result.stderr == b"runner stderr\n"
    assert result.warning_codes == ["DOCKER_SETUP_OUTPUT_CAPTURED"]
    assert b"docker build stdout" in result.hidden_stdout
    assert b"docker build stderr" in result.hidden_stderr
    assert b"setup-secret" not in result.hidden_stdout
    assert b"setup-secret" not in result.hidden_stderr
    assert b"[REDACTED]" in result.hidden_stdout
    assert b"[REDACTED]" in result.hidden_stderr
    assert b"docker build" not in result.stdout
    assert b"docker build" not in result.stderr


def test_docker_runner_pulls_missing_image_and_uses_default_network_without_visible_setup(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-pull-calls.jsonl"
    workspace.mkdir()
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    raise SystemExit(1)
if args[:1] == ["pull"]:
    print("docker pull stdout")
    print("docker pull stderr", file=sys.stderr)
    raise SystemExit(0)
if args and args[0] == "run":
    print("reward=17")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))
    cfg = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Docker Pull Project", "task": "Pull missing image"},
            "runner": {
                "type": "docker",
                "timeout_seconds": 30,
                "working_directory": ".",
                "image": "example:missing",
                "command": ["python", "main.py"],
            },
            "reward": {"type": "stdout_regex", "direction": "maximize", "primary_metric": "reward", "pattern": "reward=([0-9.]+)"},
        }
    )

    result = run_configured_runner(
        config=cfg,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-pull-hidden",
        secrets={},
    )

    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    run_call = next(call for call in calls if call and call[0] == "run")
    assert ["pull", "example:missing"] in calls
    assert "--network" not in run_call
    assert result.status == "passed"
    assert result.reward == 17.0
    assert result.warning_codes == ["DOCKER_SETUP_OUTPUT_CAPTURED"]
    assert b"docker pull stdout" in result.hidden_stdout
    assert b"docker pull stderr" in result.hidden_stderr
    assert b"docker pull" not in result.stdout
    assert b"docker pull" not in result.stderr


def test_docker_runner_setup_failure_keeps_setup_bytes_hidden(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    bin_dir = tmp_path / "bin"
    workspace.mkdir()
    bin_dir.mkdir()
    (workspace / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import sys

args = sys.argv[1:]
if args[:2] == ["image", "inspect"]:
    raise SystemExit(1)
if args and args[0] == "build":
    print("private build stdout setup-secret")
    print("private build stderr setup-secret", file=sys.stderr)
    raise SystemExit(23)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    result = run_configured_runner(
        config=_docker_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-build-failed",
        secrets={"SECRET": "setup-secret"},
    )

    assert result.status == "error"
    assert result.failure_reason == "docker build failed"
    assert result.stderr == b"docker build failed"
    assert b"private build stdout" in result.hidden_stdout
    assert b"private build stderr" in result.hidden_stderr
    assert b"setup-secret" not in result.hidden_stdout
    assert b"setup-secret" not in result.hidden_stderr
    assert b"[REDACTED]" in result.hidden_stdout
    assert b"[REDACTED]" in result.hidden_stderr
    assert b"private build" not in result.stderr


def test_project_init_persists_docker_setup_output_as_hidden_validation_logs(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.docker.toml"
    bin_dir = tmp_path / "bin"
    source.mkdir()
    bin_dir.mkdir()
    (source / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config.write_text(
        """
schema_version = 1

[project]
name = "Docker Hidden Setup Project"
task = "Persist Docker setup output as hidden logs"

[runner]
type = "docker"
timeout_seconds = 30
working_directory = "."
dockerfile = "Dockerfile"
context = "."
command = ["python", "main.py"]

[reward]
type = "stdout_regex"
direction = "maximize"
primary_metric = "reward"
pattern = "reward=([0-9.]+)"

[secret_env]
SETUP_SECRET = "setup-secret"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
if args[:2] == ["image", "inspect"]:
    raise SystemExit(1)
if args and args[0] == "build":
    print("validation build stdout setup-secret")
    print("validation build stderr setup-secret", file=sys.stderr)
    raise SystemExit(0)
if args and args[0] == "run":
    print("reward=19")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    out = capsys.readouterr().out
    project_id = _field(out, "project id")
    validation_id = _field(out, "validation id")

    assert "validation status: passed" in out
    assert "warning code: DOCKER_SETUP_OUTPUT_CAPTURED" in out
    assert not (home / "tmp" / project_id / validation_id).exists()
    _assert_project_tmp_clean(home, project_id)
    with sqlite3.connect(home / "alab.db") as conn:
        validation_record = conn.execute(
            "SELECT record_json FROM project_validations WHERE validation_id = ?",
            (validation_id,),
        ).fetchone()[0]
        previews = dict(
            conn.execute(
                "SELECT stream, preview_text FROM log_streams WHERE validation_id = ? ORDER BY stream",
                (validation_id,),
            ).fetchall()
        )
        hidden = dict(
            conn.execute(
                "SELECT stream, hidden FROM log_streams WHERE validation_id = ? ORDER BY stream",
                (validation_id,),
            ).fetchall()
        )

    assert "DOCKER_SETUP_OUTPUT_CAPTURED" in json.loads(validation_record)["warnings"]
    assert "validation build stdout" in previews["hidden_stdout"]
    assert "validation build stderr" in previews["hidden_stderr"]
    assert "setup-secret" not in previews["hidden_stdout"]
    assert "setup-secret" not in previews["hidden_stderr"]
    assert "[REDACTED]" in previews["hidden_stdout"]
    assert "[REDACTED]" in previews["hidden_stderr"]
    assert "validation build" not in previews["stdout"]
    assert "validation build" not in previews["stderr"]
    assert hidden["hidden_stdout"] == 1
    assert hidden["hidden_stderr"] == 1
    assert project_id in out

    worktree = tmp_path / "docker-exp"
    assert run(["--home", str(home), "--key", root_key, "exp", "create", "--project", project_id, "--name", "docker-run", "--path", str(worktree)]) == 0
    capsys.readouterr()
    head_before_run = _git(["rev-parse", "HEAD"], worktree)
    _assert_worktree_clean(worktree)
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "docker service cleanup"]) == 0
    run_out = capsys.readouterr().out
    run_id = _field(run_out, "run id")
    assert "run status: passed" in run_out
    assert "reward: 19.0" in run_out
    assert not (home / "tmp" / project_id / run_id).exists()
    _assert_project_tmp_clean(home, project_id)
    assert _git(["rev-parse", "HEAD"], worktree) == head_before_run
    _assert_worktree_clean(worktree)


def test_docker_platform_aliases_are_canonicalized_for_cache_and_cli(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-platform-calls.jsonl"
    workspace.mkdir()
    bin_dir.mkdir()
    (workspace / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    print("[]")
    raise SystemExit(1)
if args and args[0] == "build":
    raise SystemExit(0)
if args and args[0] == "run":
    print("ok")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))

    aliased = _docker_config(platform="Linux/X86_64")
    canonical = _docker_config(platform="linux/amd64")
    assert aliased.runner.platform == "linux/amd64"
    assert docker_build_cache_key(aliased, workspace)[0] == docker_build_cache_key(canonical, workspace)[0]

    result = run_configured_runner(
        config=aliased,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-platform",
        secrets={},
    )

    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    build_call = next(call for call in calls if call and call[0] == "build")
    run_call = next(call for call in calls if call and call[0] == "run")
    assert result.status == "passed"
    assert build_call[build_call.index("--platform") + 1] == "linux/amd64"
    assert run_call[run_call.index("--platform") + 1] == "linux/amd64"


def test_docker_config_paths_must_stay_inside_workspace(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc:
        _docker_config(context="../outside")

    assert "runner.context escapes repository" in str(exc.value)


def test_adapter_without_resolver_returns_structured_runner_error(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    cfg = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Harbor Project", "task": "Adapter placeholder"},
            "runner": {"type": "harbor", "harbor_task_ref": "task"},
            "reward": {"type": "harbor", "direction": "maximize", "primary_metric": "reward"},
        }
    )

    result = run_configured_runner(config=cfg, workspace=workspace, run_dir=run_dir, operation_id="val-test", secrets={})

    assert result.status == "error"
    assert result.failure_reason == "Harbor task resolver is unavailable"
    assert b"resolver is unavailable" in result.stderr


def test_docker_runner_timeout_removes_named_container_and_redacts_output(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    calls: list[list[str]] = []

    def fake_docker(args, *, timeout=None):
        calls.append(args)
        if args[:2] == ["image", "inspect"]:
            return subprocess.CompletedProcess(["docker", *args], 0, b"", b"")
        if args and args[0] == "run":
            raise subprocess.TimeoutExpired(["docker", *args], timeout or 1, output=b"visible docker-secret stdout", stderr=b"visible docker-secret stderr")
        if args[:2] == ["rm", "-f"]:
            return subprocess.CompletedProcess(["docker", *args], 0, b"", b"")
        raise AssertionError(args)

    monkeypatch.setattr(runner_mod, "_run_docker_cli", fake_docker)
    result = run_configured_runner(
        config=_docker_config(image="example:latest", dockerfile=None, context=None, command=["python", "main.py"]),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="timeout-test",
        secrets={"SECRET": "docker-secret"},
    )

    assert result.status == "timeout"
    assert result.failure_reason == "runner timed out"
    assert b"docker-secret" not in result.stdout
    assert b"docker-secret" not in result.stderr
    assert b"[REDACTED]" in result.stdout
    assert b"[REDACTED]" in result.stderr
    assert ["rm", "-f", "alab-timeout-test"] in calls


def test_docker_runner_contract_with_fake_docker(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-calls.jsonl"
    workspace.mkdir()
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    print("[]")
    raise SystemExit(0)
if args and args[0] == "run":
    print("reward=7")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))
    cfg = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Docker Project", "task": "Run fake docker"},
            "runner": {
                "type": "docker",
                "timeout_seconds": 30,
                "working_directory": ".",
                "image": "example:latest",
                "network": "none",
                "command": ["python", "main.py"],
            },
            "reward": {"type": "stdout_regex", "direction": "maximize", "primary_metric": "reward", "pattern": "reward=([0-9.]+)"},
            "env": {"VISIBLE": "1"},
        }
    )

    result = run_configured_runner(
        config=cfg,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-fake",
        secrets={"SECRET": "dont-print"},
        project_id="proj-test",
        exp_id="exp-test",
        config_version=3,
    )

    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    run_call = next(call for call in calls if call and call[0] == "run")
    assert result.status == "passed"
    assert result.reward == 7.0
    assert "--network" in run_call
    assert "none" in run_call
    assert "ALAB_WORKSPACE=/app" in run_call
    assert "ALAB_RUN_DIR=/logs/alab" in run_call
    assert "ALAB_PROJECT_ID=proj-test" in run_call
    assert "VISIBLE=1" in run_call
    assert "SECRET=dont-print" in run_call


def test_docker_runner_shell_uses_container_sh(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-shell-calls.jsonl"
    shell_command = "printf 'reward=11\\n'; test \"$ALAB_RUN_ID\" = run-shell"
    workspace.mkdir()
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    print("[]")
    raise SystemExit(0)
if args and args[0] == "run":
    print("reward=11")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))
    cfg = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Docker Shell Project", "task": "Run fake docker shell"},
            "runner": {
                "type": "docker",
                "timeout_seconds": 30,
                "working_directory": ".",
                "image": "example:latest",
                "network": "none",
                "command": None,
                "shell": shell_command,
            },
            "reward": {"type": "stdout_regex", "direction": "maximize", "primary_metric": "reward", "pattern": "reward=([0-9.]+)"},
        }
    )

    result = run_configured_runner(
        config=cfg,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-shell",
        secrets={},
    )

    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    run_call = next(call for call in calls if call and call[0] == "run")
    image_index = run_call.index("example:latest")
    assert result.status == "passed"
    assert result.reward == 11.0
    assert run_call[image_index + 1 :] == ["/bin/sh", "-c", shell_command]


def test_docker_runner_env_is_hostless_and_internal_env_overrides_config_env(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-env-calls.jsonl"
    workspace.mkdir()
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    print("[]")
    raise SystemExit(0)
if args and args[0] == "run":
    print("reward=13")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))
    monkeypatch.setenv("HOST_ONLY_VALUE", "host-only")
    monkeypatch.setenv("ALAB_KEY", "host-root-key")
    monkeypatch.setenv("ALAB_TOKEN", "host-token")
    cfg = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Docker Env Project", "task": "Run fake docker env"},
            "runner": {
                "type": "docker",
                "timeout_seconds": 30,
                "working_directory": ".",
                "image": "example:latest",
                "network": "none",
                "command": ["python", "main.py"],
            },
            "env": {
                "ALAB_PROJECT_ID": "user-project",
                "ALAB_EXP_ID": "user-exp",
                "ALAB_RUN_ID": "user-run",
                "ALAB_CONFIG_VERSION": "user-version",
                "ALAB_WORKSPACE": "/user-workspace",
                "ALAB_RUN_DIR": "/user-run-dir",
                "VISIBLE": "1",
            },
            "reward": {"type": "stdout_regex", "direction": "maximize", "primary_metric": "reward", "pattern": "reward=([0-9.]+)"},
        }
    )

    result = run_configured_runner(
        config=cfg,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-docker-env",
        secrets={"SECRET": "docker-secret"},
        project_id="proj-docker",
        exp_id="exp-docker",
        config_version=4,
    )

    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    run_call = next(call for call in calls if call and call[0] == "run")
    env_values = [run_call[index + 1] for index, item in enumerate(run_call[:-1]) if item == "--env"]
    assert result.status == "passed"
    assert result.reward == 13.0
    assert "VISIBLE=1" in env_values
    assert "SECRET=docker-secret" in env_values
    assert "ALAB_PROJECT_ID=proj-docker" in env_values
    assert "ALAB_EXP_ID=exp-docker" in env_values
    assert "ALAB_RUN_ID=run-docker-env" in env_values
    assert "ALAB_CONFIG_VERSION=4" in env_values
    assert "ALAB_WORKSPACE=/app" in env_values
    assert "ALAB_RUN_DIR=/logs/alab" in env_values
    assert "HOST_ONLY_VALUE=host-only" not in env_values
    assert "ALAB_KEY=host-root-key" not in env_values
    assert "ALAB_TOKEN=host-token" not in env_values
    assert "ALAB_PROJECT_ID=user-project" not in env_values
    assert "ALAB_EXP_ID=user-exp" not in env_values
    assert "ALAB_RUN_ID=user-run" not in env_values
    assert "ALAB_CONFIG_VERSION=user-version" not in env_values
    assert "ALAB_WORKSPACE=/user-workspace" not in env_values
    assert "ALAB_RUN_DIR=/user-run-dir" not in env_values


def test_config_validate_refreshes_docker_capability_cache(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args[:1] == ["version"]:
    print(json.dumps({"Client": {"Version": "fake-client"}, "Server": {"Version": "fake-server"}}))
    raise SystemExit(0)
if args[:1] == ["info"]:
    print(json.dumps({"OSType": "linux", "Architecture": "amd64", "NCPU": 4, "MemTotal": 1073741824}))
    raise SystemExit(0)
if args[:2] == ["buildx", "ls"]:
    print("default * docker running linux/amd64, linux/arm64")
    raise SystemExit(0)
if args[:2] == ["run", "--help"]:
    print("Usage: docker run [OPTIONS] IMAGE [COMMAND]\\n      --cpus float\\n      --memory bytes")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    assert run(["--home", str(home), "auth", "init"]) == 0
    capsys.readouterr()

    assert run(["--home", str(home), "config", "validate", "--refresh-capabilities"]) == 0
    out = capsys.readouterr().out

    assert "object: config" in out
    assert "object: capability" in out
    assert "capability: docker.availability" in out
    assert "capability: docker.resource.cpus" in out
    assert "status: supported" in out

    with sqlite3.connect(home / "alab.db") as conn:
        rows = conn.execute("SELECT capability_key, status FROM runtime_capabilities ORDER BY capability_key").fetchall()
    assert rows == [
        ("docker.availability", "supported"),
        ("docker.platform.linux", "supported"),
        ("docker.platform.linux/amd64", "supported"),
        ("docker.platform.linux/arm64", "supported"),
        ("docker.resource.cpus", "supported"),
        ("docker.resource.memory", "supported"),
    ]


def test_cache_prune_removes_alab_owned_docker_image(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-prune.jsonl"
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "rm"]:
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = next(line.split(": ", 1)[1] for line in capsys.readouterr().out.splitlines() if line.startswith("root key: "))
    now = utc_now()
    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute(
            """
            INSERT INTO cache_entries(cache_id, cache_kind, cache_key, project_id, path, docker_tag,
              size_bytes, status, metadata_json, created_at, last_used_at, removed_at)
            VALUES ('cache-test', 'docker_image', 'sha256:test', NULL, NULL, 'alab-cache:test',
              NULL, 'active', ?, ?, ?, NULL)
            """,
            (canonical_json({"schema_version": 1}), now, now),
        )

    assert run(["--home", str(home), "--key", root_key, "cache", "prune", "--docker-images"]) == 0
    out = capsys.readouterr().out

    assert "cache pruned count: 1" in out
    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert ["image", "rm", "alab-cache:test"] in calls
    with sqlite3.connect(home / "alab.db") as conn:
        row = conn.execute("SELECT status FROM cache_entries WHERE cache_id = 'cache-test'").fetchone()
    assert row == ("removed",)


def test_project_init_rejects_unsupported_docker_resource_limit(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    bin_dir = tmp_path / "bin"
    source.mkdir()
    bin_dir.mkdir()
    (source / "main.py").write_text("print('hello')\n", encoding="utf-8")
    config.write_text(
        """
schema_version = 1

[project]
name = "Docker Resource Project"
task = "Reject unsupported Docker resources"

[runner]
type = "docker"
timeout_seconds = 30
working_directory = "."
image = "example:latest"
command = ["python", "main.py"]
cpus = 1.0

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args[:1] == ["version"]:
    print(json.dumps({"Client": {"Version": "fake-client"}, "Server": {"Version": "fake-server"}}))
    raise SystemExit(0)
if args[:1] == ["info"]:
    print(json.dumps({"OSType": "linux", "Architecture": "amd64"}))
    raise SystemExit(0)
if args[:2] == ["run", "--help"]:
    print("Usage: docker run [OPTIONS] IMAGE [COMMAND]\\n      --memory bytes")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = next(line.split(": ", 1)[1] for line in capsys.readouterr().out.splitlines() if line.startswith("root key: "))

    status = run(
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
    err = capsys.readouterr().err

    assert status == 2
    assert "runner.cpus is not supported" in err
    with sqlite3.connect(home / "alab.db") as conn:
        project_count = conn.execute("SELECT count(*) FROM projects").fetchone()[0]
    assert project_count == 0


def test_project_init_rejects_unsupported_docker_platform_architecture(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    bin_dir = tmp_path / "bin"
    source.mkdir()
    bin_dir.mkdir()
    (source / "main.py").write_text("print('hello')\n", encoding="utf-8")
    config.write_text(
        """
schema_version = 1

[project]
name = "Docker Platform Project"
task = "Reject unsupported Docker platform"

[runner]
type = "docker"
timeout_seconds = 30
working_directory = "."
image = "example:latest"
command = ["python", "main.py"]
platform = "linux/arm64"

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args[:1] == ["version"]:
    print(json.dumps({"Client": {"Version": "fake-client"}, "Server": {"Version": "fake-server"}}))
    raise SystemExit(0)
if args[:1] == ["info"]:
    print(json.dumps({"OSType": "linux", "Architecture": "amd64"}))
    raise SystemExit(0)
if args[:2] == ["buildx", "ls"]:
    print("default * docker running linux/amd64")
    raise SystemExit(0)
if args[:2] == ["run", "--help"]:
    print("Usage: docker run [OPTIONS] IMAGE [COMMAND]\\n      --cpus float\\n      --memory bytes")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = next(line.split(": ", 1)[1] for line in capsys.readouterr().out.splitlines() if line.startswith("root key: "))

    status = run(
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
    err = capsys.readouterr().err

    assert status == 2
    assert "runner.platform linux/arm64 is not supported" in err
    with sqlite3.connect(home / "alab.db") as conn:
        project_count = conn.execute("SELECT count(*) FROM projects").fetchone()[0]
    assert project_count == 0


def test_docker_platform_probe_uses_native_architecture_when_buildx_unavailable(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args[:1] == ["version"]:
    print(json.dumps({"Client": {"Version": "fake-client"}, "Server": {"Version": "fake-server"}}))
    raise SystemExit(0)
if args[:1] == ["info"]:
    print(json.dumps({"OSType": "linux", "Architecture": "aarch64"}))
    raise SystemExit(0)
if args[:2] == ["buildx", "ls"]:
    print("buildx unavailable", file=sys.stderr)
    raise SystemExit(2)
if args[:2] == ["run", "--help"]:
    print("Usage: docker run [OPTIONS] IMAGE [COMMAND]\\n      --cpus float\\n      --memory bytes")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    assert run(["--home", str(home), "auth", "init"]) == 0
    capsys.readouterr()

    assert run(["--home", str(home), "config", "validate", "--refresh-capabilities"]) == 0
    out = capsys.readouterr().out
    assert "capability: docker.platform.linux/arm64" in out
    with sqlite3.connect(home / "alab.db") as conn:
        rows = dict(conn.execute("SELECT capability_key, status FROM runtime_capabilities").fetchall())
        details = {
            key: json.loads(value)
            for key, value in conn.execute("SELECT capability_key, details_json FROM runtime_capabilities").fetchall()
        }

    assert rows["docker.platform.linux/arm64"] == "supported"
    assert rows["docker.platform.linux/amd64"] == "unsupported"
    assert details["docker.platform.linux/arm64"]["probed_values"]["supported_platforms"] == ["linux/arm64"]
    assert details["docker.platform.linux/amd64"]["probed_values"]["buildx_available"] is False


def test_project_init_records_docker_unavailable_baseline_error(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    source.mkdir()
    (source / "main.py").write_text("print('hello')\n", encoding="utf-8")
    config.write_text(
        """
schema_version = 1

[project]
name = "Docker Missing Project"
task = "Record Docker unavailable baseline"

[runner]
type = "docker"
timeout_seconds = 30
working_directory = "."
image = "example:latest"
command = ["python", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    def missing_docker(_args, *, timeout=None):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(runner_mod, "_run_docker_cli", missing_docker)

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = next(line.split(": ", 1)[1] for line in capsys.readouterr().out.splitlines() if line.startswith("root key: "))

    status = run(
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
    out = capsys.readouterr().out

    assert status == 1
    assert _field_labels(out) == _project_init_field_labels(failure=True)
    assert "project status: invalid" in out
    assert "validation status: error" in out
    assert "error code: BASELINE_VALIDATION_FAILED" in out
    assert "exit code: 1" in out
    assert "reason: baseline validation status is error" in out
    project_id = next(line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("project id: "))
    validation_id = next(line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("validation id: "))
    with sqlite3.connect(home / "alab.db") as conn:
        project = conn.execute(
            "SELECT status, active_valid_config_version FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        validation = conn.execute(
            "SELECT status, exit_code, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (validation_id,),
        ).fetchone()
        logs = conn.execute(
            "SELECT stream, preview_text FROM log_streams WHERE validation_id = ? ORDER BY stream",
            (validation_id,),
        ).fetchall()

    assert project == ("invalid", None)
    assert validation[0] == "error"
    assert validation[1] is None
    assert validation[2] == "not_attempted"
    assert json.loads(validation[3])["failure"] == "docker executable not found"
    assert ("stderr", "docker executable not found") in logs


def test_docker_unavailable_run_is_saved_result_failure(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    bin_dir = tmp_path / "bin"
    worktree = tmp_path / "exp"
    source.mkdir()
    bin_dir.mkdir()
    (source / "main.py").write_text("print('hello')\n", encoding="utf-8")
    config.write_text(
        """
schema_version = 1

[project]
name = "Docker Missing Run Project"
task = "Record Docker unavailable run"

[runner]
type = "docker"
timeout_seconds = 30
working_directory = "."
image = "example:latest"
command = ["python", "main.py"]

[reward]
type = "stdout_regex"
direction = "maximize"
primary_metric = "reward"
pattern = "reward=([0-9.]+)"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import sys

args = sys.argv[1:]
if args[:2] == ["image", "inspect"]:
    print("[]")
    raise SystemExit(0)
if args and args[0] == "run":
    print("reward=5")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels(warning_count=1)
    assert "warning code: DOCKER_SETUP_OUTPUT_CAPTURED" in project_out
    assert "project status: valid" in project_out
    project_id = _field(project_out, "project id")
    assert run(["--home", str(home), "--key", root_key, "exp", "create", "--project", project_id, "--name", "docker unavailable run", "--path", str(worktree)]) == 0
    capsys.readouterr()

    def missing_docker(_args, *, timeout=None):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(runner_mod, "_run_docker_cli", missing_docker)
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "docker unavailable run"]) == 1
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels(failure=True)
    assert "run status: error" in run_out
    assert "exit code: none" in run_out
    assert "reward parse status: not_attempted" in run_out
    assert "stderr preview: docker executable not found" in run_out
    assert "error code: RUNNER_ERROR" in run_out
    assert "reason: docker executable not found" in run_out
    run_id = _field(run_out, "run id")
    with sqlite3.connect(home / "alab.db") as conn:
        run_record = conn.execute(
            "SELECT status, exit_code, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        run_logs = conn.execute(
            "SELECT stream, preview_text FROM log_streams WHERE run_id = ? ORDER BY stream",
            (run_id,),
        ).fetchall()
    assert run_record[:3] == ("error", None, "not_attempted")
    assert json.loads(run_record[3])["failure"] == "docker executable not found"
    assert ("stderr", "docker executable not found") in run_logs


def test_docker_setup_pull_and_build_failures_are_saved_result_failures(tmp_path, monkeypatch, capsys) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import os
import sys

mode = os.environ["FAKE_DOCKER_MODE"]
args = sys.argv[1:]
if args[:2] == ["image", "inspect"]:
    raise SystemExit(0 if mode == "image-ok" else 1)
if args and args[0] == "pull":
    print(f"{mode} pull stdout")
    print(f"{mode} pull stderr", file=sys.stderr)
    raise SystemExit(0 if mode == "pull-ok" else 21)
if args and args[0] == "build":
    print(f"{mode} build stdout")
    print(f"{mode} build stderr", file=sys.stderr)
    raise SystemExit(0 if mode == "build-ok" else 23)
if args and args[0] == "run":
    print("reward=11")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    def write_config(path: Path, *, name: str, use_image: bool) -> None:
        runner_source = (
            'image = "example:missing"\n'
            if use_image
            else 'dockerfile = "Dockerfile"\ncontext = "."\n'
        )
        path.write_text(
            f"""
schema_version = 1

[project]
name = {json.dumps(name)}
task = "Persist Docker setup failures"

[runner]
type = "docker"
timeout_seconds = 30
working_directory = "."
{runner_source}command = ["python", "main.py"]

[reward]
type = "stdout_regex"
direction = "maximize"
primary_metric = "reward"
pattern = "reward=([0-9.]+)"
""".strip()
            + "\n",
            encoding="utf-8",
        )

    def make_source(path: Path, *, dockerfile: bool) -> None:
        path.mkdir()
        (path / "main.py").write_text("print('unused')\n", encoding="utf-8")
        if dockerfile:
            (path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    def assert_saved_validation_failure(home: Path, validation_id: str, reason: str, setup_marker: str) -> None:
        with sqlite3.connect(home / "alab.db") as conn:
            validation = conn.execute(
                "SELECT status, exit_code, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
                (validation_id,),
            ).fetchone()
            logs = conn.execute(
                "SELECT stream, preview_text, hidden FROM log_streams WHERE validation_id = ? ORDER BY stream",
                (validation_id,),
            ).fetchall()
        assert validation[:3] == ("error", None, "not_attempted")
        assert json.loads(validation[3])["failure"] == reason
        assert ("stderr", reason, 0) in logs
        assert any(stream == "hidden_stdout" and setup_marker in preview and hidden == 1 for stream, preview, hidden in logs)
        assert any(stream == "hidden_stderr" and setup_marker in preview and hidden == 1 for stream, preview, hidden in logs)

    def assert_saved_run_failure(home: Path, run_id: str, reason: str, setup_marker: str) -> None:
        with sqlite3.connect(home / "alab.db") as conn:
            run_record = conn.execute(
                "SELECT status, exit_code, reward_parse_status, record_json FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            logs = conn.execute(
                "SELECT stream, preview_text, hidden FROM log_streams WHERE run_id = ? ORDER BY stream",
                (run_id,),
            ).fetchall()
        assert run_record[:3] == ("error", None, "not_attempted")
        assert json.loads(run_record[3])["failure"] == reason
        assert ("stderr", reason, 0) in logs
        assert any(stream == "hidden_stdout" and setup_marker in preview and hidden == 1 for stream, preview, hidden in logs)
        assert any(stream == "hidden_stderr" and setup_marker in preview and hidden == 1 for stream, preview, hidden in logs)

    baseline_cases = [
        ("pull", True, "pull-fail", "docker pull failed", "pull-fail pull"),
        ("build", False, "build-fail", "docker build failed", "build-fail build"),
    ]
    for name, use_image, mode, reason, setup_marker in baseline_cases:
        home = tmp_path / f"baseline-{name}-home"
        source = tmp_path / f"baseline-{name}-source"
        config = tmp_path / f"baseline-{name}.toml"
        make_source(source, dockerfile=not use_image)
        write_config(config, name=f"Docker {name} baseline failure", use_image=use_image)
        monkeypatch.setenv("FAKE_DOCKER_MODE", mode)
        assert run(["--home", str(home), "auth", "init"]) == 0
        root_key = _field(capsys.readouterr().out, "root key")
        assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 1
        project_out = capsys.readouterr().out
        assert _field_labels(project_out) == _project_init_field_labels(failure=True)
        assert "project status: invalid" in project_out
        assert "validation status: error" in project_out
        assert "error code: BASELINE_VALIDATION_FAILED" in project_out
        assert "exit code: 1" in project_out
        assert "reason: baseline validation status is error" in project_out
        assert_saved_validation_failure(home, _field(project_out, "validation id"), reason, setup_marker)

    run_cases = [
        ("pull", True, "image-ok", "pull-fail", "docker pull failed", "pull-fail pull"),
        ("build", False, "build-ok", "build-fail", "docker build failed", "build-fail build"),
    ]
    for name, use_image, init_mode, run_mode, reason, setup_marker in run_cases:
        home = tmp_path / f"run-{name}-home"
        source = tmp_path / f"run-{name}-source"
        config = tmp_path / f"run-{name}.toml"
        worktree = tmp_path / f"run-{name}-exp"
        make_source(source, dockerfile=not use_image)
        write_config(config, name=f"Docker {name} run failure", use_image=use_image)
        monkeypatch.setenv("FAKE_DOCKER_MODE", init_mode)
        assert run(["--home", str(home), "auth", "init"]) == 0
        root_key = _field(capsys.readouterr().out, "root key")
        assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
        project_out = capsys.readouterr().out
        assert "project status: valid" in project_out
        project_id = _field(project_out, "project id")
        assert run(["--home", str(home), "--key", root_key, "exp", "create", "--project", project_id, "--name", f"Docker {name} run failure", "--path", str(worktree)]) == 0
        capsys.readouterr()
        monkeypatch.chdir(worktree)
        monkeypatch.setenv("FAKE_DOCKER_MODE", run_mode)
        assert run(["--home", str(home), "run", "--message", f"docker {name} setup failure"]) == 1
        run_out = capsys.readouterr().out
        assert _field_labels(run_out) == _run_field_labels(failure=True)
        assert "run status: error" in run_out
        assert "exit code: none" in run_out
        assert "reward parse status: not_attempted" in run_out
        assert "error code: RUNNER_ERROR" in run_out
        assert f"reason: {reason}" in run_out
        assert_saved_run_failure(home, _field(run_out, "run id"), reason, setup_marker)
        monkeypatch.chdir(tmp_path)


def test_missing_dockerfile_and_context_are_saved_baseline_and_run_errors(tmp_path, monkeypatch, capsys) -> None:
    baseline_home = tmp_path / "baseline-home"
    baseline_source = tmp_path / "baseline-source"
    baseline_config = tmp_path / "alab.missing-dockerfile.toml"
    baseline_source.mkdir()
    (baseline_source / "main.py").write_text("print('unused')\n", encoding="utf-8")
    baseline_config.write_text(
        """
schema_version = 1

[project]
name = "Missing Dockerfile Project"
task = "Persist missing Dockerfile baseline failure"

[runner]
type = "docker"
timeout_seconds = 30
working_directory = "."
dockerfile = "Dockerfile"
context = "."
command = ["python", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(baseline_home), "auth", "init"]) == 0
    baseline_root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(baseline_home), "--key", baseline_root_key, "project", "init", "local", "--config", str(baseline_config), "--source-path", str(baseline_source)]) == 1
    baseline_out = capsys.readouterr().out
    assert _field_labels(baseline_out) == _project_init_field_labels(failure=True)
    assert "project status: invalid" in baseline_out
    assert "validation status: error" in baseline_out
    assert "error code: BASELINE_VALIDATION_FAILED" in baseline_out
    assert "exit code: 1" in baseline_out
    assert "reason: baseline validation status is error" in baseline_out
    baseline_validation_id = _field(baseline_out, "validation id")
    with sqlite3.connect(baseline_home / "alab.db") as conn:
        baseline_validation = conn.execute(
            "SELECT status, exit_code, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (baseline_validation_id,),
        ).fetchone()
        baseline_logs = conn.execute(
            "SELECT stream, preview_text FROM log_streams WHERE validation_id = ? ORDER BY stream",
            (baseline_validation_id,),
        ).fetchall()
    assert baseline_validation[:3] == ("error", None, "not_attempted")
    assert json.loads(baseline_validation[3])["failure"] == "runner.dockerfile does not exist or is not a file"
    assert ("stderr", "runner.dockerfile does not exist or is not a file") in baseline_logs

    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.missing-docker-context.toml"
    bin_dir = tmp_path / "bin"
    docker_context = source / "docker-context"
    source.mkdir()
    docker_context.mkdir()
    bin_dir.mkdir()
    (docker_context / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (source / "main.py").write_text("print('unused')\n", encoding="utf-8")
    config.write_text(
        """
schema_version = 1

[project]
name = "Missing Docker Context Project"
task = "Persist missing Docker context run failure"

[runner]
type = "docker"
timeout_seconds = 30
working_directory = "."
dockerfile = "docker-context/Dockerfile"
context = "docker-context"
command = ["python", "main.py"]

[reward]
type = "stdout_regex"
direction = "maximize"
primary_metric = "reward"
pattern = "reward=([0-9.]+)"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import sys

args = sys.argv[1:]
if args[:2] == ["image", "inspect"]:
    raise SystemExit(1)
if args and args[0] == "build":
    raise SystemExit(0)
if args and args[0] == "run":
    print("reward=13")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert "project status: valid" in project_out
    project_id = _field(project_out, "project id")

    worktree = tmp_path / "missing-docker-context-exp"
    assert run(["--home", str(home), "--key", root_key, "exp", "create", "--project", project_id, "--name", "missing docker context", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    shutil.rmtree(worktree / "docker-context")
    assert run(["--home", str(home), "run", "--message", "missing docker context"]) == 1
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels(failure=True)
    assert "run status: error" in run_out
    assert "exit code: none" in run_out
    assert "reward parse status: not_attempted" in run_out
    assert "error code: RUNNER_ERROR" in run_out
    assert "reason: runner.context does not exist or is not a directory" in run_out
    run_id = _field(run_out, "run id")
    with sqlite3.connect(home / "alab.db") as conn:
        run_record = conn.execute(
            "SELECT status, exit_code, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        run_logs = conn.execute(
            "SELECT stream, preview_text FROM log_streams WHERE run_id = ? ORDER BY stream",
            (run_id,),
        ).fetchall()
    assert run_record[:3] == ("error", None, "not_attempted")
    assert json.loads(run_record[3])["failure"] == "runner.context does not exist or is not a directory"
    assert ("stderr", "runner.context does not exist or is not a directory") in run_logs

    assert run(["--home", str(home), "submit", "--message", "missing docker context submit", "--summary", "done", "--feedback", "ok", "--ref", "none", "--rerun"]) == 1
    submit_out = capsys.readouterr().out
    assert _field_labels(submit_out) == _submission_failure_field_labels()
    submit_exp_id = _field(submit_out, "exp id")
    assert "submit accepted: false" in submit_out
    assert "final run id: none" in submit_out
    assert "experiment status: open" in submit_out
    assert "summary stored: false" in submit_out
    assert "feedback stored: false" in submit_out
    assert "error code: RUNNER_ERROR" in submit_out
    assert "exit code: 1" in submit_out
    assert "reason: final run " in submit_out
    assert "status is error: runner.context does not exist or is not a directory" in submit_out
    submit_run_match = re.search(r"reason: final run (run-[^ ]+) status is error", submit_out)
    assert submit_run_match is not None
    submit_run_id = submit_run_match.group(1)
    with sqlite3.connect(home / "alab.db") as conn:
        experiment_row = conn.execute(
            "SELECT status, final_run_id, final_commit FROM experiments WHERE exp_id = ?",
            (submit_exp_id,),
        ).fetchone()
        submission_count = conn.execute(
            "SELECT COUNT(*) FROM experiment_submissions WHERE exp_id = ?",
            (submit_exp_id,),
        ).fetchone()[0]
        submit_run_record = conn.execute(
            "SELECT status, exit_code, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (submit_run_id,),
        ).fetchone()
    assert experiment_row == ("open", None, None)
    assert submission_count == 0
    assert submit_run_record[:3] == ("error", None, "not_attempted")
    assert json.loads(submit_run_record[3])["failure"] == "runner.context does not exist or is not a directory"
