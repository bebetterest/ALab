from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from alab.configs import ProjectConfig
from alab.runner import run_configured_runner


def _skydiscover_python_config(ref: str = "skydiscover:benchmarks/demo", primary_metric: str = "combined_score", program_path: str = ".") -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "SkyDiscover Python", "task": "Evaluate candidate program"},
            "runner": {
                "type": "skydiscover_python",
                "timeout_seconds": 30,
                "working_directory": ".",
                "skydiscover_task_ref": ref,
                "program_path": program_path,
            },
            "reward": {
                "type": "skydiscover",
                "direction": "maximize",
                "primary_metric": primary_metric,
            },
        }
    )


def _skydiscover_docker_config(ref: str = "skydiscover:benchmarks/docker-demo", program_path: str = ".") -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "SkyDiscover Docker", "task": "Evaluate candidate program"},
            "runner": {
                "type": "skydiscover_docker",
                "timeout_seconds": 30,
                "working_directory": ".",
                "network": "none",
                "skydiscover_task_ref": ref,
                "program_path": program_path,
            },
            "reward": {
                "type": "skydiscover",
                "direction": "maximize",
                "primary_metric": "combined_score",
            },
        }
    )


def _resolver(target: Path):
    return lambda ref: {
        "ref": ref,
        "relative_path": "benchmarks/demo",
        "target_kind": "skydiscover_python_evaluator",
        "pinned_commit": "a" * 40,
        "target_path": str(target),
    }


def _docker_resolver(target: Path):
    return lambda ref: {
        "ref": ref,
        "relative_path": "benchmarks/docker-demo",
        "target_kind": "skydiscover_docker_evaluator",
        "pinned_commit": "b" * 40,
        "target_path": str(target),
    }


