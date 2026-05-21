from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import alab.services as services
from alab.cli import run

pytestmark = pytest.mark.live_skydiscover_catalog


def _require_live_skydiscover_catalog() -> None:
    if os.environ.get("ALAB_RUN_LIVE_SKYDISCOVER_CATALOG", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("set ALAB_RUN_LIVE_SKYDISCOVER_CATALOG=1 to run live SkyDiscover catalog tests")
    if shutil.which("git") is None:
        pytest.skip("git executable is not available")
    try:
        probe = subprocess.run(
            ["git", "ls-remote", "--heads", services.SKYDISCOVER_ORIGIN_URL, "main"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        pytest.skip("live SkyDiscover catalog probe timed out")
    if probe.returncode != 0:
        reason = (probe.stderr or probe.stdout).decode("utf-8", errors="replace").strip()
        pytest.skip(f"live SkyDiscover catalog is not reachable: {reason}")


def _field(output: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}: (.+)$", output, re.MULTILINE)
    assert match, output
    return match.group(1)


def _git(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)
    return completed.stdout.decode("utf-8", errors="replace").strip()


def _find_live_evaluator_ref(catalog: Path) -> tuple[str, str] | None:
    candidates = [
        path
        for path in catalog.rglob("*")
        if ".git" not in path.parts and (path.is_dir() or path.name in {"evaluator.py", "evaluate.py"})
    ]
    candidates.sort(key=lambda path: (not path.relative_to(catalog).as_posix().startswith("benchmarks/"), len(path.parts), path.as_posix()))
    for path in candidates:
        rel = path.relative_to(catalog).as_posix()
        try:
            target_kind = services._recognize_skydiscover_target(path)
        except Exception:
            continue
        if target_kind == "skydiscover_python_evaluator":
            return rel, "skydiscover_python"
        if target_kind == "skydiscover_docker_evaluator":
            return rel, "skydiscover_docker"
    return None


def test_live_skydiscover_catalog_add_show_and_resolve_project_init(tmp_path, monkeypatch, capsys) -> None:
    _require_live_skydiscover_catalog()
    home = tmp_path / "home"
    config = tmp_path / "live-skydiscover.toml"

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--ref", "main"]) == 0
    add_out = capsys.readouterr().out
    pinned_commit = _field(add_out, "pinned commit")
    local_path = Path(_field(add_out, "local path"))
    assert re.fullmatch(r"[0-9a-f]{40}", pinned_commit)
    assert local_path.is_dir()
    assert _git(["rev-parse", "HEAD"], local_path) == pinned_commit

    def fail_show_network(*_args, **_kwargs):
        raise AssertionError("catalog show must not run Git or fetch the network")

    monkeypatch.setattr(services, "run_cmd", fail_show_network)
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "show"]) == 0
    show_out = capsys.readouterr().out
    assert f"pinned commit: {pinned_commit}" in show_out
    assert f"local path: {local_path}" in show_out
    monkeypatch.undo()

    evaluator = _find_live_evaluator_ref(local_path)
    if evaluator is None:
        pytest.skip("live SkyDiscover catalog contains no supported Python or Docker evaluator ref")
    rel, runner_type = evaluator
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Live SkyDiscover Catalog"
task = "Resolve a live SkyDiscover catalog evaluator"

[runner]
type = "{runner_type}"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = {json.dumps(f"skydiscover:{rel}")}
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert (
        run(
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
                "--source-empty",
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    init_out = capsys.readouterr().out
    assert "object: project" in init_out
    assert "project name: Live SkyDiscover Catalog" in init_out
    assert "project status: invalid" in init_out
    assert "validation status: skipped" in init_out
