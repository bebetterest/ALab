from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from alab.configs import ProjectConfig, load_project_config
from alab.errors import AlabError
from alab.runner import capture_artifacts, parse_reward, run_local_runner


def test_sanitized_local_runner_creates_temp_home_and_strips_alab_credentials(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    monkeypatch.setenv("ALAB_KEY", "host-root-key")
    monkeypatch.setenv("ALAB_TOKEN", "host-token")
    monkeypatch.setenv("HOST_ONLY_VALUE", "not-in-sanitized-runner")
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Sanitized Runner", "task": "Check local runner environment"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "sanitized",
                "command": [
                    sys.executable,
                    "-c",
                    (
                        "import os, pathlib, sys\n"
                        "home = pathlib.Path(os.environ['HOME'])\n"
                        "print(f'home_exists={home.is_dir()}')\n"
                        "print(f'host_alab_key={os.environ.get(\"ALAB_KEY\", \"\")!r}')\n"
                        "print(f'host_alab_token={os.environ.get(\"ALAB_TOKEN\", \"\")!r}')\n"
                        "print(f'host_only={os.environ.get(\"HOST_ONLY_VALUE\", \"\")!r}')\n"
                        "print(f'internal_project={os.environ.get(\"ALAB_PROJECT_ID\", \"\")}')\n"
                        "sys.exit(0 if home.is_dir() and 'ALAB_KEY' not in os.environ and 'ALAB_TOKEN' not in os.environ and 'HOST_ONLY_VALUE' not in os.environ else 7)\n"
                    ),
                ],
            },
            "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
        }
    )

    result = run_local_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-local-env",
        secrets={},
        project_id="proj-local",
        exp_id="exp-local",
        config_version=1,
    )

    assert result.status == "passed"
    assert result.exit_code == 0
    assert (tmp_path / "home").is_dir()
    stdout = result.stdout.decode("utf-8")
    assert "home_exists=True" in stdout
    assert "host_alab_key=''" in stdout
    assert "host_alab_token=''" in stdout
    assert "host_only=''" in stdout
    assert "internal_project=proj-local" in stdout


def test_full_local_runner_strips_alab_credentials_and_internal_env_overrides(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    monkeypatch.setenv("ALAB_KEY", "host-root-key")
    monkeypatch.setenv("ALAB_TOKEN", "host-token")
    monkeypatch.setenv("HOST_ONLY_VALUE", "visible-host-value")
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Full Env Runner", "task": "Check full environment isolation"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "full",
                "command": [
                    sys.executable,
                    "-c",
                    (
                        "import os, sys\n"
                        "print(f'host_visible={os.environ.get(\"HOST_ONLY_VALUE\", \"\")!r}')\n"
                        "print(f'host_alab_key={os.environ.get(\"ALAB_KEY\", \"\")!r}')\n"
                        "print(f'host_alab_token={os.environ.get(\"ALAB_TOKEN\", \"\")!r}')\n"
                        "print(f'project={os.environ.get(\"ALAB_PROJECT_ID\", \"\")}')\n"
                        "print(f'run={os.environ.get(\"ALAB_RUN_ID\", \"\")}')\n"
                        "print(f'config={os.environ.get(\"ALAB_CONFIG_VERSION\", \"\")}')\n"
                        "ok = os.environ.get('HOST_ONLY_VALUE') == 'visible-host-value'\n"
                        "ok = ok and 'ALAB_KEY' not in os.environ and 'ALAB_TOKEN' not in os.environ\n"
                        "ok = ok and os.environ.get('ALAB_PROJECT_ID') == 'proj-full'\n"
                        "ok = ok and os.environ.get('ALAB_RUN_ID') == 'run-full'\n"
                        "ok = ok and os.environ.get('ALAB_CONFIG_VERSION') == '2'\n"
                        "sys.exit(0 if ok else 9)\n"
                    ),
                ],
            },
            "env": {
                "ALAB_PROJECT_ID": "user-project",
                "ALAB_RUN_ID": "user-run",
                "ALAB_CONFIG_VERSION": "user-config",
            },
            "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
        }
    )

    result = run_local_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-full",
        secrets={},
        project_id="proj-full",
        exp_id="exp-full",
        config_version=2,
    )

    assert result.status == "passed"
    assert result.exit_code == 0
    assert result.warning_codes == ["ENV_MODE_FULL_UNREDACTED_HOST_ENV"]
    stdout = result.stdout.decode("utf-8")
    assert "host_visible='visible-host-value'" in stdout
    assert "host_alab_key=''" in stdout
    assert "host_alab_token=''" in stdout
    assert "project=proj-full" in stdout
    assert "run=run-full" in stdout
    assert "config=2" in stdout