def test_skydiscover_adapter_resolver_failures_do_not_create_runtime_dirs(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    evaluator = tmp_path / "catalog" / "benchmarks" / "demo"
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    cases = [
        ("python_no_resolver", _skydiscover_python_config(), None, "SkyDiscover catalog resolver is unavailable"),
        (
            "python_incomplete_resolver",
            _skydiscover_python_config(),
            lambda _ref: {"target_kind": "skydiscover_python_evaluator"},
            "SkyDiscover catalog resolver returned incomplete data",
        ),
        (
            "python_wrong_kind",
            _skydiscover_python_config(),
            _docker_resolver(evaluator),
            "runner.skydiscover_task_ref must resolve to a Python evaluator",
        ),
        (
            "python_missing_program_path",
            _skydiscover_python_config(program_path="missing"),
            _resolver(evaluator),
            "runner.program_path does not exist",
        ),
        ("docker_no_resolver", _skydiscover_docker_config(), None, "SkyDiscover catalog resolver is unavailable"),
        (
            "docker_incomplete_resolver",
            _skydiscover_docker_config(),
            lambda _ref: {"target_kind": "skydiscover_docker_evaluator"},
            "SkyDiscover catalog resolver returned incomplete data",
        ),
        (
            "docker_wrong_kind",
            _skydiscover_docker_config(),
            _resolver(evaluator),
            "runner.skydiscover_task_ref must resolve to a Docker evaluator",
        ),
        (
            "docker_missing_program_path",
            _skydiscover_docker_config(program_path="missing"),
            _docker_resolver(evaluator),
            "runner.program_path does not exist",
        ),
    ]

    for case_name, config, resolver, expected_reason in cases:
        run_dir = tmp_path / f"run-{case_name}"
        hidden_dir = tmp_path / f"hidden-{case_name}"
        result = run_configured_runner(
            config=config,
            workspace=workspace,
            run_dir=run_dir,
            operation_id=case_name,
            secrets={},
            hidden_dir=hidden_dir,
            cache_dir=tmp_path / f"cache-{case_name}",
            adapter_resolver=resolver,
        )

        assert result.status == "error"
        assert result.failure_reason == expected_reason
        assert expected_reason.encode() in result.stderr
        assert not run_dir.exists()
        assert not hidden_dir.exists()
        assert (workspace / "main.py").read_text(encoding="utf-8") == "print('candidate')\n"


def test_skydiscover_docker_timeout_removes_named_container_and_keeps_output_hidden(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    evaluator = tmp_path / "catalog" / "benchmarks" / "docker-demo"
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "Dockerfile").write_text("FROM alpine:3.20\n", encoding="utf-8")
    (evaluator / "evaluate.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_docker(args, *, timeout=None):
        calls.append(args)
        if args[:2] == ["image", "inspect"]:
            return subprocess.CompletedProcess(["docker", *args], 0, b"", b"")
        if args and args[0] == "run":
            raise subprocess.TimeoutExpired(["docker", *args], timeout or 1, output=b"sky-secret stdout", stderr=b"sky-secret stderr")
        if args[:2] == ["rm", "-f"]:
            return subprocess.CompletedProcess(["docker", *args], 0, b"", b"")
        raise AssertionError(args)

    monkeypatch.setattr("alab.runner._run_docker_cli", fake_docker)
    result = run_configured_runner(
        config=_skydiscover_docker_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="sky-timeout",
        secrets={"SECRET": "sky-secret"},
        hidden_dir=hidden_dir,
        adapter_resolver=_docker_resolver(evaluator),
    )

    assert result.status == "timeout"
    assert result.failure_reason == "runner timed out"
    assert b"SkyDiscover Docker evaluator timed out" in result.stderr
    assert b"sky-secret" not in result.hidden_stdout
    assert b"sky-secret" not in result.hidden_stderr
    assert b"[REDACTED]" in result.hidden_stdout
    assert b"[REDACTED]" in result.hidden_stderr
    assert ["rm", "-f", "alab-sky-timeout"] in calls


def test_skydiscover_docker_runner_builds_hidden_bundle_and_parses_metrics(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    evaluator = tmp_path / "catalog" / "benchmarks" / "docker-demo"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-calls.jsonl"
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    bin_dir.mkdir()
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "Dockerfile").write_text("FROM alpine:3.20\n", encoding="utf-8")
    (evaluator / "evaluate.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (evaluator / "private.txt").write_text("hidden test data\n", encoding="utf-8")
    monkeypatch.setenv("HOST_ONLY_VALUE", "host-only")
    monkeypatch.setenv("ALAB_KEY", "host-root-key")
    monkeypatch.setenv("ALAB_TOKEN", "host-token")
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
    print("built evaluator image")
    raise SystemExit(0)
if args and args[0] == "run":
    print(json.dumps({"combined_score": 8.25, "other": 2.0, "artifacts": {"note": "kept in feedback"}}))
    print("private docker sky-secret stderr", file=sys.stderr)
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "SkyDiscover Docker", "task": "Evaluate candidate program"},
            "runner": {
                "type": "skydiscover_docker",
                "timeout_seconds": 30,
                "working_directory": ".",
                "network": "none",
                "skydiscover_task_ref": "skydiscover:benchmarks/docker-demo",
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
        operation_id="run-sky-docker",
        secrets={"SECRET": "sky-secret"},
        project_id="proj-sky-docker",
        exp_id="exp-sky-docker",
        config_version=7,
        hidden_dir=hidden_dir,
        adapter_resolver=_docker_resolver(evaluator),
    )

    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    build_call = next(call for call in calls if call and call[0] == "build")
    run_call = next(call for call in calls if call and call[0] == "run")
    bundle = hidden_dir / "skydiscover-docker-evaluator"
    assert result.status == "passed"
    assert result.reward == 8.25
    assert result.metrics["combined_score"] == 8.25
    assert result.adapter_feedback["feedback"]["artifacts"]["note"] == "kept in feedback"
    assert result.cache_metadata["cache_kind"] == "docker_image"
    assert result.cache_metadata["adapter"] == "skydiscover_docker"
    assert b"SkyDiscover Docker evaluator completed" in result.stdout
    assert str(evaluator).encode() not in result.stdout
    assert str(bundle).encode() not in result.stdout
    assert b"hidden test data" not in result.stdout
    assert b"private docker" not in result.stdout
    assert b"combined_score" in result.hidden_stdout
    assert b"sky-secret" not in result.hidden_stderr
    assert b"private docker [REDACTED] stderr" in result.hidden_stderr
    assert (bundle / "Dockerfile").is_file()
    assert (bundle / "evaluate.sh").is_file()
    assert not (workspace / "evaluate.sh").exists()
    assert str(bundle) in build_call
    assert f"{workspace.resolve()}:/workspace" in run_call
    assert f"{bundle.resolve()}:/alab/evaluator:ro" in run_call
    assert "--network" in run_call
    assert "none" in run_call
    env_values = [run_call[index + 1] for index, item in enumerate(run_call[:-1]) if item == "--env"]
    assert "VISIBLE=1" in env_values
    assert "SECRET=sky-secret" in env_values
    assert "ALAB_PROJECT_ID=proj-sky-docker" in env_values
    assert "ALAB_EXP_ID=exp-sky-docker" in env_values
    assert "ALAB_RUN_ID=run-sky-docker" in env_values
    assert "ALAB_CONFIG_VERSION=7" in env_values
    assert "ALAB_WORKSPACE=/workspace" in env_values
    assert "ALAB_RUN_DIR=/logs/alab" in env_values
    assert "ALAB_PROGRAM_PATH=/workspace" in env_values
    assert "HOST_ONLY_VALUE=host-only" not in env_values
    assert "ALAB_KEY=host-root-key" not in env_values
    assert "ALAB_TOKEN=host-token" not in env_values
    assert "ALAB_PROJECT_ID=user-project" not in env_values
    assert "ALAB_EXP_ID=user-exp" not in env_values
    assert "ALAB_RUN_ID=user-run" not in env_values
    assert "ALAB_CONFIG_VERSION=user-version" not in env_values
    assert "ALAB_WORKSPACE=/user-workspace" not in env_values
    assert "ALAB_RUN_DIR=/user-run-dir" not in env_values
    assert "ALAB_PROGRAM_PATH=/user-program" not in env_values


def test_skydiscover_python_runner_materializes_hidden_bundle_and_metrics(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    evaluator = tmp_path / "catalog" / "benchmarks" / "demo"
    import_pid_file = tmp_path / "evaluator-import-pid.txt"
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "evaluator.py").write_text(
        f"""
import os
from pathlib import Path

Path({str(import_pid_file)!r}).write_text(str(os.getpid()), encoding="utf-8")


def evaluate(program_path):
    print("private evaluator stdout")
    content = (Path(program_path) / "main.py").read_text(encoding="utf-8")
    return {{"metrics": {{"combined_score": 3.5, "length": len(content)}}, "feedback": {{"ok": True}}}}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    sys.modules.pop("alab_skydiscover_evaluator", None)
    result = run_configured_runner(
        config=_skydiscover_python_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-sky",
        secrets={},
        hidden_dir=hidden_dir,
        cache_dir=tmp_path / "cache",
        adapter_resolver=_resolver(evaluator),
    )

    assert result.status == "passed"
    assert result.reward == 3.5
    assert result.metrics["combined_score"] == 3.5
    assert result.adapter_feedback["sandbox"] == "not_os_sandbox"
    assert b"SkyDiscover Python evaluator completed" in result.stdout
    assert str(evaluator).encode() not in result.stdout
    assert str(hidden_dir).encode() not in result.stdout
    assert b"private evaluator stdout" not in result.stdout
    assert b"evaluator.py" not in result.stdout
    assert b"private evaluator stdout" in result.hidden_stdout
    assert (hidden_dir / "skydiscover-python-evaluator" / "evaluator.py").is_file()
    assert not (workspace / "evaluator.py").exists()
    assert import_pid_file.read_text(encoding="utf-8") != str(os.getpid())
    assert "alab_skydiscover_evaluator" not in sys.modules


def test_skydiscover_python_reward_fallback_and_missing_custom_primary_metric(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    fallback_run_dir = tmp_path / "fallback-run"
    fallback_hidden_dir = tmp_path / "fallback-hidden"
    missing_run_dir = tmp_path / "missing-run"
    missing_hidden_dir = tmp_path / "missing-hidden"
    evaluator = tmp_path / "catalog" / "benchmarks" / "demo"
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "evaluator.py").write_text(
        """
def evaluate(program_path):
    return {"metrics": {"other": 2.0, "length": 4.0}, "feedback": {"ok": True}}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    fallback = run_configured_runner(
        config=_skydiscover_python_config(),
        workspace=workspace,
        run_dir=fallback_run_dir,
        operation_id="run-sky-fallback",
        secrets={},
        hidden_dir=fallback_hidden_dir,
        cache_dir=tmp_path / "fallback-cache",
        adapter_resolver=_resolver(evaluator),
    )
    assert fallback.status == "passed"
    assert fallback.reward_parse_status == "parsed"
    assert fallback.reward == 3.0
    assert fallback.metrics == {"other": 2.0, "length": 4.0}

    missing = run_configured_runner(
        config=_skydiscover_python_config(primary_metric="accuracy"),
        workspace=workspace,
        run_dir=missing_run_dir,
        operation_id="run-sky-missing-primary",
        secrets={},
        hidden_dir=missing_hidden_dir,
        cache_dir=tmp_path / "missing-cache",
        adapter_resolver=_resolver(evaluator),
    )
    assert missing.status == "error"
    assert missing.reward is None
    assert missing.reward_parse_status == "missing"
    assert missing.failure_reason == "SkyDiscover reward metric missing"
    assert b"metric names: length, other" in missing.stdout
    assert b"reward: none" in missing.stdout


def test_skydiscover_python_runner_env_boundary_and_redaction(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    evaluator = tmp_path / "catalog" / "benchmarks" / "demo"
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    monkeypatch.setenv("HOST_ONLY_VALUE", "host-only")
    monkeypatch.setenv("ALAB_KEY", "host-root-key")
    monkeypatch.setenv("ALAB_TOKEN", "host-token")
    expected_workspace = str(workspace)
    expected_run_dir = str(run_dir)
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "evaluator.py").write_text(
        f"""
import os


def evaluate(program_path):
    checks = {{
        "host_only_absent": "HOST_ONLY_VALUE" not in os.environ,
        "host_alab_key_absent": "ALAB_KEY" not in os.environ,
        "host_alab_token_absent": "ALAB_TOKEN" not in os.environ,
        "project_id": os.environ.get("ALAB_PROJECT_ID") == "proj-sky",
        "exp_id": os.environ.get("ALAB_EXP_ID") == "exp-sky",
        "run_id": os.environ.get("ALAB_RUN_ID") == "run-sky-env",
        "config_version": os.environ.get("ALAB_CONFIG_VERSION") == "5",
        "workspace": os.environ.get("ALAB_WORKSPACE") == {expected_workspace!r},
        "run_dir": os.environ.get("ALAB_RUN_DIR") == {expected_run_dir!r},
        "program_path": str(program_path) == {expected_workspace!r},
        "visible_env": os.environ.get("VISIBLE") == "1",
        "secret_env": os.environ.get("SECRET") == "sky-secret",
    }}
    print(f"visible={{os.environ.get('VISIBLE', '')}}")
    print(f"secret={{os.environ.get('SECRET', '')}}")
    return {{
        "metrics": {{"combined_score": 6.0, "checks": sum(1 for ok in checks.values() if ok)}},
        "feedback": checks,
    }}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "SkyDiscover Python Env", "task": "Check evaluator environment"},
            "runner": {
                "type": "skydiscover_python",
                "timeout_seconds": 30,
                "working_directory": ".",
                "skydiscover_task_ref": "skydiscover:benchmarks/demo",
                "program_path": ".",
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
        operation_id="run-sky-env",
        secrets={"SECRET": "sky-secret"},
        project_id="proj-sky",
        exp_id="exp-sky",
        config_version=5,
        hidden_dir=hidden_dir,
        cache_dir=tmp_path / "cache",
        adapter_resolver=_resolver(evaluator),
    )

    assert result.status == "passed"
    assert result.reward == 6.0
    assert result.metrics["checks"] == 12
    assert all(result.adapter_feedback["feedback"].values())
    assert b"visible=1" in result.hidden_stdout
    assert b"sky-secret" not in result.hidden_stdout
    assert b"secret=[REDACTED]" in result.hidden_stdout


def test_skydiscover_python_runner_reuses_uv_environment_cache(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    evaluator = tmp_path / "catalog" / "benchmarks" / "demo"
    bin_dir = tmp_path / "bin"
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    bin_dir.mkdir()
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "requirements.txt").write_text("# no external dependencies\n", encoding="utf-8")
    (evaluator / "evaluator.py").write_text(
        "def evaluate(program_path):\n    return {'combined_score': 4.0}\n",
        encoding="utf-8",
    )
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(
        f"""#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
if args and args[0] == "venv":
    env_dir = Path(args[1])
    (env_dir / "bin").mkdir(parents=True, exist_ok=True)
    python_path = env_dir / "bin" / "python"
    if python_path.exists() or python_path.is_symlink():
        python_path.unlink()
    os.symlink({sys.executable!r}, python_path)
    print("created env")
    raise SystemExit(0)
if args[:2] == ["pip", "install"]:
    print("installed requirements")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    cache_dir = tmp_path / "cache"

    first = run_configured_runner(
        config=_skydiscover_python_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-sky-1",
        secrets={},
        hidden_dir=hidden_dir,
        cache_dir=cache_dir,
        adapter_resolver=_resolver(evaluator),
    )
    second = run_configured_runner(
        config=_skydiscover_python_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="run-sky-2",
        secrets={},
        hidden_dir=hidden_dir,
        cache_dir=cache_dir,
        adapter_resolver=_resolver(evaluator),
    )

    assert first.status == "passed"
    assert first.cache_metadata["cache_kind"] == "skydiscover_python_env"
    assert first.cache_metadata["status"] == "built"
    assert second.status == "passed"
    assert second.cache_metadata["status"] == "hit"
