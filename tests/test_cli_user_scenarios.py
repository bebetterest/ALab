from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from alab import cli, registry

SCENARIO_COMMANDS: dict[str, set[tuple[str, ...]]] = {
    "root_global_admin": {
        ("help",),
        ("auth", "init"),
        ("auth", "root", "regenerate"),
        ("config", "show"),
        ("config", "set"),
        ("config", "reset"),
        ("config", "validate"),
        ("feedback",),
        ("feedback", "list"),
        ("feedback", "show"),
        ("feedback", "archive"),
        ("dashboard",),
        ("audit", "list"),
        ("audit", "show"),
        ("backup", "prune"),
        ("cache", "prune"),
        ("catalog", "skydiscover", "add"),
        ("catalog", "skydiscover", "update"),
        ("catalog", "skydiscover", "show"),
        ("catalog", "skydiscover", "remove"),
    },
    "project_controller": {
        ("key", "create"),
        ("key", "list"),
        ("key", "revoke"),
        ("project", "init"),
        ("project", "list"),
        ("project", "show"),
        ("project", "config", "show"),
        ("project", "config", "export"),
        ("project", "config", "import"),
        ("project", "config", "set"),
        ("project", "env", "set"),
        ("project", "env", "unset"),
        ("project", "env", "list"),
        ("project", "secret", "set"),
        ("project", "secret", "unset"),
        ("project", "secret", "list"),
        ("project", "secret", "gc"),
        ("project", "validate"),
        ("project", "validation", "archive"),
        ("project", "validation", "unarchive"),
        ("project", "validation", "remove"),
        ("source", "import"),
        ("source", "list"),
        ("source", "show"),
        ("source", "archive"),
        ("source", "unarchive"),
        ("source", "remove"),
        ("status",),
        ("report",),
    },
    "experiment_worker": {
        ("help",),
        ("context", "show"),
        ("context", "repair"),
        ("exp", "create"),
        ("exp", "tag", "add"),
        ("exp", "tag", "remove"),
        ("exp", "tag", "list"),
        ("run",),
        ("submit",),
        ("runs", "list"),
        ("runs", "show"),
        ("artifacts", "list"),
        ("artifacts", "show"),
        ("artifacts", "export"),
        ("logs", "list"),
        ("logs", "show"),
        ("logs", "export"),
        ("annotate", "add"),
        ("annotate", "edit"),
        ("annotate", "archive"),
        ("annotate", "unarchive"),
        ("annotate", "remove"),
        ("annotations", "list"),
        ("annotations", "show"),
        ("status",),
    },
    "collaboration_observer": {
        ("exp", "list"),
        ("exp", "search"),
        ("exp", "show"),
        ("exp", "best"),
        ("exp", "checkout"),
        ("exp", "checkout", "remove"),
        ("observe", "experiments", "list"),
        ("observe", "experiments", "search"),
        ("observe", "experiments", "show"),
        ("observe", "experiments", "best"),
        ("observe", "runs", "list"),
        ("observe", "runs", "show"),
        ("observe", "artifacts", "list"),
        ("observe", "artifacts", "show"),
        ("observe", "artifacts", "export"),
        ("observe", "logs", "list"),
        ("observe", "logs", "show"),
        ("observe", "logs", "export"),
        ("observe", "annotations", "list"),
        ("observe", "annotations", "show"),
        ("runs", "archive"),
        ("runs", "unarchive"),
        ("artifacts", "archive"),
        ("artifacts", "unarchive"),
        ("logs", "archive"),
        ("logs", "unarchive"),
        ("report",),
    },
    "lifecycle_recovery": {
        ("project", "archive"),
        ("project", "unarchive"),
        ("project", "remove"),
        ("project", "locks", "clear-stale"),
        ("exp", "archive"),
        ("exp", "unarchive"),
        ("exp", "remove"),
        ("exp", "worktree", "remove"),
        ("exp", "worktree", "restore"),
        ("exp", "token", "list"),
        ("exp", "token", "revoke"),
        ("exp", "token", "regenerate"),
        ("observe", "runs", "archive"),
        ("observe", "runs", "unarchive"),
        ("observe", "runs", "remove"),
        ("observe", "artifacts", "archive"),
        ("observe", "artifacts", "unarchive"),
        ("observe", "artifacts", "remove"),
        ("observe", "logs", "archive"),
        ("observe", "logs", "unarchive"),
        ("observe", "logs", "remove"),
        ("runs", "remove"),
        ("artifacts", "remove"),
        ("logs", "remove"),
    },
    "misuse_boundaries": {
        ("auth", "root", "regenerate"),
        ("cache", "prune"),
        ("key", "list"),
        ("project", "init"),
        ("project", "config", "show"),
        ("project", "config", "export"),
        ("project", "secret", "set"),
        ("project", "secret", "list"),
        ("source", "import"),
        ("exp", "create"),
        ("exp", "token", "regenerate"),
        ("run",),
        ("logs", "export"),
        ("annotate", "add"),
        ("status",),
    },
}


