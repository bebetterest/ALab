#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from alab import cli
from alab.auth import create_credential
from alab.db import canonical_json
from alab.home import Home

EXAMPLE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_HOME = EXAMPLE_DIR / ".run" / "alab-home"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@dataclass
class ProjectSeed:
    project_id: str
    slug: str
    name: str
    task: str
    goal: str
    status: str
    runner_type: str
    reward_type: str
    reward_direction: str
    visibility_scope: str
    allow_public: bool
    archived: bool = False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a rich ALab dashboard showcase home.")
    parser.add_argument("--home", type=Path, default=DEFAULT_HOME, help="Output ALab home path.")
    parser.add_argument("--force", action="store_true", help="Replace an existing demo home.")
    args = parser.parse_args(argv)

    home = Home(args.home.expanduser().resolve())
    if home.path.exists():
        if not args.force:
            raise SystemExit(f"{home.path} already exists; pass --force to replace it")
        shutil.rmtree(home.path)
    home.path.parent.mkdir(parents=True, exist_ok=True)

    root_key = _init_home(home)
    with sqlite3.connect(home.db_path) as conn:
        conn.row_factory = sqlite3.Row
        admin_keys, token_keys = _seed_home(conn, home)

    _write_feedback(home)
    secrets_dir = home.path.parent / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    keys_path = secrets_dir / "dashboard-showcase-credentials.txt"
    keys_path.write_text(
        "\n".join(
            [
                "# Generated dashboard showcase credentials. This file is under ignored .run/.",
                f"root_key={root_key}",
                *[f"admin_key_{idx + 1}={key}" for idx, key in enumerate(admin_keys)],
                *[f"token_key_{idx + 1}={key}" for idx, key in enumerate(token_keys)],
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"home={home.path}")
    print(f"root_key={root_key}")
    print(f"credentials_file={keys_path}")
    print("dashboard_command=")
    print(f"  uv run --locked alab --home {home.path} --key {root_key} dashboard --refresh-seconds 0")
    return 0


def _init_home(home: Home) -> str:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = cli.run(["--home", str(home.path), "auth", "init"])
    if code != 0:
        raise SystemExit(code)
    for line in stdout.getvalue().splitlines():
        if line.startswith("root key: "):
            return line.split(": ", 1)[1]
    raise SystemExit("auth init did not render a root key")


def _seed_home(conn: sqlite3.Connection, home: Home) -> tuple[list[str], list[str]]:
    projects = [
        ProjectSeed(
            project_id="proj-showcase-clinic-ops",
            slug="clinic-ops",
            name="Clinic Ops Planner",
            task="Assign clinic orders to warehouses under inventory and cold-chain constraints.",
            goal="Show a healthy local/Docker-style project with many runs and artifacts.",
            status="valid",
            runner_type="docker",
            reward_type="file",
            reward_direction="maximize",
            visibility_scope="same_project",
            allow_public=True,
        ),
        ProjectSeed(
            project_id="proj-showcase-incident-triage",
            slug="incident-triage",
            name="Incident Triage Classifier",
            task="Classify support tickets with hidden verifier logs and public collaboration traces.",
            goal="Show failed, timeout, hidden-log, annotation, and submit workflows.",
            status="valid",
            runner_type="harbor",
            reward_type="harbor",
            reward_direction="maximize",
            visibility_scope="same_project",
            allow_public=True,
        ),
        ProjectSeed(
            project_id="proj-showcase-circle-pack",
            slug="circle-pack",
            name="SkyDiscover Circle Packing",
            task="Improve packed-circle density through a Python evaluator bundle.",
            goal="Show SkyDiscover catalog/cache/system diagnostics and a minimize-style metric.",
            status="invalid",
            runner_type="skydiscover_python",
            reward_type="skydiscover",
            reward_direction="minimize",
            visibility_scope="same_project",
            allow_public=False,
        ),
        ProjectSeed(
            project_id="proj-showcase-archived-router",
            slug="archived-router",
            name="Archived Routing Baseline",
            task="Historical routing baseline kept for audit and lifecycle demonstration.",
            goal="Show archived project/experiment/source rows without active mutations.",
            status="archived",
            runner_type="local",
            reward_type="exit_code",
            reward_direction="maximize",
            visibility_scope="same_project",
            allow_public=False,
            archived=True,
        ),
    ]

    admin_keys: list[str] = []
    token_keys: list[str] = []
    for index, project in enumerate(projects):
        key_id, raw_admin = create_credential(conn, credential_type="admin", project_id=project.project_id)
        admin_keys.append(raw_admin)
        _insert_project(conn, home, project, key_id, index)
        token_keys.extend(_insert_project_activity(conn, home, project, key_id, index))

    _insert_system_state(conn, home)
    _insert_global_audit(conn)
    return admin_keys, token_keys


def _insert_project(conn: sqlite3.Connection, home: Home, project: ProjectSeed, admin_key_id: str, index: int) -> None:
    config_version = 2 if project.slug == "clinic-ops" else 1
    validation_id = f"val-{project.slug}-baseline"
    config = _project_config(project)
    created = _ts(index, 0)
    updated = _ts(index, 50)
    pre_archive = "valid" if project.archived else None
    archived_at = _ts(index, 70) if project.archived else None
    conn.execute(
        """
        INSERT INTO projects(project_id, status, pre_archive_status, canonical_repo_path, control_path,
          secret_fingerprint_key, latest_attempted_config_version, active_valid_config_version,
          active_validation_id, created_at, updated_at, archived_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project.project_id,
            project.status,
            pre_archive,
            str(home.projects_path / project.project_id / "repo.git"),
            str(home.project_workspaces_path / project.project_id),
            sha256(project.project_id.encode("utf-8")).digest(),
            config_version,
            config_version if project.status == "valid" else None,
            validation_id,
            created,
            updated,
            archived_at,
        ),
    )
    if project.slug == "clinic-ops":
        old_config = dict(config)
        old_config["runner"] = dict(old_config["runner"], timeout_seconds=120)
        _insert_config(conn, project, 1, old_config, "failed", admin_key_id, _ts(index, 2))
    _insert_config(conn, project, config_version, config, "passed" if project.status != "invalid" else "failed", admin_key_id, _ts(index, 5))
    _insert_secret(conn, project, admin_key_id, index)
    _insert_source(conn, project, index, archived=project.archived)
    _insert_validation(conn, home, project, validation_id, config_version, index, admin_key_id)
    _audit(
        conn,
        project,
        None,
        admin_key_id,
        "admin",
        "add",
        "project",
        project.project_id,
        _ts(index, 6),
        metadata={"config_version": config_version, "runner": project.runner_type},
    )


def _insert_project_activity(conn: sqlite3.Connection, home: Home, project: ProjectSeed, admin_key_id: str, index: int) -> list[str]:
    token_keys: list[str] = []
    exp_specs = _experiment_specs(project)
    latest_run_for_project: tuple[str, str, str] | None = None
    for exp_index, spec in enumerate(exp_specs):
        exp_id = f"exp-{project.slug}-{spec['slug']}"
        token_id, raw_token = create_credential(
            conn,
            credential_type="token",
            project_id=project.project_id,
            exp_id=exp_id,
            token_mode="worktree",
            registered_path_hash=f"hash-{project.slug}-{spec['slug']}",
        )
        token_keys.append(raw_token)
        latest_run_id, latest_commit = _insert_experiment(conn, home, project, spec, exp_id, token_id, admin_key_id, index, exp_index)
        latest_run_for_project = (exp_id, latest_run_id, latest_commit)
    if latest_run_for_project:
        exp_id, run_id, commit = latest_run_for_project
        conn.execute(
            "UPDATE experiments SET latest_run_id = ?, latest_commit = ? WHERE exp_id = ?",
            (run_id, commit, exp_id),
        )
    return token_keys


def _insert_experiment(
    conn: sqlite3.Connection,
    home: Home,
    project: ProjectSeed,
    spec: dict[str, Any],
    exp_id: str,
    token_id: str,
    admin_key_id: str,
    project_index: int,
    exp_index: int,
) -> tuple[str, str]:
    source_id = f"src-{project.slug}-main"
    validation_id = f"val-{project.slug}-baseline"
    created = _ts(project_index, 10 + exp_index * 8)
    updated = _ts(project_index, 28 + exp_index * 8)
    status = spec["status"]
    pre_archive = spec.get("pre_archive")
    archived_at = _ts(project_index, 64 + exp_index) if status == "archived" else None
    closed_at = _ts(project_index, 48 + exp_index) if status == "closed" else None
    branch_name = f"alab/exp/{project.slug}/{spec['slug']}"
    metadata = {
        "schema_version": 1,
        "name": spec["name"],
        "name_slug": spec["slug"],
        "goal": spec["goal"],
        "owner": spec.get("owner", "demo-agent"),
        "hypothesis": spec.get("hypothesis", "Tune the solution and compare reward trend."),
    }
    policy = {"schema_version": 1, "visibility": {"scope": spec.get("visibility", project.visibility_scope), "experiment_ids": []}}
    final_run_id = None
    final_commit = None
    run_ids: list[tuple[str, str]] = []
    for run_index, run in enumerate(spec["runs"]):
        run_id = f"run-{project.slug}-{spec['slug']}-{run_index + 1:02d}"
        commit = f"{project.slug[:4]}{exp_index}{run_index:02d}abc"
        _insert_run(conn, home, project, exp_id, run_id, commit, run, project_index, exp_index, run_index, token_id)
        run_ids.append((run_id, commit))
        if run.get("final"):
            final_run_id = run_id
            final_commit = commit
    latest_run_id, latest_commit = run_ids[-1]
    worktree_state = spec.get("worktree_state", "active")
    worktree_path = str(home.project_workspaces_path / project.project_id / spec["slug"]) if worktree_state == "active" else None
    conn.execute(
        """
        INSERT INTO experiments(exp_id, project_id, source_id, bound_config_version, bound_validation_id,
          baseline_commit, branch_name, worktree_path, worktree_path_hash, worktree_state, status,
          pre_archive_status, metadata_json, policy_json, latest_run_id, latest_commit, final_run_id,
          final_commit, final_run_removed_at, final_run_removed_by, final_run_removed_audit_id,
          created_at, updated_at, closed_at, archived_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?)
        """,
        (
            exp_id,
            project.project_id,
            source_id,
            2 if project.slug == "clinic-ops" else 1,
            validation_id,
            f"base-{project.slug}",
            branch_name,
            worktree_path,
            f"hash-{project.slug}-{spec['slug']}" if worktree_state == "active" else None,
            worktree_state,
            status,
            pre_archive,
            canonical_json(metadata),
            canonical_json(policy),
            latest_run_id,
            latest_commit,
            final_run_id,
            final_commit,
            created,
            updated,
            closed_at,
            archived_at,
        ),
    )
    _insert_path_registry(conn, home, project, exp_id, spec["slug"], token_id, worktree_state, created)
    for tag in spec.get("tags", []):
        conn.execute(
            """
            INSERT INTO experiment_tags(project_id, exp_id, tag_slug, created_by_type, created_by_id, created_at)
            VALUES (?, ?, ?, 'token', ?, ?)
            """,
            (project.project_id, exp_id, tag, token_id, _ts(project_index, 16 + exp_index)),
        )
    if final_run_id:
        _insert_submission(conn, project, exp_id, final_run_id, final_commit or latest_commit, token_id, project_index, exp_index)
    _insert_annotations(conn, project, exp_id, final_run_id or latest_run_id, token_id, project_index, exp_index)
    _audit(conn, project, exp_id, admin_key_id, "admin", "add", "experiment", exp_id, created, metadata={"branch": branch_name})
    if status in {"closed", "archived"}:
        _audit(conn, project, exp_id, admin_key_id, "admin", "archive" if status == "archived" else "update", "experiment", exp_id, updated, metadata={"status": status})
    return latest_run_id, latest_commit


def _insert_run(
    conn: sqlite3.Connection,
    home: Home,
    project: ProjectSeed,
    exp_id: str,
    run_id: str,
    commit: str,
    run: dict[str, Any],
    project_index: int,
    exp_index: int,
    run_index: int,
    token_id: str,
) -> None:
    started = _ts(project_index, 20 + exp_index * 8 + run_index)
    ended = None if run["status"] == "running" else _ts(project_index, 21 + exp_index * 8 + run_index)
    record = {
        "schema_version": 1,
        "runner": {"type": project.runner_type, "host": "demo-host", "platform": "darwin-arm64"},
        "metrics": {"reward": run.get("reward"), **run.get("metrics", {})},
        "warning_codes": run.get("warnings", []),
        "failure_reason": run.get("failure_reason"),
        "duration_seconds": run.get("duration", 12 + run_index),
    }
    conn.execute(
        """
        INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, exit_code,
          reward_value, reward_parse_status, archive_status, archived_at, unarchived_at, started_at,
          ended_at, rolled_back_auto_commit, record_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            run_id,
            exp_id,
            project.project_id,
            commit,
            2 if project.slug == "clinic-ops" else 1,
            run["status"],
            run.get("exit_code"),
            run.get("reward"),
            run.get("reward_parse_status", "parsed" if run.get("reward") is not None else "missing"),
            run.get("archive_status", "active"),
            run.get("archived_at"),
            started,
            ended,
            run.get("rolled_back_auto_commit"),
            canonical_json(record),
        ),
    )
    _write_run_files(conn, home, project, exp_id, run_id, run, project_index, exp_index, run_index)
    _audit(conn, project, exp_id, token_id, "token", "add", "run", run_id, started, metadata={"status": run["status"], "reward": run.get("reward")})


def _write_run_files(
    conn: sqlite3.Connection,
    home: Home,
    project: ProjectSeed,
    exp_id: str,
    run_id: str,
    run: dict[str, Any],
    project_index: int,
    exp_index: int,
    run_index: int,
) -> None:
    store = home.projects_path / project.project_id / "artifacts"
    stdout_text = f"{project.name} / {exp_id} / {run_id}\nstatus={run['status']}\nreward={run.get('reward')}\n"
    stderr_text = run.get("stderr", "")
    hidden_text = f"hidden evaluator trace for {run_id}\nprivate score components: {run.get('metrics', {})}\n"
    _write_log(conn, store, project, exp_id, run_id, None, "stdout", stdout_text, False, project_index, exp_index, run_index)
    if stderr_text:
        _write_log(conn, store, project, exp_id, run_id, None, "stderr", stderr_text, False, project_index, exp_index, run_index)
    if run.get("hidden_log"):
        _write_log(conn, store, project, exp_id, run_id, None, "hidden_stdout", hidden_text, True, project_index, exp_index, run_index)
    if run.get("artifact_text"):
        _write_artifact(conn, store, project, exp_id, run_id, None, "workspace", f"reports/{run_id}.md", run["artifact_text"], "captured", project_index, exp_index, run_index)
    if run.get("artifact_json"):
        _write_artifact(conn, store, project, exp_id, run_id, None, "run", f"metrics/{run_id}.json", json.dumps(run["artifact_json"], indent=2), "captured", project_index, exp_index, run_index)
    if run.get("artifact_image"):
        _write_artifact(conn, store, project, exp_id, run_id, None, "workspace", f"plots/{run_id}.png", PNG_1X1, "captured", project_index, exp_index, run_index)
    if run.get("artifact_error"):
        _write_artifact(conn, store, project, exp_id, run_id, None, "workspace", f"reports/{run_id}-missing.txt", b"", "error", project_index, exp_index, run_index, capture_error="file was not produced")
    if run.get("artifact_skipped"):
        _write_artifact(conn, store, project, exp_id, run_id, None, "workspace", f"large/{run_id}.bin", b"", "skipped", project_index, exp_index, run_index)


def _write_log(
    conn: sqlite3.Connection,
    store: Path,
    project: ProjectSeed,
    exp_id: str | None,
    run_id: str | None,
    validation_id: str | None,
    stream: str,
    text: str,
    hidden: bool,
    project_index: int,
    exp_index: int,
    run_index: int,
) -> None:
    rel = f"logs/{exp_id or validation_id}/{run_id or validation_id}-{stream}.log"
    path = store / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    payload = text.encode("utf-8")
    log_id = f"log-{project.slug}-{exp_index}-{run_index}-{stream.replace('_', '-')}"
    conn.execute(
        """
        INSERT INTO log_streams(log_id, project_id, exp_id, run_id, validation_id, stream, size_bytes,
          stored_bytes, content_hash, truncated, hidden, archive_status, file_path, preview_text,
          archived_at, unarchived_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'active', ?, ?, NULL, NULL, ?)
        """,
        (
            log_id,
            project.project_id,
            exp_id,
            run_id,
            validation_id,
            stream,
            len(payload),
            len(payload),
            "sha256:" + sha256(payload).hexdigest(),
            1 if hidden else 0,
            rel,
            text[:160],
            _ts(project_index, 22 + exp_index * 8 + run_index),
        ),
    )


def _write_artifact(
    conn: sqlite3.Connection,
    store: Path,
    project: ProjectSeed,
    exp_id: str | None,
    run_id: str | None,
    validation_id: str | None,
    root: str,
    relative_path: str,
    payload: Any,
    status: str,
    project_index: int,
    exp_index: int,
    run_index: int,
    *,
    capture_error: str | None = None,
) -> None:
    if isinstance(payload, bytes):
        data = payload
    elif isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    blob_path = None
    if status == "captured":
        blob_path = f"blobs/{run_id or validation_id}/{relative_path}"
        path = store / blob_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    artifact_id = f"art-{project.slug}-{exp_index}-{run_index}-{relative_path.split('/')[-1].replace('.', '-')}"
    conn.execute(
        """
        INSERT INTO artifacts(artifact_id, project_id, exp_id, run_id, validation_id, root, relative_path,
          size_bytes, content_hash, status, archive_status, blob_path, capture_error, archived_at,
          unarchived_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, NULL, NULL, ?)
        """,
        (
            artifact_id,
            project.project_id,
            exp_id,
            run_id,
            validation_id,
            root,
            relative_path,
            len(data) if status == "captured" else None,
            "sha256:" + sha256(data).hexdigest() if status == "captured" else None,
            status,
            blob_path,
            capture_error,
            _ts(project_index, 23 + exp_index * 8 + run_index),
        ),
    )


def _insert_config(conn: sqlite3.Connection, project: ProjectSeed, version: int, config: dict[str, Any], status: str, key_id: str, created: str) -> None:
    payload = canonical_json(config)
    conn.execute(
        """
        INSERT INTO project_config_versions(project_id, version, canonical_config_json, config_hash,
          baseline_required, validation_status, inherited_from_validation_id, created_at, created_by_credential_id)
        VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (project.project_id, version, payload, "sha256:" + sha256(payload.encode("utf-8")).hexdigest(), 1 if version == 1 else 0, status, created, key_id),
    )


def _insert_secret(conn: sqlite3.Connection, project: ProjectSeed, admin_key_id: str, index: int) -> None:
    for name in ("API_TOKEN", "WAREHOUSE_PASSWORD") if project.slug == "clinic-ops" else ("EVAL_TOKEN",):
        value = f"demo-secret-value-for-{project.slug}-{name.lower()}"
        fingerprint = "hmac-sha256:" + sha256(value.encode("utf-8")).hexdigest()
        conn.execute(
            """
            INSERT INTO secret_values(secret_value_id, project_id, name, value, fingerprint, created_at,
              created_by_credential_id, replaced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (f"sec-{project.slug}-{name.lower().replace('_', '-')}", project.project_id, name, value, fingerprint, _ts(index, 4), admin_key_id),
        )


def _insert_source(conn: sqlite3.Connection, project: ProjectSeed, index: int, *, archived: bool) -> None:
    source_id = f"src-{project.slug}-main"
    metadata = {
        "schema_version": 1,
        "origin": "dashboard-showcase",
        "adapter": project.runner_type,
        "files": ["solution.py", "README.md", "data/sample.json"],
    }
    conn.execute(
        """
        INSERT INTO sources(source_id, project_id, name, name_slug, source_ref, source_commit, tree_hash,
          status, origin_metadata_json, created_at, archived_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            project.project_id,
            "main-source",
            "main-source",
            f"alab/source/{source_id}",
            f"commit-{project.slug}-main",
            "alab-tree-sha256-v1:" + sha256(project.slug.encode("utf-8")).hexdigest(),
            "archived" if archived else "active",
            canonical_json(metadata),
            _ts(index, 3),
            _ts(index, 71) if archived else None,
        ),
    )


def _insert_validation(conn: sqlite3.Connection, home: Home, project: ProjectSeed, validation_id: str, config_version: int, index: int, admin_key_id: str) -> None:
    status = "failed" if project.status == "invalid" else "passed"
    record = {
        "schema_version": 1,
        "metrics": {"reward": 0.72 if project.reward_direction == "maximize" else 0.18},
        "warning_codes": ["BASELINE_SLOW"] if project.runner_type.startswith("sky") else [],
        "created_by": admin_key_id,
    }
    conn.execute(
        """
        INSERT INTO project_validations(validation_id, project_id, config_version, source_ref, source_commit,
          status, exit_code, reward_value, reward_parse_status, archive_status, archived_at, unarchived_at,
          started_at, ended_at, record_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', NULL, NULL, ?, ?, ?)
        """,
        (
            validation_id,
            project.project_id,
            config_version,
            f"alab/source/src-{project.slug}-main",
            f"commit-{project.slug}-main",
            status,
            0 if status == "passed" else 1,
            0.72 if project.reward_direction == "maximize" else 0.18,
            "parsed",
            _ts(index, 7),
            _ts(index, 8),
            canonical_json(record),
        ),
    )
    store = home.projects_path / project.project_id / "artifacts"
    validation_text = f"validation={validation_id}\nstatus={status}\nrunner={project.runner_type}\n"
    _write_log(conn, store, project, None, None, validation_id, "stdout", validation_text, False, index, 99, 0)
    if status == "failed":
        _write_log(conn, store, project, None, None, validation_id, "stderr", "baseline validation failed in demo\n", False, index, 99, 1)
    _write_artifact(
        conn,
        store,
        project,
        None,
        None,
        validation_id,
        "workspace",
        f"validations/{validation_id}.json",
        {"validation_id": validation_id, "status": status, "runner": project.runner_type},
        "captured",
        index,
        99,
        2,
    )


def _insert_submission(conn: sqlite3.Connection, project: ProjectSeed, exp_id: str, final_run_id: str, final_commit: str, token_id: str, project_index: int, exp_index: int) -> None:
    conn.execute(
        """
        INSERT INTO experiment_submissions(submission_id, project_id, exp_id, final_run_id, final_commit,
          message, summary, feedback, refs_json, created_at, created_by_credential_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"sub-{project.slug}-{exp_index}",
            project.project_id,
            exp_id,
            final_run_id,
            final_commit,
            "Submit best observed demo result",
            f"Final run {final_run_id} is the selected showcase submission.",
            "Dashboard should show this as the final submission and preserve run context.",
            canonical_json({"schema_version": 1, "artifacts": ["report", "metrics"], "logs": ["stdout", "hidden_stdout"]}),
            _ts(project_index, 45 + exp_index),
            token_id,
        ),
    )


def _insert_annotations(conn: sqlite3.Connection, project: ProjectSeed, exp_id: str, run_id: str, token_id: str, project_index: int, exp_index: int) -> None:
    annotations = [
        ("run", run_id, {"run_id": run_id}, "Compare this run against the current best before pruning."),
        ("experiment", exp_id, {"exp_id": exp_id}, "Good candidate for follow-up experiment."),
    ]
    for idx, (target_type, target_id, target, body) in enumerate(annotations):
        annotation_id = f"ann-{project.slug}-{exp_index}-{idx}"
        conn.execute(
            """
            INSERT INTO annotations(annotation_id, project_id, target_type, target_id, target_json,
              resolved_commit, current_revision, visibility_json, status, created_by_type,
              created_by_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, 'active', 'token', ?, ?, ?)
            """,
            (
                annotation_id,
                project.project_id,
                target_type,
                target_id,
                canonical_json({"schema_version": 1, **target}),
                None,
                canonical_json({"schema_version": 1, "scope": project.visibility_scope}),
                token_id,
                _ts(project_index, 42 + exp_index + idx),
                _ts(project_index, 42 + exp_index + idx),
            ),
        )
        conn.execute(
            """
            INSERT INTO annotation_revisions(annotation_id, revision, body, author_label, created_at,
              created_by_type, created_by_id)
            VALUES (?, 1, ?, ?, ?, 'token', ?)
            """,
            (annotation_id, body, "demo worker", _ts(project_index, 42 + exp_index + idx), token_id),
        )


def _insert_path_registry(conn: sqlite3.Connection, home: Home, project: ProjectSeed, exp_id: str, slug: str, token_id: str, worktree_state: str, created: str) -> None:
    status = "active" if worktree_state == "active" else "removed"
    removed_at = None if status == "active" else _ts(9, 80)
    conn.execute(
        """
        INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id,
          exp_id, token_id, status, removed_at, removed_by_credential_id, created_at, updated_at)
        VALUES (?, ?, ?, 'experiment', (SELECT home_id FROM homes LIMIT 1), ?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (
            f"path-{project.slug}-{slug}",
            f"hash-{project.slug}-{slug}",
            str(home.project_workspaces_path / project.project_id / slug),
            project.project_id,
            exp_id,
            token_id,
            status,
            removed_at,
            created,
            removed_at or created,
        ),
    )


def _insert_system_state(conn: sqlite3.Connection, home: Home) -> None:
    conn.executemany(
        """
        INSERT INTO runtime_capabilities(capability_key, fingerprint, status, details_json, checked_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            ("docker:linux/amd64", "sha256:demo-amd64", "supported", canonical_json({"version": "25.0", "platform": "linux/amd64"}), _ts(0, 90)),
            ("docker:linux/arm64", "sha256:demo-arm64", "supported", canonical_json({"version": "25.0", "platform": "linux/arm64"}), _ts(0, 91)),
            ("skydiscover:python", "sha256:demo-sky-py", "error", canonical_json({"reason": "demo evaluator missing optional dependency"}), _ts(0, 92)),
        ],
    )
    sky_path = home.sources_path / "skydiscover" / "catalog-demo"
    sky_path.mkdir(parents=True, exist_ok=True)
    conn.execute(
        """
        INSERT INTO catalogs(catalog_key, catalog_type, origin_url, pinned_commit, local_path, status,
          metadata_json, retrieved_at, updated_at, removed_at)
        VALUES ('skydiscover', 'skydiscover', ?, ?, ?, 'active', ?, ?, ?, NULL)
        """,
        (
            "https://example.invalid/skydiscover/catalog.git",
            "demo-catalog-commit",
            str(sky_path),
            canonical_json({"schema_version": 1, "tasks": ["circle-packing", "routing"]}),
            _ts(0, 86),
            _ts(0, 93),
        ),
    )
    cache_rows = [
        ("cache-docker-clinic", "docker_image", "clinic-ops:Dockerfile", "proj-showcase-clinic-ops", None, "alab/demo/clinic:latest", 148_000_000, "active", {"platform": "linux/arm64"}, _ts(0, 54), _ts(0, 88), None),
        ("cache-sky-python", "skydiscover_python_env", "sky-python-demo", "proj-showcase-circle-pack", str(home.cache_path / "skydiscover-python-envs" / "demo"), None, 72_000_000, "active", {"python": "3.12"}, _ts(0, 55), _ts(0, 89), None),
        ("cache-trash-old", "trash", "removed-worktrees", None, str(home.cache_path / "trash" / "old"), None, 9_000_000, "removed", {"reason": "pruned during demo"}, _ts(0, 40), _ts(0, 50), _ts(0, 94)),
    ]
    conn.executemany(
        """
        INSERT INTO cache_entries(cache_id, cache_kind, cache_key, project_id, path, docker_tag,
          size_bytes, status, metadata_json, created_at, last_used_at, removed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (cache_id, kind, key, project_id, path, docker_tag, size, status, canonical_json(metadata), created, used, removed)
            for cache_id, kind, key, project_id, path, docker_tag, size, status, metadata, created, used, removed in cache_rows
        ],
    )
    conn.execute(
        """
        INSERT INTO locks(lock_name, owner_operation_id, owner_host, owner_pid, project_id, exp_id,
          acquired_at, heartbeat_at, expires_at)
        VALUES (?, ?, 'demo-host', 4242, ?, ?, ?, ?, ?)
        """,
        (
            "run:proj-showcase-incident-triage:exp-incident-triage-public-rules",
            "op-demo-running-hidden-verifier",
            "proj-showcase-incident-triage",
            "exp-incident-triage-public-rules",
            _ts(0, 95),
            _ts(0, 96),
            _ts(0, 120),
        ),
    )


def _insert_global_audit(conn: sqlite3.Connection) -> None:
    rows = [
        ("aud-demo-root-regenerate", None, None, None, "root", "regenerate", "credential", "cred-root-demo", False, "rotated root key during demo preparation", {}, {"surface": "auth"}, _ts(0, 1)),
        ("aud-demo-cache-prune", None, None, None, "root", "prune", "cache", "cache-trash-old", True, "remove old demo trash", {"cache": ["cache-trash-old"]}, {"bytes": 9_000_000}, _ts(0, 97)),
        ("aud-demo-lock-clear", "proj-showcase-incident-triage", None, None, "admin", "clear", "lock", "stale-lock-demo", False, "operator cleared stale lock before run", {}, {"operation": "locks clear-stale"}, _ts(0, 98)),
    ]
    for audit_id, project_id, exp_id, actor_id, actor_type, action, object_type, object_id, cascade, reason, deleted, metadata, created in rows:
        conn.execute(
            """
            INSERT INTO audit_events(audit_id, project_id, exp_id, actor_credential_id, actor_type,
              action, object_type, object_id, cascade, reason, deleted_ids_json, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (audit_id, project_id, exp_id, actor_id, actor_type, action, object_type, object_id, int(cascade), reason, canonical_json({"schema_version": 1, "ids": deleted}), canonical_json({"schema_version": 1, **metadata}), created),
        )


def _audit(
    conn: sqlite3.Connection,
    project: ProjectSeed,
    exp_id: str | None,
    actor_id: str | None,
    actor_type: str,
    action: str,
    object_type: str,
    object_id: str,
    created: str,
    *,
    metadata: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO audit_events(audit_id, project_id, exp_id, actor_credential_id, actor_type,
          action, object_type, object_id, cascade, reason, deleted_ids_json, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?)
        """,
        (
            f"aud-{project.slug}-{action}-{object_type}-{_stable_suffix(object_id, created)}",
            project.project_id,
            exp_id,
            actor_id,
            actor_type,
            action,
            object_type,
            object_id,
            canonical_json({"schema_version": 1, "ids": {}}),
            canonical_json({"schema_version": 1, **metadata}),
            created,
        ),
    )


def _write_feedback(home: Home) -> None:
    feedback = [
        ("fb-demo-dashboard", "question", "Dashboard layout review", "Can the project detail view prioritize trend and run history?"),
        ("fb-demo-runner", "bug", "Hidden log surfaced correctly", "Root dashboard should show hidden verifier logs while public observe stays redacted."),
        ("fb-demo-cleanup", "note", "Lifecycle cleanup candidate", "Archived router project can be used to demo remove dry-run and retained audit evidence."),
    ]
    for idx, (feedback_id, kind, title, body) in enumerate(feedback):
        path = home.feedback_path / feedback_id
        path.mkdir(parents=True, exist_ok=True)
        metadata = {
            "schema_version": 1,
            "feedback_id": feedback_id,
            "kind": kind,
            "title": title,
            "created_at": _ts(0, 100 + idx),
            "role": "dashboard-showcase",
        }
        (path / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (path / "body.md").write_text(body + "\n", encoding="utf-8")


def _stable_suffix(*parts: str) -> str:
    return sha256("|".join(parts).encode("utf-8")).hexdigest()[:10]


def _project_config(project: ProjectSeed) -> dict[str, Any]:
    secret_names = ("API_TOKEN", "WAREHOUSE_PASSWORD") if project.slug == "clinic-ops" else ("EVAL_TOKEN",)
    docker_runner = project.runner_type == "docker"
    adapter_runner = project.runner_type in {"harbor", "skydiscover_docker", "skydiscover_python"}
    reward_path = "run:reward.json" if project.reward_type == "file" else None
    reward_pattern = r"reward=([0-9.]+)" if project.reward_type == "stdout_regex" else None
    return {
        "schema_version": 1,
        "project": {
            "name": project.name,
            "task": project.task,
            "goal": project.goal,
            "allow_public_exp_create": project.allow_public,
        },
        "source": {"default_source_ref": f"alab/source/src-{project.slug}-main"},
        "public_source_import": {"enabled": project.allow_public, "max_files": 100000, "max_total_bytes": 1073741824, "max_file_bytes": 104857600},
        "mutable": {"include": ["**"], "exclude": [".venv/**", ".alab/**"]},
        "visibility": {"scope": project.visibility_scope, "experiment_ids": []},
        "runner": {
            "type": project.runner_type,
            "timeout_seconds": 180,
            "working_directory": ".",
            "env_mode": "sanitized",
            "command": None if adapter_runner else [sys.executable, "-c", "print('reward=0.5')"],
            "shell": None,
            "image": None,
            "dockerfile": "Dockerfile" if docker_runner else None,
            "context": "." if docker_runner else None,
            "network": "none" if docker_runner else "default",
            "build_args": {},
            "target": None,
            "platform": "linux/arm64" if docker_runner else None,
            "user": None,
            "cpus": 2 if docker_runner else None,
            "memory_mb": 2048 if docker_runner else None,
            "harbor_task_ref": "harbor:incident-triage" if project.runner_type == "harbor" else None,
            "skydiscover_task_ref": "skydiscover:circle-packing" if project.runner_type.startswith("skydiscover") else None,
            "program_path": ".",
        },
        "reward": {
            "type": project.reward_type,
            "direction": project.reward_direction,
            "primary_metric": "reward",
            "path": reward_path,
            "pattern": reward_pattern,
        },
        "artifacts": {
            "globs": ["workspace:reports/*.md", "run:metrics/*.json", "workspace:plots/*.png"],
            "per_file_limit_bytes": 10485760,
            "per_run_limit_bytes": 104857600,
        },
        "logs": {"stdout_limit_bytes": 10485760, "stderr_limit_bytes": 10485760},
        "git": {"author_name": "ALab Demo", "author_email": "demo@alab.local"},
        "env": {"DEMO_MODE": "dashboard", "PROJECT_SLUG": project.slug},
        "secret_env": {
            name: {
                "secret_value_id": f"sec-{project.slug}-{name.lower().replace('_', '-')}",
                "fingerprint": "hmac-sha256:" + sha256(f"demo-secret-value-for-{project.slug}-{name.lower()}".encode()).hexdigest(),
            }
            for name in secret_names
        },
    }


def _experiment_specs(project: ProjectSeed) -> list[dict[str, Any]]:
    if project.slug == "clinic-ops":
        return [
            {
                "slug": "greedy-baseline",
                "name": "Greedy baseline",
                "goal": "Fast deterministic route with basic inventory constraints.",
                "status": "closed",
                "tags": ["baseline", "submitted"],
                "runs": [
                    _run("passed", 0.42, artifact_text="Initial warehouse allocation report.", artifact_json={"late_orders": 8}),
                    _run("passed", 0.61, artifact_text="Improved cold-chain handling.", artifact_json={"late_orders": 4}, final=True),
                ],
            },
            {
                "slug": "tabu-search",
                "name": "Tabu search allocator",
                "goal": "Use local search to reduce split shipments and improve reward.",
                "status": "open",
                "tags": ["search", "best"],
                "runs": [
                    _run("failed", 0.33, exit_code=1, stderr="capacity assertion failed\n", warnings=["CAPACITY_GAP"], artifact_error=True, failure_reason="capacity check failed"),
                    _run("passed", 0.73, artifact_text="Tabu search found better assignment.", artifact_json={"late_orders": 2}, artifact_image=True),
                    _run("passed", 0.81, artifact_text="Best clinic ops run.", artifact_json={"late_orders": 1}, hidden_log=True, final=True),
                ],
            },
        ]
    if project.slug == "incident-triage":
        return [
            {
                "slug": "public-rules",
                "name": "Public rules classifier",
                "goal": "Tune interpretable rules from public ticket examples.",
                "status": "open",
                "tags": ["public", "rules"],
                "runs": [
                    _run("passed", 0.55, artifact_text="Rule coverage report.", artifact_json={"macro_f1": 0.55}),
                    _run("timeout", None, exit_code=None, reward_parse_status="not_attempted", stderr="verifier timed out\n", warnings=["RUNNER_TIMEOUT"], hidden_log=True, failure_reason="hidden verifier timed out", artifact_skipped=True),
                    _run("passed", 0.69, artifact_text="Recovered with bounded rules.", artifact_json={"macro_f1": 0.69}, hidden_log=True, final=True),
                ],
            },
            {
                "slug": "embedding-rerank",
                "name": "Embedding reranker",
                "goal": "Rerank incident categories using hidden verifier feedback.",
                "status": "closed",
                "tags": ["rerank", "submitted"],
                "runs": [
                    _run("error", None, exit_code=0, reward_parse_status="missing", stderr="reward line missing\n", warnings=["REWARD_PARSE_ERROR"], failure_reason="reward parse status is missing"),
                    _run("passed", 0.74, artifact_text="Reranker summary.", artifact_json={"macro_f1": 0.74}, hidden_log=True, final=True),
                ],
            },
        ]
    if project.slug == "circle-pack":
        return [
            {
                "slug": "annealing-density",
                "name": "Annealing density search",
                "goal": "Minimize overlap penalty while keeping high packing density.",
                "status": "open",
                "tags": ["skydiscover", "annealing"],
                "runs": [
                    _run("passed", 0.29, artifact_text="Initial overlap penalty.", artifact_json={"penalty": 0.29}, hidden_log=True),
                    _run("passed", 0.21, artifact_text="Lower penalty after cooling schedule.", artifact_json={"penalty": 0.21}, artifact_image=True, hidden_log=True),
                    _run("interrupted", 0.24, exit_code=130, warnings=["INTERRUPTED"], stderr="operator interrupted long evaluator\n", failure_reason="interrupted by operator"),
                ],
            }
        ]
    return [
        {
            "slug": "retired-baseline",
            "name": "Retired baseline",
            "goal": "Preserve archived lifecycle traces.",
            "status": "archived",
            "pre_archive": "closed",
            "worktree_state": "removed",
            "tags": ["archived", "baseline"],
            "runs": [
                _run("passed", 1.0, archive_status="archived", archived_at=_ts(3, 70), artifact_text="Archived baseline report.", final=True),
            ],
        }
    ]


def _run(status: str, reward: float | None, **kwargs: Any) -> dict[str, Any]:
    return {"status": status, "reward": reward, "exit_code": 0 if status == "passed" else kwargs.pop("exit_code", 1), **kwargs}


def _ts(project_index: int, minute: int) -> str:
    day = 20 + project_index
    hour = 9 + minute // 60
    mins = minute % 60
    return f"2026-05-{day:02d}T{hour:02d}:{mins:02d}:00Z"


if __name__ == "__main__":
    raise SystemExit(main())
