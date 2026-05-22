from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import uuid
from pathlib import Path

import pytest

from alab.cli import run
from alab.configs import ProjectConfig
from alab.runner import run_configured_runner

pytestmark = pytest.mark.real_docker


@pytest.fixture(autouse=True)
def _isolated_docker_config(tmp_path, monkeypatch) -> None:
    if "DOCKER_CONFIG" in os.environ:
        return
    docker_config = tmp_path / "docker-config"
    docker_config.mkdir()
    monkeypatch.setenv("DOCKER_CONFIG", str(docker_config))


def _docker(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["docker", *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _field(output: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}: (.+)$", output, re.MULTILINE)
    assert match, output
    return match.group(1)


def _field_labels(output: str) -> list[str]:
    labels: list[str] = []
    for line in output.splitlines():
        if not line or line.startswith("  "):
            continue
        label, _, _value = line.partition(":")
        labels.append(label)
    return labels


def _require_real_docker_image(image: str) -> None:
    if os.environ.get("ALAB_RUN_REAL_DOCKER", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("set ALAB_RUN_REAL_DOCKER=1 to run real Docker integration tests")
    try:
        version = _docker(["version"], timeout=10)
    except FileNotFoundError:
        pytest.skip("docker executable is not available")
    except subprocess.TimeoutExpired:
        pytest.skip("docker version timed out")
    if version.returncode != 0:
        reason = (version.stderr or version.stdout).decode("utf-8", errors="replace").strip()
        pytest.skip(f"docker daemon is not available: {reason}")
    inspect = _docker(["image", "inspect", image], timeout=30)
    if inspect.returncode == 0:
        return
    pull = _docker(["pull", image], timeout=180)
    if pull.returncode != 0:
        reason = (pull.stderr or pull.stdout).decode("utf-8", errors="replace").strip()
        pytest.skip(f"docker image {image} is not available and pull failed: {reason}")


def _harbor_resolver(task_dir: Path):
    return lambda ref: {
        "ref": ref,
        "relative_path": task_dir.name,
        "target_kind": "harbor_task",
        "pinned_commit": "c" * 40,
        "target_path": str(task_dir),
    }


def _skydiscover_docker_resolver(evaluator_dir: Path):
    return lambda ref: {
        "ref": ref,
        "relative_path": "benchmarks/real-docker",
        "target_kind": "skydiscover_docker_evaluator",
        "pinned_commit": "d" * 40,
        "target_path": str(evaluator_dir),
    }


def test_real_docker_runner_mount_env_and_reward(tmp_path) -> None:
    image = "alpine:3.20"
    _require_real_docker_image(image)
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Real Docker Project", "task": "Run a real Docker container"},
            "runner": {
                "type": "docker",
                "timeout_seconds": 30,
                "working_directory": ".",
                "image": image,
                "network": "none",
                "command": [
                    "sh",
                    "-c",
                    "test \"$ALAB_WORKSPACE\" = /app && test \"$ALAB_RUN_DIR\" = /logs/alab && printf 'artifact bytes' > \"$ALAB_RUN_DIR/result.txt\" && echo reward=9",
                ],
            },
            "reward": {
                "type": "stdout_regex",
                "direction": "maximize",
                "primary_metric": "reward",
                "pattern": "reward=([0-9.]+)",
            },
        }
    )

    result = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-docker",
        secrets={},
    )

    assert result.status == "passed"
    assert result.reward == 9.0
    assert (run_dir / "result.txt").read_text(encoding="utf-8") == "artifact bytes"


