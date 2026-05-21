from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

import pytest

from alab.configs import ProjectConfig
from alab.runner import run_configured_runner

pytestmark = pytest.mark.real_skydiscover_python


def _require_real_skydiscover_python() -> None:
    if os.environ.get("ALAB_RUN_REAL_SKYDISCOVER_PYTHON", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("set ALAB_RUN_REAL_SKYDISCOVER_PYTHON=1 to run real SkyDiscover Python integration tests")
    if shutil.which("uv") is None:
        pytest.skip("uv executable is not available")


def _require_networked_skydiscover_python() -> None:
    if os.environ.get("ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("set ALAB_RUN_NETWORKED_SKYDISCOVER_PYTHON=1 to run networked SkyDiscover Python dependency tests")
    if shutil.which("uv") is None:
        pytest.skip("uv executable is not available")


def _require_native_skydiscover_python() -> tuple[str, str]:
    if os.environ.get("ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("set ALAB_RUN_NATIVE_SKYDISCOVER_PYTHON=1 to run native SkyDiscover Python dependency tests")
    if shutil.which("uv") is None:
        pytest.skip("uv executable is not available")
    requirement = os.environ.get("ALAB_NATIVE_SKYDISCOVER_PYTHON_REQUIREMENT", "orjson>=3.10,<4")
    module_name = os.environ.get("ALAB_NATIVE_SKYDISCOVER_PYTHON_MODULE", "orjson")
    return requirement, module_name


def _resolver(evaluator_dir: Path):
    return lambda ref: {
        "ref": ref,
        "relative_path": "benchmarks/real-python",
        "target_kind": "skydiscover_python_evaluator",
        "pinned_commit": "e" * 40,
        "target_path": str(evaluator_dir),
    }


def _config() -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {
                "name": "Real SkyDiscover Python",
                "task": "Run a real SkyDiscover Python evaluator environment",
            },
            "runner": {
                "type": "skydiscover_python",
                "timeout_seconds": 120,
                "working_directory": ".",
                "skydiscover_task_ref": "skydiscover:benchmarks/real-python",
                "program_path": ".",
            },
            "reward": {
                "type": "skydiscover",
                "direction": "maximize",
                "primary_metric": "combined_score",
            },
        }
    )


def _write_metric_wheel(wheelhouse: Path) -> Path:
    wheelhouse.mkdir(parents=True)
    wheel = wheelhouse / "alab_metriclib-0.1-py3-none-any.whl"
    dist_info = "alab_metriclib-0.1.dist-info"
    files = {
        "metriclib/__init__.py": (
            "def score(text):\n"
            "    return float(text.count('candidate') + 10)\n"
        ),
        f"{dist_info}/METADATA": "Metadata-Version: 2.1\nName: alab-metriclib\nVersion: 0.1\n",
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: ALab test fixture\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ),
    }
    record = "".join(f"{name},,\n" for name in [*files, f"{dist_info}/RECORD"])
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr(f"{dist_info}/RECORD", record)
    return wheel