class Scenario:
    def __init__(self, capsys) -> None:
        self.capsys = capsys
        self.seen: set[tuple[str, ...]] = set()

    def run(
        self,
        args: list[str],
        *,
        code: int = 0,
        cwd: Path | None = None,
    ) -> tuple[str, str]:
        try:
            parsed = cli.pre_scan(list(args))
            spec, _rest = registry.match_command(parsed.argv)
            if spec is not None:
                self.seen.add(spec.path)
            elif not parsed.argv or parsed.argv[0] in {"help", "--help"}:
                self.seen.add(("help",))
        except Exception:
            pass

        previous_cwd = Path.cwd()
        if cwd is not None:
            os.chdir(cwd)
        try:
            actual = cli.run(args)
            captured = self.capsys.readouterr()
        finally:
            if cwd is not None:
                os.chdir(previous_cwd)
        assert actual == code, (
            f"command exited {actual}, expected {code}: {args}\n"
            f"stdout:\n{captured.out}\n"
            f"stderr:\n{captured.err}"
        )
        return captured.out, captured.err


def _assert_recorded(scenario: Scenario, scenario_name: str) -> None:
    expected = SCENARIO_COMMANDS[scenario_name]
    assert expected - scenario.seen == set()


def _field(output: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}: (.+)$", output, re.MULTILINE)
    assert match, output
    return match.group(1)


def _assert_error(output: str, error_code: str, *reasons: str, absent: tuple[str, ...] = ()) -> None:
    assert "object: error" in output
    assert f"error code: {error_code}" in output
    for reason in reasons:
        assert reason in output
    for value in absent:
        assert value not in output


def _table_count(home: Path, table: str) -> int:
    assert re.fullmatch(r"[a-z_]+", table), table
    with sqlite3.connect(home / "alab.db") as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _git(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)
    return completed.stdout.decode("utf-8", errors="replace").strip()


def _init_git_repo(path: Path) -> str:
    _git(["init"], path)
    _git(["config", "user.name", "ALab Test"], path)
    _git(["config", "user.email", "alab@example.test"], path)
    _git(["config", "commit.gpgsign", "false"], path)
    _git(["add", "."], path)
    _git(["commit", "-m", "initial"], path)
    _git(["branch", "-M", "main"], path)
    return _git(["rev-parse", "HEAD"], path)


def _write_scored_source(source: Path, *, score: str = "1") -> None:
    source.mkdir(parents=True)
    (source / "score.txt").write_text(score + "\n", encoding="utf-8")
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

score = Path("score.txt").read_text(encoding="utf-8").strip()
print(f"reward={score}")
print("user scenario stdout")
Path(os.environ["ALAB_RUN_DIR"], "result.txt").write_text(f"artifact reward={score}\\n", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_local_config(path: Path, *, name: str = "Scenario Project") -> None:
    path.write_text(
        f"""
schema_version = 1

[project]
name = "{name}"
task = "Exercise realistic CLI user journeys"
goal = "Keep the scenario reward parseable"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "stdout_regex"
direction = "maximize"
primary_metric = "reward"
pattern = "reward=([0-9.]+)"

[artifacts]
globs = ["run:result.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_free_config(path: Path) -> None:
    path.write_text(
        """
schema_version = 1

[project]
name = "Free Scenario Project"
task = "Submit without an evaluator"
allow_public_exp_create = true

[runner]
type = "none"

[reward]
type = "none"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _init_home(scenario: Scenario, home: Path) -> str:
    out, _err = scenario.run(["--home", str(home), "auth", "init"])
    return _field(out, "root key")


def _init_local_project(
    scenario: Scenario,
    tmp_path: Path,
    home: Path,
    root_key: str,
    *,
    name: str = "Scenario Project",
) -> tuple[str, str, str, str]:
    source = tmp_path / f"{name.lower().replace(' ', '-')}-source"
    config = tmp_path / f"{name.lower().replace(' ', '-')}.toml"
    _write_scored_source(source)
    _write_local_config(config, name=name)
    out, _err = scenario.run(
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
    return (
        _field(out, "project id"),
        _field(out, "admin key"),
        _field(out, "source id"),
        _field(out, "validation id"),
    )


def _one(home: Path, sql: str, params: tuple[object, ...]) -> sqlite3.Row:
    with sqlite3.connect(home / "alab.db") as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(sql, params).fetchone()
    assert row is not None, sql
    return row


def _run_ids_for_exp(home: Path, exp_id: str) -> list[str]:
    with sqlite3.connect(home / "alab.db") as conn:
        return [
            row[0]
            for row in conn.execute(
                "SELECT run_id FROM runs WHERE exp_id = ? ORDER BY started_at, run_id", (exp_id,)
            )
        ]


def _artifact_id_for_run(home: Path, run_id: str) -> str:
    return _one(
        home,
        "SELECT artifact_id FROM artifacts WHERE run_id = ? AND blob_path IS NOT NULL ORDER BY artifact_id LIMIT 1",
        (run_id,),
    )["artifact_id"]


def _stdout_log_id_for_run(home: Path, run_id: str) -> str:
    return _one(
        home,
        "SELECT log_id FROM log_streams WHERE run_id = ? AND stream = 'stdout' AND hidden = 0 ORDER BY log_id LIMIT 1",
        (run_id,),
    )["log_id"]


def test_cli_user_scenario_manifest_covers_every_registered_command() -> None:
    covered = set().union(*SCENARIO_COMMANDS.values())
    registered = set(registry.COMMANDS_BY_PATH)
    assert covered - registered == set()
    assert registered - covered == set()


def test_root_global_admin_user_journey(tmp_path: Path, capsys) -> None:
    scenario = Scenario(capsys)
    home = tmp_path / "home"
    root_key = _init_home(scenario, home)

    scenario.run(["--home", str(home), "help"])
    scenario.run(["--home", str(home), "config", "show"])
    scenario.run(["--home", str(home), "config", "set", "storage.busy_timeout_ms", "6000"])
    scenario.run(["--home", str(home), "config", "validate"])
    scenario.run(["--home", str(home), "config", "reset", "storage.busy_timeout_ms"])

    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "feedback",
            "--kind",
            "suggestion",
            "--title",
            "Scenario feedback",
            "--body",
            "The realistic CLI journey remains usable.",
        ]
    )
    feedback_id = _field(out, "feedback id")
    out, _err = scenario.run(["--home", str(home), "--key", root_key, "feedback", "list"])
    assert feedback_id in out
    out, _err = scenario.run(["--home", str(home), "--key", root_key, "feedback", "show", feedback_id])
    assert "realistic CLI journey" in out
    scenario.run(["--home", str(home), "--key", root_key, "feedback", "archive", feedback_id])

    out, _err = scenario.run(["--home", str(home), "--key", root_key, "auth", "root", "regenerate"])
    old_root_key = root_key
    root_key = _field(out, "root key")
    assert root_key != old_root_key

    scenario.run(["--home", str(home), "dashboard", "--no-open"], code=4)
    scenario.run(
        ["--home", str(home), "--key", root_key, "dashboard", "--no-open", "--port", "70000"],
        code=2,
    )
    scenario.run(["--home", str(home), "--key", root_key, "backup", "prune", "--keep", "0"])
    scenario.run(["--home", str(home), "--key", root_key, "cache", "prune", "--trash-all"])

    upstream = tmp_path / "skydiscover-upstream"
    upstream.mkdir()
    (upstream / "README.md").write_text("one\n", encoding="utf-8")
    first_commit = _init_git_repo(upstream)
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            root_key,
            "catalog",
            "skydiscover",
            "add",
            "--origin-url",
            str(upstream),
            "--ref",
            "main",
        ]
    )
    assert first_commit in out
    scenario.run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "show"])
    (upstream / "README.md").write_text("two\n", encoding="utf-8")
    _git(["add", "README.md"], upstream)
    _git(["commit", "-m", "two"], upstream)
    scenario.run(
        ["--home", str(home), "--key", root_key, "catalog", "skydiscover", "update", "--ref", "main"]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            root_key,
            "catalog",
            "skydiscover",
            "remove",
            "--force",
            "--confirm",
            "skydiscover",
        ]
    )

    out, _err = scenario.run(["--home", str(home), "--key", root_key, "audit", "list"])
    audit_id = _field(out, "audit id")
    scenario.run(["--home", str(home), "--key", root_key, "audit", "show", audit_id])

    _assert_recorded(scenario, "root_global_admin")