def test_real_docker_runner_shell_mode_uses_container_sh(tmp_path) -> None:
    image = "alpine:3.20"
    _require_real_docker_image(image)
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {
                "name": "Real Docker Shell Project",
                "task": "Run a real Docker shell-mode container",
            },
            "runner": {
                "type": "docker",
                "timeout_seconds": 30,
                "working_directory": ".",
                "image": image,
                "network": "none",
                "command": None,
                "shell": "test \"$ALAB_WORKSPACE\" = /app && test \"$ALAB_RUN_DIR\" = /logs/alab && printf shell-ok > \"$ALAB_RUN_DIR/shell.txt\" && echo reward=4.25",
            },
            "reward": {
                "type": "stdout_regex",
                "direction": "maximize",
                "primary_metric": "reward",
                "pattern": "reward=([0-9.]+)",
            },
        }
    )

    result = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-docker-shell",
        secrets={},
    )

    assert result.status == "passed"
    assert result.reward == 4.25
    assert result.cache_metadata is None
    assert (run_dir / "shell.txt").read_text(encoding="utf-8") == "shell-ok"


def test_real_docker_runner_env_is_hostless_and_internal_env_wins(tmp_path, monkeypatch) -> None:
    image = "alpine:3.20"
    _require_real_docker_image(image)
    monkeypatch.setenv("HOST_ONLY_VALUE", "host-only")
    monkeypatch.setenv("ALAB_KEY", "host-alab-key")
    monkeypatch.setenv("ALAB_TOKEN", "host-alab-token")
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {
                "name": "Real Docker Env Project",
                "task": "Verify real Docker environment isolation",
            },
            "runner": {
                "type": "docker",
                "timeout_seconds": 30,
                "working_directory": ".",
                "image": image,
                "network": "none",
                "command": [
                    "sh",
                    "-c",
                    "test -z \"${HOST_ONLY_VALUE+x}\" && test -z \"${ALAB_KEY+x}\" && test -z \"${ALAB_TOKEN+x}\" && test \"$ALAB_PROJECT_ID\" = proj-real && test \"$ALAB_EXP_ID\" = exp-real && test \"$ALAB_RUN_ID\" = real-docker-env && test \"$ALAB_CONFIG_VERSION\" = 7 && test \"$ALAB_WORKSPACE\" = /app && test \"$ALAB_RUN_DIR\" = /logs/alab && test \"$VISIBLE\" = 1 && test \"$SECRET\" = real-docker-secret && echo reward=3.5",
                ],
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
            "reward": {
                "type": "stdout_regex",
                "direction": "maximize",
                "primary_metric": "reward",
                "pattern": "reward=([0-9.]+)",
            },
        }
    )

    result = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-docker-env",
        secrets={"SECRET": "real-docker-secret"},
        project_id="proj-real",
        exp_id="exp-real",
        config_version=7,
    )

    assert result.status == "passed"
    assert result.reward == 3.5
    assert b"real-docker-secret" not in result.stdout