def test_local_runner_warns_when_secret_values_and_artifact_globs_are_configured(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Artifact Warning Runner", "task": "Warn about exact artifact bytes"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "none",
                "command": [
                    sys.executable,
                    "-c",
                    "print('reward=1')\n",
                ],
            },
            "reward": {"type": "stdout_regex", "direction": "maximize", "primary_metric": "reward", "pattern": "reward=([0-9.]+)"},
            "artifacts": {"globs": ["run:secret-artifact.txt"]},
        }
    )

    result = run_local_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-artifact-warning",
        secrets={"API_TOKEN": "artifact-secret"},
    )

    assert result.status == "passed"
    assert result.warning_codes == ["ARTIFACT_BYTES_NOT_REDACTED"]


def test_local_runner_stdin_is_closed(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Closed Stdin Runner", "task": "Check runner stdin"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "none",
                "command": [
                    sys.executable,
                    "-c",
                    "import sys\ntext = sys.stdin.read()\nprint(f'stdin={text!r}')\nsys.exit(0 if text == '' else 7)\n",
                ],
            },
            "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
        }
    )

    result = run_local_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-closed-stdin",
        secrets={},
    )

    assert result.status == "passed"
    assert result.exit_code == 0
    assert result.stdout == b"stdin=''\n"


def test_local_runner_timeout_terminates_child_process_group(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    marker = run_dir / "child-survived.txt"
    workspace.mkdir()
    child_script = (
        "import pathlib, sys, time\n"
        "time.sleep(2)\n"
        "pathlib.Path(sys.argv[1]).write_text('alive', encoding='utf-8')\n"
    )
    parent_script = (
        "import os, pathlib, subprocess, sys, time\n"
        "marker = pathlib.Path(os.environ['ALAB_RUN_DIR']) / 'child-survived.txt'\n"
        f"subprocess.Popen([sys.executable, '-c', {child_script!r}, str(marker)])\n"
        "time.sleep(60)\n"
    )
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Timeout Runner", "task": "Kill child process group"},
            "runner": {
                "type": "local",
                "timeout_seconds": 1,
                "working_directory": ".",
                "env_mode": "none",
                "command": [sys.executable, "-c", parent_script],
            },
            "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
        }
    )

    result = run_local_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-timeout-group",
        secrets={},
    )
    time.sleep(2.5)

    assert result.status == "timeout"
    assert result.failure_reason == "runner timed out"
    assert not marker.exists()


def test_stdout_regex_reward_uses_redacted_and_truncated_stdout(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()

    redacted_config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Redacted Stdout Reward", "task": "Parse redacted stdout reward"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "none",
                "command": [sys.executable, "-c", "print('reward=1234')"],
            },
            "secret_env": {"TOKEN": "1234"},
            "reward": {
                "type": "stdout_regex",
                "direction": "maximize",
                "primary_metric": "reward",
                "pattern": "reward=([0-9.]+)",
            },
        }
    )

    redacted = run_local_runner(
        config=redacted_config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-redacted-stdout",
        secrets={"TOKEN": "1234"},
    )

    assert redacted.status == "error"
    assert redacted.reward is None
    assert redacted.reward_parse_status == "missing"
    assert redacted.stdout == b"reward=[REDACTED]\n"

    truncated_config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Truncated Stdout Reward", "task": "Parse truncated stdout reward"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "none",
                "command": [sys.executable, "-c", "print('prefix reward=42')"],
            },
            "reward": {
                "type": "stdout_regex",
                "direction": "maximize",
                "primary_metric": "reward",
                "pattern": "reward=([0-9.]+)",
            },
            "logs": {"stdout_limit_bytes": 6},
        }
    )

    truncated = run_local_runner(
        config=truncated_config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-truncated-stdout",
        secrets={},
    )

    assert truncated.status == "error"
    assert truncated.reward is None
    assert truncated.reward_parse_status == "missing"
    assert truncated.stdout == b"prefix reward=42\n"