def test_project_controller_user_journey(tmp_path: Path, capsys) -> None:
    scenario = Scenario(capsys)
    home = tmp_path / "home"
    root_key = _init_home(scenario, home)
    project_id, admin_key, _source_id, validation_id = _init_local_project(
        scenario, tmp_path, home, root_key, name="Controller Scenario"
    )

    scenario.run(["--home", str(home), "--key", root_key, "project", "list"])
    scenario.run(["--home", str(home), "--key", admin_key, "project", "show", "--project", project_id])
    scenario.run(["--home", str(home), "status", "--project", project_id])

    out, _err = scenario.run(["--home", str(home), "--key", root_key, "key", "create", "--project", project_id])
    created_key_id = _field(out, "key id")
    scenario.run(["--home", str(home), "--key", root_key, "key", "list", "--project", project_id])
    scenario.run(["--home", str(home), "--key", root_key, "key", "revoke", created_key_id, "--project", project_id])

    export_path = tmp_path / "project-config.toml"
    scenario.run(["--home", str(home), "--key", admin_key, "project", "config", "show", "--project", project_id])
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "config",
            "export",
            "--project",
            project_id,
            "--out",
            str(export_path),
        ]
    )
    assert export_path.exists()
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "config",
            "import",
            "--project",
            project_id,
            "--config",
            str(export_path),
            "--skip-baseline-test",
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "config",
            "set",
            "project.goal",
            '"Controller updated goal"',
            "--project",
            project_id,
            "--skip-baseline-test",
        ]
    )

    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "env",
            "set",
            "SCENARIO_MODE",
            "controller",
            "--project",
            project_id,
            "--skip-baseline-test",
        ]
    )
    scenario.run(["--home", str(home), "--key", admin_key, "project", "env", "list", "--project", project_id])
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "env",
            "unset",
            "SCENARIO_MODE",
            "--project",
            project_id,
            "--skip-baseline-test",
        ]
    )

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("secret-value\n", encoding="utf-8")
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "secret",
            "set",
            "API_TOKEN",
            "--value-file",
            str(secret_file),
            "--project",
            project_id,
            "--skip-baseline-test",
        ]
    )
    out, _err = scenario.run(
        ["--home", str(home), "--key", admin_key, "project", "secret", "list", "--project", project_id]
    )
    assert "secret-value" not in out
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "secret",
            "unset",
            "API_TOKEN",
            "--project",
            project_id,
            "--skip-baseline-test",
        ]
    )
    scenario.run(
        ["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id, "--dry-run"]
    )
    scenario.run(
        ["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id, "--apply"]
    )

    scenario.run(["--home", str(home), "--key", admin_key, "project", "validate", "--project", project_id])
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "validation",
            "archive",
            validation_id,
            "--project",
            project_id,
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "validation",
            "unarchive",
            validation_id,
            "--project",
            project_id,
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "validation",
            "remove",
            validation_id,
            "--project",
            project_id,
            "--dry-run",
            "--cascade",
        ]
    )

    alt_source = tmp_path / "controller-alt-source"
    _write_scored_source(alt_source, score="2")
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "source",
            "import",
            "--project",
            project_id,
            "--name",
            "controller-alt",
            "--source-path",
            str(alt_source),
        ]
    )
    alt_source_id = _field(out, "source id")
    scenario.run(["--home", str(home), "--key", admin_key, "source", "list", "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "source", "show", alt_source_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "source", "archive", alt_source_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "source", "unarchive", alt_source_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "source", "archive", alt_source_id, "--project", project_id])
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "source",
            "remove",
            alt_source_id,
            "--project",
            project_id,
            "--dry-run",
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "source",
            "remove",
            alt_source_id,
            "--project",
            project_id,
            "--force",
            "--confirm",
            alt_source_id,
        ]
    )

    report_path = tmp_path / "project-report.md"
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "report",
            "--project",
            project_id,
            "--out",
            str(report_path),
        ]
    )
    assert "# ALab Project Report" in report_path.read_text(encoding="utf-8")

    _assert_recorded(scenario, "project_controller")