def test_real_docker_runner_dockerfile_build_context_and_cache(tmp_path) -> None:
    image = "alpine:3.20"
    _require_real_docker_image(image)
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    build_token = uuid.uuid4().hex
    (workspace / "Dockerfile").write_text(
        f"""
FROM {image}
COPY . /image-context
RUN test "$(cat /image-context/build-marker.txt)" = "{build_token}"
RUN test ! -e /image-context/ignored.txt
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (workspace / ".dockerignore").write_text("ignored.txt\n", encoding="utf-8")
    (workspace / "build-marker.txt").write_text(build_token, encoding="utf-8")
    (workspace / "ignored.txt").write_text("must stay out of the image context\n", encoding="utf-8")
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {
                "name": "Real Dockerfile Project",
                "task": "Build and cache a real Dockerfile runner image",
            },
            "runner": {
                "type": "docker",
                "timeout_seconds": 60,
                "working_directory": ".",
                "dockerfile": "Dockerfile",
                "context": ".",
                "network": "none",
                "command": [
                    "sh",
                    "-c",
                    "test \"$ALAB_WORKSPACE\" = /app && test \"$ALAB_RUN_DIR\" = /logs/alab && test -f /image-context/main.py && test ! -e /image-context/ignored.txt && test \"$(cat /image-context/build-marker.txt)\" = \"$(cat /app/build-marker.txt)\" && echo reward=5.5",
                ],
            },
            "reward": {
                "type": "stdout_regex",
                "direction": "maximize",
                "primary_metric": "reward",
                "pattern": "reward=([0-9.]+)",
            },
        }
    )

    first = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-dockerfile-1",
        secrets={},
    )
    second = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-dockerfile-2",
        secrets={},
    )

    assert first.status == "passed"
    assert first.reward == 5.5
    assert first.cache_metadata is not None
    assert first.cache_metadata["cache_kind"] == "docker_image"
    assert first.cache_metadata["status"] == "built"
    assert "DOCKER_SETUP_OUTPUT_CAPTURED" in first.warning_codes
    assert second.status == "passed"
    assert second.reward == 5.5
    assert second.cache_metadata is not None
    assert second.cache_metadata["cache_kind"] == "docker_image"
    assert second.cache_metadata["cache_key"] == first.cache_metadata["cache_key"]
    assert second.cache_metadata["docker_tag"] == first.cache_metadata["docker_tag"]
    assert second.cache_metadata["status"] == "hit"


def test_real_docker_cli_project_run_workflow(tmp_path, monkeypatch, capsys) -> None:
    image = "alpine:3.20"
    _require_real_docker_image(image)
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config = tmp_path / "alab.docker.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Real Docker CLI Project"
task = "Run Docker through the CLI workflow"
allow_public_exp_create = true

[runner]
type = "docker"
timeout_seconds = 30
working_directory = "."
image = "{image}"
network = "none"
command = ["sh", "-c", "test \\"$ALAB_WORKSPACE\\" = /app && test \\"$ALAB_RUN_DIR\\" = /logs/alab && test -f /app/main.py && printf 'cli artifact bytes' > /logs/alab/cli-artifact.txt && echo reward=8.75"]

[reward]
type = "stdout_regex"
direction = "maximize"
primary_metric = "reward"
pattern = "reward=([0-9.]+)"

[artifacts]
globs = ["run:cli-artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == [
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
        "warning code",
        "next",
    ]
    assert "project status: valid" in project_out
    assert "validation status: passed" in project_out
    assert "warning code: DOCKER_SETUP_OUTPUT_CAPTURED" in project_out
    project_id = _field(project_out, "project id")
    validation_id = _field(project_out, "validation id")

    worktree = tmp_path / "real-docker-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "real-docker-run", "--path", str(worktree)]) == 0
    exp_out = capsys.readouterr().out
    assert _field_labels(exp_out) == [
        "object",
        "project id",
        "exp id",
        "experiment name",
        "source id",
        "branch",
        "worktree path",
        "token path",
        "config version",
        "next",
    ]
    exp_id = _field(exp_out, "exp id")

    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "real docker cli"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == [
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
        "warning code",
        "next",
    ]
    assert "run status: passed" in run_out
    assert "reward: 8.75" in run_out
    assert "artifact count: 1" in run_out
    assert "warning code: DOCKER_SETUP_OUTPUT_CAPTURED" in run_out
    run_id = _field(run_out, "run id")

    with sqlite3.connect(home / "alab.db") as conn:
        validation = conn.execute(
            "SELECT status, reward_value, reward_parse_status FROM project_validations WHERE validation_id = ?",
            (validation_id,),
        ).fetchone()
        run_row = conn.execute(
            "SELECT status, reward_value, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        artifact = conn.execute(
            "SELECT relative_path, status, blob_path FROM artifacts WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        stdout_preview = conn.execute(
            "SELECT preview_text FROM log_streams WHERE run_id = ? AND stream = 'stdout'",
            (run_id,),
        ).fetchone()[0]
    assert validation == ("passed", 8.75, "parsed")
    assert run_row[0:3] == ("passed", 8.75, "parsed")
    assert "DOCKER_SETUP_OUTPUT_CAPTURED" in run_row[3]
    assert artifact[0:2] == ("cli-artifact.txt", "captured")
    assert (home / "projects" / project_id / "artifacts" / artifact[2]).read_text(encoding="utf-8") == "cli artifact bytes"
    assert "reward=8.75" in stdout_preview
    assert exp_id in run_out


def test_real_harbor_runner_shared_verifier(tmp_path, monkeypatch) -> None:
    image = "alpine:3.20"
    _require_real_docker_image(image)
    monkeypatch.setenv("HOST_ONLY_VALUE", "host-only")
    monkeypatch.setenv("ALAB_KEY", "host-alab-key")
    monkeypatch.setenv("ALAB_TOKEN", "host-alab-token")
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    task_dir = tmp_path / "harbor-task"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test.sh").write_text(
        """
#!/bin/sh
set -eu
test -z "${HOST_ONLY_VALUE+x}"
test -z "${ALAB_KEY+x}"
test -z "${ALAB_TOKEN+x}"
test "$ALAB_PROJECT_ID" = proj-real-harbor
test "$ALAB_EXP_ID" = exp-real-harbor
test "$ALAB_RUN_ID" = real-harbor
test "$ALAB_CONFIG_VERSION" = 11
test "$ALAB_WORKSPACE" = /workspace
test "$ALAB_RUN_DIR" = /logs/alab
test "$ALAB_HARBOR_TASK_DIR" = /alab/harbor
test "$VISIBLE" = 1
test "$HARBOR_SECRET" = real-harbor-task-secret
test "$SECRET" = real-harbor-external-secret
test -f /workspace/main.py
mkdir -p /logs/alab/logs/verifier
printf '{"reward":6.5,"checks":1}' > /logs/alab/logs/verifier/reward.json
echo "real harbor verifier ok $HARBOR_SECRET $SECRET"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        f"""
[environment]
image = "{image}"
allow_internet = false

[environment.env]
HARBOR_SECRET = "real-harbor-task-secret"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Real Harbor Project", "task": "Run a real Harbor verifier"},
            "runner": {
                "type": "harbor",
                "timeout_seconds": 30,
                "working_directory": ".",
                "harbor_task_ref": "harbor-real",
            },
            "env": {
                "ALAB_PROJECT_ID": "user-project",
                "ALAB_EXP_ID": "user-exp",
                "ALAB_RUN_ID": "user-run",
                "ALAB_CONFIG_VERSION": "user-version",
                "ALAB_WORKSPACE": "/user-workspace",
                "ALAB_RUN_DIR": "/user-run-dir",
                "ALAB_HARBOR_TASK_DIR": "/user-harbor",
                "VISIBLE": "1",
            },
            "reward": {"type": "harbor", "direction": "maximize", "primary_metric": "reward"},
        }
    )

    result = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-harbor",
        secrets={"SECRET": "real-harbor-external-secret"},
        project_id="proj-real-harbor",
        exp_id="exp-real-harbor",
        config_version=11,
        hidden_dir=hidden_dir,
        adapter_resolver=_harbor_resolver(task_dir),
    )

    assert result.status == "passed"
    assert result.reward == 6.5
    assert result.metrics["checks"] == 1
    assert b"Harbor verifier completed" in result.stdout
    assert b"real harbor verifier ok" in result.hidden_stdout
    assert b"real-harbor-task-secret" not in result.hidden_stdout
    assert b"real-harbor-external-secret" not in result.hidden_stdout
    assert b"[REDACTED]" in result.hidden_stdout


def test_real_harbor_runner_separate_verifier_image(tmp_path) -> None:
    image = "alpine:3.20"
    _require_real_docker_image(image)
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    task_dir = tmp_path / "harbor-separate-image-task"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test.sh").write_text(
        """
#!/bin/sh
set -eu
test "$ALAB_WORKSPACE" = /workspace
test "$ALAB_RUN_DIR" = /logs/alab
test "$ALAB_HARBOR_TASK_DIR" = /alab/harbor
test -f /workspace/main.py
mkdir -p /logs/alab/logs/verifier
printf '6.75' > /logs/alab/logs/verifier/reward.txt
echo "real harbor separate image verifier ok"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        f"""
[environment]
allow_internet = false

[verifier]
image = "{image}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Real Harbor Separate Image", "task": "Run a separate Harbor verifier image"},
            "runner": {
                "type": "harbor",
                "timeout_seconds": 30,
                "working_directory": ".",
                "harbor_task_ref": "harbor-real-separate-image",
            },
            "reward": {"type": "harbor", "direction": "maximize", "primary_metric": "reward"},
        }
    )

    result = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-harbor-separate-image",
        secrets={},
        hidden_dir=hidden_dir,
        adapter_resolver=_harbor_resolver(task_dir),
    )

    assert result.status == "passed"
    assert result.reward == 6.75
    assert result.metrics["reward"] == 6.75
    assert result.adapter_feedback["verifier_mode"] == "separate"
    assert result.cache_metadata is None
    assert b"verifier mode: separate" in result.stdout
    assert b"real harbor separate image verifier ok" in result.hidden_stdout


def test_real_harbor_runner_separate_verifier_tests_dockerfile(tmp_path) -> None:
    image = "alpine:3.20"
    _require_real_docker_image(image)
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    task_dir = tmp_path / "harbor-tests-dockerfile-task"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "Dockerfile").write_text(f"FROM {image}\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text(
        """
#!/bin/sh
set -eu
test "$ALAB_WORKSPACE" = /workspace
test "$ALAB_RUN_DIR" = /logs/alab
test -f /alab/harbor/tests/Dockerfile
test -f /workspace/main.py
mkdir -p /logs/alab/logs/verifier
printf '{"reward":7.0,"checks":2}' > /logs/alab/logs/verifier/reward.json
echo "real harbor tests dockerfile verifier ok"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        """
[environment]
allow_internet = false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {
                "name": "Real Harbor Tests Dockerfile",
                "task": "Build and run a separate Harbor tests Dockerfile",
            },
            "runner": {
                "type": "harbor",
                "timeout_seconds": 60,
                "working_directory": ".",
                "harbor_task_ref": "harbor-real-tests-dockerfile",
            },
            "reward": {"type": "harbor", "direction": "maximize", "primary_metric": "reward"},
        }
    )

    result = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-harbor-tests-dockerfile",
        secrets={},
        hidden_dir=hidden_dir,
        adapter_resolver=_harbor_resolver(task_dir),
    )
    cached = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-harbor-tests-dockerfile-cached",
        secrets={},
        hidden_dir=hidden_dir,
        adapter_resolver=_harbor_resolver(task_dir),
    )

    assert result.status == "passed"
    assert result.reward == 7.0
    assert result.metrics["checks"] == 2
    assert result.adapter_feedback["verifier_mode"] == "separate"
    assert result.cache_metadata is not None
    assert result.cache_metadata["cache_kind"] == "docker_image"
    assert result.cache_metadata["adapter"] == "harbor"
    assert result.cache_metadata["verifier_mode"] == "separate"
    assert result.cache_metadata["status"] in {"built", "hit"}
    assert b"verifier mode: separate" in result.stdout
    assert b"real harbor tests dockerfile verifier ok" in result.hidden_stdout
    assert cached.status == "passed"
    assert cached.reward == 7.0
    assert cached.cache_metadata is not None
    assert cached.cache_metadata["cache_kind"] == "docker_image"
    assert cached.cache_metadata["adapter"] == "harbor"
    assert cached.cache_metadata["verifier_mode"] == "separate"
    assert cached.cache_metadata["status"] == "hit"


def test_real_skydiscover_docker_runner_evaluator(tmp_path, monkeypatch) -> None:
    image = "alpine:3.20"
    _require_real_docker_image(image)
    monkeypatch.setenv("HOST_ONLY_VALUE", "host-only")
    monkeypatch.setenv("ALAB_KEY", "host-alab-key")
    monkeypatch.setenv("ALAB_TOKEN", "host-alab-token")
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    evaluator = tmp_path / "catalog" / "benchmarks" / "real-docker"
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "Dockerfile").write_text(f"FROM {image}\n", encoding="utf-8")
    (evaluator / "evaluate.sh").write_text(
        """
#!/bin/sh
set -eu
test "$1" = /workspace
test -z "${HOST_ONLY_VALUE+x}"
test -z "${ALAB_KEY+x}"
test -z "${ALAB_TOKEN+x}"
test "$ALAB_PROJECT_ID" = proj-real-sky
test "$ALAB_EXP_ID" = exp-real-sky
case "$ALAB_RUN_ID" in
  real-sky-docker|real-sky-docker-cached) ;;
  *) exit 1 ;;