def test_local_runner_shell_mode_runs_through_sh(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Local Shell Runner", "task": "Run local shell command"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "none",
                "command": None,
                "shell": "printf 'reward=4\\n'; printf '%s\\n' \"$ALAB_RUN_ID\" > \"$ALAB_RUN_DIR/shell-id.txt\"",
            },
            "reward": {
                "type": "stdout_regex",
                "direction": "maximize",
                "primary_metric": "reward",
                "pattern": "reward=([0-9.]+)",
            },
        }
    )

    result = run_local_runner(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-local-shell",
        secrets={},
    )

    assert result.status == "passed"
    assert result.reward == 4.0
    assert result.stdout == b"reward=4\n"
    assert (run_dir / "shell-id.txt").read_text(encoding="utf-8") == "run-local-shell\n"


def test_project_config_rejects_working_directory_with_sibling_prefix(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    sibling = tmp_path / "workspace-sibling"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    sibling.mkdir()

    with pytest.raises(ValueError) as exc:
        ProjectConfig.model_validate(
            {
                "schema_version": 1,
                "project": {"name": "Escaping Runner", "task": "Reject sibling prefix paths"},
                "runner": {
                    "type": "local",
                    "timeout_seconds": 30,
                    "working_directory": "../workspace-sibling",
                    "env_mode": "none",
                    "command": [sys.executable, "-c", "print('should not run')"],
                },
                "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
            }
        )

    assert "runner.working_directory escapes repository" in str(exc.value)
    assert not run_dir.exists()


def test_project_config_schema_rejects_escaping_rooted_paths() -> None:
    base = {
        "schema_version": 1,
        "project": {"name": "Path Validation", "task": "Validate config path roots"},
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "none",
            "command": [sys.executable, "-c", "print('unused')"],
        },
        "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
    }

    cases = [
        ({**base, "reward": {"type": "file", "direction": "maximize", "primary_metric": "reward", "path": "hidden:score.txt"}}, "reward.path root must be one of"),
        ({**base, "reward": {"type": "file", "direction": "maximize", "primary_metric": "reward", "path": "workspace:../score.txt"}}, "reward.path escapes root"),
        ({**base, "artifacts": {"globs": ["hidden:secret.txt"]}}, "artifacts.globs[0] root must be one of"),
        ({**base, "artifacts": {"globs": ["../secret.txt"]}}, "artifacts.globs[0] escapes root"),
        (
            {
                **base,
                "runner": {
                    **base["runner"],
                    "type": "docker",
                    "dockerfile": "../Dockerfile",
                    "context": ".",
                },
            },
            "runner.dockerfile escapes repository",
        ),
        (
            {
                **base,
                "runner": {
                    **base["runner"],
                    "type": "docker",
                    "dockerfile": "Dockerfile",
                    "context": "../context",
                },
            },
            "runner.context escapes repository",
        ),
    ]

    for payload, reason in cases:
        with pytest.raises(ValueError) as exc:
            ProjectConfig.model_validate(payload)
        assert reason in str(exc.value)


def test_project_config_schema_rejects_non_positive_capture_limits() -> None:
    base = {
        "schema_version": 1,
        "project": {"name": "Limit Validation", "task": "Validate capture limits"},
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "none",
            "command": [sys.executable, "-c", "print('unused')"],
        },
        "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
    }
    cases = [
        ({**base, "artifacts": {"per_file_limit_bytes": 0}}, "artifacts.per_file_limit_bytes must be a positive integer"),
        ({**base, "artifacts": {"per_run_limit_bytes": -1}}, "artifacts.per_run_limit_bytes must be a positive integer"),
        ({**base, "logs": {"stdout_limit_bytes": 0}}, "logs.stdout_limit_bytes must be a positive integer"),
        ({**base, "logs": {"stderr_limit_bytes": False}}, "logs.stderr_limit_bytes must be a positive integer"),
    ]

    for payload, reason in cases:
        with pytest.raises(ValueError) as exc:
            ProjectConfig.model_validate(payload)
        assert reason in str(exc.value)