def test_experiment_worker_user_journey(tmp_path: Path, capsys) -> None:
    scenario = Scenario(capsys)
    home = tmp_path / "home"
    root_key = _init_home(scenario, home)
    project_id, admin_key, _source_id, _validation_id = _init_local_project(
        scenario, tmp_path, home, root_key, name="Worker Scenario"
    )

    worktree = tmp_path / "worker-exp"
    out, _err = scenario.run(
        ["--home", str(home), "exp", "create", "--project", project_id, "--name", "worker", "--path", str(worktree)]
    )
    exp_id = _field(out, "exp id")

    scenario.run(["--home", str(home), "help"], cwd=worktree)
    scenario.run(["--home", str(home), "status"], cwd=worktree)
    scenario.run(["--home", str(home), "context", "show"], cwd=worktree)
    scenario.run(["--home", str(home), "--key", admin_key, "context", "repair", "--path", str(worktree)])

    scenario.run(["--home", str(home), "exp", "tag", "add", exp_id, "worker"], cwd=worktree)
    scenario.run(["--home", str(home), "exp", "tag", "list", exp_id], cwd=worktree)
    scenario.run(["--home", str(home), "exp", "tag", "remove", exp_id, "worker"], cwd=worktree)

    out, _err = scenario.run(["--home", str(home), "run", "--message", "worker passed run"], cwd=worktree)
    run_id = _field(out, "run id")
    artifact_id = _artifact_id_for_run(home, run_id)
    log_id = _stdout_log_id_for_run(home, run_id)
    scenario.run(["--home", str(home), "runs", "list"], cwd=worktree)
    scenario.run(["--home", str(home), "runs", "show", run_id], cwd=worktree)
    scenario.run(["--home", str(home), "artifacts", "list"], cwd=worktree)
    scenario.run(["--home", str(home), "artifacts", "show", artifact_id], cwd=worktree)
    artifact_export = tmp_path / "worker-artifact.txt"
    scenario.run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(artifact_export)], cwd=worktree)
    assert "artifact reward=1" in artifact_export.read_text(encoding="utf-8")
    scenario.run(["--home", str(home), "logs", "list"], cwd=worktree)
    scenario.run(["--home", str(home), "logs", "show", log_id], cwd=worktree)
    log_export = tmp_path / "worker-stdout.log"
    scenario.run(["--home", str(home), "logs", "export", log_id, "--out", str(log_export)], cwd=worktree)
    assert "reward=1" in log_export.read_text(encoding="utf-8")

    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "annotate",
            "add",
            "--title",
            "Worker note",
            "--body",
            "The run output and artifact are readable.",
        ],
        cwd=worktree,
    )
    annotation_id = _field(out, "annotation id")
    scenario.run(["--home", str(home), "annotations", "list"], cwd=worktree)
    scenario.run(["--home", str(home), "annotations", "show", annotation_id], cwd=worktree)
    scenario.run(
        ["--home", str(home), "annotate", "edit", annotation_id, "--body", "Updated worker note."],
        cwd=worktree,
    )
    scenario.run(["--home", str(home), "annotate", "archive", annotation_id], cwd=worktree)
    scenario.run(["--home", str(home), "annotate", "unarchive", annotation_id], cwd=worktree)
    scenario.run(["--home", str(home), "annotate", "archive", annotation_id], cwd=worktree)
    scenario.run(
        ["--home", str(home), "annotate", "remove", annotation_id, "--force", "--confirm", annotation_id],
        cwd=worktree,
    )

    scenario.run(
        [
            "--home",
            str(home),
            "submit",
            "--message",
            "worker final",
            "--summary",
            "The worker produced a passing local result.",
            "--feedback",
            "The realistic worker CLI flow completed.",
            "--ref",
            "none",
        ],
        cwd=worktree,
    )

    failed_worktree = tmp_path / "worker-failed-exp"
    scenario.run(
        [
            "--home",
            str(home),
            "exp",
            "create",
            "--project",
            project_id,
            "--name",
            "worker-failed",
            "--path",
            str(failed_worktree),
        ]
    )
    (failed_worktree / "main.py").write_text("import sys\nsys.exit(7)\n", encoding="utf-8")
    scenario.run(["--home", str(home), "run", "--message", "worker failed run"], cwd=failed_worktree, code=1)

    free_source = tmp_path / "free-source"
    free_source.mkdir()
    (free_source / "README.md").write_text("free mode\n", encoding="utf-8")
    free_config = tmp_path / "free.project.toml"
    _write_free_config(free_config)
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            root_key,
            "project",
            "init",
            "local",
            "--config",
            str(free_config),
            "--source-path",
            str(free_source),
        ]
    )
    free_project_id = _field(out, "project id")
    free_worktree = tmp_path / "free-exp"
    scenario.run(
        [
            "--home",
            str(home),
            "exp",
            "create",
            "--project",
            free_project_id,
            "--name",
            "free",
            "--path",
            str(free_worktree),
        ]
    )
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "submit",
            "--message",
            "free final",
            "--summary",
            "No evaluator is configured.",
            "--feedback",
            "Direct submit works.",
            "--ref",
            "none",
        ],
        cwd=free_worktree,
    )
    assert "final run id: none" in out

    _assert_recorded(scenario, "experiment_worker")