def test_real_skydiscover_python_uv_dependency_install_and_cache(tmp_path) -> None:
    _require_real_skydiscover_python()
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    cache_dir = tmp_path / "cache"
    evaluator = tmp_path / "catalog" / "benchmarks" / "real-python"
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")

    wheel = _write_metric_wheel(tmp_path / "wheelhouse")
    (evaluator / "requirements.txt").write_text(f"{wheel.as_uri()}\n", encoding="utf-8")
    (evaluator / "evaluator.py").write_text(
        """
from pathlib import Path

import metriclib


def evaluate(program_path):
    print("real skydiscover python evaluator ok")
    content = (Path(program_path) / "main.py").read_text(encoding="utf-8")
    score = metriclib.score(content)
    return {"metrics": {"combined_score": score, "checks": 1}, "feedback": {"dependency": metriclib.__name__}}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    first = run_configured_runner(
        config=_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-sky-python-1",
        secrets={},
        hidden_dir=hidden_dir,
        cache_dir=cache_dir,
        adapter_resolver=_resolver(evaluator),
    )
    second = run_configured_runner(
        config=_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="real-sky-python-2",
        secrets={},
        hidden_dir=hidden_dir,
        cache_dir=cache_dir,
        adapter_resolver=_resolver(evaluator),
    )

    assert first.status == "passed"
    assert first.reward == 11.0
    assert first.metrics["checks"] == 1
    assert first.adapter_feedback["feedback"]["dependency"] == "metriclib"
    assert first.cache_metadata["cache_kind"] == "skydiscover_python_env"
    assert first.cache_metadata["status"] == "built"
    assert b"SkyDiscover Python evaluator completed" in first.stdout
    assert b"real skydiscover python evaluator ok" in first.hidden_stdout
    assert (hidden_dir / "skydiscover-python-evaluator" / "requirements.txt").is_file()
    assert not (workspace / "evaluator.py").exists()

    assert second.status == "passed"
    assert second.reward == 11.0
    assert second.cache_metadata["status"] == "hit"


@pytest.mark.networked_skydiscover_python
@pytest.mark.parametrize(
    ("case_name", "requirements", "evaluator_source", "expected_reward", "expected_feedback"),
    [
        (
            "direct-six",
            "six==1.16.0\n",
            """
import six


def evaluate(program_path):
    print("networked direct dependency evaluator ok")
    return {
        "metrics": {"combined_score": 16.0, "py3": 1 if six.PY3 else 0},
        "feedback": {"dependency": "six", "dependency_version": six.__version__},
    }
""".strip()
            + "\n",
            16.0,
            {"dependency": "six", "dependency_version": "1.16.0"},
        ),
        (
            "transitive-dateutil",
            "python-dateutil==2.9.0.post0\n",
            """
import six
from dateutil import parser


def evaluate(program_path):
    print("networked transitive dependency evaluator ok")
    parsed = parser.isoparse("2026-05-21T00:00:00+00:00")
    return {
        "metrics": {"combined_score": float(parsed.year), "six_py3": 1 if six.PY3 else 0},
        "feedback": {"dependency": "python-dateutil", "parsed": parsed.isoformat(), "six": six.__version__},
    }
""".strip()
            + "\n",
            2026.0,
            {"dependency": "python-dateutil", "parsed": "2026-05-21T00:00:00+00:00"},
        ),
    ],
    ids=["direct-six", "transitive-dateutil"],
)
def test_networked_skydiscover_python_dependency_install(
    tmp_path,
    case_name: str,
    requirements: str,
    evaluator_source: str,
    expected_reward: float,
    expected_feedback: dict[str, str],
) -> None:
    _require_networked_skydiscover_python()
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    cache_dir = tmp_path / "cache"
    evaluator = tmp_path / "catalog" / "benchmarks" / case_name
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "requirements.txt").write_text(requirements, encoding="utf-8")
    (evaluator / "evaluator.py").write_text(evaluator_source, encoding="utf-8")

    first = run_configured_runner(
        config=_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id=f"networked-sky-python-{case_name}-1",
        secrets={},
        hidden_dir=hidden_dir,
        cache_dir=cache_dir,
        adapter_resolver=_resolver(evaluator),
    )
    second = run_configured_runner(
        config=_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id=f"networked-sky-python-{case_name}-2",
        secrets={},
        hidden_dir=hidden_dir,
        cache_dir=cache_dir,
        adapter_resolver=_resolver(evaluator),
    )

    assert first.status == "passed"
    assert first.reward == expected_reward
    assert first.cache_metadata["cache_kind"] == "skydiscover_python_env"
    assert first.cache_metadata["status"] == "built"
    assert expected_feedback.items() <= first.adapter_feedback["feedback"].items()
    assert f"networked {case_name.split('-', 1)[0]} dependency evaluator ok".encode() in first.hidden_stdout
    assert second.status == "passed"
    assert second.reward == expected_reward
    assert second.cache_metadata["status"] == "hit"


@pytest.mark.native_skydiscover_python
def test_native_skydiscover_python_dependency_install(tmp_path) -> None:
    requirement, module_name = _require_native_skydiscover_python()
    workspace = tmp_path / "workspace"
    run_dir = tmp_path / "run"
    hidden_dir = tmp_path / "hidden"
    cache_dir = tmp_path / "cache"
    evaluator = tmp_path / "catalog" / "benchmarks" / "native-python"
    workspace.mkdir()
    evaluator.mkdir(parents=True)
    (workspace / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "requirements.txt").write_text(f"{requirement}\n", encoding="utf-8")
    (evaluator / "evaluator.py").write_text(
        f"""
import importlib


def evaluate(program_path):
    native_module = importlib.import_module({module_name!r})
    payload = native_module.dumps({{"combined_score": 42.5, "checks": 2}})
    parsed = native_module.loads(payload)
    print("native skydiscover python dependency evaluator ok")
    return {{
        "metrics": {{
            "combined_score": float(parsed["combined_score"]),
            "checks": int(parsed["checks"]),
        }},
        "feedback": {{"dependency": {module_name!r}, "requirement": {requirement!r}}},
    }}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    first = run_configured_runner(
        config=_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="native-sky-python-1",
        secrets={},
        hidden_dir=hidden_dir,
        cache_dir=cache_dir,
        adapter_resolver=_resolver(evaluator),
    )
    second = run_configured_runner(
        config=_config(),
        workspace=workspace,
        run_dir=run_dir,
        operation_id="native-sky-python-2",
        secrets={},
        hidden_dir=hidden_dir,
        cache_dir=cache_dir,
        adapter_resolver=_resolver(evaluator),
    )

    assert first.status == "passed"
    assert first.reward == 42.5
    assert first.metrics["checks"] == 2
    assert first.cache_metadata["cache_kind"] == "skydiscover_python_env"
    assert first.cache_metadata["status"] == "built"
    assert first.adapter_feedback["feedback"] == {"dependency": module_name, "requirement": requirement}
    assert b"native skydiscover python dependency evaluator ok" in first.hidden_stdout
    assert second.status == "passed"
    assert second.reward == 42.5
    assert second.cache_metadata["status"] == "hit"