def test_project_config_schema_rejects_ambiguous_numeric_values() -> None:
    base = {
        "schema_version": 1,
        "project": {"name": "Numeric Validation", "task": "Validate numeric config values"},
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "none",
            "command": [sys.executable, "-c", "print('unused')"],
        },
        "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
    }

    cases = [
        ({**base, "runner": {**base["runner"], "timeout_seconds": True}}, "runner.timeout_seconds must be an integer"),
        ({**base, "runner": {**base["runner"], "timeout_seconds": "30"}}, "runner.timeout_seconds must be an integer"),
        (
            {
                **base,
                "runner": {
                    **base["runner"],
                    "type": "docker",
                    "image": "example:latest",
                    "cpus": float("nan"),
                },
            },
            "runner.cpus must be a positive finite number",
        ),
        (
            {
                **base,
                "runner": {
                    **base["runner"],
                    "type": "docker",
                    "image": "example:latest",
                    "memory_mb": False,
                },
            },
            "runner.memory_mb must be a positive integer",
        ),
        (
            {**base, "public_source_import": {"max_files": False, "max_total_bytes": 1, "max_file_bytes": 1}},
            "public_source_import.max_files must be a non-negative integer",
        ),
        (
            {**base, "public_source_import": {"max_files": 1, "max_total_bytes": -1, "max_file_bytes": 1}},
            "public_source_import.max_total_bytes must be a non-negative integer",
        ),
    ]

    for payload, reason in cases:
        with pytest.raises(ValueError) as exc:
            ProjectConfig.model_validate(payload)
        assert reason in str(exc.value)


def test_project_config_schema_rejects_empty_runner_command_and_shell() -> None:
    base = {
        "schema_version": 1,
        "project": {"name": "Command Validation", "task": "Validate command shapes"},
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "none",
            "command": [sys.executable, "-c", "print('unused')"],
        },
        "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
    }
    cases = [
        ({**base, "runner": {**base["runner"], "command": []}}, "runner.command must not be empty"),
        ({**base, "runner": {**base["runner"], "command": [""]}}, "runner.command entries must be non-empty strings"),
        (
            {**base, "runner": {**base["runner"], "shell": "printf ok"}},
            "runner.command conflicts with runner.shell",
        ),
        (
            {**base, "runner": {**base["runner"], "command": None, "shell": "   "}},
            "runner.shell must not be empty",
        ),
        (
            {
                **base,
                "runner": {
                    **base["runner"],
                    "type": "harbor",
                    "command": None,
                    "shell": "printf ok",
                    "harbor_task_ref": "task",
                },
                "reward": {"type": "harbor", "direction": "maximize", "primary_metric": "reward"},
            },
            "runner.shell is not valid for adapter runners",
        ),
        (
            {
                **base,
                "runner": {
                    **base["runner"],
                    "type": "skydiscover_python",
                    "command": None,
                    "shell": "printf ok",
                    "skydiscover_task_ref": "skydiscover:benchmarks/demo",
                },
                "reward": {"type": "skydiscover", "direction": "maximize", "primary_metric": "combined_score"},
            },
            "runner.shell is not valid for adapter runners",
        ),
        (
            {
                **base,
                "runner": {
                    **base["runner"],
                    "type": "skydiscover_docker",
                    "command": None,
                    "shell": "printf ok",
                    "skydiscover_task_ref": "skydiscover:benchmarks/demo",
                },
                "reward": {"type": "skydiscover", "direction": "maximize", "primary_metric": "combined_score"},
            },
            "runner.shell is not valid for adapter runners",
        ),
    ]

    for payload, reason in cases:
        with pytest.raises(ValueError) as exc:
            ProjectConfig.model_validate(payload)
        assert reason in str(exc.value)