def test_collaboration_observer_user_journey(tmp_path: Path, capsys) -> None:
    scenario = Scenario(capsys)
    home = tmp_path / "home"
    root_key = _init_home(scenario, home)
    project_id, admin_key, _source_id, _validation_id = _init_local_project(
        scenario, tmp_path, home, root_key, name="Observer Scenario"
    )

    alpha = tmp_path / "alpha-exp"
    bravo = tmp_path / "bravo-exp"
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "exp",
            "create",
            "--project",
            project_id,
            "--name",
            "Alpha",
            "--goal",
            "Observe alpha",
            "--tag",
            "observe",
            "--path",
            str(alpha),
        ]
    )
    alpha_id = _field(out, "exp id")
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "exp",
            "create",
            "--project",
            project_id,
            "--name",
            "Bravo",
            "--goal",
            "Observe bravo",
            "--tag",
            "observe",
            "--path",
            str(bravo),
        ]
    )
    bravo_id = _field(out, "exp id")

    (alpha / "score.txt").write_text("1\n", encoding="utf-8")
    out, _err = scenario.run(["--home", str(home), "run", "--message", "alpha"], cwd=alpha)
    alpha_run_id = _field(out, "run id")
    (bravo / "score.txt").write_text("5\n", encoding="utf-8")
    out, _err = scenario.run(["--home", str(home), "run", "--message", "bravo"], cwd=bravo)
    bravo_run_id = _field(out, "run id")
    bravo_artifact_id = _artifact_id_for_run(home, bravo_run_id)
    bravo_log_id = _stdout_log_id_for_run(home, bravo_run_id)

    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "annotate",
            "add",
            "--project",
            project_id,
            "--target",
            f"exp:{bravo_id}",
            "--title",
            "Observer note",
            "--body",
            "Bravo is visible to same-project observers.",
        ]
    )
    annotation_id = _field(out, "annotation id")

    for command in (["exp", "list"], ["observe", "experiments", "list"]):
        out, _err = scenario.run(["--home", str(home), *command, "--tag", "observe"], cwd=alpha)
        assert alpha_id in out and bravo_id in out
    for command in (["exp", "search"], ["observe", "experiments", "search"]):
        out, _err = scenario.run(["--home", str(home), *command, "--query", "bravo"], cwd=alpha)
        assert bravo_id in out
    for command in (["exp", "show"], ["observe", "experiments", "show"]):
        out, _err = scenario.run(["--home", str(home), *command, bravo_id], cwd=alpha)
        assert "experiment name: Bravo" in out
    for command in (["exp", "best"], ["observe", "experiments", "best"]):
        out, _err = scenario.run(["--home", str(home), *command, "--limit", "1"], cwd=alpha)
        assert bravo_id in out

    scenario.run(["--home", str(home), "observe", "runs", "list"], cwd=alpha)
    scenario.run(["--home", str(home), "observe", "runs", "show", bravo_run_id], cwd=alpha)
    scenario.run(["--home", str(home), "observe", "artifacts", "list"], cwd=alpha)
    scenario.run(["--home", str(home), "observe", "artifacts", "show", bravo_artifact_id], cwd=alpha)
    artifact_export = tmp_path / "observer-artifact.txt"
    scenario.run(
        [
            "--home",
            str(home),
            "observe",
            "artifacts",
            "export",
            bravo_artifact_id,
            "--out",
            str(artifact_export),
        ],
        cwd=alpha,
    )
    assert "artifact reward=5" in artifact_export.read_text(encoding="utf-8")
    scenario.run(["--home", str(home), "observe", "logs", "list"], cwd=alpha)
    scenario.run(["--home", str(home), "observe", "logs", "show", bravo_log_id], cwd=alpha)
    log_export = tmp_path / "observer-log.txt"
    scenario.run(
        ["--home", str(home), "observe", "logs", "export", bravo_log_id, "--out", str(log_export)],
        cwd=alpha,
    )
    assert "reward=5" in log_export.read_text(encoding="utf-8")
    scenario.run(["--home", str(home), "observe", "logs", "list", "--include-hidden"], cwd=alpha, code=4)
    scenario.run(["--home", str(home), "observe", "annotations", "list"], cwd=alpha)
    scenario.run(["--home", str(home), "observe", "annotations", "show", annotation_id], cwd=alpha)

    scenario.run(["--home", str(home), "runs", "archive", alpha_run_id], cwd=alpha)
    scenario.run(["--home", str(home), "runs", "unarchive", alpha_run_id], cwd=alpha)
    scenario.run(["--home", str(home), "--key", admin_key, "artifacts", "archive", bravo_artifact_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "artifacts", "unarchive", bravo_artifact_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "logs", "archive", bravo_log_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "logs", "unarchive", bravo_log_id, "--project", project_id])

    exp_report = tmp_path / "observer-exp-report.md"
    scenario.run(["--home", str(home), "report", "--exp", bravo_id, "--out", str(exp_report)], cwd=alpha)
    assert "# ALab Experiment Report" in exp_report.read_text(encoding="utf-8")

    inspection_path = tmp_path / "bravo-inspection"
    out, _err = scenario.run(
        ["--home", str(home), "exp", "checkout", bravo_id, "--path", str(inspection_path), "--commit", "latest"],
        cwd=alpha,
    )
    inspection_token_id = _field(out, "token id")
    scenario.run(["--home", str(home), "help"], cwd=inspection_path)
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "exp",
            "checkout",
            "remove",
            "--project",
            project_id,
            "--token-id",
            inspection_token_id,
            "--dry-run",
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "exp",
            "checkout",
            "remove",
            "--project",
            project_id,
            "--token-id",
            inspection_token_id,
            "--force",
            "--confirm",
            inspection_token_id,
        ]
    )

    assert alpha_run_id in _run_ids_for_exp(home, alpha_id)
    _assert_recorded(scenario, "collaboration_observer")