esac
test "$ALAB_CONFIG_VERSION" = 12
test "$ALAB_WORKSPACE" = /workspace
test "$ALAB_RUN_DIR" = /logs/alab
test "$ALAB_PROGRAM_PATH" = /workspace
test "$VISIBLE" = 1
test "$SKY_SECRET" = real-sky-secret
test -f "$1/main.py"
echo '{"combined_score":7.25,"checks":2}'
echo "real skydiscover docker evaluator ok $SKY_SECRET" >&2
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {
                "name": "Real SkyDiscover Docker",
                "task": "Run a real SkyDiscover Docker evaluator",
            },
            "runner": {
                "type": "skydiscover_docker",
                "timeout_seconds": 30,
                "working_directory": ".",
                "network": "none",
                "skydiscover_task_ref": "skydiscover:benchmarks/real-docker",
                "program_path": ".",
            },
            "env": {
                "ALAB_PROJECT_ID": "user-project",
                "ALAB_EXP_ID": "user-exp",
                "ALAB_RUN_ID": "user-run",
                "ALAB_CONFIG_VERSION": "user-version",
                "ALAB_WORKSPACE": "/user-workspace",
                "ALAB_RUN_DIR": "/user-run-dir",
                "ALAB_PROGRAM_PATH": "/user-program",
                "VISIBLE": "1",
            },
            "reward": {
                "type": "skydiscover",
                "direction": "maximize",
                "primary_metric": "combined_score",
            },
        }
    )

    result = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-sky-docker",
        secrets={"SKY_SECRET": "real-sky-secret"},
        project_id="proj-real-sky",
        exp_id="exp-real-sky",
        config_version=12,
        hidden_dir=hidden_dir,
        adapter_resolver=_skydiscover_docker_resolver(evaluator),
    )
    cached = run_configured_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-sky-docker-cached",
        secrets={"SKY_SECRET": "real-sky-secret"},
        project_id="proj-real-sky",
        exp_id="exp-real-sky",
        config_version=12,
        hidden_dir=hidden_dir,
        adapter_resolver=_skydiscover_docker_resolver(evaluator),
    )

    assert result.status == "passed"
    assert result.reward == 7.25
    assert result.metrics["checks"] == 2
    assert result.cache_metadata is not None
    assert result.cache_metadata["cache_kind"] == "docker_image"
    assert result.cache_metadata["adapter"] == "skydiscover_docker"
    assert result.cache_metadata["status"] in {"built", "hit"}
    assert b"SkyDiscover Docker evaluator completed" in result.stdout
    assert b"real skydiscover docker evaluator ok" in result.hidden_stderr
    assert b"real-sky-secret" not in result.stdout
    assert b"real-sky-secret" not in result.hidden_stderr
    assert b"[REDACTED]" in result.hidden_stderr
    assert cached.status == "passed"
    assert cached.reward == 7.25
    assert cached.cache_metadata is not None
    assert cached.cache_metadata["cache_kind"] == "docker_image"
    assert cached.cache_metadata["adapter"] == "skydiscover_docker"
    assert cached.cache_metadata["status"] == "hit"