def test_project_config_schema_maps_runner_reward_and_env_edges() -> None:
    base = {
        "schema_version": 1,
        "project": {"name": "Schema Edges", "task": "Map remaining runner and reward fields"},
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "none",
            "command": [sys.executable, "-c", "print('unused')"],
        },
        "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
    }
    aliased_platform = ProjectConfig.model_validate(
        {
            **base,
            "runner": {
                **base["runner"],
                "type": "docker",
                "image": "example:latest",
                "platform": "Linux/X64",
            },
        }
    )
    assert aliased_platform.runner.platform == "linux/amd64"

    cases = [
        ({**base, "schema_version": 2}, "Input should be 1"),
        ({**base, "runner": {**base["runner"], "type": "bogus"}}, "Input should be"),
        ({**base, "runner": {**base["runner"], "env_mode": "host"}}, "Input should be"),
        ({**base, "runner": {**base["runner"], "timeout_seconds": 0}}, "runner.timeout_seconds must be between 1 and 86400"),
        ({**base, "runner": {**base["runner"], "timeout_seconds": 86401}}, "runner.timeout_seconds must be between 1 and 86400"),
        ({**base, "runner": {**base["runner"], "working_directory": ""}}, "runner.working_directory is required"),
        ({**base, "runner": {**base["runner"], "working_directory": "/tmp"}}, "runner.working_directory must be relative"),
        ({**base, "runner": {**base["runner"], "working_directory": "C:\\tmp"}}, "runner.working_directory must be relative"),
        ({**base, "runner": {**base["runner"], "working_directory": "sub\\..\\..\\outside"}}, "runner.working_directory escapes repository"),
        ({**base, "runner": {**base["runner"], "program_path": "sub/../../outside"}}, "runner.program_path escapes repository"),
        ({**base, "runner": {**base["runner"], "program_path": "bad\0path"}}, "runner.program_path contains NUL"),
        ({**base, "runner": {**base["runner"], "type": "docker", "network": "host", "image": "example:latest"}}, "Input should be 'default' or 'none'"),
        (
            {**base, "runner": {**base["runner"], "type": "docker", "raw_docker_args": ["--privileged"], "image": "example:latest"}},
            "Extra inputs are not permitted",
        ),
        ({**base, "runner": {**base["runner"], "type": "docker", "image": "example:latest", "dockerfile": "Dockerfile", "context": "."}}, "docker runner requires exactly one of runner.image or runner.dockerfile"),
        ({**base, "runner": {**base["runner"], "type": "docker"}}, "docker runner requires exactly one of runner.image or runner.dockerfile"),
        ({**base, "runner": {**base["runner"], "type": "docker", "dockerfile": "Dockerfile"}}, "dockerfile runner requires runner.context"),
        ({**base, "runner": {**base["runner"], "type": "docker", "image": "example:latest", "platform": "windows/amd64"}}, "runner.platform must be linux, linux/amd64, or linux/arm64"),
        ({**base, "runner": {**base["runner"], "type": "docker", "image": "example:latest", "build_args": {"COUNT": 1}}}, "Input should be a valid string"),
        ({**base, "runner": {**base["runner"], "type": "harbor", "command": None}, "reward": {"type": "harbor", "direction": "maximize", "primary_metric": "reward"}}, "harbor runner requires runner.harbor_task_ref"),
        ({**base, "runner": {**base["runner"], "type": "skydiscover_python", "command": None}, "reward": {"type": "skydiscover", "direction": "maximize", "primary_metric": "combined_score"}}, "skydiscover runner requires runner.skydiscover_task_ref"),
        ({**base, "reward": {"type": "exit_code", "direction": "minimize", "primary_metric": "reward"}}, "exit_code reward requires maximize direction"),
        ({**base, "reward": {"type": "file", "direction": "maximize", "primary_metric": "reward"}}, "file reward requires reward.path"),
        ({**base, "reward": {"type": "file", "direction": "maximize", "primary_metric": "reward", "path": "workspace:"}}, "reward.path path is required"),
        ({**base, "reward": {"type": "stdout_regex", "direction": "maximize", "primary_metric": "reward"}}, "stdout_regex reward requires reward.pattern"),
        ({**base, "artifacts": {"globs": ["workspace:"]}}, "artifacts.globs[0] path is required"),
        ({**base, "artifacts": {"globs": ["bad\0pattern"]}}, "artifacts.globs[0] contains NUL"),
        ({**base, "logs": {"stdout_limit_bytes": "1024"}}, "logs.stdout_limit_bytes must be a positive integer"),
        ({**base, "public_source_import": {"max_files": 1, "max_total_bytes": 1, "max_file_bytes": False}}, "public_source_import.max_file_bytes must be a non-negative integer"),
        ({**base, "visibility": {"scope": "explicit", "experiment_ids": []}}, "visibility.experiment_ids is required for explicit scope"),
        ({**base, "env": {"COUNT": 1}}, "Input should be a valid string"),
    ]

    for payload, reason in cases:
        with pytest.raises(ValueError) as exc:
            ProjectConfig.model_validate(payload)
        assert reason in str(exc.value)