def test_lifecycle_and_recovery_user_journey(tmp_path: Path, capsys) -> None:
    scenario = Scenario(capsys)
    home = tmp_path / "home"
    root_key = _init_home(scenario, home)
    project_id, admin_key, _source_id, _validation_id = _init_local_project(
        scenario, tmp_path, home, root_key, name="Lifecycle Scenario"
    )

    worktree = tmp_path / "lifecycle-exp"
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "exp",
            "create",
            "--project",
            project_id,
            "--name",
            "lifecycle",
            "--path",
            str(worktree),
        ]
    )
    exp_id = _field(out, "exp id")
    out, _err = scenario.run(["--home", str(home), "run", "--message", "lifecycle run"], cwd=worktree)
    run_id = _field(out, "run id")
    artifact_id = _artifact_id_for_run(home, run_id)
    log_id = _stdout_log_id_for_run(home, run_id)

    scenario.run(["--home", str(home), "--key", admin_key, "project", "locks", "clear-stale", "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "exp", "token", "list", exp_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "exp", "token", "regenerate", exp_id, "--project", project_id])
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "exp",
            "checkout",
            exp_id,
            "--project",
            project_id,
            "--path",
            str(tmp_path / "lifecycle-inspection"),
        ]
    )
    inspection_token_id = _field(out, "token id")
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "exp",
            "token",
            "revoke",
            exp_id,
            "--project",
            project_id,
            "--token-id",
            inspection_token_id,
        ]
    )

    scenario.run(["--home", str(home), "--key", admin_key, "observe", "runs", "archive", run_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "observe", "runs", "unarchive", run_id, "--project", project_id])
    scenario.run(
        ["--home", str(home), "--key", admin_key, "observe", "artifacts", "archive", artifact_id, "--project", project_id]
    )
    scenario.run(
        ["--home", str(home), "--key", admin_key, "observe", "artifacts", "unarchive", artifact_id, "--project", project_id]
    )
    scenario.run(["--home", str(home), "--key", admin_key, "observe", "logs", "archive", log_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "observe", "logs", "unarchive", log_id, "--project", project_id])

    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "exp",
            "worktree",
            "remove",
            exp_id,
            "--project",
            project_id,
            "--dry-run",
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "exp",
            "worktree",
            "remove",
            exp_id,
            "--project",
            project_id,
            "--force",
            "--confirm",
            exp_id,
        ]
    )
    restored = tmp_path / "lifecycle-restored"
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "exp",
            "worktree",
            "restore",
            exp_id,
            "--project",
            project_id,
            "--path",
            str(restored),
        ]
    )
    assert restored.exists()

    removable = tmp_path / "removable-exp"
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "exp",
            "create",
            "--project",
            project_id,
            "--name",
            "removable",
            "--path",
            str(removable),
        ]
    )
    removable_exp_id = _field(out, "exp id")
    scenario.run(["--home", str(home), "--key", admin_key, "exp", "archive", removable_exp_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "exp", "unarchive", removable_exp_id, "--project", project_id])
    scenario.run(["--home", str(home), "--key", admin_key, "exp", "archive", removable_exp_id, "--project", project_id])
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "exp",
            "remove",
            removable_exp_id,
            "--project",
            project_id,
            "--dry-run",
            "--cascade",
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "exp",
            "remove",
            removable_exp_id,
            "--project",
            project_id,
            "--force",
            "--confirm",
            removable_exp_id,
            "--cascade",
        ]
    )

    remove_project_source = tmp_path / "remove-project-source"
    _write_scored_source(remove_project_source)
    remove_project_config = tmp_path / "remove-project.toml"
    _write_local_config(remove_project_config, name="Remove Project Scenario")
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            root_key,
            "project",
            "init",
            "local",
            "--config",
            str(remove_project_config),
            "--source-path",
            str(remove_project_source),
        ]
    )
    remove_project_id = _field(out, "project id")
    remove_project_admin_key = _field(out, "admin key")
    scenario.run(
        ["--home", str(home), "--key", remove_project_admin_key, "project", "archive", "--project", remove_project_id]
    )
    scenario.run(
        ["--home", str(home), "--key", remove_project_admin_key, "project", "unarchive", "--project", remove_project_id]
    )
    scenario.run(
        ["--home", str(home), "--key", remove_project_admin_key, "project", "archive", "--project", remove_project_id]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            root_key,
            "project",
            "remove",
            "--project",
            remove_project_id,
            "--dry-run",
            "--cascade",
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            root_key,
            "project",
            "remove",
            "--project",
            remove_project_id,
            "--force",
            "--confirm",
            remove_project_id,
            "--cascade",
        ]
    )

    # Exercise remove commands on already archived objects through both canonical and alias routes.
    scenario.run(["--home", str(home), "--key", admin_key, "observe", "runs", "archive", run_id, "--project", project_id])
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "observe",
            "runs",
            "remove",
            run_id,
            "--project",
            project_id,
            "--dry-run",
            "--cascade",
        ]
    )
    scenario.run(["--home", str(home), "--key", admin_key, "artifacts", "archive", artifact_id, "--project", project_id])
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "artifacts",
            "remove",
            artifact_id,
            "--project",
            project_id,
            "--dry-run",
        ]
    )
    scenario.run(["--home", str(home), "--key", admin_key, "logs", "archive", log_id, "--project", project_id])
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "logs",
            "remove",
            log_id,
            "--project",
            project_id,
            "--dry-run",
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "observe",
            "artifacts",
            "remove",
            artifact_id,
            "--project",
            project_id,
            "--dry-run",
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "observe",
            "logs",
            "remove",
            log_id,
            "--project",
            project_id,
            "--dry-run",
        ]
    )
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "runs",
            "remove",
            run_id,
            "--project",
            project_id,
            "--dry-run",
            "--cascade",
        ]
    )

    _assert_recorded(scenario, "lifecycle_recovery")