def test_project_config_schema_validates_secret_env_shapes(tmp_path) -> None:
    base = {
        "schema_version": 1,
        "project": {"name": "Secret Shape", "task": "Validate secret env values"},
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "none",
            "command": [sys.executable, "-c", "print('unused')"],
        },
        "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
    }

    ProjectConfig.model_validate({**base, "secret_env": {"API_TOKEN": "valid-secret"}})
    ProjectConfig.model_validate({**base, "secret_env": {"API_TOKEN": {"retain": True, "fingerprint": "hmac-sha256:" + "0" * 64}}})
    ProjectConfig.model_validate(
        {
            **base,
            "secret_env": {
                "API_TOKEN": {
                    "secret_value_id": "sec-token-AAAAAAAAAAAAAAAAAAAAAA",
                    "fingerprint": "hmac-sha256:" + "1" * 64,
                }
            },
        }
    )

    cases = [
        ({"API_TOKEN": 123}, "secret_env entries must be strings or retain marker objects"),
        ({"API_TOKEN": "abc"}, "secret_env values must be single-line UTF-8 strings at least 4 bytes"),
        ({"API_TOKEN": {"retain": False}}, "secret_env.API_TOKEN.retain must be true"),
        ({"API_TOKEN": {"retain": True, "fingerprint": "plain"}}, "secret_env.API_TOKEN.fingerprint must be an HMAC string"),
        ({"API_TOKEN": {"retain": True, "unexpected": True}}, "secret_env.API_TOKEN contains unknown marker keys: unexpected"),
        ({"API_TOKEN": {}}, "secret_env.API_TOKEN marker must set retain = true"),
    ]
    for secret_env, reason in cases:
        with pytest.raises(ValueError) as exc:
            ProjectConfig.model_validate({**base, "secret_env": secret_env})
        assert reason in str(exc.value)

    config_path = tmp_path / "alab.project.toml"
    config_path.write_text(
        """
schema_version = 1

[project]
name = "Stored Marker Import"
task = "Reject stored markers in user config files"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["python", "-c", "print('unused')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[secret_env]
API_TOKEN = { secret_value_id = "sec-token-AAAAAAAAAAAAAAAAAAAAAA", fingerprint = "hmac-sha256:1111111111111111111111111111111111111111111111111111111111111111" }
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(AlabError) as exc:
        load_project_config(config_path)
    assert "secret_env.API_TOKEN import marker must use retain = true" in exc.value.reason


def test_project_config_schema_validates_policy_field_shapes() -> None:
    exp_id = "exp-visible-AAAAAAAAAAAAAAAAAAAAAA"
    base = {
        "schema_version": 1,
        "project": {"name": "Policy Shapes", "task": "Validate project policy fields"},
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "none",
            "command": [sys.executable, "-c", "print('unused')"],
        },
        "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
    }

    explicit = ProjectConfig.model_validate({**base, "visibility": {"scope": "explicit", "experiment_ids": [exp_id, exp_id]}})
    assert explicit.visibility.experiment_ids == [exp_id]

    cases = [
        ({**base, "project": {**base["project"], "allow_public_exp_create": "false"}}, "project.allow_public_exp_create must be a boolean"),
        (
            {**base, "public_source_import": {"enabled": "false", "max_files": 1, "max_total_bytes": 1, "max_file_bytes": 1}},
            "public_source_import.enabled must be a boolean",
        ),
        ({**base, "mutable": {"include": [], "exclude": []}}, "mutable.include must contain at least one pattern"),
        ({**base, "mutable": {"include": [""], "exclude": []}}, "mutable.include patterns must be non-empty single-line values"),
        ({**base, "mutable": {"include": ["**"], "exclude": ["bad\npattern"]}}, "mutable.exclude patterns must be non-empty single-line values"),
        (
            {**base, "visibility": {"scope": "same_project", "experiment_ids": [exp_id]}},
            "visibility.experiment_ids is only valid for explicit scope",
        ),
        (
            {**base, "visibility": {"scope": "explicit", "experiment_ids": ["exp-short"]}},
            "visibility.experiment_ids entries must be complete experiment ids",
        ),
    ]

    for payload, reason in cases:
        with pytest.raises(ValueError) as exc:
            ProjectConfig.model_validate(payload)
        assert reason in str(exc.value)


def test_stdout_regex_reward_schema_requires_usable_capture_group(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    run_dir.mkdir()
    base = {
        "schema_version": 1,
        "project": {"name": "Regex Reward", "task": "Validate stdout reward patterns"},
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "none",
            "command": [sys.executable, "-c", "print('unused')"],
        },
    }

    named = ProjectConfig.model_validate(
        {
            **base,
            "reward": {
                "type": "stdout_regex",
                "direction": "maximize",
                "primary_metric": "reward",
                "pattern": r"score=(?P<reward>[0-9.]+)",
            },
        }
    )
    assert parse_reward(named, 0, b"score=2.5\n", workspace, run_dir) == (2.5, "parsed")

    fallback_capture = ProjectConfig.model_validate(
        {
            **base,
            "reward": {
                "type": "stdout_regex",
                "direction": "maximize",
                "primary_metric": "reward",
                "pattern": r"score=(?P<score>[0-9.]+)",
            },
        }
    )
    assert parse_reward(fallback_capture, 0, b"score=3.5\n", workspace, run_dir) == (3.5, "parsed")

    cases = [
        ("score=[0-9.", "reward.pattern is invalid"),
        ("score=[0-9.]+", "stdout_regex reward requires a named reward group or a capture group"),
    ]
    for pattern, reason in cases:
        with pytest.raises(ValueError) as exc:
            ProjectConfig.model_validate(
                {
                    **base,
                    "reward": {
                        "type": "stdout_regex",
                        "direction": "maximize",
                        "primary_metric": "reward",
                        "pattern": pattern,
                    },
                }
            )
        assert reason in str(exc.value)


def test_exit_code_reward_parses_zero_and_nonzero_exits(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    run_dir.mkdir()
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Exit Code Reward", "task": "Map process exits to reward values"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "none",
                "command": [sys.executable, "-c", "print('unused')"],
            },
            "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
        }
    )

    assert parse_reward(config, 0, b"", workspace, run_dir) == (1.0, "parsed")
    assert parse_reward(config, 7, b"", workspace, run_dir) == (0.0, "parsed")


def test_artifact_capture_ignores_symlink_escape_with_sibling_prefix(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "workspace-outside"
    run_dir = tmp_path / "run"
    artifact_store = tmp_path / "artifacts"
    workspace.mkdir()
    outside.mkdir()
    run_dir.mkdir()
    outside_file = outside / "leak.txt"
    outside_file.write_text("outside\n", encoding="utf-8")
    try:
        (workspace / "leak.txt").symlink_to(outside_file)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Artifact Escape", "task": "Reject escaped artifacts"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "none",
                "command": [sys.executable, "-c", "print('unused')"],
            },
            "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
            "artifacts": {"globs": ["workspace:leak.txt"]},
        }
    )

    captured = capture_artifacts(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        artifact_store=artifact_store,
        project_id="proj-local",
        exp_id="exp-local",
        run_id="run-local",
        validation_id=None,
    )

    assert len(captured) == 1
    assert captured[0]["relative_path"] == "leak.txt"
    assert captured[0]["status"] == "skipped"
    assert captured[0]["blob_path"] is None
    assert not artifact_store.exists()


def test_artifact_capture_expands_directories_sorts_and_deduplicates(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    run_dir = tmp_path / "run"
    artifact_store = tmp_path / "artifacts"
    workspace.mkdir()
    outside.mkdir()
    run_dir.mkdir()
    (workspace / "outputs" / "nested").mkdir(parents=True)
    (workspace / "outputs" / "z.txt").write_text("z\n", encoding="utf-8")
    (workspace / "outputs" / "nested" / "a.txt").write_text("a\n", encoding="utf-8")
    (outside / "leak.txt").write_text("outside\n", encoding="utf-8")
    has_escape_symlink = True
    try:
        (workspace / "outputs" / "nested" / "leak.txt").symlink_to(outside / "leak.txt")
    except OSError:
        has_escape_symlink = False
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Artifact Directories", "task": "Expand artifact directories"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "none",
                "command": [sys.executable, "-c", "print('unused')"],
            },
            "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
            "artifacts": {"globs": ["workspace:outputs/z.txt", "workspace:outputs/nested/a.txt", "workspace:outputs"]},
        }
    )

    captured = capture_artifacts(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        artifact_store=artifact_store,
        project_id="proj-local",
        exp_id="exp-local",
        run_id="run-local",
        validation_id=None,
    )

    expected_paths = ["outputs/nested/a.txt", "outputs/z.txt"]
    expected_statuses = ["captured", "captured"]
    if has_escape_symlink:
        expected_paths.insert(1, "outputs/nested/leak.txt")
        expected_statuses.insert(1, "skipped")
    assert [artifact["relative_path"] for artifact in captured] == expected_paths
    assert [artifact["status"] for artifact in captured] == expected_statuses
    captured_artifacts = [artifact for artifact in captured if artifact["status"] == "captured"]
    assert [artifact["size_bytes"] for artifact in captured_artifacts] == [2, 2]
    assert len({artifact["blob_path"] for artifact in captured_artifacts}) == 2


def test_artifact_capture_records_read_errors_without_blob(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    artifact_store = tmp_path / "artifacts"
    workspace.mkdir()
    run_dir.mkdir()
    unreadable = workspace / "unreadable.txt"
    unreadable.write_text("host cannot read this output\n", encoding="utf-8")
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Artifact Read Error", "task": "Record unreadable outputs"},
            "runner": {
                "type": "local",
                "timeout_seconds": 30,
                "working_directory": ".",
                "env_mode": "none",
                "command": [sys.executable, "-c", "print('unused')"],
            },
            "reward": {"type": "exit_code", "direction": "maximize", "primary_metric": "reward"},
            "artifacts": {"globs": ["workspace:unreadable.txt"]},
        }
    )

    original_read_bytes = Path.read_bytes

    def fake_read_bytes(path: Path) -> bytes:
        if path == unreadable:
            raise OSError("simulated unreadable output")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)

    captured = capture_artifacts(
        config=config,
        workspace=workspace,
        run_dir=run_dir,
        artifact_store=artifact_store,
        project_id="proj-local",
        exp_id="exp-local",
        run_id="run-local",
        validation_id=None,
    )

    assert len(captured) == 1
    assert captured[0]["relative_path"] == "unreadable.txt"
    assert captured[0]["status"] == "error"
    assert captured[0]["size_bytes"] is None
    assert captured[0]["content_hash"] is None
    assert captured[0]["blob_path"] is None
    assert "simulated unreadable output" in captured[0]["capture_error"]
    assert not artifact_store.exists()


def test_file_reward_rejects_symlink_escape_at_parse_time(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "workspace-outside"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    outside.mkdir()
    run_dir.mkdir()
    (workspace / "reward.txt").write_text("1.0\n", encoding="utf-8")
    (outside / "reward.txt").write_text("9.0\n", encoding="utf-8")

    base = {
        "schema_version": 1,
        "project": {"name": "File Reward", "task": "Validate reward paths"},
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "none",
            "command": [sys.executable, "-c", "print('unused')"],
        },
        "reward": {"type": "file", "direction": "maximize", "primary_metric": "reward", "path": "workspace:reward.txt"},
    }

    valid = ProjectConfig.model_validate(base)
    assert parse_reward(valid, 0, b"", workspace, run_dir) == (1.0, "parsed")

    try:
        (workspace / "linked-reward.txt").symlink_to(outside / "reward.txt")
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    linked_escape = ProjectConfig.model_validate({**base, "reward": {**base["reward"], "path": "workspace:linked-reward.txt"}})
    assert parse_reward(linked_escape, 0, b"", workspace, run_dir) == (None, "invalid")


def test_file_reward_parses_json_and_enforces_limit_and_finite_values(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    workspace.mkdir()
    run_dir.mkdir()
    (workspace / "score.json").write_text('{"score": 2.5, "other": 1}\n', encoding="utf-8")
    (workspace / "nan.txt").write_text("NaN\n", encoding="utf-8")
    (run_dir / "score.txt").write_text("3.25\n", encoding="utf-8")

    base = {
        "schema_version": 1,
        "project": {"name": "File Reward", "task": "Parse reward files"},
        "runner": {
            "type": "local",
            "timeout_seconds": 30,
            "working_directory": ".",
            "env_mode": "none",
            "command": [sys.executable, "-c", "print('unused')"],
        },
        "reward": {"type": "file", "direction": "maximize", "primary_metric": "score", "path": "workspace:score.json"},
    }

    json_reward = ProjectConfig.model_validate(base)
    assert parse_reward(json_reward, 0, b"", workspace, run_dir) == (2.5, "parsed")

    run_reward = ProjectConfig.model_validate({**base, "reward": {**base["reward"], "primary_metric": "reward", "path": "run:score.txt"}})
    assert parse_reward(run_reward, 0, b"", workspace, run_dir) == (3.25, "parsed")

    non_finite = ProjectConfig.model_validate({**base, "reward": {**base["reward"], "path": "workspace:nan.txt"}})
    assert parse_reward(non_finite, 0, b"", workspace, run_dir) == (None, "invalid")

    too_large = ProjectConfig.model_validate({**base, "artifacts": {"per_file_limit_bytes": 3}})
    assert parse_reward(too_large, 0, b"", workspace, run_dir) == (None, "invalid")