def test_misuse_and_boundary_user_journey(tmp_path: Path, monkeypatch, capsys) -> None:
    scenario = Scenario(capsys)
    home = tmp_path / "home"
    root_key = _init_home(scenario, home)
    project_id, admin_key, _source_id, _validation_id = _init_local_project(
        scenario, tmp_path, home, root_key, name="Boundary Scenario"
    )

    public_status, _err = scenario.run(["--home", str(home), "status", "--project", project_id])
    with monkeypatch.context() as ambient_context:
        ambient_context.setenv("ALAB_KEY", admin_key)
        ambient_status, _err = scenario.run(["--home", str(home), "status", "--project", project_id])
    assert ambient_status == public_status

    bad_key = "not-a-valid-key"
    out, err = scenario.run(["--home", str(home), "--key", bad_key, "key", "list", "--root"], code=3)
    assert out == ""
    _assert_error(err, "AUTH_DENIED", "invalid credential", absent=(bad_key,))

    out, _err = scenario.run(["--home", str(home), "--key", root_key, "auth", "root", "regenerate"])
    old_root_key = root_key
    root_key = _field(out, "root key")
    out, err = scenario.run(
        ["--home", str(home), "--key", old_root_key, "cache", "prune", "--all"],
        code=3,
    )
    assert out == ""
    _assert_error(err, "AUTH_DENIED", "invalid credential", absent=(old_root_key, root_key))

    boundary_worktree = tmp_path / "boundary-exp"
    out, _err = scenario.run(
        [
            "--home",
            str(home),
            "exp",
            "create",
            "--project",
            project_id,
            "--name",
            "boundary",
            "--path",
            str(boundary_worktree),
        ]
    )
    exp_id = _field(out, "exp id")
    token_path = Path(_field(out, "token path"))
    old_token = token_path.read_text(encoding="utf-8").strip()
    token_status, _err = scenario.run(["--home", str(home), "status"], cwd=boundary_worktree)
    with monkeypatch.context() as ambient_context:
        ambient_context.setenv("ALAB_KEY", root_key)
        ambient_token_status, _err = scenario.run(["--home", str(home), "status"], cwd=boundary_worktree)
    assert ambient_token_status == token_status

    out, _err = scenario.run(
        ["--home", str(home), "--key", admin_key, "exp", "token", "regenerate", exp_id, "--project", project_id]
    )
    new_token = Path(_field(out, "token path")).read_text(encoding="utf-8").strip()
    assert new_token != old_token
    out, err = scenario.run(["--home", str(home), "--key", old_token, "status", "--project", project_id], code=3)
    assert out == ""
    _assert_error(err, "AUTH_DENIED", "invalid credential", absent=(old_token, new_token))

    out, _err = scenario.run(["--home", str(home), "run", "--message", "boundary run"], cwd=boundary_worktree)
    run_id = _field(out, "run id")
    log_id = _stdout_log_id_for_run(home, run_id)

    export_path = tmp_path / "existing-config.toml"
    export_path.write_text("preserve this config\n", encoding="utf-8")
    out, err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "config",
            "export",
            "--project",
            project_id,
            "--out",
            str(export_path),
        ],
        code=2,
    )
    assert out == ""
    _assert_error(err, "OUTPUT_EXISTS", "output path already exists")
    assert export_path.read_text(encoding="utf-8") == "preserve this config\n"
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "config",
            "export",
            "--project",
            project_id,
            "--out",
            str(export_path),
            "--overwrite",
        ]
    )
    assert "preserve this config" not in export_path.read_text(encoding="utf-8")

    out, err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "config",
            "show",
            "--project",
            project_id,
            "--reason",
            "ignored",
        ],
        code=2,
    )
    assert out == ""
    _assert_error(err, "CONFIG_INVALID", "unsupported option --reason")

    missing_value_a = tmp_path / "missing-secret-a.txt"
    missing_value_b = tmp_path / "missing-secret-b.txt"
    out, err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "secret",
            "set",
            "BOUNDARY_TOKEN",
            "--project",
            project_id,
            "--value-file",
            str(missing_value_a),
            "--value-file",
            str(missing_value_b),
        ],
        code=2,
    )
    assert out == ""
    _assert_error(err, "CONFIG_INVALID", "--value-file may be provided once")
    assert not missing_value_a.exists()
    assert not missing_value_b.exists()

    secret_file = tmp_path / "boundary-secret.txt"
    secret_file.write_text("boundary-secret-value\n", encoding="utf-8")
    scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "secret",
            "set",
            "BOUNDARY_TOKEN",
            "--project",
            project_id,
            "--value-file",
            str(secret_file),
            "--skip-baseline-test",
        ]
    )
    out, _err = scenario.run(
        ["--home", str(home), "--key", admin_key, "project", "secret", "list", "--project", project_id]
    )
    assert "BOUNDARY_TOKEN" in out
    assert "boundary-secret-value" not in out

    missing_config = tmp_path / "missing-boundary-config.toml"
    missing_source = tmp_path / "missing-boundary-source"
    project_count_before = _table_count(home, "projects")
    out, err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            root_key,
            "project",
            "init",
            "local",
            "--config",
            str(missing_config),
            "--source-path",
            str(boundary_worktree),
        ],
        code=2,
    )
    assert out == ""
    _assert_error(err, "CONFIG_INVALID", "config file not found")
    assert _table_count(home, "projects") == project_count_before

    valid_config = tmp_path / "missing-source-boundary.toml"
    _write_local_config(valid_config, name="Missing Source Boundary")
    out, err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            root_key,
            "project",
            "init",
            "local",
            "--config",
            str(valid_config),
            "--source-path",
            str(missing_source),
        ],
        code=2,
    )
    assert out == ""
    _assert_error(err, "SOURCE_INVALID", "source path not found")
    assert _table_count(home, "projects") == project_count_before

    source_count_before = _table_count(home, "sources")
    out, err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "source",
            "import",
            "--project",
            project_id,
            "--source-path",
            str(missing_source),
        ],
        code=2,
    )
    assert out == ""
    _assert_error(err, "SOURCE_INVALID", "source path not found")
    assert _table_count(home, "sources") == source_count_before

    existing_log_export = tmp_path / "existing-log.txt"
    existing_log_export.write_text("preserve log\n", encoding="utf-8")
    out, err = scenario.run(
        ["--home", str(home), "logs", "export", log_id, "--out", str(existing_log_export)],
        cwd=boundary_worktree,
        code=2,
    )
    assert out == ""
    _assert_error(err, "OUTPUT_EXISTS", "output path already exists")
    assert existing_log_export.read_text(encoding="utf-8") == "preserve log\n"

    annotations_before = _table_count(home, "annotations")
    (boundary_worktree / "main.py").write_text("print('dirty boundary')\n", encoding="utf-8")
    out, err = scenario.run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "annotate",
            "add",
            "--project",
            project_id,
            "--target",
            "path:main.py",
            "--body",
            "dirty shorthand should not bind",
        ],
        cwd=boundary_worktree,
        code=4,
    )
    assert out == ""
    _assert_error(err, "GIT_STATE_INVALID", "path/line annotation shorthand requires a clean experiment worktree")
    assert _table_count(home, "annotations") == annotations_before

    _assert_recorded(scenario, "misuse_boundaries")


def test_cli_subprocess_short_local_workflow(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "PYTHONPATH": str(repo_root / "src"),
        "ALAB_DEBUG": "",
    }
    home = tmp_path / "subprocess-home"
    source = tmp_path / "subprocess-source"
    config = tmp_path / "subprocess.toml"
    worktree = tmp_path / "subprocess-exp"
    _write_scored_source(source)
    _write_local_config(config, name="Subprocess Scenario")

    def run_subprocess(args: list[str], *, cwd: Path | None = None, code: int = 0) -> str:
        completed = subprocess.run(
            [sys.executable, "-m", "alab", *args],
            cwd=cwd or repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == code, (
            f"subprocess exited {completed.returncode}, expected {code}: {args}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
        return completed.stdout

    auth_out = run_subprocess(["--home", str(home), "auth", "init"])
    root_key = _field(auth_out, "root key")
    project_out = run_subprocess(
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
    project_id = _field(project_out, "project id")
    exp_out = run_subprocess(
        ["--home", str(home), "exp", "create", "--project", project_id, "--name", "subprocess", "--path", str(worktree)]
    )
    assert "token path:" in exp_out
    run_out = run_subprocess(["--home", str(home), "run", "--message", "subprocess run"], cwd=worktree)
    assert "run status: passed" in run_out
    submit_out = run_subprocess(
        [
            "--home",
            str(home),
            "submit",
            "--message",
            "subprocess final",
            "--summary",
            "The module entrypoint completed the workflow.",
            "--feedback",
            "Subprocess smoke passed.",
            "--ref",
            "none",
        ],
        cwd=worktree,
    )
    assert "submit accepted: true" in submit_out
