import errno
import hashlib
import hmac
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import alab.cli as cli
import alab.maintenance as maintenance_services
import alab.observe as observe_services
import alab.services as services
import alab.sources as source_services
from alab.cli import run
from alab.home import Home
from alab.ids import new_id, slugify
from alab.rendering import ResultBlock, multiline_text, render_text
from alab.source_import import canonical_tree_hash, copy_filtered_source


def test_text_renderer_object_block() -> None:
    text = render_text([ResultBlock("example", [("name", "ALab"), ("ok", True)])])

    assert text == "object: example\nname: ALab\nok: true\n"

    multiline = render_text(
        [
            ResultBlock(
                "example",
                [
                    ("body", multiline_text("line one\nline two")),
                    ("empty body", multiline_text("")),
                    ("optional body", multiline_text(None)),
                    ("literal none body", multiline_text("none")),
                    ("tag", ["alpha", "beta"]),
                ],
            )
        ]
    )

    assert multiline == (
        "object: example\n"
        "body:\n"
        "  line one\n"
        "  line two\n"
        "empty body:\n"
        "  [empty]\n"
        "optional body: none\n"
        "literal none body:\n"
        "  none\n"
        "tag: alpha\n"
        "tag: beta\n"
    )


def test_debug_stack_trace_only_for_internal_errors(monkeypatch, capsys) -> None:
    def broken_build_request(_parsed):
        raise RuntimeError("debug boom")

    monkeypatch.setattr(cli, "build_request", broken_build_request)

    assert run(["config", "show"]) == 5
    normal_err = capsys.readouterr().err
    assert _field_labels(normal_err) == _error_field_labels()
    assert "error code: STORAGE_ERROR" in normal_err
    assert "RuntimeError" not in normal_err
    assert "Traceback" not in normal_err

    monkeypatch.setenv("ALAB_DEBUG", "1")
    assert run(["config", "show"]) == 5
    debug_err = capsys.readouterr().err
    assert "error code: STORAGE_ERROR" in debug_err
    assert "RuntimeError: debug boom" in debug_err
    assert "Traceback" in debug_err


def test_debug_does_not_trace_saved_result_failures(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("ok")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Saved Failure Project"
task = "Keep saved failures stable"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_id = _field(capsys.readouterr().out, "project id")
    worktree = tmp_path / "exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "failed-run", "--path", str(worktree)]) == 0
    capsys.readouterr()

    monkeypatch.chdir(worktree)
    (worktree / "main.py").write_text("import sys\nsys.exit(7)\n", encoding="utf-8")
    monkeypatch.setenv("ALAB_DEBUG", "1")
    assert run(["--home", str(home), "run", "--message", "saved failure"]) == 1
    captured = capsys.readouterr()

    assert captured.err == ""
    assert "Traceback" not in captured.out
    assert _field_labels(captured.out) == _run_field_labels(failure=True)
    assert "run status: failed" in captured.out
    assert re.search(r"run status: failed\nexit code: 7", captured.out)
    assert re.search(r"error code: RUNNER_FAILED\nexit code: 1\nreason: runner exited with code 7\nnext:", captured.out)
    failed_run_id = _field(captured.out, "run id")
    with sqlite3.connect(home / "alab.db") as conn:
        record_json = conn.execute("SELECT record_json FROM runs WHERE run_id = ?", (failed_run_id,)).fetchone()[0]
    assert json.loads(record_json)["failure"] == "runner exited with code 7"

    assert run(["--home", str(home), "runs", "list", "--failure-reason-query", "code 7"]) == 0
    failure_filtered = capsys.readouterr().out
    assert f"run id: {failed_run_id}" in failure_filtered
    assert "run status: failed" in failure_filtered
    assert run(["--home", str(home), "runs", "list", "--failure-reason-query", "missing failure"]) == 0
    assert _field_labels(capsys.readouterr().out) == []


def _field(output: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}: (.+)$", output, re.MULTILINE)
    assert match, output
    return match.group(1)


def _commands(output: str) -> set[str]:
    return set(re.findall(r"^command: (.+)$", output, re.MULTILINE))


def _field_labels(output: str) -> list[str]:
    labels: list[str] = []
    for line in output.splitlines():
        if not line or line.startswith("  "):
            continue
        label, _, _value = line.partition(":")
        labels.append(label)
    return labels


def _block_labels(output: str) -> list[list[str]]:
    return [_field_labels(block) for block in output.strip().split("\n\n") if block]


def _error_field_labels() -> list[str]:
    return ["object", "message", "error code", "exit code", "reason", "next"]


def _assert_confirm_guard(base_args: list[str], confirm_id: str, message: str, capsys) -> None:
    variants = [
        ([*base_args, "--confirm", confirm_id], message),
        ([*base_args, "--force"], message),
        ([*base_args, "--force", "--confirm", f"{confirm_id}-wrong"], message),
        ([*base_args, "--force", "--force", "--confirm", confirm_id], "--force may be provided once"),
        ([*base_args, "--force", "--confirm", confirm_id, "--confirm", confirm_id], "--confirm may be provided once"),
    ]
    for args, expected_message in variants:
        assert run(args) == 2
        err = capsys.readouterr().err
        assert _field_labels(err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in err
        assert expected_message in err


def _assert_duplicate_option_error(args: list[str], option: str, capsys) -> None:
    assert run(args) == 2
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in err
    assert f"{option} may be provided once" in err


def _assert_not_archived_remove_blocked(args: list[str], home: Path, object_type: str, object_id: str, capsys) -> None:
    assert run(args) == 4
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: RESOURCE_BUSY" in err
    assert "target_not_archived" in err
    assert _audit_count(home, "remove", object_type, object_id) == 0


def _assert_remove_resource_busy(
    args: list[str],
    home: Path,
    object_type: str,
    object_id: str,
    blocker: str,
    capsys,
) -> None:
    assert run(args) == 4
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: RESOURCE_BUSY" in err
    assert blocker in err
    assert _audit_count(home, "remove", object_type, object_id) == 0


def _assert_remove_dry_run_preserved(home: Path, object_type: str, object_id: str, table: str, id_column: str) -> None:
    assert _audit_count(home, "remove", object_type, object_id) == 0
    assert _row_count(home, table, id_column, object_id) == 1


def _audit_count(home: Path, action: str, object_type: str, object_id: str) -> int:
    with sqlite3.connect(home / "alab.db") as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action = ? AND object_type = ? AND object_id = ?",
            (action, object_type, object_id),
        ).fetchone()[0]


def _audit_type_count(home: Path, action: str, object_type: str) -> int:
    with sqlite3.connect(home / "alab.db") as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action = ? AND object_type = ?",
            (action, object_type),
        ).fetchone()[0]


def _row_count(home: Path, table: str, id_column: str, object_id: str) -> int:
    with sqlite3.connect(home / "alab.db") as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {id_column} = ?", (object_id,)).fetchone()[0]


def _table_count(home: Path, table: str) -> int:
    with sqlite3.connect(home / "alab.db") as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _assert_project_tmp_clean(home: Path, project_id: str) -> None:
    project_tmp = home / "tmp" / project_id
    if not project_tmp.exists():
        return
    assert sorted(path.relative_to(project_tmp).as_posix() for path in project_tmp.rglob("*")) == []


def _assert_worktree_clean(worktree: Path) -> None:
    visible_changes = [line for line in _git(["status", "--porcelain", "--untracked-files=all"], worktree).splitlines() if ".alab/" not in line]
    assert visible_changes == []


def _insert_active_lock(home: Path, lock_name: str, project_id: str, exp_id: str | None = None) -> None:
    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute(
            """
            INSERT INTO locks(lock_name, owner_operation_id, owner_host, owner_pid, project_id, exp_id, acquired_at, heartbeat_at, expires_at)
            VALUES (?, ?, 'test-host', 123, ?, ?, '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z', '2999-01-01T00:00:00Z')
            """,
            (lock_name, f"op-{lock_name}", project_id, exp_id),
        )


def _delete_lock(home: Path, lock_name: str) -> None:
    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute("DELETE FROM locks WHERE lock_name = ?", (lock_name,))


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
    if failure:
        labels.extend(["error code", "exit code", "reason", "next"])
    else:
        labels.append("next")
    return labels


def _project_config_set_field_labels(*, warning_count: int = 0, failure: bool = False) -> list[str]:
    labels = [
        "object",
        "project id",
        "previous active config version",
        "latest attempted config version",
        "runtime affecting",
        "validation status",
        "project status",
    ]
    labels.extend(["warning code"] * warning_count)
    if failure:
        labels.extend(["error code", "exit code", "reason", "next"])
    else:
        labels.append("next")
    return labels


def _project_validation_field_labels(*, warning_count: int = 0, failure: bool = False) -> list[str]:
    labels = [
        "object",
        "project id",
        "validation id",
        "config version",
        "validation status",
        "exit code",
        "reward",
        "reward parse status",
        "project status",
    ]
    labels.extend(["warning code"] * warning_count)
    if failure:
        labels.extend(["error code", "exit code", "reason", "next"])
    else:
        labels.append("next")
    return labels


def _project_list_field_labels() -> list[str]:
    return ["object", "project id", "project name", "project status", "created at", "updated at", "archived at"]


def _exp_create_field_labels(*, warning_count: int = 0) -> list[str]:
    labels = [
        "object",
        "project id",
        "exp id",
        "experiment name",
        "source id",
        "branch",
        "worktree path",
        "token path",
        "config version",
    ]
    labels.extend(["warning"] * warning_count)
    labels.append("next")
    return labels


def _run_field_labels(*, warning_count: int = 0, failure: bool = False) -> list[str]:
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
    labels.extend(["warning code"] * warning_count)
    if failure:
        labels.extend(["error code", "exit code", "reason", "next"])
    else:
        labels.append("next")
    return labels


def _submission_field_labels(*, ref_count: int = 1) -> list[str]:
    labels = [
        "object",
        "exp id",
        "submit accepted",
        "final run id",
        "final commit",
        "experiment status",
        "summary stored",
        "feedback stored",
    ]
    labels.extend(["ref"] * ref_count)
    return labels


def _submission_failure_field_labels(*, ref_count: int = 1) -> list[str]:
    labels = _submission_field_labels(ref_count=ref_count)
    labels.extend(["error code", "exit code", "reason", "next"])
    return labels


def _experiment_field_labels() -> list[str]:
    return [
        "object",
        "project id",
        "exp id",
        "experiment name",
        "experiment status",
        "source id",
        "source ref",
        "tag",
        "latest run id",
        "latest commit",
        "final run id",
        "final commit",
        "best run id",
        "reward",
        "reward parse status",
        "created at",
        "updated at",
        "closed at",
        "archived at",
    ]


def _log_field_labels() -> list[str]:
    return [
        "object",
        "log id",
        "exp id",
        "run id",
        "validation id",
        "stream",
        "size bytes",
        "stored bytes",
        "truncated",
        "hidden",
        "archive status",
        "preview",
        "out",
        "audit id",
    ]


def _log_show_field_labels() -> list[str]:
    labels = _log_field_labels()
    return [*labels[: labels.index("out")], "content", *labels[labels.index("out") :]]


def _artifact_field_labels() -> list[str]:
    return [
        "object",
        "artifact id",
        "exp id",
        "run id",
        "validation id",
        "root",
        "path",
        "status",
        "archive status",
        "size bytes",
        "content hash",
        "created at",
        "out",
    ]


def _archive_field_labels(object_type: str) -> list[str]:
    return ["object", f"{object_type} id", "previous archive status", "archive status", "archived at", "audit id"]


def _unarchive_field_labels(object_type: str) -> list[str]:
    return ["object", f"{object_type} id", "previous archive status", "archive status", "unarchived at", "audit id"]


def _observe_remove_field_labels(
    object_type: str,
    *,
    dry_run: bool,
    has_blocker: bool = False,
    blocker_count: int = 1,
    filesystem_path_count: int = 0,
) -> list[str]:
    labels = ["object", f"{object_type} id", "dry run", "removed", "cascade", "audit id"]
    if has_blocker:
        labels.extend(["blocker"] * blocker_count)
    if object_type == "run":
        labels.extend(
            [
                "deleted artifacts",
                "deleted logs",
                "active dependent artifacts",
                "active dependent logs",
                "latest run id before",
                "latest run id after",
                "final run removed",
            ]
        )
    labels.append("deleted filesystem paths")
    if dry_run and filesystem_path_count:
        labels.extend(["filesystem path"] * filesystem_path_count)
        labels.extend(["planned trash move"] * filesystem_path_count)
    if not dry_run:
        labels.append("trash cleanup pending")
    return labels


def _validation_archive_field_labels(*, unarchive: bool = False) -> list[str]:
    time_label = "unarchived at" if unarchive else "archived at"
    return ["object", "project id", "validation id", "previous archive status", "archive status", time_label, "audit id"]


def _validation_remove_field_labels(*, dry_run: bool, has_blocker: bool = False, blocker_count: int = 1, filesystem_path_count: int = 0) -> list[str]:
    labels = ["object", "project id", "validation id", "dry run", "removed", "cascade", "audit id"]
    if has_blocker:
        labels.extend(["blocker"] * blocker_count)
    labels.extend(
        [
            "deleted artifacts",
            "deleted logs",
            "active dependent artifacts",
            "active dependent logs",
            "deleted filesystem paths",
        ]
    )
    if dry_run and filesystem_path_count:
        labels.extend(["filesystem path"] * filesystem_path_count)
        labels.extend(["planned trash move"] * filesystem_path_count)
    if not dry_run:
        labels.append("trash cleanup pending")
    return labels


def _annotation_edit_field_labels() -> list[str]:
    return ["object", "annotation id", "revision", "updated at"]


def _annotation_add_field_labels() -> list[str]:
    return ["object", "annotation id", "target type", "target id", "resolved commit", "revision", "visibility", "created at"]


def _annotation_field_labels(*, history_revision_count: int = 0) -> list[str]:
    labels = [
        "object",
        "annotation id",
        "target type",
        "target id",
        "resolved commit",
        "status",
        "current revision",
        "visibility",
        "author",
        "body",
        "created at",
        "updated at",
    ]
    labels.extend(["revision"] * history_revision_count)
    return labels


def _annotation_status_field_labels(*, unarchive: bool = False) -> list[str]:
    time_label = "unarchived at" if unarchive else "archived at"
    return ["object", "annotation id", "previous status", "annotation status", time_label]


def _annotation_remove_field_labels(*, dry_run: bool, has_blocker: bool = False) -> list[str]:
    labels = ["object", "annotation id", "dry run", "removed", "audit id"]
    if has_blocker:
        labels.append("blocker")
    labels.extend(["deleted revisions", "deleted filesystem paths"])
    if not dry_run:
        labels.append("trash cleanup pending")
    return labels


def _project_status_field_labels(*, unarchive: bool = False) -> list[str]:
    time_label = "unarchived at" if unarchive else "archived at"
    return ["object", "project id", "previous status", "project status", time_label]


def _project_remove_field_labels(*, dry_run: bool, has_blocker: bool = False, filesystem_path_count: int = 0) -> list[str]:
    labels = ["object", "project id", "dry run", "removed", "cascade", "audit id"]
    if has_blocker:
        labels.append("blocker")
    labels.extend(
        [
            "deleted experiments",
            "deleted runs",
            "deleted artifacts",
            "deleted logs",
            "deleted sources",
            "deleted filesystem paths",
        ]
    )
    if dry_run and filesystem_path_count:
        labels.extend(["filesystem path"] * filesystem_path_count)
        labels.extend(["planned trash move"] * filesystem_path_count)
    if not dry_run:
        labels.append("trash cleanup pending")
    return labels


def _experiment_status_field_labels(*, unarchive: bool = False) -> list[str]:
    time_label = "unarchived at" if unarchive else "archived at"
    return ["object", "exp id", "previous status", "experiment status", time_label]


def _experiment_remove_field_labels(*, dry_run: bool, has_blocker: bool = False, filesystem_path_count: int = 0) -> list[str]:
    labels = ["object", "exp id", "dry run", "removed", "cascade", "audit id"]
    if has_blocker:
        labels.append("blocker")
    labels.extend(
        [
            "deleted runs",
            "deleted artifacts",
            "deleted logs",
            "deleted annotations",
            "deleted tags",
            "deleted submissions",
            "branch ref",
        ]
    )
    if dry_run:
        labels.append("branch ref exists")
    else:
        labels.extend(["deleted branch ref", "branch ref existed"])
    labels.append("deleted filesystem paths")
    if dry_run and filesystem_path_count:
        labels.extend(["filesystem path"] * filesystem_path_count)
        labels.extend(["planned trash move"] * filesystem_path_count)
    if not dry_run:
        labels.append("trash cleanup pending")
    return labels


def _source_list_field_labels() -> list[str]:
    return ["object", "source id", "source ref", "source name", "status", "tree hash", "created at", "archived at"]


def _source_import_field_labels(*, warning_count: int = 0) -> list[str]:
    labels = ["object", "project id", "source id", "source ref", "source name", "tree hash", "deduped"]
    labels.extend(["warning"] * warning_count)
    return labels


def _source_status_field_labels(*, unarchive: bool = False) -> list[str]:
    time_label = "unarchived at" if unarchive else "archived at"
    return ["object", "source id", "previous status", "source status", time_label]


def _source_remove_field_labels(*, dry_run: bool, has_blocker: bool = False) -> list[str]:
    labels = ["object", "source id", "dry run", "removed", "cascade", "audit id"]
    if has_blocker:
        labels.append("blocker")
    return labels


def _admin_key_list_field_labels() -> list[str]:
    return ["object", "project id", "key id", "role", "status", "created at", "revoked at"]


def _root_key_list_field_labels() -> list[str]:
    return ["object", "key id", "credential type", "status", "created at", "revoked at"]


def _key_revoke_field_labels() -> list[str]:
    return ["object", "key id", "status", "revoked at"]


def _backup_prune_field_labels(*, pruned_count: int) -> list[str]:
    labels = ["object", "backup pruned count"]
    labels.extend(["backup path"] * pruned_count)
    labels.append("audit id")
    return labels


def _cache_prune_field_labels(*, cache_kind_count: int) -> list[str]:
    labels = ["object", "cache pruned count"]
    labels.extend(["cache kind"] * cache_kind_count)
    labels.append("audit id")
    return labels


def _catalog_change_field_labels() -> list[str]:
    return ["object", "catalog", "origin url", "requested ref", "pinned commit", "local path", "retrieved at", "status", "audit id"]


def _catalog_show_field_labels() -> list[str]:
    return ["object", "catalog", "origin url", "pinned commit", "local path", "retrieved at", "status"]


def _catalog_remove_field_labels() -> list[str]:
    return ["object", "catalog", "removed", "audit id"]


def _context_show_field_labels() -> list[str]:
    return [
        "object",
        "path",
        "resolved path",
        "home id",
        "context type",
        "project id",
        "exp id",
        "token id",
        "registered",
        "path status",
        "next",
    ]


def _context_repair_field_labels() -> list[str]:
    return ["object", "path", "resolved path", "context type", "project id", "exp id", "repair mode", "status"]


def _credential_list_field_labels() -> list[str]:
    return ["object", "project id", "exp id", "token id", "token mode", "status", "path status", "created at", "revoked at"]


def _credential_regenerate_field_labels() -> list[str]:
    return ["object", "project id", "exp id", "revoked token id", "new token id", "token mode", "token path", "created at"]


def _inspection_checkout_create_field_labels() -> list[str]:
    return ["object", "exp id", "inspection path", "inspection commit", "token path", "token id", "next"]


def _inspection_checkout_remove_field_labels(*, dry_run: bool) -> list[str]:
    path_field = "path exists" if dry_run else "path existed"
    trailing_field = "planned trash move" if dry_run else "trash path"
    labels = ["object", "exp id", "inspection path", "token id", "dry run", "removed", path_field, "token revocation target", "token revoked", trailing_field]
    if not dry_run:
        labels.append("trash cleanup pending")
    labels.append("audit id")
    return labels


def _worktree_remove_field_labels(*, dry_run: bool) -> list[str]:
    path_field = "path exists" if dry_run else "path existed"
    trailing_field = "planned trash move" if dry_run else "trash path"
    labels = [
        "object",
        "exp id",
        "old worktree path",
        "worktree state",
        "dry run",
        "removed",
        path_field,
        "dirty state",
        "token revocation target",
        "token revoked",
        trailing_field,
    ]
    if not dry_run:
        labels.append("trash cleanup pending")
    labels.append("audit id")
    return labels


def _worktree_restore_field_labels() -> list[str]:
    return ["object", "exp id", "branch", "worktree path", "worktree state", "token path", "revoked token id", "new token id"]


def _git(args: list[str], cwd) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)
    return completed.stdout.decode("utf-8", errors="replace").strip()


def _source_tree_files(home, project_id: str, source_ref: str) -> set[str]:
    repo = home / "projects" / project_id / "repo.git"
    output = _git(["--git-dir", str(repo), "ls-tree", "-r", "--name-only", f"refs/heads/{source_ref}"], home)
    return set(output.splitlines()) if output else set()


def _source_refs(home, project_id: str) -> set[str]:
    repo = home / "projects" / project_id / "repo.git"
    output = _git(["--git-dir", str(repo), "for-each-ref", "--format=%(refname)", "refs/heads/alab/source"], home)
    return set(output.splitlines()) if output else set()


def test_canonical_tree_hash_manifest_matches_v1_spec(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    bin_dir = source / "bin"
    bin_dir.mkdir()
    alpha = source / "a.txt"
    runner = bin_dir / "run.sh"
    alpha.write_text("alpha\n", encoding="utf-8")
    runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    os.chmod(runner, 0o755)
    try:
        (source / "link.txt").symlink_to("a.txt")
        (source / "dir-link").symlink_to("bin", target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    expected_manifest = "\n".join(
        [
            f"F 100644 a.txt\0{hashlib.sha256(alpha.read_bytes()).hexdigest()}",
            f"F 100755 bin/run.sh\0{hashlib.sha256(runner.read_bytes()).hexdigest()}",
            "L dir-link\0bin",
            "L link.txt\0a.txt",
        ]
    ).encode("utf-8")

    assert canonical_tree_hash(source) == "sha256:" + hashlib.sha256(expected_manifest).hexdigest()
    copied = tmp_path / "copied"
    result = copy_filtered_source(source, copied)
    assert result.imported_files == 4
    assert (copied / "dir-link").is_symlink()
    assert os.readlink(copied / "dir-link") == "bin"
    assert canonical_tree_hash(copied) == canonical_tree_hash(source)


def test_auth_init_and_config_show(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    extra_home = tmp_path / "extra-home"
    unsupported_home = tmp_path / "unsupported-home"

    assert run(["--home", str(extra_home), "auth", "init", "extra"]) == 2
    extra_auth_init_err = capsys.readouterr().err
    assert _field_labels(extra_auth_init_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_auth_init_err
    assert "auth init accepts no positional arguments" in extra_auth_init_err
    assert not extra_home.exists()
    assert run(["--home", str(unsupported_home), "auth", "init", "--reason", "ignored"]) == 2
    unsupported_auth_init_err = capsys.readouterr().err
    assert _field_labels(unsupported_auth_init_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_auth_init_err
    assert "unsupported option --reason" in unsupported_auth_init_err
    assert not unsupported_home.exists()

    assert run(["--home", str(home), "auth", "init"]) == 0
    out = capsys.readouterr().out

    assert "object: auth" in out
    assert _field_labels(out) == ["object", "home", "home id", "root key", "created"]
    root_key = _field(out, "root key")
    assert root_key.startswith("alab_root_v1_")
    old_root_id = root_key.removeprefix("alab_root_v1_").rpartition("_")[0]

    assert run(["--home", str(home), "--key", root_key, "auth", "root", "regenerate", "extra"]) == 2
    extra_root_regenerate_err = capsys.readouterr().err
    assert _field_labels(extra_root_regenerate_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_root_regenerate_err
    assert "auth root regenerate accepts no positional arguments" in extra_root_regenerate_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM credentials WHERE credential_id = ?", (old_root_id,)).fetchone()[0] == "active"
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE credential_type = 'root'").fetchone()[0] == 1
    assert run(["--home", str(home), "--key", root_key, "auth", "root", "regenerate", "--reason", "ignored"]) == 2
    unsupported_root_regenerate_err = capsys.readouterr().err
    assert _field_labels(unsupported_root_regenerate_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_root_regenerate_err
    assert "unsupported option --reason" in unsupported_root_regenerate_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM credentials WHERE credential_id = ?", (old_root_id,)).fetchone()[0] == "active"
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE credential_type = 'root'").fetchone()[0] == 1

    assert run(["--home", str(home), "--key", root_key, "auth", "root", "regenerate"]) == 0
    regenerate_out = capsys.readouterr().out
    assert _field_labels(regenerate_out) == [
        "object",
        "home",
        "home id",
        "root key",
        "revoked key id",
        "created key id",
    ]
    old_root_key = root_key
    assert f"revoked key id: {old_root_id}" in regenerate_out
    root_key = _field(regenerate_out, "root key")
    root_credential_id = root_key.removeprefix("alab_root_v1_").rpartition("_")[0]
    with sqlite3.connect(home / "alab.db") as conn:
        root_regenerate_audit = conn.execute(
            """
            SELECT actor_credential_id, actor_type, action, object_type, object_id,
              project_id, exp_id, cascade, reason, metadata_json
            FROM audit_events
            WHERE action = 'regenerate' AND object_type = 'credential' AND object_id = ?
            """,
            (root_credential_id,),
        ).fetchone()
    assert root_regenerate_audit[:9] == (old_root_id, "root", "regenerate", "credential", root_credential_id, None, None, 0, None)
    root_regenerate_metadata_text = root_regenerate_audit[9]
    root_regenerate_metadata = json.loads(root_regenerate_metadata_text)
    assert root_regenerate_metadata == {
        "created_credential_id": root_credential_id,
        "credential_type": "root",
        "revoked_at": root_regenerate_metadata["revoked_at"],
        "revoked_credential_id": old_root_id,
        "schema_version": 1,
    }
    assert old_root_key not in root_regenerate_metadata_text
    assert root_key not in root_regenerate_metadata_text
    assert run(["--home", str(home), "--key", old_root_key, "cache", "prune", "--all"]) == 3
    old_root_err = capsys.readouterr().err
    assert _field_labels(old_root_err) == _error_field_labels()
    assert "error code: AUTH_DENIED" in old_root_err
    assert run(["--home", str(home), "--key", root_key, "key", "list", "--root"]) == 0
    root_key_list_out = capsys.readouterr().out
    assert all(labels == _root_key_list_field_labels() for labels in _block_labels(root_key_list_out))
    assert run(["--home", str(home), "--key", root_key, "key", "list", "extra", "--root"]) == 2
    extra_root_key_list_err = capsys.readouterr().err
    assert _field_labels(extra_root_key_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_root_key_list_err
    assert "key list accepts no positional arguments" in extra_root_key_list_err
    assert run(["--home", str(home), "--key", root_key, "key", "list", "--root", "extra"]) == 2
    trailing_root_key_list_err = capsys.readouterr().err
    assert _field_labels(trailing_root_key_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in trailing_root_key_list_err
    assert "key list accepts no positional arguments" in trailing_root_key_list_err
    assert run(["--home", str(home), "--key", root_key, "key", "list", "--root", "--root"]) == 2
    duplicate_root_key_list_err = capsys.readouterr().err
    assert _field_labels(duplicate_root_key_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_root_key_list_err
    assert "--root may be provided once" in duplicate_root_key_list_err
    assert run(["--home", str(home), "--key", root_key, "key", "list", "--root", "--reason", "ignored"]) == 2
    unsupported_root_key_list_err = capsys.readouterr().err
    assert _field_labels(unsupported_root_key_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_root_key_list_err
    assert "unsupported option --reason" in unsupported_root_key_list_err

    old_backup = home / "backups" / "old.db"
    new_backup = home / "backups" / "new.db"
    old_backup.write_text("old", encoding="utf-8")
    new_backup.write_text("new", encoding="utf-8")
    os.utime(old_backup, (1, 1))
    os.utime(new_backup, (2, 2))
    assert run(["--home", str(home), "--key", root_key, "backup", "prune"]) == 2
    backup_selector_err = capsys.readouterr().err
    assert _field_labels(backup_selector_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in backup_selector_err
    assert "backup prune requires exactly one of --keep or --older-than" in backup_selector_err
    assert run(["--home", str(home), "--key", root_key, "backup", "prune", "--keep", "1", "--older-than", "1"]) == 2
    backup_conflict_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in backup_conflict_err
    assert "backup prune requires exactly one of --keep or --older-than" in backup_conflict_err
    assert run(["--home", str(home), "--key", root_key, "backup", "prune", "--keep", "1", "--keep", "2"]) == 2
    backup_duplicate_keep_err = capsys.readouterr().err
    assert _field_labels(backup_duplicate_keep_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in backup_duplicate_keep_err
    assert "--keep may be provided once" in backup_duplicate_keep_err
    assert old_backup.exists()
    assert new_backup.exists()
    assert run(["--home", str(home), "--key", root_key, "backup", "prune", "--older-than", "1", "--older-than", "2"]) == 2
    backup_duplicate_older_err = capsys.readouterr().err
    assert _field_labels(backup_duplicate_older_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in backup_duplicate_older_err
    assert "--older-than may be provided once" in backup_duplicate_older_err
    assert old_backup.exists()
    assert new_backup.exists()
    assert run(["--home", str(home), "--key", root_key, "backup", "prune", "--keep", "not-an-int"]) == 2
    backup_keep_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in backup_keep_err
    assert "--keep must be an integer" in backup_keep_err
    assert run(["--home", str(home), "--key", root_key, "backup", "prune", "--older-than", "-1"]) == 2
    backup_older_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in backup_older_err
    assert "--older-than must be zero or greater" in backup_older_err
    backup_audits_before_extra = _audit_type_count(home, "prune", "backup")
    assert run(["--home", str(home), "--key", root_key, "backup", "prune", "--keep", "1", "--reason", "ignored"]) == 2
    unsupported_backup_prune_err = capsys.readouterr().err
    assert _field_labels(unsupported_backup_prune_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_backup_prune_err
    assert "unsupported option --reason" in unsupported_backup_prune_err
    assert old_backup.exists()
    assert new_backup.exists()
    assert _audit_type_count(home, "prune", "backup") == backup_audits_before_extra
    assert run(["--home", str(home), "--key", root_key, "backup", "prune", "extra", "--keep", "1"]) == 2
    extra_backup_prune_err = capsys.readouterr().err
    assert _field_labels(extra_backup_prune_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_backup_prune_err
    assert "backup prune accepts no positional arguments" in extra_backup_prune_err
    assert old_backup.exists()
    assert new_backup.exists()
    assert _audit_type_count(home, "prune", "backup") == backup_audits_before_extra
    assert run(["--home", str(home), "--key", root_key, "backup", "prune", "--keep", "1"]) == 0
    backup_out = capsys.readouterr().out
    assert _field_labels(backup_out) == _backup_prune_field_labels(pruned_count=1)
    assert "backup pruned count: 1" in backup_out
    backup_audit_id = _field(backup_out, "audit id")
    assert not old_backup.exists()
    assert new_backup.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        backup_audit_row = conn.execute(
            """
            SELECT actor_credential_id, action, object_type, object_id, cascade, metadata_json
            FROM audit_events
            WHERE audit_id = ?
            """,
            (backup_audit_id,),
        ).fetchone()
    assert backup_audit_row[:5] == (root_credential_id, "prune", "backup", "backups", 0)
    assert json.loads(backup_audit_row[5]) == {"schema_version": 1, "pruned_count": 1}
    os.utime(new_backup, None)
    stale_backup = home / "backups" / "stale.db"
    fresh_backup = home / "backups" / "fresh.db"
    stale_backup.write_text("stale", encoding="utf-8")
    fresh_backup.write_text("fresh", encoding="utf-8")
    os.utime(stale_backup, (1, 1))
    os.utime(fresh_backup, None)
    assert run(["--home", str(home), "--key", root_key, "backup", "prune", "--older-than", "1"]) == 0
    older_backup_out = capsys.readouterr().out
    assert _field_labels(older_backup_out) == _backup_prune_field_labels(pruned_count=1)
    assert "backup pruned count: 1" in older_backup_out
    older_backup_audit_id = _field(older_backup_out, "audit id")
    assert f"backup path: {stale_backup}" in older_backup_out
    assert not stale_backup.exists()
    assert new_backup.exists()
    assert fresh_backup.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        older_backup_audit_row = conn.execute(
            "SELECT actor_credential_id, action, object_type, object_id, cascade, metadata_json FROM audit_events WHERE audit_id = ?",
            (older_backup_audit_id,),
        ).fetchone()
    assert older_backup_audit_row[:5] == (root_credential_id, "prune", "backup", "backups", 0)
    assert json.loads(older_backup_audit_row[5]) == {"schema_version": 1, "pruned_count": 1}

    assert run(["--home", str(home), "--key", root_key, "cache", "prune", "--all"]) == 0
    cache_prune_out = capsys.readouterr().out
    assert _field_labels(cache_prune_out) == _cache_prune_field_labels(cache_kind_count=3)
    assert "cache pruned count: 0" in cache_prune_out
    cache_audit_id = _field(cache_prune_out, "audit id")
    with sqlite3.connect(home / "alab.db") as conn:
        cache_audit_row = conn.execute(
            "SELECT actor_credential_id, action, object_type, object_id, cascade, metadata_json FROM audit_events WHERE audit_id = ?",
            (cache_audit_id,),
        ).fetchone()
    assert cache_audit_row[:5] == (root_credential_id, "prune", "cache", "cache", 0)
    assert json.loads(cache_audit_row[5]) == {
        "schema_version": 1,
        "cache_kinds": ["docker_image", "skydiscover_python_env", "trash"],
        "pruned_count": 0,
        "warning_count": 0,
    }

    assert run(["config", "show", "extra", "--home", str(home)]) == 2
    extra_config_show_err = capsys.readouterr().err
    assert _field_labels(extra_config_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_config_show_err
    assert "config show accepts no positional arguments" in extra_config_show_err
    assert run(["config", "show", "--home", str(home), "--reason", "ignored"]) == 2
    unsupported_config_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_config_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_config_show_err
    assert "unsupported option --reason" in unsupported_config_show_err

    assert run(["config", "show", "--home", str(home)]) == 0
    out = capsys.readouterr().out

    assert "object: config" in out
    assert _field_labels(out) == [
        "object",
        "home",
        "schema version",
        "output format",
        "preview bytes",
        "busy timeout ms",
        "lock acquire timeout ms",
        "lock heartbeat interval ms",
        "lock stale after ms",
        "config valid",
    ]
    assert "output format: text" in out

    assert run(["--home", str(home), "config", "set", "output.preview_bytes", "1234"]) == 0
    set_out = capsys.readouterr().out
    assert _field_labels(set_out) == ["object", "field", "previous value", "value", "config valid"]
    assert "field: output.preview_bytes" in set_out
    assert "value: 1234" in set_out
    assert run(["--home", str(home), "config", "show"]) == 0
    assert "preview bytes: 1234" in capsys.readouterr().out
    assert run(["--home", str(home), "config", "set", "output.preview_bytes", "5678", "extra"]) == 2
    extra_config_set_err = capsys.readouterr().err
    assert _field_labels(extra_config_set_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_config_set_err
    assert "config set requires field and TOML literal" in extra_config_set_err
    assert run(["--home", str(home), "config", "show"]) == 0
    assert "preview bytes: 1234" in capsys.readouterr().out
    assert run(["--home", str(home), "config", "set", "output.preview_bytes", "5678", "--reason", "ignored"]) == 2
    unsupported_config_set_err = capsys.readouterr().err
    assert _field_labels(unsupported_config_set_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_config_set_err
    assert "unsupported option --reason" in unsupported_config_set_err
    assert run(["--home", str(home), "config", "show"]) == 0
    assert "preview bytes: 1234" in capsys.readouterr().out

    assert run(["--home", str(home), "config", "set", "output.format", '"rich"']) == 2
    format_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in format_err
    assert 'output.format may only be "text"' in format_err
    assert run(["--home", str(home), "config", "set", "unknown.field", "1"]) == 2
    field_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in field_err
    assert "unsupported config field" in field_err
    assert run(["--home", str(home), "config", "set", "output.preview_bytes", "true"]) == 2
    value_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in value_err
    assert "output.preview_bytes must be a positive integer" in value_err

    assert run(["--home", str(home), "config", "reset"]) == 2
    reset_missing_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in reset_missing_err
    assert "config reset requires exactly one field or --all" in reset_missing_err
    assert run(["--home", str(home), "config", "reset", "output.preview_bytes", "--all"]) == 2
    reset_conflict_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in reset_conflict_err
    _assert_duplicate_option_error(["--home", str(home), "config", "reset", "--all", "--all"], "--all", capsys)
    assert run(["--home", str(home), "config", "reset", "output.preview_bytes", "--reason", "ignored"]) == 2
    unsupported_config_reset_err = capsys.readouterr().err
    assert _field_labels(unsupported_config_reset_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_config_reset_err
    assert "unsupported option --reason" in unsupported_config_reset_err
    assert run(["--home", str(home), "config", "show"]) == 0
    assert "preview bytes: 1234" in capsys.readouterr().out
    assert run(["--home", str(home), "config", "reset", "output.preview_bytes"]) == 0
    reset_field_out = capsys.readouterr().out
    assert _field_labels(reset_field_out) == ["object", "reset", "field", "value", "config valid"]
    assert "reset: field" in reset_field_out
    assert run(["--home", str(home), "config", "show"]) == 0
    assert "preview bytes: 4096" in capsys.readouterr().out

    (home / "config.toml").write_text((home / "config.toml").read_text(encoding="utf-8").replace('format = "text"', 'format = "rich"'), encoding="utf-8")
    assert run(["--home", str(home), "config", "set", "output.format", '"text"']) == 0
    repair_out = capsys.readouterr().out
    assert "field: output.format" in repair_out
    assert run(["--home", str(home), "config", "reset", "--all"]) == 0
    assert "reset: all" in capsys.readouterr().out
    _assert_duplicate_option_error(["--home", str(home), "config", "validate", "--refresh-capabilities", "--refresh-capabilities"], "--refresh-capabilities", capsys)
    assert run(["--home", str(home), "config", "validate", "--reason", "ignored"]) == 2
    unsupported_config_validate_err = capsys.readouterr().err
    assert _field_labels(unsupported_config_validate_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_config_validate_err
    assert "unsupported option --reason" in unsupported_config_validate_err
    assert run(["--home", str(home), "config", "validate", "extra"]) == 2
    extra_config_validate_err = capsys.readouterr().err
    assert _field_labels(extra_config_validate_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_config_validate_err
    assert "config validate accepts no positional arguments" in extra_config_validate_err
    (home / "config.toml").write_text((home / "config.toml").read_text(encoding="utf-8").replace("preview_bytes = 4096", "preview_bytes = true"), encoding="utf-8")
    assert run(["--home", str(home), "config", "validate"]) == 2
    validate_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in validate_err
    assert "output.preview_bytes must be a positive integer" in validate_err
    assert run(["--home", str(home), "config", "reset", "--all"]) == 0
    assert "reset: all" in capsys.readouterr().out
    valid_global_config = (home / "config.toml").read_text(encoding="utf-8")
    invalid_global_configs = [
        (
            valid_global_config.replace("schema_version = 1", "schema_version = true"),
            "global config schema_version must be 1",
        ),
        (
            valid_global_config.replace("schema_version = 1", "schema_version = 1\nunknown = true"),
            "global config contains unknown keys: unknown",
        ),
        (
            valid_global_config.replace("format = \"text\"", "format = \"text\"\nextra = 1"),
            "output contains unknown keys: extra",
        ),
        (
            valid_global_config.replace("[output]\nformat = \"text\"\npreview_bytes = 4096", "output = \"text\""),
            "output must be a table",
        ),
    ]
    for invalid_config, reason in invalid_global_configs:
        (home / "config.toml").write_text(invalid_config, encoding="utf-8")
        assert run(["--home", str(home), "config", "validate"]) == 2
        invalid_config_err = capsys.readouterr().err
        assert "error code: CONFIG_INVALID" in invalid_config_err
        assert reason in invalid_config_err
        assert run(["--home", str(home), "config", "show"]) == 2
        invalid_config_show_err = capsys.readouterr().err
        assert "error code: CONFIG_INVALID" in invalid_config_show_err
        assert reason in invalid_config_show_err
    assert run(["--home", str(home), "config", "reset", "--all"]) == 0
    assert "reset: all" in capsys.readouterr().out
    valid_global_config = (home / "config.toml").read_text(encoding="utf-8")
    invalid_syntax_config = "schema_version = 1\n[output\n"
    (home / "config.toml").write_text(invalid_syntax_config, encoding="utf-8")
    assert run(["--home", str(home), "config", "set", "output.preview_bytes", "2048"]) == 2
    invalid_syntax_set_err = capsys.readouterr().err
    assert _field_labels(invalid_syntax_set_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in invalid_syntax_set_err
    assert "invalid global config:" in invalid_syntax_set_err
    assert "next: alab config reset --all" in invalid_syntax_set_err
    assert (home / "config.toml").read_text(encoding="utf-8") == invalid_syntax_config
    assert run(["--home", str(home), "config", "reset", "output.preview_bytes"]) == 2
    invalid_syntax_reset_err = capsys.readouterr().err
    assert _field_labels(invalid_syntax_reset_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in invalid_syntax_reset_err
    assert "invalid global config:" in invalid_syntax_reset_err
    assert "next: alab config reset --all" in invalid_syntax_reset_err
    assert (home / "config.toml").read_text(encoding="utf-8") == invalid_syntax_config
    assert run(["--home", str(home), "config", "validate"]) == 2
    invalid_syntax_validate_err = capsys.readouterr().err
    assert _field_labels(invalid_syntax_validate_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in invalid_syntax_validate_err
    assert "invalid global config:" in invalid_syntax_validate_err
    assert "next: alab config reset --all" in invalid_syntax_validate_err
    assert run(["--home", str(home), "--key", root_key, "key", "list", "--root"]) == 2
    invalid_syntax_command_err = capsys.readouterr().err
    assert _field_labels(invalid_syntax_command_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in invalid_syntax_command_err
    assert "invalid global config:" in invalid_syntax_command_err
    assert run(["--home", str(home), "--key", "not-a-valid-alab-key", "key", "list", "--root"]) == 2
    invalid_syntax_bad_key_err = capsys.readouterr().err
    assert _field_labels(invalid_syntax_bad_key_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in invalid_syntax_bad_key_err
    assert "invalid global config:" in invalid_syntax_bad_key_err
    for help_args in [[], ["help"], ["--help"]]:
        assert run(["--home", str(home), *help_args]) == 2
        invalid_syntax_help_err = capsys.readouterr().err
        assert _field_labels(invalid_syntax_help_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in invalid_syntax_help_err
        assert "invalid global config:" in invalid_syntax_help_err
    assert run(["--home", str(home), "config", "reset", "--all"]) == 0
    assert "reset: all" in capsys.readouterr().out
    assert (home / "config.toml").read_text(encoding="utf-8") == valid_global_config


def test_cache_prune_removes_trash_cache_entries(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    root_credential_id = root_key.removeprefix("alab_root_v1_").rpartition("_")[0]
    old_trash_path = home / "tmp" / "trash" / "manual-audit" / "old-leftover"
    fresh_trash_path = home / "tmp" / "trash" / "manual-audit" / "fresh-leftover"
    old_trash_path.mkdir(parents=True)
    fresh_trash_path.mkdir(parents=True)
    (old_trash_path / "payload.txt").write_text("old staged bytes\n", encoding="utf-8")
    (fresh_trash_path / "payload.txt").write_text("fresh staged bytes\n", encoding="utf-8")
    with sqlite3.connect(home / "alab.db") as conn:
        conn.executemany(
            """
            INSERT INTO cache_entries(cache_id, cache_kind, cache_key, project_id, path, docker_tag,
              size_bytes, status, metadata_json, created_at, last_used_at, removed_at)
            VALUES (?, 'trash', ?, NULL, ?, NULL, NULL, 'active',
              '{"schema_version":1}', ?, ?, NULL)
            """,
            [
                ("cache-trash-old", "manual-audit-old", str(old_trash_path), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
                ("cache-trash-fresh", "manual-audit-fresh", str(fresh_trash_path), "2999-01-01T00:00:00Z", "2999-01-01T00:00:00Z"),
            ],
        )
        conn.commit()

    invalid_cache_prunes = [
        (["--home", str(home), "--key", root_key, "cache", "prune"], "cache prune requires at least one selector"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--all", "--trash"], "--all conflicts with specific cache selectors"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--all", "--older-than", "1"], "--all conflicts with --older-than"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--trash"], "--trash requires --older-than"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--trash", "--trash-all"], "--trash conflicts with --trash-all"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--trash-all", "--older-than", "1"], "--trash-all conflicts with --older-than"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--docker-images", "--older-than", "1"], "--older-than is only valid with --trash"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--trash", "--older-than", "not-an-int"], "--older-than must be an integer number of days"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--all", "--all"], "--all may be provided once"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--trash", "--trash", "--older-than", "1"], "--trash may be provided once"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--trash", "--older-than", "1", "--older-than", "2"], "--older-than may be provided once"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--trash-all", "--trash-all"], "--trash-all may be provided once"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "extra", "--trash", "--older-than", "1"], "cache prune accepts no positional arguments"),
        (["--home", str(home), "--key", root_key, "cache", "prune", "--trash", "--older-than", "1", "--reason", "ignored"], "unsupported option --reason"),
    ]
    for args, message in invalid_cache_prunes:
        assert run(args) == 2
        err = capsys.readouterr().err
        assert _field_labels(err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in err
        assert message in err
        assert old_trash_path.exists()
        assert fresh_trash_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0] == 2

    assert run(["--home", str(home), "--key", root_key, "cache", "prune", "--trash", "--older-than", "1"]) == 0
    old_out = capsys.readouterr().out
    assert _field_labels(old_out) == _cache_prune_field_labels(cache_kind_count=1)
    assert "cache pruned count: 1" in old_out
    old_audit_id = _field(old_out, "audit id")
    assert not old_trash_path.exists()
    assert fresh_trash_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        old_status = conn.execute("SELECT status FROM cache_entries WHERE cache_id = 'cache-trash-old'").fetchone()[0]
        fresh_status = conn.execute("SELECT status FROM cache_entries WHERE cache_id = 'cache-trash-fresh'").fetchone()[0]
        old_audit_row = conn.execute(
            "SELECT actor_credential_id, action, object_type, object_id, cascade, metadata_json FROM audit_events WHERE audit_id = ?",
            (old_audit_id,),
        ).fetchone()
    assert old_status == "removed"
    assert fresh_status == "active"
    assert old_audit_row[:5] == (root_credential_id, "prune", "cache", "cache", 0)
    assert json.loads(old_audit_row[5]) == {
        "schema_version": 1,
        "cache_kinds": ["trash"],
        "pruned_count": 1,
        "warning_count": 0,
    }

    assert run(["--home", str(home), "--key", root_key, "cache", "prune", "--trash-all"]) == 0
    out = capsys.readouterr().out

    assert _field_labels(out) == _cache_prune_field_labels(cache_kind_count=1)
    assert "cache pruned count: 1" in out
    fresh_audit_id = _field(out, "audit id")
    assert not fresh_trash_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        status = conn.execute("SELECT status FROM cache_entries WHERE cache_id = 'cache-trash-fresh'").fetchone()[0]
        fresh_audit_row = conn.execute(
            "SELECT actor_credential_id, action, object_type, object_id, cascade, metadata_json FROM audit_events WHERE audit_id = ?",
            (fresh_audit_id,),
        ).fetchone()
    assert status == "removed"
    assert fresh_audit_row[:5] == (root_credential_id, "prune", "cache", "cache", 0)
    assert json.loads(fresh_audit_row[5]) == {
        "schema_version": 1,
        "cache_kinds": ["trash"],
        "pruned_count": 1,
        "warning_count": 0,
    }


def test_cache_prune_docker_image_failure_renders_warning_and_keeps_entry(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    root_credential_id = root_key.removeprefix("alab_root_v1_").rpartition("_")[0]
    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute(
            """
            INSERT INTO cache_entries(cache_id, cache_kind, cache_key, project_id, path, docker_tag,
              size_bytes, status, metadata_json, created_at, last_used_at, removed_at)
            VALUES ('cache-docker-failed', 'docker_image', 'docker-failed', NULL, NULL,
              'alab-cache:failed-prune', NULL, 'active', '{"schema_version":1}',
              '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', NULL)
            """
        )

    def fake_prune_docker_image(tag: str) -> tuple[bool, str | None]:
        assert tag == "alab-cache:failed-prune"
        return False, "fake docker refused removal"

    monkeypatch.setattr(maintenance_services, "prune_docker_image", fake_prune_docker_image)

    assert run(["--home", str(home), "--key", root_key, "cache", "prune", "--docker-images"]) == 0
    out = capsys.readouterr().out
    assert _block_labels(out) == [
        _cache_prune_field_labels(cache_kind_count=1),
        ["object", "warning code", "warning reason"],
    ]
    assert "cache pruned count: 0" in out
    assert "cache kind: docker_image" in out
    audit_id = _field(out, "audit id")
    assert "warning code: DOCKER_CACHE_PRUNE_FAILED" in out
    assert "warning reason: alab-cache:failed-prune: fake docker refused removal" in out

    with sqlite3.connect(home / "alab.db") as conn:
        status = conn.execute(
            "SELECT status FROM cache_entries WHERE cache_id = 'cache-docker-failed'",
        ).fetchone()[0]
        audit_row = conn.execute(
            "SELECT actor_credential_id, action, object_type, object_id, cascade, metadata_json FROM audit_events WHERE audit_id = ?",
            (audit_id,),
        ).fetchone()
    assert status == "active"
    assert audit_row[:5] == (root_credential_id, "prune", "cache", "cache", 0)
    assert json.loads(audit_row[5]) == {
        "schema_version": 1,
        "cache_kinds": ["docker_image"],
        "pruned_count": 0,
        "warning_count": 1,
    }


def test_trash_staging_uses_same_parent_fallback_on_cross_device_rename(tmp_path, monkeypatch) -> None:
    home = Home(tmp_path / "home")
    home.tmp_path.mkdir(parents=True)
    external_parent = tmp_path / "external"
    victim = external_parent / "victim"
    victim.mkdir(parents=True)
    (victim / "payload.txt").write_text("payload\n", encoding="utf-8")
    audit_id = "aud-cross-device"
    original_rename = Path.rename

    def rename_with_exdev(self: Path, target: Path | str) -> Path:
        target_path = Path(target)
        if self == victim and target_path.parent == home.tmp_path / "trash" / audit_id:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", rename_with_exdev)

    stage = services._stage_path_to_trash(home, victim, audit_id)

    assert stage.mode == "same_parent"
    assert stage.audit_label == f".alab-trash-{audit_id}"
    assert stage.trash_path == external_parent / f".alab-trash-{audit_id}"
    assert not victim.exists()
    assert (stage.trash_path / "payload.txt").read_text(encoding="utf-8") == "payload\n"
    assert not (home.tmp_path / "trash" / audit_id).exists()

    services._restore_staged_trash(stage)

    assert (victim / "payload.txt").read_text(encoding="utf-8") == "payload\n"
    assert not stage.trash_path.exists()


def _init_trash_restore_project(tmp_path: Path, capsys, *, include_root: bool = False):
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    source.mkdir()
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Trash Restore Project"
task = "Restore staged trash when DB writes fail"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    if include_root:
        return home, project_id, root_key, admin_key
    return home, project_id, admin_key


def _init_artifact_log_restore_project(tmp_path: Path, monkeypatch, capsys):
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

print(f"restore run {os.environ['ALAB_RUN_ID']}")
Path(os.environ["ALAB_RUN_DIR"], "artifact.txt").write_text("restore artifact", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Artifact Log Restore Project"
task = "Restore observe trash when DB writes fail"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    worktree = tmp_path / "observe-trash-restore"
    assert run(["--home", str(home), "--key", admin_key, "exp", "create", "--project", project_id, "--name", "Observe Trash Restore", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "observe restore"]) == 0
    run_id = _field(capsys.readouterr().out, "run id")
    monkeypatch.chdir(tmp_path)

    artifact_store = home / "projects" / project_id / "artifacts"
    with sqlite3.connect(home / "alab.db") as conn:
        artifact_id, artifact_rel = conn.execute(
            "SELECT artifact_id, blob_path FROM artifacts WHERE run_id = ? AND blob_path IS NOT NULL",
            (run_id,),
        ).fetchone()
        log_rows = conn.execute(
            "SELECT log_id, stream, file_path FROM log_streams WHERE run_id = ? ORDER BY stream, log_id",
            (run_id,),
        ).fetchall()
        latest_run_id = conn.execute("SELECT latest_run_id FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()[0]
    assert latest_run_id == run_id
    assert log_rows
    return {
        "home": home,
        "project_id": project_id,
        "admin_key": admin_key,
        "exp_id": exp_id,
        "run_id": run_id,
        "artifact_id": artifact_id,
        "artifact_path": artifact_store / artifact_rel,
        "logs": [(log_id, stream, artifact_store / file_path) for log_id, stream, file_path in log_rows],
    }


def _init_validation_trash_restore_project(tmp_path: Path, capsys):
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

print(f"validation {os.environ['ALAB_RUN_ID']}")
Path(os.environ["ALAB_RUN_DIR"], "validation-artifact.txt").write_text(os.environ["ALAB_RUN_ID"], encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Validation Trash Restore Project"
task = "Restore validation trash when DB writes fail"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:validation-artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    baseline_validation_id = _field(project_out, "validation id")
    assert run(["--home", str(home), "--key", admin_key, "project", "validate", "--project", project_id]) == 0
    active_validation_id = _field(capsys.readouterr().out, "validation id")
    assert active_validation_id != baseline_validation_id
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "archive", baseline_validation_id, "--project", project_id]) == 0
    capsys.readouterr()

    artifact_store = home / "projects" / project_id / "artifacts"
    with sqlite3.connect(home / "alab.db") as conn:
        artifact_rows = conn.execute(
            "SELECT artifact_id, blob_path FROM artifacts WHERE validation_id = ? AND blob_path IS NOT NULL ORDER BY artifact_id",
            (baseline_validation_id,),
        ).fetchall()
        log_rows = conn.execute(
            "SELECT log_id, stream, file_path FROM log_streams WHERE validation_id = ? ORDER BY stream, log_id",
            (baseline_validation_id,),
        ).fetchall()
    assert len(artifact_rows) == 1
    assert len(log_rows) == 2
    for artifact_id, _blob_path in artifact_rows:
        assert run(["--home", str(home), "--key", admin_key, "artifacts", "archive", artifact_id, "--project", project_id]) == 0
        capsys.readouterr()
    for log_id, _stream, _file_path in log_rows:
        assert run(["--home", str(home), "--key", admin_key, "logs", "archive", log_id, "--project", project_id]) == 0
        capsys.readouterr()

    return {
        "home": home,
        "project_id": project_id,
        "admin_key": admin_key,
        "baseline_validation_id": baseline_validation_id,
        "active_validation_id": active_validation_id,
        "artifacts": [(artifact_id, artifact_store / blob_path) for artifact_id, blob_path in artifact_rows],
        "logs": [(log_id, stream, artifact_store / file_path) for log_id, stream, file_path in log_rows],
    }


def test_worktree_remove_restores_staged_trash_after_transaction_failure(tmp_path, monkeypatch, capsys) -> None:
    home, project_id, admin_key = _init_trash_restore_project(tmp_path, capsys)
    worktree = tmp_path / "trash-restore-worktree"
    assert run(["--home", str(home), "--key", admin_key, "exp", "create", "--project", project_id, "--name", "Trash Restore", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")

    original_audit = source_services.audit

    def fail_worktree_remove_audit(conn, **kwargs):
        if kwargs.get("action") == "remove" and kwargs.get("object_type") == "worktree":
            raise sqlite3.OperationalError("injected audit failure")
        return original_audit(conn, **kwargs)

    monkeypatch.setattr(services, "audit", fail_worktree_remove_audit)

    assert (
        run(
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
        == 5
    )
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: STORAGE_ERROR" in err
    assert "database update failed after trash staging: OperationalError" in err
    assert "next: alab context repair" in err

    assert (worktree / "main.py").read_text(encoding="utf-8") == "print('candidate')\n"
    assert (worktree / ".alab" / "token").exists()
    assert not any(path.name.startswith(".alab-trash-") for path in tmp_path.iterdir())
    trash_root = home / "tmp" / "trash"
    assert not trash_root.exists() or not any(trash_root.rglob("*"))

    with sqlite3.connect(home / "alab.db") as conn:
        exp_row = conn.execute("SELECT worktree_state, worktree_path FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()
        assert exp_row == ("active", str(worktree))
        assert conn.execute("SELECT COUNT(*) FROM path_registry WHERE exp_id = ? AND status = 'active'", (exp_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE exp_id = ? AND status = 'active'", (exp_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'remove' AND object_type = 'worktree' AND object_id = ?", (exp_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0] == 0


def test_source_remove_restores_deleted_ref_after_transaction_failure(tmp_path, monkeypatch, capsys) -> None:
    home, project_id, admin_key = _init_trash_restore_project(tmp_path, capsys)
    assert run(["--home", str(home), "--key", admin_key, "source", "import", "--project", project_id, "--source-empty", "--name", "Ref Restore Source"]) == 0
    import_out = capsys.readouterr().out
    source_id = _field(import_out, "source id")
    source_ref = _field(import_out, "source ref")
    assert run(["--home", str(home), "--key", admin_key, "source", "archive", source_id, "--project", project_id]) == 0
    capsys.readouterr()

    repo_git = home / "projects" / project_id / "repo.git"
    branch_ref = f"refs/heads/{source_ref}"
    branch_commit = _git(["--git-dir", str(repo_git), "rev-parse", "--verify", branch_ref], home)
    original_audit = services.audit

    def fail_source_remove_audit(conn, **kwargs):
        if kwargs.get("action") == "remove" and kwargs.get("object_type") == "source":
            raise sqlite3.OperationalError("injected source audit failure")
        return original_audit(conn, **kwargs)

    monkeypatch.setattr(source_services, "audit", fail_source_remove_audit)

    assert run(["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--force", "--confirm", source_id]) == 5
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: STORAGE_ERROR" in err
    assert "database update failed after source ref deletion: OperationalError" in err
    assert "next: alab context repair" in err
    assert _git(["--git-dir", str(repo_git), "rev-parse", "--verify", branch_ref], home) == branch_commit

    with sqlite3.connect(home / "alab.db") as conn:
        source_row = conn.execute("SELECT status, source_ref FROM sources WHERE source_id = ?", (source_id,)).fetchone()
        assert source_row == ("archived", source_ref)
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'remove' AND object_type = 'source' AND object_id = ?", (source_id,)).fetchone()[0] == 0


def test_experiment_remove_restores_branch_and_trash_after_transaction_failure(tmp_path, monkeypatch, capsys) -> None:
    home, project_id, admin_key = _init_trash_restore_project(tmp_path, capsys)
    worktree = tmp_path / "trash-restore-exp"
    assert run(["--home", str(home), "--key", admin_key, "exp", "create", "--project", project_id, "--name", "Exp Trash Restore", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    assert run(["--home", str(home), "--key", admin_key, "exp", "archive", exp_id, "--project", project_id]) == 0
    capsys.readouterr()

    repo_git = home / "projects" / project_id / "repo.git"
    branch_ref = f"refs/heads/alab/exp/{exp_id}"
    branch_commit = _git(["--git-dir", str(repo_git), "rev-parse", "--verify", branch_ref], home)
    original_audit = observe_services.audit

    def fail_experiment_remove_audit(conn, **kwargs):
        if kwargs.get("action") == "remove" and kwargs.get("object_type") == "experiment":
            raise sqlite3.OperationalError("injected experiment audit failure")
        return original_audit(conn, **kwargs)

    monkeypatch.setattr(services, "audit", fail_experiment_remove_audit)

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "remove",
                exp_id,
                "--project",
                project_id,
                "--cascade",
                "--force",
                "--confirm",
                exp_id,
            ]
        )
        == 5
    )
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: STORAGE_ERROR" in err
    assert "database update failed after trash staging: OperationalError" in err
    assert "next: alab context repair" in err
    assert _git(["--git-dir", str(repo_git), "rev-parse", "--verify", branch_ref], home) == branch_commit
    assert (worktree / "main.py").read_text(encoding="utf-8") == "print('candidate')\n"
    assert (worktree / ".alab" / "token").exists()
    trash_root = home / "tmp" / "trash"
    assert not trash_root.exists() or not any(trash_root.rglob("*"))

    with sqlite3.connect(home / "alab.db") as conn:
        exp_row = conn.execute("SELECT status, worktree_state, worktree_path FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()
        assert exp_row == ("archived", "active", str(worktree))
        assert conn.execute("SELECT COUNT(*) FROM path_registry WHERE exp_id = ? AND status = 'active'", (exp_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE exp_id = ? AND status = 'active'", (exp_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'remove' AND object_type = 'experiment' AND object_id = ?", (exp_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0] == 0


def test_checkout_remove_restores_staged_trash_after_transaction_failure(tmp_path, monkeypatch, capsys) -> None:
    home, project_id, admin_key = _init_trash_restore_project(tmp_path, capsys)
    worktree = tmp_path / "trash-restore-checkout-exp"
    inspect = tmp_path / "trash-restore-inspect"
    assert run(["--home", str(home), "--key", admin_key, "exp", "create", "--project", project_id, "--name", "Checkout Trash Restore", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(inspect), "--commit", "latest"]) == 0
    token_id = _field(capsys.readouterr().out, "token id")
    original_audit = services.audit

    def fail_checkout_remove_audit(conn, **kwargs):
        if kwargs.get("action") == "remove" and kwargs.get("object_type") == "inspection_checkout":
            raise sqlite3.OperationalError("injected checkout audit failure")
        return original_audit(conn, **kwargs)

    monkeypatch.setattr(services, "audit", fail_checkout_remove_audit)

    assert (
        run(
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
                token_id,
                "--force",
                "--confirm",
                token_id,
            ]
        )
        == 5
    )
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: STORAGE_ERROR" in err
    assert "database update failed after trash staging: OperationalError" in err
    assert "next: alab context repair" in err
    assert (inspect / "main.py").read_text(encoding="utf-8") == "print('candidate')\n"
    assert (inspect / ".alab" / "token").exists()
    assert not any(path.name.startswith(".alab-trash-") for path in tmp_path.iterdir())
    trash_root = home / "tmp" / "trash"
    assert not trash_root.exists() or not any(trash_root.rglob("*"))

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM path_registry WHERE token_id = ? AND context_type = 'inspection'", (token_id,)).fetchone()[0] == "active"
        assert conn.execute("SELECT status FROM credentials WHERE credential_id = ? AND token_mode = 'inspection'", (token_id,)).fetchone()[0] == "active"
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'remove' AND object_type = 'inspection_checkout' AND object_id = ?", (token_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0] == 0


def test_project_remove_restores_whole_tree_trash_after_transaction_failure(tmp_path, monkeypatch, capsys) -> None:
    home, project_id, root_key, admin_key = _init_trash_restore_project(tmp_path, capsys, include_root=True)
    worktree = tmp_path / "trash-restore-project-exp"
    assert run(["--home", str(home), "--key", admin_key, "exp", "create", "--project", project_id, "--name", "Project Trash Restore", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    with sqlite3.connect(home / "alab.db") as conn:
        control_path = Path(conn.execute("SELECT control_path FROM projects WHERE project_id = ?", (project_id,)).fetchone()[0])
    project_root = home / "projects" / project_id
    assert run(["--home", str(home), "--key", admin_key, "project", "archive", "--project", project_id]) == 0
    capsys.readouterr()
    original_audit = services.audit

    def fail_project_remove_audit(conn, **kwargs):
        if kwargs.get("action") == "remove" and kwargs.get("object_type") == "project":
            raise sqlite3.OperationalError("injected project audit failure")
        return original_audit(conn, **kwargs)

    monkeypatch.setattr(services, "audit", fail_project_remove_audit)

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "remove",
                "--project",
                project_id,
                "--cascade",
                "--force",
                "--confirm",
                project_id,
            ]
        )
        == 5
    )
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: STORAGE_ERROR" in err
    assert "database update failed after trash staging: OperationalError" in err
    assert "next: alab context repair" in err
    assert project_root.exists()
    assert control_path.exists()
    assert (worktree / "main.py").read_text(encoding="utf-8") == "print('candidate')\n"
    assert (worktree / ".alab" / "token").exists()
    assert not any(path.name.startswith(".alab-trash-") for path in tmp_path.iterdir())
    trash_root = home / "tmp" / "trash"
    assert not trash_root.exists() or not any(trash_root.rglob("*"))

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM projects WHERE project_id = ?", (project_id,)).fetchone()[0] == "archived"
        exp_row = conn.execute("SELECT worktree_state, worktree_path FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()
        assert exp_row == ("active", str(worktree))
        assert conn.execute("SELECT status FROM path_registry WHERE exp_id = ? AND context_type = 'experiment'", (exp_id,)).fetchone()[0] == "active"
        assert conn.execute("SELECT status FROM credentials WHERE exp_id = ? AND token_mode = 'worktree'", (exp_id,)).fetchone()[0] == "active"
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'remove' AND object_type = 'project' AND object_id = ?", (project_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0] == 0


def test_validation_remove_restores_staged_trash_after_transaction_failure(tmp_path, monkeypatch, capsys) -> None:
    state = _init_validation_trash_restore_project(tmp_path, capsys)
    home = state["home"]
    project_id = state["project_id"]
    admin_key = state["admin_key"]
    baseline_validation_id = state["baseline_validation_id"]
    active_validation_id = state["active_validation_id"]
    artifacts = state["artifacts"]
    logs = state["logs"]
    original_audit = services.audit

    def fail_validation_remove_audit(conn, **kwargs):
        if kwargs.get("action") == "remove" and kwargs.get("object_type") == "validation":
            raise sqlite3.OperationalError("injected validation audit failure")
        return original_audit(conn, **kwargs)

    monkeypatch.setattr(services, "audit", fail_validation_remove_audit)
    assert all(path.exists() for _artifact_id, path in artifacts)
    assert all(path.exists() for _log_id, _stream, path in logs)

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "validation",
                "remove",
                baseline_validation_id,
                "--project",
                project_id,
                "--cascade",
                "--force",
                "--confirm",
                baseline_validation_id,
            ]
        )
        == 5
    )
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: STORAGE_ERROR" in err
    assert "database update failed after trash staging: OperationalError" in err
    assert "next: alab context repair" in err
    assert all(path.read_text(encoding="utf-8") == baseline_validation_id for _artifact_id, path in artifacts)
    assert all(path.exists() for _log_id, _stream, path in logs)
    trash_root = home / "tmp" / "trash"
    assert not trash_root.exists() or not any(trash_root.rglob("*"))

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT archive_status FROM project_validations WHERE validation_id = ?", (baseline_validation_id,)).fetchone()[0] == "archived"
        assert conn.execute("SELECT active_validation_id FROM projects WHERE project_id = ?", (project_id,)).fetchone()[0] == active_validation_id
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE validation_id = ?", (baseline_validation_id,)).fetchone()[0] == len(artifacts)
        assert conn.execute("SELECT COUNT(*) FROM log_streams WHERE validation_id = ?", (baseline_validation_id,)).fetchone()[0] == len(logs)
        assert all(
            conn.execute("SELECT archive_status FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()[0] == "archived"
            for artifact_id, _path in artifacts
        )
        assert all(
            conn.execute("SELECT archive_status FROM log_streams WHERE log_id = ?", (log_id,)).fetchone()[0] == "archived"
            for log_id, _stream, _path in logs
        )
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'remove' AND object_type = 'validation' AND object_id = ?", (baseline_validation_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0] == 0


def test_observe_remove_restores_staged_trash_after_transaction_failure(tmp_path, monkeypatch, capsys) -> None:
    state = _init_artifact_log_restore_project(tmp_path, monkeypatch, capsys)
    home = state["home"]
    project_id = state["project_id"]
    admin_key = state["admin_key"]
    exp_id = state["exp_id"]
    run_id = state["run_id"]
    artifact_id = state["artifact_id"]
    artifact_path = state["artifact_path"]
    logs = state["logs"]
    stdout_log_id, _stdout_stream, stdout_log_path = next(row for row in logs if row[1] == "stdout")
    original_audit = services.audit

    def fail_observe_remove_audit(conn, **kwargs):
        if kwargs.get("action") == "remove" and kwargs.get("object_type") in {"artifact", "log", "run"}:
            raise sqlite3.OperationalError("injected observe audit failure")
        return original_audit(conn, **kwargs)

    monkeypatch.setattr(observe_services, "audit", fail_observe_remove_audit)
    assert artifact_path.exists()
    assert stdout_log_path.exists()

    assert run(["--home", str(home), "--key", admin_key, "artifacts", "archive", artifact_id, "--project", project_id]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "remove", artifact_id, "--project", project_id, "--force", "--confirm", artifact_id]) == 5
    artifact_err = capsys.readouterr().err
    assert _field_labels(artifact_err) == _error_field_labels()
    assert "error code: STORAGE_ERROR" in artifact_err
    assert "database update failed after trash staging: OperationalError" in artifact_err
    assert "next: alab context repair" in artifact_err
    assert artifact_path.read_text(encoding="utf-8") == "restore artifact"
    assert not any(path.name.startswith(".alab-trash-") for path in (artifact_path.parent if artifact_path.parent.exists() else tmp_path).iterdir())

    assert run(["--home", str(home), "--key", admin_key, "logs", "archive", stdout_log_id, "--project", project_id]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "--key", admin_key, "logs", "remove", stdout_log_id, "--project", project_id, "--force", "--confirm", stdout_log_id]) == 5
    log_err = capsys.readouterr().err
    assert _field_labels(log_err) == _error_field_labels()
    assert "error code: STORAGE_ERROR" in log_err
    assert "database update failed after trash staging: OperationalError" in log_err
    assert "next: alab context repair" in log_err
    assert stdout_log_path.exists()

    assert run(["--home", str(home), "--key", admin_key, "runs", "archive", run_id, "--project", project_id]) == 0
    capsys.readouterr()
    for log_id, _stream, _path in logs:
        assert run(["--home", str(home), "--key", admin_key, "logs", "archive", log_id, "--project", project_id]) == 0
        capsys.readouterr()
    assert run(["--home", str(home), "--key", admin_key, "runs", "remove", run_id, "--project", project_id, "--cascade", "--force", "--confirm", run_id]) == 5
    run_err = capsys.readouterr().err
    assert _field_labels(run_err) == _error_field_labels()
    assert "error code: STORAGE_ERROR" in run_err
    assert "database update failed after trash staging: OperationalError" in run_err
    assert "next: alab context repair" in run_err
    assert artifact_path.read_text(encoding="utf-8") == "restore artifact"
    assert all(path.exists() for _log_id, _stream, path in logs)
    trash_root = home / "tmp" / "trash"
    assert not trash_root.exists() or not any(trash_root.rglob("*"))

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT archive_status FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()[0] == "archived"
        assert conn.execute("SELECT archive_status FROM log_streams WHERE log_id = ?", (stdout_log_id,)).fetchone()[0] == "archived"
        assert conn.execute("SELECT archive_status FROM runs WHERE run_id = ?", (run_id,)).fetchone()[0] == "archived"
        assert conn.execute("SELECT latest_run_id FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()[0] == run_id
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM log_streams WHERE run_id = ?", (run_id,)).fetchone()[0] == len(logs)
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE run_id = ?", (run_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'remove' AND object_type IN ('artifact', 'log', 'run')").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0] == 0


def test_project_init_rejects_runtime_flags(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("print('ok')\n", encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Runtime Flag Project"
task = "Reject init runtime flags"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")

    for runtime_flag, value in [
        ("--runner-type", "local"),
        ("--reward-type", "exit_code"),
        ("--artifact-glob", "run:out.txt"),
        ("--log-stdout-limit", "1024"),
        ("--env", "FOO=bar"),
        ("--secret-env", "TOKEN=secret"),
        ("--docker-image", "python:3.12"),
        ("--harbor-task-ref", "harbor:task"),
        ("--skydiscover-task-ref", "skydiscover:task"),
    ]:
        assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source), runtime_flag, value]) == 2
        err = capsys.readouterr().err
        assert _field_labels(err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in err
        assert runtime_flag in err
        assert "set runtime fields in --config" in err

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE credential_type = 'admin'").fetchone()[0] == 0


def test_project_init_requires_explicit_mode_source_origin(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    first_source = tmp_path / "first-source"
    second_source = tmp_path / "second-source"
    first_source.mkdir()
    second_source.mkdir()
    (first_source / "main.py").write_text("print('first')\n", encoding="utf-8")
    (second_source / "main.py").write_text("print('second')\n", encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Explicit Source Origin"
task = "Require init mode source origin"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    second_config = tmp_path / "second.project.toml"
    second_config.write_text(config.read_text(encoding="utf-8").replace("Explicit Source Origin", "Second Explicit Source Origin"), encoding="utf-8")

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")

    invalid_inits = [
        ("local", "project init local requires --source-path"),
        ("git", "project init git requires --source-git"),
        ("empty", "project init empty requires --source-empty"),
    ]
    for mode, message in invalid_inits:
        assert run(["--home", str(home), "--key", root_key, "project", "init", mode, "--config", str(config), "--skip-baseline-test"]) == 2
        err = capsys.readouterr().err
        assert _field_labels(err) == _error_field_labels()
        assert "error code: SOURCE_INVALID" in err
        assert message in err

    assert (
        run(
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
                str(first_source),
                "--source-path",
                str(second_source),
                "--skip-baseline-test",
            ]
        )
        == 2
    )
    duplicate_origin_err = capsys.readouterr().err
    assert _field_labels(duplicate_origin_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_origin_err
    assert "--source-path may be provided once" in duplicate_origin_err

    duplicate_single_option_cases = [
        (
            [
                "--config",
                str(config),
                "--config",
                str(second_config),
                "--source-path",
                str(first_source),
                "--skip-baseline-test",
            ],
            "--config may be provided once",
        ),
        (
            [
                "--config",
                str(config),
                "--source-path",
                str(first_source),
                "--name",
                "first",
                "--name",
                "second",
                "--skip-baseline-test",
            ],
            "--name may be provided once",
        ),
        (
            [
                "--config",
                str(config),
                "--source-path",
                str(first_source),
                "--skip-baseline-test",
                "--skip-baseline-test",
            ],
            "--skip-baseline-test may be provided once",
        ),
    ]
    for duplicate_args, message in duplicate_single_option_cases:
        assert run(["--home", str(home), "--key", root_key, "project", "init", "local", *duplicate_args]) == 2
        duplicate_single_err = capsys.readouterr().err
        assert _field_labels(duplicate_single_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_single_err
        assert message in duplicate_single_err

    assert (
        run(
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
                str(first_source),
                "--max-files",
                "0",
                "--skip-baseline-test",
            ]
        )
        == 2
    )
    source_limit_err = capsys.readouterr().err
    assert _field_labels(source_limit_err) == _error_field_labels()
    assert "error code: SOURCE_LIMIT_EXCEEDED" in source_limit_err
    assert "source import exceeds max files: 0" in source_limit_err

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM project_config_versions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE credential_type = 'admin'").fetchone()[0] == 0
    assert list((home / "projects").iterdir()) == []
    assert list((home / "project-workspaces").iterdir()) == []
    init_dir = home / "tmp" / "init"
    assert not init_dir.exists() or list(init_dir.iterdir()) == []


def test_project_init_source_ref_mismatch_cleans_staged_paths(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("print('ok')\n", encoding="utf-8")
    config = tmp_path / "mismatched-source-ref.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Source Ref Mismatch"
task = "Reject mismatched canonical source ref"

[source]
default_source_ref = "alab/source/src-not-the-staged-source"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 2
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in err
    assert "input source.default_source_ref does not match staged source ref" in err

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM project_config_versions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE credential_type = 'admin'").fetchone()[0] == 0
    assert list((home / "projects").iterdir()) == []
    assert list((home / "project-workspaces").iterdir()) == []
    assert list((home / "tmp" / "init").iterdir()) == []


def test_project_config_validation_edges(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("print('ok')\n", encoding="utf-8")

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    exact_multibyte_display = "界" * 40
    exact_multibyte_body = ("界" * 21845) + "x"
    long_multibyte_display = "界" * 41
    long_multibyte_body = "界" * 21846
    exact_tag = "a" * 64

    host_network_config = tmp_path / "host-network.toml"
    host_network_config.write_text(
        f"""
schema_version = 1

[project]
name = "Host Network Project"
task = "Reject host network"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
network = "host"
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(host_network_config), "--source-path", str(source)]) == 2
    host_network_err = capsys.readouterr().err
    assert _field_labels(host_network_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in host_network_err
    assert "network" in host_network_err

    long_name_config = tmp_path / "long-name.toml"
    long_name_config.write_text(
        f"""
schema_version = 1

[project]
name = "{"x" * 121}"
task = "Reject long project name"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(long_name_config), "--source-path", str(source)]) == 2
    long_name_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in long_name_err
    assert "project.name exceeds 120 bytes" in long_name_err

    long_multibyte_name_config = tmp_path / "long-multibyte-name.toml"
    long_multibyte_name_config.write_text(
        f"""
schema_version = 1

[project]
name = "{long_multibyte_display}"
task = "Reject long multibyte project name"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(long_multibyte_name_config), "--source-path", str(source)]) == 2
    long_multibyte_name_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in long_multibyte_name_err
    assert "project.name exceeds 120 bytes" in long_multibyte_name_err

    long_task_config = tmp_path / "long-task.toml"
    long_task_config.write_text(
        f"""
schema_version = 1

[project]
name = "Long Task Project"
task = "{long_multibyte_body}"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(long_task_config), "--source-path", str(source)]) == 2
    long_task_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in long_task_err
    assert "project.task exceeds 65536 bytes" in long_task_err

    long_goal_config = tmp_path / "long-goal.toml"
    long_goal_config.write_text(
        f"""
schema_version = 1

[project]
name = "Long Goal Project"
task = "Reject long goal"
goal = "{long_multibyte_body}"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(long_goal_config), "--source-path", str(source)]) == 2
    long_goal_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in long_goal_err
    assert "project.goal exceeds 65536 bytes" in long_goal_err

    exact_boundary_config = tmp_path / "exact-boundary.toml"
    exact_boundary_config.write_text(
        f"""
schema_version = 1

[project]
name = "{exact_multibyte_display}"
task = "{exact_multibyte_body}"
goal = "{exact_multibyte_body}"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(exact_boundary_config), "--source-path", str(source)]) == 0
    exact_boundary_out = capsys.readouterr().out
    assert _field_labels(exact_boundary_out) == _project_init_field_labels()
    assert "project status: valid" in exact_boundary_out

    failing_config = tmp_path / "failing-project.toml"
    failing_config.write_text(
        f"""
schema_version = 1

[project]
name = "Failing Baseline Project"
task = "Exercise baseline failure output"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "import sys; sys.exit(3)"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(failing_config), "--source-path", str(source)]) == 1
    failing_project_out = capsys.readouterr().out
    assert _field_labels(failing_project_out) == _project_init_field_labels(failure=True)
    failing_project_id = _field(failing_project_out, "project id")
    failing_admin_key = _field(failing_project_out, "admin key")
    assert "project status: invalid" in failing_project_out
    assert "validation status: failed" in failing_project_out
    assert "error code: BASELINE_VALIDATION_FAILED" in failing_project_out
    assert run(["--home", str(home), "--key", failing_admin_key, "project", "validate", "--project", failing_project_id]) == 1
    failing_validation_out = capsys.readouterr().out
    assert _field_labels(failing_validation_out) == _project_validation_field_labels(failure=True)
    assert "validation status: failed" in failing_validation_out
    assert "error code: BASELINE_VALIDATION_FAILED" in failing_validation_out

    invalid_env_config = tmp_path / "invalid-env.toml"
    invalid_env_config.write_text(
        f"""
schema_version = 1

[project]
name = "Invalid Env Project"
task = "Reject invalid env"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[env]
"BAD-NAME" = "value"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(invalid_env_config), "--source-path", str(source)]) == 2
    invalid_env_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in invalid_env_err
    assert "invalid environment variable name" in invalid_env_err

    valid_config = tmp_path / "valid-project.toml"
    valid_config.write_text(
        f"""
schema_version = 1

[project]
name = "Valid Config Project"
task = "Create valid project"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(valid_config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    failing_command = json.dumps([sys.executable, "-c", "import sys; sys.exit(4)"])
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "runner.command", failing_command, "--project", project_id]) == 1
    failing_config_out = capsys.readouterr().out
    assert _field_labels(failing_config_out) == _project_config_set_field_labels(failure=True)
    assert "runtime affecting: true" in failing_config_out
    assert "validation status: failed" in failing_config_out
    assert "project status: invalid" in failing_config_out
    assert "error code: BASELINE_VALIDATION_FAILED" in failing_config_out
    passing_command = json.dumps([sys.executable, "-c", "print('ok')"])
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "runner.command", passing_command, "--project", project_id]) == 0
    recovered_config_out = capsys.readouterr().out
    assert _field_labels(recovered_config_out) == _project_config_set_field_labels()
    assert "runtime affecting: true" in recovered_config_out
    assert "validation status: passed" in recovered_config_out
    assert "project status: valid" in recovered_config_out
    recovered_version = int(_field(recovered_config_out, "latest attempted config version"))
    with sqlite3.connect(home / "alab.db") as conn:
        recovered_project = conn.execute(
            "SELECT latest_attempted_config_version, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        recovered_hash = conn.execute(
            "SELECT config_hash FROM project_config_versions WHERE project_id = ? AND version = ?",
            (project_id, recovered_version),
        ).fetchone()[0]
        config_count = conn.execute(
            "SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "runner.command", passing_command, "--project", project_id]) == 0
    no_op_config_out = capsys.readouterr().out
    assert _field_labels(no_op_config_out) == _project_config_set_field_labels()
    assert f"latest attempted config version: {recovered_version}" in no_op_config_out
    assert "runtime affecting: false" in no_op_config_out
    assert "next: none" in no_op_config_out
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == config_count

    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "project.allow_public_exp_create", "false", "--project", project_id]) == 0
    metadata_config_out = capsys.readouterr().out
    assert _field_labels(metadata_config_out) == _project_config_set_field_labels()
    metadata_version = int(_field(metadata_config_out, "latest attempted config version"))
    assert metadata_version == recovered_version + 1
    assert "runtime affecting: false" in metadata_config_out
    assert "validation status: inherited" in metadata_config_out
    with sqlite3.connect(home / "alab.db") as conn:
        inherited_row = conn.execute(
            "SELECT validation_status, inherited_from_validation_id FROM project_config_versions WHERE project_id = ? AND version = ?",
            (project_id, metadata_version),
        ).fetchone()
        metadata_project = conn.execute(
            "SELECT active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert inherited_row == ("inherited", recovered_project[2])
    assert metadata_project == (metadata_version, recovered_project[2])

    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "project.allow_public_exp_create", "true", "--project", project_id]) == 0
    reverted_metadata_out = capsys.readouterr().out
    assert _field_labels(reverted_metadata_out) == _project_config_set_field_labels()
    reverted_metadata_version = int(_field(reverted_metadata_out, "latest attempted config version"))
    assert reverted_metadata_version == metadata_version + 1
    assert "runtime affecting: false" in reverted_metadata_out
    assert "validation status: inherited" in reverted_metadata_out
    with sqlite3.connect(home / "alab.db") as conn:
        reverted_hash = conn.execute(
            "SELECT config_hash FROM project_config_versions WHERE project_id = ? AND version = ?",
            (project_id, reverted_metadata_version),
        ).fetchone()[0]
        duplicate_hash_count = conn.execute(
            "SELECT COUNT(*) FROM project_config_versions WHERE project_id = ? AND config_hash = ?",
            (project_id, recovered_hash),
        ).fetchone()[0]
    assert reverted_hash == recovered_hash
    assert duplicate_hash_count >= 2

    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "project.allow_public_exp_create", "true", "--project", project_id]) == 0
    repeated_metadata_no_op_out = capsys.readouterr().out
    assert f"latest attempted config version: {reverted_metadata_version}" in repeated_metadata_no_op_out
    assert "next: none" in repeated_metadata_no_op_out

    with sqlite3.connect(home / "alab.db") as conn:
        before_dry_run_counts = {
            "configs": conn.execute("SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?", (project_id,)).fetchone()[0],
            "validations": conn.execute("SELECT COUNT(*) FROM project_validations WHERE project_id = ?", (project_id,)).fetchone()[0],
            "audit": conn.execute("SELECT COUNT(*) FROM audit_events WHERE project_id = ?", (project_id,)).fetchone()[0],
        }
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "runner.command", failing_command, "--project", project_id, "--dry-run"]) == 0
    dry_run_config_out = capsys.readouterr().out
    assert _field_labels(dry_run_config_out) == _project_config_set_field_labels()
    assert f"latest attempted config version: {reverted_metadata_version}" in dry_run_config_out
    assert "runtime affecting: true" in dry_run_config_out
    assert "validation status: dry-run" in dry_run_config_out
    assert "next: rerun without --dry-run" in dry_run_config_out
    with sqlite3.connect(home / "alab.db") as conn:
        after_dry_run_counts = {
            "configs": conn.execute("SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?", (project_id,)).fetchone()[0],
            "validations": conn.execute("SELECT COUNT(*) FROM project_validations WHERE project_id = ?", (project_id,)).fetchone()[0],
            "audit": conn.execute("SELECT COUNT(*) FROM audit_events WHERE project_id = ?", (project_id,)).fetchone()[0],
        }
        dry_run_project = conn.execute(
            "SELECT latest_attempted_config_version, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert after_dry_run_counts == before_dry_run_counts
    assert dry_run_project == (reverted_metadata_version, reverted_metadata_version, recovered_project[2])

    with sqlite3.connect(home / "alab.db") as conn:
        latest_config_json = json.loads(
            conn.execute(
                "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?",
                (project_id, reverted_metadata_version),
            ).fetchone()[0]
        )
        before_import_dry_run_counts = {
            "configs": conn.execute("SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?", (project_id,)).fetchone()[0],
            "validations": conn.execute("SELECT COUNT(*) FROM project_validations WHERE project_id = ?", (project_id,)).fetchone()[0],
            "audit": conn.execute("SELECT COUNT(*) FROM audit_events WHERE project_id = ?", (project_id,)).fetchone()[0],
        }
    latest_config_json["runner"]["command"] = [sys.executable, "-c", "import sys; sys.exit(99)"]
    dry_run_import_path = tmp_path / "dry-run-import.toml"
    dry_run_import_path.write_text(services.dumps_toml(latest_config_json), encoding="utf-8")
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "import", "--project", project_id, "--config", str(dry_run_import_path), "--dry-run"]) == 0
    dry_run_import_out = capsys.readouterr().out
    assert _field_labels(dry_run_import_out) == _project_config_set_field_labels()
    assert f"latest attempted config version: {reverted_metadata_version}" in dry_run_import_out
    assert "runtime affecting: true" in dry_run_import_out
    assert "validation status: dry-run" in dry_run_import_out
    with sqlite3.connect(home / "alab.db") as conn:
        after_import_dry_run_counts = {
            "configs": conn.execute("SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?", (project_id,)).fetchone()[0],
            "validations": conn.execute("SELECT COUNT(*) FROM project_validations WHERE project_id = ?", (project_id,)).fetchone()[0],
            "audit": conn.execute("SELECT COUNT(*) FROM audit_events WHERE project_id = ?", (project_id,)).fetchone()[0],
        }
        import_dry_run_project = conn.execute(
            "SELECT latest_attempted_config_version, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert after_import_dry_run_counts == before_import_dry_run_counts
    assert import_dry_run_project == (reverted_metadata_version, reverted_metadata_version, recovered_project[2])
    long_reason = "r" * 65537
    assert run(["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--dry-run", "--reason", long_reason]) == 2
    project_reason_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in project_reason_err
    assert "reason exceeds 65536 bytes" in project_reason_err
    assert run(["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--dry-run", "--reason", "one", "--reason", "two"]) == 2
    duplicate_project_reason_err = capsys.readouterr().err
    assert _field_labels(duplicate_project_reason_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_project_reason_err
    assert "--reason may be provided once" in duplicate_project_reason_err
    _assert_duplicate_option_error(["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--dry-run", "--dry-run", "--cascade"], "--dry-run", capsys)
    _assert_duplicate_option_error(["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--dry-run", "--cascade", "--cascade"], "--cascade", capsys)
    assert _audit_count(home, "remove", "project", project_id) == 0
    assert run(["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--dry-run", "--reason", long_multibyte_body]) == 2
    project_multibyte_reason_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in project_multibyte_reason_err
    assert "reason exceeds 65536 bytes" in project_multibyte_reason_err
    long_display = "x" * 121
    source2 = tmp_path / "source2"
    source2.mkdir()
    (source2 / "main.py").write_text("print('second')\n", encoding="utf-8")
    assert run(["--home", str(home), "--key", admin_key, "source", "import", "--project", project_id, "--source-path", str(source2), "--name", long_display]) == 2
    source_name_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in source_name_err
    assert "source name exceeds 120 bytes" in source_name_err
    assert run(["--home", str(home), "--key", admin_key, "source", "import", "--project", project_id, "--source-path", str(source2), "--name", long_multibyte_display]) == 2
    source_multibyte_name_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in source_multibyte_name_err
    assert "source name exceeds 120 bytes" in source_multibyte_name_err
    exact_source = tmp_path / "source-exact"
    exact_source.mkdir()
    (exact_source / "main.py").write_text("print('exact')\n", encoding="utf-8")
    assert run(["--home", str(home), "--key", admin_key, "source", "import", "--project", project_id, "--source-path", str(exact_source), "--name", exact_multibyte_display]) == 0
    exact_source_out = capsys.readouterr().out
    assert _field_labels(exact_source_out) == _source_import_field_labels()
    assert f"source name: {exact_multibyte_display}" in exact_source_out
    assert run(["--home", str(home), "--key", admin_key, "source", "import", "--project", project_id, "--source-path", str(source2), "--name", "second"]) == 0
    second_source_out = capsys.readouterr().out
    assert _field_labels(second_source_out) == _source_import_field_labels()
    second_source_id = _field(second_source_out, "source id")
    assert run(["--home", str(home), "--key", admin_key, "source", "remove", second_source_id, "--project", project_id, "--dry-run", "--reason", "one", "--reason", "two"]) == 2
    duplicate_source_reason_err = capsys.readouterr().err
    assert _field_labels(duplicate_source_reason_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_source_reason_err
    assert "--reason may be provided once" in duplicate_source_reason_err
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "source", "remove", second_source_id, "--project", project_id, "--dry-run", "--dry-run"], "--dry-run", capsys)
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "source", "remove", second_source_id, "--project", project_id, "--dry-run", "--cascade", "--cascade"], "--cascade", capsys)
    assert _audit_count(home, "remove", "source", second_source_id) == 0
    assert run(["--home", str(home), "--key", admin_key, "source", "remove", second_source_id, "--project", project_id, "--dry-run", "--reason", long_reason]) == 2
    source_reason_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in source_reason_err
    assert "reason exceeds 65536 bytes" in source_reason_err
    default_parent = tmp_path / "default-worktrees"
    default_parent.mkdir()
    monkeypatch.chdir(default_parent)
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", long_multibyte_display]) == 2
    exp_multibyte_name_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in exp_multibyte_name_err
    assert "experiment name exceeds 120 bytes" in exp_multibyte_name_err
    assert not list(default_parent.glob(f"{project_id}_exp-*"))
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", long_display]) == 2
    exp_name_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in exp_name_err
    assert "experiment name exceeds 120 bytes" in exp_name_err
    assert not list(default_parent.glob(f"{project_id}_exp-*"))
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "long-goal", "--goal", "g" * 65537]) == 2
    exp_goal_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in exp_goal_err
    assert "experiment goal exceeds 65536 bytes" in exp_goal_err
    assert not list(default_parent.glob(f"{project_id}_exp-*"))
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "tagged", "--tag", "a" * 65]) == 2
    create_tag_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in create_tag_err
    assert "tag exceeds 64 bytes" in create_tag_err
    assert not list(default_parent.glob(f"{project_id}_exp-*"))
    exact_worktree = tmp_path / "exact-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", exact_multibyte_display, "--goal", exact_multibyte_body, "--tag", exact_tag, "--path", str(exact_worktree)]) == 0
    exact_exp_out = capsys.readouterr().out
    assert _field_labels(exact_exp_out) == _exp_create_field_labels()
    exact_exp_id = _field(exact_exp_out, "exp id")
    assert f"experiment name: {exact_multibyte_display}" in exact_exp_out
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM experiment_tags WHERE exp_id = ? AND tag_slug = ?", (exact_exp_id, exact_tag)).fetchone()[0] == 1
    tagged_worktree = tmp_path / "tagged"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "tagged", "--path", str(tagged_worktree)]) == 0
    tagged_exp_out = capsys.readouterr().out
    assert _field_labels(tagged_exp_out) == _exp_create_field_labels()
    tagged_exp_id = _field(tagged_exp_out, "exp id")
    assert run(["--home", str(home), "--key", admin_key, "exp", "worktree", "remove", tagged_exp_id, "--project", project_id, "--dry-run", "--reason", "one", "--reason", "two"]) == 2
    duplicate_worktree_reason_err = capsys.readouterr().err
    assert _field_labels(duplicate_worktree_reason_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_worktree_reason_err
    assert "--reason may be provided once" in duplicate_worktree_reason_err
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "exp", "worktree", "remove", tagged_exp_id, "--project", project_id, "--dry-run", "--dry-run"], "--dry-run", capsys)
    assert _audit_count(home, "remove", "worktree", tagged_exp_id) == 0
    assert run(["--home", str(home), "--key", admin_key, "exp", "worktree", "remove", tagged_exp_id, "--project", project_id, "--dry-run", "--reason", long_reason]) == 2
    worktree_reason_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in worktree_reason_err
    assert "reason exceeds 65536 bytes" in worktree_reason_err
    assert run(["--home", str(home), "--key", admin_key, "exp", "tag", "add", tagged_exp_id, "a" * 65, "--project", project_id]) == 2
    tag_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in tag_err
    assert "tag exceeds 64 bytes" in tag_err
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "secret_env.API_TOKEN", '"abcd"', "--project", project_id]) == 2
    secret_env_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in secret_env_err
    assert "secret_env changes must use project secret" in secret_env_err


def test_invalid_runtime_config_preserves_previous_active_valid_config(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("print('baseline')\n", encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Active Valid Preserve Project"
task = "Keep previous active config for observe"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert (
        run(
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
        == 0
    )
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    token_status_worktree = tmp_path / "token-status-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "token-status",
                "--path",
                str(token_status_worktree),
            ]
        )
        == 0
    )
    token_status_out = capsys.readouterr().out
    explicit_token = Path(_field(token_status_out, "token path")).read_text(encoding="utf-8").strip()
    with sqlite3.connect(home / "alab.db") as conn:
        active_before = conn.execute(
            "SELECT active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert active_before[0] == 1
    assert active_before[1] is not None

    failing_command = json.dumps([sys.executable, "-c", "import sys; sys.exit(7)"])
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "config",
                "set",
                "runner.command",
                failing_command,
                "--project",
                project_id,
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    skipped_out = capsys.readouterr().out
    assert _field_labels(skipped_out) == _project_config_set_field_labels()
    assert "validation status: skipped" in skipped_out
    assert "project status: invalid" in skipped_out
    skipped_version = int(_field(skipped_out, "latest attempted config version"))
    assert skipped_version == 2
    with sqlite3.connect(home / "alab.db") as conn:
        skipped_project = conn.execute(
            """
            SELECT status, latest_attempted_config_version, active_valid_config_version,
              active_validation_id
            FROM projects
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
    assert skipped_project == ("invalid", skipped_version, active_before[0], active_before[1])

    assert run(["--home", str(home), "status", "--project", project_id]) == 0
    public_invalid_status = capsys.readouterr().out
    assert _field_labels(public_invalid_status) == ["object", "context type", "project id", "project status", "next"]
    assert "project status: invalid" in public_invalid_status
    assert f"next: alab project validate --project {project_id} --key <root-or-admin-key>" in public_invalid_status
    assert "task:" not in public_invalid_status
    assert "Project Validation Edges" not in public_invalid_status

    with monkeypatch.context() as ambient_context:
        ambient_context.setenv("ALAB_KEY", admin_key)
        assert run(["--home", str(home), "status", "--project", project_id]) == 0
    ambient_invalid_status = capsys.readouterr().out
    assert _field_labels(ambient_invalid_status) == ["object", "context type", "project id", "project status", "next"]
    assert "project status: invalid" in ambient_invalid_status
    assert "task:" not in ambient_invalid_status

    assert run(["--home", str(home), "--key", explicit_token, "status", "--project", project_id]) == 0
    token_invalid_status = capsys.readouterr().out
    assert _field_labels(token_invalid_status) == ["object", "context type", "project id", "project status", "next"]
    assert "project status: invalid" in token_invalid_status
    assert "task:" not in token_invalid_status

    with sqlite3.connect(home / "alab.db") as conn:
        project_context_path = Path(
            conn.execute("SELECT control_path FROM projects WHERE project_id = ?", (project_id,)).fetchone()[0]
        )
    with monkeypatch.context() as marker_context:
        marker_context.chdir(project_context_path)
        assert run(["--home", str(home), "status"]) == 0
    project_context_invalid_status = capsys.readouterr().out
    assert _field_labels(project_context_invalid_status) == ["object", "context type", "project id", "project status", "next"]
    assert "context type: project" in project_context_invalid_status
    assert "project status: invalid" in project_context_invalid_status
    assert f"next: alab project validate --project {project_id} --key <root-or-admin-key>" in project_context_invalid_status
    assert "task:" not in project_context_invalid_status

    assert (
        run(
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
                "--version",
                "active-valid",
            ]
        )
        == 0
    )
    active_show = capsys.readouterr().out
    assert f"config version: {active_before[0]}" in active_show

    blocked_worktree = tmp_path / "blocked-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "blocked",
                "--path",
                str(blocked_worktree),
            ]
        )
        == 4
    )
    blocked_err = capsys.readouterr().err
    assert "error code: COMMAND_UNAVAILABLE" in blocked_err
    assert "command is not available in the current context" in blocked_err
    assert not blocked_worktree.exists()

    with sqlite3.connect(home / "alab.db") as conn:
        validations_before_extra = conn.execute("SELECT COUNT(*) FROM project_validations WHERE project_id = ?", (project_id,)).fetchone()[0]
        project_before_extra = conn.execute(
            "SELECT status, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert run(["--home", str(home), "--key", admin_key, "project", "validate", "extra", "--project", project_id]) == 2
    extra_project_validate_err = capsys.readouterr().err
    assert _field_labels(extra_project_validate_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_project_validate_err
    assert "project validate accepts no positional arguments" in extra_project_validate_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM project_validations WHERE project_id = ?", (project_id,)).fetchone()[0] == validations_before_extra
        assert (
            conn.execute(
                "SELECT status, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            == project_before_extra
        )

    assert run(["--home", str(home), "--key", admin_key, "project", "validate", "--project", project_id]) == 1
    failed_validate = capsys.readouterr().out
    assert "validation status: failed" in failed_validate
    assert "project status: invalid" in failed_validate
    with sqlite3.connect(home / "alab.db") as conn:
        failed_project = conn.execute(
            "SELECT status, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert failed_project == ("invalid", active_before[0], active_before[1])


def test_global_option_contract_edges(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    other_home = tmp_path / "other-home"
    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")

    duplicate_global_cases = [
        (["--home", str(home), "--home", str(other_home), "config", "show"], "duplicate global option --home"),
        (["--home", str(home), "--output", "text", "--output", "rich", "config", "show"], "duplicate global option --output"),
        (["--home", str(home), "--key", root_key, "--key", root_key, "config", "show"], "duplicate global option --key"),
    ]
    for global_args, message in duplicate_global_cases:
        assert run(global_args) == 2
        duplicate_global_err = capsys.readouterr().err
        assert _field_labels(duplicate_global_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_global_err
        assert message in duplicate_global_err

    missing_global_value_cases = [
        (["--home"], "--home requires a value"),
        (["--output"], "--output requires a value"),
        (["--key"], "--key requires a value"),
    ]
    for global_args, message in missing_global_value_cases:
        assert run(global_args) == 2
        missing_global_err = capsys.readouterr().err
        assert _field_labels(missing_global_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in missing_global_err
        assert message in missing_global_err

    assert run(["--home", str(home), "--output", "json", "config", "show"]) == 2
    invalid_output_err = capsys.readouterr().err
    assert _field_labels(invalid_output_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in invalid_output_err
    assert "--output must be text or rich" in invalid_output_err

    invalid_key_stdin_values = ["", "\n", "not-a-single-line-key\nwith-extra-line\n", "not-a\0key", "key-with-extra-newline\n\n"]
    for value in invalid_key_stdin_values:
        monkeypatch.setattr(sys, "stdin", io.StringIO(value))
        assert run(["--home", str(home), "--key-stdin", "config", "show"]) == 2
        key_stdin_err = capsys.readouterr().err
        assert _field_labels(key_stdin_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in key_stdin_err
        assert "--key-stdin requires a non-empty single-line value" in key_stdin_err

    monkeypatch.setattr(sys, "stdin", io.StringIO(root_key + "\n"))
    assert run(["--home", str(home), "--key-stdin", "--key-stdin", "config", "show"]) == 2
    duplicate_key_stdin_err = capsys.readouterr().err
    assert _field_labels(duplicate_key_stdin_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_key_stdin_err
    assert "--key conflicts with --key-stdin" in duplicate_key_stdin_err

    monkeypatch.setattr(sys, "stdin", io.StringIO(root_key + "\n"))
    assert run(["--home", str(home), "--key-stdin", "--key", root_key, "config", "show"]) == 2
    err = capsys.readouterr().err
    assert _field_labels(err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in err
    assert "--key conflicts with --key-stdin" in err

    assert run(["--home", str(home), "config", "show", "--", "--home", str(other_home)]) == 0
    out = capsys.readouterr().out
    assert f"home: {home.resolve()}" in out
    assert str(other_home.resolve()) not in out

    monkeypatch.setattr(sys, "stdin", io.StringIO("not-a-single-line-key\nwith-extra-line\n"))
    assert run(["--home", str(home), "config", "show", "--", "--key-stdin"]) == 0
    stdin_stop_out = capsys.readouterr().out
    assert f"home: {home.resolve()}" in stdin_stop_out

    assert run(["--home", str(home), "--output", "rich", "config", "show"]) == 0
    rich_out = capsys.readouterr().out
    assert "object: config" in rich_out
    assert "output format: text" in rich_out
    assert run(["config", "show", "--home", str(home), "--output", "rich"]) == 0
    trailing_global_out = capsys.readouterr().out
    assert "object: config" in trailing_global_out
    assert f"home: {home.resolve()}" in trailing_global_out
    assert run(["config", "show", "--output", "json", "--home", str(home)]) == 2
    trailing_invalid_output_err = capsys.readouterr().err
    assert _field_labels(trailing_invalid_output_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in trailing_invalid_output_err
    assert "--output must be text or rich" in trailing_invalid_output_err
    assert run(["--home", str(home), "help", "--bogus"]) == 2
    help_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in help_err
    assert "invalid help option --bogus" in help_err
    assert run(["--home", str(home), "--help", "--bogus"]) == 2
    top_help_invalid_err = capsys.readouterr().err
    assert _field_labels(top_help_invalid_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in top_help_invalid_err
    assert "invalid help option --bogus" in top_help_invalid_err
    assert run(["--home", str(home), "help", "--all", "--all"]) == 2
    duplicate_help_err = capsys.readouterr().err
    assert _field_labels(duplicate_help_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_help_err
    assert "duplicate help option --all" in duplicate_help_err
    assert run(["--home", str(home), "--help", "--explain", "--explain"]) == 2
    top_help_duplicate_err = capsys.readouterr().err
    assert _field_labels(top_help_duplicate_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in top_help_duplicate_err
    assert "duplicate help option --explain" in top_help_duplicate_err
    assert run(["--home", str(home), "config", "show", "--help", "--help"]) == 2
    duplicate_help_flag_err = capsys.readouterr().err
    assert _field_labels(duplicate_help_flag_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_help_flag_err
    assert "duplicate help option --help" in duplicate_help_flag_err
    assert run(["--home", str(home), "config", "show", "--help", "--explain", "--explain"]) == 2
    duplicate_nested_help_err = capsys.readouterr().err
    assert _field_labels(duplicate_nested_help_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_nested_help_err
    assert "duplicate help option --explain" in duplicate_nested_help_err

    assert run(["--home", str(home), "config", "show", "--help"]) == 0
    help_out = capsys.readouterr().out
    assert re.findall(r"^command: (.+)$", help_out, re.MULTILINE) == ["config show"]
    assert _block_labels(help_out) == [
        ["object", "context type", "credential source", "credential scope", "project id", "exp id", "mode", "next"],
        ["object", "command", "available", "locked reason", "unlock hint", "capability source", "summary"],
    ]
    assert "available: true" in help_out
    assert run(["--home", str(home), "help"]) == 0
    top_help_out = capsys.readouterr().out
    top_help_commands = _commands(top_help_out)
    assert "help" in top_help_commands
    assert re.findall(r"^command: (.+)$", top_help_out, re.MULTILINE)[0] == "help"

    assert run(["--home", str(home), "--key", root_key, "audit", "list", "--created-after", "2026-01-01T00:00:00"]) == 2
    time_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in time_err
    assert "timestamps must include Z or a numeric offset" in time_err
    assert run(["--home", str(home), "--key", root_key, "audit", "list", "--created-after", "2026-01-01 00:00:00Z"]) == 2
    strict_time_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in strict_time_err
    assert "invalid RFC 3339 timestamp" in strict_time_err
    assert run(["--home", str(home), "--key", root_key, "audit", "list", "--created-after", "2000-01-01T00:00:00+08:00"]) == 0
    audit_out = capsys.readouterr()
    assert audit_out.err == ""


def test_capability_help_and_preflight_surfaces(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    source.mkdir()
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Capability Project"
task = "Exercise capability surfaces"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert (
        run(
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
        == 0
    )
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    control_path = home / "project-workspaces" / project_id

    monkeypatch.chdir(control_path)
    assert run(["--home", str(home), "help"]) == 0
    project_commands = _commands(capsys.readouterr().out)
    assert {"status", "exp create"}.issubset(project_commands)
    assert "project config show" not in project_commands
    assert "runs list" not in project_commands
    assert "cache prune" not in project_commands
    assert run(["--home", str(home), "help", "--all", "--explain"]) == 0
    all_help = capsys.readouterr().out
    all_availability = re.findall(r"^available: (true|false)$", all_help, re.MULTILINE)
    first_locked = all_availability.index("false")
    assert "true" not in all_availability[first_locked:]
    assert "locked reason: project admin or root credential required" in all_help
    assert "unlock hint: pass --key or --key-stdin" in all_help
    assert "capability source: public-project" in all_help

    monkeypatch.setenv("ALAB_KEY", admin_key)
    assert run(["--home", str(home), "help"]) == 0
    ambient_project_commands = _commands(capsys.readouterr().out)
    assert "project config show" not in ambient_project_commands
    assert run(["--home", str(home), "project", "config", "show"]) == 4
    ambient_err = capsys.readouterr().err
    assert _field_labels(ambient_err) == _error_field_labels()
    assert "error code: COMMAND_UNAVAILABLE" in ambient_err
    monkeypatch.delenv("ALAB_KEY")

    assert run(["--home", str(home), "--key", admin_key, "help"]) == 0
    explicit_admin_commands = _commands(capsys.readouterr().out)
    assert "project config show" in explicit_admin_commands
    assert "cache prune" not in explicit_admin_commands
    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id]) == 2
    assert "error code: CONFIG_INVALID" in capsys.readouterr().err
    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id, "--dry-run", "--apply"]) == 2
    assert "error code: CONFIG_INVALID" in capsys.readouterr().err
    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id, "--dry-run"]) == 0
    assert "dry run: true" in capsys.readouterr().out

    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--help"]) == 0
    public_exp_help = capsys.readouterr().out
    assert re.findall(r"^command: (.+)$", public_exp_help, re.MULTILINE) == ["exp create"]
    assert "available: true" in public_exp_help

    with sqlite3.connect(home / "alab.db") as conn:
        _wrong_admin_id, wrong_admin_key = services.create_credential(
            conn,
            credential_type="admin",
            project_id=f"{project_id}-other",
        )
    wrong_admin_public_worktree = tmp_path / "wrong-admin-public-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                wrong_admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "wrong-admin-public",
                "--path",
                str(wrong_admin_public_worktree),
            ]
        )
        == 0
    )
    wrong_admin_public_out = capsys.readouterr().out
    assert _field_labels(wrong_admin_public_out) == _exp_create_field_labels()
    assert wrong_admin_public_worktree.exists()

    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "project.allow_public_exp_create", "false", "--project", project_id]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "help"]) == 0
    public_disabled_commands = _commands(capsys.readouterr().out)
    assert "status" in public_disabled_commands
    assert "exp create" not in public_disabled_commands
    disabled_public_worktree = tmp_path / "disabled-public-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "disabled-public",
                "--path",
                str(disabled_public_worktree),
            ]
        )
        == 4
    )
    disabled_public_err = capsys.readouterr().err
    assert _field_labels(disabled_public_err) == _error_field_labels()
    assert "error code: COMMAND_UNAVAILABLE" in disabled_public_err
    assert not disabled_public_worktree.exists()
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "disabled-public",
                "--path",
                str(disabled_public_worktree),
                "--help",
                "--explain",
            ]
        )
        == 0
    )
    disabled_public_help = capsys.readouterr().out
    assert re.findall(r"^command: (.+)$", disabled_public_help, re.MULTILINE) == ["exp create"]
    assert "available: false" in disabled_public_help
    assert "locked reason: project admin or root credential required" in disabled_public_help
    assert "capability source: pass --key or --key-stdin" in disabled_public_help
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "project.allow_public_exp_create", "true", "--project", project_id]) == 0
    capsys.readouterr()

    missing_secret_file = tmp_path / "missing-secret.txt"
    assert (
        run(
            [
                "--home",
                str(home),
                "project",
                "secret",
                "set",
                "BLOCKED_SECRET",
                "--project",
                project_id,
                "--value-file",
                str(missing_secret_file),
                "--help",
            ]
        )
        == 0
    )
    blocked_secret_help = capsys.readouterr().out
    assert re.findall(r"^command: (.+)$", blocked_secret_help, re.MULTILINE) == ["project secret set"]
    assert "available: false" in blocked_secret_help

    assert run(["--home", str(home), "exp", "create", "--name", "cap-one"]) == 0
    exp_out = capsys.readouterr().out
    worktree_path = Path(_field(exp_out, "worktree path"))
    second_worktree = tmp_path / "second-worktree"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "cap-two", "--path", str(second_worktree)]) == 0
    second_exp_id = _field(capsys.readouterr().out, "exp id")
    monkeypatch.chdir(worktree_path)
    assert run(["--home", str(home), "help"]) == 0
    experiment_commands = _commands(capsys.readouterr().out)
    assert {"run", "submit", "runs list", "runs archive", "annotate add", "exp tag add", "exp checkout"}.issubset(experiment_commands)
    assert "project config show" not in experiment_commands
    assert "exp worktree remove" not in experiment_commands
    assert "key list" not in experiment_commands
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "nested-default"]) == 4
    nested_err = capsys.readouterr().err
    assert _field_labels(nested_err) == _error_field_labels()
    assert "error code: CONTEXT_CONFLICT" in nested_err

    inspection_path = tmp_path / "inspection"
    assert run(["--home", str(home), "exp", "checkout", second_exp_id, "--path", str(inspection_path)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(inspection_path)
    assert run(["--home", str(home), "help"]) == 0
    inspection_commands = _commands(capsys.readouterr().out)
    assert {"runs list", "logs export", "exp checkout remove"}.issubset(inspection_commands)
    assert "run" not in inspection_commands
    assert "submit" not in inspection_commands
    assert "exp tag add" not in inspection_commands
    assert "annotate add" not in inspection_commands
    assert "runs archive" not in inspection_commands
    assert run(["--home", str(home), "exp", "tag", "add", second_exp_id, "inspection-blocked"]) == 4
    inspection_tag_err = capsys.readouterr().err
    assert _field_labels(inspection_tag_err) == _error_field_labels()
    assert "error code: COMMAND_UNAVAILABLE" in inspection_tag_err
    assert run(["--home", str(home), "runs", "archive", "run-missing"]) == 4
    inspection_err = capsys.readouterr().err
    assert _field_labels(inspection_err) == _error_field_labels()
    assert "error code: COMMAND_UNAVAILABLE" in inspection_err

    missing_summary_file = tmp_path / "missing-summary.txt"
    missing_feedback_file = tmp_path / "missing-feedback.txt"
    assert (
        run(
            [
                "--home",
                str(home),
                "submit",
                "--message",
                "blocked inspection submit",
                "--summary-file",
                str(missing_summary_file),
                "--feedback-file",
                str(missing_feedback_file),
                "--ref",
                "none",
            ]
        )
        == 4
    )
    submit_err = capsys.readouterr().err
    assert _field_labels(submit_err) == _error_field_labels()
    assert "error code: COMMAND_UNAVAILABLE" in submit_err
    assert "No such file" not in submit_err

    missing_annotation_file = tmp_path / "missing-annotation.md"
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{second_exp_id}", "--body-file", str(missing_annotation_file)]) == 4
    annotation_err = capsys.readouterr().err
    assert _field_labels(annotation_err) == _error_field_labels()
    assert "error code: COMMAND_UNAVAILABLE" in annotation_err
    assert "No such file" not in annotation_err


def test_project_secret_input_contract(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    source.mkdir()
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Secret Input Project"
task = "Validate secret inputs"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert (
        run(
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
        == 0
    )
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    control_path = home / "project-workspaces" / project_id

    monkeypatch.setattr(sys, "stdin", io.StringIO("valid-secret\n"))
    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "set", "--project", project_id, "API_TOKEN", "--value-stdin"]) == 0
    valid_out = capsys.readouterr().out
    assert "secret name: API_TOKEN" in valid_out
    assert "secret fingerprint:" in valid_out
    assert "valid-secret" not in valid_out
    secret_fingerprint = _field(valid_out, "secret fingerprint")

    with sqlite3.connect(home / "alab.db") as conn:
        conn.row_factory = sqlite3.Row
        project_row = conn.execute(
            "SELECT secret_fingerprint_key, latest_attempted_config_version FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        secret_row = conn.execute(
            "SELECT secret_value_id, name, value, fingerprint FROM secret_values WHERE project_id = ? AND name = ?",
            (project_id, "API_TOKEN"),
        ).fetchone()
        cfg_row = conn.execute(
            "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?",
            (project_id, project_row["latest_attempted_config_version"]),
        ).fetchone()
    expected_fingerprint = "hmac-sha256:" + hmac.new(
        bytes(project_row["secret_fingerprint_key"]),
        b"API_TOKEN\0valid-secret",
        hashlib.sha256,
    ).hexdigest()
    same_value_other_name = "hmac-sha256:" + hmac.new(
        bytes(project_row["secret_fingerprint_key"]),
        b"OTHER_TOKEN\0valid-secret",
        hashlib.sha256,
    ).hexdigest()
    same_name_other_value = "hmac-sha256:" + hmac.new(
        bytes(project_row["secret_fingerprint_key"]),
        b"API_TOKEN\0other-secret",
        hashlib.sha256,
    ).hexdigest()
    config_secret_marker = json.loads(cfg_row["canonical_config_json"])["secret_env"]["API_TOKEN"]

    assert secret_row["name"] == "API_TOKEN"
    assert secret_row["value"] == "valid-secret"
    assert secret_row["fingerprint"] == secret_fingerprint == expected_fingerprint
    assert secret_fingerprint != same_value_other_name
    assert secret_fingerprint != same_name_other_value
    assert config_secret_marker == {"fingerprint": secret_fingerprint, "secret_value_id": secret_row["secret_value_id"]}

    first_secret_file = tmp_path / "first.secret"
    second_secret_file = tmp_path / "second.secret"
    first_secret_file.write_text("first-secret\n", encoding="utf-8")
    second_secret_file.write_text("second-secret\n", encoding="utf-8")
    with sqlite3.connect(home / "alab.db") as conn:
        before_duplicate_input_secret_count = conn.execute(
            "SELECT COUNT(*) FROM secret_values WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        before_duplicate_input_config_count = conn.execute(
            "SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        before_duplicate_input_audit_count = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]

    duplicate_input_cases = [
        (
            [
                "--value-file",
                str(first_secret_file),
                "--value-file",
                str(second_secret_file),
            ],
            "--value-file may be provided once",
        ),
        (
            [
                "--value-stdin",
                "--value-stdin",
            ],
            "--value-stdin may be provided once",
        ),
    ]
    for idx, (input_args, message) in enumerate(duplicate_input_cases):
        monkeypatch.setattr(sys, "stdin", io.StringIO("stdin-secret\n"))
        assert (
            run(
                [
                    "--home",
                    str(home),
                    "--key",
                    admin_key,
                    "project",
                    "secret",
                    "set",
                    "--project",
                    project_id,
                    f"DUPLICATE_INPUT_{idx}",
                    *input_args,
                ]
            )
            == 2
        )
        duplicate_input_err = capsys.readouterr().err
        assert _field_labels(duplicate_input_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_input_err
        assert message in duplicate_input_err

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "secret",
                "set",
                "--project",
                project_id,
                "DUPLICATE_DRY_RUN",
                "--value-file",
                str(first_secret_file),
                "--dry-run",
                "--dry-run",
            ]
        )
        == 2
    )
    duplicate_dry_run_err = capsys.readouterr().err
    assert _field_labels(duplicate_dry_run_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_dry_run_err
    assert "--dry-run may be provided once" in duplicate_dry_run_err
    unsupported_import_path = tmp_path / "unsupported-import.toml"
    unsupported_project_config_cases = [
        (
            ["project", "config", "set", "--project", project_id, "project.name", '"Ignored"', "--reason", "ignored"],
            "unsupported option --reason",
        ),
        (
            ["project", "config", "import", "--project", project_id, "--config", str(unsupported_import_path), "--reason", "ignored"],
            "unsupported option --reason",
        ),
        (
            ["project", "env", "set", "--project", project_id, "UNSUPPORTED_ENV", "value", "--reason", "ignored"],
            "unsupported option --reason",
        ),
        (
            ["project", "env", "unset", "--project", project_id, "UNSUPPORTED_ENV", "--reason", "ignored"],
            "unsupported option --reason",
        ),
        (
            ["project", "secret", "set", "--project", project_id, "UNSUPPORTED_SECRET", "--value-stdin", "--reason", "ignored"],
            "unsupported option --reason",
        ),
        (
            ["project", "secret", "unset", "--project", project_id, "API_TOKEN", "--reason", "ignored"],
            "unsupported option --reason",
        ),
    ]
    for command_args, message in unsupported_project_config_cases:
        monkeypatch.setattr(sys, "stdin", io.StringIO("unsupported-secret\n"))
        assert run(["--home", str(home), "--key", admin_key, *command_args]) == 2
        unsupported_project_config_err = capsys.readouterr().err
        assert _field_labels(unsupported_project_config_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in unsupported_project_config_err
        assert message in unsupported_project_config_err
    assert not unsupported_import_path.exists()
    fixed_positional_cases = [
        (
            ["project", "config", "set", "--project", project_id, "project.name", '"Renamed"', "extra"],
            "project config set requires field and TOML literal",
        ),
        (
            ["project", "config", "show", "--project", project_id, "extra"],
            "project config show accepts no positional arguments",
        ),
        (
            ["project", "env", "list", "--project", project_id, "extra"],
            "project env list accepts no positional arguments",
        ),
        (
            ["project", "env", "set", "--project", project_id, "EXTRA_ENV", "value", "extra"],
            "project env set requires name and value",
        ),
        (
            ["project", "env", "unset", "--project", project_id, "EXTRA_ENV", "extra"],
            "project env unset requires name",
        ),
        (
            ["project", "secret", "set", "--project", project_id, "EXTRA_SECRET", "extra", "--value-stdin"],
            "project secret set requires name",
        ),
        (
            ["project", "secret", "list", "--project", project_id, "extra"],
            "project secret list accepts no positional arguments",
        ),
        (
            ["project", "secret", "unset", "--project", project_id, "API_TOKEN", "extra"],
            "project secret unset requires name",
        ),
    ]
    for command_args, message in fixed_positional_cases:
        monkeypatch.setattr(sys, "stdin", io.StringIO("extra-secret\n"))
        assert run(["--home", str(home), "--key", admin_key, *command_args]) == 2
        extra_positional_err = capsys.readouterr().err
        assert _field_labels(extra_positional_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in extra_positional_err
        assert message in extra_positional_err

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM secret_values WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_input_secret_count
        assert conn.execute(
            "SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_input_config_count
        assert conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_input_audit_count

    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "list", "--project", project_id]) == 0
    secret_list_out = capsys.readouterr().out
    assert "secret name: API_TOKEN" in secret_list_out
    assert f"secret fingerprint: {secret_fingerprint}" in secret_list_out
    assert "valid-secret" not in secret_list_out

    assert run(["--home", str(home), "--key", admin_key, "project", "config", "show", "--project", project_id]) == 0
    config_show_out = capsys.readouterr().out
    assert "secret name: API_TOKEN" in config_show_out
    assert f"secret fingerprint: {secret_fingerprint}" in config_show_out
    assert "valid-secret" not in config_show_out
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "show", "--project", project_id, "--version", "latest-attempted", "--version", "active-valid"]) == 2
    duplicate_version_err = capsys.readouterr().err
    assert _field_labels(duplicate_version_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_version_err
    assert "--version may be provided once" in duplicate_version_err
    for invalid_version in ("0", "-1"):
        assert (
            run(
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
                    "--version",
                    invalid_version,
                ]
            )
            == 2
        )
        invalid_version_err = capsys.readouterr().err
        assert _field_labels(invalid_version_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in invalid_version_err
        assert "invalid config version selector" in invalid_version_err
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "show", "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_config_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_config_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_config_show_err
    assert "unsupported option --reason" in unsupported_config_show_err

    export_path = tmp_path / "secret-retain.toml"
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "export", "--project", project_id, "--out", str(export_path)]) == 0
    capsys.readouterr()
    export_text = export_path.read_text(encoding="utf-8")
    assert "valid-secret" not in export_text
    assert "secret_value_id" not in export_text
    assert "retain = true" in export_text
    assert secret_fingerprint in export_text
    unsupported_export_path = tmp_path / "unsupported-export.toml"
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "export", "--project", project_id, "--out", str(unsupported_export_path), "--reason", "ignored"]) == 2
    unsupported_export_err = capsys.readouterr().err
    assert _field_labels(unsupported_export_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_export_err
    assert "unsupported option --reason" in unsupported_export_err
    assert not unsupported_export_path.exists()
    duplicate_export_a = tmp_path / "duplicate-export-a.toml"
    duplicate_export_b = tmp_path / "duplicate-export-b.toml"
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "export", "--project", project_id, "--out", str(duplicate_export_a), "--out", str(duplicate_export_b)]) == 2
    duplicate_out_err = capsys.readouterr().err
    assert _field_labels(duplicate_out_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_out_err
    assert "--out may be provided once" in duplicate_out_err
    assert not duplicate_export_a.exists()
    assert not duplicate_export_b.exists()
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "export", "--project", project_id, "--out", str(export_path), "--overwrite", "--overwrite"]) == 2
    duplicate_overwrite_err = capsys.readouterr().err
    assert _field_labels(duplicate_overwrite_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_overwrite_err
    assert "--overwrite may be provided once" in duplicate_overwrite_err
    assert export_path.read_text(encoding="utf-8") == export_text
    extra_export_path = tmp_path / "extra-export.toml"
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "export", "extra", "--project", project_id, "--out", str(extra_export_path)]) == 2
    extra_export_err = capsys.readouterr().err
    assert _field_labels(extra_export_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_export_err
    assert "project config export accepts no positional arguments" in extra_export_err
    assert not extra_export_path.exists()

    renamed_retain_path = tmp_path / "renamed-secret-retain.toml"
    renamed_retain_path.write_text(export_text.replace("API_TOKEN", "OTHER_TOKEN"), encoding="utf-8")
    with sqlite3.connect(home / "alab.db") as conn:
        before_duplicate_config_import_versions = conn.execute(
            "SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        before_duplicate_config_import_audits = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    missing_import_path = tmp_path / "missing-import.toml"
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "import", "extra", "--project", project_id, "--config", str(missing_import_path)]) == 2
    extra_import_err = capsys.readouterr().err
    assert _field_labels(extra_import_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_import_err
    assert "project config import accepts no positional arguments" in extra_import_err
    assert not missing_import_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_config_import_versions
        assert conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_config_import_audits
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "import", "--project", project_id, "--config", str(renamed_retain_path), "--config", str(export_path)]) == 2
    duplicate_config_import_err = capsys.readouterr().err
    assert _field_labels(duplicate_config_import_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_config_import_err
    assert "--config may be provided once" in duplicate_config_import_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_config_import_versions
        assert conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_config_import_audits
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "import", "--project", project_id, "--config", str(renamed_retain_path)]) == 2
    renamed_retain_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in renamed_retain_err
    assert "secret_env.OTHER_TOKEN retain marker has no previous secret value" in renamed_retain_err

    mismatched_retain_path = tmp_path / "mismatched-secret-retain.toml"
    mismatched_retain_path.write_text(export_text.replace(secret_fingerprint, same_name_other_value), encoding="utf-8")
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "import", "--project", project_id, "--config", str(mismatched_retain_path), "--dry-run"]) == 2
    mismatched_retain_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in mismatched_retain_err
    assert "secret_env.API_TOKEN retain marker fingerprint does not match" in mismatched_retain_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM project_config_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_config_import_versions
        assert conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_config_import_audits

    orphan_secret_id = "sec-orphan-AAAAAAAAAAAAAAAAAAAAAA"
    orphan_fingerprint = "hmac-sha256:" + "0" * 64
    with sqlite3.connect(home / "alab.db") as conn:
        audit_count_before_gc = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO secret_values(secret_value_id, project_id, name, value, fingerprint, created_at, created_by_credential_id, replaced_at)
            VALUES (?, ?, 'ORPHAN_TOKEN', 'orphan-secret', ?, '2026-05-19T00:00:00Z', NULL, NULL)
            """,
            (orphan_secret_id, project_id, orphan_fingerprint),
        )

    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id, "--dry-run"]) == 0
    secret_gc_dry_run = capsys.readouterr().out
    assert _field_labels(secret_gc_dry_run) == ["object", "project id", "dry run", "deleted count", "secret value id", "audit id"]
    assert "dry run: true" in secret_gc_dry_run
    assert "deleted count: 1" in secret_gc_dry_run
    assert f"secret value id: {orphan_secret_id}" in secret_gc_dry_run
    assert "ORPHAN_TOKEN" not in secret_gc_dry_run
    assert "orphan-secret" not in secret_gc_dry_run
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT value FROM secret_values WHERE secret_value_id = ?",
            (orphan_secret_id,),
        ).fetchone()[0] == "orphan-secret"
        assert conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == audit_count_before_gc

    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id, "--apply", "--apply"]) == 2
    duplicate_secret_gc_apply_err = capsys.readouterr().err
    assert _field_labels(duplicate_secret_gc_apply_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_secret_gc_apply_err
    assert "--apply may be provided once" in duplicate_secret_gc_apply_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT value FROM secret_values WHERE secret_value_id = ?",
            (orphan_secret_id,),
        ).fetchone()[0] == "orphan-secret"
        assert conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == audit_count_before_gc

    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id, "--dry-run", "--dry-run"]) == 2
    duplicate_secret_gc_dry_run_err = capsys.readouterr().err
    assert _field_labels(duplicate_secret_gc_dry_run_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_secret_gc_dry_run_err
    assert "--dry-run may be provided once" in duplicate_secret_gc_dry_run_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT value FROM secret_values WHERE secret_value_id = ?",
            (orphan_secret_id,),
        ).fetchone()[0] == "orphan-secret"
        assert conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == audit_count_before_gc

    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "gc", "extra", "--project", project_id, "--apply"]) == 2
    extra_secret_gc_err = capsys.readouterr().err
    assert _field_labels(extra_secret_gc_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_secret_gc_err
    assert "project secret gc accepts no positional arguments" in extra_secret_gc_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT value FROM secret_values WHERE secret_value_id = ?",
            (orphan_secret_id,),
        ).fetchone()[0] == "orphan-secret"
        assert conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == audit_count_before_gc

    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id, "--apply"]) == 0
    secret_gc_apply = capsys.readouterr().out
    assert _field_labels(secret_gc_apply) == ["object", "project id", "dry run", "deleted count", "secret value id", "audit id"]
    assert "dry run: false" in secret_gc_apply
    assert "deleted count: 1" in secret_gc_apply
    secret_gc_audit_id = _field(secret_gc_apply, "audit id")
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM secret_values WHERE secret_value_id = ?",
            (orphan_secret_id,),
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT value FROM secret_values WHERE secret_value_id = ?",
            (secret_row["secret_value_id"],),
        ).fetchone()[0] == "valid-secret"
        audit_row = conn.execute(
            "SELECT action, object_type, object_id FROM audit_events WHERE audit_id = ?",
            (secret_gc_audit_id,),
        ).fetchone()
        assert audit_row == ("gc", "secret_value", project_id)

    invalid_stdin_values = ["\n", "abc\n", "valid\nsecret", "valid\0secret", "valid-secret\n\n"]
    for idx, value in enumerate(invalid_stdin_values):
        monkeypatch.setattr(sys, "stdin", io.StringIO(value))
        assert (
            run(
                [
                    "--home",
                    str(home),
                    "--key",
                    admin_key,
                    "project",
                    "secret",
                    "set",
                    "--project",
                    project_id,
                    f"BAD_STDIN_{idx}",
                    "--value-stdin",
                ]
            )
            == 2
        )
        err = capsys.readouterr().err
        assert "error code: CONFIG_INVALID" in err
        assert "secret value must be a single-line UTF-8 string at least 4 bytes" in err

    invalid_files = {
        "empty": "",
        "short": "abc\n",
        "newline": "valid\nsecret",
        "nul": "valid\0secret",
        "double-newline": "valid-secret\n\n",
    }
    for name, value in invalid_files.items():
        path = tmp_path / f"{name}.secret"
        path.write_text(value, encoding="utf-8")
        assert (
            run(
                [
                    "--home",
                    str(home),
                    "--key",
                    admin_key,
                    "project",
                    "secret",
                    "set",
                    "--project",
                    project_id,
                    f"BAD_FILE_{name.replace('-', '_').upper()}",
                    "--value-file",
                    str(path),
                ]
            )
            == 2
        )
        err = capsys.readouterr().err
        assert "error code: CONFIG_INVALID" in err

    missing_secret_file = tmp_path / "missing-secret.txt"
    secret_count_before_missing = _table_count(home, "secret_values")
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "secret",
                "set",
                "--project",
                project_id,
                "MISSING_FILE_SECRET",
                "--value-file",
                str(missing_secret_file),
            ]
        )
        == 2
    )
    missing_secret_err = capsys.readouterr().err
    assert _field_labels(missing_secret_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in missing_secret_err
    assert "secret value file not found" in missing_secret_err
    assert "No such file" not in missing_secret_err
    assert _table_count(home, "secret_values") == secret_count_before_missing

    monkeypatch.chdir(control_path)
    assert (
        run(
            [
                "--home",
                str(home),
                "project",
                "secret",
                "set",
                "BLOCKED_SECRET",
                "--value-file",
                str(missing_secret_file),
            ]
        )
        == 4
    )
    blocked_err = capsys.readouterr().err
    assert "error code: COMMAND_UNAVAILABLE" in blocked_err
    assert "No such file" not in blocked_err


def test_experiment_runs_keep_bound_secret_after_project_secret_change(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    old_worktree = tmp_path / "old-secret-exp"
    new_worktree = tmp_path / "new-secret-exp"
    config = tmp_path / "alab.bound-secret.toml"
    old_secret = "old-bound-secret"
    new_secret = "new-bound-secret"
    old_digest = hashlib.sha256(old_secret.encode("utf-8")).hexdigest()
    new_digest = hashlib.sha256(new_secret.encode("utf-8")).hexdigest()
    source.mkdir()
    (source / "main.py").write_text(
        f"""
import hashlib
import json
import os
from pathlib import Path

digest = hashlib.sha256(os.environ.get("API_TOKEN", "").encode("utf-8")).hexdigest()
reward = {{{old_digest!r}: 11.0, {new_digest!r}: 22.0}}.get(digest, -1.0)
Path(os.environ["ALAB_RUN_DIR"], "reward.json").write_text(json.dumps({{"reward": reward}}), encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Bound Secret Project"
task = "Keep experiment-bound secrets stable"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "file"
direction = "maximize"
primary_metric = "reward"
path = "run:reward.json"

[secret_env]
API_TOKEN = {json.dumps(old_secret)}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    assert "validation status: passed" in project_out
    assert old_secret not in project_out
    assert new_secret not in project_out

    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "legacy-binding", "--path", str(old_worktree)]) == 0
    old_exp_out = capsys.readouterr().out
    old_exp_id = _field(old_exp_out, "exp id")
    assert _field(old_exp_out, "config version") == "1"
    assert old_secret not in old_exp_out
    assert new_secret not in old_exp_out

    monkeypatch.setattr(sys, "stdin", io.StringIO(new_secret + "\n"))
    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "set", "--project", project_id, "API_TOKEN", "--value-stdin"]) == 0
    secret_set_out = capsys.readouterr().out
    new_config_version = int(_field(secret_set_out, "config version"))
    assert new_config_version == 2
    assert "validation status: passed" in secret_set_out
    assert old_secret not in secret_set_out
    assert new_secret not in secret_set_out

    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "current-binding", "--path", str(new_worktree)]) == 0
    new_exp_out = capsys.readouterr().out
    new_exp_id = _field(new_exp_out, "exp id")
    assert _field(new_exp_out, "config version") == str(new_config_version)
    assert old_secret not in new_exp_out
    assert new_secret not in new_exp_out

    monkeypatch.chdir(old_worktree)
    assert run(["--home", str(home), "run", "--message", "old secret still bound"]) == 0
    old_run_out = capsys.readouterr().out
    old_run_id = _field(old_run_out, "run id")
    assert float(_field(old_run_out, "reward")) == 11.0
    assert old_secret not in old_run_out
    assert new_secret not in old_run_out

    monkeypatch.chdir(new_worktree)
    assert run(["--home", str(home), "run", "--message", "new secret bound"]) == 0
    new_run_out = capsys.readouterr().out
    new_run_id = _field(new_run_out, "run id")
    assert float(_field(new_run_out, "reward")) == 22.0
    assert old_secret not in new_run_out
    assert new_secret not in new_run_out

    with sqlite3.connect(home / "alab.db") as conn:
        conn.row_factory = sqlite3.Row
        exp_rows = {
            row["exp_id"]: row
            for row in conn.execute(
                "SELECT exp_id, bound_config_version FROM experiments WHERE exp_id IN (?, ?)",
                (old_exp_id, new_exp_id),
            )
        }
        run_rows = {
            row["run_id"]: row
            for row in conn.execute(
                "SELECT run_id, exp_id, config_version, reward_value FROM runs WHERE run_id IN (?, ?)",
                (old_run_id, new_run_id),
            )
        }
        config_rows = {
            row["version"]: json.loads(row["canonical_config_json"])
            for row in conn.execute(
                "SELECT version, canonical_config_json FROM project_config_versions WHERE project_id = ? ORDER BY version",
                (project_id,),
            )
        }
        secret_values = {
            row["secret_value_id"]: row["value"]
            for row in conn.execute(
                "SELECT secret_value_id, value FROM secret_values WHERE project_id = ?",
                (project_id,),
            )
        }

    old_marker = config_rows[1]["secret_env"]["API_TOKEN"]
    new_marker = config_rows[new_config_version]["secret_env"]["API_TOKEN"]
    assert exp_rows[old_exp_id]["bound_config_version"] == 1
    assert exp_rows[new_exp_id]["bound_config_version"] == new_config_version
    assert run_rows[old_run_id]["exp_id"] == old_exp_id
    assert run_rows[new_run_id]["exp_id"] == new_exp_id
    assert run_rows[old_run_id]["config_version"] == 1
    assert run_rows[new_run_id]["config_version"] == new_config_version
    assert run_rows[old_run_id]["reward_value"] == 11.0
    assert run_rows[new_run_id]["reward_value"] == 22.0
    assert old_marker["secret_value_id"] != new_marker["secret_value_id"]
    assert secret_values[old_marker["secret_value_id"]] == old_secret
    assert secret_values[new_marker["secret_value_id"]] == new_secret


def test_stale_running_records_are_interrupted(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    config = tmp_path / "alab.project.toml"
    worktree = tmp_path / "worktree"
    source.mkdir()
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Stale Running Project"
task = "Interrupt stale records"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
command = [{json.dumps(sys.executable)}, "-c", "print('ok')"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "stale", "--path", str(worktree)]) == 0
    exp_out = capsys.readouterr().out
    exp_id = _field(exp_out, "exp id")
    commit = _git(["rev-parse", "HEAD"], worktree)
    stale_run_id = new_id("run", "stale-manual")
    stale_validation_id = new_id("val", "stale-manual")

    with sqlite3.connect(home / "alab.db") as conn:
        project = conn.execute(
            "SELECT active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        config_version = project[0]
        active_validation_id = project[1]
        source_row = conn.execute("SELECT source_ref, source_commit FROM sources WHERE project_id = ? LIMIT 1", (project_id,)).fetchone()
        conn.execute(
            """
            INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, exit_code,
              reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
            VALUES (?, ?, ?, ?, ?, 'running', NULL, NULL, 'not_attempted',
              'active', '2026-01-01T00:00:00Z', NULL, '{"schema_version":1}')
            """,
            (stale_run_id, exp_id, project_id, commit, config_version),
        )
        conn.execute(
            """
            INSERT INTO project_validations(validation_id, project_id, config_version, source_ref, source_commit,
              status, exit_code, reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
            VALUES (?, ?, ?, ?, ?, 'running', NULL, NULL, 'not_attempted',
              'active', '2026-01-01T00:00:00Z', NULL, '{"schema_version":1}')
            """,
            (stale_validation_id, project_id, config_version, source_row[0], source_row[1]),
        )
        conn.execute(
            "UPDATE project_config_versions SET validation_status = 'running' WHERE project_id = ? AND version = ?",
            (project_id, config_version),
        )
        conn.commit()

    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "status"]) == 0
    status_out = capsys.readouterr().out
    assert "project status: invalid" in status_out

    assert run(["--home", str(home), "runs", "list", "--status", "interrupted"]) == 0
    interrupted_runs_out = capsys.readouterr().out
    assert f"run id: {stale_run_id}" in interrupted_runs_out
    assert "run status: interrupted" in interrupted_runs_out
    assert "exit code: none" in interrupted_runs_out
    assert "reward: none" in interrupted_runs_out
    assert "reward parse status: not_attempted" in interrupted_runs_out
    assert "ended at: none" not in interrupted_runs_out
    assert run(["--home", str(home), "runs", "list", "--status", "running"]) == 0
    assert stale_run_id not in capsys.readouterr().out
    assert run(["--home", str(home), "runs", "list", "--failure-reason-query", "stale running run"]) == 0
    failure_query_out = capsys.readouterr().out
    assert f"run id: {stale_run_id}" in failure_query_out
    assert "run status: interrupted" in failure_query_out
    assert run(["--home", str(home), "runs", "show", stale_run_id]) == 0
    interrupted_run_show = capsys.readouterr().out
    assert _field(interrupted_run_show, "run id") == stale_run_id
    assert "run status: interrupted" in interrupted_run_show
    assert "hidden log available: false" in interrupted_run_show

    assert run(["--home", str(home), "--key", root_key, "project", "validation", "archive", stale_validation_id, "--project", project_id]) == 0
    validation_archive_out = capsys.readouterr().out
    assert _field_labels(validation_archive_out) == _validation_archive_field_labels()
    assert "previous archive status: active" in validation_archive_out
    assert "archive status: archived" in validation_archive_out

    with sqlite3.connect(home / "alab.db") as conn:
        run_status, run_ended_at, run_record = conn.execute("SELECT status, ended_at, record_json FROM runs WHERE run_id = ?", (stale_run_id,)).fetchone()
        validation_status, validation_record = conn.execute(
            "SELECT status, record_json FROM project_validations WHERE validation_id = ?",
            (stale_validation_id,),
        ).fetchone()
        validation_archive_status = conn.execute(
            "SELECT archive_status FROM project_validations WHERE validation_id = ?",
            (stale_validation_id,),
        ).fetchone()[0]
        config_status = conn.execute(
            "SELECT validation_status FROM project_config_versions WHERE project_id = ? AND version = ?",
            (project_id, config_version),
        ).fetchone()[0]
        project_status, active_version, active_validation = conn.execute(
            "SELECT status, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert run_status == "interrupted"
    assert run_ended_at is not None
    assert '"interrupted":true' in run_record
    interrupted_run_record = json.loads(run_record)
    assert interrupted_run_record["config_hash"].startswith("sha256:")
    assert interrupted_run_record["runner"] == {"type": "local"}
    assert interrupted_run_record["reward"] == {"type": "exit_code", "value": None}
    assert validation_status == "interrupted"
    assert validation_archive_status == "archived"
    assert '"interrupted":true' in validation_record
    interrupted_validation_record = json.loads(validation_record)
    assert interrupted_validation_record["config_hash"].startswith("sha256:")
    assert interrupted_validation_record["runner"] == {"type": "local"}
    assert interrupted_validation_record["reward"] == {"type": "exit_code", "value": None}
    assert config_status == "interrupted"
    assert project_status == "invalid"
    assert active_version == config_version
    assert active_validation == active_validation_id


def test_skydiscover_catalog_lifecycle(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    upstream.mkdir()
    _git(["init"], upstream)
    _git(["config", "user.name", "ALab Test"], upstream)
    _git(["config", "user.email", "alab@example.test"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    (upstream / "README.md").write_text("one\n", encoding="utf-8")
    _git(["add", "README.md"], upstream)
    _git(["commit", "-m", "one"], upstream)
    _git(["branch", "-M", "main"], upstream)
    first_commit = _git(["rev-parse", "HEAD"], upstream)

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    catalog_path = home / "sources" / "skydiscover"
    initial_catalog_entries = sorted(path.name for path in catalog_path.iterdir())

    duplicate_catalog_add_cases = [
        ["--origin-url", str(upstream), "--origin-url", str(upstream), "--ref", "main"],
        ["--origin-url", str(upstream), "--ref", "main", "--ref", "main"],
        ["--origin-url", str(upstream), "--commit", first_commit, "--commit", first_commit],
    ]
    for duplicate_add_args in duplicate_catalog_add_cases:
        assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", *duplicate_add_args]) == 2
        duplicate_add_err = capsys.readouterr().err
        assert _field_labels(duplicate_add_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_add_err
        assert "may be provided once" in duplicate_add_err
        assert sorted(path.name for path in catalog_path.iterdir()) == initial_catalog_entries
        with sqlite3.connect(home / "alab.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM catalogs WHERE catalog_key = 'skydiscover'").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE object_type = 'catalog'").fetchone()[0] == 0

    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "extra", "--origin-url", str(upstream), "--ref", "main"]) == 2
    extra_add_err = capsys.readouterr().err
    assert _field_labels(extra_add_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_add_err
    assert "catalog skydiscover add accepts no positional arguments" in extra_add_err
    assert sorted(path.name for path in catalog_path.iterdir()) == initial_catalog_entries
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM catalogs WHERE catalog_key = 'skydiscover'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE object_type = 'catalog'").fetchone()[0] == 0
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main", "--path", "ignored"]) == 2
    unsupported_add_err = capsys.readouterr().err
    assert _field_labels(unsupported_add_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_add_err
    assert "unsupported option --path" in unsupported_add_err
    assert sorted(path.name for path in catalog_path.iterdir()) == initial_catalog_entries
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM catalogs WHERE catalog_key = 'skydiscover'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE object_type = 'catalog'").fetchone()[0] == 0

    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
    add_out = capsys.readouterr().out
    assert _field_labels(add_out) == _catalog_change_field_labels()
    assert _field(add_out, "pinned commit") == first_commit

    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "show"]) == 0
    show_out = capsys.readouterr().out
    assert _field_labels(show_out) == _catalog_show_field_labels()
    assert first_commit in show_out
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "show", "extra"]) == 2
    extra_show_err = capsys.readouterr().err
    assert _field_labels(extra_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_show_err
    assert "catalog skydiscover show accepts no positional arguments" in extra_show_err
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "show", "--reason", "ignored"]) == 2
    unsupported_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_show_err
    assert "unsupported option --reason" in unsupported_show_err

    (upstream / "README.md").write_text("two\n", encoding="utf-8")
    _git(["add", "README.md"], upstream)
    _git(["commit", "-m", "two"], upstream)
    second_commit = _git(["rev-parse", "HEAD"], upstream)

    duplicate_catalog_update_cases = [
        ["--origin-url", str(upstream), "--origin-url", str(upstream), "--ref", "main"],
        ["--ref", "main", "--ref", "main"],
        ["--commit", second_commit, "--commit", second_commit],
    ]
    for duplicate_update_args in duplicate_catalog_update_cases:
        assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "update", *duplicate_update_args]) == 2
        duplicate_update_err = capsys.readouterr().err
        assert _field_labels(duplicate_update_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_update_err
        assert "may be provided once" in duplicate_update_err
        with sqlite3.connect(home / "alab.db") as conn:
            catalog_row = conn.execute("SELECT pinned_commit FROM catalogs WHERE catalog_key = 'skydiscover' AND status = 'active'").fetchone()
            assert catalog_row[0] == first_commit
            assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'update' AND object_type = 'catalog'").fetchone()[0] == 0

    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "update", "extra", "--ref", "main"]) == 2
    extra_update_err = capsys.readouterr().err
    assert _field_labels(extra_update_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_update_err
    assert "catalog skydiscover update accepts no positional arguments" in extra_update_err
    with sqlite3.connect(home / "alab.db") as conn:
        catalog_row = conn.execute("SELECT pinned_commit FROM catalogs WHERE catalog_key = 'skydiscover' AND status = 'active'").fetchone()
        assert catalog_row[0] == first_commit
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'update' AND object_type = 'catalog'").fetchone()[0] == 0
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "update", "--ref", "main", "--path", "ignored"]) == 2
    unsupported_update_err = capsys.readouterr().err
    assert _field_labels(unsupported_update_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_update_err
    assert "unsupported option --path" in unsupported_update_err
    with sqlite3.connect(home / "alab.db") as conn:
        catalog_row = conn.execute("SELECT pinned_commit FROM catalogs WHERE catalog_key = 'skydiscover' AND status = 'active'").fetchone()
        assert catalog_row[0] == first_commit
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'update' AND object_type = 'catalog'").fetchone()[0] == 0

    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "update", "--ref", "main"]) == 0
    update_out = capsys.readouterr().out
    assert _field_labels(update_out) == _catalog_change_field_labels()
    assert _field(update_out, "pinned commit") == second_commit

    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "remove", "--force", "--confirm", "skydiscover", "--reason", "x" * 65537]) == 2
    reason_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in reason_err
    assert "reason exceeds 65536 bytes" in reason_err
    assert catalog_path.exists()
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "show"]) == 0
    active_show_out = capsys.readouterr().out
    assert _field_labels(active_show_out) == _catalog_show_field_labels()
    assert "status: active" in active_show_out

    _assert_confirm_guard(
        ["--home", str(home), "--key", root_key, "catalog", "skydiscover", "remove"],
        "skydiscover",
        "catalog remove requires --force and --confirm skydiscover",
        capsys,
    )
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "remove", "extra", "--force", "--confirm", "skydiscover"]) == 2
    extra_remove_err = capsys.readouterr().err
    assert _field_labels(extra_remove_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_remove_err
    assert "catalog skydiscover remove accepts no positional arguments" in extra_remove_err
    assert catalog_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM catalogs WHERE catalog_key = 'skydiscover'").fetchone()[0] == "active"
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'remove' AND object_type = 'catalog'").fetchone()[0] == 0
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "remove", "--force", "--confirm", "skydiscover", "--path", "ignored"]) == 2
    unsupported_remove_err = capsys.readouterr().err
    assert _field_labels(unsupported_remove_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_remove_err
    assert "unsupported option --path" in unsupported_remove_err
    assert catalog_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM catalogs WHERE catalog_key = 'skydiscover'").fetchone()[0] == "active"
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'remove' AND object_type = 'catalog'").fetchone()[0] == 0
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "remove", "--force", "--confirm", "skydiscover"]) == 0
    remove_out = capsys.readouterr().out
    assert _field_labels(remove_out) == _catalog_remove_field_labels()
    assert "removed: true" in remove_out


def test_skydiscover_catalog_ref_validation(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    source = tmp_path / "source"
    upstream.mkdir()
    source.mkdir()
    evaluator = upstream / "benchmarks" / "demo"
    evaluator.mkdir(parents=True)
    (evaluator / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (evaluator / "evaluate.sh").write_text("#!/bin/sh\nprintf '{\"combined_score\":1}'\n", encoding="utf-8")
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    _git(["init"], upstream)
    _git(["config", "user.name", "ALab Test"], upstream)
    _git(["config", "user.email", "alab@example.test"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    _git(["add", "."], upstream)
    _git(["commit", "-m", "catalog"], upstream)
    _git(["branch", "-M", "main"], upstream)
    first_commit = _git(["rev-parse", "HEAD"], upstream)

    config = tmp_path / "alab.skydiscover.toml"
    config.write_text(
        """
schema_version = 1

[project]
name = "SkyDiscover Ref Project"
task = "Validate catalog refs"

[runner]
type = "skydiscover_docker"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/demo"

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    future_config = tmp_path / "alab.skydiscover-future.toml"
    future_config.write_text(config.read_text(encoding="utf-8").replace("benchmarks/demo", "benchmarks/future"), encoding="utf-8")

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
    capsys.readouterr()

    future_evaluator = upstream / "benchmarks" / "future"
    future_evaluator.mkdir()
    (future_evaluator / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (future_evaluator / "evaluate.sh").write_text("#!/bin/sh\nprintf '{\"combined_score\":2}'\n", encoding="utf-8")
    _git(["add", "."], upstream)
    _git(["commit", "-m", "future evaluator"], upstream)
    second_commit = _git(["rev-parse", "HEAD"], upstream)

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "--config",
                str(future_config),
                "--source-path",
                str(source),
                "--skip-baseline-test",
            ]
        )
        == 2
    )
    assert "SkyDiscover catalog ref target does not exist" in capsys.readouterr().err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT pinned_commit FROM catalogs WHERE catalog_key = 'skydiscover'").fetchone()[0] == first_commit

    dirty_file = home / "sources" / "skydiscover" / "local-only.txt"
    dirty_file.write_text("dirty\n", encoding="utf-8")
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "update", "--ref", "main"]) == 2
    dirty_update_err = capsys.readouterr().err
    assert _field_labels(dirty_update_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in dirty_update_err
    assert "catalog has non-ALab modifications" in dirty_update_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT pinned_commit FROM catalogs WHERE catalog_key = 'skydiscover'").fetchone()[0] == first_commit
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'update' AND object_type = 'catalog'").fetchone()[0] == 0
    dirty_file.unlink()

    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "update", "--ref", "main"]) == 0
    update_out = capsys.readouterr().out
    assert _field_labels(update_out) == _catalog_change_field_labels()
    assert _field(update_out, "pinned commit") == second_commit

    assert (
        run(
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
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "validation status: skipped" in project_out


def test_skydiscover_catalog_remove_blockers_unexpected_remote_and_history(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    benchmark = upstream / "benchmarks" / "history-demo"
    exp_path = tmp_path / "history-exp"
    benchmark.mkdir(parents=True)
    (benchmark / "evaluator.py").write_text(
        """
def evaluate(program_path):
    print("hidden history evaluator stdout")
    return {"metrics": {"combined_score": 3.25}, "feedback": {"note": "history feedback"}}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    _git(["init"], upstream)
    _git(["config", "user.name", "ALab Test"], upstream)
    _git(["config", "user.email", "alab@example.test"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    _git(["add", "."], upstream)
    _git(["commit", "-m", "catalog"], upstream)
    _git(["branch", "-M", "main"], upstream)
    config = tmp_path / "alab.skydiscover-history.toml"
    config.write_text(
        """
schema_version = 1

[project]
name = "SkyDiscover History Project"
task = "Keep catalog-independent history"

[runner]
type = "skydiscover_python"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/history-demo"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    root_credential_id = root_key.removeprefix("alab_root_v1_").rpartition("_")[0]
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
    capsys.readouterr()
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
            ]
        )
        == 0
    )
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "remove", "--force", "--confirm", "skydiscover"]) == 4
    active_config_err = capsys.readouterr().err
    assert _field_labels(active_config_err) == _error_field_labels()
    assert "error code: RESOURCE_BUSY" in active_config_err
    assert f"active_config:{project_id}:1" in active_config_err
    assert (home / "sources" / "skydiscover").exists()
    assert _audit_count(home, "remove", "catalog", "skydiscover") == 0

    assert run(["--home", str(home), "--key", admin_key, "exp", "create", "--project", project_id, "--name", "History", "--path", str(exp_path)]) == 0
    exp_out = capsys.readouterr().out
    exp_id = _field(exp_out, "exp id")
    monkeypatch.chdir(exp_path)
    assert run(["--home", str(home), "run", "--message", "history"]) == 0
    run_out = capsys.readouterr().out
    run_id = _field(run_out, "run id")
    assert "run status: passed" in run_out
    assert "reward: 3.25" in run_out

    assert run(["--home", str(home), "--key", admin_key, "project", "archive", "--project", project_id]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "remove", "--force", "--confirm", "skydiscover"]) == 4
    open_exp_err = capsys.readouterr().err
    assert _field_labels(open_exp_err) == _error_field_labels()
    assert "error code: RESOURCE_BUSY" in open_exp_err
    assert f"open_experiment:{exp_id}" in open_exp_err
    assert "active_config:" not in open_exp_err
    assert _audit_count(home, "remove", "catalog", "skydiscover") == 0

    catalog_path = home / "sources" / "skydiscover"
    _git(["remote", "set-url", "origin", str(tmp_path / "unexpected-upstream")], catalog_path)
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "update", "--ref", "main"]) == 2
    remote_err = capsys.readouterr().err
    assert _field_labels(remote_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in remote_err
    assert "catalog has unexpected origin remote" in remote_err
    assert _audit_count(home, "update", "catalog", "skydiscover") == 0
    _git(["remote", "set-url", "origin", str(upstream)], catalog_path)

    assert run(["--home", str(home), "--key", admin_key, "exp", "archive", exp_id, "--project", project_id]) == 0
    archive_exp_out = capsys.readouterr().out
    assert "experiment status: archived" in archive_exp_out
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "remove", "--force", "--confirm", "skydiscover"]) == 0
    remove_out = capsys.readouterr().out
    assert _field_labels(remove_out) == _catalog_remove_field_labels()
    assert "removed: true" in remove_out
    remove_audit_id = _field(remove_out, "audit id")
    assert not catalog_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        catalog_row = conn.execute("SELECT status, removed_at FROM catalogs WHERE catalog_key = 'skydiscover'").fetchone()
        catalog_audit_row = conn.execute(
            "SELECT actor_credential_id, action, object_type, object_id, project_id, exp_id, cascade, reason, metadata_json FROM audit_events WHERE audit_id = ?",
            (remove_audit_id,),
        ).fetchone()
    assert catalog_row[0] == "removed"
    assert catalog_row[1] is not None
    assert catalog_audit_row[:8] == (root_credential_id, "remove", "catalog", "skydiscover", None, None, 0, None)
    assert json.loads(catalog_audit_row[8]) == {"schema_version": 1}

    assert run(["--home", str(home), "--key", root_key, "exp", "show", exp_id, "--project", project_id, "--include-archived"]) == 0
    history_exp_out = capsys.readouterr().out
    assert f"exp id: {exp_id}" in history_exp_out
    assert "experiment status: archived" in history_exp_out
    assert "reward: 3.25" in history_exp_out
    assert run(["--home", str(home), "--key", root_key, "runs", "show", run_id, "--project", project_id]) == 0
    history_run_out = capsys.readouterr().out
    assert f"run id: {run_id}" in history_run_out
    assert "run status: passed" in history_run_out
    assert "reward: 3.25" in history_run_out
    assert run(["--home", str(home), "--key", root_key, "logs", "list", "--project", project_id, "--run", run_id]) == 0
    history_logs_out = capsys.readouterr().out
    assert f"run id: {run_id}" in history_logs_out
    assert "stream: stdout" in history_logs_out


def test_skydiscover_python_baseline_records_metrics_and_hidden_logs(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    source = tmp_path / "source"
    upstream.mkdir()
    source.mkdir()
    evaluator = upstream / "benchmarks" / "python-demo"
    evaluator.mkdir(parents=True)
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "evaluator.py").write_text(
        """
from pathlib import Path


def evaluate(program_path):
    print("private evaluator stdout")
    Path(program_path, "workspace-only.txt").write_text("temporary evaluator workspace", encoding="utf-8")
    content = (Path(program_path) / "main.py").read_text(encoding="utf-8")
    return {"metrics": {"combined_score": 9.0, "source_bytes": len(content)}, "feedback": {"checked": True}}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    _git(["init"], upstream)
    _git(["config", "user.name", "ALab Test"], upstream)
    _git(["config", "user.email", "alab@example.test"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    _git(["add", "."], upstream)
    _git(["commit", "-m", "catalog"], upstream)
    _git(["branch", "-M", "main"], upstream)
    config = tmp_path / "alab.skydiscover-python.toml"
    config.write_text(
        """
schema_version = 1

[project]
name = "SkyDiscover Python Project"
task = "Run Python evaluator baseline"

[runner]
type = "skydiscover_python"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/python-demo"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
    capsys.readouterr()
    assert (
        run(
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
        == 0
    )
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    project_id = _field(project_out, "project id")
    validation_id = _field(project_out, "validation id")
    assert "project status: valid" in project_out
    assert "validation status: passed" in project_out
    assert not (home / "tmp" / project_id / validation_id).exists()
    _assert_project_tmp_clean(home, project_id)

    assert run(["--home", str(home), "--key", root_key, "project", "show", "--project", project_id]) == 0
    project_show_out = capsys.readouterr().out
    assert "runner type: skydiscover_python" in project_show_out
    assert "sandbox: not-os-sandbox" in project_show_out
    assert run(["--home", str(home), "--key", root_key, "project", "config", "show", "--project", project_id]) == 0
    config_show_out = capsys.readouterr().out
    assert "runner type: skydiscover_python" in config_show_out
    assert "sandbox: not-os-sandbox" in config_show_out

    with sqlite3.connect(home / "alab.db") as conn:
        rows = conn.execute(
            "SELECT stream, hidden, preview_text FROM log_streams WHERE validation_id = ? ORDER BY stream",
            (validation_id,),
        ).fetchall()
        validation = conn.execute(
            "SELECT reward_value, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (validation_id,),
        ).fetchone()
        hidden_stdout_file = conn.execute(
            "SELECT file_path FROM log_streams WHERE validation_id = ? AND stream = 'hidden_stdout' AND hidden = 1",
            (validation_id,),
        ).fetchone()[0]
        hidden_stdout_artifacts = conn.execute(
            "SELECT COUNT(*) FROM artifacts WHERE project_id = ? AND blob_path = ?",
            (project_id, hidden_stdout_file),
        ).fetchone()[0]
    previews = {row[0]: row[2] for row in rows}
    hidden = {row[0]: row[1] for row in rows}
    assert validation[0] == 9.0
    assert validation[1] == "parsed"
    assert '"combined_score":9.0' in validation[2]
    assert "SkyDiscover Python evaluator completed" in previews["stdout"]
    assert "private evaluator stdout" in previews["hidden_stdout"]
    assert hidden["hidden_stdout"] == 1
    assert hidden_stdout_artifacts == 0

    worktree = tmp_path / "sky-python-exp"
    assert run(["--home", str(home), "--key", root_key, "exp", "create", "--project", project_id, "--name", "sky-python-run", "--path", str(worktree)]) == 0
    exp_create_out = capsys.readouterr().out
    assert _field_labels(exp_create_out) == _exp_create_field_labels()
    head_before_run = _git(["rev-parse", "HEAD"], worktree)
    _assert_worktree_clean(worktree)
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "sky python adapter"]) == 0
    run_out = capsys.readouterr().out
    run_id = _field(run_out, "run id")
    assert _field_labels(run_out) == _run_field_labels()
    assert "run status: passed" in run_out
    assert "reward: 9.0" in run_out
    assert not (home / "tmp" / project_id / run_id).exists()
    _assert_project_tmp_clean(home, project_id)
    assert _git(["rev-parse", "HEAD"], worktree) == head_before_run
    assert not (worktree / "workspace-only.txt").exists()
    _assert_worktree_clean(worktree)

    shutil.rmtree(home / "sources" / "skydiscover")
    assert run(["--home", str(home), "--key", root_key, "project", "validate", "--project", project_id]) == 1
    failed_validation_out = capsys.readouterr().out
    failed_validation_id = _field(failed_validation_out, "validation id")
    assert _field_labels(failed_validation_out) == _project_validation_field_labels(failure=True)
    assert "validation status: error" in failed_validation_out
    assert "project status: invalid" in failed_validation_out
    assert "error code: BASELINE_VALIDATION_FAILED" in failed_validation_out
    assert not (home / "tmp" / project_id / failed_validation_id).exists()
    _assert_project_tmp_clean(home, project_id)
    with sqlite3.connect(home / "alab.db") as conn:
        validation_row = conn.execute(
            "SELECT status, exit_code, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (failed_validation_id,),
        ).fetchone()
        validation_stderr = conn.execute(
            "SELECT preview_text FROM log_streams WHERE validation_id = ? AND stream = 'stderr' AND hidden = 0",
            (failed_validation_id,),
        ).fetchone()[0]
    validation_record = json.loads(validation_row[3])
    assert validation_row[:3] == ("error", None, "not_attempted")
    assert validation_record["failure"] == "SkyDiscover catalog ref target does not exist"
    assert "SkyDiscover catalog ref target does not exist" in validation_stderr

    head_before_failed_run = _git(["rev-parse", "HEAD"], worktree)
    assert run(["--home", str(home), "run", "--message", "missing catalog resolver"]) == 1
    failed_run_out = capsys.readouterr().out
    failed_run_id = _field(failed_run_out, "run id")
    assert _field_labels(failed_run_out) == _run_field_labels(failure=True)
    assert "run status: error" in failed_run_out
    assert "reason: SkyDiscover catalog ref target does not exist" in failed_run_out
    assert not (home / "tmp" / project_id / failed_run_id).exists()
    _assert_project_tmp_clean(home, project_id)
    assert _git(["rev-parse", "HEAD"], worktree) == head_before_failed_run
    _assert_worktree_clean(worktree)
    with sqlite3.connect(home / "alab.db") as conn:
        run_row = conn.execute(
            "SELECT status, exit_code, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (failed_run_id,),
        ).fetchone()
        run_stderr = conn.execute(
            "SELECT preview_text FROM log_streams WHERE run_id = ? AND stream = 'stderr' AND hidden = 0",
            (failed_run_id,),
        ).fetchone()[0]
    run_record = json.loads(run_row[3])
    assert run_row[:3] == ("error", None, "not_attempted")
    assert run_record["failure"] == "SkyDiscover catalog ref target does not exist"
    assert "SkyDiscover catalog ref target does not exist" in run_stderr


def test_skydiscover_python_missing_primary_metric_is_saved_failure(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    source = tmp_path / "source"
    upstream.mkdir()
    source.mkdir()
    evaluator = upstream / "benchmarks" / "missing-primary"
    evaluator.mkdir(parents=True)
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "evaluator.py").write_text(
        """
def evaluate(program_path):
    return {"metrics": {"other": 2.0}, "feedback": {"checked": True}}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    _git(["init"], upstream)
    _git(["config", "user.name", "ALab Test"], upstream)
    _git(["config", "user.email", "alab@example.test"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    _git(["add", "."], upstream)
    _git(["commit", "-m", "catalog"], upstream)
    _git(["branch", "-M", "main"], upstream)
    config = tmp_path / "alab.skydiscover-missing-primary.toml"
    config.write_text(
        """
schema_version = 1

[project]
name = "SkyDiscover Missing Primary"
task = "Persist missing SkyDiscover primary metric"

[runner]
type = "skydiscover_python"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/missing-primary"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "accuracy"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 1
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels(failure=True)
    validation_id = _field(project_out, "validation id")
    assert "project status: invalid" in project_out
    assert "validation status: error" in project_out
    assert "error code: BASELINE_VALIDATION_FAILED" in project_out
    assert "reason: baseline validation status is error" in project_out

    with sqlite3.connect(home / "alab.db") as conn:
        validation = conn.execute(
            "SELECT status, exit_code, reward_value, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (validation_id,),
        ).fetchone()
        visible_stdout = conn.execute(
            "SELECT preview_text FROM log_streams WHERE validation_id = ? AND stream = 'stdout' AND hidden = 0",
            (validation_id,),
        ).fetchone()[0]
    assert validation[:4] == ("error", 0, None, "missing")
    validation_record = json.loads(validation[4])
    assert validation_record["reward"] == {"type": "skydiscover", "value": None}
    assert validation_record["metrics"] == {"other": 2.0}
    assert validation_record["failure"] == "SkyDiscover reward metric missing"
    assert "metric names: other" in visible_stdout
    assert "reward: none" in visible_stdout


def test_skydiscover_python_dependency_failures_are_saved_results(tmp_path, monkeypatch, capsys) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
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
    print("fake uv created env")
    raise SystemExit(0)
if args[:2] == ["pip", "install"]:
    print("fake dependency stdout")
    print("fake dependency stderr", file=sys.stderr)
    raise SystemExit(23 if os.environ.get("FAKE_UV_DEPENDENCY_MODE") == "fail" else 0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("ALAB_DEBUG", "1")

    def create_catalog(upstream: Path, ref_name: str) -> None:
        evaluator = upstream / "benchmarks" / ref_name
        evaluator.mkdir(parents=True)
        (evaluator / "requirements.txt").write_text("fake-dependency==1.0\n", encoding="utf-8")
        (evaluator / "evaluator.py").write_text(
            """
def evaluate(program_path):
    print("private evaluator stdout")
    return {"metrics": {"combined_score": 5.5}, "feedback": {"checked": True}}
""".strip()
            + "\n",
            encoding="utf-8",
        )
        _git(["init"], upstream)
        _git(["config", "user.name", "ALab Test"], upstream)
        _git(["config", "user.email", "alab@example.test"], upstream)
        _git(["config", "commit.gpgsign", "false"], upstream)
        _git(["add", "."], upstream)
        _git(["commit", "-m", "catalog"], upstream)
        _git(["branch", "-M", "main"], upstream)

    def write_config(path: Path, ref_name: str) -> None:
        path.write_text(
            f"""
schema_version = 1

[project]
name = "SkyDiscover Python Dependency Failure"
task = "Persist dependency failures"

[runner]
type = "skydiscover_python"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/{ref_name}"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
            + "\n",
            encoding="utf-8",
        )

    def create_source(path: Path) -> None:
        path.mkdir()
        (path / "main.py").write_text("print('candidate')\n", encoding="utf-8")

    validation_home = tmp_path / "validation-home"
    validation_upstream = tmp_path / "validation-catalog"
    validation_source = tmp_path / "validation-source"
    validation_config = tmp_path / "validation.toml"
    create_catalog(validation_upstream, "dependency-validation")
    create_source(validation_source)
    write_config(validation_config, "dependency-validation")

    assert run(["--home", str(validation_home), "auth", "init"]) == 0
    validation_root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(validation_home), "--key", validation_root_key, "catalog", "skydiscover", "add", "--origin-url", str(validation_upstream), "--ref", "main"]) == 0
    capsys.readouterr()
    monkeypatch.setenv("FAKE_UV_DEPENDENCY_MODE", "fail")
    assert (
        run(
            [
                "--home",
                str(validation_home),
                "--key",
                validation_root_key,
                "project",
                "init",
                "local",
                "--config",
                str(validation_config),
                "--source-path",
                str(validation_source),
            ]
        )
        == 1
    )
    validation_out = capsys.readouterr()
    validation_id = _field(validation_out.out, "validation id")
    assert validation_out.err == ""
    assert "Traceback" not in validation_out.out
    assert _field_labels(validation_out.out) == _project_init_field_labels(failure=True)
    assert "validation status: error" in validation_out.out
    assert "exit code: 1" in validation_out.out
    assert "error code: BASELINE_VALIDATION_FAILED" in validation_out.out
    assert "reason: baseline validation status is error" in validation_out.out

    with sqlite3.connect(validation_home / "alab.db") as conn:
        validation_row = conn.execute(
            "SELECT status, exit_code, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (validation_id,),
        ).fetchone()
        validation_hidden = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT stream, preview_text FROM log_streams WHERE validation_id = ? AND hidden = 1",
                (validation_id,),
            )
        }
    validation_record = json.loads(validation_row[3])
    assert validation_row[:3] == ("error", None, "not_attempted")
    assert validation_record["failure"] == "SkyDiscover Python dependency installation failed"
    assert "fake dependency stdout" in validation_hidden["hidden_stdout"]
    assert "fake dependency stderr" in validation_hidden["hidden_stderr"]

    run_home = tmp_path / "run-home"
    run_upstream = tmp_path / "run-catalog"
    run_source = tmp_path / "run-source"
    run_config = tmp_path / "run.toml"
    create_catalog(run_upstream, "dependency-run")
    create_source(run_source)
    write_config(run_config, "dependency-run")

    assert run(["--home", str(run_home), "auth", "init"]) == 0
    run_root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(run_home), "--key", run_root_key, "catalog", "skydiscover", "add", "--origin-url", str(run_upstream), "--ref", "main"]) == 0
    capsys.readouterr()
    monkeypatch.setenv("FAKE_UV_DEPENDENCY_MODE", "pass")
    assert (
        run(
            [
                "--home",
                str(run_home),
                "--key",
                run_root_key,
                "project",
                "init",
                "local",
                "--config",
                str(run_config),
                "--source-path",
                str(run_source),
            ]
        )
        == 0
    )
    run_project_out = capsys.readouterr().out
    assert _field_labels(run_project_out) == _project_init_field_labels()
    project_id = _field(run_project_out, "project id")
    shutil.rmtree(run_home / "cache" / "skydiscover-python-envs")

    worktree = tmp_path / "dependency-run-worktree"
    assert run(["--home", str(run_home), "--key", run_root_key, "exp", "create", "--project", project_id, "--name", "dependency-run", "--path", str(worktree)]) == 0
    assert _field_labels(capsys.readouterr().out) == _exp_create_field_labels()
    monkeypatch.chdir(worktree)
    monkeypatch.setenv("FAKE_UV_DEPENDENCY_MODE", "fail")
    assert run(["--home", str(run_home), "run", "--message", "dependency failure"]) == 1
    run_failure_out = capsys.readouterr()
    run_id = _field(run_failure_out.out, "run id")
    assert run_failure_out.err == ""
    assert "Traceback" not in run_failure_out.out
    assert _field_labels(run_failure_out.out) == _run_field_labels(failure=True)
    assert "run status: error" in run_failure_out.out
    assert "exit code: none" in run_failure_out.out
    assert "reward parse status: not_attempted" in run_failure_out.out
    assert "error code: RUNNER_ERROR" in run_failure_out.out
    assert "exit code: 1" in run_failure_out.out
    assert "reason: SkyDiscover Python dependency installation failed" in run_failure_out.out

    with sqlite3.connect(run_home / "alab.db") as conn:
        run_row = conn.execute(
            "SELECT status, exit_code, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        run_hidden = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT stream, preview_text FROM log_streams WHERE run_id = ? AND hidden = 1",
                (run_id,),
            )
        }
    run_record = json.loads(run_row[3])
    assert run_row[:3] == ("error", None, "not_attempted")
    assert run_record["failure"] == "SkyDiscover Python dependency installation failed"
    assert "fake dependency stdout" in run_hidden["hidden_stdout"]
    assert "fake dependency stderr" in run_hidden["hidden_stderr"]


def test_skydiscover_docker_baseline_records_metrics_and_hidden_logs(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    source = tmp_path / "source"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-calls.jsonl"
    upstream.mkdir()
    source.mkdir()
    bin_dir.mkdir()
    evaluator = upstream / "benchmarks" / "docker-demo"
    evaluator.mkdir(parents=True)
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (evaluator / "Dockerfile").write_text("FROM alpine:3.20\n", encoding="utf-8")
    (evaluator / "evaluate.sh").write_text("#!/bin/sh\n", encoding="utf-8")
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
    print("built evaluator image")
    raise SystemExit(0)
if args and args[0] == "run":
    workspace_mount = next(args[index + 1] for index, item in enumerate(args[:-1]) if item == "-v" and args[index + 1].endswith(":/workspace"))
    workspace_dir = Path(workspace_mount.split(":", 1)[0])
    (workspace_dir / "captured.txt").write_text("captured file artifact", encoding="utf-8")
    print(json.dumps({"combined_score": 6.0, "artifacts": {"summary": "feedback only"}}))
    print("private docker stderr", file=sys.stderr)
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))
    _git(["init"], upstream)
    _git(["config", "user.name", "ALab Test"], upstream)
    _git(["config", "user.email", "alab@example.test"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    _git(["add", "."], upstream)
    _git(["commit", "-m", "catalog"], upstream)
    _git(["branch", "-M", "main"], upstream)
    config = tmp_path / "alab.skydiscover-docker.toml"
    config.write_text(
        """
schema_version = 1

[project]
name = "SkyDiscover Docker Project"
task = "Run Docker evaluator baseline"

[runner]
type = "skydiscover_docker"
timeout_seconds = 30
working_directory = "."
network = "none"
skydiscover_task_ref = "skydiscover:benchmarks/docker-demo"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"

[artifacts]
globs = ["workspace:captured.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
    capsys.readouterr()
    assert (
        run(
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
        == 0
    )
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    project_id = _field(project_out, "project id")
    validation_id = _field(project_out, "validation id")
    assert "project status: valid" in project_out
    assert not (home / "tmp" / project_id / validation_id).exists()
    _assert_project_tmp_clean(home, project_id)

    with sqlite3.connect(home / "alab.db") as conn:
        validation = conn.execute(
            "SELECT reward_value, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (validation_id,),
        ).fetchone()
        validation_artifacts = conn.execute(
            "SELECT root, relative_path, status, blob_path FROM artifacts WHERE validation_id = ? ORDER BY relative_path",
            (validation_id,),
        ).fetchall()
        logs = conn.execute(
            "SELECT stream, hidden, preview_text FROM log_streams WHERE validation_id = ? ORDER BY stream",
            (validation_id,),
        ).fetchall()
        hidden_stderr_file = conn.execute(
            "SELECT file_path FROM log_streams WHERE validation_id = ? AND stream = 'hidden_stderr' AND hidden = 1",
            (validation_id,),
        ).fetchone()[0]
        hidden_stderr_artifacts = conn.execute(
            "SELECT COUNT(*) FROM artifacts WHERE project_id = ? AND blob_path = ?",
            (project_id, hidden_stderr_file),
        ).fetchone()[0]
        cache_rows = conn.execute(
            "SELECT cache_kind, docker_tag, metadata_json FROM cache_entries WHERE project_id = ? AND status = 'active'",
            (project_id,),
        ).fetchall()
    previews = {row[0]: row[2] for row in logs}
    hidden = {row[0]: row[1] for row in logs}
    validation_record = json.loads(validation[2])
    assert validation[0] == 6.0
    assert validation[1] == "parsed"
    assert validation_record["adapter_feedback"]["mode"] == "docker"
    assert validation_record["adapter_feedback"]["feedback"]["artifacts"] == {"summary": "feedback only"}
    assert validation_artifacts[0][:3] == ("workspace", "captured.txt", "captured")
    assert validation_artifacts[0][3] is not None
    assert "SkyDiscover Docker evaluator completed" in previews["stdout"]
    assert "private docker stderr" in previews["hidden_stderr"]
    assert hidden["hidden_stderr"] == 1
    assert hidden_stderr_artifacts == 0
    assert cache_rows[0][0] == "docker_image"
    assert cache_rows[0][1].startswith("alab-cache:")

    worktree = tmp_path / "sky-docker-exp"
    assert run(["--home", str(home), "--key", root_key, "exp", "create", "--project", project_id, "--name", "sky-docker-run", "--path", str(worktree)]) == 0
    exp_create_out = capsys.readouterr().out
    assert _field_labels(exp_create_out) == _exp_create_field_labels()
    head_before_run = _git(["rev-parse", "HEAD"], worktree)
    _assert_worktree_clean(worktree)
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "sky docker adapter"]) == 0
    run_out = capsys.readouterr().out
    run_id = _field(run_out, "run id")
    assert _field_labels(run_out) == _run_field_labels()
    assert "run status: passed" in run_out
    assert "reward: 6.0" in run_out
    assert "artifact count: 1" in run_out
    assert not (home / "tmp" / project_id / run_id).exists()
    _assert_project_tmp_clean(home, project_id)
    assert _git(["rev-parse", "HEAD"], worktree) == head_before_run
    _assert_worktree_clean(worktree)
    with sqlite3.connect(home / "alab.db") as conn:
        run_record = json.loads(conn.execute("SELECT record_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()[0])
        run_artifacts = conn.execute(
            "SELECT root, relative_path, status, blob_path FROM artifacts WHERE run_id = ? ORDER BY relative_path",
            (run_id,),
        ).fetchall()
    assert run_record["adapter_feedback"]["feedback"]["artifacts"] == {"summary": "feedback only"}
    assert run_artifacts[0][:3] == ("workspace", "captured.txt", "captured")
    assert run_artifacts[0][3] is not None


def test_adapter_docker_build_failures_are_saved_results(tmp_path, monkeypatch, capsys) -> None:
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-build-failure-calls.jsonl"
    bin_dir.mkdir()
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

mode = os.environ["FAKE_DOCKER_MODE"]
args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    raise SystemExit(1)
if args and args[0] == "build":
    print(f"{mode} build stdout")
    print(f"{mode} build stderr", file=sys.stderr)
    raise SystemExit(23 if mode.endswith("fail") else 0)
if args and args[0] == "run":
    if any(":/alab/harbor:ro" in arg for arg in args):
        run_mount = next(args[index + 1] for index, arg in enumerate(args) if arg == "-v" and args[index + 1].endswith(":/logs/alab"))
        run_dir = Path(run_mount.split(":", 1)[0])
        reward_dir = run_dir / "logs" / "verifier"
        reward_dir.mkdir(parents=True, exist_ok=True)
        (reward_dir / "reward.json").write_text(json.dumps({"reward": 5.0}), encoding="utf-8")
        print("harbor verifier stdout")
        raise SystemExit(0)
    print(json.dumps({"combined_score": 6.0}))
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))

    def make_source(path: Path) -> None:
        path.mkdir()
        (path / "main.py").write_text("print('candidate')\n", encoding="utf-8")

    def make_harbor_task(path: Path) -> None:
        (path / "tests").mkdir(parents=True)
        (path / "tests" / "Dockerfile").write_text("FROM verifier-base:latest\n", encoding="utf-8")
        (path / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        (path / "task.toml").write_text(
            """
[environment]
allow_internet = false
""".strip()
            + "\n",
            encoding="utf-8",
        )

    def write_harbor_config(path: Path, task_dir: Path, name: str) -> None:
        path.write_text(
            f"""
schema_version = 1

[project]
name = {json.dumps(name)}
task = "Persist Harbor build failures"

[runner]
type = "harbor"
timeout_seconds = 30
working_directory = "."
harbor_task_ref = {json.dumps(str(task_dir))}

[reward]
type = "harbor"
direction = "maximize"
primary_metric = "reward"
""".strip()
            + "\n",
            encoding="utf-8",
        )

    def make_skydiscover_upstream(path: Path) -> None:
        evaluator = path / "benchmarks" / "docker-build-failure"
        evaluator.mkdir(parents=True)
        (evaluator / "Dockerfile").write_text("FROM alpine:3.20\n", encoding="utf-8")
        (evaluator / "evaluate.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        _git(["init"], path)
        _git(["config", "user.name", "ALab Test"], path)
        _git(["config", "user.email", "alab@example.test"], path)
        _git(["config", "commit.gpgsign", "false"], path)
        _git(["add", "."], path)
        _git(["commit", "-m", "catalog"], path)
        _git(["branch", "-M", "main"], path)

    def write_skydiscover_config(path: Path, name: str) -> None:
        path.write_text(
            f"""
schema_version = 1

[project]
name = {json.dumps(name)}
task = "Persist SkyDiscover Docker build failures"

[runner]
type = "skydiscover_docker"
timeout_seconds = 30
working_directory = "."
network = "none"
skydiscover_task_ref = "skydiscover:benchmarks/docker-build-failure"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
            + "\n",
            encoding="utf-8",
        )

    def assert_saved_validation_failure(home: Path, validation_id: str, reason: str, marker: str) -> None:
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
        assert any(stream == "hidden_stdout" and marker in preview and hidden == 1 for stream, preview, hidden in logs)
        assert any(stream == "hidden_stderr" and marker in preview and hidden == 1 for stream, preview, hidden in logs)

    def assert_saved_run_failure(home: Path, run_id: str, reason: str, marker: str) -> None:
        with sqlite3.connect(home / "alab.db") as conn:
            run_row = conn.execute(
                "SELECT status, exit_code, reward_parse_status, record_json FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            logs = conn.execute(
                "SELECT stream, preview_text, hidden FROM log_streams WHERE run_id = ? ORDER BY stream",
                (run_id,),
            ).fetchall()
        assert run_row[:3] == ("error", None, "not_attempted")
        assert json.loads(run_row[3])["failure"] == reason
        assert ("stderr", reason, 0) in logs
        assert any(stream == "hidden_stdout" and marker in preview and hidden == 1 for stream, preview, hidden in logs)
        assert any(stream == "hidden_stderr" and marker in preview and hidden == 1 for stream, preview, hidden in logs)

    adapter_cases = [
        ("harbor", "Harbor verifier build failed: harbor-build-fail build stderr"),
        ("skydiscover", "SkyDiscover Docker evaluator build failed: skydiscover-build-fail build stderr"),
    ]

    for adapter, reason in adapter_cases:
        home = tmp_path / f"{adapter}-baseline-home"
        source = tmp_path / f"{adapter}-baseline-source"
        config = tmp_path / f"{adapter}-baseline.toml"
        make_source(source)
        if adapter == "harbor":
            task = tmp_path / "harbor-baseline-task"
            make_harbor_task(task)
            write_harbor_config(config, task, "Harbor build baseline failure")
        else:
            upstream = tmp_path / "sky-baseline-upstream"
            make_skydiscover_upstream(upstream)
            write_skydiscover_config(config, "SkyDiscover Docker build baseline failure")
        monkeypatch.setenv("FAKE_DOCKER_MODE", f"{adapter}-build-fail")
        assert run(["--home", str(home), "auth", "init"]) == 0
        root_key = _field(capsys.readouterr().out, "root key")
        if adapter == "skydiscover":
            assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
            capsys.readouterr()
        assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 1
        project_out = capsys.readouterr().out
        assert _field_labels(project_out) == _project_init_field_labels(failure=True)
        assert "project status: invalid" in project_out
        assert "validation status: error" in project_out
        assert "error code: BASELINE_VALIDATION_FAILED" in project_out
        assert "reason: baseline validation status is error" in project_out
        assert_saved_validation_failure(home, _field(project_out, "validation id"), reason, f"{adapter}-build-fail build")

    for adapter, reason in adapter_cases:
        home = tmp_path / f"{adapter}-run-home"
        source = tmp_path / f"{adapter}-run-source"
        config = tmp_path / f"{adapter}-run.toml"
        worktree = tmp_path / f"{adapter}-run-exp"
        make_source(source)
        if adapter == "harbor":
            task = tmp_path / "harbor-run-task"
            make_harbor_task(task)
            write_harbor_config(config, task, "Harbor build run failure")
        else:
            upstream = tmp_path / "sky-run-upstream"
            make_skydiscover_upstream(upstream)
            write_skydiscover_config(config, "SkyDiscover Docker build run failure")
        monkeypatch.setenv("FAKE_DOCKER_MODE", f"{adapter}-build-ok")
        assert run(["--home", str(home), "auth", "init"]) == 0
        root_key = _field(capsys.readouterr().out, "root key")
        if adapter == "skydiscover":
            assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
            capsys.readouterr()
        assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
        project_out = capsys.readouterr().out
        assert _field_labels(project_out) == _project_init_field_labels()
        project_id = _field(project_out, "project id")
        assert "project status: valid" in project_out
        assert run(["--home", str(home), "--key", root_key, "exp", "create", "--project", project_id, "--name", f"{adapter} build run failure", "--path", str(worktree)]) == 0
        capsys.readouterr()
        monkeypatch.chdir(worktree)
        monkeypatch.setenv("FAKE_DOCKER_MODE", f"{adapter}-build-fail")
        assert run(["--home", str(home), "run", "--message", f"{adapter} build failure"]) == 1
        run_out = capsys.readouterr().out
        assert _field_labels(run_out) == _run_field_labels(failure=True)
        assert "run status: error" in run_out
        assert "error code: RUNNER_ERROR" in run_out
        assert f"reason: {reason}" in run_out
        assert_saved_run_failure(home, _field(run_out, "run id"), reason, f"{adapter}-build-fail build")
        monkeypatch.chdir(tmp_path)


def test_harbor_project_init_uses_declared_source_and_excludes_private_assets(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    task_dir = tmp_path / "harbor-task"
    starter = task_dir / "starter"
    starter.mkdir(parents=True)
    (starter / "main.py").write_text("print('editable')\n", encoding="utf-8")
    (task_dir / "tests").mkdir()
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (task_dir / "tests" / "private.txt").write_text("hidden\n", encoding="utf-8")
    (task_dir / "environment").mkdir()
    (task_dir / "environment" / "private.txt").write_text("hidden environment\n", encoding="utf-8")
    (task_dir / "solution").mkdir()
    (task_dir / "solution" / "main.py").write_text("print('solution')\n", encoding="utf-8")
    (task_dir / "instruction.md").write_text("Visible Harbor instruction\n\nDetails.\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        """
source = "starter"

[environment]
image = "harbor-env:latest"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.harbor-source.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Harbor Source Project"
task = ""

[runner]
type = "harbor"
timeout_seconds = 30
working_directory = "."
harbor_task_ref = "{task_dir}"

[reward]
type = "harbor"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "harbor",
                "--config",
                str(config),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert _field_labels(out) == _project_init_field_labels()
    project_id = _field(out, "project id")
    source_ref = _field(out, "source ref")
    assert _source_tree_files(home, project_id, source_ref) == {"main.py"}
    with sqlite3.connect(home / "alab.db") as conn:
        metadata = conn.execute("SELECT origin_metadata_json FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
        config_json = conn.execute("SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = 1", (project_id,)).fetchone()[0]
    assert '"origin_type":"harbor"' in metadata
    assert '"source_path":"starter"' in metadata
    assert json.loads(config_json)["project"]["task"] == "Visible Harbor instruction\n\nDetails."


def test_adapter_init_rejects_conflicting_explicit_source(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    explicit = tmp_path / "explicit"
    task_dir = tmp_path / "harbor-task"
    explicit.mkdir()
    (explicit / "main.py").write_text("print('explicit')\n", encoding="utf-8")
    (task_dir / "starter").mkdir(parents=True)
    (task_dir / "starter" / "main.py").write_text("print('adapter')\n", encoding="utf-8")
    (task_dir / "tests").mkdir()
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        """
source = "starter"

[environment]
image = "harbor-env:latest"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.harbor-conflict.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Harbor Conflict Project"
task = "Reject mismatched explicit source"

[runner]
type = "harbor"
timeout_seconds = 30
working_directory = "."
harbor_task_ref = "{task_dir}"

[reward]
type = "harbor"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "harbor",
                "--config",
                str(config),
                "--source-path",
                str(explicit),
                "--skip-baseline-test",
            ]
        )
        == 2
    )
    assert "explicit source content conflicts with adapter-derived source" in capsys.readouterr().err


def test_skydiscover_project_init_uses_initial_program_metadata(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    benchmark = upstream / "benchmarks" / "metadata-demo"
    starter = benchmark / "starter"
    starter.mkdir(parents=True)
    (starter / "main.py").write_text("print('starter')\n", encoding="utf-8")
    (benchmark / "evaluator.py").write_text("def evaluate(program_path):\n    return {'combined_score': 1}\n", encoding="utf-8")
    (benchmark / "private.txt").write_text("hidden\n", encoding="utf-8")
    (benchmark / "benchmark.toml").write_text('initial_program = "starter"\n', encoding="utf-8")
    _git(["init"], upstream)
    _git(["config", "user.name", "ALab Test"], upstream)
    _git(["config", "user.email", "alab@example.test"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    _git(["add", "."], upstream)
    _git(["commit", "-m", "catalog"], upstream)
    _git(["branch", "-M", "main"], upstream)
    config = tmp_path / "alab.skydiscover-source.toml"
    config.write_text(
        """
schema_version = 1

[project]
name = "SkyDiscover Source Project"
task = "Import initial program"

[runner]
type = "skydiscover_python"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/metadata-demo"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
    capsys.readouterr()
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
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert _field_labels(out) == _project_init_field_labels()
    project_id = _field(out, "project id")
    source_ref = _field(out, "source ref")
    assert _source_tree_files(home, project_id, source_ref) == {"main.py"}
    with sqlite3.connect(home / "alab.db") as conn:
        metadata = conn.execute("SELECT origin_metadata_json FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
    assert '"origin_type":"skydiscover"' in metadata
    assert '"initial_program_path":"starter"' in metadata


def test_skydiscover_project_init_requires_initial_program_without_explicit_source(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    benchmark = upstream / "benchmarks" / "missing-initial"
    benchmark.mkdir(parents=True)
    (benchmark / "evaluator.py").write_text("def evaluate(program_path):\n    return {'combined_score': 1}\n", encoding="utf-8")
    _git(["init"], upstream)
    _git(["config", "user.name", "ALab Test"], upstream)
    _git(["config", "user.email", "alab@example.test"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    _git(["add", "."], upstream)
    _git(["commit", "-m", "catalog"], upstream)
    _git(["branch", "-M", "main"], upstream)
    config = tmp_path / "alab.skydiscover-missing-source.toml"
    config.write_text(
        """
schema_version = 1

[project]
name = "SkyDiscover Missing Source Project"
task = "Require explicit source"

[runner]
type = "skydiscover_python"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/missing-initial"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
    capsys.readouterr()
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
                "--skip-baseline-test",
            ]
        )
        == 2
    )
    assert "SkyDiscover benchmark has no initial program" in capsys.readouterr().err


def test_skydiscover_project_init_source_precedence_and_rejections(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    benchmark = upstream / "benchmarks" / "precedence-demo"
    starter = benchmark / "starter"
    matching_source = tmp_path / "matching-source"
    conflicting_source = tmp_path / "conflicting-source"
    starter.mkdir(parents=True)
    matching_source.mkdir()
    conflicting_source.mkdir()
    (starter / "main.py").write_text("print('starter')\n", encoding="utf-8")
    (matching_source / "main.py").write_text("print('starter')\n", encoding="utf-8")
    (conflicting_source / "main.py").write_text("print('conflict')\n", encoding="utf-8")
    (benchmark / "evaluator.py").write_text("def evaluate(program_path):\n    return {'combined_score': 1}\n", encoding="utf-8")
    (benchmark / "private.txt").write_text("hidden\n", encoding="utf-8")
    (benchmark / "benchmark.toml").write_text('initial_program = "starter"\n', encoding="utf-8")
    _git(["init"], upstream)
    _git(["config", "user.name", "ALab Test"], upstream)
    _git(["config", "user.email", "alab@example.test"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    _git(["add", "."], upstream)
    _git(["commit", "-m", "catalog"], upstream)
    _git(["branch", "-M", "main"], upstream)
    config = tmp_path / "alab.skydiscover-precedence.toml"
    config.write_text(
        """
schema_version = 1

[project]
name = "SkyDiscover Precedence Project"
task = "Check SkyDiscover source precedence"

[runner]
type = "skydiscover_python"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/precedence-demo"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
    capsys.readouterr()

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
                "--source-ref",
                "alab/source/src-existing",
                "--skip-baseline-test",
            ]
        )
        == 2
    )
    source_ref_err = capsys.readouterr().err
    assert _field_labels(source_ref_err) == _error_field_labels()
    assert "error code: SOURCE_INVALID" in source_ref_err
    assert "adapter project init does not accept --source-ref" in source_ref_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0

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
                "--source-path",
                str(conflicting_source),
                "--skip-baseline-test",
            ]
        )
        == 2
    )
    conflict_err = capsys.readouterr().err
    assert _field_labels(conflict_err) == _error_field_labels()
    assert "error code: SOURCE_INVALID" in conflict_err
    assert "explicit source content conflicts with adapter-derived source" in conflict_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0

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
                "--source-path",
                str(matching_source),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert _field_labels(out) == _project_init_field_labels()
    project_id = _field(out, "project id")
    source_ref = _field(out, "source ref")
    assert _source_tree_files(home, project_id, source_ref) == {"main.py"}
    with sqlite3.connect(home / "alab.db") as conn:
        metadata = conn.execute("SELECT origin_metadata_json FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
    assert '"origin_type":"local"' in metadata
    assert '"origin_type":"skydiscover"' in metadata
    assert '"initial_program_path":"starter"' in metadata
    assert "evaluator.py" not in metadata
    assert "private.txt" not in metadata


def test_skydiscover_project_init_allows_explicit_git_and_empty_without_initial_program(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    upstream = tmp_path / "skydiscover-upstream"
    source_repo = tmp_path / "explicit-source-repo"
    benchmark = upstream / "benchmarks" / "explicit-demo"
    benchmark.mkdir(parents=True)
    source_repo.mkdir()
    (benchmark / "evaluator.py").write_text("def evaluate(program_path):\n    return {'combined_score': 1}\n", encoding="utf-8")
    (source_repo / "main.py").write_text("print('explicit git')\n", encoding="utf-8")
    _git(["init"], source_repo)
    _git(["config", "user.name", "ALab Test"], source_repo)
    _git(["config", "user.email", "alab@example.test"], source_repo)
    _git(["config", "commit.gpgsign", "false"], source_repo)
    _git(["add", "."], source_repo)
    _git(["commit", "-m", "explicit source"], source_repo)
    _git(["init"], upstream)
    _git(["config", "user.name", "ALab Test"], upstream)
    _git(["config", "user.email", "alab@example.test"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    _git(["add", "."], upstream)
    _git(["commit", "-m", "catalog"], upstream)
    _git(["branch", "-M", "main"], upstream)
    config = tmp_path / "alab.skydiscover-explicit.toml"
    config.write_text(
        """
schema_version = 1

[project]
name = "SkyDiscover Explicit Source Project"
task = "Use explicit source"

[runner]
type = "skydiscover_python"
timeout_seconds = 30
working_directory = "."
skydiscover_task_ref = "skydiscover:benchmarks/explicit-demo"
program_path = "."

[reward]
type = "skydiscover"
direction = "maximize"
primary_metric = "combined_score"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "catalog", "skydiscover", "add", "--origin-url", str(upstream), "--ref", "main"]) == 0
    capsys.readouterr()

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
                "--source-git",
                str(source_repo),
                "--skip-baseline-test",
            ]
        )
        == 0
    )
    git_out = capsys.readouterr().out
    git_project_id = _field(git_out, "project id")
    git_source_ref = _field(git_out, "source ref")
    assert _source_tree_files(home, git_project_id, git_source_ref) == {"main.py"}
    with sqlite3.connect(home / "alab.db") as conn:
        git_metadata = conn.execute("SELECT origin_metadata_json FROM sources WHERE project_id = ?", (git_project_id,)).fetchone()[0]
    assert '"origin_type":"git"' in git_metadata
    assert '"origin_type":"skydiscover"' not in git_metadata

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
    empty_out = capsys.readouterr().out
    empty_project_id = _field(empty_out, "project id")
    empty_source_ref = _field(empty_out, "source ref")
    assert _source_tree_files(home, empty_project_id, empty_source_ref) == set()
    with sqlite3.connect(home / "alab.db") as conn:
        empty_metadata = conn.execute("SELECT origin_metadata_json FROM sources WHERE project_id = ?", (empty_project_id,)).fetchone()[0]
    assert '"origin_type":"empty"' in empty_metadata
    assert '"origin_type":"skydiscover"' not in empty_metadata


def test_harbor_baseline_records_reward_and_hidden_logs(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    task_dir = tmp_path / "harbor-task"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "docker-calls.jsonl"
    source.mkdir()
    (source / "main.py").write_text("print('candidate')\n", encoding="utf-8")
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        """
[environment]
image = "harbor-env:latest"
allow_internet = false

[environment.env]
HARBOR_TOKEN = "literal-secret"
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
    (reward_dir / "reward.json").write_text(json.dumps({"reward": 4.25, "tests": 2}), encoding="utf-8")
    print("literal-secret verifier stdout")
    print("literal-secret verifier stderr", file=sys.stderr)
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_DOCKER_LOG", str(log_path))
    config = tmp_path / "alab.harbor.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Harbor Project"
task = "Run Harbor verifier baseline"

[runner]
type = "harbor"
timeout_seconds = 30
working_directory = "."
harbor_task_ref = "{task_dir}"

[reward]
type = "harbor"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert (
        run(
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
        == 0
    )
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    project_id = _field(project_out, "project id")
    validation_id = _field(project_out, "validation id")
    assert "project status: valid" in project_out
    assert not (home / "tmp" / project_id / validation_id).exists()
    _assert_project_tmp_clean(home, project_id)
    with sqlite3.connect(home / "alab.db") as conn:
        validation = conn.execute(
            "SELECT reward_value, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (validation_id,),
        ).fetchone()
        logs = conn.execute(
            "SELECT stream, hidden, preview_text FROM log_streams WHERE validation_id = ? ORDER BY stream",
            (validation_id,),
        ).fetchall()
    previews = {row[0]: row[2] for row in logs}
    hidden = {row[0]: row[1] for row in logs}
    assert validation[0] == 4.25
    assert validation[1] == "parsed"
    assert '"mode":"harbor"' in validation[2]
    assert "Harbor verifier completed" in previews["stdout"]
    assert "literal-secret" not in previews["hidden_stdout"]
    assert "[REDACTED]" in previews["hidden_stdout"]
    assert hidden["hidden_stdout"] == 1

    worktree = tmp_path / "harbor-exp"
    assert run(["--home", str(home), "--key", root_key, "exp", "create", "--project", project_id, "--name", "harbor-run", "--path", str(worktree)]) == 0
    exp_create_out = capsys.readouterr().out
    assert _field_labels(exp_create_out) == _exp_create_field_labels()
    head_before_run = _git(["rev-parse", "HEAD"], worktree)
    _assert_worktree_clean(worktree)
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "harbor adapter"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels()
    run_id = _field(run_out, "run id")
    assert "run status: passed" in run_out
    assert "reward: 4.25" in run_out
    assert not (home / "tmp" / project_id / run_id).exists()
    _assert_project_tmp_clean(home, project_id)
    assert _git(["rev-parse", "HEAD"], worktree) == head_before_run
    _assert_worktree_clean(worktree)
    with sqlite3.connect(home / "alab.db") as conn:
        hidden_run_log = conn.execute(
            """
            SELECT log_id, preview_text
            FROM log_streams
            WHERE run_id = ? AND stream = 'hidden_stdout' AND hidden = 1
            """,
            (run_id,),
        ).fetchone()
    assert hidden_run_log is not None
    hidden_log_id, hidden_preview = hidden_run_log
    assert "literal-secret" not in hidden_preview
    assert "[REDACTED]" in hidden_preview

    assert run(["--home", str(home), "logs", "show", hidden_log_id]) == 4
    hidden_show_err = capsys.readouterr().err
    assert "error code: SCOPE_VIOLATION" in hidden_show_err
    assert "log is not visible or not found" in hidden_show_err
    assert run(["--home", str(home), "logs", "show", hidden_log_id, "--include-hidden"]) == 4
    token_hidden_show_include_err = capsys.readouterr().err
    assert "error code: SCOPE_VIOLATION" in token_hidden_show_include_err
    assert "hidden logs require admin/root" in token_hidden_show_include_err
    token_hidden_export = tmp_path / "token-hidden.log"
    assert (
        run(
            [
                "--home",
                str(home),
                "logs",
                "export",
                hidden_log_id,
                "--out",
                str(token_hidden_export),
                "--include-hidden",
            ]
        )
        == 4
    )
    token_hidden_export_err = capsys.readouterr().err
    assert "error code: SCOPE_VIOLATION" in token_hidden_export_err
    assert "hidden logs require admin/root" in token_hidden_export_err
    assert not token_hidden_export.exists()

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "show",
                hidden_log_id,
                "--project",
                project_id,
            ]
        )
        == 4
    )
    root_hidden_show_err = capsys.readouterr().err
    assert "error code: SCOPE_VIOLATION" in root_hidden_show_err
    assert "hidden log requires --include-hidden" in root_hidden_show_err
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "show",
                hidden_log_id,
                "--project",
                project_id,
                "--include-hidden",
            ]
        )
        == 0
    )
    root_hidden_show = capsys.readouterr().out
    assert _field_labels(root_hidden_show) == _log_show_field_labels()
    assert "hidden: true" in root_hidden_show
    assert "content:" in root_hidden_show
    assert "literal-secret" not in root_hidden_show
    assert "[REDACTED]" in root_hidden_show

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "list",
                "--project",
                project_id,
                "--run",
                run_id,
            ]
        )
        == 0
    )
    root_visible_logs = capsys.readouterr().out
    assert f"log id: {hidden_log_id}" not in root_visible_logs
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "list",
                "--project",
                project_id,
                "--run",
                run_id,
                "--include-hidden",
            ]
        )
        == 0
    )
    root_hidden_logs = capsys.readouterr().out
    assert f"log id: {hidden_log_id}" in root_hidden_logs
    assert "stream: hidden_stdout" in root_hidden_logs

    root_hidden_export = tmp_path / "root-hidden.log"
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "export",
                hidden_log_id,
                "--project",
                project_id,
                "--out",
                str(root_hidden_export),
                "--include-hidden",
            ]
        )
        == 0
    )
    root_hidden_export_out = capsys.readouterr().out
    assert _field_labels(root_hidden_export_out) == _log_field_labels()
    assert root_hidden_export.read_text(encoding="utf-8").strip() == hidden_preview.strip()

    assert run(["--home", str(home), "logs", "archive", hidden_log_id]) == 4
    token_hidden_archive_err = capsys.readouterr().err
    assert "error code: SCOPE_VIOLATION" in token_hidden_archive_err
    assert "object is not visible or not found" in token_hidden_archive_err
    assert _audit_count(home, "archive", "log", hidden_log_id) == 0
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT archive_status FROM log_streams WHERE log_id = ?",
            (hidden_log_id,),
        ).fetchone()[0] == "active"

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "archive",
                hidden_log_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    root_hidden_archive = capsys.readouterr().out
    assert _field_labels(root_hidden_archive) == _archive_field_labels("log")
    assert f"log id: {hidden_log_id}" in root_hidden_archive
    assert "previous archive status: active" in root_hidden_archive
    assert "archive status: archived" in root_hidden_archive
    assert _audit_count(home, "archive", "log", hidden_log_id) == 1

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "show",
                hidden_log_id,
                "--project",
                project_id,
                "--include-hidden",
            ]
        )
        == 0
    )
    archived_hidden_show = capsys.readouterr().out
    assert _field_labels(archived_hidden_show) == _log_show_field_labels()
    assert "hidden: true" in archived_hidden_show
    assert "archive status: archived" in archived_hidden_show
    assert "content:" in archived_hidden_show
    assert "literal-secret" not in archived_hidden_show
    assert "[REDACTED]" in archived_hidden_show
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "list",
                "--project",
                project_id,
                "--run",
                run_id,
                "--include-hidden",
            ]
        )
        == 0
    )
    archived_hidden_default_list = capsys.readouterr().out
    assert f"log id: {hidden_log_id}" not in archived_hidden_default_list
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "list",
                "--project",
                project_id,
                "--run",
                run_id,
                "--include-hidden",
                "--include-archived",
            ]
        )
        == 0
    )
    archived_hidden_included_list = capsys.readouterr().out
    assert f"log id: {hidden_log_id}" in archived_hidden_included_list
    assert "hidden: true" in archived_hidden_included_list
    assert "archive status: archived" in archived_hidden_included_list
    archived_hidden_export = tmp_path / "archived-root-hidden.log"
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "export",
                hidden_log_id,
                "--project",
                project_id,
                "--out",
                str(archived_hidden_export),
                "--include-hidden",
            ]
        )
        == 2
    )
    archived_hidden_export_err = capsys.readouterr().err
    assert _field_labels(archived_hidden_export_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in archived_hidden_export_err
    assert "exporting archived logs requires --include-archived" in archived_hidden_export_err
    assert not archived_hidden_export.exists()
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "export",
                hidden_log_id,
                "--project",
                project_id,
                "--out",
                str(archived_hidden_export),
                "--include-hidden",
                "--include-archived",
            ]
        )
        == 0
    )
    archived_hidden_export_out = capsys.readouterr().out
    assert _field_labels(archived_hidden_export_out) == _log_field_labels()
    assert "hidden: true" in archived_hidden_export_out
    assert "archive status: archived" in archived_hidden_export_out
    assert archived_hidden_export.read_text(encoding="utf-8").strip() == hidden_preview.strip()

    assert run(["--home", str(home), "logs", "unarchive", hidden_log_id]) == 4
    token_hidden_unarchive_err = capsys.readouterr().err
    assert "error code: SCOPE_VIOLATION" in token_hidden_unarchive_err
    assert "object is not visible or not found" in token_hidden_unarchive_err
    assert _audit_count(home, "unarchive", "log", hidden_log_id) == 0
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT archive_status FROM log_streams WHERE log_id = ?",
            (hidden_log_id,),
        ).fetchone()[0] == "archived"

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "unarchive",
                hidden_log_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    root_hidden_unarchive = capsys.readouterr().out
    assert _field_labels(root_hidden_unarchive) == _unarchive_field_labels("log")
    assert f"log id: {hidden_log_id}" in root_hidden_unarchive
    assert "previous archive status: archived" in root_hidden_unarchive
    assert "archive status: active" in root_hidden_unarchive
    assert _audit_count(home, "unarchive", "log", hidden_log_id) == 1

    with sqlite3.connect(home / "alab.db") as conn:
        hidden_file_rel = conn.execute(
            "SELECT file_path FROM log_streams WHERE log_id = ?",
            (hidden_log_id,),
        ).fetchone()[0]
        assert conn.execute(
            "SELECT COUNT(*) FROM artifacts WHERE project_id = ? AND blob_path = ?",
            (project_id, hidden_file_rel),
        ).fetchone()[0] == 0
    hidden_file_path = home / "projects" / project_id / "artifacts" / hidden_file_rel
    assert hidden_file_path.exists()
    assert run(["--home", str(home), "logs", "remove", hidden_log_id, "--dry-run"]) == 4
    token_hidden_remove_err = capsys.readouterr().err
    assert "error code: COMMAND_UNAVAILABLE" in token_hidden_remove_err
    assert _audit_count(home, "remove", "log", hidden_log_id) == 0
    assert hidden_file_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT archive_status FROM log_streams WHERE log_id = ?",
            (hidden_log_id,),
        ).fetchone()[0] == "active"

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "remove",
                hidden_log_id,
                "--project",
                project_id,
                "--dry-run",
            ]
        )
        == 0
    )
    active_hidden_remove_dry_run = capsys.readouterr().out
    assert _field_labels(active_hidden_remove_dry_run) == _observe_remove_field_labels(
        "log",
        dry_run=True,
        has_blocker=True,
        filesystem_path_count=1,
    )
    assert "blocker: target_not_archived" in active_hidden_remove_dry_run
    assert "deleted filesystem paths: 1" in active_hidden_remove_dry_run
    assert "planned trash move:" in active_hidden_remove_dry_run
    assert hidden_file_path.exists()

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "archive",
                hidden_log_id,
                "--project",
                project_id,
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "logs",
                "remove",
                hidden_log_id,
                "--project",
                project_id,
                "--force",
                "--confirm",
                hidden_log_id,
            ]
        )
        == 0
    )
    hidden_remove_out = capsys.readouterr().out
    assert _field_labels(hidden_remove_out) == _observe_remove_field_labels("log", dry_run=False)
    assert "removed: true" in hidden_remove_out
    assert "deleted filesystem paths: 1" in hidden_remove_out
    assert "trash cleanup pending: false" in hidden_remove_out
    assert _audit_count(home, "remove", "log", hidden_log_id) == 1
    assert not hidden_file_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM log_streams WHERE log_id = ?",
            (hidden_log_id,),
        ).fetchone()[0] == 0


def test_local_project_run_submit_workflow(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("ok")\n', encoding="utf-8")
    exact_message = "界" * 100
    exact_body = ("界" * 21845) + "x"
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Smoke Project"
task = "Keep smoke passing"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")

    assert (
        run(
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
        == 0
    )
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    project_id = _field(project_out, "project id")
    assert "project status: valid" in project_out

    worktree = tmp_path / "exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "attempt",
                "--path",
                str(worktree),
            ]
        )
        == 0
    )
    exp_create_out = capsys.readouterr().out
    assert _field_labels(exp_create_out) == _exp_create_field_labels()
    exp_id = _field(exp_create_out, "exp id")

    monkeypatch.chdir(worktree)
    runs_before_extra = _table_count(home, "runs")
    assert run(["--home", str(home), "run", "extra", "--message", "ignored"]) == 2
    extra_run_err = capsys.readouterr().err
    assert _field_labels(extra_run_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_run_err
    assert "run accepts no positional arguments" in extra_run_err
    assert _table_count(home, "runs") == runs_before_extra
    assert run(["--home", str(home), "run", "--message", "ignored", "--summary", "unsupported"]) == 2
    unsupported_run_option_err = capsys.readouterr().err
    assert _field_labels(unsupported_run_option_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_run_option_err
    assert "unsupported option --summary" in unsupported_run_option_err
    assert _table_count(home, "runs") == runs_before_extra
    assert run(["--home", str(home), "run", "--message", exact_message]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels()
    assert "run status: passed" in run_out
    summary_file = tmp_path / "exact-summary.txt"
    summary_file.write_text(exact_body, encoding="utf-8")
    feedback_file = tmp_path / "exact-feedback.txt"
    feedback_file.write_text(exact_body, encoding="utf-8")
    submit_args = [
        "--home",
        str(home),
        "submit",
        "--message",
        exact_message,
        "--summary-file",
        str(summary_file),
        "--feedback-file",
        str(feedback_file),
        "--ref",
        "none",
    ]

    submissions_before_extra = _table_count(home, "experiment_submissions")
    missing_summary_file = tmp_path / "missing-summary.txt"
    assert run(["--home", str(home), "submit", "extra", "--message", exact_message, "--summary-file", str(missing_summary_file), "--feedback", "ok", "--ref", "none"]) == 2
    extra_submit_err = capsys.readouterr().err
    assert _field_labels(extra_submit_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_submit_err
    assert "submit accepts no positional arguments" in extra_submit_err
    assert "No such file" not in extra_submit_err
    assert _table_count(home, "experiment_submissions") == submissions_before_extra
    assert run(["--home", str(home), "submit", "--message", exact_message, "--summary", "done", "--feedback", "ok", "--ref", "none", "--path", "unsupported"]) == 2
    unsupported_submit_option_err = capsys.readouterr().err
    assert _field_labels(unsupported_submit_option_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_submit_option_err
    assert "unsupported option --path" in unsupported_submit_option_err
    assert _table_count(home, "experiment_submissions") == submissions_before_extra

    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute(
            "UPDATE projects SET status = 'archived', pre_archive_status = 'valid', archived_at = '2026-05-19T00:00:00Z' WHERE project_id = ?",
            (project_id,),
        )
    assert run(submit_args) == 4
    archived_project_err = capsys.readouterr().err
    assert _field_labels(archived_project_err) == _error_field_labels()
    assert "error code: PROJECT_ARCHIVED" in archived_project_err
    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute("UPDATE projects SET status = 'valid', pre_archive_status = NULL, archived_at = NULL WHERE project_id = ?", (project_id,))
        conn.execute("UPDATE experiments SET worktree_state = 'removed' WHERE exp_id = ?", (exp_id,))
    assert run(submit_args) == 4
    removed_worktree_err = capsys.readouterr().err
    assert _field_labels(removed_worktree_err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in removed_worktree_err
    assert "experiment worktree is removed" in removed_worktree_err
    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute("UPDATE experiments SET worktree_state = 'active' WHERE exp_id = ?", (exp_id,))

    assert run(submit_args) == 0
    submit_out = capsys.readouterr().out
    assert _field_labels(submit_out) == _submission_field_labels()
    assert "submit accepted: true" in submit_out
    with sqlite3.connect(home / "alab.db") as conn:
        stored_summary, stored_feedback, refs_json = conn.execute("SELECT summary, feedback, refs_json FROM experiment_submissions").fetchone()
    assert stored_summary == exact_body
    assert stored_feedback == exact_body
    assert json.loads(refs_json) == {"schema_version": 1, "refs": ["none"]}
    assert run(submit_args) == 4
    closed_exp_err = capsys.readouterr().err
    assert _field_labels(closed_exp_err) == _error_field_labels()
    assert "error code: EXPERIMENT_CLOSED" in closed_exp_err


def test_submit_result_failures_and_input_preflight(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("ok")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Submit Failure Project"
task = "Keep submit failures structured"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    monkeypatch.setattr(sys, "stdin", io.StringIO("active-secret\n"))
    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "set", "--project", project_id, "API_TOKEN", "--value-stdin"]) == 0
    capsys.readouterr()
    peer_worktree = tmp_path / "submit-peer"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "submit-peer", "--path", str(peer_worktree)]) == 0
    peer_exp_id = _field(capsys.readouterr().out, "exp id")
    worktree = tmp_path / "submit-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "submit-failure", "--path", str(worktree), "--visibility-scope", "none"]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")

    monkeypatch.chdir(worktree)
    summary_file = tmp_path / "summary.txt"
    summary_file.write_text("from file\n", encoding="utf-8")
    long_summary_file = tmp_path / "long-summary.txt"
    long_summary_file.write_text("界" * 21846, encoding="utf-8")
    long_feedback_file = tmp_path / "long-feedback.txt"
    long_feedback_file.write_text("界" * 21846, encoding="utf-8")
    (worktree / "main.py").write_text("import sys\nsys.exit(9)\n", encoding="utf-8")

    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "done", "--feedback", "ok"]) == 2
    assert "submit requires at least one --ref" in capsys.readouterr().err
    assert (
        run(
            [
                "--home",
                str(home),
                "submit",
                "--message",
                "invalid",
                "--summary",
                "done",
                "--summary-file",
                str(summary_file),
                "--feedback",
                "ok",
                "--ref",
                "none",
            ]
        )
        == 2
    )
    assert "submit requires exactly one of --summary or --summary-file" in capsys.readouterr().err
    missing_summary_a = tmp_path / "missing-summary-a.txt"
    missing_summary_b = tmp_path / "missing-summary-b.txt"
    missing_feedback_a = tmp_path / "missing-feedback-a.txt"
    missing_feedback_b = tmp_path / "missing-feedback-b.txt"
    duplicate_submit_inputs = [
        (
            ["--summary", "one", "--summary", "two", "--feedback", "ok"],
            "--summary may be provided once",
        ),
        (
            ["--summary-file", str(missing_summary_a), "--summary-file", str(missing_summary_b), "--feedback", "ok"],
            "--summary-file may be provided once",
        ),
        (
            ["--summary", "done", "--feedback", "one", "--feedback", "two"],
            "--feedback may be provided once",
        ),
        (
            ["--summary", "done", "--feedback-file", str(missing_feedback_a), "--feedback-file", str(missing_feedback_b)],
            "--feedback-file may be provided once",
        ),
    ]
    for input_args, message in duplicate_submit_inputs:
        assert run(["--home", str(home), "submit", "--message", "invalid", *input_args, "--ref", "none"]) == 2
        duplicate_input_err = capsys.readouterr().err
        assert _field_labels(duplicate_input_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_input_err
        assert message in duplicate_input_err
        assert "No such file" not in duplicate_input_err
        with sqlite3.connect(home / "alab.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM runs WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
    duplicate_submit_single_options = [
        (
            ["--message", "first", "--message", "second", "--summary", "done", "--feedback", "ok", "--ref", "none"],
            "--message may be provided once",
        ),
        (
            ["--message", "invalid", "--summary", "done", "--feedback", "ok", "--ref", "none", "--rerun", "--rerun"],
            "--rerun may be provided once",
        ),
    ]
    for input_args, message in duplicate_submit_single_options:
        assert run(["--home", str(home), "submit", *input_args]) == 2
        duplicate_single_err = capsys.readouterr().err
        assert _field_labels(duplicate_single_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_single_err
        assert message in duplicate_single_err
        with sqlite3.connect(home / "alab.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM runs WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
    for stdin_flag in ("--summary-stdin", "--feedback-stdin"):
        assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "done", "--feedback", "ok", "--ref", "none", stdin_flag]) == 2
        stdin_err = capsys.readouterr().err
        assert _field_labels(stdin_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in stdin_err
        assert f"{stdin_flag} is not supported" in stdin_err
        with sqlite3.connect(home / "alab.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM runs WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
    missing_submit_files = [
        (
            ["--summary-file", str(tmp_path / "missing-submit-summary.txt"), "--feedback", "ok"],
            "submit summary file not found",
        ),
        (
            ["--summary", "done", "--feedback-file", str(tmp_path / "missing-submit-feedback.txt")],
            "submit feedback file not found",
        ),
    ]
    for input_args, expected_reason in missing_submit_files:
        assert run(["--home", str(home), "submit", "--message", "invalid", *input_args, "--ref", "none"]) == 2
        missing_file_err = capsys.readouterr().err
        assert _field_labels(missing_file_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in missing_file_err
        assert expected_reason in missing_file_err
        assert "No such file" not in missing_file_err
        with sqlite3.connect(home / "alab.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM runs WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM experiment_submissions WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
    assert run(["--home", str(home), "run", "--message", "x" * 301]) == 2
    assert "run message exceeds 300 bytes" in capsys.readouterr().err
    assert run(["--home", str(home), "run", "--message", "first", "--message", "second"]) == 2
    duplicate_run_message_err = capsys.readouterr().err
    assert _field_labels(duplicate_run_message_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_run_message_err
    assert "--message may be provided once" in duplicate_run_message_err
    assert run(["--home", str(home), "run", "--message", "界" * 101]) == 2
    assert "run message exceeds 300 bytes" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "x" * 301, "--summary", "done", "--feedback", "ok", "--ref", "none"]) == 2
    assert "submit message exceeds 300 bytes" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "界" * 101, "--summary", "done", "--feedback", "ok", "--ref", "none"]) == 2
    assert "submit message exceeds 300 bytes" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "x" * 65537, "--feedback", "ok", "--ref", "none"]) == 2
    assert "submit summary exceeds 65536 bytes" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "界" * 21846, "--feedback", "ok", "--ref", "none"]) == 2
    assert "submit summary exceeds 65536 bytes" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary-file", str(long_summary_file), "--feedback", "ok", "--ref", "none"]) == 2
    assert "submit summary exceeds 65536 bytes" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "done", "--feedback", "x" * 65537, "--ref", "none"]) == 2
    assert "submit feedback exceeds 65536 bytes" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "done", "--feedback", "界" * 21846, "--ref", "none"]) == 2
    assert "submit feedback exceeds 65536 bytes" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "done", "--feedback-file", str(long_feedback_file), "--ref", "none"]) == 2
    assert "submit feedback exceeds 65536 bytes" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "contains active-secret", "--feedback", "ok", "--ref", "none"]) == 2
    assert "submit summary contains an active secret value" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "done", "--feedback", "ok", "--ref"]) == 2
    assert "--ref requires a value" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "done", "--feedback", "ok", "--ref", "--rerun"]) == 2
    assert "--ref requires a value" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "done", "--feedback", "ok", "--ref", "none", "--ref", peer_exp_id]) == 2
    assert "--ref none conflicts with experiment refs" in capsys.readouterr().err
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "done", "--feedback", "ok", "--ref", peer_exp_id]) == 4
    invisible_ref_err = capsys.readouterr().err
    assert "error code: SCOPE_VIOLATION" in invisible_ref_err
    assert "not visible or not found" in invisible_ref_err
    missing_ref_id = "exp-missing-" + "R" * 22
    assert run(["--home", str(home), "submit", "--message", "invalid", "--summary", "done", "--feedback", "ok", "--ref", missing_ref_id]) == 4
    missing_ref_err = capsys.readouterr().err
    assert "error code: SCOPE_VIOLATION" in missing_ref_err
    assert "not visible or not found" in missing_ref_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0

    monkeypatch.setenv("ALAB_DEBUG", "1")
    assert run(["--home", str(home), "submit", "--message", "final", "--summary", "done", "--feedback", "ok", "--ref", "none", "--rerun"]) == 1
    failed_submit = capsys.readouterr()
    failed_submit_out = failed_submit.out
    assert _field_labels(failed_submit_out) == _submission_failure_field_labels()
    assert "object: submission" in failed_submit_out
    assert "submit accepted: false" in failed_submit_out
    assert "final run id: none" in failed_submit_out
    assert "experiment status: open" in failed_submit_out
    assert "summary stored: false" in failed_submit_out
    assert "feedback stored: false" in failed_submit_out
    assert "error code: RUNNER_FAILED" in failed_submit_out
    assert "exit code: 1" in failed_submit_out
    assert "Traceback" not in failed_submit_out
    assert failed_submit.err == ""
    with sqlite3.connect(home / "alab.db") as conn:
        experiment = conn.execute("SELECT status, final_run_id, final_commit FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()
        assert experiment == ("open", None, None)
        assert conn.execute("SELECT COUNT(*) FROM experiment_submissions WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE exp_id = ? AND status = 'failed'", (exp_id,)).fetchone()[0] == 1

    _git(["restore", "main.py"], worktree)
    assert run(["--home", str(home), "submit", "--message", "missing reusable", "--summary", "done", "--feedback", "ok", "--ref", "none"]) == 1
    missing_reuse_out = capsys.readouterr().out
    assert _field_labels(missing_reuse_out) == _submission_failure_field_labels()
    assert "submit accepted: false" in missing_reuse_out
    assert "error code: RUNNER_FAILED" in missing_reuse_out
    assert "reason: no reusable passed run for current HEAD" in missing_reuse_out
    assert "next: alab submit --rerun ..." in missing_reuse_out


def test_runner_workspace_is_contextless_and_stdin_closed(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
import sys
from pathlib import Path

workspace = Path(os.environ["ALAB_WORKSPACE"])
stdin_text = sys.stdin.read()
context_exists = (workspace / ".alab" / "context.json").exists() or Path(".alab/context.json").exists()
token_exists = (workspace / ".alab" / "token").exists() or Path(".alab/token").exists()
Path(os.environ["ALAB_WORKSPACE"], "workspace-only.txt").write_text("temporary workspace", encoding="utf-8")
Path(os.environ["ALAB_RUN_DIR"], "run-only.txt").write_text("temporary run dir", encoding="utf-8")
print(f"stdin_empty={stdin_text == ''}")
print(f"context_exists={context_exists}")
print(f"token_exists={token_exists}")
sys.exit(0 if stdin_text == "" and not context_exists and not token_exists else 9)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Runner Isolation"
task = "Keep runner workspace contextless"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert (
        run(
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
        == 0
    )
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    validation_id = _field(project_out, "validation id")

    worktree = tmp_path / "runner-isolation-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "runner isolation",
                "--path",
                str(worktree),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (worktree / ".alab" / "context.json").is_file()
    assert (worktree / ".alab" / "token").is_file()
    assert not (home / "tmp" / project_id / validation_id).exists()
    _assert_project_tmp_clean(home, project_id)
    head_before_run = _git(["rev-parse", "HEAD"], worktree)
    _assert_worktree_clean(worktree)

    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "runner isolation"]) == 0
    run_out = capsys.readouterr().out
    run_id = _field(run_out, "run id")
    assert "run status: passed" in run_out
    assert "reward parse status: parsed" in run_out
    assert not (home / "tmp" / project_id / run_id).exists()
    _assert_project_tmp_clean(home, project_id)
    assert _git(["rev-parse", "HEAD"], worktree) == head_before_run
    assert not (worktree / "workspace-only.txt").exists()
    assert not (worktree / "run-only.txt").exists()
    _assert_worktree_clean(worktree)


def test_artifact_capture_errors_are_warning_codes_for_validations_and_runs(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("ok")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Artifact Capture Warnings"
task = "Keep artifact capture errors visible"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    def fake_capture_artifacts(*, config, workspace, run_dir, artifact_store, project_id, exp_id, run_id, validation_id):
        object_id = run_id or validation_id
        return [
            {
                "artifact_id": services.new_id("art", "capture-error"),
                "root": "run",
                "relative_path": f"{object_id}.txt",
                "size_bytes": None,
                "content_hash": None,
                "status": "error",
                "blob_path": None,
                "capture_error": "injected capture error",
            }
        ]

    monkeypatch.setattr(services, "capture_artifacts", fake_capture_artifacts)

    assert run(["--home", str(home), "--key", admin_key, "project", "validate", "--project", project_id]) == 0
    validation_out = capsys.readouterr().out
    validation_id = _field(validation_out, "validation id")
    assert _field_labels(validation_out) == _project_validation_field_labels(warning_count=1)
    assert "warning code: ARTIFACT_CAPTURE_ERROR" in validation_out

    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "runner.timeout_seconds", "31", "--project", project_id]) == 0
    config_set_out = capsys.readouterr().out
    assert _field_labels(config_set_out) == _project_config_set_field_labels(warning_count=1)
    assert "validation status: passed" in config_set_out
    assert "warning code: ARTIFACT_CAPTURE_ERROR" in config_set_out

    worktree = tmp_path / "capture-warning-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "capture warning", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "capture warning"]) == 0
    run_out = capsys.readouterr().out
    run_id = _field(run_out, "run id")
    assert _field_labels(run_out) == _run_field_labels(warning_count=1)
    assert "artifact count: 1" in run_out
    assert "warning code: ARTIFACT_CAPTURE_ERROR" in run_out

    assert run(["--home", str(home), "runs", "show", run_id]) == 0
    run_show = capsys.readouterr().out
    assert "warning code: ARTIFACT_CAPTURE_ERROR" in run_show

    with sqlite3.connect(home / "alab.db") as conn:
        validation_record = json.loads(conn.execute("SELECT record_json FROM project_validations WHERE validation_id = ?", (validation_id,)).fetchone()[0])
        run_record = json.loads(conn.execute("SELECT record_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()[0])
        validation_artifact = conn.execute("SELECT status, capture_error FROM artifacts WHERE validation_id = ?", (validation_id,)).fetchone()
        run_artifact = conn.execute("SELECT status, capture_error FROM artifacts WHERE run_id = ?", (run_id,)).fetchone()
    assert validation_record["warnings"] == ["ARTIFACT_CAPTURE_ERROR"]
    assert run_record["warnings"] == ["ARTIFACT_CAPTURE_ERROR"]
    assert validation_artifact == ("error", "injected capture error")
    assert run_artifact == ("error", "injected capture error")


def test_oversized_artifacts_are_skipped_without_failing_validation_or_run(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    oversized_text = "large-data\n"
    (source / "main.py").write_text(
        f"""
import os
from pathlib import Path

Path(os.environ["ALAB_RUN_DIR"], "big.txt").write_text({oversized_text!r}, encoding="utf-8")
print("runner completed")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.oversized-artifact.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Oversized Artifact"
task = "Skip oversized artifacts"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:big.txt"]
per_file_limit_bytes = 4
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "validation status: passed" in project_out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    validation_id = _field(project_out, "validation id")

    assert run(["--home", str(home), "--key", admin_key, "artifacts", "list", "--project", project_id, "--validation", validation_id, "--status", "skipped"]) == 0
    validation_artifacts_out = capsys.readouterr().out
    assert _field_labels(validation_artifacts_out) == _artifact_field_labels()
    validation_artifact_id = _field(validation_artifacts_out, "artifact id")
    assert f"validation id: {validation_id}" in validation_artifacts_out
    assert "run id: none" in validation_artifacts_out
    assert "path: big.txt" in validation_artifacts_out
    assert "status: skipped" in validation_artifacts_out
    assert f"size bytes: {len(oversized_text.encode('utf-8'))}" in validation_artifacts_out
    assert "content hash: none" in validation_artifacts_out
    validation_export = tmp_path / "validation-big.txt"
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "export", validation_artifact_id, "--project", project_id, "--out", str(validation_export)]) == 2
    validation_export_err = capsys.readouterr().err
    assert _field_labels(validation_export_err) == _error_field_labels()
    assert "error code: ARTIFACT_NOT_FOUND" in validation_export_err
    assert "artifact bytes were not captured" in validation_export_err
    assert not validation_export.exists()

    worktree = tmp_path / "oversized-artifact-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "oversized artifact", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "skip oversized artifact"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels()
    run_id = _field(run_out, "run id")
    assert "run status: passed" in run_out
    assert "artifact count: 1" in run_out
    assert "warning code:" not in run_out

    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--status", "captured"]) == 0
    assert _field_labels(capsys.readouterr().out) == []
    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--status", "skipped"]) == 0
    run_artifacts_out = capsys.readouterr().out
    assert _field_labels(run_artifacts_out) == _artifact_field_labels()
    run_artifact_id = _field(run_artifacts_out, "artifact id")
    assert f"run id: {run_id}" in run_artifacts_out
    assert "validation id: none" in run_artifacts_out
    assert "path: big.txt" in run_artifacts_out
    assert "status: skipped" in run_artifacts_out
    assert f"size bytes: {len(oversized_text.encode('utf-8'))}" in run_artifacts_out
    assert "content hash: none" in run_artifacts_out
    run_export = tmp_path / "run-big.txt"
    assert run(["--home", str(home), "artifacts", "export", run_artifact_id, "--out", str(run_export)]) == 2
    run_export_err = capsys.readouterr().err
    assert _field_labels(run_export_err) == _error_field_labels()
    assert "error code: ARTIFACT_NOT_FOUND" in run_export_err
    assert "artifact bytes were not captured" in run_export_err
    assert not run_export.exists()


def test_artifact_directory_globs_expand_sort_deduplicate_and_export(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "workspace-note.txt").write_text("validation-workspace", encoding="utf-8")
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

outputs = Path(os.environ["ALAB_RUN_DIR"], "outputs")
(outputs / "nested").mkdir(parents=True, exist_ok=True)
(outputs / "nested" / "a.txt").write_text("validation-a", encoding="utf-8")
(outputs / "z.txt").write_text("validation-z", encoding="utf-8")
print("runner completed")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.artifact-directory.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Artifact Directory Expansion"
task = "Expand artifact directories"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:outputs/z.txt", "run:outputs/nested/a.txt", "run:outputs", "workspace-note.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "validation status: passed" in project_out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    validation_id = _field(project_out, "validation id")

    assert run(["--home", str(home), "--key", admin_key, "artifacts", "list", "--project", project_id, "--validation", validation_id, "--status", "captured", "--sort", "path:asc"]) == 0
    validation_artifacts = capsys.readouterr().out
    assert all(labels == _artifact_field_labels() for labels in _block_labels(validation_artifacts))
    assert re.findall(r"^path: (.+)$", validation_artifacts, re.MULTILINE) == ["outputs/nested/a.txt", "outputs/z.txt", "workspace-note.txt"]
    assert validation_artifacts.count("object: artifact") == 3
    assert "content hash: sha256:" in validation_artifacts
    with sqlite3.connect(home / "alab.db") as conn:
        validation_rows = conn.execute(
            "SELECT relative_path, root, COUNT(*) FROM artifacts WHERE validation_id = ? GROUP BY relative_path, root ORDER BY relative_path",
            (validation_id,),
        ).fetchall()
    assert validation_rows == [("outputs/nested/a.txt", "run", 1), ("outputs/z.txt", "run", 1), ("workspace-note.txt", "workspace", 1)]

    worktree = tmp_path / "artifact-directory-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "artifact directory", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    (worktree / "workspace-note.txt").write_text("run-workspace", encoding="utf-8")
    (worktree / "main.py").write_text(
        """
import os
from pathlib import Path

outputs = Path(os.environ["ALAB_RUN_DIR"], "outputs")
(outputs / "nested").mkdir(parents=True, exist_ok=True)
(outputs / "nested" / "a.txt").write_text("run-a", encoding="utf-8")
(outputs / "z.txt").write_text("run-z", encoding="utf-8")
print("runner completed")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "run", "--message", "capture directory artifacts"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels()
    run_id = _field(run_out, "run id")
    assert "run status: passed" in run_out
    assert "artifact count: 3" in run_out
    assert "warning code:" not in run_out

    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--status", "captured", "--sort", "path:asc"]) == 0
    run_artifacts = capsys.readouterr().out
    assert all(labels == _artifact_field_labels() for labels in _block_labels(run_artifacts))
    assert re.findall(r"^path: (.+)$", run_artifacts, re.MULTILINE) == ["outputs/nested/a.txt", "outputs/z.txt", "workspace-note.txt"]
    assert run_artifacts.count("object: artifact") == 3
    with sqlite3.connect(home / "alab.db") as conn:
        run_rows = conn.execute(
            "SELECT relative_path, root, artifact_id FROM artifacts WHERE run_id = ? ORDER BY relative_path",
            (run_id,),
        ).fetchall()
    assert [(row[0], row[1]) for row in run_rows] == [("outputs/nested/a.txt", "run"), ("outputs/z.txt", "run"), ("workspace-note.txt", "workspace")]
    for relative_path, _root, artifact_id in run_rows:
        export = tmp_path / relative_path.replace("/", "-")
        assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(export)]) == 0
        capsys.readouterr()
        if relative_path.endswith("a.txt"):
            expected = "run-a"
        elif relative_path.endswith("z.txt"):
            expected = "run-z"
        else:
            expected = "run-workspace"
        assert export.read_text(encoding="utf-8") == expected


def test_log_secret_redaction_happens_before_truncation(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
import sys

secret = os.environ["API_TOKEN"]
print(f"prefix {secret} suffix")
print(f"prefix {secret} suffix", file=sys.stderr)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.redact-before-truncate.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Redact Before Truncate"
task = "Redact secrets before log truncation"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[logs]
stdout_limit_bytes = 17
stderr_limit_bytes = 17

[secret_env]
API_TOKEN = "artifact-secret"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    expected_log_bytes = b"prefix [REDACTED]"
    expected_full_redacted_log_bytes = b"prefix [REDACTED] suffix\n"
    expected_log_hash = "sha256:" + hashlib.sha256(expected_log_bytes).hexdigest()

    def assert_log_preview(args: list[str], *, stream: str, owner_field: str, owner_id: str) -> str:
        assert run(args) == 0
        out = capsys.readouterr().out
        assert _field_labels(out) == _log_field_labels()
        log_id = _field(out, "log id")
        assert f"{owner_field}: {owner_id}" in out
        assert f"stream: {stream}" in out
        assert f"stored bytes: {len(expected_log_bytes)}" in out
        assert "truncated: true" in out
        assert "preview: prefix [REDACTED]" in out
        assert "artifact" not in out
        assert "secret" not in out.replace("[REDACTED]", "")
        return log_id

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "validation status: passed" in project_out
    assert "artifact-secret" not in project_out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    validation_id = _field(project_out, "validation id")

    validation_stdout_log_id = assert_log_preview(
        ["--home", str(home), "--key", admin_key, "logs", "list", "--project", project_id, "--validation", validation_id, "--stream", "stdout", "--truncated", "true"],
        stream="stdout",
        owner_field="validation id",
        owner_id=validation_id,
    )
    validation_stderr_log_id = assert_log_preview(
        ["--home", str(home), "--key", admin_key, "logs", "list", "--project", project_id, "--validation", validation_id, "--stream", "stderr", "--truncated", "true"],
        stream="stderr",
        owner_field="validation id",
        owner_id=validation_id,
    )
    for stream, log_id in [("stdout", validation_stdout_log_id), ("stderr", validation_stderr_log_id)]:
        export = tmp_path / f"validation-{stream}.log"
        assert run(["--home", str(home), "--key", admin_key, "logs", "export", log_id, "--project", project_id, "--out", str(export)]) == 0
        capsys.readouterr()
        assert export.read_bytes() == expected_log_bytes
        assert run(["--home", str(home), "--key", admin_key, "logs", "show", log_id, "--project", project_id]) == 0
        validation_log_show = capsys.readouterr().out
        assert _field_labels(validation_log_show) == _log_show_field_labels()
        assert "content:" in validation_log_show
        assert "  prefix [REDACTED]" in validation_log_show
        assert "suffix" not in validation_log_show

    worktree = tmp_path / "redact-before-truncate-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "redact before truncate", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "redact before truncate"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels()
    run_id = _field(run_out, "run id")
    assert "stdout preview: prefix [REDACTED]" in run_out
    assert "stderr preview: prefix [REDACTED]" in run_out
    assert "artifact-secret" not in run_out

    run_stdout_log_id = assert_log_preview(
        ["--home", str(home), "logs", "list", "--run", run_id, "--stream", "stdout", "--truncated", "true"],
        stream="stdout",
        owner_field="run id",
        owner_id=run_id,
    )
    run_stderr_log_id = assert_log_preview(
        ["--home", str(home), "logs", "list", "--run", run_id, "--stream", "stderr", "--truncated", "true"],
        stream="stderr",
        owner_field="run id",
        owner_id=run_id,
    )
    for stream, log_id in [("stdout", run_stdout_log_id), ("stderr", run_stderr_log_id)]:
        export = tmp_path / f"run-{stream}.log"
        assert run(["--home", str(home), "logs", "export", log_id, "--out", str(export)]) == 0
        capsys.readouterr()
        assert export.read_bytes() == expected_log_bytes
        assert run(["--home", str(home), "logs", "show", log_id]) == 0
        run_log_show = capsys.readouterr().out
        assert _field_labels(run_log_show) == _log_show_field_labels()
        assert "content:" in run_log_show
        assert "  prefix [REDACTED]" in run_log_show
        assert "suffix" not in run_log_show

    with sqlite3.connect(home / "alab.db") as conn:
        stored_logs = conn.execute(
            """
            SELECT stream, size_bytes, stored_bytes, content_hash, preview_text
            FROM log_streams
            WHERE log_id IN (?, ?, ?, ?)
            ORDER BY validation_id IS NULL, stream
            """,
            (validation_stdout_log_id, validation_stderr_log_id, run_stdout_log_id, run_stderr_log_id),
        ).fetchall()
    assert stored_logs == [
        ("stderr", len(expected_full_redacted_log_bytes), len(expected_log_bytes), expected_log_hash, expected_log_bytes.decode("utf-8")),
        ("stdout", len(expected_full_redacted_log_bytes), len(expected_log_bytes), expected_log_hash, expected_log_bytes.decode("utf-8")),
        ("stderr", len(expected_full_redacted_log_bytes), len(expected_log_bytes), expected_log_hash, expected_log_bytes.decode("utf-8")),
        ("stdout", len(expected_full_redacted_log_bytes), len(expected_log_bytes), expected_log_hash, expected_log_bytes.decode("utf-8")),
    ]


def test_global_preview_bytes_controls_validation_and_run_log_previews(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    stdout_text = "alpha-preview-full\n"
    stderr_text = "bravo-preview-full\n"
    (source / "main.py").write_text(
        f"""
import sys

print({stdout_text!r}, end="")
print({stderr_text!r}, end="", file=sys.stderr)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.preview-bytes.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Preview Bytes"
task = "Respect global log preview length"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    def assert_single_log(args: list[str], *, stream: str, expected_preview: str, forbidden_prefix: str) -> str:
        assert run(args) == 0
        out = capsys.readouterr().out
        assert _field_labels(out) == _log_field_labels()
        assert f"stream: {stream}" in out
        assert f"preview: {expected_preview}" in out
        assert f"preview: {forbidden_prefix}" not in out
        assert "truncated: false" in out
        return _field(out, "log id")

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "config", "set", "output.preview_bytes", "7"]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "validation status: passed" in project_out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    validation_id = _field(project_out, "validation id")

    validation_stdout_log_id = assert_single_log(
        ["--home", str(home), "--key", admin_key, "logs", "list", "--project", project_id, "--validation", validation_id, "--stream", "stdout"],
        stream="stdout",
        expected_preview="alpha-p",
        forbidden_prefix="alpha-pr",
    )
    validation_stderr_log_id = assert_single_log(
        ["--home", str(home), "--key", admin_key, "logs", "list", "--project", project_id, "--validation", validation_id, "--stream", "stderr"],
        stream="stderr",
        expected_preview="bravo-p",
        forbidden_prefix="bravo-pr",
    )

    worktree = tmp_path / "preview-bytes-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "preview bytes", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "preview bytes"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels()
    run_id = _field(run_out, "run id")
    assert "stdout preview: alpha-p" in run_out
    assert "stdout preview: alpha-pr" not in run_out
    assert "stderr preview: bravo-p" in run_out
    assert "stderr preview: bravo-pr" not in run_out

    run_stdout_log_id = assert_single_log(
        ["--home", str(home), "logs", "list", "--run", run_id, "--stream", "stdout"],
        stream="stdout",
        expected_preview="alpha-p",
        forbidden_prefix="alpha-pr",
    )
    run_stderr_log_id = assert_single_log(
        ["--home", str(home), "logs", "list", "--run", run_id, "--stream", "stderr"],
        stream="stderr",
        expected_preview="bravo-p",
        forbidden_prefix="bravo-pr",
    )

    with sqlite3.connect(home / "alab.db") as conn:
        stored_logs = conn.execute(
            """
            SELECT stream, size_bytes, stored_bytes, truncated, preview_text
            FROM log_streams
            WHERE log_id IN (?, ?, ?, ?)
            ORDER BY validation_id IS NULL, stream
            """,
            (validation_stdout_log_id, validation_stderr_log_id, run_stdout_log_id, run_stderr_log_id),
        ).fetchall()
    assert stored_logs == [
        ("stderr", len(stderr_text.encode("utf-8")), len(stderr_text.encode("utf-8")), 0, "bravo-p"),
        ("stdout", len(stdout_text.encode("utf-8")), len(stdout_text.encode("utf-8")), 0, "alpha-p"),
        ("stderr", len(stderr_text.encode("utf-8")), len(stderr_text.encode("utf-8")), 0, "bravo-p"),
        ("stdout", len(stdout_text.encode("utf-8")), len(stdout_text.encode("utf-8")), 0, "alpha-p"),
    ]


def test_annotation_path_targets_resolve_commits_and_reject_dirty_shorthand(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

print('annotate')
Path(os.environ["ALAB_RUN_DIR"], "note.txt").write_text("artifact note", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (source / "pkg" / "mod.py").write_text("value = 1\n", encoding="utf-8")
    config = tmp_path / "alab.annotation-targets.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Annotation Targets"
task = "Resolve annotation path targets"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:note.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    worktree = tmp_path / "annotation-targets-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "targeted", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "target baseline"]) == 0
    run_out = capsys.readouterr().out
    assert "run status: passed" in run_out
    run_id = _field(run_out, "run id")
    head_commit = _git(["rev-parse", "HEAD"], worktree)
    with sqlite3.connect(home / "alab.db") as conn:
        artifact_id = conn.execute(
            "SELECT artifact_id FROM artifacts WHERE run_id = ? AND relative_path = 'note.txt'",
            (run_id,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE experiments SET final_run_id = ?, final_commit = ? WHERE exp_id = ?",
            (run_id, head_commit, exp_id),
        )
        conn.commit()

    for target, expected_type, expected_id, expected_commit in [
        (f"exp:{exp_id}", "experiment", exp_id, head_commit),
        (f"run:{run_id}", "run", run_id, head_commit),
        (f"artifact:{artifact_id}", "artifact", artifact_id, None),
    ]:
        assert run(["--home", str(home), "annotate", "add", "--target", target, "--body", f"{expected_type} object note"]) == 0
        object_target_out = capsys.readouterr().out
        assert _field_labels(object_target_out) == _annotation_add_field_labels()
        assert _field(object_target_out, "target type") == expected_type
        assert _field(object_target_out, "target id") == expected_id
        assert _field(object_target_out, "resolved commit") == (expected_commit or "none")
        annotation_id = _field(object_target_out, "annotation id")
        with sqlite3.connect(home / "alab.db") as conn:
            target_json = json.loads(conn.execute("SELECT target_json FROM annotations WHERE annotation_id = ?", (annotation_id,)).fetchone()[0])
        assert target_json["target_type"] == expected_type
        assert target_json["target_id"] == expected_id
        assert target_json["exp_id"] == exp_id
        assert target_json["commit"] == expected_commit

    for selector in ["HEAD", "head", "latest", "final", "best", head_commit[:12]]:
        assert run(["--home", str(home), "annotate", "add", "--target", f"path:{exp_id}@{selector}:main.py", "--body", f"{selector} path note"]) == 0
        target_out = capsys.readouterr().out
        assert _field_labels(target_out) == _annotation_add_field_labels()
        assert _field(target_out, "resolved commit") == head_commit
        annotation_id = _field(target_out, "annotation id")
        with sqlite3.connect(home / "alab.db") as conn:
            row = conn.execute(
                "SELECT target_id, target_json, resolved_commit FROM annotations WHERE annotation_id = ?",
                (annotation_id,),
            ).fetchone()
        target_json = json.loads(row[1])
        assert row[0] == f"{exp_id}:{head_commit}:main.py"
        assert row[2] == head_commit
        assert target_json["commit"] == head_commit
        assert target_json["target_id"] == f"{exp_id}:{head_commit}:main.py"

    assert run(["--home", str(home), "--key", admin_key, "annotate", "add", "--project", project_id, "--target", f"path:{exp_id}@latest:pkg", "--body", "tree path note"]) == 0
    tree_path_out = capsys.readouterr().out
    assert _field_labels(tree_path_out) == _annotation_add_field_labels()
    assert "target type: path" in tree_path_out
    invalid_targets_before = _table_count(home, "annotations")
    invalid_target_cases = [
        (f"lines:{exp_id}@latest:pkg:1-1", "line annotation target must be a file"),
        (f"lines:{exp_id}@latest:main.py:2-1", "invalid line range"),
        (f"lines:{exp_id}@latest:main.py:1-99", "line range exceeds target file length"),
        (f"path:{exp_id}@latest:../main.py", "annotation repo path must be relative"),
        (f"path:{exp_id}@latest:pkg\\mod.py", "annotation repo path must be relative"),
    ]
    for target, reason in invalid_target_cases:
        assert run(["--home", str(home), "--key", admin_key, "annotate", "add", "--project", project_id, "--target", target, "--body", "invalid target"]) == 2
        target_err = capsys.readouterr().err
        assert _field_labels(target_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in target_err
        assert reason in target_err
    assert _table_count(home, "annotations") == invalid_targets_before

    def assert_dirty_shorthand_rejected(name: str, mutate) -> None:
        _git(["reset", "--hard", "HEAD"], worktree)
        _git(["clean", "-fd", "-e", ".alab"], worktree)
        before_annotations = _table_count(home, "annotations")
        mutate()
        assert (
            run(
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
                    f"{name} dirty note",
                ]
            )
            == 4
        )
        dirty_err = capsys.readouterr().err
        assert _field_labels(dirty_err) == _error_field_labels()
        assert "error code: GIT_STATE_INVALID" in dirty_err
        assert "path/line annotation shorthand requires a clean experiment worktree" in dirty_err
        assert _table_count(home, "annotations") == before_annotations
        _git(["reset", "--hard", "HEAD"], worktree)
        _git(["clean", "-fd", "-e", ".alab"], worktree)

    assert_dirty_shorthand_rejected(
        "staged",
        lambda: ((worktree / "main.py").write_text("print('staged')\n", encoding="utf-8"), _git(["add", "main.py"], worktree)),
    )
    assert_dirty_shorthand_rejected(
        "unstaged",
        lambda: (worktree / "main.py").write_text("print('unstaged')\n", encoding="utf-8"),
    )
    assert_dirty_shorthand_rejected("deleted", lambda: (worktree / "main.py").unlink())
    assert_dirty_shorthand_rejected("renamed", lambda: _git(["mv", "main.py", "renamed.py"], worktree))
    assert_dirty_shorthand_rejected(
        "copied",
        lambda: (shutil.copyfile(worktree / "main.py", worktree / "copy.py"), _git(["add", "copy.py"], worktree)),
    )
    assert_dirty_shorthand_rejected(
        "untracked",
        lambda: (worktree / "untracked.py").write_text("print('untracked')\n", encoding="utf-8"),
    )
    assert run(["--home", str(home), "annotate", "add", "--target", "lines:main.py:1-1", "--body", "clean shorthand works"]) == 0
    clean_shorthand_out = capsys.readouterr().out
    assert _field_labels(clean_shorthand_out) == _annotation_add_field_labels()
    assert _field(clean_shorthand_out, "resolved commit") == head_commit


def test_artifact_symlink_escape_is_skipped_without_failing_validation_or_run(tmp_path, monkeypatch, capsys) -> None:
    probe_target = tmp_path / "probe-target.txt"
    probe_link = tmp_path / "probe-link.txt"
    probe_target.write_text("probe\n", encoding="utf-8")
    try:
        probe_link.symlink_to(probe_target)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    home = tmp_path / "home"
    source = tmp_path / "source"
    outside = tmp_path / "outside"
    source.mkdir()
    outside.mkdir()
    outside_file = outside / "leak.txt"
    outside_file.write_text("outside bytes\n", encoding="utf-8")
    (source / "main.py").write_text(
        f"""
import os
from pathlib import Path

link = Path(os.environ["ALAB_RUN_DIR"], "leak.txt")
if link.exists() or link.is_symlink():
    link.unlink()
link.symlink_to(Path({json.dumps(str(outside_file))}))
print("runner completed")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.symlink-artifact.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Symlink Artifact"
task = "Skip escaping artifact symlinks"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:leak.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "validation status: passed" in project_out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    validation_id = _field(project_out, "validation id")

    assert run(["--home", str(home), "--key", admin_key, "artifacts", "list", "--project", project_id, "--validation", validation_id, "--status", "captured"]) == 0
    assert _field_labels(capsys.readouterr().out) == []
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "list", "--project", project_id, "--validation", validation_id, "--status", "skipped"]) == 0
    validation_artifacts_out = capsys.readouterr().out
    assert _field_labels(validation_artifacts_out) == _artifact_field_labels()
    validation_artifact_id = _field(validation_artifacts_out, "artifact id")
    assert f"validation id: {validation_id}" in validation_artifacts_out
    assert "run id: none" in validation_artifacts_out
    assert "path: leak.txt" in validation_artifacts_out
    assert "status: skipped" in validation_artifacts_out
    assert "size bytes: none" in validation_artifacts_out
    assert "content hash: none" in validation_artifacts_out
    validation_export = tmp_path / "validation-leak.txt"
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "export", validation_artifact_id, "--project", project_id, "--out", str(validation_export)]) == 2
    validation_export_err = capsys.readouterr().err
    assert _field_labels(validation_export_err) == _error_field_labels()
    assert "error code: ARTIFACT_NOT_FOUND" in validation_export_err
    assert "artifact bytes were not captured" in validation_export_err
    assert not validation_export.exists()

    worktree = tmp_path / "symlink-artifact-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "symlink artifact", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "skip escaping symlink artifact"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels()
    run_id = _field(run_out, "run id")
    assert "run status: passed" in run_out
    assert "artifact count: 1" in run_out
    assert "warning code:" not in run_out

    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--status", "captured"]) == 0
    assert _field_labels(capsys.readouterr().out) == []
    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--status", "skipped"]) == 0
    run_artifacts_out = capsys.readouterr().out
    assert _field_labels(run_artifacts_out) == _artifact_field_labels()
    run_artifact_id = _field(run_artifacts_out, "artifact id")
    assert f"run id: {run_id}" in run_artifacts_out
    assert "validation id: none" in run_artifacts_out
    assert "path: leak.txt" in run_artifacts_out
    assert "status: skipped" in run_artifacts_out
    assert "size bytes: none" in run_artifacts_out
    assert "content hash: none" in run_artifacts_out
    run_export = tmp_path / "run-leak.txt"
    assert run(["--home", str(home), "artifacts", "export", run_artifact_id, "--out", str(run_export)]) == 2
    run_export_err = capsys.readouterr().err
    assert _field_labels(run_export_err) == _error_field_labels()
    assert "error code: ARTIFACT_NOT_FOUND" in run_export_err
    assert "artifact bytes were not captured" in run_export_err
    assert not run_export.exists()


def test_non_passed_runs_still_capture_available_artifacts(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

run_dir = Path(os.environ["ALAB_RUN_DIR"])
(run_dir / "artifact.txt").write_text("baseline artifact", encoding="utf-8")
(run_dir / "reward.txt").write_text("1.0", encoding="utf-8")
print("baseline completed")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.non-passed-artifacts.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Non Passed Artifacts"
task = "Capture artifacts on non-passed runs"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 1
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "file"
direction = "maximize"
primary_metric = "reward"
path = "run:reward.txt"

[artifacts]
globs = ["run:artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "validation status: passed" in project_out
    project_id = _field(project_out, "project id")

    worktree = tmp_path / "non-passed-artifacts-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "non-passed artifacts", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)

    def assert_captured_artifact(run_id: str, expected_text: str, export_name: str) -> None:
        assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--status", "captured"]) == 0
        artifacts_out = capsys.readouterr().out
        assert _field_labels(artifacts_out) == _artifact_field_labels()
        artifact_id = _field(artifacts_out, "artifact id")
        assert f"run id: {run_id}" in artifacts_out
        assert "validation id: none" in artifacts_out
        assert "path: artifact.txt" in artifacts_out
        assert "status: captured" in artifacts_out
        assert f"size bytes: {len(expected_text.encode('utf-8'))}" in artifacts_out
        assert "content hash: sha256:" in artifacts_out
        export_path = tmp_path / export_name
        assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(export_path)]) == 0
        capsys.readouterr()
        assert export_path.read_text(encoding="utf-8") == expected_text

    (worktree / "main.py").write_text(
        """
import os
import sys
from pathlib import Path

run_dir = Path(os.environ["ALAB_RUN_DIR"])
(run_dir / "artifact.txt").write_text("failed artifact", encoding="utf-8")
(run_dir / "reward.txt").write_text("2.0", encoding="utf-8")
print("failed run completed")
sys.exit(7)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "run", "--message", "failed artifact capture"]) == 1
    failed_out = capsys.readouterr().out
    failed_run_id = _field(failed_out, "run id")
    assert _field_labels(failed_out) == _run_field_labels(failure=True)
    assert "run status: failed" in failed_out
    assert "exit code: 7" in failed_out
    assert "reward parse status: parsed" in failed_out
    assert "artifact count: 1" in failed_out
    assert_captured_artifact(failed_run_id, "failed artifact", "failed-artifact.txt")

    (worktree / "main.py").write_text(
        """
import os
import sys
from pathlib import Path

run_dir = Path(os.environ["ALAB_RUN_DIR"])
(run_dir / "artifact.txt").write_text("failed invalid reward artifact", encoding="utf-8")
(run_dir / "reward.txt").write_text("not-a-number", encoding="utf-8")
print("failed invalid reward completed")
sys.exit(7)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "run", "--message", "failed invalid reward artifact capture"]) == 1
    failed_invalid_reward_out = capsys.readouterr().out
    failed_invalid_reward_run_id = _field(failed_invalid_reward_out, "run id")
    assert _field_labels(failed_invalid_reward_out) == _run_field_labels(failure=True)
    assert "run status: failed" in failed_invalid_reward_out
    assert "exit code: 7" in failed_invalid_reward_out
    assert "reward parse status: invalid" in failed_invalid_reward_out
    assert "artifact count: 1" in failed_invalid_reward_out
    assert "error code: RUNNER_FAILED" in failed_invalid_reward_out
    assert "reason: runner exited with code 7" in failed_invalid_reward_out
    with sqlite3.connect(home / "alab.db") as conn:
        failed_invalid_reward_record = conn.execute(
            "SELECT status, exit_code, reward_value, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (failed_invalid_reward_run_id,),
        ).fetchone()
    assert failed_invalid_reward_record[:4] == ("failed", 7, None, "invalid")
    failed_invalid_reward_json = json.loads(failed_invalid_reward_record[4])
    assert failed_invalid_reward_json["reward"] == {"type": "file", "value": None}
    assert failed_invalid_reward_json["failure"] == "runner exited with code 7"
    assert_captured_artifact(failed_invalid_reward_run_id, "failed invalid reward artifact", "failed-invalid-reward-artifact.txt")

    (worktree / "main.py").write_text(
        """
import os
from pathlib import Path

run_dir = Path(os.environ["ALAB_RUN_DIR"])
(run_dir / "artifact.txt").write_text("reward-error artifact", encoding="utf-8")
(run_dir / "reward.txt").write_text("not-a-number", encoding="utf-8")
print("reward parse error completed")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "run", "--message", "reward error artifact capture"]) == 1
    reward_error_out = capsys.readouterr().out
    reward_error_run_id = _field(reward_error_out, "run id")
    assert _field_labels(reward_error_out) == _run_field_labels(failure=True)
    assert "run status: error" in reward_error_out
    assert "exit code: 0" in reward_error_out
    assert "reward parse status: invalid" in reward_error_out
    assert "artifact count: 1" in reward_error_out
    assert_captured_artifact(reward_error_run_id, "reward-error artifact", "reward-error-artifact.txt")

    (worktree / "main.py").write_text(
        """
import os
import time
from pathlib import Path

run_dir = Path(os.environ["ALAB_RUN_DIR"])
(run_dir / "artifact.txt").write_text("timeout artifact", encoding="utf-8")
(run_dir / "reward.txt").write_text("3.0", encoding="utf-8")
print("timeout run waiting", flush=True)
time.sleep(5)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "run", "--message", "timeout artifact capture"]) == 1
    timeout_out = capsys.readouterr().out
    timeout_run_id = _field(timeout_out, "run id")
    assert _field_labels(timeout_out) == _run_field_labels(failure=True)
    assert "run status: timeout" in timeout_out
    assert "exit code: none" in timeout_out
    assert "reward parse status: not_attempted" in timeout_out
    assert "artifact count: 1" in timeout_out
    assert_captured_artifact(timeout_run_id, "timeout artifact", "timeout-artifact.txt")


def test_file_reward_read_limit_is_saved_as_baseline_and_run_failure(tmp_path, monkeypatch, capsys) -> None:
    baseline_home = tmp_path / "baseline-home"
    baseline_source = tmp_path / "baseline-source"
    baseline_source.mkdir()
    (baseline_source / "main.py").write_text(
        """
import os
from pathlib import Path

Path(os.environ["ALAB_RUN_DIR"], "reward.txt").write_text("1.00", encoding="utf-8")
print("oversized baseline reward")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    baseline_config = tmp_path / "alab.baseline-reward-limit.toml"
    baseline_config.write_text(
        f"""
schema_version = 1

[project]
name = "Baseline Reward Limit"
task = "Persist oversized file reward baseline failure"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "file"
direction = "maximize"
primary_metric = "reward"
path = "run:reward.txt"

[artifacts]
per_file_limit_bytes = 3
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(baseline_home), "auth", "init"]) == 0
    baseline_root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(baseline_home), "--key", baseline_root_key, "project", "init", "local", "--config", str(baseline_config), "--source-path", str(baseline_source)]) == 1
    baseline_out = capsys.readouterr().out
    assert _field_labels(baseline_out) == _project_init_field_labels(failure=True)
    baseline_validation_id = _field(baseline_out, "validation id")
    assert "project status: invalid" in baseline_out
    assert "validation status: error" in baseline_out
    assert "error code: BASELINE_VALIDATION_FAILED" in baseline_out
    assert "reason: baseline validation status is error" in baseline_out
    with sqlite3.connect(baseline_home / "alab.db") as conn:
        baseline_row = conn.execute(
            "SELECT status, exit_code, reward_value, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (baseline_validation_id,),
        ).fetchone()
    assert baseline_row[:4] == ("error", 0, None, "invalid")
    baseline_record = json.loads(baseline_row[4])
    assert baseline_record["reward"] == {"type": "file", "value": None}
    assert baseline_record["failure"] == "reward parse status is invalid"

    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

Path(os.environ["ALAB_RUN_DIR"], "reward.txt").write_text("1.0", encoding="utf-8")
print("valid baseline reward")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.run-reward-limit.toml"
    config.write_text(baseline_config.read_text(encoding="utf-8").replace("Baseline Reward Limit", "Run Reward Limit"), encoding="utf-8")

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "project status: valid" in project_out
    project_id = _field(project_out, "project id")

    worktree = tmp_path / "file-reward-limit-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "file reward limit", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    (worktree / "main.py").write_text(
        """
import os
from pathlib import Path

Path(os.environ["ALAB_RUN_DIR"], "reward.txt").write_text("1.00", encoding="utf-8")
print("oversized run reward")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "run", "--message", "oversized file reward"]) == 1
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels(failure=True)
    run_id = _field(run_out, "run id")
    assert "run status: error" in run_out
    assert "exit code: 0" in run_out
    assert "reward parse status: invalid" in run_out
    assert "error code: REWARD_PARSE_ERROR" in run_out
    assert "reason: reward parse status is invalid" in run_out
    with sqlite3.connect(home / "alab.db") as conn:
        run_row = conn.execute(
            "SELECT status, exit_code, reward_value, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    assert run_row[:4] == ("error", 0, None, "invalid")
    run_record = json.loads(run_row[4])
    assert run_record["reward"] == {"type": "file", "value": None}
    assert run_record["failure"] == "reward parse status is invalid"

    assert run(["--home", str(home), "runs", "list", "--failure-reason-query", "reward parse status is invalid"]) == 0
    failure_filtered = capsys.readouterr().out
    assert _field_labels(failure_filtered) == [
        "object",
        "run id",
        "exp id",
        "commit",
        "run status",
        "exit code",
        "reward",
        "reward parse status",
        "config version",
        "stdout preview",
        "stderr preview",
        "artifact count",
        "log count",
        "hidden log available",
        "started at",
        "ended at",
    ]
    assert f"run id: {run_id}" in failure_filtered
    assert "run status: error" in failure_filtered
    assert "reward parse status: invalid" in failure_filtered


def test_stdout_regex_reward_truncation_is_saved_as_baseline_and_run_failure(tmp_path, monkeypatch, capsys) -> None:
    baseline_home = tmp_path / "baseline-home"
    baseline_source = tmp_path / "baseline-source"
    baseline_source.mkdir()
    (baseline_source / "main.py").write_text(
        """
print("prefix before reward=42")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    baseline_config = tmp_path / "alab.stdout-regex-truncated.toml"
    baseline_config.write_text(
        f"""
schema_version = 1

[project]
name = "Truncated Stdout Regex Reward"
task = "Persist truncated stdout regex reward failures"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "stdout_regex"
direction = "maximize"
primary_metric = "reward"
pattern = "reward=([0-9.]+)"

[logs]
stdout_limit_bytes = 8
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(baseline_home), "auth", "init"]) == 0
    baseline_root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(baseline_home), "--key", baseline_root_key, "project", "init", "local", "--config", str(baseline_config), "--source-path", str(baseline_source)]) == 1
    baseline_out = capsys.readouterr().out
    assert _field_labels(baseline_out) == _project_init_field_labels(failure=True)
    baseline_project_id = _field(baseline_out, "project id")
    baseline_validation_id = _field(baseline_out, "validation id")
    assert "project status: invalid" in baseline_out
    assert "validation status: error" in baseline_out
    assert "error code: BASELINE_VALIDATION_FAILED" in baseline_out
    assert "reason: baseline validation status is error" in baseline_out
    with sqlite3.connect(baseline_home / "alab.db") as conn:
        baseline_row = conn.execute(
            "SELECT status, exit_code, reward_value, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (baseline_validation_id,),
        ).fetchone()
    assert baseline_row[:4] == ("error", 0, None, "missing")
    baseline_record = json.loads(baseline_row[4])
    assert baseline_record["reward"] == {"type": "stdout_regex", "value": None}
    assert baseline_record["failure"] == "reward parse status is missing"
    assert run(["--home", str(baseline_home), "--key", baseline_root_key, "logs", "list", "--project", baseline_project_id, "--validation", baseline_validation_id, "--stream", "stdout", "--truncated", "true"]) == 0
    baseline_logs = capsys.readouterr().out
    assert _field_labels(baseline_logs) == _log_field_labels()
    assert "validation id: " + baseline_validation_id in baseline_logs
    assert "truncated: true" in baseline_logs
    assert "preview: prefix b" in baseline_logs
    assert "reward=42" not in baseline_logs

    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("reward=1")\n', encoding="utf-8")
    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(baseline_config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "project status: valid" in project_out
    project_id = _field(project_out, "project id")

    worktree = tmp_path / "stdout-regex-truncated-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "stdout regex truncation", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    (worktree / "main.py").write_text('print("prefix before reward=7")\n', encoding="utf-8")
    assert run(["--home", str(home), "run", "--message", "truncated stdout reward"]) == 1
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels(failure=True)
    run_id = _field(run_out, "run id")
    assert "run status: error" in run_out
    assert "exit code: 0" in run_out
    assert "reward parse status: missing" in run_out
    assert "stdout preview: prefix b" in run_out
    assert "reward=7" not in run_out
    assert "error code: REWARD_PARSE_ERROR" in run_out
    assert "reason: reward parse status is missing" in run_out
    with sqlite3.connect(home / "alab.db") as conn:
        run_row = conn.execute(
            "SELECT status, exit_code, reward_value, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    assert run_row[:4] == ("error", 0, None, "missing")
    run_record = json.loads(run_row[4])
    assert run_record["reward"] == {"type": "stdout_regex", "value": None}
    assert run_record["failure"] == "reward parse status is missing"

    assert run(["--home", str(home), "logs", "list", "--run", run_id, "--stream", "stdout", "--truncated", "true"]) == 0
    run_logs = capsys.readouterr().out
    assert _field_labels(run_logs) == _log_field_labels()
    assert "run id: " + run_id in run_logs
    assert "truncated: true" in run_logs
    assert "preview: prefix b" in run_logs
    assert "reward=7" not in run_logs

    assert run(["--home", str(home), "runs", "list", "--failure-reason-query", "reward parse status is missing"]) == 0
    failure_filtered = capsys.readouterr().out
    assert f"run id: {run_id}" in failure_filtered
    assert "run status: error" in failure_filtered
    assert "reward parse status: missing" in failure_filtered


def test_missing_file_reward_is_saved_as_baseline_and_run_failure(tmp_path, monkeypatch, capsys) -> None:
    baseline_home = tmp_path / "baseline-home"
    baseline_source = tmp_path / "baseline-source"
    baseline_source.mkdir()
    (baseline_source / "main.py").write_text(
        """
print("missing baseline reward")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    baseline_config = tmp_path / "alab.missing-file-reward.toml"
    baseline_config.write_text(
        f"""
schema_version = 1

[project]
name = "Missing File Reward"
task = "Persist missing file reward failures"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "file"
direction = "maximize"
primary_metric = "reward"
path = "run:reward.txt"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(baseline_home), "auth", "init"]) == 0
    baseline_root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(baseline_home), "--key", baseline_root_key, "project", "init", "local", "--config", str(baseline_config), "--source-path", str(baseline_source)]) == 1
    baseline_out = capsys.readouterr().out
    assert _field_labels(baseline_out) == _project_init_field_labels(failure=True)
    baseline_validation_id = _field(baseline_out, "validation id")
    assert "project status: invalid" in baseline_out
    assert "validation status: error" in baseline_out
    assert "error code: BASELINE_VALIDATION_FAILED" in baseline_out
    assert "reason: baseline validation status is error" in baseline_out
    with sqlite3.connect(baseline_home / "alab.db") as conn:
        baseline_row = conn.execute(
            "SELECT status, exit_code, reward_value, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (baseline_validation_id,),
        ).fetchone()
    assert baseline_row[:4] == ("error", 0, None, "invalid")
    baseline_record = json.loads(baseline_row[4])
    assert baseline_record["reward"] == {"type": "file", "value": None}
    assert baseline_record["failure"] == "reward parse status is invalid"

    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

Path(os.environ["ALAB_RUN_DIR"], "reward.txt").write_text("1.0", encoding="utf-8")
print("valid reward")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(baseline_config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "project status: valid" in project_out
    project_id = _field(project_out, "project id")

    worktree = tmp_path / "missing-file-reward-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "missing file reward", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    (worktree / "main.py").write_text(
        """
print("missing run reward")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "run", "--message", "missing file reward"]) == 1
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels(failure=True)
    run_id = _field(run_out, "run id")
    assert "run status: error" in run_out
    assert "exit code: 0" in run_out
    assert "reward parse status: invalid" in run_out
    assert "error code: REWARD_PARSE_ERROR" in run_out
    assert "reason: reward parse status is invalid" in run_out
    with sqlite3.connect(home / "alab.db") as conn:
        run_row = conn.execute(
            "SELECT status, exit_code, reward_value, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    assert run_row[:4] == ("error", 0, None, "invalid")
    run_record = json.loads(run_row[4])
    assert run_record["reward"] == {"type": "file", "value": None}
    assert run_record["failure"] == "reward parse status is invalid"


def test_missing_runner_working_directory_is_saved_as_baseline_and_run_error(tmp_path, monkeypatch, capsys) -> None:
    baseline_home = tmp_path / "baseline-home"
    baseline_source = tmp_path / "baseline-source"
    baseline_source.mkdir()
    (baseline_source / "main.py").write_text('print("unused")\n', encoding="utf-8")
    baseline_config = tmp_path / "alab.missing-working-dir.toml"
    baseline_config.write_text(
        f"""
schema_version = 1

[project]
name = "Missing Working Directory"
task = "Persist missing working directory failures"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "src"
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

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
    baseline_validation_id = _field(baseline_out, "validation id")
    assert "project status: invalid" in baseline_out
    assert "validation status: error" in baseline_out
    assert "error code: BASELINE_VALIDATION_FAILED" in baseline_out
    assert "reason: baseline validation status is error" in baseline_out
    with sqlite3.connect(baseline_home / "alab.db") as conn:
        baseline_row = conn.execute(
            "SELECT status, exit_code, reward_value, reward_parse_status, record_json FROM project_validations WHERE validation_id = ?",
            (baseline_validation_id,),
        ).fetchone()
        baseline_stderr = conn.execute(
            "SELECT preview_text FROM log_streams WHERE validation_id = ? AND stream = 'stderr'",
            (baseline_validation_id,),
        ).fetchone()[0]
    assert baseline_row[:4] == ("error", None, None, "not_attempted")
    baseline_record = json.loads(baseline_row[4])
    assert baseline_record["reward"] == {"type": "exit_code", "value": None}
    assert baseline_record["failure"] == "runner working directory does not exist"
    assert baseline_stderr == "runner working directory does not exist"

    home = tmp_path / "home"
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "main.py").write_text('print("valid working dir")\n', encoding="utf-8")
    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(baseline_config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    assert _field_labels(project_out) == _project_init_field_labels()
    assert "project status: valid" in project_out
    project_id = _field(project_out, "project id")

    worktree = tmp_path / "missing-working-dir-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "missing working dir", "--path", str(worktree)]) == 0
    capsys.readouterr()
    shutil.rmtree(worktree / "src")
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "missing working dir"]) == 1
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels(failure=True)
    run_id = _field(run_out, "run id")
    assert "run status: error" in run_out
    assert "exit code: none" in run_out
    assert "reward parse status: not_attempted" in run_out
    assert "stderr preview: runner working directory does not exist" in run_out
    assert "error code: RUNNER_ERROR" in run_out
    assert "reason: runner working directory does not exist" in run_out
    with sqlite3.connect(home / "alab.db") as conn:
        run_row = conn.execute(
            "SELECT status, exit_code, reward_value, reward_parse_status, record_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        run_stderr = conn.execute(
            "SELECT preview_text FROM log_streams WHERE run_id = ? AND stream = 'stderr'",
            (run_id,),
        ).fetchone()[0]
    assert run_row[:4] == ("error", None, None, "not_attempted")
    run_record = json.loads(run_row[4])
    assert run_record["reward"] == {"type": "exit_code", "value": None}
    assert run_record["failure"] == "runner working directory does not exist"
    assert run_stderr == "runner working directory does not exist"

    assert run(["--home", str(home), "runs", "list", "--failure-reason-query", "working directory"]) == 0
    failure_filtered = capsys.readouterr().out
    assert f"run id: {run_id}" in failure_filtered
    assert "run status: error" in failure_filtered
    assert "reward parse status: not_attempted" in failure_filtered


def test_artifact_bytes_not_redacted_warning_is_persisted_and_rendered(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

secret = os.environ["API_TOKEN"]
print(f"stdout secret {secret}")
Path(os.environ["ALAB_RUN_DIR"], "secret-artifact.txt").write_text(secret, encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Artifact Bytes Warning"
task = "Warn that artifact bytes are exact"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = [{json.dumps(sys.executable)}, "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:secret-artifact.txt"]

[secret_env]
API_TOKEN = "artifact-secret"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    baseline_validation_id = _field(project_out, "validation id")
    assert _field_labels(project_out) == _project_init_field_labels(warning_count=1)
    assert "warning code: ARTIFACT_BYTES_NOT_REDACTED" in project_out
    assert "artifact-secret" not in project_out

    assert run(["--home", str(home), "--key", admin_key, "project", "validate", "--project", project_id]) == 0
    validation_out = capsys.readouterr().out
    validation_id = _field(validation_out, "validation id")
    assert _field_labels(validation_out) == _project_validation_field_labels(warning_count=1)
    assert "warning code: ARTIFACT_BYTES_NOT_REDACTED" in validation_out
    assert "artifact-secret" not in validation_out

    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "runner.timeout_seconds", "31", "--project", project_id]) == 0
    config_set_out = capsys.readouterr().out
    with sqlite3.connect(home / "alab.db") as conn:
        config_validation_id = conn.execute("SELECT active_validation_id FROM projects WHERE project_id = ?", (project_id,)).fetchone()[0]
    assert _field_labels(config_set_out) == _project_config_set_field_labels(warning_count=1)
    assert "validation status: passed" in config_set_out
    assert "warning code: ARTIFACT_BYTES_NOT_REDACTED" in config_set_out
    assert "artifact-secret" not in config_set_out

    worktree = tmp_path / "artifact-warning-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "artifact warning", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "artifact warning"]) == 0
    run_out = capsys.readouterr().out
    run_id = _field(run_out, "run id")
    assert _field_labels(run_out) == _run_field_labels(warning_count=1)
    assert "stdout preview:\n  stdout secret [REDACTED]" in run_out
    assert "artifact count: 1" in run_out
    assert "warning code: ARTIFACT_BYTES_NOT_REDACTED" in run_out
    assert "artifact-secret" not in run_out

    assert run(["--home", str(home), "runs", "show", run_id]) == 0
    run_show = capsys.readouterr().out
    assert _field_labels(run_show) == [
        "object",
        "run id",
        "exp id",
        "commit",
        "run status",
        "exit code",
        "reward",
        "reward parse status",
        "config version",
        "stdout preview",
        "stderr preview",
        "artifact count",
        "log count",
        "hidden log available",
        "started at",
        "ended at",
        "warning code",
    ]
    assert "stdout preview:\n  stdout secret [REDACTED]" in run_show
    assert "warning code: ARTIFACT_BYTES_NOT_REDACTED" in run_show
    assert "artifact-secret" not in run_show

    export_path = tmp_path / "secret-artifact.txt"
    with sqlite3.connect(home / "alab.db") as conn:
        validation_records = {
            row[0]: json.loads(row[1])["warnings"]
            for row in conn.execute(
                "SELECT validation_id, record_json FROM project_validations WHERE validation_id IN (?, ?, ?)",
                (baseline_validation_id, validation_id, config_validation_id),
            )
        }
        run_record = json.loads(conn.execute("SELECT record_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()[0])
        artifact_id = conn.execute(
            "SELECT artifact_id FROM artifacts WHERE run_id = ? AND relative_path = 'secret-artifact.txt'",
            (run_id,),
        ).fetchone()[0]
        stdout_preview = conn.execute(
            "SELECT preview_text FROM log_streams WHERE run_id = ? AND stream = 'stdout'",
            (run_id,),
        ).fetchone()[0]
    assert validation_records == {
        baseline_validation_id: ["ARTIFACT_BYTES_NOT_REDACTED"],
        validation_id: ["ARTIFACT_BYTES_NOT_REDACTED"],
        config_validation_id: ["ARTIFACT_BYTES_NOT_REDACTED"],
    }
    assert run_record["warnings"] == ["ARTIFACT_BYTES_NOT_REDACTED"]
    assert stdout_preview == "stdout secret [REDACTED]\n"

    assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(export_path)]) == 0
    capsys.readouterr()
    assert export_path.read_text(encoding="utf-8") == "artifact-secret"


def test_run_enforces_experiment_mutable_scope(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "src").mkdir()
    (source / "src" / "main.py").write_text('print("ok")\n', encoding="utf-8")
    (source / "README.md").write_text("base\n", encoding="utf-8")
    config = tmp_path / "alab.mutable.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Mutable Project"
task = "Enforce mutable scope"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "src/main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[mutable]
include = ["**"]
exclude = []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_id = _field(capsys.readouterr().out, "project id")

    worktree = tmp_path / "mutable-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "mutable",
                "--path",
                str(worktree),
                "--mutable-include",
                "src/**",
            ]
        )
        == 0
    )
    capsys.readouterr()

    monkeypatch.chdir(worktree)
    (worktree / "README.md").write_text("blocked\n", encoding="utf-8")
    assert run(["--home", str(home), "run", "--message", "blocked"]) == 4
    blocked_err = capsys.readouterr().err
    assert "SCOPE_VIOLATION" in blocked_err
    assert "README.md" in blocked_err
    assert "blocked" in (worktree / "README.md").read_text(encoding="utf-8")

    _git(["checkout", "--", "README.md"], worktree)
    (worktree / "src" / "main.py").write_text('print("allowed")\n', encoding="utf-8")
    assert run(["--home", str(home), "run", "--message", "allowed"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels()
    assert "run status: passed" in run_out
    assert "created commit: true" in run_out
    assert "stdout preview:\n  allowed" in run_out

    _git(["mv", "src/main.py", "README_RENAMED.md"], worktree)
    assert run(["--home", str(home), "run", "--message", "renamed blocked"]) == 4
    renamed_err = capsys.readouterr().err
    assert "SCOPE_VIOLATION" in renamed_err
    assert "README_RENAMED.md" in renamed_err
    _git(["restore", "--staged", "."], worktree)
    _git(["restore", "."], worktree)
    (worktree / "README_RENAMED.md").unlink(missing_ok=True)

    (worktree / "src" / "readme_copy.md").write_text((worktree / "README.md").read_text(encoding="utf-8"), encoding="utf-8")
    _git(["add", "src/readme_copy.md"], worktree)
    assert run(["--home", str(home), "run", "--message", "copy blocked"]) == 4
    copy_err = capsys.readouterr().err
    assert "SCOPE_VIOLATION" in copy_err
    assert "README.md" in copy_err
    _git(["restore", "--staged", "."], worktree)
    (worktree / "src" / "readme_copy.md").unlink()

    (worktree / "README.md").write_text("manual blocked\n", encoding="utf-8")
    _git(["add", "README.md"], worktree)
    _git(["commit", "-m", "manual blocked"], worktree)
    manual_commit = _git(["rev-parse", "HEAD"], worktree)
    assert run(["--home", str(home), "run", "--message", "manual blocked"]) == 1
    manual_out = capsys.readouterr().out
    assert _field_labels(manual_out) == _run_field_labels(failure=True)
    manual_run_id = _field(manual_out, "run id")
    assert "run status: error" in manual_out
    assert "stderr preview: SCOPE_VIOLATION: committed changes outside mutable scope: README.md" in manual_out
    assert _git(["rev-parse", "HEAD"], worktree) == manual_commit
    with sqlite3.connect(home / "alab.db") as conn:
        row = conn.execute("SELECT status, commit_sha, record_json FROM runs WHERE run_id = ?", (manual_run_id,)).fetchone()
    assert row[0] == "error"
    assert row[1] == manual_commit
    record = json.loads(row[2])
    assert record["config_hash"].startswith("sha256:")
    assert record["runner"] == {"type": "local"}
    assert record["reward"] == {"type": "exit_code", "value": None}
    assert record["mutable_scope"]["error_code"] == "SCOPE_VIOLATION"
    assert record["mutable_scope"]["violation_paths"] == ["README.md"]


def test_run_writes_running_record_before_auto_commit_without_long_write_tx(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("before")\n', encoding="utf-8")
    config = tmp_path / "alab.running-order.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Running Order Project"
task = "Write running before commit"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[git]
author_name = "Configured ALab"
author_email = "configured@example.invalid"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_id = _field(capsys.readouterr().out, "project id")

    worktree = tmp_path / "running-order-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "running-order", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    monkeypatch.chdir(worktree)
    (worktree / "main.py").write_text('print("after")\n', encoding="utf-8")

    observed = {"running_before_commit": False, "runner_write": False}
    original_run_cmd = services.run_cmd
    original_runner = services.run_configured_runner
    monkeypatch.setenv("GIT_AUTHOR_NAME", "External Author")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "external-author@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "External Committer")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "external-committer@example.invalid")

    def observed_run_cmd(args, *pargs, **kwargs):
        if args[:2] == ["git", "commit"]:
            with sqlite3.connect(home / "alab.db") as conn:
                observed["running_before_commit"] = (
                    conn.execute(
                        "SELECT COUNT(*) FROM runs WHERE exp_id = ? AND status = 'running' AND ended_at IS NULL",
                        (exp_id,),
                    ).fetchone()[0]
                    == 1
                )
        return original_run_cmd(args, *pargs, **kwargs)

    def observed_runner(*args, **kwargs):
        with sqlite3.connect(home / "alab.db", timeout=0.1) as conn:
            conn.execute(
                """
                INSERT INTO locks(lock_name, owner_operation_id, owner_host, owner_pid, project_id, exp_id,
                  acquired_at, heartbeat_at, expires_at)
                VALUES ('lock-runner-write-probe', 'op-runner-write-probe', 'test-host', 123, ?, ?,
                  '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z', '2026-05-19T00:00:01Z')
                """,
                (project_id, exp_id),
            )
            conn.execute("DELETE FROM locks WHERE lock_name = 'lock-runner-write-probe'")
        observed["runner_write"] = True
        return original_runner(*args, **kwargs)

    monkeypatch.setattr(services, "run_cmd", observed_run_cmd)
    monkeypatch.setattr(services, "run_configured_runner", observed_runner)

    assert run(["--home", str(home), "run", "--message", "observe running order"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels()
    assert "run status: passed" in run_out
    assert "created commit: true" in run_out
    assert observed == {"running_before_commit": True, "runner_write": True}
    commit_identity = _git(["show", "-s", "--format=%an%x00%ae%x00%cn%x00%ce", "HEAD"], worktree)
    assert commit_identity.split("\0") == [
        "Configured ALab",
        "configured@example.invalid",
        "Configured ALab",
        "configured@example.invalid",
    ]


def test_run_and_submit_use_experiment_operation_lock(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("locked")\n', encoding="utf-8")
    config = tmp_path / "alab.locked.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Locked Experiment Project"
task = "Serialize run and submit"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_id = _field(capsys.readouterr().out, "project id")

    worktree = tmp_path / "locked-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "locked", "--path", str(worktree)]) == 0
    exp_out = capsys.readouterr().out
    exp_id = _field(exp_out, "exp id")
    lock_name = f"experiment-run-submit:{exp_id}"
    monkeypatch.chdir(worktree)

    _insert_active_lock(home, lock_name, project_id, exp_id)
    assert run(["--home", str(home), "run", "--message", "blocked by lock"]) == 4
    run_err = capsys.readouterr().err
    assert _field_labels(run_err) == _error_field_labels()
    assert "error code: EXPERIMENT_BUSY" in run_err
    assert "experiment has an active run or submit lock" in run_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
    _delete_lock(home, lock_name)

    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute(
            """
            INSERT INTO locks(lock_name, owner_operation_id, owner_host, owner_pid, project_id, exp_id,
              acquired_at, heartbeat_at, expires_at)
            VALUES (?, 'op-expired', 'test-host', 123, ?, ?,
              '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z', '2026-05-19T00:00:01Z')
            """,
            (lock_name, project_id, exp_id),
        )
    assert run(["--home", str(home), "run", "--message", "expired lock replaced"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels()
    assert "run status: passed" in run_out
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM locks WHERE lock_name = ?", (lock_name,)).fetchone()[0] == 0

    _insert_active_lock(home, lock_name, project_id, exp_id)
    assert run(["--home", str(home), "submit", "--message", "blocked submit", "--summary", "done", "--feedback", "ok", "--ref", "none"]) == 4
    submit_err = capsys.readouterr().err
    assert _field_labels(submit_err) == _error_field_labels()
    assert "error code: EXPERIMENT_BUSY" in submit_err
    assert "experiment has an active run or submit lock" in submit_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM experiment_submissions WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
    _delete_lock(home, lock_name)

    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute(
            """
            INSERT INTO locks(lock_name, owner_operation_id, owner_host, owner_pid, project_id, exp_id,
              acquired_at, heartbeat_at, expires_at)
            VALUES (?, 'op-expired-submit', 'test-host', 123, ?, ?,
              '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z', '2026-05-19T00:00:01Z')
            """,
            (lock_name, project_id, exp_id),
        )
    assert run(["--home", str(home), "submit", "--message", "expired lock replaced submit", "--summary", "done", "--feedback", "ok", "--ref", "none"]) == 0
    submit_out = capsys.readouterr().out
    assert _field_labels(submit_out) == _submission_field_labels()
    assert "submit accepted: true" in submit_out
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM locks WHERE lock_name = ?", (lock_name,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM experiment_submissions WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 1


def test_run_rejects_invalid_git_states(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("ok")\n', encoding="utf-8")
    config = tmp_path / "alab.git-state.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Git State Project"
task = "Reject invalid Git states"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_id = _field(capsys.readouterr().out, "project id")

    worktree = tmp_path / "git-state-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "git-state", "--path", str(worktree)]) == 0
    branch = _field(capsys.readouterr().out, "branch")
    monkeypatch.chdir(worktree)

    _git(["checkout", "--detach", "HEAD"], worktree)
    assert run(["--home", str(home), "run", "--message", "detached"]) == 4
    detached_err = capsys.readouterr().err
    assert "GIT_STATE_INVALID" in detached_err
    assert "registered branch" in detached_err

    _git(["checkout", branch], worktree)
    _git(["checkout", "-b", "not-the-experiment-branch"], worktree)
    assert run(["--home", str(home), "run", "--message", "wrong branch"]) == 4
    wrong_branch_err = capsys.readouterr().err
    assert "GIT_STATE_INVALID" in wrong_branch_err
    assert "expected" in wrong_branch_err

    _git(["checkout", branch], worktree)
    merge_head = Path(_git(["rev-parse", "--git-path", "MERGE_HEAD"], worktree))
    if not merge_head.is_absolute():
        merge_head = worktree / merge_head
    merge_head.write_text(_git(["rev-parse", "HEAD"], worktree) + "\n", encoding="utf-8")
    try:
        assert run(["--home", str(home), "run", "--message", "merge state"]) == 4
        merge_err = capsys.readouterr().err
        assert "GIT_STATE_INVALID" in merge_err
        assert "MERGE_HEAD" in merge_err
    finally:
        merge_head.unlink(missing_ok=True)


def test_public_exp_create_from_exp_uses_latest_commit(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("base")\n', encoding="utf-8")
    config = tmp_path / "alab.from-exp.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "From Exp Project"
task = "Continue from experiment"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_id = _field(capsys.readouterr().out, "project id")

    parent = tmp_path / "parent"
    child = tmp_path / "child"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "parent", "--path", str(parent)]) == 0
    parent_out = capsys.readouterr().out
    parent_id = _field(parent_out, "exp id")
    duplicate_parent = tmp_path / "duplicate-parent"
    with sqlite3.connect(home / "alab.db") as conn:
        before_duplicate_exp_count = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    before_duplicate_exp_audits = _audit_type_count(home, "add", "experiment")
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Parent!",
                "--path",
                str(duplicate_parent),
            ]
        )
        == 2
    )
    duplicate_name_err = capsys.readouterr().err
    assert _field_labels(duplicate_name_err) == _error_field_labels()
    assert "error code: NAME_CONFLICT" in duplicate_name_err
    assert "experiment name already exists" in duplicate_name_err
    assert not duplicate_parent.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        after_duplicate_exp_count = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    assert after_duplicate_exp_count == before_duplicate_exp_count
    assert _audit_type_count(home, "add", "experiment") == before_duplicate_exp_audits

    duplicate_from_exp_child = tmp_path / "duplicate-from-exp-child"
    with sqlite3.connect(home / "alab.db") as conn:
        before_duplicate_from_exp_count = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    before_duplicate_from_exp_audits = _audit_type_count(home, "add", "experiment")
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "duplicate-from-exp-child",
                "--from-exp",
                parent_id,
                "--from-exp",
                parent_id,
                "--path",
                str(duplicate_from_exp_child),
            ]
        )
        == 2
    )
    duplicate_from_exp_err = capsys.readouterr().err
    assert _field_labels(duplicate_from_exp_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_from_exp_err
    assert "--from-exp may be provided once" in duplicate_from_exp_err
    assert not duplicate_from_exp_child.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_from_exp_count
    assert _audit_type_count(home, "add", "experiment") == before_duplicate_from_exp_audits

    duplicate_from_commit_child = tmp_path / "duplicate-from-commit-child"
    with sqlite3.connect(home / "alab.db") as conn:
        before_duplicate_from_commit_count = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    before_duplicate_from_commit_audits = _audit_type_count(home, "add", "experiment")
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "duplicate-from-commit-child",
                "--from-exp",
                parent_id,
                "--from-commit",
                "latest",
                "--from-commit",
                "final",
                "--path",
                str(duplicate_from_commit_child),
            ]
        )
        == 2
    )
    duplicate_from_commit_err = capsys.readouterr().err
    assert _field_labels(duplicate_from_commit_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_from_commit_err
    assert "--from-commit may be provided once" in duplicate_from_commit_err
    assert not duplicate_from_commit_child.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_from_commit_count
    assert _audit_type_count(home, "add", "experiment") == before_duplicate_from_commit_audits

    no_best_child = tmp_path / "no-best-child"
    with sqlite3.connect(home / "alab.db") as conn:
        before_no_best_count = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    before_no_best_audits = _audit_type_count(home, "add", "experiment")
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "no-best-child",
                "--from-exp",
                parent_id,
                "--from-commit",
                "best",
                "--path",
                str(no_best_child),
            ]
        )
        == 2
    )
    no_best_err = capsys.readouterr().err
    assert _field_labels(no_best_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in no_best_err
    assert "experiment has no qualifying best run" in no_best_err
    assert not no_best_child.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_no_best_count
    assert _audit_type_count(home, "add", "experiment") == before_no_best_audits

    (parent / "main.py").write_text('print("continued")\n', encoding="utf-8")
    monkeypatch.chdir(parent)
    assert run(["--home", str(home), "run", "--message", "continue"]) == 0
    capsys.readouterr()

    monkeypatch.chdir(tmp_path)
    for public_history_args in [
        ["--home", str(home), "observe", "experiments", "show", parent_id, "--project", project_id],
        ["--home", str(home), "runs", "list", "--project", project_id],
    ]:
        assert run(public_history_args) == 4
        public_history_err = capsys.readouterr().err
        assert _field_labels(public_history_err) == _error_field_labels()
        assert "error code: COMMAND_UNAVAILABLE" in public_history_err
        assert "command is not available in the current context" in public_history_err

    public_checkout = tmp_path / "public-checkout"
    before_public_checkout_audits = _audit_type_count(home, "add", "inspection_checkout")
    assert run(["--home", str(home), "exp", "checkout", parent_id, "--project", project_id, "--path", str(public_checkout)]) == 4
    public_checkout_err = capsys.readouterr().err
    assert _field_labels(public_checkout_err) == _error_field_labels()
    assert "error code: COMMAND_UNAVAILABLE" in public_checkout_err
    assert "command is not available in the current context" in public_checkout_err
    assert not public_checkout.exists()
    assert _audit_type_count(home, "add", "inspection_checkout") == before_public_checkout_audits

    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "child", "--from-exp", parent_id, "--path", str(child)]) == 0
    child_out = capsys.readouterr().out
    child_id = _field(child_out, "exp id")
    assert (child / "main.py").read_text(encoding="utf-8") == 'print("continued")\n'

    with sqlite3.connect(home / "alab.db") as conn:
        parent_latest = conn.execute("SELECT latest_commit FROM experiments WHERE exp_id = ?", (parent_id,)).fetchone()[0]
        child_row = conn.execute("SELECT baseline_commit, metadata_json FROM experiments WHERE exp_id = ?", (child_id,)).fetchone()
        source_count = conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
    metadata = json.loads(child_row[1])
    assert child_row[0] == parent_latest
    assert metadata["creation_origin"]["kind"] == "from_exp"
    assert metadata["creation_origin"]["source_exp_id"] == parent_id
    assert metadata["creation_origin"]["resolved_commit"] == parent_latest
    assert source_count == 1

    invalid_commit_child = tmp_path / "invalid-commit-child"
    with sqlite3.connect(home / "alab.db") as conn:
        before_invalid_commit_count = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    before_invalid_commit_audits = _audit_type_count(home, "add", "experiment")
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "invalid-commit-child",
                "--from-exp",
                parent_id,
                "--from-commit",
                "HEAD",
                "--path",
                str(invalid_commit_child),
            ]
        )
        == 2
    )
    invalid_commit_err = capsys.readouterr().err
    assert _field_labels(invalid_commit_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in invalid_commit_err
    assert "commit selector must be latest, final, best, or a commit SHA" in invalid_commit_err
    assert not invalid_commit_child.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_invalid_commit_count
    assert _audit_type_count(home, "add", "experiment") == before_invalid_commit_audits

    sha_child = tmp_path / "sha-child"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "sha-child",
                "--from-exp",
                parent_id,
                "--from-commit",
                parent_latest,
                "--path",
                str(sha_child),
            ]
        )
        == 0
    )
    sha_child_out = capsys.readouterr().out
    assert _field_labels(sha_child_out) == _exp_create_field_labels()
    sha_child_id = _field(sha_child_out, "exp id")
    assert (sha_child / "main.py").read_text(encoding="utf-8") == 'print("continued")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        sha_child_row = conn.execute(
            "SELECT baseline_commit, metadata_json FROM experiments WHERE exp_id = ?",
            (sha_child_id,),
        ).fetchone()
    sha_child_metadata = json.loads(sha_child_row[1])
    assert sha_child_row[0] == parent_latest
    assert sha_child_metadata["creation_origin"]["kind"] == "from_exp"
    assert sha_child_metadata["creation_origin"]["source_exp_id"] == parent_id
    assert sha_child_metadata["creation_origin"]["from_commit"] == parent_latest
    assert sha_child_metadata["creation_origin"]["resolved_commit"] == parent_latest

    no_final_child = tmp_path / "no-final-child"
    with sqlite3.connect(home / "alab.db") as conn:
        before_no_final_count = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    before_no_final_audits = _audit_type_count(home, "add", "experiment")
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "no-final-child",
                "--from-exp",
                parent_id,
                "--from-commit",
                "final",
                "--path",
                str(no_final_child),
            ]
        )
        == 2
    )
    no_final_err = capsys.readouterr().err
    assert _field_labels(no_final_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in no_final_err
    assert "experiment has no final commit" in no_final_err
    assert not no_final_child.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_no_final_count
    assert _audit_type_count(home, "add", "experiment") == before_no_final_audits

    monkeypatch.chdir(parent)
    assert run(["--home", str(home), "submit", "--message", "final", "--summary", "done", "--feedback", "ok", "--ref", "none"]) == 0
    submit_out = capsys.readouterr().out
    assert _field_labels(submit_out) == _submission_field_labels()
    parent_final = _field(submit_out, "final commit")
    assert parent_final == parent_latest

    final_child = tmp_path / "final-child"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "final-child",
                "--from-exp",
                parent_id,
                "--from-commit",
                "final",
                "--path",
                str(final_child),
            ]
        )
        == 0
    )
    final_child_out = capsys.readouterr().out
    assert _field_labels(final_child_out) == _exp_create_field_labels()
    final_child_id = _field(final_child_out, "exp id")
    assert (final_child / "main.py").read_text(encoding="utf-8") == 'print("continued")\n'

    best_child = tmp_path / "best-child"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "best-child",
                "--from-exp",
                parent_id,
                "--from-commit",
                "best",
                "--path",
                str(best_child),
            ]
        )
        == 0
    )
    best_child_out = capsys.readouterr().out
    assert _field_labels(best_child_out) == _exp_create_field_labels()
    best_child_id = _field(best_child_out, "exp id")
    assert (best_child / "main.py").read_text(encoding="utf-8") == 'print("continued")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        final_child_row = conn.execute(
            "SELECT baseline_commit, metadata_json FROM experiments WHERE exp_id = ?",
            (final_child_id,),
        ).fetchone()
        best_child_row = conn.execute(
            "SELECT baseline_commit, metadata_json FROM experiments WHERE exp_id = ?",
            (best_child_id,),
        ).fetchone()
        source_count_after_selectors = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    final_child_metadata = json.loads(final_child_row[1])
    best_child_metadata = json.loads(best_child_row[1])
    assert final_child_row[0] == parent_final
    assert final_child_metadata["creation_origin"]["from_commit"] == "final"
    assert final_child_metadata["creation_origin"]["resolved_commit"] == parent_final
    assert best_child_row[0] == parent_latest
    assert best_child_metadata["creation_origin"]["from_commit"] == "best"
    assert best_child_metadata["creation_origin"]["resolved_commit"] == parent_latest
    assert source_count_after_selectors == 1

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "annotate",
                "add",
                "--project",
                project_id,
                "--target",
                f"path:{parent_id}@final:main.py",
                "--body",
                "final alias annotation",
            ]
        )
        == 0
    )
    final_alias_annotation_out = capsys.readouterr().out
    assert _field_labels(final_alias_annotation_out) == _annotation_add_field_labels()
    final_alias_annotation_id = _field(final_alias_annotation_out, "annotation id")
    assert _field(final_alias_annotation_out, "resolved commit") == parent_final
    with sqlite3.connect(home / "alab.db") as conn:
        final_alias_row = conn.execute(
            "SELECT target_id, target_json, resolved_commit FROM annotations WHERE annotation_id = ?",
            (final_alias_annotation_id,),
        ).fetchone()
    final_alias_target = json.loads(final_alias_row[1])
    assert final_alias_row[0] == f"{parent_id}:{parent_final}:main.py"
    assert final_alias_row[2] == parent_final
    assert final_alias_target["commit"] == parent_final
    assert final_alias_target["target_id"] == f"{parent_id}:{parent_final}:main.py"

    assert run(["--home", str(home), "--key", root_key, "exp", "archive", parent_id, "--project", project_id]) == 0
    archive_out = capsys.readouterr().out
    assert _field_labels(archive_out) == _experiment_status_field_labels()
    assert "experiment status: archived" in archive_out
    blocked_archived_child = tmp_path / "blocked-archived-child"
    with sqlite3.connect(home / "alab.db") as conn:
        before_archived_child_count = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    before_archived_child_audits = _audit_type_count(home, "add", "experiment")
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "blocked-archived-child",
                "--from-exp",
                parent_id,
                "--path",
                str(blocked_archived_child),
            ]
        )
        == 4
    )
    archived_child_err = capsys.readouterr().err
    assert _field_labels(archived_child_err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in archived_child_err
    assert "archived source experiments require root/admin for --from-exp" in archived_child_err
    assert not blocked_archived_child.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_archived_child_count
    assert _audit_type_count(home, "add", "experiment") == before_archived_child_audits

    admin_archived_child = tmp_path / "admin-archived-child"
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "admin-archived-child",
                "--from-exp",
                parent_id,
                "--path",
                str(admin_archived_child),
            ]
        )
        == 0
    )
    admin_archived_out = capsys.readouterr().out
    assert _field_labels(admin_archived_out) == _exp_create_field_labels()
    admin_archived_id = _field(admin_archived_out, "exp id")
    assert (admin_archived_child / "main.py").read_text(encoding="utf-8") == 'print("continued")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        admin_archived_row = conn.execute(
            "SELECT baseline_commit, metadata_json FROM experiments WHERE exp_id = ?",
            (admin_archived_id,),
        ).fetchone()
        source_count_after_archived = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    admin_archived_metadata = json.loads(admin_archived_row[1])
    assert admin_archived_row[0] == parent_latest
    assert admin_archived_metadata["creation_origin"]["kind"] == "from_exp"
    assert admin_archived_metadata["creation_origin"]["source_exp_id"] == parent_id
    assert admin_archived_metadata["creation_origin"]["resolved_commit"] == parent_latest
    assert source_count_after_archived == 1


def test_public_from_exp_respects_visibility_upper_bound(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("base")\n', encoding="utf-8")
    config = tmp_path / "alab.from-exp-private.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Private Inheritance Project"
task = "Block public inheritance"
allow_public_exp_create = true

[visibility]
scope = "none"

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    def import_visibility(scope: str, experiment_ids: list[str] | None = None) -> None:
        with sqlite3.connect(home / "alab.db") as conn:
            project = conn.execute(
                "SELECT latest_attempted_config_version FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            config_json = json.loads(
                conn.execute(
                    "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?",
                    (project_id, project[0]),
                ).fetchone()[0]
            )
        config_json["visibility"] = {"scope": scope}
        if scope == "explicit":
            config_json["visibility"]["experiment_ids"] = experiment_ids or []
        import_path = tmp_path / f"visibility-{scope}-{len(experiment_ids or [])}.toml"
        import_path.write_text(services.dumps_toml(config_json), encoding="utf-8")
        assert run(["--home", str(home), "--key", admin_key, "project", "config", "import", "--project", project_id, "--config", str(import_path), "--skip-baseline-test"]) == 0
        assert "runtime affecting: false" in capsys.readouterr().out

    parent = tmp_path / "private-parent"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "private-parent", "--path", str(parent)]) == 0
    parent_id = _field(capsys.readouterr().out, "exp id")

    assert (
        run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "blocked-child", "--from-exp", parent_id, "--path", str(tmp_path / "blocked-child")])
        == 4
    )
    assert "source experiment is not visible for public inheritance" in capsys.readouterr().err
    assert not (tmp_path / "blocked-child").exists()

    import_visibility("same_project")
    allowed_parent = tmp_path / "explicit-allowed-parent"
    blocked_parent = tmp_path / "explicit-blocked-parent"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "explicit-allowed-parent", "--path", str(allowed_parent)]) == 0
    allowed_parent_id = _field(capsys.readouterr().out, "exp id")
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "explicit-blocked-parent", "--path", str(blocked_parent)]) == 0
    blocked_parent_id = _field(capsys.readouterr().out, "exp id")

    import_visibility("explicit", [allowed_parent_id])
    allowed_child = tmp_path / "explicit-allowed-child"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "explicit-allowed-child", "--from-exp", allowed_parent_id, "--path", str(allowed_child)]) == 0
    allowed_child_out = capsys.readouterr().out
    assert _field_labels(allowed_child_out) == _exp_create_field_labels()
    allowed_child_id = _field(allowed_child_out, "exp id")
    with sqlite3.connect(home / "alab.db") as conn:
        allowed_child_metadata = json.loads(
            conn.execute("SELECT metadata_json FROM experiments WHERE exp_id = ?", (allowed_child_id,)).fetchone()[0]
        )
    assert allowed_child_metadata["creation_origin"]["kind"] == "from_exp"
    assert allowed_child_metadata["creation_origin"]["source_exp_id"] == allowed_parent_id
    assert allowed_child.exists()
    blocked_child = tmp_path / "explicit-blocked-child"
    before_blocked_exp_count = _table_count(home, "experiments")
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "explicit-blocked-child", "--from-exp", blocked_parent_id, "--path", str(blocked_child)]) == 4
    blocked_child_err = capsys.readouterr().err
    assert _field_labels(blocked_child_err) == _error_field_labels()
    assert "source experiment is not visible for public inheritance" in blocked_child_err
    assert _table_count(home, "experiments") == before_blocked_exp_count
    assert not blocked_child.exists()

    import_visibility("same_project")
    upper_explicit_parent = tmp_path / "upper-explicit-parent"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "upper-explicit-parent",
                "--path",
                str(upper_explicit_parent),
                "--visibility-scope",
                "explicit",
                "--visible-exp",
                allowed_parent_id,
            ]
        )
        == 0
    )
    upper_explicit_parent_id = _field(capsys.readouterr().out, "exp id")
    upper_explicit_child = tmp_path / "upper-explicit-child"
    before_upper_block_count = _table_count(home, "experiments")
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "upper-explicit-child", "--from-exp", upper_explicit_parent_id, "--path", str(upper_explicit_child)]) == 4
    upper_explicit_err = capsys.readouterr().err
    assert _field_labels(upper_explicit_err) == _error_field_labels()
    assert "source experiment is not visible for public inheritance" in upper_explicit_err
    assert _table_count(home, "experiments") == before_upper_block_count
    assert not upper_explicit_child.exists()


def test_admin_exp_create_can_bind_archived_source_ref(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    base_source = tmp_path / "base-source"
    archived_source = tmp_path / "archived-source"
    base_source.mkdir()
    archived_source.mkdir()
    (base_source / "main.py").write_text('print("base")\n', encoding="utf-8")
    (archived_source / "main.py").write_text('print("archived source")\n', encoding="utf-8")
    config = tmp_path / "alab.archived-source.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Archived Source Project"
task = "Create from archived source"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert (
        run(
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
                str(base_source),
            ]
        )
        == 0
    )
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    assert (
        run(
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
                str(archived_source),
                "--name",
                "archived-exp-source",
            ]
        )
        == 0
    )
    import_out = capsys.readouterr().out
    source_id = _field(import_out, "source id")
    source_ref = _field(import_out, "source ref")
    assert run(["--home", str(home), "--key", admin_key, "source", "archive", source_id, "--project", project_id]) == 0
    archive_out = capsys.readouterr().out
    assert _field_labels(archive_out) == _source_status_field_labels()
    with sqlite3.connect(home / "alab.db") as conn:
        archived_source_commit = conn.execute(
            "SELECT source_commit FROM sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()[0]
        before_public_exp_count = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    before_public_exp_audits = _audit_type_count(home, "add", "experiment")

    public_worktree = tmp_path / "public-archived-source-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "public-archived-source",
                "--source-ref",
                source_ref,
                "--path",
                str(public_worktree),
            ]
        )
        == 3
    )
    public_err = capsys.readouterr().err
    assert _field_labels(public_err) == _error_field_labels()
    assert "error code: AUTH_REQUIRED" in public_err
    assert not public_worktree.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_public_exp_count
    assert _audit_type_count(home, "add", "experiment") == before_public_exp_audits

    admin_worktree = tmp_path / "admin-archived-source-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "admin-archived-source",
                "--source-ref",
                source_ref,
                "--path",
                str(admin_worktree),
            ]
        )
        == 0
    )
    admin_out = capsys.readouterr().out
    assert _field_labels(admin_out) == _exp_create_field_labels()
    exp_id = _field(admin_out, "exp id")
    assert f"source id: {source_id}" in admin_out
    assert (admin_worktree / "main.py").read_text(encoding="utf-8") == 'print("archived source")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        exp_row = conn.execute(
            "SELECT source_id, baseline_commit, metadata_json FROM experiments WHERE exp_id = ?",
            (exp_id,),
        ).fetchone()
        source_status = conn.execute(
            "SELECT status FROM sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()[0]
    metadata = json.loads(exp_row[2])
    assert exp_row[:2] == (source_id, archived_source_commit)
    assert metadata["creation_origin"] == {"kind": "source", "source_id": source_id}
    assert source_status == "archived"


def test_config_source_observe_and_tags(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
print("hello from runner")
with open(os.path.join(os.environ["ALAB_RUN_DIR"], "artifact.txt"), "w", encoding="utf-8") as fh:
    fh.write("artifact bytes")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Observe Project"
task = "Capture logs and artifacts"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "full"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    root_credential_id = root_key.removeprefix("alab_root_v1_").rpartition("_")[0]

    assert (
        run(
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
        == 0
    )
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    baseline_validation_id = _field(project_out, "validation id")
    default_source_id = _field(project_out, "source id")
    default_source_ref = _field(project_out, "source ref")
    with sqlite3.connect(home / "alab.db") as conn:
        admin_credential_id = conn.execute(
            "SELECT credential_id FROM credentials WHERE project_id = ? AND credential_type = 'admin' AND status = 'active'",
            (project_id,),
        ).fetchone()[0]
    assert run(["--home", str(home), "status", "--project", project_id]) == 0
    status_out = capsys.readouterr().out
    assert _field_labels(status_out) == ["object", "context type", "project id", "project status", "task", "next"]
    assert "task:\n  Capture logs and artifacts" in status_out

    duplicate_project_cases = [
        (
            ["--home", str(home), "--key", root_key, "project", "list", "--include-archived", "--include-archived"],
            "--include-archived may be provided once",
        ),
        (
            ["--home", str(home), "--key", admin_key, "project", "show", "--project", project_id, "--project", project_id],
            "--project may be provided once",
        ),
    ]
    for project_args, message in duplicate_project_cases:
        assert run(project_args) == 2
        duplicate_project_err = capsys.readouterr().err
        assert _field_labels(duplicate_project_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_project_err
        assert message in duplicate_project_err
    assert run(["--home", str(home), "status", "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_status_err = capsys.readouterr().err
    assert _field_labels(unsupported_status_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_status_err
    assert "unsupported option --reason" in unsupported_status_err
    assert run(["--home", str(home), "--key", admin_key, "project", "show", "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_project_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_project_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_project_show_err
    assert "unsupported option --reason" in unsupported_project_show_err

    with sqlite3.connect(home / "alab.db") as conn:
        before_duplicate_key_create = {
            "credentials": conn.execute("SELECT COUNT(*) FROM credentials WHERE credential_type = 'admin' AND project_id = ?", (project_id,)).fetchone()[0],
            "audits": conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'add' AND object_type = 'credential' AND project_id = ?", (project_id,)).fetchone()[0],
        }
    duplicate_key_create_cases = [
        (
            ["--home", str(home), "--key", root_key, "key", "create", "--project", project_id, "--project", project_id],
            "--project may be provided once",
        ),
        (
            ["--home", str(home), "--key", root_key, "key", "create", "--project", project_id, "--role", "admin", "--role", "admin"],
            "--role may be provided once",
        ),
        (
            ["--home", str(home), "--key", root_key, "key", "create", "extra", "--project", project_id],
            "key create accepts no positional arguments",
        ),
    ]
    for key_args, message in duplicate_key_create_cases:
        assert run(key_args) == 2
        duplicate_key_create_err = capsys.readouterr().err
        assert _field_labels(duplicate_key_create_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_key_create_err
        assert message in duplicate_key_create_err
    assert run(["--home", str(home), "--key", root_key, "key", "create", "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_key_create_err = capsys.readouterr().err
    assert _field_labels(unsupported_key_create_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_key_create_err
    assert "unsupported option --reason" in unsupported_key_create_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE credential_type = 'admin' AND project_id = ?", (project_id,)).fetchone()[0] == before_duplicate_key_create["credentials"]
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE action = 'add' AND object_type = 'credential' AND project_id = ?", (project_id,)).fetchone()[0] == before_duplicate_key_create["audits"]

    assert run(["--home", str(home), "--key", root_key, "key", "create", "--project", project_id]) == 0
    key_create_out = capsys.readouterr().out
    created_admin_id = _field(key_create_out, "key id")
    created_admin_key = _field(key_create_out, "admin key")
    assert created_admin_key.startswith("alab_admin_v1_")
    with sqlite3.connect(home / "alab.db") as conn:
        key_create_audit = conn.execute(
            """
            SELECT actor_credential_id, actor_type, action, object_type, object_id,
              project_id, exp_id, cascade, reason, metadata_json
            FROM audit_events
            WHERE action = 'add' AND object_type = 'credential' AND object_id = ?
            """,
            (created_admin_id,),
        ).fetchone()
    assert key_create_audit[:9] == (root_credential_id, "root", "add", "credential", created_admin_id, project_id, None, 0, None)
    assert json.loads(key_create_audit[9]) == {"schema_version": 1}
    assert root_key not in key_create_audit[9]
    assert created_admin_key not in key_create_audit[9]
    assert run(["--home", str(home), "--key", root_key, "key", "list", "--project", project_id]) == 0
    admin_key_list_out = capsys.readouterr().out
    assert all(labels == _admin_key_list_field_labels() for labels in _block_labels(admin_key_list_out))
    assert created_admin_id in admin_key_list_out
    assert run(["--home", str(home), "--key", root_key, "key", "list", "extra", "--project", project_id]) == 2
    extra_project_key_list_err = capsys.readouterr().err
    assert _field_labels(extra_project_key_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_project_key_list_err
    assert "key list accepts no positional arguments" in extra_project_key_list_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM credentials WHERE credential_type = 'admin' AND project_id = ?",
            (project_id,),
        ).fetchone()[0] == before_duplicate_key_create["credentials"] + 1
    assert run(["--home", str(home), "--key", root_key, "key", "revoke", created_admin_id[:8], "--project", project_id]) == 2
    short_key_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in short_key_err
    assert "object ids must be complete" in short_key_err
    assert run(["--home", str(home), "--key", root_key, "key", "revoke", created_admin_id, "--project", project_id, "--project", project_id]) == 2
    duplicate_key_revoke_err = capsys.readouterr().err
    assert _field_labels(duplicate_key_revoke_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_key_revoke_err
    assert "--project may be provided once" in duplicate_key_revoke_err
    assert run(["--home", str(home), "--key", root_key, "key", "revoke", created_admin_id, "extra", "--project", project_id]) == 2
    extra_key_revoke_err = capsys.readouterr().err
    assert _field_labels(extra_key_revoke_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_key_revoke_err
    assert "key revoke accepts exactly one key id" in extra_key_revoke_err
    with sqlite3.connect(home / "alab.db") as conn:
        duplicate_revoke_status = conn.execute("SELECT status FROM credentials WHERE credential_id = ?", (created_admin_id,)).fetchone()[0]
    assert duplicate_revoke_status == "active"
    assert _audit_count(home, "revoke", "credential", created_admin_id) == 0
    assert run(["--home", str(home), "--key", root_key, "key", "revoke", created_admin_id, "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_key_revoke_err = capsys.readouterr().err
    assert _field_labels(unsupported_key_revoke_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_key_revoke_err
    assert "unsupported option --reason" in unsupported_key_revoke_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM credentials WHERE credential_id = ?", (created_admin_id,)).fetchone()[0] == "active"
    assert _audit_count(home, "revoke", "credential", created_admin_id) == 0
    assert run(["--home", str(home), "--key", root_key, "key", "revoke", created_admin_id, "--project", project_id]) == 0
    key_revoke_out = capsys.readouterr().out
    assert _field_labels(key_revoke_out) == _key_revoke_field_labels()
    assert "status: revoked" in key_revoke_out
    with sqlite3.connect(home / "alab.db") as conn:
        key_revoke_audit = conn.execute(
            """
            SELECT actor_credential_id, actor_type, action, object_type, object_id,
              project_id, exp_id, cascade, reason, metadata_json
            FROM audit_events
            WHERE action = 'revoke' AND object_type = 'credential' AND object_id = ?
            """,
            (created_admin_id,),
        ).fetchone()
    assert key_revoke_audit[:9] == (root_credential_id, "root", "revoke", "credential", created_admin_id, project_id, None, 0, None)
    key_revoke_metadata_text = key_revoke_audit[9]
    key_revoke_metadata = json.loads(key_revoke_metadata_text)
    assert key_revoke_metadata == {
        "credential_status": "revoked",
        "credential_type": "admin",
        "previous_status": "active",
        "revoked_at": _field(key_revoke_out, "revoked at"),
        "schema_version": 1,
        "token_mode": None,
    }
    assert root_key not in key_revoke_metadata_text
    assert created_admin_key not in key_revoke_metadata_text

    validation_count_before_unsupported_validate = _table_count(home, "project_validations")
    assert run(["--home", str(home), "--key", admin_key, "project", "validate", "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_project_validate_err = capsys.readouterr().err
    assert _field_labels(unsupported_project_validate_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_project_validate_err
    assert "unsupported option --reason" in unsupported_project_validate_err
    assert _table_count(home, "project_validations") == validation_count_before_unsupported_validate

    assert run(["--home", str(home), "--key", admin_key, "project", "validate", "--project", project_id]) == 0
    project_validate_out = capsys.readouterr().out
    assert _field_labels(project_validate_out) == _project_validation_field_labels(warning_count=1)
    assert "validation status: passed" in project_validate_out
    assert "warning code: ENV_MODE_FULL_UNREDACTED_HOST_ENV" in project_validate_out
    active_validation_id = _field(project_validate_out, "validation id")
    assert active_validation_id != baseline_validation_id
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "archive", active_validation_id, "--project", project_id]) == 4
    active_validation_archive_err = capsys.readouterr().err
    assert _field_labels(active_validation_archive_err) == _error_field_labels()
    assert "error code: RESOURCE_BUSY" in active_validation_archive_err
    assert "active_validation" in active_validation_archive_err
    assert _audit_count(home, "archive", "validation", active_validation_id) == 0
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "archive", active_validation_id, "extra", "--project", project_id]) == 2
    extra_validation_archive_err = capsys.readouterr().err
    assert _field_labels(extra_validation_archive_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_validation_archive_err
    assert "validation archive accepts exactly one validation id" in extra_validation_archive_err
    assert _audit_count(home, "archive", "validation", active_validation_id) == 0
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "remove", active_validation_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    active_validation_remove_dry_run = capsys.readouterr().out
    assert _field_labels(active_validation_remove_dry_run) == _validation_remove_field_labels(
        dry_run=True,
        has_blocker=True,
        blocker_count=3,
        filesystem_path_count=2,
    )
    assert "removed: false" in active_validation_remove_dry_run
    assert "cascade: true" in active_validation_remove_dry_run
    assert "blocker: active_validation" in active_validation_remove_dry_run
    assert "blocker: target_not_archived" in active_validation_remove_dry_run
    assert "blocker: dependent_records_not_archived" in active_validation_remove_dry_run
    assert "deleted artifacts: 1" in active_validation_remove_dry_run
    assert "deleted logs: 2" in active_validation_remove_dry_run
    assert "active dependent artifacts: 1" in active_validation_remove_dry_run
    assert "active dependent logs: 2" in active_validation_remove_dry_run
    assert "deleted filesystem paths: 2" in active_validation_remove_dry_run
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "project", "validation", "remove", active_validation_id, "--project", project_id, "--dry-run", "--dry-run", "--cascade"], "--dry-run", capsys)
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "project", "validation", "remove", active_validation_id, "--project", project_id, "--dry-run", "--cascade", "--cascade"], "--cascade", capsys)
    _assert_remove_dry_run_preserved(home, "validation", active_validation_id, "project_validations", "validation_id")
    _assert_remove_resource_busy(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "validation",
            "remove",
            active_validation_id,
            "--project",
            project_id,
            "--force",
            "--confirm",
            active_validation_id,
            "--cascade",
        ],
        home,
        "validation",
        active_validation_id,
        "active_validation",
        capsys,
    )
    with sqlite3.connect(home / "alab.db") as conn:
        active_project_validation = conn.execute(
            "SELECT active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        active_validation_archive_status = conn.execute(
            "SELECT archive_status FROM project_validations WHERE validation_id = ?",
            (active_validation_id,),
        ).fetchone()[0]
    assert active_project_validation == active_validation_id
    assert active_validation_archive_status == "active"
    _assert_not_archived_remove_blocked(
        ["--home", str(home), "--key", admin_key, "project", "validation", "remove", baseline_validation_id, "--project", project_id, "--force", "--confirm", baseline_validation_id],
        home,
        "validation",
        baseline_validation_id,
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "archive", baseline_validation_id, "--project", project_id]) == 0
    validation_archive_out = capsys.readouterr().out
    assert _field_labels(validation_archive_out) == _validation_archive_field_labels()
    assert "archive status: archived" in validation_archive_out
    validation_archived_at = _field(validation_archive_out, "archived at")
    assert _audit_count(home, "archive", "validation", baseline_validation_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "archive", baseline_validation_id, "--project", project_id]) == 0
    validation_archive_repeat_out = capsys.readouterr().out
    assert _field_labels(validation_archive_repeat_out) == _validation_archive_field_labels()
    assert "previous archive status: archived" in validation_archive_repeat_out
    assert _field(validation_archive_repeat_out, "archived at") == validation_archived_at
    assert _field(validation_archive_repeat_out, "audit id") == "none"
    assert _audit_count(home, "archive", "validation", baseline_validation_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "unarchive", baseline_validation_id, "--project", project_id]) == 0
    validation_unarchive_out = capsys.readouterr().out
    assert _field_labels(validation_unarchive_out) == _validation_archive_field_labels(unarchive=True)
    assert "archive status: active" in validation_unarchive_out
    validation_unarchived_at = _field(validation_unarchive_out, "unarchived at")
    assert _audit_count(home, "unarchive", "validation", baseline_validation_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "unarchive", baseline_validation_id, "--project", project_id]) == 0
    validation_unarchive_repeat_out = capsys.readouterr().out
    assert _field_labels(validation_unarchive_repeat_out) == _validation_archive_field_labels(unarchive=True)
    assert "previous archive status: active" in validation_unarchive_repeat_out
    assert _field(validation_unarchive_repeat_out, "unarchived at") == validation_unarchived_at
    assert _field(validation_unarchive_repeat_out, "audit id") == "none"
    assert _audit_count(home, "unarchive", "validation", baseline_validation_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "archive", baseline_validation_id, "--project", project_id]) == 0
    assert _field_labels(capsys.readouterr().out) == _validation_archive_field_labels()
    assert _audit_count(home, "archive", "validation", baseline_validation_id) == 2

    artifact_store = home / "projects" / project_id / "artifacts"
    with sqlite3.connect(home / "alab.db") as conn:
        validation_artifacts = conn.execute(
            "SELECT artifact_id, blob_path FROM artifacts WHERE validation_id = ? AND blob_path IS NOT NULL ORDER BY artifact_id",
            (baseline_validation_id,),
        ).fetchall()
        validation_logs = conn.execute(
            "SELECT log_id, file_path FROM log_streams WHERE validation_id = ? ORDER BY stream",
            (baseline_validation_id,),
        ).fetchall()
        validation_artifact_ref_counts = [
            conn.execute("SELECT COUNT(*) FROM artifacts WHERE project_id = ? AND blob_path = ?", (project_id, row[1])).fetchone()[0]
            for row in validation_artifacts
        ]
    assert len(validation_artifacts) == 1
    assert len(validation_logs) == 2
    validation_artifact_paths = [artifact_store / row[1] for row in validation_artifacts]
    validation_log_paths = [artifact_store / row[1] for row in validation_logs]
    expected_deleted_validation_files = len(validation_logs) + sum(1 for count in validation_artifact_ref_counts if count == 1)
    assert all(path.exists() for path in validation_artifact_paths)
    assert all(path.exists() for path in validation_log_paths)
    validation_artifact_id = validation_artifacts[0][0]
    with sqlite3.connect(home / "alab.db") as conn:
        validation_stdout_log_id = conn.execute(
            "SELECT log_id FROM log_streams WHERE validation_id = ? AND stream = 'stdout'",
            (baseline_validation_id,),
        ).fetchone()[0]

    assert run(["--home", str(home), "--key", admin_key, "artifacts", "list", "--project", project_id, "--validation", baseline_validation_id]) == 0
    validation_artifacts_out = capsys.readouterr().out
    assert _field_labels(validation_artifacts_out) == _artifact_field_labels()
    assert f"artifact id: {validation_artifact_id}" in validation_artifacts_out
    assert f"validation id: {baseline_validation_id}" in validation_artifacts_out
    assert run(["--home", str(home), "--key", admin_key, "logs", "list", "--project", project_id, "--validation", baseline_validation_id, "--stream", "stdout"]) == 0
    validation_logs_out = capsys.readouterr().out
    assert _field_labels(validation_logs_out) == _log_field_labels()
    assert f"log id: {validation_stdout_log_id}" in validation_logs_out
    assert f"validation id: {baseline_validation_id}" in validation_logs_out
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "list", "--project", project_id, "--validation", baseline_validation_id[:8]]) == 2
    short_validation_artifact_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in short_validation_artifact_err
    assert "object ids must be complete" in short_validation_artifact_err

    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "remove", baseline_validation_id, "--project", project_id, "--dry-run"]) == 0
    no_cascade_out = capsys.readouterr().out
    assert _field_labels(no_cascade_out) == _validation_remove_field_labels(dry_run=True, has_blocker=True, filesystem_path_count=expected_deleted_validation_files)
    assert "blocker: dependent_records_require_cascade" in no_cascade_out
    assert "deleted artifacts: 1" in no_cascade_out
    assert "deleted logs: 2" in no_cascade_out
    _assert_remove_dry_run_preserved(home, "validation", baseline_validation_id, "project_validations", "validation_id")
    _assert_remove_resource_busy(
        ["--home", str(home), "--key", admin_key, "project", "validation", "remove", baseline_validation_id, "--project", project_id, "--force", "--confirm", baseline_validation_id],
        home,
        "validation",
        baseline_validation_id,
        "dependent_records_require_cascade",
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "remove", baseline_validation_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    active_children_out = capsys.readouterr().out
    assert _field_labels(active_children_out) == _validation_remove_field_labels(dry_run=True, has_blocker=True, filesystem_path_count=expected_deleted_validation_files)
    assert "blocker: dependent_records_not_archived" in active_children_out
    assert "active dependent artifacts: 1" in active_children_out
    assert "active dependent logs: 2" in active_children_out
    _assert_remove_resource_busy(
        ["--home", str(home), "--key", admin_key, "project", "validation", "remove", baseline_validation_id, "--project", project_id, "--force", "--confirm", baseline_validation_id, "--cascade"],
        home,
        "validation",
        baseline_validation_id,
        "dependent_records_not_archived",
        capsys,
    )
    _assert_remove_dry_run_preserved(home, "validation", baseline_validation_id, "project_validations", "validation_id")
    for artifact_id, _blob_path in validation_artifacts:
        assert _row_count(home, "artifacts", "artifact_id", artifact_id) == 1
    for log_id, _file_path in validation_logs:
        assert _row_count(home, "log_streams", "log_id", log_id) == 1
    assert all(path.exists() for path in validation_artifact_paths)
    assert all(path.exists() for path in validation_log_paths)

    for artifact_id, _blob_path in validation_artifacts:
        assert run(["--home", str(home), "--key", admin_key, "artifacts", "archive", artifact_id, "--project", project_id]) == 0
        capsys.readouterr()
    for log_id, _file_path in validation_logs:
        assert run(["--home", str(home), "--key", admin_key, "logs", "archive", log_id, "--project", project_id]) == 0
        capsys.readouterr()

    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "remove", baseline_validation_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    validation_dry_run = capsys.readouterr().out
    assert _field_labels(validation_dry_run) == _validation_remove_field_labels(dry_run=True, filesystem_path_count=expected_deleted_validation_files)
    assert "blocker:" not in validation_dry_run
    assert "removed: false" in validation_dry_run
    assert "active dependent artifacts: 0" in validation_dry_run
    assert "active dependent logs: 0" in validation_dry_run
    assert f"deleted filesystem paths: {expected_deleted_validation_files}" in validation_dry_run
    _assert_remove_dry_run_preserved(home, "validation", baseline_validation_id, "project_validations", "validation_id")
    assert all(path.exists() for path in validation_artifact_paths)
    assert all(path.exists() for path in validation_log_paths)

    _assert_confirm_guard(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "project",
            "validation",
            "remove",
            baseline_validation_id,
            "--project",
            project_id,
            "--cascade",
        ],
        baseline_validation_id,
        "validation remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "project", "validation", "remove", baseline_validation_id, "--project", project_id, "--force", "--confirm", baseline_validation_id, "--cascade"]) == 0
    validation_remove_out = capsys.readouterr().out
    assert _field_labels(validation_remove_out) == _validation_remove_field_labels(dry_run=False)
    validation_audit_id = _field(validation_remove_out, "audit id")
    assert "removed: true" in validation_remove_out
    assert "deleted artifacts: 1" in validation_remove_out
    assert "deleted logs: 2" in validation_remove_out
    assert f"deleted filesystem paths: {expected_deleted_validation_files}" in validation_remove_out
    assert "trash cleanup pending: false" in validation_remove_out
    for path, ref_count in zip(validation_artifact_paths, validation_artifact_ref_counts, strict=True):
        assert path.exists() == (ref_count > 1)
    assert all(not path.exists() for path in validation_log_paths)
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM project_validations WHERE validation_id = ?", (baseline_validation_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE validation_id = ?", (baseline_validation_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM log_streams WHERE validation_id = ?", (baseline_validation_id,)).fetchone()[0] == 0
        validation_audit_row = conn.execute(
            """
            SELECT actor_credential_id, action, object_type, object_id, project_id, exp_id, cascade, reason, metadata_json
            FROM audit_events
            WHERE audit_id = ?
            """,
            (validation_audit_id,),
        ).fetchone()
        validation_trash_rows = conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0]
    assert validation_audit_row[:8] == (admin_credential_id, "remove", "validation", baseline_validation_id, project_id, None, 1, None)
    validation_metadata = json.loads(validation_audit_row[8])
    assert validation_metadata["deleted_artifact_count"] == 1
    assert validation_metadata["deleted_log_count"] == 2
    assert validation_metadata["active_dependent_artifact_count"] == 0
    assert validation_metadata["active_dependent_log_count"] == 0
    assert validation_metadata["filesystem_target_count"] == expected_deleted_validation_files
    expected_trash_kinds = {"log"}
    if any(count == 1 for count in validation_artifact_ref_counts):
        expected_trash_kinds.add("artifact")
    assert {entry["kind"] for entry in validation_metadata["trash"]} == expected_trash_kinds
    assert validation_trash_rows == 0
    assert run(["--home", str(home), "--key", root_key, "audit", "show", validation_audit_id[:8], "--project", project_id]) == 2
    short_audit_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in short_audit_err
    assert "object ids must be complete" in short_audit_err
    assert run(["--home", str(home), "--key", root_key, "audit", "show", validation_audit_id, "extra", "--project", project_id]) == 2
    extra_audit_show_err = capsys.readouterr().err
    assert _field_labels(extra_audit_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_audit_show_err
    assert "audit show accepts exactly one audit id" in extra_audit_show_err
    assert run(["--home", str(home), "--key", root_key, "audit", "show", validation_audit_id, "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_audit_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_audit_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_audit_show_err
    assert "unsupported option --reason" in unsupported_audit_show_err

    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "project.goal", '"Observe everything"', "--project", project_id]) == 0
    config_out = capsys.readouterr().out
    assert _field_labels(config_out) == _project_config_set_field_labels()
    assert "runtime affecting: false" in config_out
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "show", "--project", project_id]) == 0
    config_show_out = capsys.readouterr().out
    assert _field_labels(config_show_out) == [
        "object",
        "project id",
        "config version",
        "version selector",
        "config hash",
        "project name",
        "task",
        "goal",
        "default source",
        "runner type",
        "sandbox",
        "runner working directory",
        "timeout seconds",
        "env mode",
        "reward type",
        "reward direction",
        "primary metric",
        "artifact glob count",
        "stdout limit bytes",
        "stderr limit bytes",
        "mutable summary",
        "visibility scope",
        "public exp create",
    ]
    assert "task:\n  Capture logs and artifacts" in config_show_out
    assert "goal:\n  Observe everything" in config_show_out
    assert "sandbox: not-declared" in config_show_out

    secret_gc_audits_before_unsupported = _audit_type_count(home, "gc", "secret_value")
    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id, "--apply", "--reason", "ignored"]) == 2
    unsupported_secret_gc_err = capsys.readouterr().err
    assert _field_labels(unsupported_secret_gc_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_secret_gc_err
    assert "unsupported option --reason" in unsupported_secret_gc_err
    assert _audit_type_count(home, "gc", "secret_value") == secret_gc_audits_before_unsupported

    assert run(["--home", str(home), "--key", admin_key, "project", "secret", "gc", "--project", project_id, "--apply"]) == 0
    secret_gc_out = capsys.readouterr().out
    assert _field_labels(secret_gc_out) == ["object", "project id", "dry run", "deleted count", "audit id"]
    assert "deleted count: 0" in secret_gc_out
    assert run(["--home", str(home), "--key", admin_key, "project", "locks", "clear-stale", "--project", project_id]) == 0
    lock_clear_out = capsys.readouterr().out
    assert _field_labels(lock_clear_out) == ["object", "project id", "cleared count", "audit id"]
    assert "cleared count: 0" in lock_clear_out
    with sqlite3.connect(home / "alab.db") as conn:
        conn.executemany(
            """
            INSERT INTO locks(lock_name, owner_operation_id, owner_host, owner_pid, project_id, exp_id, acquired_at, heartbeat_at, expires_at)
            VALUES (?, ?, 'test-host', 123, ?, NULL, '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z', ?)
            """,
            [
                ("lock-stale-manual", "op-stale", project_id, "2000-01-01T00:00:00Z"),
                ("lock-live-manual", "op-live", project_id, "2999-01-01T00:00:00Z"),
            ],
        )
    before_extra_lock_clear_audits = _audit_type_count(home, "clear", "lock")
    assert run(["--home", str(home), "--key", admin_key, "project", "locks", "clear-stale", "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_lock_clear_err = capsys.readouterr().err
    assert _field_labels(unsupported_lock_clear_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_lock_clear_err
    assert "unsupported option --reason" in unsupported_lock_clear_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM locks WHERE lock_name = 'lock-stale-manual'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM locks WHERE lock_name = 'lock-live-manual'").fetchone()[0] == 1
    assert _audit_type_count(home, "clear", "lock") == before_extra_lock_clear_audits
    assert run(["--home", str(home), "--key", admin_key, "project", "locks", "clear-stale", "extra", "--project", project_id]) == 2
    extra_lock_clear_err = capsys.readouterr().err
    assert _field_labels(extra_lock_clear_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_lock_clear_err
    assert "project locks clear-stale accepts no positional arguments" in extra_lock_clear_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM locks WHERE lock_name = 'lock-stale-manual'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM locks WHERE lock_name = 'lock-live-manual'").fetchone()[0] == 1
    assert _audit_type_count(home, "clear", "lock") == before_extra_lock_clear_audits

    assert run(["--home", str(home), "--key", admin_key, "project", "locks", "clear-stale", "--project", project_id]) == 0
    stale_lock_clear_out = capsys.readouterr().out
    assert _field_labels(stale_lock_clear_out) == ["object", "project id", "cleared count", "lock name", "audit id"]
    assert "cleared count: 1" in stale_lock_clear_out
    assert "lock name: lock-stale-manual" in stale_lock_clear_out
    assert "lock-live-manual" not in stale_lock_clear_out
    stale_lock_audit_id = _field(stale_lock_clear_out, "audit id")
    with sqlite3.connect(home / "alab.db") as conn:
        stale_lock_count = conn.execute("SELECT COUNT(*) FROM locks WHERE lock_name = 'lock-stale-manual'").fetchone()[0]
        live_lock_count = conn.execute("SELECT COUNT(*) FROM locks WHERE lock_name = 'lock-live-manual'").fetchone()[0]
        lock_audit = conn.execute(
            "SELECT actor_credential_id, project_id, exp_id, action, object_type, object_id, cascade, metadata_json FROM audit_events WHERE audit_id = ?",
            (stale_lock_audit_id,),
        ).fetchone()
        conn.execute("DELETE FROM locks WHERE lock_name = 'lock-live-manual'")
    assert stale_lock_count == 0
    assert live_lock_count == 1
    assert lock_audit[:7] == (admin_credential_id, project_id, None, "clear", "lock", project_id, 0)
    assert json.loads(lock_audit[7]) == {"schema_version": 1, "cleared_count": 1}

    export_path = tmp_path / "exported.toml"
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "export", "--project", project_id, "--out", str(export_path)]) == 0
    assert export_path.exists()
    assert "Observe everything" in export_path.read_text(encoding="utf-8")
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "export", "--project", project_id, "--out", str(export_path)]) == 2
    config_export_err = capsys.readouterr().err
    assert _field_labels(config_export_err) == _error_field_labels()
    assert "error code: OUTPUT_EXISTS" in config_export_err
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "export", "--project", project_id, "--out", str(export_path), "--overwrite"]) == 0
    config_export_out = capsys.readouterr().out
    assert _field_labels(config_export_out) == ["object", "project id", "config version", "out", "wrote", "secret mode"]

    assert run(["--home", str(home), "--key", admin_key, "source", "archive", default_source_id, "--project", project_id]) == 4
    default_source_archive_err = capsys.readouterr().err
    assert _field_labels(default_source_archive_err) == _error_field_labels()
    assert "error code: RESOURCE_BUSY" in default_source_archive_err
    assert "active default source cannot be archived" in default_source_archive_err
    assert _audit_count(home, "archive", "source", default_source_id) == 0

    config_ref_source = tmp_path / "source-config-ref"
    config_ref_source.mkdir()
    (config_ref_source / "main.py").write_text(
        """
import os
print("config ref")
with open(os.path.join(os.environ["ALAB_RUN_DIR"], "artifact.txt"), "w", encoding="utf-8") as fh:
    fh.write("config ref artifact")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert run(["--home", str(home), "--key", admin_key, "source", "import", "--project", project_id, "--source-path", str(config_ref_source), "--name", "config-ref"]) == 0
    config_ref_source_out = capsys.readouterr().out
    assert _field_labels(config_ref_source_out) == _source_import_field_labels()
    config_ref_source_id = _field(config_ref_source_out, "source id")
    config_ref_source_ref = _field(config_ref_source_out, "source ref")
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "config",
                "set",
                "source.default_source_ref",
                f'"{config_ref_source_ref}"',
                "--project",
                project_id,
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "config",
                "set",
                "source.default_source_ref",
                f'"{default_source_ref}"',
                "--project",
                project_id,
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert run(["--home", str(home), "--key", admin_key, "source", "archive", config_ref_source_id, "--project", project_id]) == 0
    config_ref_archive_out = capsys.readouterr().out
    assert _field_labels(config_ref_archive_out) == _source_status_field_labels()
    assert run(["--home", str(home), "--key", admin_key, "source", "remove", config_ref_source_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    config_ref_remove_out = capsys.readouterr().out
    assert _field_labels(config_ref_remove_out) == _source_remove_field_labels(dry_run=True, has_blocker=True)
    assert "blocker: referenced_by_config_version" in config_ref_remove_out
    _assert_remove_resource_busy(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "source",
            "remove",
            config_ref_source_id,
            "--project",
            project_id,
            "--force",
            "--confirm",
            config_ref_source_id,
            "--cascade",
        ],
        home,
        "source",
        config_ref_source_id,
        "referenced_by_config_version",
        capsys,
    )
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT source_id FROM sources WHERE source_id = ?", (config_ref_source_id,)).fetchone() is not None
    config_ref_source_ref_check = subprocess.run(
        ["git", "--git-dir", str(home / "projects" / project_id / "repo.git"), "rev-parse", "--verify", f"refs/heads/{config_ref_source_ref}"],
        capture_output=True,
        check=False,
    )
    assert config_ref_source_ref_check.returncode == 0

    source2 = tmp_path / "source2"
    source2.mkdir()
    (source2 / "main.py").write_text('print("second")\n', encoding="utf-8")
    source_count_before_extra_import = _table_count(home, "sources")
    source_add_audits_before_extra_import = _audit_type_count(home, "add", "source")
    assert run(["--home", str(home), "--key", admin_key, "source", "import", "extra", "--project", project_id, "--source-path", str(source2), "--name", "second-extra"]) == 2
    extra_source_import_err = capsys.readouterr().err
    assert _field_labels(extra_source_import_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_source_import_err
    assert "source import accepts no positional arguments" in extra_source_import_err
    assert _table_count(home, "sources") == source_count_before_extra_import
    assert _audit_type_count(home, "add", "source") == source_add_audits_before_extra_import
    assert run(["--home", str(home), "--key", admin_key, "source", "import", "--project", project_id, "--source-path", str(source2), "--name", "second"]) == 0
    source_import_out = capsys.readouterr().out
    assert _field_labels(source_import_out) == _source_import_field_labels()
    source_id = _field(source_import_out, "source id")
    source_ref = _field(source_import_out, "source ref")
    assert "deduped: false" in source_import_out
    for source_args, message in [
        (["source", "list", "extra"], "source list accepts no positional arguments"),
        (["source", "show", source_id, "extra"], "source show accepts at most one source selector"),
        (["source", "archive", source_id, "extra"], "source archive accepts exactly one source selector"),
        (["source", "unarchive", source_id, "extra"], "source unarchive accepts exactly one source selector"),
        (["source", "remove", source_id, "extra", "--dry-run"], "source remove accepts exactly one source selector"),
    ]:
        assert run(["--home", str(home), "--key", admin_key, *source_args, "--project", project_id]) == 2
        extra_source_selector_err = capsys.readouterr().err
        assert _field_labels(extra_source_selector_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in extra_source_selector_err
        assert message in extra_source_selector_err
    assert run(["--home", str(home), "--key", admin_key, "source", "list", "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_source_list_err = capsys.readouterr().err
    assert _field_labels(unsupported_source_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_source_list_err
    assert "unsupported option --reason" in unsupported_source_list_err
    assert _audit_count(home, "archive", "source", source_id) == 0
    assert _row_count(home, "sources", "source_id", source_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "source", "show", source_id, "--source-ref", source_ref, "--project", project_id]) == 2
    conflicting_source_show_err = capsys.readouterr().err
    assert _field_labels(conflicting_source_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in conflicting_source_show_err
    assert "source show accepts only one source selector" in conflicting_source_show_err
    assert run(["--home", str(home), "--key", admin_key, "source", "show", source_id, "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_source_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_source_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_source_show_err
    assert "unsupported option --reason" in unsupported_source_show_err
    assert run(["--home", str(home), "--key", admin_key, "source", "show", source_id[:8], "--project", project_id]) == 2
    short_source_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in short_source_err
    assert "object ids must be complete" in short_source_err
    assert run(["--home", str(home), "--key", root_key, "audit", "list", "--project", project_id, "--object-type", "source", "--object-id", source_id[:8]]) == 2
    short_audit_object_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in short_audit_object_err
    assert "object ids must be complete" in short_audit_object_err
    assert run(["--home", str(home), "--key", root_key, "audit", "list", "--project", project_id, "--object-type", "source", "--object-id", source_id]) == 0
    filtered_audit_out = capsys.readouterr().out
    assert _field_labels(filtered_audit_out) == [
        "object",
        "audit id",
        "project id",
        "exp id",
        "actor type",
        "actor credential id",
        "action",
        "object type",
        "object id",
        "cascade",
        "reason",
        "created at",
    ]
    source_audit_id = _field(filtered_audit_out, "audit id")
    assert "object type: source" in filtered_audit_out
    assert f"object id: {source_id}" in filtered_audit_out
    assert run(["--home", str(home), "--key", root_key, "audit", "list", "extra", "--project", project_id, "--object-type", "source", "--object-id", source_id]) == 2
    extra_audit_list_err = capsys.readouterr().err
    assert _field_labels(extra_audit_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_audit_list_err
    assert "audit list accepts no positional arguments" in extra_audit_list_err
    assert run(["--home", str(home), "--key", root_key, "audit", "list", "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_audit_list_err = capsys.readouterr().err
    assert _field_labels(unsupported_audit_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_audit_list_err
    assert "unsupported option --reason" in unsupported_audit_list_err
    assert run(["--home", str(home), "--key", root_key, "audit", "show", source_audit_id, "--project", project_id]) == 0
    audit_show_out = capsys.readouterr().out
    assert _field_labels(audit_show_out) == [
        "object",
        "audit id",
        "project id",
        "exp id",
        "actor type",
        "actor credential id",
        "action",
        "object type",
        "object id",
        "cascade",
        "reason",
        "deleted ids",
        "sanitized metadata",
        "created at",
    ]
    assert run(["--home", str(home), "--key", root_key, "audit", "list", "--project", project_id, "--object-type", "source", "--object-type", "experiment"]) == 2
    duplicate_audit_filter_err = capsys.readouterr().err
    assert _field_labels(duplicate_audit_filter_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_audit_filter_err
    assert "--object-type may be provided once" in duplicate_audit_filter_err
    actor_filter_id = _field(filtered_audit_out, "actor credential id")
    for args, message in [
        (["--actor", actor_filter_id, "--actor", actor_filter_id], "--actor may be provided once"),
        (["--limit", "1", "--limit", "2"], "--limit may be provided once"),
    ]:
        assert run(["--home", str(home), "--key", root_key, "audit", "list", "--project", project_id, *args]) == 2
        duplicate_audit_option_err = capsys.readouterr().err
        assert _field_labels(duplicate_audit_option_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_audit_option_err
        assert message in duplicate_audit_option_err
    assert run(["--home", str(home), "--key", root_key, "audit", "show", source_audit_id, "--project", project_id, "--project", project_id]) == 2
    duplicate_audit_project_err = capsys.readouterr().err
    assert _field_labels(duplicate_audit_project_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_audit_project_err
    assert "--project may be provided once" in duplicate_audit_project_err
    assert run(["--home", str(home), "--key", root_key, "audit", "list", "--project", project_id, "--limit", "not-an-int"]) == 2
    audit_limit_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in audit_limit_err
    assert "--limit and --offset must be integers" in audit_limit_err
    assert run(["--home", str(home), "--key", root_key, "audit", "list", "--project", project_id, "--offset", "-1"]) == 2
    audit_offset_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in audit_offset_err
    assert "invalid audit pagination" in audit_offset_err
    assert run(["--home", str(home), "--key", root_key, "audit", "list", "--object-type", "catalog", "--object-id", "not-skydiscover"]) == 2
    literal_audit_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in literal_audit_err
    assert "--object-id must be one of skydiscover" in literal_audit_err
    assert run(["--home", str(home), "--key", admin_key, "source", "show", source_id, "--project", project_id]) == 0
    source_show_out = capsys.readouterr().out
    assert _field_labels(source_show_out) == [
        "object",
        "source id",
        "source ref",
        "source name",
        "status",
        "source commit",
        "tree hash",
        "origin type",
        "origin summary",
    ]
    assert run(["--home", str(home), "--key", admin_key, "source", "archive", source_id, "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_source_archive_err = capsys.readouterr().err
    assert _field_labels(unsupported_source_archive_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_source_archive_err
    assert "unsupported option --reason" in unsupported_source_archive_err
    assert _audit_count(home, "archive", "source", source_id) == 0
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM sources WHERE source_id = ?", (source_id,)).fetchone()[0] == "active"
    assert run(["--home", str(home), "--key", admin_key, "source", "archive", source_id, "--project", project_id]) == 0
    source_archive_out = capsys.readouterr().out
    assert _field_labels(source_archive_out) == _source_status_field_labels()
    assert "previous status: active" in source_archive_out
    source_archived_at = _field(source_archive_out, "archived at")
    assert _audit_count(home, "archive", "source", source_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "source", "list", "--project", project_id]) == 0
    archived_hidden_sources = capsys.readouterr().out
    assert all(labels == _source_list_field_labels() for labels in _block_labels(archived_hidden_sources))
    assert f"source id: {source_id}" not in archived_hidden_sources
    assert f"source id: {default_source_id}" in archived_hidden_sources
    assert run(["--home", str(home), "--key", admin_key, "source", "list", "--project", project_id, "--include-archived"]) == 0
    archived_included_sources = capsys.readouterr().out
    assert all(labels == _source_list_field_labels() for labels in _block_labels(archived_included_sources))
    assert f"source id: {source_id}" in archived_included_sources
    assert "status: archived" in archived_included_sources
    assert run(["--home", str(home), "--key", admin_key, "source", "archive", source_id, "--project", project_id]) == 0
    source_archive_repeat_out = capsys.readouterr().out
    assert _field_labels(source_archive_repeat_out) == _source_status_field_labels()
    assert "previous status: archived" in source_archive_repeat_out
    assert _field(source_archive_repeat_out, "archived at") == source_archived_at
    assert _audit_count(home, "archive", "source", source_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "source", "unarchive", source_id, "--project", project_id]) == 0
    source_unarchive_out = capsys.readouterr().out
    assert _field_labels(source_unarchive_out) == _source_status_field_labels(unarchive=True)
    assert "source status: active" in source_unarchive_out
    assert _audit_count(home, "unarchive", "source", source_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "source", "unarchive", source_id, "--project", project_id]) == 0
    source_unarchive_repeat_out = capsys.readouterr().out
    assert _field_labels(source_unarchive_repeat_out) == _source_status_field_labels(unarchive=True)
    assert "previous status: active" in source_unarchive_repeat_out
    assert _field(source_unarchive_repeat_out, "unarchived at") == "none"
    assert _audit_count(home, "unarchive", "source", source_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "source", "list", "--project", project_id]) == 0
    source_list_out = capsys.readouterr().out
    assert all(labels == _source_list_field_labels() for labels in _block_labels(source_list_out))
    assert f"source id: {source_id}" in source_list_out
    assert run(["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--dry-run"]) == 0
    active_source_remove_dry_run = capsys.readouterr().out
    assert _field_labels(active_source_remove_dry_run) == _source_remove_field_labels(dry_run=True, has_blocker=True)
    assert "blocker: target_not_archived" in active_source_remove_dry_run
    _assert_remove_dry_run_preserved(home, "source", source_id, "sources", "source_id")
    _assert_not_archived_remove_blocked(
        ["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--force", "--confirm", source_id],
        home,
        "source",
        source_id,
        capsys,
    )
    dependent_worktree = tmp_path / "source-dependent-exp"
    assert run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "exp",
            "create",
            "--project",
            project_id,
            "--name",
            "source-dependent",
            "--source-ref",
            source_ref,
            "--path",
            str(dependent_worktree),
        ]
    ) == 0
    dependent_exp_out = capsys.readouterr().out
    assert _field_labels(dependent_exp_out) == _exp_create_field_labels()
    dependent_exp_id = _field(dependent_exp_out, "exp id")
    assert f"source id: {source_id}" in dependent_exp_out
    assert run(["--home", str(home), "--key", admin_key, "source", "archive", source_id, "--project", project_id]) == 0
    source_archive_again_out = capsys.readouterr().out
    assert _field_labels(source_archive_again_out) == _source_status_field_labels()
    assert run(["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--dry-run"]) == 0
    source_remove_dry_run = capsys.readouterr().out
    assert _field_labels(source_remove_dry_run) == _source_remove_field_labels(dry_run=True, has_blocker=True)
    assert "removed: false" in source_remove_dry_run
    assert "blocker: dependent_records_require_cascade" in source_remove_dry_run
    _assert_remove_resource_busy(
        ["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--force", "--confirm", source_id],
        home,
        "source",
        source_id,
        "dependent_records_require_cascade",
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    source_remove_open_cascade = capsys.readouterr().out
    assert _field_labels(source_remove_open_cascade) == _source_remove_field_labels(dry_run=True, has_blocker=True)
    assert "blocker: dependent_records_not_archived" in source_remove_open_cascade
    _assert_remove_resource_busy(
        ["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--force", "--confirm", source_id, "--cascade"],
        home,
        "source",
        source_id,
        "dependent_records_not_archived",
        capsys,
    )
    _assert_remove_dry_run_preserved(home, "source", source_id, "sources", "source_id")
    assert _row_count(home, "experiments", "exp_id", dependent_exp_id) == 1
    source_ref_check_before_dependency_archive = subprocess.run(
        ["git", "--git-dir", str(home / "projects" / project_id / "repo.git"), "rev-parse", "--verify", f"refs/heads/{source_ref}"],
        capture_output=True,
        check=False,
    )
    assert source_ref_check_before_dependency_archive.returncode == 0
    assert run(["--home", str(home), "--key", admin_key, "exp", "archive", dependent_exp_id, "--project", project_id]) == 0
    dependent_archive_out = capsys.readouterr().out
    assert _field_labels(dependent_archive_out) == _experiment_status_field_labels()
    assert run(["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--dry-run"]) == 0
    source_remove_archived_dry_run = capsys.readouterr().out
    assert _field_labels(source_remove_archived_dry_run) == _source_remove_field_labels(dry_run=True, has_blocker=True)
    assert "blocker: dependent_records_require_cascade" in source_remove_archived_dry_run
    assert run(["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    source_remove_cascade_dry_run = capsys.readouterr().out
    assert _field_labels(source_remove_cascade_dry_run) == _source_remove_field_labels(dry_run=True)
    assert "cascade: true" in source_remove_cascade_dry_run
    assert "removed: false" in source_remove_cascade_dry_run
    _assert_remove_dry_run_preserved(home, "source", source_id, "sources", "source_id")
    _assert_confirm_guard(
        ["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--cascade"],
        source_id,
        "source remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "source", "remove", source_id, "--project", project_id, "--force", "--confirm", source_id, "--cascade"]) == 0
    source_remove_out = capsys.readouterr().out
    assert _field_labels(source_remove_out) == _source_remove_field_labels(dry_run=False)
    assert "removed: true" in source_remove_out
    source_remove_audit_id = _field(source_remove_out, "audit id")
    with sqlite3.connect(home / "alab.db") as conn:
        conn.row_factory = sqlite3.Row
        assert conn.execute("SELECT source_id FROM sources WHERE source_id = ?", (source_id,)).fetchone() is None
        dependent_row = conn.execute("SELECT status, source_id FROM experiments WHERE exp_id = ?", (dependent_exp_id,)).fetchone()
        source_audit_row = conn.execute(
            """
            SELECT actor_credential_id, action, object_type, object_id, project_id, exp_id, cascade, reason, metadata_json
            FROM audit_events
            WHERE audit_id = ?
            """,
            (source_remove_audit_id,),
        ).fetchone()
        assert dependent_row is not None
        assert dependent_row["status"] == "archived"
        assert dependent_row["source_id"] == source_id
    assert tuple(source_audit_row)[:8] == (admin_credential_id, "remove", "source", source_id, project_id, None, 1, None)
    source_metadata = json.loads(source_audit_row["metadata_json"])
    assert source_metadata["branch_ref"] == f"refs/heads/{source_ref}"
    assert source_metadata["branch_ref_commit"]
    assert source_metadata["branch_ref_deleted"] is True
    assert source_metadata["branch_ref_already_absent"] is False
    source_ref_check = subprocess.run(
        ["git", "--git-dir", str(home / "projects" / project_id / "repo.git"), "rev-parse", "--verify", f"refs/heads/{source_ref}"],
        capture_output=True,
        check=False,
    )
    assert source_ref_check.returncode != 0

    worktree = tmp_path / "exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "attempt", "--path", str(worktree)]) == 0
    exp_out = capsys.readouterr().out
    exp_id = _field(exp_out, "exp id")

    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "exp", "show", exp_id, "extra"]) == 2
    extra_exp_show_err = capsys.readouterr().err
    assert _field_labels(extra_exp_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_exp_show_err
    assert "exp show accepts exactly one experiment id" in extra_exp_show_err
    assert run(["--home", str(home), "exp", "show", exp_id, "--reason", "ignored"]) == 2
    unsupported_exp_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_exp_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_exp_show_err
    assert "unsupported option --reason" in unsupported_exp_show_err
    assert run(["--home", str(home), "exp", "tag", "list", exp_id, "extra"]) == 2
    extra_tag_list_err = capsys.readouterr().err
    assert _field_labels(extra_tag_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_tag_list_err
    assert "exp tag list accepts at most one experiment id" in extra_tag_list_err
    assert run(["--home", str(home), "exp", "tag", "add", exp_id, "baseline"]) == 0
    tag_add_out = capsys.readouterr().out
    assert _field_labels(tag_add_out) == ["object", "exp id", "tag", "action", "tags"]
    assert "tag: baseline" in tag_add_out
    assert run(["--home", str(home), "exp", "tag", "add", exp_id, "BASELINE"]) == 0
    duplicate_tag_add_out = capsys.readouterr().out
    assert _field_labels(duplicate_tag_add_out) == ["object", "exp id", "tag", "action", "tags"]
    assert "tag: baseline" in duplicate_tag_add_out
    assert duplicate_tag_add_out.count("tags: baseline") == 1
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM experiment_tags WHERE exp_id = ? AND tag_slug = 'baseline'", (exp_id,)).fetchone()[0] == 1
    assert run(["--home", str(home), "--key", root_key, "exp", "tag", "add", exp_id, "root-visible", "--project", project_id]) == 0
    root_tag_add_out = capsys.readouterr().out
    assert _field_labels(root_tag_add_out) == ["object", "exp id", "tag", "action", "tags", "tags"]
    assert "tag: root-visible" in root_tag_add_out
    assert run(["--home", str(home), "--key", admin_key, "exp", "tag", "remove", exp_id, "root-visible", "--project", project_id]) == 0
    admin_tag_remove_out = capsys.readouterr().out
    assert _field_labels(admin_tag_remove_out) == ["object", "exp id", "tag", "action", "tags"]
    assert "tag: root-visible" in admin_tag_remove_out
    assert run(["--home", str(home), "exp", "tag", "list", exp_id]) == 0
    tag_list_out = capsys.readouterr().out
    assert _field_labels(tag_list_out) == ["object", "exp id", "tag", "action", "tags"]
    assert "tags: baseline" in tag_list_out
    assert run(["--home", str(home), "exp", "tag", "remove", exp_id, "baseline"]) == 0
    tag_remove_out = capsys.readouterr().out
    assert _field_labels(tag_remove_out) == ["object", "exp id", "tag", "action"]
    assert "action: remove" in tag_remove_out
    with sqlite3.connect(home / "alab.db") as conn:
        before_extra_tag_positionals = conn.execute("SELECT COUNT(*) FROM experiment_tags WHERE exp_id = ?", (exp_id,)).fetchone()[0]
    assert run(["--home", str(home), "exp", "tag", "add", exp_id, "baseline", "extra"]) == 2
    extra_tag_add_err = capsys.readouterr().err
    assert _field_labels(extra_tag_add_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_tag_add_err
    assert "exp tag add requires exp id and tag" in extra_tag_add_err
    assert run(["--home", str(home), "exp", "tag", "remove", exp_id, "baseline", "extra"]) == 2
    extra_tag_remove_err = capsys.readouterr().err
    assert _field_labels(extra_tag_remove_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_tag_remove_err
    assert "exp tag remove requires exp id and tag" in extra_tag_remove_err
    assert run(["--home", str(home), "exp", "tag", "add", exp_id, "baseline", "--reason", "ignored"]) == 2
    unsupported_tag_add_err = capsys.readouterr().err
    assert _field_labels(unsupported_tag_add_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_tag_add_err
    assert "unsupported option --reason" in unsupported_tag_add_err
    assert run(["--home", str(home), "exp", "tag", "remove", exp_id, "baseline", "--reason", "ignored"]) == 2
    unsupported_tag_remove_err = capsys.readouterr().err
    assert _field_labels(unsupported_tag_remove_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_tag_remove_err
    assert "unsupported option --reason" in unsupported_tag_remove_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM experiment_tags WHERE exp_id = ?", (exp_id,)).fetchone()[0] == before_extra_tag_positionals

    assert run(["--home", str(home), "run", "--message", "capture"]) == 0
    run_out = capsys.readouterr().out
    assert _field_labels(run_out) == _run_field_labels(warning_count=1)
    run_id = _field(run_out, "run id")
    assert "run status: passed" in run_out
    assert "created commit:" in run_out
    assert "created commit: unknown" not in run_out
    assert "stdout preview:\n  hello from runner" in run_out
    assert "artifact count: 1" in run_out
    assert "warning code: ENV_MODE_FULL_UNREDACTED_HOST_ENV" in run_out
    assert run(["--home", str(home), "runs", "show", run_id, "extra"]) == 2
    extra_run_show_err = capsys.readouterr().err
    assert _field_labels(extra_run_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_run_show_err
    assert "runs show accepts exactly one run id" in extra_run_show_err
    assert run(["--home", str(home), "runs", "show", run_id, "--reason", "ignored"]) == 2
    unsupported_run_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_run_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_run_show_err
    assert "unsupported option --reason" in unsupported_run_show_err

    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--status", "passed", "--runner-type", "local", "--exit-code", "0", "--limit", "1"]) == 0
    filtered_runs = capsys.readouterr().out
    run_list_labels = [
        "object",
        "run id",
        "exp id",
        "commit",
        "run status",
        "exit code",
        "reward",
        "reward parse status",
        "config version",
        "stdout preview",
        "stderr preview",
        "artifact count",
        "log count",
        "hidden log available",
        "started at",
        "ended at",
        "warning code",
    ]
    assert _field_labels(filtered_runs) == run_list_labels
    assert f"run id: {run_id}" in filtered_runs
    assert "artifact count: 1" in filtered_runs
    assert "warning code: ENV_MODE_FULL_UNREDACTED_HOST_ENV" in filtered_runs
    run_commit = _field(filtered_runs, "commit")
    run_config_version = _field(filtered_runs, "config version")
    run_reward = _field(filtered_runs, "reward")
    run_started = _field(filtered_runs, "started at")
    run_ended = _field(filtered_runs, "ended at")
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--config-version", run_config_version, "--commit", run_commit, "--reward-min", run_reward, "--reward-max", run_reward, "--started-after", run_started, "--started-before", run_started, "--ended-after", run_ended, "--ended-before", run_ended]) == 0
    bounded_runs = capsys.readouterr().out
    assert _field_labels(bounded_runs) == run_list_labels
    assert f"run id: {run_id}" in bounded_runs
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--commit", run_commit[:12]]) == 0
    abbreviated_commit_runs = capsys.readouterr().out
    assert _field_labels(abbreviated_commit_runs) == run_list_labels
    assert f"run id: {run_id}" in abbreviated_commit_runs
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--commit", "HEAD"]) == 2
    invalid_commit_runs_err = capsys.readouterr().err
    assert _field_labels(invalid_commit_runs_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in invalid_commit_runs_err
    assert "--commit must be a commit SHA" in invalid_commit_runs_err
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--reward-min", "2"]) == 0
    reward_miss_runs = capsys.readouterr().out
    assert _field_labels(reward_miss_runs) == []
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--reward-min", "2", "--reward-max", "1"]) == 2
    inverted_run_reward_err = capsys.readouterr().err
    assert _field_labels(inverted_run_reward_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in inverted_run_reward_err
    assert "--reward-min must be less than or equal to --reward-max" in inverted_run_reward_err
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--started-after", "2999-01-01T00:00:00Z"]) == 0
    future_runs = capsys.readouterr().out
    assert _field_labels(future_runs) == []
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--sort", "reward:desc"]) == 0
    sorted_runs = capsys.readouterr().out
    assert f"run id: {run_id}" in sorted_runs
    assert run(["--home", str(home), "observe", "experiments", "show", exp_id]) == 0
    canonical_exp_show = capsys.readouterr().out
    assert run(["exp", "show", exp_id, "--home", str(home)]) == 0
    assert capsys.readouterr().out == canonical_exp_show
    assert run(["--home", str(home), "observe", "runs", "list", "--exp", exp_id, "--limit", "1"]) == 0
    canonical_runs_list = capsys.readouterr().out
    assert run(["runs", "list", "--exp", exp_id, "--limit", "1", "--home", str(home)]) == 0
    assert capsys.readouterr().out == canonical_runs_list
    assert run(["--home", str(home), "runs", "show", run_id[:8]]) == 2
    short_run_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in short_run_err
    assert "object ids must be complete" in short_run_err
    assert run(["--home", str(home), "runs", "list", "--status", "bogus"]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().err
    assert run(["--home", str(home), "runs", "list", "--sort", "bogus:asc"]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().err
    duplicate_run_list_cases = [
        (
            ["--status", "passed", "--status", "failed"],
            "--status may be provided once",
        ),
        (
            ["--limit", "1", "--limit", "2"],
            "--limit may be provided once",
        ),
        (
            ["--sort", "started:desc", "--sort", "ended:asc"],
            "--sort may be provided once",
        ),
        (
            ["--project", project_id, "--project", project_id],
            "--project may be provided once",
        ),
    ]
    for list_args, message in duplicate_run_list_cases:
        assert run(["--home", str(home), "runs", "list", *list_args]) == 2
        duplicate_run_list_err = capsys.readouterr().err
        assert _field_labels(duplicate_run_list_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_run_list_err
        assert message in duplicate_run_list_err
    assert run(["--home", str(home), "runs", "list", "extra", "--exp", exp_id]) == 2
    extra_runs_list_err = capsys.readouterr().err
    assert _field_labels(extra_runs_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_runs_list_err
    assert "runs list accepts no positional arguments" in extra_runs_list_err
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--reason", "ignored"]) == 2
    unsupported_runs_list_err = capsys.readouterr().err
    assert _field_labels(unsupported_runs_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_runs_list_err
    assert "unsupported option --reason" in unsupported_runs_list_err

    assert run(["--home", str(home), "logs", "list"]) == 0
    logs_out = capsys.readouterr().out
    assert _block_labels(logs_out)[0] == _log_field_labels()
    log_id = _field(logs_out, "log id")
    assert "preview:" in logs_out
    assert run(["--home", str(home), "logs", "show", log_id]) == 0
    log_show = capsys.readouterr().out
    assert _field_labels(log_show) == _log_show_field_labels()
    assert "content:" in log_show
    assert "  hello from runner" in log_show
    assert run(["--home", str(home), "logs", "show", log_id, "extra"]) == 2
    extra_log_show_err = capsys.readouterr().err
    assert _field_labels(extra_log_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_log_show_err
    assert "logs show accepts exactly one log id" in extra_log_show_err
    assert run(["--home", str(home), "logs", "show", log_id, "--reason", "ignored"]) == 2
    unsupported_log_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_log_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_log_show_err
    assert "unsupported option --reason" in unsupported_log_show_err
    assert run(["--home", str(home), "logs", "list", "--run", run_id, "--stream", "stdout", "--truncated", "false"]) == 0
    stdout_logs = capsys.readouterr().out
    assert "stream: stdout" in stdout_logs
    assert "stream: stderr" not in stdout_logs
    stdout_log_id = _field(stdout_logs, "log id")
    with sqlite3.connect(home / "alab.db") as conn:
        stdout_log_created = conn.execute("SELECT created_at FROM log_streams WHERE log_id = ?", (stdout_log_id,)).fetchone()[0]
    assert run(["--home", str(home), "logs", "list", "--run", run_id, "--stream", "stdout", "--created-after", stdout_log_created, "--created-before", stdout_log_created]) == 0
    created_filtered_logs = capsys.readouterr().out
    assert _field_labels(created_filtered_logs) == _log_field_labels()
    assert f"log id: {stdout_log_id}" in created_filtered_logs
    assert run(["--home", str(home), "logs", "list", "--run", run_id, "--created-after", "2999-01-01T00:00:00Z"]) == 0
    future_filtered_logs = capsys.readouterr().out
    assert _field_labels(future_filtered_logs) == []
    assert run(["--home", str(home), "logs", "list", "--run", run_id[:8]]) == 2
    assert "object ids must be complete" in capsys.readouterr().err
    assert run(["--home", str(home), "logs", "list", "--include-hidden"]) == 4
    assert "SCOPE_VIOLATION" in capsys.readouterr().err
    assert run(["--home", str(home), "logs", "list", "--run", run_id, "--sort", "stream:asc"]) == 0
    sorted_logs_asc = capsys.readouterr().out
    assert sorted_logs_asc.index("stream: stderr") < sorted_logs_asc.index("stream: stdout")
    assert run(["--home", str(home), "observe", "logs", "list", "--run", run_id, "--sort", "stream:asc"]) == 0
    canonical_logs_list = capsys.readouterr().out
    assert run(["logs", "list", "--run", run_id, "--sort", "stream:asc", "--home", str(home)]) == 0
    assert capsys.readouterr().out == canonical_logs_list
    assert run(["--home", str(home), "logs", "list", "--run", run_id, "--sort", "stream:desc"]) == 0
    sorted_logs_desc = capsys.readouterr().out
    assert sorted_logs_desc.index("stream: stdout") < sorted_logs_desc.index("stream: stderr")
    assert run(["--home", str(home), "logs", "list", "--sort", "bogus:desc"]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().err
    assert run(["--home", str(home), "logs", "list", "--stream", "stdout", "--stream", "stderr"]) == 2
    duplicate_log_stream_err = capsys.readouterr().err
    assert _field_labels(duplicate_log_stream_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_log_stream_err
    assert "--stream may be provided once" in duplicate_log_stream_err
    for list_args, message in [
        (["--limit", "1", "--limit", "2"], "--limit may be provided once"),
        (["--sort", "created:desc", "--sort", "stream:asc"], "--sort may be provided once"),
        (["--truncated", "false", "--truncated", "true"], "--truncated may be provided once"),
    ]:
        assert run(["--home", str(home), "logs", "list", *list_args]) == 2
        duplicate_log_list_err = capsys.readouterr().err
        assert _field_labels(duplicate_log_list_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_log_list_err
        assert message in duplicate_log_list_err
    assert run(["--home", str(home), "logs", "list", "extra", "--run", run_id]) == 2
    extra_logs_list_err = capsys.readouterr().err
    assert _field_labels(extra_logs_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_logs_list_err
    assert "logs list accepts no positional arguments" in extra_logs_list_err
    assert run(["--home", str(home), "logs", "list", "--run", run_id, "--reason", "ignored"]) == 2
    unsupported_logs_list_err = capsys.readouterr().err
    assert _field_labels(unsupported_logs_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_logs_list_err
    assert "unsupported option --reason" in unsupported_logs_list_err

    log_out = tmp_path / "stdout.log"
    assert run(["--home", str(home), "--key", admin_key, "logs", "remove", log_id, "--project", project_id, "--dry-run"]) == 0
    active_log_remove_dry_run = capsys.readouterr().out
    assert _field_labels(active_log_remove_dry_run) == _observe_remove_field_labels("log", dry_run=True, has_blocker=True, filesystem_path_count=1)
    assert "blocker: target_not_archived" in active_log_remove_dry_run
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "logs", "remove", log_id, "--project", project_id, "--dry-run", "--dry-run"], "--dry-run", capsys)
    _assert_remove_dry_run_preserved(home, "log", log_id, "log_streams", "log_id")
    _assert_not_archived_remove_blocked(
        ["--home", str(home), "--key", admin_key, "logs", "remove", log_id, "--project", project_id, "--force", "--confirm", log_id],
        home,
        "log",
        log_id,
        capsys,
    )
    duplicate_log_out_a = tmp_path / "duplicate-log-a.log"
    duplicate_log_out_b = tmp_path / "duplicate-log-b.log"
    assert run(["--home", str(home), "logs", "export", log_id, "--out", str(duplicate_log_out_a), "--out", str(duplicate_log_out_b)]) == 2
    duplicate_log_out_err = capsys.readouterr().err
    assert _field_labels(duplicate_log_out_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_log_out_err
    assert "--out may be provided once" in duplicate_log_out_err
    assert not duplicate_log_out_a.exists()
    assert not duplicate_log_out_b.exists()
    extra_log_export = tmp_path / "extra-log.log"
    assert run(["--home", str(home), "logs", "export", log_id, "extra", "--out", str(extra_log_export)]) == 2
    extra_log_export_err = capsys.readouterr().err
    assert _field_labels(extra_log_export_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_log_export_err
    assert "logs export accepts exactly one log id" in extra_log_export_err
    assert not extra_log_export.exists()
    unsupported_log_export = tmp_path / "unsupported-log.log"
    assert run(["--home", str(home), "logs", "export", log_id, "--out", str(unsupported_log_export), "--reason", "ignored"]) == 2
    unsupported_log_export_err = capsys.readouterr().err
    assert _field_labels(unsupported_log_export_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_log_export_err
    assert "unsupported option --reason" in unsupported_log_export_err
    assert not unsupported_log_export.exists()
    assert run(["--home", str(home), "logs", "export", log_id, "--out", str(log_out)]) == 0
    log_export_out = capsys.readouterr().out
    assert _field_labels(log_export_out) == _log_field_labels()
    assert f"out: {log_out}" in log_export_out
    assert "hello from runner" in log_out.read_text(encoding="utf-8")
    assert run(["--home", str(home), "logs", "export", log_id, "--out", str(log_out)]) == 2
    log_export_err = capsys.readouterr().err
    assert _field_labels(log_export_err) == _error_field_labels()
    assert "error code: OUTPUT_EXISTS" in log_export_err
    assert run(["--home", str(home), "logs", "export", log_id, "--out", str(log_out), "--overwrite"]) == 0
    log_overwrite_out = capsys.readouterr().out
    assert _field_labels(log_overwrite_out) == _log_field_labels()
    assert run(["--home", str(home), "logs", "export", log_id, "--out", str(tmp_path / "missing-log-parent" / "stdout.log")]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().err
    assert run(["--home", str(home), "logs", "archive", log_id, "extra"]) == 2
    extra_log_archive_err = capsys.readouterr().err
    assert _field_labels(extra_log_archive_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_log_archive_err
    assert "log archive accepts exactly one object id" in extra_log_archive_err
    assert _audit_count(home, "archive", "log", log_id) == 0
    assert run(["--home", str(home), "logs", "archive", log_id, "--reason", "ignored"]) == 2
    unsupported_log_archive_err = capsys.readouterr().err
    assert _field_labels(unsupported_log_archive_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_log_archive_err
    assert "unsupported option --reason" in unsupported_log_archive_err
    assert _audit_count(home, "archive", "log", log_id) == 0
    assert run(["--home", str(home), "logs", "archive", log_id]) == 0
    archived_log_out = capsys.readouterr().out
    assert _field_labels(archived_log_out) == _archive_field_labels("log")
    assert "archive status: archived" in archived_log_out
    assert run(["--home", str(home), "logs", "list", "--run", run_id, "--stream", "stdout"]) == 0
    archived_hidden_logs = capsys.readouterr().out
    assert _field_labels(archived_hidden_logs) == []
    assert log_id not in archived_hidden_logs
    assert run(["--home", str(home), "logs", "list", "--run", run_id, "--stream", "stdout", "--include-archived"]) == 0
    archived_included_logs = capsys.readouterr().out
    assert _field_labels(archived_included_logs) == _log_field_labels()
    assert f"log id: {log_id}" in archived_included_logs
    assert "archive status: archived" in archived_included_logs
    assert run(["--home", str(home), "logs", "show", log_id]) == 0
    archived_log_show = capsys.readouterr().out
    assert _field_labels(archived_log_show) == _log_show_field_labels()
    assert "archive status: archived" in archived_log_show
    assert "content:" in archived_log_show
    assert "  hello from runner" in archived_log_show
    archived_log_export = tmp_path / "archived-stdout.log"
    assert run(["--home", str(home), "logs", "export", log_id, "--out", str(archived_log_export)]) == 2
    archived_log_export_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in archived_log_export_err
    assert "exporting archived logs requires --include-archived" in archived_log_export_err
    assert run(["--home", str(home), "logs", "export", log_id, "--out", str(archived_log_export), "--include-archived"]) == 0
    archived_log_export_out = capsys.readouterr().out
    assert _field_labels(archived_log_export_out) == _log_field_labels()
    assert "hello from runner" in archived_log_export.read_text(encoding="utf-8")
    assert run(["--home", str(home), "logs", "unarchive", log_id]) == 0
    unarchived_log_out = capsys.readouterr().out
    assert _field_labels(unarchived_log_out) == _unarchive_field_labels("log")
    assert "archive status: active" in unarchived_log_out

    assert run(["--home", str(home), "artifacts", "list"]) == 0
    artifacts_out = capsys.readouterr().out
    assert _field_labels(artifacts_out) == _artifact_field_labels()
    artifact_id = _field(artifacts_out, "artifact id")
    artifact_hash = _field(artifacts_out, "content hash")
    artifact_size = _field(artifacts_out, "size bytes")
    artifact_created = _field(artifacts_out, "created at")
    assert run(["--home", str(home), "artifacts", "show", artifact_id, "extra"]) == 2
    extra_artifact_show_err = capsys.readouterr().err
    assert _field_labels(extra_artifact_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_artifact_show_err
    assert "artifacts show accepts exactly one artifact id" in extra_artifact_show_err
    assert run(["--home", str(home), "artifacts", "show", artifact_id, "--reason", "ignored"]) == 2
    unsupported_artifact_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_artifact_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_artifact_show_err
    assert "unsupported option --reason" in unsupported_artifact_show_err
    assert run(["--home", str(home), "artifacts", "list", "--exp", exp_id, "--run", run_id, "--root", "run", "--status", "captured", "--path-query", "artifact", "--content-hash", artifact_hash, "--size-min", "1", "--size-max", artifact_size, "--created-after", artifact_created, "--created-before", artifact_created, "--limit", "1"]) == 0
    filtered_artifacts = capsys.readouterr().out
    assert _field_labels(filtered_artifacts) == _artifact_field_labels()
    assert f"artifact id: {artifact_id}" in filtered_artifacts
    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--size-min", str(int(artifact_size) + 1), "--size-max", artifact_size]) == 2
    inverted_artifact_size_err = capsys.readouterr().err
    assert _field_labels(inverted_artifact_size_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in inverted_artifact_size_err
    assert "--size-min must be less than or equal to --size-max" in inverted_artifact_size_err
    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--content-hash", "sha256:" + "0" * 64]) == 0
    hash_miss_artifacts = capsys.readouterr().out
    assert _field_labels(hash_miss_artifacts) == []
    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--content-hash", "not-a-hash"]) == 2
    invalid_artifact_hash_err = capsys.readouterr().err
    assert _field_labels(invalid_artifact_hash_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in invalid_artifact_hash_err
    assert "--content-hash must be sha256:<64-hex>" in invalid_artifact_hash_err
    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--created-after", "2999-01-01T00:00:00Z"]) == 0
    future_artifacts = capsys.readouterr().out
    assert _field_labels(future_artifacts) == []
    assert run(["--home", str(home), "artifacts", "export", artifact_id[:8], "--out", str(tmp_path / "short-artifact.txt")]) == 2
    assert "object ids must be complete" in capsys.readouterr().err
    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--sort", "path:asc"]) == 0
    sorted_artifacts = capsys.readouterr().out
    assert f"artifact id: {artifact_id}" in sorted_artifacts
    assert run(["--home", str(home), "artifacts", "list", "--content-hash", artifact_hash, "--content-hash", "sha256:" + "0" * 64]) == 2
    duplicate_artifact_hash_err = capsys.readouterr().err
    assert _field_labels(duplicate_artifact_hash_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_artifact_hash_err
    assert "--content-hash may be provided once" in duplicate_artifact_hash_err
    for list_args, message in [
        (["--limit", "1", "--limit", "2"], "--limit may be provided once"),
        (["--sort", "created:desc", "--sort", "path:asc"], "--sort may be provided once"),
        (["--run", run_id, "--run", run_id], "--run may be provided once"),
    ]:
        assert run(["--home", str(home), "artifacts", "list", *list_args]) == 2
        duplicate_artifact_list_err = capsys.readouterr().err
        assert _field_labels(duplicate_artifact_list_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_artifact_list_err
        assert message in duplicate_artifact_list_err
    assert run(["--home", str(home), "artifacts", "list", "extra", "--run", run_id]) == 2
    extra_artifacts_list_err = capsys.readouterr().err
    assert _field_labels(extra_artifacts_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_artifacts_list_err
    assert "artifacts list accepts no positional arguments" in extra_artifacts_list_err
    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--reason", "ignored"]) == 2
    unsupported_artifacts_list_err = capsys.readouterr().err
    assert _field_labels(unsupported_artifacts_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_artifacts_list_err
    assert "unsupported option --reason" in unsupported_artifacts_list_err
    assert run(["--home", str(home), "observe", "artifacts", "list", "--run", run_id, "--sort", "path:asc"]) == 0
    canonical_artifacts_list = capsys.readouterr().out
    assert run(["artifacts", "list", "--run", run_id, "--sort", "path:asc", "--home", str(home)]) == 0
    assert capsys.readouterr().out == canonical_artifacts_list

    artifact_out = tmp_path / "artifact.txt"
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "remove", artifact_id, "--project", project_id, "--dry-run"]) == 0
    active_artifact_remove_dry_run = capsys.readouterr().out
    assert _field_labels(active_artifact_remove_dry_run) == _observe_remove_field_labels("artifact", dry_run=True, has_blocker=True)
    assert "blocker: target_not_archived" in active_artifact_remove_dry_run
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "artifacts", "remove", artifact_id, "--project", project_id, "--dry-run", "--dry-run"], "--dry-run", capsys)
    _assert_remove_dry_run_preserved(home, "artifact", artifact_id, "artifacts", "artifact_id")
    _assert_not_archived_remove_blocked(
        ["--home", str(home), "--key", admin_key, "artifacts", "remove", artifact_id, "--project", project_id, "--force", "--confirm", artifact_id],
        home,
        "artifact",
        artifact_id,
        capsys,
    )
    duplicate_artifact_out_a = tmp_path / "duplicate-artifact-a.txt"
    duplicate_artifact_out_b = tmp_path / "duplicate-artifact-b.txt"
    assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(duplicate_artifact_out_a), "--out", str(duplicate_artifact_out_b)]) == 2
    duplicate_artifact_out_err = capsys.readouterr().err
    assert _field_labels(duplicate_artifact_out_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_artifact_out_err
    assert "--out may be provided once" in duplicate_artifact_out_err
    assert not duplicate_artifact_out_a.exists()
    assert not duplicate_artifact_out_b.exists()
    extra_artifact_export = tmp_path / "extra-artifact.txt"
    assert run(["--home", str(home), "artifacts", "export", artifact_id, "extra", "--out", str(extra_artifact_export)]) == 2
    extra_artifact_export_err = capsys.readouterr().err
    assert _field_labels(extra_artifact_export_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_artifact_export_err
    assert "artifacts export accepts exactly one artifact id" in extra_artifact_export_err
    assert not extra_artifact_export.exists()
    unsupported_artifact_export = tmp_path / "unsupported-artifact.txt"
    assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(unsupported_artifact_export), "--reason", "ignored"]) == 2
    unsupported_artifact_export_err = capsys.readouterr().err
    assert _field_labels(unsupported_artifact_export_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_artifact_export_err
    assert "unsupported option --reason" in unsupported_artifact_export_err
    assert not unsupported_artifact_export.exists()
    assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(artifact_out)]) == 0
    artifact_export_out = capsys.readouterr().out
    assert _field_labels(artifact_export_out) == _artifact_field_labels()
    assert f"out: {artifact_out}" in artifact_export_out
    assert artifact_out.read_text(encoding="utf-8") == "artifact bytes"
    assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(artifact_out)]) == 2
    artifact_export_err = capsys.readouterr().err
    assert _field_labels(artifact_export_err) == _error_field_labels()
    assert "error code: OUTPUT_EXISTS" in artifact_export_err
    assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(artifact_out), "--overwrite"]) == 0
    artifact_overwrite_out = capsys.readouterr().out
    assert _field_labels(artifact_overwrite_out) == _artifact_field_labels()
    assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(tmp_path / "missing-artifact-parent" / "artifact.txt")]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().err
    assert run(["--home", str(home), "artifacts", "archive", artifact_id, "extra"]) == 2
    extra_artifact_archive_err = capsys.readouterr().err
    assert _field_labels(extra_artifact_archive_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_artifact_archive_err
    assert "artifact archive accepts exactly one object id" in extra_artifact_archive_err
    assert _audit_count(home, "archive", "artifact", artifact_id) == 0
    assert run(["--home", str(home), "artifacts", "archive", artifact_id]) == 0
    archived_artifact_out = capsys.readouterr().out
    assert _field_labels(archived_artifact_out) == _archive_field_labels("artifact")
    assert "archive status: archived" in archived_artifact_out
    assert run(["--home", str(home), "artifacts", "list", "--run", run_id]) == 0
    archived_hidden_artifacts = capsys.readouterr().out
    assert _field_labels(archived_hidden_artifacts) == []
    assert artifact_id not in archived_hidden_artifacts
    assert run(["--home", str(home), "artifacts", "list", "--run", run_id, "--include-archived"]) == 0
    archived_included_artifacts = capsys.readouterr().out
    assert _field_labels(archived_included_artifacts) == _artifact_field_labels()
    assert f"artifact id: {artifact_id}" in archived_included_artifacts
    assert "archive status: archived" in archived_included_artifacts
    assert run(["--home", str(home), "artifacts", "show", artifact_id]) == 0
    archived_artifact_show = capsys.readouterr().out
    assert _field_labels(archived_artifact_show) == _artifact_field_labels()
    assert "archive status: archived" in archived_artifact_show
    archived_artifact_export = tmp_path / "archived-artifact.txt"
    assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(archived_artifact_export)]) == 2
    archived_artifact_export_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in archived_artifact_export_err
    assert "exporting archived artifacts requires --include-archived" in archived_artifact_export_err
    assert run(["--home", str(home), "artifacts", "export", artifact_id, "--out", str(archived_artifact_export), "--include-archived"]) == 0
    archived_artifact_export_out = capsys.readouterr().out
    assert _field_labels(archived_artifact_export_out) == _artifact_field_labels()
    assert archived_artifact_export.read_text(encoding="utf-8") == "artifact bytes"
    assert run(["--home", str(home), "artifacts", "unarchive", artifact_id]) == 0
    unarchived_artifact_out = capsys.readouterr().out
    assert _field_labels(unarchived_artifact_out) == _unarchive_field_labels("artifact")
    assert "archive status: active" in unarchived_artifact_out


def test_observe_list_pagination_contracts(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
print("stdout marker")
with open(os.path.join(os.environ["ALAB_RUN_DIR"], "artifact-a.txt"), "w", encoding="utf-8") as fh:
    fh.write("a")
with open(os.path.join(os.environ["ALAB_RUN_DIR"], "artifact-b.txt"), "w", encoding="utf-8") as fh:
    fh.write("b")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Observe Pagination Project"
task = "Page observe lists"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:artifact-a.txt", "run:artifact-b.txt", "workspace:main.py"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_id = _field(capsys.readouterr().out, "project id")
    worktree = tmp_path / "exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "paged", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")

    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "first"]) == 0
    first_run_out = capsys.readouterr().out
    first_run_id = _field(first_run_out, "run id")
    (worktree / "main.py").write_text("import sys\nprint('failed stdout')\nprint('failed stderr', file=sys.stderr)\nsys.exit(7)\n", encoding="utf-8")
    assert run(["--home", str(home), "run", "--message", "failed"]) == 1
    failed_run_out = capsys.readouterr().out
    failed_run_id = _field(failed_run_out, "run id")
    assert "run status: failed" in failed_run_out

    def field_values(output: str, name: str) -> list[str]:
        return re.findall(rf"^{re.escape(name)}: (.+)$", output, re.MULTILINE)

    pinned_times = {
        "first_started": "2026-01-01T00:00:00Z",
        "first_ended": "2026-01-01T00:00:10Z",
        "failed_started": "2026-01-01T00:01:00Z",
        "failed_ended": "2026-01-01T00:01:10Z",
        "artifact_a": "2026-01-01T00:00:20Z",
        "artifact_b": "2026-01-01T00:00:30Z",
        "artifact_workspace": "2026-01-01T00:00:40Z",
        "validation_artifact": "2026-01-01T00:00:05Z",
        "stderr_log": "2026-01-01T00:00:50Z",
        "stdout_log": "2026-01-01T00:00:55Z",
        "validation_log": "2026-01-01T00:00:04Z",
    }
    with sqlite3.connect(home / "alab.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("UPDATE runs SET started_at = ?, ended_at = ? WHERE run_id = ?", (pinned_times["first_started"], pinned_times["first_ended"], first_run_id))
        conn.execute("UPDATE runs SET started_at = ?, ended_at = ? WHERE run_id = ?", (pinned_times["failed_started"], pinned_times["failed_ended"], failed_run_id))
        conn.execute("UPDATE runs SET reward_value = NULL WHERE run_id = ?", (failed_run_id,))
        for relative_path, created_at in [
            ("artifact-a.txt", pinned_times["artifact_a"]),
            ("artifact-b.txt", pinned_times["artifact_b"]),
            ("main.py", pinned_times["artifact_workspace"]),
        ]:
            conn.execute(
                "UPDATE artifacts SET created_at = ? WHERE run_id = ? AND relative_path = ?",
                (created_at, first_run_id, relative_path),
            )
        conn.execute(
            "UPDATE artifacts SET created_at = ? WHERE validation_id IS NOT NULL AND relative_path = 'main.py'",
            (pinned_times["validation_artifact"],),
        )
        conn.execute("UPDATE log_streams SET created_at = ? WHERE run_id = ? AND stream = 'stderr'", (pinned_times["stderr_log"], first_run_id))
        conn.execute("UPDATE log_streams SET created_at = ? WHERE run_id = ? AND stream = 'stdout'", (pinned_times["stdout_log"], first_run_id))
        conn.execute(
            "UPDATE log_streams SET created_at = ? WHERE validation_id IS NOT NULL AND stream = 'stdout'",
            (pinned_times["validation_log"],),
        )
        conn.commit()
        first_run = dict(conn.execute("SELECT * FROM runs WHERE run_id = ?", (first_run_id,)).fetchone())
        failed_run = dict(conn.execute("SELECT * FROM runs WHERE run_id = ?", (failed_run_id,)).fetchone())
        failed_record = json.loads(failed_run["record_json"])
        failed_record["failure"] = "process exited with code 7 and literal 100Xneedle"
        failed_record_json = services.canonical_json(failed_record)
        conn.execute("UPDATE runs SET record_json = ? WHERE run_id = ?", (failed_record_json, failed_run_id))
        failed_run["record_json"] = failed_record_json
        conn.commit()
        validation_id = conn.execute("SELECT validation_id FROM project_validations WHERE project_id = ? ORDER BY started_at DESC LIMIT 1", (project_id,)).fetchone()[0]
        artifact_a = dict(
            conn.execute(
                "SELECT * FROM artifacts WHERE run_id = ? AND relative_path = 'artifact-a.txt'",
                (first_run_id,),
            ).fetchone()
        )
        artifact_b = dict(
            conn.execute(
                "SELECT * FROM artifacts WHERE run_id = ? AND relative_path = 'artifact-b.txt'",
                (first_run_id,),
            ).fetchone()
        )
        workspace_artifact = dict(
            conn.execute(
                "SELECT * FROM artifacts WHERE run_id = ? AND root = 'workspace' AND relative_path = 'main.py'",
                (first_run_id,),
            ).fetchone()
        )
        validation_artifact = dict(
            conn.execute(
                "SELECT * FROM artifacts WHERE validation_id = ? AND root = 'workspace' AND relative_path = 'main.py'",
                (validation_id,),
            ).fetchone()
        )
        stdout_log = dict(conn.execute("SELECT * FROM log_streams WHERE run_id = ? AND stream = 'stdout'", (first_run_id,)).fetchone())
        stderr_log = dict(conn.execute("SELECT * FROM log_streams WHERE run_id = ? AND stream = 'stderr'", (first_run_id,)).fetchone())
        validation_log = dict(conn.execute("SELECT * FROM log_streams WHERE validation_id = ? AND stream = 'stdout'", (validation_id,)).fetchone())

    assert first_run["reward_value"] is not None
    assert failed_run["reward_value"] is None

    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--sort", "exit-code:asc", "--limit", "1", "--offset", "1"]) == 0
    paged_runs = capsys.readouterr().out
    assert _field(paged_runs, "run id") == failed_run_id
    assert "exit code: 7" in paged_runs
    assert first_run_id not in paged_runs
    assert run(["--home", str(home), "runs", "list", "--limit", "not-an-int"]) == 2
    runs_limit_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in runs_limit_err
    assert "--limit and --offset must be integers" in runs_limit_err

    assert run(["--home", str(home), "runs", "list", "--status", "failed", "--exit-code", "7", "--failure-reason-query", "code 7"]) == 0
    failed_filtered_runs = capsys.readouterr().out
    assert field_values(failed_filtered_runs, "run id") == [failed_run_id]
    assert "run status: failed" in failed_filtered_runs
    assert run(["--home", str(home), "runs", "list", "--status", "failed", "--failure-reason-query", "100_needle"]) == 0
    assert field_values(capsys.readouterr().out, "run id") == []
    assert run(["--home", str(home), "runs", "list", "--config-version", str(first_run["config_version"]), "--commit", first_run["commit_sha"][:8], "--runner-type", "local", "--sort", "started:asc"]) == 0
    run_commit_filtered = capsys.readouterr().out
    assert field_values(run_commit_filtered, "run id") == [first_run_id]
    assert run(
        [
            "--home",
            str(home),
            "runs",
            "list",
            "--reward-min",
            str(first_run["reward_value"]),
            "--reward-max",
            str(first_run["reward_value"]),
            "--started-after",
            pinned_times["first_started"],
            "--started-before",
            pinned_times["first_started"],
            "--ended-after",
            pinned_times["first_ended"],
            "--ended-before",
            pinned_times["first_ended"],
            "--sort",
            "ended:desc",
        ]
    ) == 0
    run_time_filtered = capsys.readouterr().out
    assert field_values(run_time_filtered, "run id") == [first_run_id]
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--sort", "reward:asc"]) == 0
    reward_sorted_runs = capsys.readouterr().out
    assert field_values(reward_sorted_runs, "run id") == [first_run_id, failed_run_id]
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--sort", "status:asc"]) == 0
    status_sorted_runs = capsys.readouterr().out
    assert field_values(status_sorted_runs, "run id") == [failed_run_id, first_run_id]
    assert run(["--home", str(home), "runs", "list", "--exp", exp_id, "--sort", "config-version:desc"]) == 0
    assert set(field_values(capsys.readouterr().out, "run id")) == {first_run_id, failed_run_id}

    assert run(["--home", str(home), "artifacts", "list", "--run", first_run_id, "--sort", "path:asc", "--limit", "1", "--offset", "1"]) == 0
    paged_artifacts = capsys.readouterr().out
    assert _field_labels(paged_artifacts) == _artifact_field_labels()
    assert "path: artifact-b.txt" in paged_artifacts
    assert "artifact-a.txt" not in paged_artifacts

    assert run(["--home", str(home), "artifacts", "list", "--exp", exp_id, "--root", "workspace", "--status", "captured", "--path-query", "main", "--sort", "created:desc"]) == 0
    workspace_artifacts = capsys.readouterr().out
    assert workspace_artifact["artifact_id"] in field_values(workspace_artifacts, "artifact id")
    assert "root: workspace" in workspace_artifacts
    assert "path: main.py" in workspace_artifacts
    assert run(["--home", str(home), "--key", root_key, "artifacts", "list", "--project", project_id, "--validation", validation_id, "--root", "workspace"]) == 0
    validation_artifacts = capsys.readouterr().out
    assert field_values(validation_artifacts, "artifact id") == [validation_artifact["artifact_id"]]
    assert f"validation id: {validation_id}" in validation_artifacts
    assert run(["--home", str(home), "artifacts", "list", "--content-hash", artifact_b["content_hash"]]) == 0
    content_hash_artifacts = capsys.readouterr().out
    assert field_values(content_hash_artifacts, "artifact id") == [artifact_b["artifact_id"]]
    assert run(
        [
            "--home",
            str(home),
            "artifacts",
            "list",
            "--run",
            first_run_id,
            "--size-min",
            str(artifact_a["size_bytes"]),
            "--size-max",
            str(artifact_b["size_bytes"]),
            "--created-after",
            pinned_times["artifact_b"],
            "--created-before",
            pinned_times["artifact_b"],
            "--sort",
            "size:desc",
        ]
    ) == 0
    artifact_size_filtered = capsys.readouterr().out
    assert field_values(artifact_size_filtered, "artifact id") == [artifact_b["artifact_id"]]
    assert run(["--home", str(home), "artifacts", "list", "--run", first_run_id, "--sort", "status:asc"]) == 0
    assert set(field_values(capsys.readouterr().out, "artifact id")) == {artifact_a["artifact_id"], artifact_b["artifact_id"], workspace_artifact["artifact_id"]}
    assert run(["--home", str(home), "artifacts", "list", "--run", first_run_id, "--sort", "content-hash:asc"]) == 0
    assert set(field_values(capsys.readouterr().out, "artifact id")) == {artifact_a["artifact_id"], artifact_b["artifact_id"], workspace_artifact["artifact_id"]}

    assert run(["--home", str(home), "logs", "list", "--run", first_run_id, "--sort", "stream:asc", "--limit", "1", "--offset", "1"]) == 0
    paged_logs = capsys.readouterr().out
    assert _field_labels(paged_logs) == _log_field_labels()
    assert "stream: stdout" in paged_logs
    assert "stream: stderr" not in paged_logs

    assert run(["--home", str(home), "logs", "list", "--exp", exp_id, "--stream", "stdout", "--truncated", "false", "--sort", "created:desc"]) == 0
    stdout_logs = capsys.readouterr().out
    assert stdout_log["log_id"] in field_values(stdout_logs, "log id")
    assert "stream: stdout" in stdout_logs
    assert "truncated: false" in stdout_logs
    assert run(["--home", str(home), "--key", root_key, "logs", "list", "--project", project_id, "--validation", validation_id, "--stream", "stdout"]) == 0
    validation_logs = capsys.readouterr().out
    assert field_values(validation_logs, "log id") == [validation_log["log_id"]]
    assert f"validation id: {validation_id}" in validation_logs
    assert run(
        [
            "--home",
            str(home),
            "logs",
            "list",
            "--run",
            first_run_id,
            "--created-after",
            pinned_times["stdout_log"],
            "--created-before",
            pinned_times["stdout_log"],
            "--sort",
            "stored-bytes:desc",
        ]
    ) == 0
    log_time_filtered = capsys.readouterr().out
    assert field_values(log_time_filtered, "log id") == [stdout_log["log_id"]]
    assert run(["--home", str(home), "logs", "list", "--run", first_run_id, "--sort", "size:asc"]) == 0
    assert set(field_values(capsys.readouterr().out, "log id")) == {stdout_log["log_id"], stderr_log["log_id"]}
    assert run(["--home", str(home), "logs", "list", "--run", first_run_id, "--sort", "hidden:asc"]) == 0
    assert set(field_values(capsys.readouterr().out, "log id")) == {stdout_log["log_id"], stderr_log["log_id"]}
    assert run(["--home", str(home), "logs", "list", "--run", first_run_id, "--sort", "truncated:asc"]) == 0
    assert set(field_values(capsys.readouterr().out, "log id")) == {stdout_log["log_id"], stderr_log["log_id"]}

    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body", "experiment note", "--author", "Ada"]) == 0
    exp_annotation_id = _field(capsys.readouterr().out, "annotation id")
    assert run(["--home", str(home), "annotate", "add", "--target", "path:main.py", "--body", "path note", "--author", "Ben"]) == 0
    path_annotation_id = _field(capsys.readouterr().out, "annotation id")
    assert run(["--home", str(home), "annotations", "list", "--sort", "target-type:asc", "--limit", "1", "--offset", "1"]) == 0
    paged_annotations = capsys.readouterr().out
    assert _field_labels(paged_annotations) == _annotation_field_labels()
    assert _field(paged_annotations, "annotation id") == path_annotation_id
    assert "target type: path" in paged_annotations
    assert "body:\n  path note" in paged_annotations
    assert exp_annotation_id not in paged_annotations

    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body", "private note", "--author", "Cy", "--private"]) == 0
    private_annotation_id = _field(capsys.readouterr().out, "annotation id")
    assert run(["--home", str(home), "--key", root_key, "annotate", "add", "--project", project_id, "--target", f"exp:{exp_id}", "--body", "admin note", "--author", "Root"]) == 0
    admin_annotation_id = _field(capsys.readouterr().out, "annotation id")
    annotation_times = {
        exp_annotation_id: "2026-01-01T00:02:00Z",
        path_annotation_id: "2026-01-01T00:03:00Z",
        private_annotation_id: "2026-01-01T00:04:00Z",
        admin_annotation_id: "2026-01-01T00:05:00Z",
    }
    with sqlite3.connect(home / "alab.db") as conn:
        conn.row_factory = sqlite3.Row
        for annotation_id, created_at in annotation_times.items():
            conn.execute("UPDATE annotations SET created_at = ?, updated_at = ? WHERE annotation_id = ?", (created_at, created_at, annotation_id))
            conn.execute("UPDATE annotation_revisions SET created_at = ? WHERE annotation_id = ? AND revision = 1", (created_at, annotation_id))
        conn.commit()
        exp_annotation = dict(conn.execute("SELECT * FROM annotations WHERE annotation_id = ?", (exp_annotation_id,)).fetchone())
        admin_annotation = dict(conn.execute("SELECT * FROM annotations WHERE annotation_id = ?", (admin_annotation_id,)).fetchone())

    assert exp_annotation["created_by_id"] == exp_id
    assert admin_annotation["created_by_id"].startswith("cred-")

    assert run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-id", exp_id, "--author", "Ada", "--query", "EXPERIMENT"]) == 0
    experiment_annotations = capsys.readouterr().out
    assert field_values(experiment_annotations, "annotation id") == [exp_annotation_id]
    assert "author: Ada" in experiment_annotations
    assert run(["--home", str(home), "annotations", "list", "--target", exp_id, "--created-by", exp_id, "--sort", "target-id:asc"]) == 0
    created_by_annotations = capsys.readouterr().out
    assert exp_annotation_id in field_values(created_by_annotations, "annotation id")
    assert private_annotation_id in field_values(created_by_annotations, "annotation id")
    assert admin_annotation_id not in created_by_annotations
    assert run(["--home", str(home), "--key", root_key, "annotations", "list", "--project", project_id, "--created-by", admin_annotation["created_by_id"], "--sort", "created-by:asc"]) == 0
    admin_created_by_annotations = capsys.readouterr().out
    assert field_values(admin_created_by_annotations, "annotation id") == [admin_annotation_id]
    assert run(["--home", str(home), "annotations", "list", "--private", "--author", "Cy"]) == 0
    private_annotations = capsys.readouterr().out
    assert field_values(private_annotations, "annotation id") == [private_annotation_id]
    assert "visibility: private" in private_annotations
    assert run(
        [
            "--home",
            str(home),
            "annotations",
            "list",
            "--created-after",
            annotation_times[exp_annotation_id],
            "--created-before",
            annotation_times[exp_annotation_id],
            "--updated-after",
            annotation_times[exp_annotation_id],
            "--updated-before",
            annotation_times[exp_annotation_id],
            "--sort",
            "created:desc",
        ]
    ) == 0
    annotation_time_filtered = capsys.readouterr().out
    assert field_values(annotation_time_filtered, "annotation id") == [exp_annotation_id]
    assert run(["--home", str(home), "annotations", "list", "--sort", "updated:asc"]) == 0
    assert field_values(capsys.readouterr().out, "annotation id")[:3] == [exp_annotation_id, path_annotation_id, private_annotation_id]
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body", "wildcard body 100Xneedle", "--author", "Wild"]) == 0
    wildcard_annotation_id = _field(capsys.readouterr().out, "annotation id")
    assert run(["--home", str(home), "annotations", "list", "--query", "100_needle"]) == 0
    wildcard_query_annotations = capsys.readouterr().out
    assert field_values(wildcard_query_annotations, "annotation id") == []
    assert wildcard_annotation_id not in wildcard_query_annotations

    assert run(["--home", str(home), "runs", "archive", failed_run_id]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "runs", "list", "--status", "failed"]) == 0
    assert field_values(capsys.readouterr().out, "run id") == []
    assert run(["--home", str(home), "runs", "list", "--include-archived", "--status", "failed"]) == 0
    assert field_values(capsys.readouterr().out, "run id") == [failed_run_id]
    assert run(["--home", str(home), "artifacts", "archive", artifact_b["artifact_id"]]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "artifacts", "list", "--run", first_run_id, "--path-query", "artifact-b"]) == 0
    assert field_values(capsys.readouterr().out, "artifact id") == []
    assert run(["--home", str(home), "artifacts", "list", "--include-archived", "--run", first_run_id, "--path-query", "artifact-b"]) == 0
    assert field_values(capsys.readouterr().out, "artifact id") == [artifact_b["artifact_id"]]
    assert run(["--home", str(home), "logs", "archive", stderr_log["log_id"]]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "logs", "list", "--run", first_run_id, "--stream", "stderr"]) == 0
    assert field_values(capsys.readouterr().out, "log id") == []
    assert run(["--home", str(home), "logs", "list", "--include-archived", "--run", first_run_id, "--stream", "stderr"]) == 0
    assert field_values(capsys.readouterr().out, "log id") == [stderr_log["log_id"]]
    assert run(["--home", str(home), "annotate", "archive", path_annotation_id]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "annotations", "list", "--target-type", "path"]) == 0
    assert field_values(capsys.readouterr().out, "annotation id") == []
    assert run(["--home", str(home), "annotations", "list", "--include-archived", "--target-type", "path", "--sort", "status:asc"]) == 0
    archived_annotations = capsys.readouterr().out
    assert field_values(archived_annotations, "annotation id") == [path_annotation_id]
    assert "status: archived" in archived_annotations


def test_public_exp_create_inline_source_import(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    base_source = tmp_path / "base-source"
    duplicate_base_source = tmp_path / "duplicate-base-source"
    inline_source = tmp_path / "inline-source"
    subdir_source = tmp_path / "subdir-source"
    conflicting_name_source = tmp_path / "Inline Project"
    base_source.mkdir()
    duplicate_base_source.mkdir()
    inline_source.mkdir()
    subdir_source.mkdir()
    (subdir_source / "app").mkdir()
    conflicting_name_source.mkdir()
    (base_source / "main.py").write_text('print("base")\n', encoding="utf-8")
    (duplicate_base_source / "main.py").write_text('print("base")\n', encoding="utf-8")
    (inline_source / "main.py").write_text('print("inline")\n', encoding="utf-8")
    (subdir_source / "app" / "main.py").write_text('print("subdir")\n', encoding="utf-8")
    (subdir_source / "outside.py").write_text('print("outside")\n', encoding="utf-8")
    (conflicting_name_source / "main.py").write_text('print("conflict")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Inline Project"
task = "Accept inline public sources"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(base_source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    base_source_id = _field(project_out, "source id")
    base_source_ref = _field(project_out, "source ref")
    base_refs = _source_refs(home, project_id)

    deduped_worktree = tmp_path / "deduped-inline-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "deduped inline", "--source-path", str(duplicate_base_source), "--path", str(deduped_worktree)]) == 0
    deduped_out = capsys.readouterr().out
    assert _field_labels(deduped_out) == _exp_create_field_labels()
    assert _field(deduped_out, "source id") == base_source_id
    assert "warning:" not in deduped_out
    assert (deduped_worktree / "main.py").read_text(encoding="utf-8") == 'print("base")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        source_count_after_dedupe = conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
        deduped_metadata_json = conn.execute(
            "SELECT metadata_json FROM experiments WHERE project_id = ? AND json_extract(metadata_json,'$.display.safe_summary') = 'deduped inline'",
            (project_id,),
        ).fetchone()[0]
        base_origin_metadata = conn.execute("SELECT origin_metadata_json FROM sources WHERE source_id = ?", (base_source_id,)).fetchone()[0]
    assert source_count_after_dedupe == 1
    assert _source_refs(home, project_id) == base_refs
    assert json.loads(deduped_metadata_json)["creation_origin"] == {
        "kind": "inline_source",
        "source_id": base_source_id,
        "source_ref": base_source_ref,
    }
    base_origins = json.loads(base_origin_metadata)["origins"]
    assert len(base_origins) == 2
    assert json.loads(base_origin_metadata)["primary_origin"] == base_origins[0]
    assert base_origins[0]["origin_id"].startswith("origin-")
    assert base_origins[1]["origin_id"].startswith("origin-")
    assert base_origins[1]["warnings"] == []

    worktree = tmp_path / "inline-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "inline", "--source-path", str(inline_source), "--path", str(worktree)]) == 0
    exp_out = capsys.readouterr().out
    assert _field_labels(exp_out) == _exp_create_field_labels()
    inline_source_id = _field(exp_out, "source id")

    assert inline_source_id != base_source_id
    assert (worktree / "main.py").read_text(encoding="utf-8") == 'print("inline")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        source_count = conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
        metadata_json = conn.execute("SELECT metadata_json FROM experiments WHERE project_id = ?", (project_id,)).fetchone()[0]
    assert source_count == 2
    assert json.loads(metadata_json)["creation_origin"]["kind"] == "inline_source"

    conflicting_worktree = tmp_path / "conflicting-source-name-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "conflicting source name",
                "--source-path",
                str(conflicting_name_source),
                "--path",
                str(conflicting_worktree),
            ]
        )
        == 0
    )
    conflict_exp_out = capsys.readouterr().out
    assert _field_labels(conflict_exp_out) == _exp_create_field_labels()
    conflict_source_id = _field(conflict_exp_out, "source id")
    conflict_suffix = conflict_source_id.rsplit("-", 1)[-1][:8]
    assert (conflicting_worktree / "main.py").read_text(encoding="utf-8") == 'print("conflict")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        conflict_source_row = conn.execute(
            "SELECT name, name_slug FROM sources WHERE source_id = ?",
            (conflict_source_id,),
        ).fetchone()
        source_count_after_conflict = conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
    conflict_source_name = f"Inline Project-{conflict_suffix}"
    assert conflict_source_row == (conflict_source_name, slugify(conflict_source_name, "source"))
    assert source_count_after_conflict == 3

    empty_worktree = tmp_path / "empty-inline-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "empty inline", "--source-empty", "--path", str(empty_worktree)]) == 0
    empty_out = capsys.readouterr().out
    assert _field_labels(empty_out) == _exp_create_field_labels()
    empty_source_id = _field(empty_out, "source id")
    assert "warning:" not in empty_out
    assert not (empty_worktree / "main.py").exists()
    with sqlite3.connect(home / "alab.db") as conn:
        empty_source_row = conn.execute(
            "SELECT name, origin_metadata_json FROM sources WHERE source_id = ?",
            (empty_source_id,),
        ).fetchone()
        empty_metadata_json = conn.execute(
            "SELECT metadata_json FROM experiments WHERE project_id = ? AND json_extract(metadata_json,'$.display.safe_summary') = 'empty inline'",
            (project_id,),
        ).fetchone()[0]
    empty_origin = json.loads(empty_source_row[1])["primary_origin"]
    assert empty_source_row[0] == "empty"
    assert empty_origin["origin_type"] == "empty"
    assert empty_origin["warnings"] == []
    assert _source_tree_files(home, project_id, f"alab/source/{empty_source_id}") == set()
    assert json.loads(empty_metadata_json)["creation_origin"] == {
        "kind": "inline_source",
        "source_id": empty_source_id,
        "source_ref": f"alab/source/{empty_source_id}",
    }

    subdir_worktree = tmp_path / "subdir-inline-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "subdir inline",
                "--source-path",
                str(subdir_source),
                "--source-subdir",
                "app",
                "--path",
                str(subdir_worktree),
            ]
        )
        == 0
    )
    subdir_out = capsys.readouterr().out
    assert _field_labels(subdir_out) == _exp_create_field_labels()
    subdir_source_id = _field(subdir_out, "source id")
    assert (subdir_worktree / "main.py").read_text(encoding="utf-8") == 'print("subdir")\n'
    assert not (subdir_worktree / "app").exists()
    assert not (subdir_worktree / "outside.py").exists()
    with sqlite3.connect(home / "alab.db") as conn:
        subdir_source_metadata = conn.execute(
            "SELECT origin_metadata_json FROM sources WHERE source_id = ?",
            (subdir_source_id,),
        ).fetchone()[0]
    subdir_origin = json.loads(subdir_source_metadata)["primary_origin"]
    assert subdir_origin["origin_type"] == "local"
    assert subdir_origin["safe_summary"] == "local"
    assert subdir_origin["exact"] == {"source_subdir": "app"}
    assert "source_path" not in json.dumps(subdir_origin, sort_keys=True)
    assert _source_tree_files(home, project_id, f"alab/source/{subdir_source_id}") == {"main.py"}

    remote_source = tmp_path / "remote-source"
    remote_head_source = tmp_path / "remote-head-source"
    remote_no_helper_source = tmp_path / "remote-no-helper-source"
    remote_source.mkdir()
    remote_head_source.mkdir()
    remote_no_helper_source.mkdir()
    _git(["init"], remote_source)
    _git(["config", "user.name", "ALab Test"], remote_source)
    _git(["config", "user.email", "alab@example.test"], remote_source)
    _git(["config", "commit.gpgsign", "false"], remote_source)
    (remote_source / "app").mkdir()
    (remote_source / "main.py").write_text('print("remote")\n', encoding="utf-8")
    (remote_source / "app" / "main.py").write_text('print("remote subdir")\n', encoding="utf-8")
    _git(["add", "main.py", "app/main.py"], remote_source)
    _git(["commit", "-m", "remote"], remote_source)
    _git(["branch", "-M", "main"], remote_source)
    remote_commit = _git(["rev-parse", "HEAD"], remote_source)

    _git(["init"], remote_head_source)
    _git(["config", "user.name", "ALab Test"], remote_head_source)
    _git(["config", "user.email", "alab@example.test"], remote_head_source)
    _git(["config", "commit.gpgsign", "false"], remote_head_source)
    (remote_head_source / "main.py").write_text('print("remote head")\n', encoding="utf-8")
    _git(["add", "main.py"], remote_head_source)
    _git(["commit", "-m", "remote head"], remote_head_source)
    _git(["branch", "-M", "main"], remote_head_source)
    remote_head_commit = _git(["rev-parse", "HEAD"], remote_head_source)

    _git(["init"], remote_no_helper_source)
    _git(["config", "user.name", "ALab Test"], remote_no_helper_source)
    _git(["config", "user.email", "alab@example.test"], remote_no_helper_source)
    _git(["config", "commit.gpgsign", "false"], remote_no_helper_source)
    (remote_no_helper_source / "main.py").write_text('print("remote no helper")\n', encoding="utf-8")
    _git(["add", "main.py"], remote_no_helper_source)
    _git(["commit", "-m", "remote no helper"], remote_no_helper_source)
    _git(["branch", "-M", "main"], remote_no_helper_source)
    remote_no_helper_commit = _git(["rev-parse", "HEAD"], remote_no_helper_source)

    no_helper_home = tmp_path / "git-no-helper-home"
    no_helper_home.mkdir()
    monkeypatch.setenv("HOME", str(no_helper_home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(no_helper_home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    git_no_helper_worktree = tmp_path / "git-no-helper-inline-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "git-no-helper-inline",
                "--source-git",
                str(remote_no_helper_source),
                "--git-ref",
                "main",
                "--path",
                str(git_no_helper_worktree),
            ]
        )
        == 0
    )
    git_no_helper_out = capsys.readouterr().out
    assert _field_labels(git_no_helper_out) == _exp_create_field_labels()
    git_no_helper_source_id = _field(git_no_helper_out, "source id")
    assert "warning: PUBLIC_GIT_CREDENTIAL_HELPER_USED" not in git_no_helper_out
    assert (git_no_helper_worktree / "main.py").read_text(encoding="utf-8") == 'print("remote no helper")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        git_no_helper_meta = conn.execute("SELECT origin_metadata_json FROM sources WHERE source_id = ?", (git_no_helper_source_id,)).fetchone()[0]
    git_no_helper_origin = json.loads(git_no_helper_meta)["primary_origin"]
    assert git_no_helper_origin["origin_type"] == "git"
    assert git_no_helper_origin["exact"] == {"git_ref": "main", "resolved_commit": remote_no_helper_commit, "source_subdir": None}
    assert git_no_helper_origin["warnings"] == []

    git_home = tmp_path / "git-home"
    git_home.mkdir()
    monkeypatch.setenv("HOME", str(git_home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(git_home / ".gitconfig"))
    subprocess.run(["git", "config", "--global", "credential.helper", "store"], check=True)

    git_worktree = tmp_path / "git-inline-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "git-inline", "--source-git", str(remote_source), "--git-ref", "main", "--path", str(git_worktree)]) == 0
    git_exp_out = capsys.readouterr().out
    assert _field_labels(git_exp_out) == _exp_create_field_labels(warning_count=1)
    git_source_id = _field(git_exp_out, "source id")
    assert "warning: PUBLIC_GIT_CREDENTIAL_HELPER_USED" in git_exp_out
    assert (git_worktree / "main.py").read_text(encoding="utf-8") == 'print("remote")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        git_source_meta = conn.execute("SELECT origin_metadata_json FROM sources WHERE source_id = ?", (git_source_id,)).fetchone()[0]
    primary_origin = json.loads(git_source_meta)["primary_origin"]
    assert primary_origin["exact"] == {"git_ref": "main", "resolved_commit": remote_commit, "source_subdir": None}
    assert "PUBLIC_GIT_CREDENTIAL_HELPER_USED" in primary_origin["warnings"]

    git_head_worktree = tmp_path / "git-head-inline-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "git-head-inline",
                "--source-git",
                str(remote_head_source),
                "--path",
                str(git_head_worktree),
            ]
        )
        == 0
    )
    git_head_exp_out = capsys.readouterr().out
    assert _field_labels(git_head_exp_out) == _exp_create_field_labels(warning_count=1)
    git_head_source_id = _field(git_head_exp_out, "source id")
    assert "warning: PUBLIC_GIT_CREDENTIAL_HELPER_USED" in git_head_exp_out
    assert (git_head_worktree / "main.py").read_text(encoding="utf-8") == 'print("remote head")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        git_head_meta = conn.execute("SELECT origin_metadata_json FROM sources WHERE source_id = ?", (git_head_source_id,)).fetchone()[0]
    git_head_origin = json.loads(git_head_meta)["primary_origin"]
    assert git_head_origin["origin_type"] == "git"
    assert git_head_origin["safe_summary"] == "git"
    assert git_head_origin["exact"] == {"git_ref": "HEAD", "resolved_commit": remote_head_commit, "source_subdir": None}
    assert "PUBLIC_GIT_CREDENTIAL_HELPER_USED" in git_head_origin["warnings"]
    assert "source_git" not in json.dumps(git_head_origin, sort_keys=True)
    assert str(remote_head_source) not in json.dumps(git_head_origin, sort_keys=True)
    assert _source_tree_files(home, project_id, f"alab/source/{git_head_source_id}") == {"main.py"}

    git_subdir_worktree = tmp_path / "git-subdir-inline-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "git-subdir-inline",
                "--source-git",
                str(remote_source),
                "--git-ref",
                "main",
                "--source-subdir",
                "app",
                "--path",
                str(git_subdir_worktree),
            ]
        )
        == 0
    )
    git_subdir_out = capsys.readouterr().out
    assert _field_labels(git_subdir_out) == _exp_create_field_labels(warning_count=1)
    git_subdir_source_id = _field(git_subdir_out, "source id")
    assert "warning: PUBLIC_GIT_CREDENTIAL_HELPER_USED" in git_subdir_out
    assert (git_subdir_worktree / "main.py").read_text(encoding="utf-8") == 'print("remote subdir")\n'
    assert not (git_subdir_worktree / "app").exists()
    with sqlite3.connect(home / "alab.db") as conn:
        git_subdir_meta = conn.execute("SELECT origin_metadata_json FROM sources WHERE source_id = ?", (git_subdir_source_id,)).fetchone()[0]
    git_subdir_origin = json.loads(git_subdir_meta)["primary_origin"]
    assert git_subdir_origin["origin_type"] == "git"
    assert git_subdir_origin["safe_summary"] == "git"
    assert git_subdir_origin["exact"] == {"git_ref": "main", "resolved_commit": remote_commit, "source_subdir": "app"}
    assert "PUBLIC_GIT_CREDENTIAL_HELPER_USED" in git_subdir_origin["warnings"]
    assert "source_git" not in json.dumps(git_subdir_origin, sort_keys=True)
    assert str(remote_source) not in json.dumps(git_subdir_origin, sort_keys=True)
    assert _source_tree_files(home, project_id, f"alab/source/{git_subdir_source_id}") == {"main.py"}


def test_public_inline_source_import_enforces_project_limits(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    base_source = tmp_path / "base-source"
    large_source = tmp_path / "large-source"
    base_source.mkdir()
    large_source.mkdir()
    (base_source / "main.py").write_text('print("base")\n', encoding="utf-8")
    (large_source / "main.py").write_text('print("too large")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Limited Inline Project"
task = "Limit public inline sources"
allow_public_exp_create = true

[public_source_import]
enabled = true
max_files = 10
max_total_bytes = 10
max_file_bytes = 3

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(base_source)]) == 0
    project_id = _field(capsys.readouterr().out, "project id")
    before_refs = _source_refs(home, project_id)
    before_source_add_audits = _audit_type_count(home, "add", "source")

    missing_source = tmp_path / "missing-public-source"
    missing_policy_worktree = tmp_path / "missing-policy-exp"
    code = run(
        [
            "--home",
            str(home),
            "exp",
            "create",
            "--project",
            project_id,
            "--name",
            "missing-policy",
            "--source-path",
            str(missing_source),
            "--path",
            str(missing_policy_worktree),
            "--max-files",
            "11",
        ]
    )
    err = capsys.readouterr().err

    assert code == 2
    assert _field_labels(err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in err
    assert "public inline source import limits cannot exceed project policy" in err
    assert "source path does not exist" not in err
    with sqlite3.connect(home / "alab.db") as conn:
        source_count = conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
        exp_count = conn.execute("SELECT COUNT(*) FROM experiments WHERE project_id = ?", (project_id,)).fetchone()[0]
    assert source_count == 1
    assert exp_count == 0
    assert _source_refs(home, project_id) == before_refs
    assert _audit_type_count(home, "add", "source") == before_source_add_audits
    assert not missing_policy_worktree.exists()

    blocked_worktree = tmp_path / "blocked-exp"
    code = run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "blocked", "--source-path", str(large_source), "--path", str(blocked_worktree)])
    err = capsys.readouterr().err

    assert code == 2
    assert _field_labels(err) == _error_field_labels()
    assert "error code: SOURCE_LIMIT_EXCEEDED" in err
    with sqlite3.connect(home / "alab.db") as conn:
        source_count = conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
        exp_count = conn.execute("SELECT COUNT(*) FROM experiments WHERE project_id = ?", (project_id,)).fetchone()[0]
    assert source_count == 1
    assert exp_count == 0
    assert _source_refs(home, project_id) == before_refs
    assert _audit_type_count(home, "add", "source") == before_source_add_audits
    assert not blocked_worktree.exists()

    for index, limit_args in enumerate(
        [
            ["--max-files", "11"],
            ["--max-total-bytes", "11"],
            ["--max-file-bytes", "4"],
        ],
        start=1,
    ):
        raised_worktree = tmp_path / f"raised-exp-{index}"
        code = run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                f"raised-{index}",
                "--source-path",
                str(large_source),
                "--path",
                str(raised_worktree),
                *limit_args,
            ]
        )
        err = capsys.readouterr().err

        assert code == 2
        assert _field_labels(err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in err
        assert "public inline source import limits cannot exceed project policy" in err
        with sqlite3.connect(home / "alab.db") as conn:
            source_count = conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
            exp_count = conn.execute("SELECT COUNT(*) FROM experiments WHERE project_id = ?", (project_id,)).fetchone()[0]
        assert source_count == 1
        assert exp_count == 0
        assert _source_refs(home, project_id) == before_refs
        assert _audit_type_count(home, "add", "source") == before_source_add_audits
        assert not raised_worktree.exists()


def test_public_inline_source_import_disabled_requires_admin(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    base_source = tmp_path / "base-source"
    inline_source = tmp_path / "inline-source"
    base_source.mkdir()
    inline_source.mkdir()
    (base_source / "main.py").write_text('print("base")\n', encoding="utf-8")
    (inline_source / "main.py").write_text('print("inline")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Disabled Public Source Import Project"
task = "Separate public exp creation from public source import"
allow_public_exp_create = true

[public_source_import]
enabled = false

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(base_source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    base_source_id = _field(project_out, "source id")
    baseline_refs = _source_refs(home, project_id)
    baseline_source_add_audits = _audit_type_count(home, "add", "source")

    default_worktree = tmp_path / "default-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "default source", "--path", str(default_worktree)]) == 0
    default_out = capsys.readouterr().out
    assert _field_labels(default_out) == _exp_create_field_labels()
    assert _field(default_out, "source id") == base_source_id
    assert (default_worktree / "main.py").read_text(encoding="utf-8") == 'print("base")\n'

    blocked_worktree = tmp_path / "blocked-inline-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "blocked inline", "--source-path", str(inline_source), "--path", str(blocked_worktree)]) == 3
    blocked_err = capsys.readouterr().err
    assert _field_labels(blocked_err) == _error_field_labels()
    assert "error code: AUTH_REQUIRED" in blocked_err
    assert "credential is required" in blocked_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM experiments WHERE project_id = ?", (project_id,)).fetchone()[0] == 1
    assert _source_refs(home, project_id) == baseline_refs
    assert _audit_type_count(home, "add", "source") == baseline_source_add_audits
    assert not blocked_worktree.exists()

    admin_worktree = tmp_path / "admin-inline-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "admin inline",
                "--source-path",
                str(inline_source),
                "--path",
                str(admin_worktree),
            ]
        )
        == 0
    )
    admin_out = capsys.readouterr().out
    assert _field_labels(admin_out) == _exp_create_field_labels()
    admin_source_id = _field(admin_out, "source id")
    assert admin_source_id != base_source_id
    assert (admin_worktree / "main.py").read_text(encoding="utf-8") == 'print("inline")\n'
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM experiments WHERE project_id = ?", (project_id,)).fetchone()[0] == 2
    assert _source_refs(home, project_id) != baseline_refs
    assert _audit_count(home, "add", "source", admin_source_id) == 1


def test_standalone_source_import_limit_failure_is_atomic(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    base_source = tmp_path / "base-source"
    too_many_source = tmp_path / "too-many-source"
    too_large_file_source = tmp_path / "too-large-file-source"
    too_large_total_source = tmp_path / "too-large-total-source"
    base_source.mkdir()
    too_many_source.mkdir()
    too_large_file_source.mkdir()
    too_large_total_source.mkdir()
    (base_source / "main.py").write_text('print("base")\n', encoding="utf-8")
    (too_many_source / "main.py").write_text('print("candidate")\n', encoding="utf-8")
    (too_many_source / "extra.py").write_text('print("extra")\n', encoding="utf-8")
    (too_large_file_source / "large.txt").write_text("abcd\n", encoding="utf-8")
    (too_large_total_source / "first.txt").write_text("abc", encoding="utf-8")
    (too_large_total_source / "second.txt").write_text("def", encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Source Limit Atomic Project"
task = "Keep failed source imports atomic"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(base_source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    before_refs = _source_refs(home, project_id)
    before_source_add_audits = _audit_type_count(home, "add", "source")

    for source_path, source_name, limit_args, reason in [
        (too_many_source, "too-many", ["--max-files", "1"], "source import exceeds max files: 1"),
        (too_large_file_source, "too-large-file", ["--max-file-bytes", "3"], "source file exceeds max bytes: large.txt"),
        (too_large_total_source, "too-large-total", ["--max-file-bytes", "10", "--max-total-bytes", "5"], "source import exceeds max total bytes: 5"),
    ]:
        code = run(
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
                str(source_path),
                "--name",
                source_name,
                *limit_args,
            ]
        )
        err = capsys.readouterr().err

        assert code == 2
        assert _field_labels(err) == _error_field_labels()
        assert "error code: SOURCE_LIMIT_EXCEEDED" in err
        assert reason in err
        with sqlite3.connect(home / "alab.db") as conn:
            source_count = conn.execute("SELECT COUNT(*) FROM sources WHERE project_id = ?", (project_id,)).fetchone()[0]
            failed_name_count = conn.execute(
                "SELECT COUNT(*) FROM sources WHERE project_id = ? AND name = ?",
                (project_id, source_name),
            ).fetchone()[0]
        assert source_count == 1
        assert failed_name_count == 0
        assert _source_refs(home, project_id) == before_refs
        assert _audit_type_count(home, "add", "source") == before_source_add_audits


def test_source_selector_option_scope_errors_do_not_write(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    base_source = tmp_path / "base-source"
    candidate_source = tmp_path / "candidate-source"
    base_source.mkdir()
    candidate_source.mkdir()
    (base_source / "main.py").write_text('print("base")\n', encoding="utf-8")
    (candidate_source / "main.py").write_text('print("candidate")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Source Option Scope Project"
task = "Reject scoped source options"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(base_source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    base_source_id = _field(project_out, "source id")
    with sqlite3.connect(home / "alab.db") as conn:
        baseline_source_count = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        baseline_exp_count = conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    baseline_source_add_audits = _audit_type_count(home, "add", "source")
    baseline_exp_add_audits = _audit_type_count(home, "add", "experiment")

    with sqlite3.connect(home / "alab.db") as conn:
        before_extra_mode_init = {
            "projects": conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            "sources": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
            "configs": conn.execute("SELECT COUNT(*) FROM project_config_versions").fetchone()[0],
            "validations": conn.execute("SELECT COUNT(*) FROM project_validations").fetchone()[0],
            "admin_credentials": conn.execute("SELECT COUNT(*) FROM credentials WHERE credential_type = 'admin'").fetchone()[0],
            "project_add_audits": _audit_type_count(home, "add", "project"),
            "source_add_audits": _audit_type_count(home, "add", "source"),
        }
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                root_key,
                "project",
                "init",
                "local",
                "extra",
                "--config",
                str(config),
                "--source-path",
                str(candidate_source),
            ]
        )
        == 2
    )
    extra_mode_init_err = capsys.readouterr().err
    assert _field_labels(extra_mode_init_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_mode_init_err
    assert "project init requires mode local|git|empty|harbor|skydiscover" in extra_mode_init_err
    with sqlite3.connect(home / "alab.db") as conn:
        after_extra_mode_init = {
            "projects": conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            "sources": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
            "configs": conn.execute("SELECT COUNT(*) FROM project_config_versions").fetchone()[0],
            "validations": conn.execute("SELECT COUNT(*) FROM project_validations").fetchone()[0],
            "admin_credentials": conn.execute("SELECT COUNT(*) FROM credentials WHERE credential_type = 'admin'").fetchone()[0],
            "project_add_audits": _audit_type_count(home, "add", "project"),
            "source_add_audits": _audit_type_count(home, "add", "source"),
        }
    assert after_extra_mode_init == before_extra_mode_init
    assert (
        run(
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
                str(candidate_source),
                "--reason",
                "ignored",
            ]
        )
        == 2
    )
    unsupported_project_init_err = capsys.readouterr().err
    assert _field_labels(unsupported_project_init_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_project_init_err
    assert "unsupported option --reason" in unsupported_project_init_err
    with sqlite3.connect(home / "alab.db") as conn:
        after_unsupported_project_init = {
            "projects": conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            "sources": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
            "configs": conn.execute("SELECT COUNT(*) FROM project_config_versions").fetchone()[0],
            "validations": conn.execute("SELECT COUNT(*) FROM project_validations").fetchone()[0],
            "admin_credentials": conn.execute("SELECT COUNT(*) FROM credentials WHERE credential_type = 'admin'").fetchone()[0],
            "project_add_audits": _audit_type_count(home, "add", "project"),
            "source_add_audits": _audit_type_count(home, "add", "source"),
        }
    assert after_unsupported_project_init == before_extra_mode_init

    for unsupported_selector, value in [
        ("--source-ref", base_source_id),
        ("--from-exp", "exp-source-selector"),
        ("--from-commit", "latest"),
    ]:
        assert (
            run(
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
                    str(candidate_source),
                    unsupported_selector,
                    value,
                ]
            )
            == 2
        )
        unsupported_selector_err = capsys.readouterr().err
        assert _field_labels(unsupported_selector_err) == _error_field_labels()
        assert "error code: SOURCE_INVALID" in unsupported_selector_err
        assert f"{unsupported_selector} is not valid for source import" in unsupported_selector_err

    assert (
        run(
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
                str(candidate_source),
                "--reason",
                "ignored",
            ]
        )
        == 2
    )
    unsupported_source_import_err = capsys.readouterr().err
    assert _field_labels(unsupported_source_import_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_source_import_err
    assert "unsupported option --reason" in unsupported_source_import_err

    assert (
        run(
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
                str(candidate_source),
                "--source-path",
                str(base_source),
            ]
        )
        == 2
    )
    duplicate_source_import_err = capsys.readouterr().err
    assert _field_labels(duplicate_source_import_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_source_import_err
    assert "--source-path may be provided once" in duplicate_source_import_err

    assert (
        run(
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
                str(candidate_source),
                "--name",
                "candidate-a",
                "--name",
                "candidate-b",
            ]
        )
        == 2
    )
    duplicate_source_name_err = capsys.readouterr().err
    assert _field_labels(duplicate_source_name_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_source_name_err
    assert "--name may be provided once" in duplicate_source_name_err

    assert (
        run(
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
                str(candidate_source),
                "--max-files",
                "10",
                "--max-files",
                "20",
            ]
        )
        == 2
    )
    duplicate_source_limit_err = capsys.readouterr().err
    assert _field_labels(duplicate_source_limit_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_source_limit_err
    assert "--max-files may be provided once" in duplicate_source_limit_err

    assert (
        run(
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
                str(candidate_source),
                "--git-ref",
                "main",
            ]
        )
        == 2
    )
    source_git_ref_err = capsys.readouterr().err
    assert _field_labels(source_git_ref_err) == _error_field_labels()
    assert "error code: SOURCE_INVALID" in source_git_ref_err
    assert "--git-ref requires --source-git" in source_git_ref_err

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "source",
                "import",
                "--project",
                project_id,
                "--source-empty",
                "--source-subdir",
                "src",
            ]
        )
        == 2
    )
    source_empty_subdir_err = capsys.readouterr().err
    assert _field_labels(source_empty_subdir_err) == _error_field_labels()
    assert "error code: SOURCE_INVALID" in source_empty_subdir_err
    assert "--source-subdir conflicts with --source-empty" in source_empty_subdir_err

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "source",
                "import",
                "--project",
                project_id,
                "--source-empty",
                "--source-empty",
            ]
        )
        == 2
    )
    duplicate_source_empty_err = capsys.readouterr().err
    assert _field_labels(duplicate_source_empty_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_source_empty_err
    assert "--source-empty may be provided once" in duplicate_source_empty_err

    default_git_ref_path = tmp_path / "default-git-ref-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "default-git-ref",
                "--git-ref",
                "main",
                "--path",
                str(default_git_ref_path),
            ]
        )
        == 2
    )
    exp_git_ref_err = capsys.readouterr().err
    assert _field_labels(exp_git_ref_err) == _error_field_labels()
    assert "error code: SOURCE_INVALID" in exp_git_ref_err
    assert "--git-ref requires --source-git" in exp_git_ref_err
    assert not default_git_ref_path.exists()

    duplicate_source_ref_path = tmp_path / "duplicate-source-ref-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "duplicate-source-ref",
                "--source-ref",
                base_source_id,
                "--source-ref",
                base_source_id,
                "--path",
                str(duplicate_source_ref_path),
            ]
        )
        == 2
    )
    duplicate_source_ref_err = capsys.readouterr().err
    assert _field_labels(duplicate_source_ref_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_source_ref_err
    assert "--source-ref may be provided once" in duplicate_source_ref_err
    assert not duplicate_source_ref_path.exists()

    duplicate_exp_path_a = tmp_path / "duplicate-exp-path-a"
    duplicate_exp_path_b = tmp_path / "duplicate-exp-path-b"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "duplicate-exp-path",
                "--path",
                str(duplicate_exp_path_a),
                "--path",
                str(duplicate_exp_path_b),
            ]
        )
        == 2
    )
    duplicate_exp_path_err = capsys.readouterr().err
    assert _field_labels(duplicate_exp_path_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_exp_path_err
    assert "--path may be provided once" in duplicate_exp_path_err
    assert not duplicate_exp_path_a.exists()
    assert not duplicate_exp_path_b.exists()

    duplicate_visibility_path = tmp_path / "duplicate-visibility-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "duplicate-visibility",
                "--visibility-scope",
                "same_project",
                "--visibility-scope",
                "none",
                "--path",
                str(duplicate_visibility_path),
            ]
        )
        == 2
    )
    duplicate_visibility_err = capsys.readouterr().err
    assert _field_labels(duplicate_visibility_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_visibility_err
    assert "--visibility-scope may be provided once" in duplicate_visibility_err
    assert not duplicate_visibility_path.exists()

    unsupported_exp_create_path = tmp_path / "unsupported-exp-create"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "unsupported-option",
                "--path",
                str(unsupported_exp_create_path),
                "--reason",
                "ignored",
            ]
        )
        == 2
    )
    unsupported_exp_create_err = capsys.readouterr().err
    assert _field_labels(unsupported_exp_create_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_exp_create_err
    assert "unsupported option --reason" in unsupported_exp_create_err
    assert not unsupported_exp_create_path.exists()

    source_ref_subdir_path = tmp_path / "source-ref-subdir-exp"
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "source-ref-subdir",
                "--source-ref",
                base_source_id,
                "--source-subdir",
                "src",
                "--path",
                str(source_ref_subdir_path),
            ]
        )
        == 2
    )
    source_ref_subdir_err = capsys.readouterr().err
    assert _field_labels(source_ref_subdir_err) == _error_field_labels()
    assert "error code: SOURCE_INVALID" in source_ref_subdir_err
    assert "--source-subdir requires --source-path or --source-git" in source_ref_subdir_err
    assert not source_ref_subdir_path.exists()

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM sources WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == baseline_source_count
        assert conn.execute(
            "SELECT COUNT(*) FROM experiments WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == baseline_exp_count
    assert _audit_type_count(home, "add", "source") == baseline_source_add_audits
    assert _audit_type_count(home, "add", "experiment") == baseline_exp_add_audits


def test_source_import_dedupes_active_sources_and_ignores_archived(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    base_source = tmp_path / "base-source"
    first_source = tmp_path / "first-source"
    conflict_source = tmp_path / "conflict-source"
    second_source = tmp_path / "second-source"
    archived_source = tmp_path / "archived-source"
    for source_dir in (base_source, first_source, conflict_source, second_source, archived_source):
        source_dir.mkdir()
    (base_source / "main.py").write_text('print("base")\n', encoding="utf-8")
    for source_dir in (first_source, second_source, archived_source):
        (source_dir / "main.py").write_text('print("same tree")\n', encoding="utf-8")
    (conflict_source / "main.py").write_text('print("different tree")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Source Dedupe Project"
task = "Check source dedupe"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert (
        run(
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
                str(base_source),
            ]
        )
        == 0
    )
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    assert (
        run(
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
                str(first_source),
                "--name",
                "canonical-dedupe",
            ]
        )
        == 0
    )
    first_out = capsys.readouterr().out
    assert _field_labels(first_out) == _source_import_field_labels()
    first_source_id = _field(first_out, "source id")
    first_source_ref = _field(first_out, "source ref")
    first_tree_hash = _field(first_out, "tree hash")
    assert "source name: canonical-dedupe" in first_out
    assert "deduped: false" in first_out

    with sqlite3.connect(home / "alab.db") as conn:
        before_name_conflict = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    before_name_conflict_audits = _audit_type_count(home, "add", "source")
    assert (
        run(
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
                str(conflict_source),
                "--name",
                "Canonical Dedupe!",
            ]
        )
        == 2
    )
    name_conflict_err = capsys.readouterr().err
    assert _field_labels(name_conflict_err) == _error_field_labels()
    assert "error code: NAME_CONFLICT" in name_conflict_err
    assert "source name already exists" in name_conflict_err
    with sqlite3.connect(home / "alab.db") as conn:
        after_name_conflict = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    assert after_name_conflict == before_name_conflict
    assert _audit_type_count(home, "add", "source") == before_name_conflict_audits

    assert (
        run(
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
                str(second_source),
                "--name",
                "ignored-name",
            ]
        )
        == 0
    )
    dedupe_out = capsys.readouterr().out
    assert _field_labels(dedupe_out) == _source_import_field_labels(warning_count=1)
    assert _field(dedupe_out, "source id") == first_source_id
    assert _field(dedupe_out, "source ref") == first_source_ref
    assert _field(dedupe_out, "tree hash") == first_tree_hash
    assert "source name: canonical-dedupe" in dedupe_out
    assert "deduped: true" in dedupe_out
    assert "warning: SOURCE_DEDUPED_NAME_IGNORED" in dedupe_out
    assert _audit_count(home, "add", "source", first_source_id) == 1

    with sqlite3.connect(home / "alab.db") as conn:
        source_count = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        active_hash_count = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE project_id = ? AND tree_hash = ? AND status = 'active'",
            (project_id, first_tree_hash),
        ).fetchone()[0]
        metadata = conn.execute(
            "SELECT origin_metadata_json FROM sources WHERE source_id = ?",
            (first_source_id,),
        ).fetchone()[0]
    assert source_count == 2
    assert active_hash_count == 1
    meta = json.loads(metadata)
    origins = meta["origins"]
    assert meta["primary_origin"] == origins[0]
    assert [origin["origin_type"] for origin in origins] == ["local", "local"]
    assert [origin["safe_summary"] for origin in origins] == ["local", "local"]
    assert [origin["exact"] for origin in origins] == [
        {"source_subdir": None},
        {"source_subdir": None},
    ]
    assert origins[0]["warnings"] == []
    assert origins[1]["warnings"] == ["SOURCE_DEDUPED_NAME_IGNORED"]
    assert "source_path" not in json.dumps(meta, sort_keys=True)

    assert run(["--home", str(home), "--key", admin_key, "source", "archive", first_source_id, "--project", project_id]) == 0
    archive_out = capsys.readouterr().out
    assert _field_labels(archive_out) == _source_status_field_labels()
    assert "source status: archived" in archive_out

    assert (
        run(
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
                str(archived_source),
                "--name",
                "after-archive",
            ]
        )
        == 0
    )
    archived_ignored_out = capsys.readouterr().out
    assert _field_labels(archived_ignored_out) == _source_import_field_labels()
    new_source_id = _field(archived_ignored_out, "source id")
    new_source_ref = _field(archived_ignored_out, "source ref")
    assert new_source_id != first_source_id
    assert new_source_ref != first_source_ref
    assert _field(archived_ignored_out, "tree hash") == first_tree_hash
    assert "source name: after-archive" in archived_ignored_out
    assert "deduped: false" in archived_ignored_out

    with sqlite3.connect(home / "alab.db") as conn:
        rows = conn.execute(
            "SELECT source_id, status, tree_hash FROM sources WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        ).fetchall()
        active_same_hash_count = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE project_id = ? AND tree_hash = ? AND status = 'active'",
            (project_id, first_tree_hash),
        ).fetchone()[0]
    assert len(rows) == 3
    assert {row[0]: row[1] for row in rows}[first_source_id] == "archived"
    assert {row[0]: row[1] for row in rows}[new_source_id] == "active"
    assert active_same_hash_count == 1
    assert _audit_count(home, "add", "source", new_source_id) == 1


def test_source_import_respects_git_and_alab_ignore_rules(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    base_source = tmp_path / "base-source"
    git_source = tmp_path / "git-source"
    gitlink_source = tmp_path / "gitlink-source"
    remote_git_source = tmp_path / "remote-git-source"
    expected_remote_subdir = tmp_path / "expected-remote-subdir"
    base_source.mkdir()
    git_source.mkdir()
    gitlink_source.mkdir()
    remote_git_source.mkdir()
    expected_remote_subdir.mkdir()
    (base_source / "main.py").write_text('print("base")\n', encoding="utf-8")
    (expected_remote_subdir / "main.py").write_text('print("remote subdir")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Source Fidelity Project"
task = "Check source filtering"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    _git(["init"], git_source)
    _git(["config", "user.name", "ALab Test"], git_source)
    _git(["config", "user.email", "alab@example.test"], git_source)
    _git(["config", "commit.gpgsign", "false"], git_source)
    (git_source / ".gitignore").write_text("ignored.log\n", encoding="utf-8")
    (git_source / ".alabignore").write_text("hidden.txt\n", encoding="utf-8")
    (git_source / ".env").write_text("TRACKED_SECRET=1\n", encoding="utf-8")
    (git_source / "keep.py").write_text('print("tracked")\n', encoding="utf-8")
    _git(["add", ".gitignore", ".alabignore", ".env", "keep.py"], git_source)
    _git(["commit", "-m", "tracked source"], git_source)
    (git_source / "local.py").write_text('print("untracked")\n', encoding="utf-8")
    (git_source / "hidden.txt").write_text("excluded by alabignore\n", encoding="utf-8")
    (git_source / "ignored.log").write_text("excluded by gitignore\n", encoding="utf-8")

    _git(["init"], remote_git_source)
    _git(["config", "user.name", "ALab Test"], remote_git_source)
    _git(["config", "user.email", "alab@example.test"], remote_git_source)
    _git(["config", "commit.gpgsign", "false"], remote_git_source)
    (remote_git_source / "app").mkdir()
    (remote_git_source / "app" / "main.py").write_text('print("remote subdir")\n', encoding="utf-8")
    (remote_git_source / "outside.py").write_text('print("outside")\n', encoding="utf-8")
    _git(["add", "app/main.py", "outside.py"], remote_git_source)
    _git(["commit", "-m", "remote source"], remote_git_source)
    _git(["branch", "-M", "main"], remote_git_source)
    remote_commit = _git(["rev-parse", "HEAD"], remote_git_source)

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(base_source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    _git(["init"], gitlink_source)
    _git(["config", "user.name", "ALab Test"], gitlink_source)
    _git(["config", "user.email", "alab@example.test"], gitlink_source)
    _git(["config", "commit.gpgsign", "false"], gitlink_source)
    _git(["update-index", "--add", "--cacheinfo", "160000", "1111111111111111111111111111111111111111", "vendor/module"], gitlink_source)
    _git(["commit", "-m", "gitlink source"], gitlink_source)
    before_gitlink_refs = _source_refs(home, project_id)
    before_gitlink_source_count = _row_count(home, "sources", "project_id", project_id)
    before_gitlink_audits = _audit_type_count(home, "add", "source")
    assert run(["--home", str(home), "--key", admin_key, "source", "import", "--project", project_id, "--source-path", str(gitlink_source), "--name", "gitlink"]) == 2
    gitlink_err = capsys.readouterr().err
    assert _field_labels(gitlink_err) == _error_field_labels()
    assert "error code: SOURCE_INVALID" in gitlink_err
    assert "Git submodules/gitlinks are not supported" in gitlink_err
    assert "next: vendor or expand submodule contents before import" in gitlink_err
    assert _row_count(home, "sources", "project_id", project_id) == before_gitlink_source_count
    assert _audit_type_count(home, "add", "source") == before_gitlink_audits
    assert _source_refs(home, project_id) == before_gitlink_refs

    assert run(["--home", str(home), "--key", admin_key, "source", "import", "--project", project_id, "--source-path", str(git_source), "--name", "git-fidelity"]) == 0
    import_out = capsys.readouterr().out
    assert _field_labels(import_out) == _source_import_field_labels(warning_count=1)
    source_ref = _field(import_out, "source ref")

    assert "warning: TRACKED_SENSITIVE_SOURCE_FILE" in import_out
    assert _source_tree_files(home, project_id, source_ref) == {".alabignore", ".env", ".gitignore", "keep.py", "local.py"}

    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "source",
                "import",
                "--project",
                project_id,
                "--source-git",
                str(remote_git_source),
                "--git-ref",
                "main",
                "--source-subdir",
                "app",
                "--name",
                "remote-git-subdir",
            ]
        )
        == 0
    )
    git_import_out = capsys.readouterr().out
    assert _field_labels(git_import_out) == _source_import_field_labels()
    git_source_id = _field(git_import_out, "source id")
    git_source_ref = _field(git_import_out, "source ref")
    assert "warning:" not in git_import_out
    assert _source_tree_files(home, project_id, git_source_ref) == {"main.py"}
    with sqlite3.connect(home / "alab.db") as conn:
        git_source_row = conn.execute(
            "SELECT tree_hash, origin_metadata_json FROM sources WHERE source_id = ?",
            (git_source_id,),
        ).fetchone()
    git_origin = json.loads(git_source_row[1])["primary_origin"]
    assert git_source_row[0] == canonical_tree_hash(expected_remote_subdir)
    assert git_origin["origin_type"] == "git"
    assert git_origin["safe_summary"] == "git"
    assert git_origin["exact"] == {"git_ref": "main", "resolved_commit": remote_commit, "source_subdir": "app"}
    assert git_origin["warnings"] == []
    assert "source_git" not in json.dumps(git_origin, sort_keys=True)
    assert str(remote_git_source) not in json.dumps(git_origin, sort_keys=True)


def test_source_import_empty_after_filter_warns(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    base_source = tmp_path / "base-source"
    sensitive_source = tmp_path / "sensitive-source"
    base_source.mkdir()
    sensitive_source.mkdir()
    (base_source / "main.py").write_text('print("base")\n', encoding="utf-8")
    (sensitive_source / ".env").write_text("SECRET=1\n", encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Empty Filter Project"
task = "Warn on empty filtered source"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(base_source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    assert run(["--home", str(home), "--key", admin_key, "source", "import", "--project", project_id, "--source-path", str(sensitive_source), "--name", "filtered-empty"]) == 0
    import_out = capsys.readouterr().out
    assert _field_labels(import_out) == _source_import_field_labels(warning_count=1)
    source_ref = _field(import_out, "source ref")

    assert "warning: SOURCE_EMPTY_AFTER_FILTER" in import_out
    assert _source_tree_files(home, project_id, source_ref) == set()


def test_tokens_checkout_worktree_and_annotations(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

print("collab")
Path(os.environ["ALAB_RUN_DIR"], "token-artifact.txt").write_text("token artifact", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Collab Project"
task = "Exercise collaboration commands"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:token-artifact.txt"]

[secret_env]
API_TOKEN = "annotation-secret"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    validation_id = _field(project_out, "validation id")
    with sqlite3.connect(home / "alab.db") as conn:
        validation_artifact_id = conn.execute(
            "SELECT artifact_id FROM artifacts WHERE validation_id = ? AND relative_path = 'token-artifact.txt'",
            (validation_id,),
        ).fetchone()[0]

    worktree = tmp_path / "exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "collab", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    peer_worktree = tmp_path / "peer-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "peer", "--path", str(peer_worktree)]) == 0
    peer_exp_id = _field(capsys.readouterr().out, "exp id")
    exact_annotation_body = ("界" * 21845) + "x"

    with sqlite3.connect(home / "alab.db") as conn:
        before_unscoped_artifact_target = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    for private_args in ([], ["--private-to-exp", exp_id]):
        assert (
            run(
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
                    f"artifact:{validation_artifact_id}",
                    "--body",
                    "validation artifact target must stay unowned",
                    *private_args,
                ]
            )
            == 2
        )
        unscoped_artifact_target_err = capsys.readouterr().err
        assert _field_labels(unscoped_artifact_target_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in unscoped_artifact_target_err
        assert "annotation target must resolve to exactly one experiment" in unscoped_artifact_target_err
    with sqlite3.connect(home / "alab.db") as conn:
        after_unscoped_artifact_target = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    assert after_unscoped_artifact_target == before_unscoped_artifact_target

    assert (
        run(
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
                f"exp:{exp_id}",
                "--body",
                "annotation-secret",
            ]
        )
        == 2
    )
    admin_secret_annotation_err = capsys.readouterr().err
    assert _field_labels(admin_secret_annotation_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in admin_secret_annotation_err
    assert "annotation body contains an active secret value" in admin_secret_annotation_err
    with sqlite3.connect(home / "alab.db") as conn:
        after_admin_secret_annotation = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    assert after_admin_secret_annotation == before_unscoped_artifact_target

    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "context", "show"]) == 0
    context_out = capsys.readouterr().out
    assert _field_labels(context_out) == _context_show_field_labels()
    assert "registered: true" in context_out
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{peer_exp_id}", "--body", "private peer target", "--private"]) == 0
    cross_private_annotation_out = capsys.readouterr().out
    cross_private_annotation_id = _field(cross_private_annotation_out, "annotation id")
    assert _field_labels(cross_private_annotation_out) == _annotation_add_field_labels()
    assert "visibility: private" in cross_private_annotation_out
    assert run(["--home", str(home), "annotations", "show", cross_private_annotation_id]) == 0
    cross_private_show_out = capsys.readouterr().out
    assert _field_labels(cross_private_show_out) == _annotation_field_labels()
    assert "body:\n  private peer target" in cross_private_show_out
    monkeypatch.chdir(tmp_path)
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "config",
                "set",
                "visibility.scope",
                '"none"',
                "--project",
                project_id,
            ]
        )
        == 0
    )
    assert "runtime affecting: false" in capsys.readouterr().out
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "annotations", "show", cross_private_annotation_id]) == 4
    hidden_cross_private_err = capsys.readouterr().err
    assert _field_labels(hidden_cross_private_err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in hidden_cross_private_err
    assert "annotation is not visible or not found" in hidden_cross_private_err
    assert run(["--home", str(home), "annotate", "edit", cross_private_annotation_id, "--body", "still hidden"]) == 4
    hidden_cross_private_edit_err = capsys.readouterr().err
    assert _field_labels(hidden_cross_private_edit_err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in hidden_cross_private_edit_err
    assert "annotation is not visible in this context" in hidden_cross_private_edit_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT current_revision FROM annotations WHERE annotation_id = ?", (cross_private_annotation_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM annotation_revisions WHERE annotation_id = ?", (cross_private_annotation_id,)).fetchone()[0] == 1
    monkeypatch.chdir(tmp_path)
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "project",
                "config",
                "set",
                "visibility.scope",
                '"same_project"',
                "--project",
                project_id,
            ]
        )
        == 0
    )
    assert "runtime affecting: false" in capsys.readouterr().out
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "annotations", "show", cross_private_annotation_id]) == 0
    restored_cross_private_show = capsys.readouterr().out
    assert _field_labels(restored_cross_private_show) == _annotation_field_labels()
    assert "body:\n  private peer target" in restored_cross_private_show
    assert run(["--home", str(home), "context", "show", "--path", str(worktree), "--path", str(tmp_path)]) == 2
    duplicate_context_show_err = capsys.readouterr().err
    assert _field_labels(duplicate_context_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_context_show_err
    assert "--path may be provided once" in duplicate_context_show_err
    assert run(["--home", str(home), "context", "show", "extra", "--path", str(worktree)]) == 2
    extra_context_show_err = capsys.readouterr().err
    assert _field_labels(extra_context_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_context_show_err
    assert "context show accepts no positional arguments" in extra_context_show_err
    assert run(["--home", str(home), "context", "show", "--path", str(worktree), "--reason", "ignored"]) == 2
    unsupported_context_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_context_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_context_show_err
    assert "unsupported option --reason" in unsupported_context_show_err
    assert run(["--home", str(home), "--key", admin_key, "context", "repair", "--path", str(worktree), "--path", str(tmp_path)]) == 2
    duplicate_context_repair_err = capsys.readouterr().err
    assert _field_labels(duplicate_context_repair_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_context_repair_err
    assert "--path may be provided once" in duplicate_context_repair_err
    context_marker = worktree / ".alab" / "context.json"
    marker_before_extra_repair = context_marker.read_text(encoding="utf-8")
    repair_audits_before_extra = _audit_count(home, "repair", "worktree", exp_id)
    assert run(["--home", str(home), "--key", admin_key, "context", "repair", "--path", str(worktree), "--reason", "ignored"]) == 2
    unsupported_context_repair_err = capsys.readouterr().err
    assert _field_labels(unsupported_context_repair_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_context_repair_err
    assert "unsupported option --reason" in unsupported_context_repair_err
    assert context_marker.read_text(encoding="utf-8") == marker_before_extra_repair
    assert _audit_count(home, "repair", "worktree", exp_id) == repair_audits_before_extra
    assert run(["--home", str(home), "--key", admin_key, "context", "repair", "extra", "--path", str(worktree)]) == 2
    extra_context_repair_err = capsys.readouterr().err
    assert _field_labels(extra_context_repair_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_context_repair_err
    assert "context repair accepts no positional arguments" in extra_context_repair_err
    assert context_marker.read_text(encoding="utf-8") == marker_before_extra_repair
    assert _audit_count(home, "repair", "worktree", exp_id) == repair_audits_before_extra
    assert run(["--home", str(home), "--key", admin_key, "context", "repair", "--path", str(worktree)]) == 0
    repair_out = capsys.readouterr().out
    assert _field_labels(repair_out) == _context_repair_field_labels()
    assert "status: repaired" in repair_out

    assert run(["--home", str(home), "run", "--message", "baseline"]) == 0
    baseline_run_out = capsys.readouterr().out
    assert "run status: passed" in baseline_run_out
    run_id = _field(baseline_run_out, "run id")
    with sqlite3.connect(home / "alab.db") as conn:
        artifact_id = conn.execute(
            "SELECT artifact_id FROM artifacts WHERE run_id = ? AND relative_path = 'token-artifact.txt'",
            (run_id,),
        ).fetchone()[0]
        stdout_log_id = conn.execute(
            "SELECT log_id FROM log_streams WHERE run_id = ? AND stream = 'stdout' AND hidden = 0",
            (run_id,),
        ).fetchone()[0]
    fake_run_id = "run-missing-" + "A" * 22
    assert run(["--home", str(home), "runs", "show", fake_run_id]) == 4
    fake_run_err = capsys.readouterr().err
    assert _field_labels(fake_run_err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in fake_run_err
    assert "RUN_NOT_FOUND" not in fake_run_err
    assert "not visible or not found" in fake_run_err
    fake_exp_id = "exp-missing-" + "B" * 22
    assert run(["--home", str(home), "exp", "show", fake_exp_id]) == 4
    fake_exp_err = capsys.readouterr().err
    assert _field_labels(fake_exp_err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in fake_exp_err
    assert "EXPERIMENT_NOT_FOUND" not in fake_exp_err
    with sqlite3.connect(home / "alab.db") as conn:
        before_ambient_optional_auth = {
            "peer_tags": conn.execute("SELECT COUNT(*) FROM experiment_tags WHERE exp_id = ?", (peer_exp_id,)).fetchone()[0],
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
        }
    monkeypatch.setenv("ALAB_KEY", admin_key)
    assert run(["--home", str(home), "logs", "list", "--include-hidden"]) == 4
    ambient_hidden_logs_err = capsys.readouterr().err
    assert _field_labels(ambient_hidden_logs_err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in ambient_hidden_logs_err
    assert "hidden logs require admin/root" in ambient_hidden_logs_err
    assert run(["--home", str(home), "exp", "tag", "add", peer_exp_id, "ambient-admin"]) == 3
    ambient_peer_tag_err = capsys.readouterr().err
    assert _field_labels(ambient_peer_tag_err) == _error_field_labels()
    assert "error code: AUTH_REQUIRED" in ambient_peer_tag_err
    assert "owning experiment token context" in ambient_peer_tag_err
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--private-to-exp", peer_exp_id, "--body", "ambient private"]) == 2
    ambient_private_annotation_err = capsys.readouterr().err
    assert _field_labels(ambient_private_annotation_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in ambient_private_annotation_err
    assert "--private-to-exp is only valid with admin/root" in ambient_private_annotation_err
    monkeypatch.delenv("ALAB_KEY")
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM experiment_tags WHERE exp_id = ?", (peer_exp_id,)).fetchone()[0] == before_ambient_optional_auth["peer_tags"]
        assert conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == before_ambient_optional_auth["annotations"]

    monkeypatch.chdir(tmp_path)
    with sqlite3.connect(home / "alab.db") as conn:
        before_admin_private_without_exp = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    assert (
        run(
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
                f"exp:{exp_id}",
                "--private",
                "--body",
                "admin private needs explicit experiment",
            ]
        )
        == 2
    )
    admin_private_without_exp_err = capsys.readouterr().err
    assert _field_labels(admin_private_without_exp_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in admin_private_without_exp_err
    assert "--private requires --private-to-exp for admin/root" in admin_private_without_exp_err
    with sqlite3.connect(home / "alab.db") as conn:
        after_admin_private_without_exp = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    assert after_admin_private_without_exp == before_admin_private_without_exp

    with sqlite3.connect(home / "alab.db") as conn:
        before_project_shorthand = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    assert (
        run(
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
                "project shorthand should fail",
            ]
        )
        == 2
    )
    project_shorthand_err = capsys.readouterr().err
    assert _field_labels(project_shorthand_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in project_shorthand_err
    assert "path/lines shorthand requires an experiment context" in project_shorthand_err
    with sqlite3.connect(home / "alab.db") as conn:
        after_project_shorthand = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    assert after_project_shorthand == before_project_shorthand

    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "annotate", "add", "--target", "path:main.py", "--body", "path note"]) == 0
    path_annotation_out = capsys.readouterr().out
    assert _field_labels(path_annotation_out) == _annotation_add_field_labels()
    assert "target type: path" in path_annotation_out
    assert "target id:" in path_annotation_out
    assert run(["--home", str(home), "annotate", "add", "--target", "lines:main.py:1-1", "--body", "line note"]) == 0
    line_annotation_out = capsys.readouterr().out
    assert _field_labels(line_annotation_out) == _annotation_add_field_labels()
    assert "target type: lines" in line_annotation_out
    assert "resolved commit:" in line_annotation_out
    head_commit = _git(["rev-parse", "HEAD"], worktree)
    assert run(["--home", str(home), "annotate", "add", "--target", f"path:{exp_id}@HEAD:main.py", "--body", "head alias note"]) == 0
    head_alias_annotation_out = capsys.readouterr().out
    assert _field_labels(head_alias_annotation_out) == _annotation_add_field_labels()
    head_alias_annotation_id = _field(head_alias_annotation_out, "annotation id")
    assert _field(head_alias_annotation_out, "resolved commit") == head_commit
    with sqlite3.connect(home / "alab.db") as conn:
        head_alias_row = conn.execute(
            "SELECT target_id, target_json, resolved_commit FROM annotations WHERE annotation_id = ?",
            (head_alias_annotation_id,),
        ).fetchone()
    head_alias_target = json.loads(head_alias_row[1])
    assert head_alias_row[0] == f"{exp_id}:{head_commit}:main.py"
    assert head_alias_row[2] == head_commit
    assert head_alias_target["commit"] == head_commit
    assert head_alias_target["target_id"] == f"{exp_id}:{head_commit}:main.py"
    assert run(["--home", str(home), "annotate", "add", "--target", f"lines:{exp_id}@best:main.py:1-1", "--body", "best alias note"]) == 0
    best_alias_annotation_out = capsys.readouterr().out
    assert _field_labels(best_alias_annotation_out) == _annotation_add_field_labels()
    best_alias_annotation_id = _field(best_alias_annotation_out, "annotation id")
    assert _field(best_alias_annotation_out, "resolved commit") == head_commit
    with sqlite3.connect(home / "alab.db") as conn:
        best_alias_row = conn.execute(
            "SELECT target_id, target_json, resolved_commit FROM annotations WHERE annotation_id = ?",
            (best_alias_annotation_id,),
        ).fetchone()
    best_alias_target = json.loads(best_alias_row[1])
    assert best_alias_row[0] == f"{exp_id}:{head_commit}:main.py"
    assert best_alias_row[2] == head_commit
    assert best_alias_target["commit"] == head_commit
    assert best_alias_target["target_id"] == f"{exp_id}:{head_commit}:main.py"
    assert best_alias_target["line_range"] == {"start": 1, "end": 1}
    exact_annotation_file = tmp_path / "exact-annotation.txt"
    exact_annotation_file.write_text(exact_annotation_body, encoding="utf-8")
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body-file", str(exact_annotation_file)]) == 0
    exact_annotation_out = capsys.readouterr().out
    assert _field_labels(exact_annotation_out) == _annotation_add_field_labels()
    exact_annotation_id = _field(exact_annotation_out, "annotation id")
    with sqlite3.connect(home / "alab.db") as conn:
        exact_visibility_json = conn.execute(
            "SELECT visibility_json FROM annotations WHERE annotation_id = ?",
            (exact_annotation_id,),
        ).fetchone()[0]
    assert json.loads(exact_visibility_json) == {"schema_version": 1, "scope": "project", "constraints": {}}
    assert run(["--home", str(home), "annotate", "add", "--target", "path:missing.py", "--body", "bad path"]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().err
    assert run(["--home", str(home), "annotate", "add", "--target", "lines:main.py:99-99", "--body", "bad line"]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().err
    assert run(["--home", str(home), "annotate", "add", "--target", "lines:missing.py:1-1", "--body", "bad missing line"]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().err
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body", "界" * 21846]) == 2
    annotation_body_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in annotation_body_err
    assert "annotation body exceeds 65536 bytes" in annotation_body_err
    long_annotation_file = tmp_path / "long-annotation.txt"
    long_annotation_file.write_text("界" * 21846, encoding="utf-8")
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body-file", str(long_annotation_file)]) == 2
    annotation_body_file_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in annotation_body_file_err
    assert "annotation body exceeds 65536 bytes" in annotation_body_file_err

    annotations_before_extra_add = _table_count(home, "annotations")
    revisions_before_extra_add = _table_count(home, "annotation_revisions")
    missing_extra_annotation_file = tmp_path / "missing-extra-annotation.txt"
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body-file", str(missing_extra_annotation_file)]) == 2
    missing_annotation_file_err = capsys.readouterr().err
    assert _field_labels(missing_annotation_file_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in missing_annotation_file_err
    assert "annotation body file not found" in missing_annotation_file_err
    assert "No such file" not in missing_annotation_file_err
    assert _table_count(home, "annotations") == annotations_before_extra_add
    assert _table_count(home, "annotation_revisions") == revisions_before_extra_add
    assert run(["--home", str(home), "annotate", "add", "extra", "--target", f"exp:{exp_id}", "--body-file", str(missing_extra_annotation_file)]) == 2
    extra_annotation_add_err = capsys.readouterr().err
    assert _field_labels(extra_annotation_add_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_annotation_add_err
    assert "annotate add accepts no positional arguments" in extra_annotation_add_err
    assert "No such file" not in extra_annotation_add_err
    assert _table_count(home, "annotations") == annotations_before_extra_add
    assert _table_count(home, "annotation_revisions") == revisions_before_extra_add
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body-file", str(missing_extra_annotation_file), "--reason", "ignored"]) == 2
    unsupported_annotation_add_err = capsys.readouterr().err
    assert _field_labels(unsupported_annotation_add_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_annotation_add_err
    assert "unsupported option --reason" in unsupported_annotation_add_err
    assert "No such file" not in unsupported_annotation_add_err
    assert _table_count(home, "annotations") == annotations_before_extra_add
    assert _table_count(home, "annotation_revisions") == revisions_before_extra_add

    missing_annotation_a = tmp_path / "missing-annotation-a.txt"
    missing_annotation_b = tmp_path / "missing-annotation-b.txt"
    with sqlite3.connect(home / "alab.db") as conn:
        before_duplicate_body = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    duplicate_annotation_inputs = [
        (["--body", "one", "--body", "two"], "--body may be provided once"),
        (["--body-file", str(missing_annotation_a), "--body-file", str(missing_annotation_b)], "--body-file may be provided once"),
        (["--body", "one", "--body-file", str(missing_annotation_a)], "annotation requires exactly one of --body or --body-file"),
    ]
    for input_args, message in duplicate_annotation_inputs:
        assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", *input_args]) == 2
        duplicate_body_err = capsys.readouterr().err
        assert _field_labels(duplicate_body_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_body_err
        assert message in duplicate_body_err
        assert "No such file" not in duplicate_body_err
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--target", f"run:{run_id}", "--body", "duplicate target"]) == 2
    duplicate_target_err = capsys.readouterr().err
    assert _field_labels(duplicate_target_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_target_err
    assert "--target may be provided once" in duplicate_target_err
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body", "duplicate private", "--private", "--private"]) == 2
    duplicate_private_err = capsys.readouterr().err
    assert _field_labels(duplicate_private_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_private_err
    assert "--private may be provided once" in duplicate_private_err
    with sqlite3.connect(home / "alab.db") as conn:
        after_duplicate_body = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    assert after_duplicate_body == before_duplicate_body

    with sqlite3.connect(home / "alab.db") as conn:
        before_body_stdin = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body", "stdin body", "--body-stdin"]) == 2
    body_stdin_err = capsys.readouterr().err
    assert _field_labels(body_stdin_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in body_stdin_err
    assert "--body-stdin is not supported" in body_stdin_err
    with sqlite3.connect(home / "alab.db") as conn:
        after_body_stdin = {
            "annotations": conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0],
            "revisions": conn.execute("SELECT COUNT(*) FROM annotation_revisions").fetchone()[0],
        }
    assert after_body_stdin == before_body_stdin

    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body", "first note", "--private"]) == 0
    annotation_out = capsys.readouterr().out
    assert _field_labels(annotation_out) == _annotation_add_field_labels()
    annotation_id = _field(annotation_out, "annotation id")
    assert "visibility: private" in annotation_out
    with sqlite3.connect(home / "alab.db") as conn:
        private_visibility_json = conn.execute(
            "SELECT visibility_json FROM annotations WHERE annotation_id = ?",
            (annotation_id,),
        ).fetchone()[0]
    assert json.loads(private_visibility_json) == {
        "schema_version": 1,
        "scope": "private",
        "creator_exp_id": exp_id,
        "constraints": {},
    }
    assert run(["--home", str(home), "annotate", "edit", annotation_id, "--body", "annotation-secret"]) == 2
    edit_secret_annotation_err = capsys.readouterr().err
    assert _field_labels(edit_secret_annotation_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in edit_secret_annotation_err
    assert "annotation body contains an active secret value" in edit_secret_annotation_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT current_revision FROM annotations WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM annotation_revisions WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1

    assert run(["--home", str(home), "annotate", "edit", annotation_id, "extra", "--body", "ignored"]) == 2
    extra_annotation_edit_err = capsys.readouterr().err
    assert _field_labels(extra_annotation_edit_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_annotation_edit_err
    assert "annotate edit accepts exactly one annotation id" in extra_annotation_edit_err
    missing_edit_annotation_file = tmp_path / "missing-edit-annotation.txt"
    assert run(["--home", str(home), "annotate", "edit", annotation_id, "--body-file", str(missing_edit_annotation_file), "--reason", "ignored"]) == 2
    unsupported_annotation_edit_err = capsys.readouterr().err
    assert _field_labels(unsupported_annotation_edit_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_annotation_edit_err
    assert "unsupported option --reason" in unsupported_annotation_edit_err
    assert "No such file" not in unsupported_annotation_edit_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT current_revision FROM annotations WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM annotation_revisions WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1
    assert run(["--home", str(home), "annotations", "show", annotation_id, "extra"]) == 2
    extra_annotation_show_err = capsys.readouterr().err
    assert _field_labels(extra_annotation_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_annotation_show_err
    assert "annotations show accepts exactly one annotation id" in extra_annotation_show_err
    assert run(["--home", str(home), "annotations", "show", annotation_id, "--reason", "ignored"]) == 2
    unsupported_annotation_show_err = capsys.readouterr().err
    assert _field_labels(unsupported_annotation_show_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_annotation_show_err
    assert "unsupported option --reason" in unsupported_annotation_show_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT current_revision FROM annotations WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM annotation_revisions WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1

    assert run(["--home", str(home), "annotate", "edit", annotation_id[:8], "--body", "short id"]) == 2
    short_annotation_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in short_annotation_err
    assert "object ids must be complete" in short_annotation_err
    assert run(["--home", str(home), "annotate", "edit", annotation_id, "--body", "dup one", "--body", "dup two"]) == 2
    edit_duplicate_body_err = capsys.readouterr().err
    assert _field_labels(edit_duplicate_body_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in edit_duplicate_body_err
    assert "--body may be provided once" in edit_duplicate_body_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT current_revision FROM annotations WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM annotation_revisions WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1
    assert run(["--home", str(home), "annotate", "edit", annotation_id, "--body", "author dup", "--author", "one", "--author", "two"]) == 2
    edit_duplicate_author_err = capsys.readouterr().err
    assert _field_labels(edit_duplicate_author_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in edit_duplicate_author_err
    assert "--author may be provided once" in edit_duplicate_author_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT current_revision FROM annotations WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM annotation_revisions WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1
    assert run(["--home", str(home), "annotate", "edit", annotation_id, "--body", "stdin edit", "--body-stdin"]) == 2
    edit_stdin_err = capsys.readouterr().err
    assert _field_labels(edit_stdin_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in edit_stdin_err
    assert "--body-stdin is not supported" in edit_stdin_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT current_revision FROM annotations WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM annotation_revisions WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 1
    assert run(["--home", str(home), "annotate", "edit", annotation_id, "--body", "second note", "--author", "agent"]) == 0
    annotation_edit_out = capsys.readouterr().out
    assert _field_labels(annotation_edit_out) == _annotation_edit_field_labels()
    assert "revision: 2" in annotation_edit_out
    assert run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-id", exp_id, "--author", "agent", "--created-by", exp_id, "--private", "--query", "second", "--limit", "1"]) == 0
    filtered_annotations = capsys.readouterr().out
    assert _field_labels(filtered_annotations) == _annotation_field_labels()
    assert f"annotation id: {annotation_id}" in filtered_annotations
    assert run(["--home", str(home), "annotations", "list", "extra", "--target-type", "experiment", "--target-id", exp_id]) == 2
    extra_annotations_list_err = capsys.readouterr().err
    assert _field_labels(extra_annotations_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_annotations_list_err
    assert "annotations list accepts no positional arguments" in extra_annotations_list_err
    assert run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-id", exp_id, "--reason", "ignored"]) == 2
    unsupported_annotations_list_err = capsys.readouterr().err
    assert _field_labels(unsupported_annotations_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_annotations_list_err
    assert "unsupported option --reason" in unsupported_annotations_list_err
    assert run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-id", exp_id, "--target", exp_id]) == 2
    conflicting_annotation_target_err = capsys.readouterr().err
    assert _field_labels(conflicting_annotation_target_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in conflicting_annotation_target_err
    assert "annotations list accepts only one of --target-id or --target" in conflicting_annotation_target_err
    wrong_annotation_creator = "exp-missing-" + "D" * 22
    assert run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-id", exp_id, "--author", "agent", "--created-by", wrong_annotation_creator, "--private", "--query", "second"]) == 0
    wrong_creator_annotations = capsys.readouterr().out
    assert _field_labels(wrong_creator_annotations) == []
    assert annotation_id not in wrong_creator_annotations
    assert run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-id", exp_id, "--sort", "updated:desc"]) == 0
    sorted_annotations = capsys.readouterr().out
    assert all(labels == _annotation_field_labels() for labels in _block_labels(sorted_annotations))
    assert f"annotation id: {annotation_id}" in sorted_annotations
    assert run(["--home", str(home), "observe", "annotations", "list", "--target-type", "experiment", "--target-id", exp_id, "--sort", "updated:desc"]) == 0
    canonical_annotations_list = capsys.readouterr().out
    assert run(["annotations", "list", "--target-type", "experiment", "--target-id", exp_id, "--sort", "updated:desc", "--home", str(home)]) == 0
    assert capsys.readouterr().out == canonical_annotations_list
    assert run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-id", exp_id[:8]]) == 2
    short_target_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in short_target_err
    assert "object ids must be complete" in short_target_err
    assert run(["--home", str(home), "annotations", "list", "--sort", "body:asc"]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().err
    assert run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-type", "run"]) == 2
    duplicate_annotation_filter_err = capsys.readouterr().err
    assert _field_labels(duplicate_annotation_filter_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_annotation_filter_err
    assert "--target-type may be provided once" in duplicate_annotation_filter_err
    for list_args, message in [
        (["--limit", "1", "--limit", "2"], "--limit may be provided once"),
        (["--sort", "updated:desc", "--sort", "created:asc"], "--sort may be provided once"),
    ]:
        assert run(["--home", str(home), "annotations", "list", *list_args]) == 2
        duplicate_annotation_list_err = capsys.readouterr().err
        assert _field_labels(duplicate_annotation_list_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_annotation_list_err
        assert message in duplicate_annotation_list_err
    assert run(["--home", str(home), "annotations", "show", annotation_id, "--history"]) == 0
    show_out = capsys.readouterr().out
    assert _field_labels(show_out) == _annotation_field_labels(history_revision_count=2)
    assert "body:\n  second note" in show_out
    assert "revision: 1:" in show_out
    assert "revision: 2:" in show_out
    assert run(["--home", str(home), "observe", "annotations", "show", annotation_id, "--history"]) == 0
    canonical_annotation_show = capsys.readouterr().out
    assert run(["annotations", "show", annotation_id, "--history", "--home", str(home)]) == 0
    assert capsys.readouterr().out == canonical_annotation_show
    assert run(["--home", str(home), "annotations", "show", annotation_id, "--history", "--history"]) == 2
    duplicate_history_err = capsys.readouterr().err
    assert _field_labels(duplicate_history_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_history_err
    assert "--history may be provided once" in duplicate_history_err
    assert run(["--home", str(home), "annotate", "add", "--target", f"exp:{exp_id}", "--body", ""]) == 0
    empty_annotation_out = capsys.readouterr().out
    assert _field_labels(empty_annotation_out) == _annotation_add_field_labels()
    empty_annotation_id = _field(empty_annotation_out, "annotation id")
    assert run(["--home", str(home), "annotations", "show", empty_annotation_id]) == 0
    empty_annotation_show = capsys.readouterr().out
    assert _field_labels(empty_annotation_show) == _annotation_field_labels()
    assert "body:\n  [empty]" in empty_annotation_show
    fake_annotation_id = "ann-missing-" + "C" * 22
    assert run(["--home", str(home), "annotations", "show", fake_annotation_id]) == 4
    fake_annotation_err = capsys.readouterr().err
    assert _field_labels(fake_annotation_err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in fake_annotation_err
    assert "ANNOTATION_NOT_FOUND" not in fake_annotation_err
    assert "not visible or not found" in fake_annotation_err

    assert run(["--home", str(home), "--key", admin_key, "exp", "token", "list", exp_id, "--project", project_id]) == 0
    token_list = capsys.readouterr().out
    assert _field_labels(token_list) == _credential_list_field_labels()
    assert "token mode: worktree" in token_list
    assert "path status: present" in token_list

    nested_inspect = worktree / "nested-inspect"
    initial_inspection_add_audits = _audit_type_count(home, "add", "inspection_checkout")
    duplicate_checkout_a = tmp_path / "duplicate-inspect-a"
    duplicate_checkout_b = tmp_path / "duplicate-inspect-b"
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(duplicate_checkout_a), "--path", str(duplicate_checkout_b), "--commit", "latest"]) == 2
    duplicate_checkout_path_err = capsys.readouterr().err
    assert _field_labels(duplicate_checkout_path_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in duplicate_checkout_path_err
    assert "--path may be provided once" in duplicate_checkout_path_err
    assert not duplicate_checkout_a.exists()
    assert not duplicate_checkout_b.exists()
    assert _audit_type_count(home, "add", "inspection_checkout") == initial_inspection_add_audits
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(nested_inspect), "--commit", "latest"]) == 4
    nested_checkout_err = capsys.readouterr().err
    assert _field_labels(nested_checkout_err) == _error_field_labels()
    assert "error code: CONTEXT_CONFLICT" in nested_checkout_err
    assert "target path nests inside another ALab context" in nested_checkout_err
    assert not nested_inspect.exists()
    assert _audit_type_count(home, "add", "inspection_checkout") == initial_inspection_add_audits

    nonempty_inspect = tmp_path / "nonempty-inspect"
    nonempty_inspect.mkdir()
    (nonempty_inspect / "existing.txt").write_text("keep\n", encoding="utf-8")
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(nonempty_inspect), "--commit", "latest"]) == 2
    nonempty_checkout_err = capsys.readouterr().err
    assert _field_labels(nonempty_checkout_err) == _error_field_labels()
    assert "error code: OUTPUT_EXISTS" in nonempty_checkout_err
    assert "inspection checkout path already exists" in nonempty_checkout_err
    assert (nonempty_inspect / "existing.txt").read_text(encoding="utf-8") == "keep\n"
    assert not (nonempty_inspect / ".alab").exists()
    assert _audit_type_count(home, "add", "inspection_checkout") == initial_inspection_add_audits
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM path_registry WHERE exp_id = ? AND context_type = 'inspection' AND status = 'active'", (exp_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE exp_id = ? AND token_mode = 'inspection' AND status = 'active'", (exp_id,)).fetchone()[0] == 0

    invalid_commit_inspect = tmp_path / "invalid-commit-inspect"
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(invalid_commit_inspect), "--commit", "HEAD"]) == 2
    invalid_commit_checkout_err = capsys.readouterr().err
    assert _field_labels(invalid_commit_checkout_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in invalid_commit_checkout_err
    assert "commit selector must be latest, final, best, or a commit SHA" in invalid_commit_checkout_err
    assert not invalid_commit_inspect.exists()
    assert _audit_type_count(home, "add", "inspection_checkout") == initial_inspection_add_audits
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM path_registry WHERE exp_id = ? AND context_type = 'inspection' AND status = 'active'", (exp_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE exp_id = ? AND token_mode = 'inspection' AND status = 'active'", (exp_id,)).fetchone()[0] == 0

    inspect = tmp_path / "inspect"
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(inspect), "--commit", "latest"]) == 0
    checkout_out = capsys.readouterr().out
    assert _field_labels(checkout_out) == _inspection_checkout_create_field_labels()
    inspection_token_id = _field(checkout_out, "token id")
    assert "object: inspection_checkout" in checkout_out
    assert _audit_type_count(home, "add", "inspection_checkout") == initial_inspection_add_audits + 1
    ambient_remove_inspect = tmp_path / "ambient-remove-inspect"
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(ambient_remove_inspect), "--commit", "latest"]) == 0
    ambient_remove_checkout_out = capsys.readouterr().out
    ambient_remove_inspection_token_id = _field(ambient_remove_checkout_out, "token id")
    assert _field_labels(ambient_remove_checkout_out) == _inspection_checkout_create_field_labels()
    assert _audit_type_count(home, "add", "inspection_checkout") == initial_inspection_add_audits + 2

    monkeypatch.chdir(inspect)
    assert run(["--home", str(home), "status"]) == 0
    assert "context type: inspection" in capsys.readouterr().out
    assert run(["--home", str(home), "runs", "list"]) == 0
    assert "run status: passed" in capsys.readouterr().out
    before_ambient_checkout_remove_audits = _audit_type_count(home, "remove", "inspection_checkout")
    monkeypatch.setenv("ALAB_KEY", admin_key)
    assert (
        run(
            [
                "--home",
                str(home),
                "exp",
                "checkout",
                "remove",
                "--project",
                project_id,
                "--token-id",
                ambient_remove_inspection_token_id,
                "--force",
                "--confirm",
                ambient_remove_inspection_token_id,
            ]
        )
        == 3
    )
    ambient_checkout_remove_err = capsys.readouterr().err
    assert _field_labels(ambient_checkout_remove_err) == _error_field_labels()
    assert "error code: AUTH_REQUIRED" in ambient_checkout_remove_err
    assert "matching inspection token context" in ambient_checkout_remove_err
    monkeypatch.delenv("ALAB_KEY")
    assert ambient_remove_inspect.exists()
    assert _audit_type_count(home, "remove", "inspection_checkout") == before_ambient_checkout_remove_audits
    assert (
        run(
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
                ambient_remove_inspection_token_id,
                "--force",
                "--confirm",
                ambient_remove_inspection_token_id,
            ]
        )
        == 0
    )
    explicit_checkout_remove_out = capsys.readouterr().out
    assert _field_labels(explicit_checkout_remove_out) == _inspection_checkout_remove_field_labels(dry_run=False)
    assert not ambient_remove_inspect.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        before_duplicate_checkout_remove = {
            "active_paths": conn.execute(
                "SELECT COUNT(*) FROM path_registry WHERE token_id = ? AND context_type = 'inspection' AND status = 'active'",
                (inspection_token_id,),
            ).fetchone()[0],
            "active_tokens": conn.execute(
                "SELECT COUNT(*) FROM credentials WHERE credential_id = ? AND token_mode = 'inspection' AND status = 'active'",
                (inspection_token_id,),
            ).fetchone()[0],
        }
    before_duplicate_checkout_remove_audits = _audit_type_count(home, "remove", "inspection_checkout")
    duplicate_checkout_remove_cases = [
        (["--token-id", inspection_token_id, "--token-id", inspection_token_id], "--token-id may be provided once"),
        (["--path", str(inspect), "--path", str(inspect)], "--path may be provided once"),
        (["--token-id", inspection_token_id, "--path", str(inspect)], "checkout remove requires exactly one of --token-id or --path"),
    ]
    for selector_args, message in duplicate_checkout_remove_cases:
        assert run(["--home", str(home), "exp", "checkout", "remove", "--project", project_id, *selector_args]) == 2
        duplicate_checkout_remove_err = capsys.readouterr().err
        assert _field_labels(duplicate_checkout_remove_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_checkout_remove_err
        assert message in duplicate_checkout_remove_err
        assert inspect.exists()
        with sqlite3.connect(home / "alab.db") as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM path_registry WHERE token_id = ? AND context_type = 'inspection' AND status = 'active'",
                (inspection_token_id,),
            ).fetchone()[0] == before_duplicate_checkout_remove["active_paths"]
            assert conn.execute(
                "SELECT COUNT(*) FROM credentials WHERE credential_id = ? AND token_mode = 'inspection' AND status = 'active'",
                (inspection_token_id,),
            ).fetchone()[0] == before_duplicate_checkout_remove["active_tokens"]
        assert _audit_type_count(home, "remove", "inspection_checkout") == before_duplicate_checkout_remove_audits
    _assert_duplicate_option_error(["--home", str(home), "exp", "checkout", "remove", "--project", project_id, "--token-id", inspection_token_id, "--dry-run", "--dry-run"], "--dry-run", capsys)
    assert inspect.exists()
    assert _audit_type_count(home, "remove", "inspection_checkout") == before_duplicate_checkout_remove_audits
    assert run(["--home", str(home), "exp", "checkout", "remove", "extra", "--project", project_id, "--token-id", inspection_token_id, "--force", "--confirm", inspection_token_id]) == 2
    extra_checkout_remove_err = capsys.readouterr().err
    assert _field_labels(extra_checkout_remove_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_checkout_remove_err
    assert "exp checkout remove accepts no positional arguments" in extra_checkout_remove_err
    assert inspect.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM path_registry WHERE token_id = ? AND context_type = 'inspection' AND status = 'active'",
            (inspection_token_id,),
        ).fetchone()[0] == before_duplicate_checkout_remove["active_paths"]
        assert conn.execute(
            "SELECT COUNT(*) FROM credentials WHERE credential_id = ? AND token_mode = 'inspection' AND status = 'active'",
            (inspection_token_id,),
        ).fetchone()[0] == before_duplicate_checkout_remove["active_tokens"]
    assert _audit_type_count(home, "remove", "inspection_checkout") == before_duplicate_checkout_remove_audits
    _assert_confirm_guard(
        ["--home", str(home), "exp", "checkout", "remove", "--project", project_id, "--token-id", inspection_token_id],
        inspection_token_id,
        "checkout remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "exp", "checkout", "remove", "--project", project_id, "--token-id", inspection_token_id, "--force", "--confirm", inspection_token_id]) == 0
    checkout_remove_out = capsys.readouterr().out
    assert _field_labels(checkout_remove_out) == _inspection_checkout_remove_field_labels(dry_run=False)
    assert "removed: true" in checkout_remove_out

    monkeypatch.chdir(tmp_path)
    nested_restore = worktree / "nested-restore"
    assert run(["--home", str(home), "--key", admin_key, "exp", "worktree", "restore", exp_id, "--project", project_id, "--path", str(nested_restore)]) == 4
    nested_restore_err = capsys.readouterr().err
    assert _field_labels(nested_restore_err) == _error_field_labels()
    assert "error code: CONTEXT_CONFLICT" in nested_restore_err
    assert "target path nests inside another ALab context" in nested_restore_err
    assert not nested_restore.exists()
    assert _audit_count(home, "restore", "worktree", exp_id) == 0
    active_restore = tmp_path / "active-restore"
    assert run(["--home", str(home), "--key", admin_key, "exp", "worktree", "restore", exp_id, "--project", project_id, "--path", str(active_restore)]) == 4
    active_restore_err = capsys.readouterr().err
    assert _field_labels(active_restore_err) == _error_field_labels()
    assert "error code: RESOURCE_BUSY" in active_restore_err
    assert "experiment already has an active worktree" in active_restore_err
    assert not active_restore.exists()
    assert _audit_count(home, "restore", "worktree", exp_id) == 0
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "exp", "worktree", "remove", exp_id, "--project", project_id, "--dry-run", "--dry-run"], "--dry-run", capsys)
    assert _audit_count(home, "remove", "worktree", exp_id) == 0
    _assert_confirm_guard(
        ["--home", str(home), "--key", admin_key, "exp", "worktree", "remove", exp_id, "--project", project_id],
        exp_id,
        "exp worktree remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "exp", "worktree", "remove", exp_id, "--project", project_id, "--force", "--confirm", exp_id]) == 0
    worktree_remove_out = capsys.readouterr().out
    assert _field_labels(worktree_remove_out) == _worktree_remove_field_labels(dry_run=False)
    assert "worktree state: removed" in worktree_remove_out

    nonempty_restore = tmp_path / "nonempty-restore"
    nonempty_restore.mkdir()
    (nonempty_restore / "existing.txt").write_text("keep\n", encoding="utf-8")
    assert run(["--home", str(home), "--key", admin_key, "exp", "worktree", "restore", exp_id, "--project", project_id, "--path", str(nonempty_restore)]) == 2
    nonempty_restore_err = capsys.readouterr().err
    assert _field_labels(nonempty_restore_err) == _error_field_labels()
    assert "error code: OUTPUT_EXISTS" in nonempty_restore_err
    assert "restore path already exists" in nonempty_restore_err
    assert (nonempty_restore / "existing.txt").read_text(encoding="utf-8") == "keep\n"
    assert not (nonempty_restore / ".alab").exists()
    assert _audit_count(home, "restore", "worktree", exp_id) == 0
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT worktree_state FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()[0] == "removed"
        assert conn.execute("SELECT COUNT(*) FROM path_registry WHERE exp_id = ? AND context_type = 'experiment' AND status = 'active'", (exp_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM credentials WHERE exp_id = ? AND token_mode = 'worktree' AND status = 'active'", (exp_id,)).fetchone()[0] == 0

    restored = tmp_path / "restored"
    assert run(["--home", str(home), "--key", admin_key, "exp", "worktree", "restore", exp_id, "--project", project_id, "--path", str(restored)]) == 0
    restore_out = capsys.readouterr().out
    assert _field_labels(restore_out) == _worktree_restore_field_labels()
    assert "worktree state: active" in restore_out
    assert "new token id:" in restore_out
    restored_token_id = _field(restore_out, "new token id")

    with sqlite3.connect(home / "alab.db") as conn:
        before_duplicate_token_selector = {
            "credentials": conn.execute(
                "SELECT COUNT(*) FROM credentials WHERE exp_id = ? AND credential_type = 'token'",
                (exp_id,),
            ).fetchone()[0],
            "active_tokens": conn.execute(
                "SELECT COUNT(*) FROM credentials WHERE exp_id = ? AND credential_type = 'token' AND status = 'active'",
                (exp_id,),
            ).fetchone()[0],
            "restored_status": conn.execute(
                "SELECT status FROM credentials WHERE credential_id = ?",
                (restored_token_id,),
            ).fetchone()[0],
            "audits": conn.execute(
                "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0],
        }
    duplicate_token_selector_cases = [
        ["exp", "token", "list", exp_id, "--project", project_id, "--token-id", restored_token_id, "--token-id", restored_token_id],
        ["exp", "token", "revoke", exp_id, "--project", project_id, "--mode", "worktree", "--mode", "inspection"],
        ["exp", "token", "revoke", exp_id, "--project", project_id, "--all", "--all"],
        ["exp", "token", "regenerate", exp_id, "--project", project_id, "--mode", "worktree", "--mode", "inspection"],
    ]
    for token_selector_args in duplicate_token_selector_cases:
        assert run(["--home", str(home), "--key", admin_key, *token_selector_args]) == 2
        duplicate_token_selector_err = capsys.readouterr().err
        assert _field_labels(duplicate_token_selector_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_token_selector_err
        assert "may be provided once" in duplicate_token_selector_err
        with sqlite3.connect(home / "alab.db") as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM credentials WHERE exp_id = ? AND credential_type = 'token'",
                (exp_id,),
            ).fetchone()[0] == before_duplicate_token_selector["credentials"]
            assert conn.execute(
                "SELECT COUNT(*) FROM credentials WHERE exp_id = ? AND credential_type = 'token' AND status = 'active'",
                (exp_id,),
            ).fetchone()[0] == before_duplicate_token_selector["active_tokens"]
            assert conn.execute(
                "SELECT status FROM credentials WHERE credential_id = ?",
                (restored_token_id,),
            ).fetchone()[0] == before_duplicate_token_selector["restored_status"]
            assert conn.execute(
                "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0] == before_duplicate_token_selector["audits"]

    assert run(["--home", str(home), "--key", admin_key, "exp", "token", "regenerate", exp_id, "--project", project_id]) == 0
    regenerate_out = capsys.readouterr().out
    assert _field_labels(regenerate_out) == _credential_regenerate_field_labels()
    assert "token mode: worktree" in regenerate_out

    monkeypatch.chdir(restored)
    assert run(["--home", str(home), "annotations", "show", annotation_id]) == 0
    regenerated_show_out = capsys.readouterr().out
    assert _field_labels(regenerated_show_out) == _annotation_field_labels()
    assert "body:\n  second note" in regenerated_show_out
    assert run(["--home", str(home), "annotate", "edit", annotation_id, "--body", "regenerated token note"]) == 0
    regenerated_edit_out = capsys.readouterr().out
    assert _field_labels(regenerated_edit_out) == _annotation_edit_field_labels()
    assert "revision: 3" in regenerated_edit_out
    for command_name, object_id, object_type in [
        ("runs", run_id, "run"),
        ("artifacts", artifact_id, "artifact"),
        ("logs", stdout_log_id, "log"),
    ]:
        assert run(["--home", str(home), command_name, "archive", object_id]) == 0
        archive_out = capsys.readouterr().out
        assert _field_labels(archive_out) == _archive_field_labels(object_type)
        assert f"{object_type} id: {object_id}" in archive_out
        assert "previous archive status: active" in archive_out
        assert "archive status: archived" in archive_out
        assert _audit_count(home, "archive", object_type, object_id) == 1
        assert run(["--home", str(home), command_name, "unarchive", object_id]) == 0
        unarchive_out = capsys.readouterr().out
        assert _field_labels(unarchive_out) == _unarchive_field_labels(object_type)
        assert f"{object_type} id: {object_id}" in unarchive_out
        assert "previous archive status: archived" in unarchive_out
        assert "archive status: active" in unarchive_out
        assert _audit_count(home, "unarchive", object_type, object_id) == 1
    assert run(["--home", str(home), "annotate", "remove", annotation_id, "--dry-run"]) == 0
    active_annotation_remove_dry_run = capsys.readouterr().out
    assert _field_labels(active_annotation_remove_dry_run) == _annotation_remove_field_labels(dry_run=True, has_blocker=True)
    assert "blocker: target_not_archived" in active_annotation_remove_dry_run
    _assert_duplicate_option_error(["--home", str(home), "annotate", "remove", annotation_id, "--dry-run", "--dry-run"], "--dry-run", capsys)
    _assert_remove_dry_run_preserved(home, "annotation", annotation_id, "annotations", "annotation_id")
    _assert_not_archived_remove_blocked(
        ["--home", str(home), "annotate", "remove", annotation_id, "--force", "--confirm", annotation_id],
        home,
        "annotation",
        annotation_id,
        capsys,
    )
    assert run(["--home", str(home), "annotate", "archive", annotation_id]) == 0
    annotation_archive_out = capsys.readouterr().out
    assert _field_labels(annotation_archive_out) == _annotation_status_field_labels()
    assert "annotation status: archived" in annotation_archive_out
    assert _audit_count(home, "archive", "annotation", annotation_id) == 1
    assert run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-id", exp_id, "--query", "regenerated token note"]) == 0
    archived_hidden_annotations = capsys.readouterr().out
    assert _field_labels(archived_hidden_annotations) == []
    assert annotation_id not in archived_hidden_annotations
    assert run(["--home", str(home), "annotations", "list", "--target-type", "experiment", "--target-id", exp_id, "--query", "regenerated token note", "--include-archived"]) == 0
    archived_included_annotations = capsys.readouterr().out
    assert _field_labels(archived_included_annotations) == _annotation_field_labels()
    assert f"annotation id: {annotation_id}" in archived_included_annotations
    assert "status: archived" in archived_included_annotations
    assert run(["--home", str(home), "annotate", "archive", annotation_id]) == 0
    annotation_archive_repeat_out = capsys.readouterr().out
    assert _field_labels(annotation_archive_repeat_out) == _annotation_status_field_labels()
    assert "previous status: archived" in annotation_archive_repeat_out
    assert _field(annotation_archive_repeat_out, "archived at") == "none"
    assert _audit_count(home, "archive", "annotation", annotation_id) == 1
    assert run(["--home", str(home), "annotate", "unarchive", annotation_id]) == 0
    annotation_unarchive_out = capsys.readouterr().out
    assert _field_labels(annotation_unarchive_out) == _annotation_status_field_labels(unarchive=True)
    assert "annotation status: active" in annotation_unarchive_out
    assert _audit_count(home, "unarchive", "annotation", annotation_id) == 1
    assert run(["--home", str(home), "annotate", "unarchive", annotation_id]) == 0
    annotation_unarchive_repeat_out = capsys.readouterr().out
    assert _field_labels(annotation_unarchive_repeat_out) == _annotation_status_field_labels(unarchive=True)
    assert "previous status: active" in annotation_unarchive_repeat_out
    assert _field(annotation_unarchive_repeat_out, "unarchived at") == "none"
    assert _audit_count(home, "unarchive", "annotation", annotation_id) == 1
    assert run(["--home", str(home), "annotate", "archive", annotation_id]) == 0
    annotation_archive_again_out = capsys.readouterr().out
    assert _field_labels(annotation_archive_again_out) == _annotation_status_field_labels()
    assert _audit_count(home, "archive", "annotation", annotation_id) == 2
    assert run(["--home", str(home), "annotate", "remove", annotation_id, "--dry-run"]) == 0
    annotation_remove_dry_run = capsys.readouterr().out
    assert _field_labels(annotation_remove_dry_run) == _annotation_remove_field_labels(dry_run=True)
    assert "removed: false" in annotation_remove_dry_run
    assert "deleted revisions: 3" in annotation_remove_dry_run
    assert "deleted filesystem paths: 0" in annotation_remove_dry_run
    _assert_remove_dry_run_preserved(home, "annotation", annotation_id, "annotations", "annotation_id")
    _assert_confirm_guard(
        ["--home", str(home), "annotate", "remove", annotation_id, "--reason", "done"],
        annotation_id,
        "annotation remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "annotate", "remove", annotation_id, "--force", "--confirm", annotation_id, "--reason", "done"]) == 0
    annotation_remove_out = capsys.readouterr().out
    assert _field_labels(annotation_remove_out) == _annotation_remove_field_labels(dry_run=False)
    annotation_audit_id = _field(annotation_remove_out, "audit id")
    assert "removed: true" in annotation_remove_out
    assert "deleted revisions: 3" in annotation_remove_out
    assert "deleted filesystem paths: 0" in annotation_remove_out
    assert "trash cleanup pending: false" in annotation_remove_out
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM annotations WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM annotation_revisions WHERE annotation_id = ?", (annotation_id,)).fetchone()[0] == 0
        annotation_metadata = json.loads(conn.execute("SELECT metadata_json FROM audit_events WHERE audit_id = ?", (annotation_audit_id,)).fetchone()[0])
    assert annotation_metadata["deleted_revision_count"] == 3
    assert annotation_metadata["filesystem_target_count"] == 0
    assert annotation_metadata["trash"] == []


def test_context_self_repair_requires_registered_branch(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("repair")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Self Repair Project"
task = "Repair moved worktree"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_id = _field(capsys.readouterr().out, "project id")

    worktree = tmp_path / "repair-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "repair", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    repo_git = home / "projects" / project_id / "repo.git"
    with sqlite3.connect(home / "alab.db") as conn:
        branch_name = conn.execute("SELECT branch_name FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()[0]
        old_registry_path, old_registry_hash = conn.execute(
            "SELECT path, path_hash FROM path_registry WHERE exp_id = ? AND context_type = 'experiment' AND status = 'active'",
            (exp_id,),
        ).fetchone()

    duplicate = tmp_path / "repair-exp-duplicate"
    shutil.copytree(worktree, duplicate)
    assert run(["--home", str(home), "context", "repair", "--path", str(duplicate)]) == 4
    old_path_exists_err = capsys.readouterr().err
    assert _field_labels(old_path_exists_err) == _error_field_labels()
    assert "error code: CONTEXT_CONFLICT" in old_path_exists_err
    assert "registered path still exists" in old_path_exists_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert (
            conn.execute(
                "SELECT path, path_hash FROM path_registry WHERE exp_id = ? AND context_type = 'experiment' AND status = 'active'",
                (exp_id,),
            ).fetchone()
            == (old_registry_path, old_registry_hash)
        )
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE object_type = 'worktree' AND object_id = ? AND action = 'repair'", (exp_id,)).fetchone()[0] == 0

    moved = tmp_path / "repair-exp-moved"
    subprocess.run(["git", f"--git-dir={repo_git}", "worktree", "move", str(worktree), str(moved)], capture_output=True, check=True)
    assert not worktree.exists()
    assert moved.exists()
    _git(["checkout", "--detach"], moved)

    monkeypatch.setenv("ALAB_KEY", root_key)
    assert run(["--home", str(home), "context", "repair", "--path", str(moved)]) == 4
    repair_err = capsys.readouterr().err
    assert "self-repair requires the registered experiment branch" in repair_err
    monkeypatch.delenv("ALAB_KEY")

    _git(["checkout", branch_name], moved)
    assert run(["--home", str(home), "context", "repair", "--path", str(moved)]) == 0
    repair_out = capsys.readouterr().out
    assert _field_labels(repair_out) == _context_repair_field_labels()
    assert "repair mode: self-token" in repair_out
    assert "status: repaired" in repair_out
    with sqlite3.connect(home / "alab.db") as conn:
        repaired = conn.execute("SELECT path, path_hash FROM path_registry WHERE exp_id = ? AND context_type = 'experiment' AND status = 'active'", (exp_id,)).fetchone()
        audits = conn.execute("SELECT COUNT(*) FROM audit_events WHERE object_type = 'worktree' AND object_id = ? AND action = 'repair'", (exp_id,)).fetchone()[0]
    assert old_registry_path == str(worktree)
    assert repaired[0] == str(moved)
    assert repaired[1] != ""
    assert audits == 1

    baseline_commit = _git(["rev-parse", "HEAD"], moved)
    (moved / "main.py").write_text('print("inspection repair")\n', encoding="utf-8")
    _git(["add", "main.py"], moved)
    _git(["config", "user.name", "ALab Test"], moved)
    _git(["config", "user.email", "alab@example.test"], moved)
    _git(["config", "commit.gpgsign", "false"], moved)
    _git(["commit", "-m", "inspection repair"], moved)
    pinned_commit = _git(["rev-parse", "HEAD"], moved)

    inspect = tmp_path / "repair-inspect"
    assert run(["--home", str(home), "--key", root_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(inspect), "--commit", pinned_commit]) == 0
    inspect_out = capsys.readouterr().out
    inspection_token_id = _field(inspect_out, "token id")
    inspection_path_hash_before = ""
    with sqlite3.connect(home / "alab.db") as conn:
        inspection_path_hash_before = conn.execute(
            "SELECT path_hash FROM path_registry WHERE token_id = ? AND context_type = 'inspection' AND status = 'active'",
            (inspection_token_id,),
        ).fetchone()[0]

    moved_inspect = tmp_path / "repair-inspect-moved"
    subprocess.run(["git", f"--git-dir={repo_git}", "worktree", "move", str(inspect), str(moved_inspect)], capture_output=True, check=True)
    assert not inspect.exists()
    assert moved_inspect.exists()
    _git(["checkout", baseline_commit], moved_inspect)

    assert run(["--home", str(home), "context", "repair", "--path", str(moved_inspect)]) == 4
    pinned_repair_err = capsys.readouterr().err
    assert _field_labels(pinned_repair_err) == _error_field_labels()
    assert "error code: CONTEXT_CONFLICT" in pinned_repair_err
    assert "self-repair requires the pinned inspection commit" in pinned_repair_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert (
            conn.execute(
                "SELECT path, path_hash FROM path_registry WHERE token_id = ? AND context_type = 'inspection' AND status = 'active'",
                (inspection_token_id,),
            ).fetchone()
            == (str(inspect), inspection_path_hash_before)
        )
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE object_type = 'inspection_checkout' AND object_id = ? AND action = 'repair'", (inspection_token_id,)).fetchone()[0] == 0

    _git(["checkout", pinned_commit], moved_inspect)
    assert run(["--home", str(home), "context", "repair", "--path", str(moved_inspect)]) == 0
    inspection_repair_out = capsys.readouterr().out
    assert _field_labels(inspection_repair_out) == _context_repair_field_labels()
    assert "repair mode: self-token" in inspection_repair_out
    assert "status: repaired" in inspection_repair_out
    with sqlite3.connect(home / "alab.db") as conn:
        inspection_repaired = conn.execute(
            "SELECT path, path_hash FROM path_registry WHERE token_id = ? AND context_type = 'inspection' AND status = 'active'",
            (inspection_token_id,),
        ).fetchone()
        inspection_repair_audit = conn.execute(
            """
            SELECT actor_credential_id, actor_type, action, object_type, object_id,
              project_id, exp_id, cascade, reason, metadata_json
            FROM audit_events
            WHERE object_type = 'inspection_checkout' AND object_id = ? AND action = 'repair'
            """,
            (inspection_token_id,),
        ).fetchone()
    assert inspection_repaired[0] == str(moved_inspect)
    assert inspection_repaired[1] != inspection_path_hash_before
    assert inspection_repair_audit[:9] == (inspection_token_id, "token", "repair", "inspection_checkout", inspection_token_id, project_id, exp_id, 0, None)
    inspection_repair_metadata = json.loads(inspection_repair_audit[9])
    assert inspection_repair_metadata == {
        "context_type": "inspection",
        "created_registry_row": False,
        "path_registry_id": inspection_repair_metadata["path_registry_id"],
        "previous_path_hash": inspection_path_hash_before,
        "repair_mode": "self-token",
        "repaired_at": inspection_repair_metadata["repaired_at"],
        "repaired_path_hash": inspection_repaired[1],
        "schema_version": 1,
    }


def test_worktree_remove_stages_trash_and_records_metadata(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("trash")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Trash Worktree Project"
task = "Remove worktree safely"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    worktree = tmp_path / "trash-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "trash", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    (worktree / "scratch.txt").write_text("dirty\n", encoding="utf-8")

    assert run(["--home", str(home), "--key", admin_key, "exp", "worktree", "remove", exp_id, "--project", project_id, "--dry-run"]) == 0
    dry_run_out = capsys.readouterr().out
    assert _field_labels(dry_run_out) == _worktree_remove_field_labels(dry_run=True)
    assert "path exists: true" in dry_run_out
    assert "dirty state: dirty" in dry_run_out
    assert "planned trash move:" in dry_run_out
    assert worktree.exists()
    assert _audit_count(home, "remove", "worktree", exp_id) == 0
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT worktree_state FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()[0] == "active"
        assert conn.execute("SELECT status FROM path_registry WHERE exp_id = ? AND context_type = 'experiment'", (exp_id,)).fetchone()[0] == "active"
        assert conn.execute("SELECT status FROM credentials WHERE exp_id = ? AND token_mode = 'worktree'", (exp_id,)).fetchone()[0] == "active"

    assert run(["--home", str(home), "--key", admin_key, "exp", "worktree", "remove", exp_id, "--project", project_id, "--force", "--confirm", exp_id]) == 0
    remove_out = capsys.readouterr().out
    assert _field_labels(remove_out) == _worktree_remove_field_labels(dry_run=False)
    audit_id = _field(remove_out, "audit id")
    assert "path existed: true" in remove_out
    assert "trash cleanup pending: false" in remove_out
    assert not worktree.exists()

    with sqlite3.connect(home / "alab.db") as conn:
        exp_row = conn.execute("SELECT worktree_state, worktree_path FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()
        path_status = conn.execute("SELECT status FROM path_registry WHERE exp_id = ? AND context_type = 'experiment'", (exp_id,)).fetchone()[0]
        token_status = conn.execute("SELECT status FROM credentials WHERE exp_id = ? AND token_mode = 'worktree'", (exp_id,)).fetchone()[0]
        metadata = json.loads(conn.execute("SELECT metadata_json FROM audit_events WHERE audit_id = ?", (audit_id,)).fetchone()[0])
        trash_rows = conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0]
    assert exp_row == ("removed", None)
    assert path_status == "removed"
    assert token_status == "revoked"
    assert metadata["filesystem_path_already_absent"] is False
    assert metadata["dirty_state"] == "dirty"
    assert metadata["trash"]["mode"] == "home"
    assert metadata["trash"]["label"].startswith(f"tmp/trash/{audit_id}/")
    assert trash_rows == 0


def test_worktree_remove_uses_same_parent_trash_fallback_on_cross_device_rename(tmp_path, monkeypatch, capsys) -> None:
    home, project_id, admin_key = _init_trash_restore_project(tmp_path, capsys)
    worktree = tmp_path / "same-parent-trash-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "same-parent-trash", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    (worktree / "scratch.txt").write_text("same-parent fallback\n", encoding="utf-8")
    original_rename = Path.rename
    home_trash_root = home / "tmp" / "trash"

    def rename_with_exdev(self: Path, target: Path | str) -> Path:
        target_path = Path(target)
        if self == worktree and home_trash_root in target_path.parents:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", rename_with_exdev)

    assert run(["--home", str(home), "--key", admin_key, "exp", "worktree", "remove", exp_id, "--project", project_id, "--force", "--confirm", exp_id]) == 0
    remove_out = capsys.readouterr().out
    audit_id = _field(remove_out, "audit id")

    assert _field_labels(remove_out) == _worktree_remove_field_labels(dry_run=False)
    assert _field(remove_out, "trash path") == f".alab-trash-{audit_id}"
    assert "trash cleanup pending: false" in remove_out
    assert not worktree.exists()
    assert not (home_trash_root / audit_id).exists()
    assert not any(path.name.startswith(".alab-trash-") for path in tmp_path.iterdir())
    with sqlite3.connect(home / "alab.db") as conn:
        metadata = json.loads(conn.execute("SELECT metadata_json FROM audit_events WHERE audit_id = ?", (audit_id,)).fetchone()[0])
        trash_rows = conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0]
        exp_row = conn.execute("SELECT worktree_state, worktree_path FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()
    assert metadata["trash"]["mode"] == "same_parent"
    assert metadata["trash"]["label"] == f".alab-trash-{audit_id}"
    assert metadata["trash"]["original_path_hash"]
    assert trash_rows == 0
    assert exp_row == ("removed", None)


def test_checkout_remove_reconciles_missing_path(tmp_path, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text('print("inspect")\n', encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Missing Checkout Project"
task = "Reconcile missing inspection checkout"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    worktree = tmp_path / "main-exp"
    inspect = tmp_path / "inspect-missing"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "main", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(inspect), "--commit", "latest"]) == 0
    token_id = _field(capsys.readouterr().out, "token id")

    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", "remove", "--project", project_id, "--token-id", token_id, "--dry-run"]) == 0
    dry_run_out = capsys.readouterr().out
    assert _field_labels(dry_run_out) == _inspection_checkout_remove_field_labels(dry_run=True)
    assert "path exists: true" in dry_run_out
    assert "planned trash move:" in dry_run_out
    assert inspect.exists()
    assert _audit_count(home, "remove", "inspection_checkout", token_id) == 0
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM path_registry WHERE token_id = ?", (token_id,)).fetchone()[0] == "active"
        assert conn.execute("SELECT status FROM credentials WHERE credential_id = ?", (token_id,)).fetchone()[0] == "active"
    shutil.rmtree(inspect)

    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", "remove", "--project", project_id, "--token-id", token_id, "--force", "--confirm", token_id]) == 0
    remove_out = capsys.readouterr().out
    assert _field_labels(remove_out) == _inspection_checkout_remove_field_labels(dry_run=False)
    audit_id = _field(remove_out, "audit id")
    assert "path existed: false" in remove_out
    assert "token revoked: true" in remove_out

    with sqlite3.connect(home / "alab.db") as conn:
        path_status = conn.execute("SELECT status FROM path_registry WHERE token_id = ?", (token_id,)).fetchone()[0]
        token_status = conn.execute("SELECT status FROM credentials WHERE credential_id = ?", (token_id,)).fetchone()[0]
        metadata = json.loads(conn.execute("SELECT metadata_json FROM audit_events WHERE audit_id = ?", (audit_id,)).fetchone()[0])
    assert path_status == "removed"
    assert token_status == "revoked"
    assert metadata["filesystem_path_already_absent"] is True
    assert metadata["trash"]["mode"] == "none"


def test_experiment_remove_cascades_filesystem_paths(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

print("cascade remove")
Path(os.environ["ALAB_RUN_DIR"], "artifact.txt").write_text(os.environ.get("ALAB_EXP_ID", "validation"), encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Cascade Remove Project"
task = "Remove experiment filesystem paths"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    worktree = tmp_path / "cascade-exp"
    inspect = tmp_path / "cascade-inspect"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "cascade", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "capture"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(inspect), "--commit", "latest"]) == 0
    inspection_token_id = _field(capsys.readouterr().out, "token id")

    artifact_store = home / "projects" / project_id / "artifacts"
    repo_git = home / "projects" / project_id / "repo.git"
    with sqlite3.connect(home / "alab.db") as conn:
        admin_credential_id = conn.execute(
            "SELECT credential_id FROM credentials WHERE project_id = ? AND credential_type = 'admin' AND status = 'active'",
            (project_id,),
        ).fetchone()[0]
        branch_name = conn.execute("SELECT branch_name FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()[0]
        log_rel = conn.execute("SELECT file_path FROM log_streams WHERE exp_id = ? AND stream = 'stdout'", (exp_id,)).fetchone()[0]
        blob_rel = conn.execute("SELECT blob_path FROM artifacts WHERE exp_id = ? AND blob_path IS NOT NULL", (exp_id,)).fetchone()[0]
        active_path_token_ids = {
            row[0]
            for row in conn.execute(
                "SELECT token_id FROM path_registry WHERE exp_id = ? AND status = 'active' ORDER BY context_type",
                (exp_id,),
            ).fetchall()
            if row[0]
        }
    log_path = artifact_store / log_rel
    blob_path = artifact_store / blob_rel
    branch_ref = f"refs/heads/{branch_name}"
    assert subprocess.run(["git", f"--git-dir={repo_git}", "show-ref", "--verify", branch_ref], capture_output=True, check=False).returncode == 0
    assert log_path.exists()
    assert blob_path.exists()

    assert run(["--home", str(home), "--key", admin_key, "exp", "remove", exp_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    active_exp_remove_dry_run = capsys.readouterr().out
    assert _field_labels(active_exp_remove_dry_run) == _experiment_remove_field_labels(dry_run=True, has_blocker=True, filesystem_path_count=5)
    assert "blocker: target_not_archived" in active_exp_remove_dry_run
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "exp", "remove", exp_id, "--project", project_id, "--dry-run", "--dry-run", "--cascade"], "--dry-run", capsys)
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "exp", "remove", exp_id, "--project", project_id, "--dry-run", "--cascade", "--cascade"], "--cascade", capsys)
    _assert_remove_dry_run_preserved(home, "experiment", exp_id, "experiments", "exp_id")
    _assert_not_archived_remove_blocked(
        ["--home", str(home), "--key", admin_key, "exp", "remove", exp_id, "--project", project_id, "--force", "--confirm", exp_id, "--cascade"],
        home,
        "experiment",
        exp_id,
        capsys,
    )
    for removed_flag in ("--remove-worktree", "--force-remove-worktree"):
        assert run(["--home", str(home), "--key", admin_key, "exp", "archive", exp_id, "--project", project_id, removed_flag]) == 2
        removed_flag_err = capsys.readouterr().err
        assert _field_labels(removed_flag_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in removed_flag_err
        assert f"{removed_flag} was removed from exp archive" in removed_flag_err
        assert "use exp worktree remove explicitly" in removed_flag_err
        assert _audit_count(home, "archive", "experiment", exp_id) == 0
        assert _row_count(home, "experiments", "exp_id", exp_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "exp", "archive", exp_id, "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_exp_archive_err = capsys.readouterr().err
    assert _field_labels(unsupported_exp_archive_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_exp_archive_err
    assert "unsupported option --reason" in unsupported_exp_archive_err
    assert _audit_count(home, "archive", "experiment", exp_id) == 0
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()[0] == "open"
    _insert_active_lock(home, "lock-exp-archive", project_id, exp_id)
    assert run(["--home", str(home), "--key", admin_key, "exp", "archive", exp_id, "--project", project_id]) == 4
    exp_archive_lock_err = capsys.readouterr().err
    assert _field_labels(exp_archive_lock_err) == _error_field_labels()
    assert "error code: RESOURCE_BUSY" in exp_archive_lock_err
    assert "experiment has active locks" in exp_archive_lock_err
    assert _audit_count(home, "archive", "experiment", exp_id) == 0
    assert _row_count(home, "experiments", "exp_id", exp_id) == 1
    _delete_lock(home, "lock-exp-archive")
    assert run(["--home", str(home), "--key", admin_key, "exp", "archive", exp_id, "--project", project_id]) == 0
    exp_archive_out = capsys.readouterr().out
    assert _field_labels(exp_archive_out) == _experiment_status_field_labels()
    exp_archived_at = _field(exp_archive_out, "archived at")
    assert _audit_count(home, "archive", "experiment", exp_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "exp", "archive", exp_id, "--project", project_id]) == 0
    exp_archive_repeat_out = capsys.readouterr().out
    assert _field_labels(exp_archive_repeat_out) == _experiment_status_field_labels()
    assert "previous status: archived" in exp_archive_repeat_out
    assert _field(exp_archive_repeat_out, "archived at") == exp_archived_at
    assert _audit_count(home, "archive", "experiment", exp_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "exp", "unarchive", exp_id, "--project", project_id]) == 0
    exp_unarchive_out = capsys.readouterr().out
    assert _field_labels(exp_unarchive_out) == _experiment_status_field_labels(unarchive=True)
    assert "experiment status: open" in exp_unarchive_out
    assert _audit_count(home, "unarchive", "experiment", exp_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "exp", "unarchive", exp_id, "--project", project_id]) == 0
    exp_unarchive_repeat_out = capsys.readouterr().out
    assert _field_labels(exp_unarchive_repeat_out) == _experiment_status_field_labels(unarchive=True)
    assert "previous status: open" in exp_unarchive_repeat_out
    assert _field(exp_unarchive_repeat_out, "unarchived at") == "none"
    assert _audit_count(home, "unarchive", "experiment", exp_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "exp", "archive", exp_id, "--project", project_id]) == 0
    exp_archive_again_out = capsys.readouterr().out
    assert _field_labels(exp_archive_again_out) == _experiment_status_field_labels()
    assert _audit_count(home, "archive", "experiment", exp_id) == 2
    assert run(["--home", str(home), "--key", admin_key, "exp", "remove", exp_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    dry_run_out = capsys.readouterr().out
    assert _field_labels(dry_run_out) == _experiment_remove_field_labels(dry_run=True, filesystem_path_count=5)
    assert "deleted filesystem paths: 5" in dry_run_out
    assert f"branch ref: {branch_ref}" in dry_run_out
    assert "branch ref exists: true" in dry_run_out
    assert "planned trash move:" in dry_run_out
    _assert_remove_dry_run_preserved(home, "experiment", exp_id, "experiments", "exp_id")
    assert worktree.exists()
    assert inspect.exists()
    assert log_path.exists()
    assert blob_path.exists()

    _insert_active_lock(home, "lock-exp-remove", project_id, exp_id)
    _assert_remove_resource_busy(
        ["--home", str(home), "--key", admin_key, "exp", "remove", exp_id, "--project", project_id, "--force", "--confirm", exp_id, "--cascade"],
        home,
        "experiment",
        exp_id,
        "experiment_has_active_lock",
        capsys,
    )
    assert worktree.exists()
    assert inspect.exists()
    assert log_path.exists()
    assert blob_path.exists()
    assert subprocess.run(["git", f"--git-dir={repo_git}", "show-ref", "--verify", branch_ref], capture_output=True, check=False).returncode == 0
    _delete_lock(home, "lock-exp-remove")

    _assert_confirm_guard(
        ["--home", str(home), "--key", admin_key, "exp", "remove", exp_id, "--project", project_id, "--cascade"],
        exp_id,
        "experiment remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "exp", "remove", exp_id, "--project", project_id, "--force", "--confirm", exp_id, "--cascade"]) == 0
    remove_out = capsys.readouterr().out
    assert _field_labels(remove_out) == _experiment_remove_field_labels(dry_run=False)
    audit_id = _field(remove_out, "audit id")
    assert "removed: true" in remove_out
    assert "deleted filesystem paths: 5" in remove_out
    assert "deleted branch ref: true" in remove_out
    assert "trash cleanup pending: false" in remove_out
    assert not worktree.exists()
    assert not inspect.exists()
    assert not log_path.exists()
    assert not blob_path.exists()
    assert subprocess.run(["git", f"--git-dir={repo_git}", "show-ref", "--verify", branch_ref], capture_output=True, check=False).returncode != 0

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM log_streams WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE exp_id = ?", (exp_id,)).fetchone()[0] == 0
        path_rows = conn.execute(
            """
            SELECT context_type, token_id, status, removed_at, removed_by_credential_id
            FROM path_registry
            WHERE exp_id = ?
            ORDER BY context_type
            """,
            (exp_id,),
        ).fetchall()
        credential_rows = conn.execute(
            "SELECT credential_id, status, revoked_at FROM credentials WHERE exp_id = ? ORDER BY credential_id",
            (exp_id,),
        ).fetchall()
        audit_row = conn.execute(
            "SELECT actor_credential_id, object_type, object_id, cascade FROM audit_events WHERE audit_id = ?",
            (audit_id,),
        ).fetchone()
        metadata = json.loads(conn.execute("SELECT metadata_json FROM audit_events WHERE audit_id = ?", (audit_id,)).fetchone()[0])
        trash_rows = conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0]
    assert audit_row == (admin_credential_id, "experiment", exp_id, 1)
    assert [row[0] for row in path_rows] == ["experiment", "inspection"]
    assert {row[1] for row in path_rows if row[1]} == active_path_token_ids
    assert all(row[2] == "removed" and row[3] is not None and row[4] == admin_credential_id for row in path_rows)
    assert {row[0] for row in credential_rows} == active_path_token_ids
    assert all(row[1] == "revoked" and row[2] is not None for row in credential_rows)
    assert metadata["filesystem_target_count"] == 5
    assert metadata["filesystem_absent_count"] == 0
    assert metadata["branch_ref"] == branch_ref
    assert metadata["branch_ref_deleted"] is True
    assert metadata["branch_ref_already_absent"] is False
    assert {entry["kind"] for entry in metadata["trash"]} == {"artifact", "experiment", "inspection", "log"}
    assert inspection_token_id in {entry["object_id"] for entry in metadata["trash"]}
    assert trash_rows == 0


def test_project_remove_cascades_whole_tree_through_trash(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

print("project cascade")
Path(os.environ["ALAB_RUN_DIR"], "artifact.txt").write_text("project cascade", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Whole Project Remove"
task = "Remove whole project safely"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    project_root = home / "projects" / project_id
    assert run(["--home", str(home), "--key", root_key, "project", "list"]) == 0
    project_list_out = capsys.readouterr().out
    assert _field_labels(project_list_out) == _project_list_field_labels()
    assert f"project id: {project_id}" in project_list_out
    assert run(["--home", str(home), "--key", root_key, "project", "list", "--reason", "ignored"]) == 2
    unsupported_project_list_err = capsys.readouterr().err
    assert _field_labels(unsupported_project_list_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_project_list_err
    assert "unsupported option --reason" in unsupported_project_list_err
    for command_args, message in [
        (["project", "list", "extra"], "project list accepts no positional arguments"),
        (["project", "show", "extra", "--project", project_id], "project show accepts no positional arguments"),
        (["status", "extra", "--project", project_id], "status accepts no positional arguments"),
    ]:
        assert run(["--home", str(home), "--key", root_key, *command_args]) == 2
        no_pos_err = capsys.readouterr().err
        assert _field_labels(no_pos_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in no_pos_err
        assert message in no_pos_err
    with sqlite3.connect(home / "alab.db") as conn:
        control_path = Path(conn.execute("SELECT control_path FROM projects WHERE project_id = ?", (project_id,)).fetchone()[0])

    worktree = tmp_path / "whole-exp"
    inspect = tmp_path / "whole-inspect"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "whole", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "project remove"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", exp_id, "--project", project_id, "--path", str(inspect), "--commit", "latest"]) == 0
    capsys.readouterr()
    assert project_root.exists()
    assert control_path.exists()
    assert worktree.exists()
    assert inspect.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        root_credential_id = conn.execute("SELECT credential_id FROM credentials WHERE credential_type = 'root' AND status = 'active'").fetchone()[0]

    assert run(["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--dry-run"]) == 2
    project_remove_cascade_err = capsys.readouterr().err
    assert _field_labels(project_remove_cascade_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in project_remove_cascade_err
    assert "project remove requires --cascade" in project_remove_cascade_err
    project_remove_audits_before_extra = _audit_count(home, "remove", "project", project_id)
    assert run(["--home", str(home), "--key", root_key, "project", "remove", "extra", "--project", project_id, "--dry-run", "--cascade"]) == 2
    extra_project_remove_err = capsys.readouterr().err
    assert _field_labels(extra_project_remove_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_project_remove_err
    assert "project remove accepts no positional arguments" in extra_project_remove_err
    assert _row_count(home, "projects", "project_id", project_id) == 1
    assert project_root.exists()
    assert control_path.exists()
    assert worktree.exists()
    assert inspect.exists()
    assert _audit_count(home, "remove", "project", project_id) == project_remove_audits_before_extra
    assert run(["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--dry-run", "--cascade"]) == 0
    active_project_remove_dry_run = capsys.readouterr().out
    assert _field_labels(active_project_remove_dry_run) == _project_remove_field_labels(dry_run=True, has_blocker=True, filesystem_path_count=4)
    assert "blocker: target_not_archived" in active_project_remove_dry_run
    _assert_remove_dry_run_preserved(home, "project", project_id, "projects", "project_id")
    _assert_not_archived_remove_blocked(
        ["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--force", "--confirm", project_id, "--cascade"],
        home,
        "project",
        project_id,
        capsys,
    )
    _insert_active_lock(home, "lock-project-archive", project_id)
    assert run(["--home", str(home), "--key", admin_key, "project", "archive", "--project", project_id]) == 4
    project_archive_lock_err = capsys.readouterr().err
    assert _field_labels(project_archive_lock_err) == _error_field_labels()
    assert "error code: RESOURCE_BUSY" in project_archive_lock_err
    assert "project has active locks" in project_archive_lock_err
    assert _audit_count(home, "archive", "project", project_id) == 0
    assert _row_count(home, "projects", "project_id", project_id) == 1
    _delete_lock(home, "lock-project-archive")
    assert run(["--home", str(home), "--key", admin_key, "project", "archive", "extra", "--project", project_id]) == 2
    extra_project_archive_err = capsys.readouterr().err
    assert _field_labels(extra_project_archive_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_project_archive_err
    assert "project archive accepts no positional arguments" in extra_project_archive_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM projects WHERE project_id = ?", (project_id,)).fetchone()[0] == "valid"
    assert _audit_count(home, "archive", "project", project_id) == 0
    assert run(["--home", str(home), "--key", admin_key, "project", "archive", "--project", project_id, "--reason", "ignored"]) == 2
    unsupported_project_archive_err = capsys.readouterr().err
    assert _field_labels(unsupported_project_archive_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in unsupported_project_archive_err
    assert "unsupported option --reason" in unsupported_project_archive_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM projects WHERE project_id = ?", (project_id,)).fetchone()[0] == "valid"
    assert _audit_count(home, "archive", "project", project_id) == 0
    assert run(["--home", str(home), "--key", admin_key, "project", "archive", "--project", project_id]) == 0
    project_archive_out = capsys.readouterr().out
    assert _field_labels(project_archive_out) == _project_status_field_labels()
    project_archived_at = _field(project_archive_out, "archived at")
    assert _audit_count(home, "archive", "project", project_id) == 1
    assert run(["--home", str(home), "--key", root_key, "project", "list"]) == 0
    archived_hidden_projects = capsys.readouterr().out
    assert _field_labels(archived_hidden_projects) == []
    assert project_id not in archived_hidden_projects
    assert run(["--home", str(home), "--key", root_key, "project", "list", "--include-archived"]) == 0
    archived_included_projects = capsys.readouterr().out
    assert _field_labels(archived_included_projects) == _project_list_field_labels()
    assert f"project id: {project_id}" in archived_included_projects
    assert "project status: archived" in archived_included_projects
    assert run(["--home", str(home), "--key", admin_key, "project", "archive", "--project", project_id]) == 0
    project_archive_repeat_out = capsys.readouterr().out
    assert _field_labels(project_archive_repeat_out) == _project_status_field_labels()
    assert "previous status: archived" in project_archive_repeat_out
    assert _field(project_archive_repeat_out, "archived at") == project_archived_at
    assert _audit_count(home, "archive", "project", project_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "project", "unarchive", "extra", "--project", project_id]) == 2
    extra_project_unarchive_err = capsys.readouterr().err
    assert _field_labels(extra_project_unarchive_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_project_unarchive_err
    assert "project unarchive accepts no positional arguments" in extra_project_unarchive_err
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT status FROM projects WHERE project_id = ?", (project_id,)).fetchone()[0] == "archived"
    assert _audit_count(home, "unarchive", "project", project_id) == 0
    assert run(["--home", str(home), "--key", admin_key, "project", "unarchive", "--project", project_id]) == 0
    project_unarchive_out = capsys.readouterr().out
    assert _field_labels(project_unarchive_out) == _project_status_field_labels(unarchive=True)
    assert "project status: valid" in project_unarchive_out
    assert _audit_count(home, "unarchive", "project", project_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "project", "unarchive", "--project", project_id]) == 0
    project_unarchive_repeat_out = capsys.readouterr().out
    assert _field_labels(project_unarchive_repeat_out) == _project_status_field_labels(unarchive=True)
    assert "previous status: valid" in project_unarchive_repeat_out
    assert _field(project_unarchive_repeat_out, "unarchived at") == "none"
    assert _audit_count(home, "unarchive", "project", project_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "project", "archive", "--project", project_id]) == 0
    project_archive_again_out = capsys.readouterr().out
    assert _field_labels(project_archive_again_out) == _project_status_field_labels()
    assert _audit_count(home, "archive", "project", project_id) == 2
    assert run(["--home", str(home), "--key", admin_key, "exp", "create", "--project", project_id, "--name", "blocked-archived-project", "--path", str(tmp_path / "blocked-archived-project")]) == 4
    exp_create_archived_err = capsys.readouterr().err
    assert _field_labels(exp_create_archived_err) == _error_field_labels()
    assert "error code: PROJECT_ARCHIVED" in exp_create_archived_err
    assert run(["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--dry-run", "--cascade"]) == 0
    dry_run_out = capsys.readouterr().out
    assert _field_labels(dry_run_out) == _project_remove_field_labels(dry_run=True, filesystem_path_count=4)
    assert "deleted experiments: 1" in dry_run_out
    assert "deleted runs: 1" in dry_run_out
    assert "deleted filesystem paths: 4" in dry_run_out
    assert "planned trash move:" in dry_run_out
    _assert_remove_dry_run_preserved(home, "project", project_id, "projects", "project_id")
    assert project_root.exists()
    assert control_path.exists()
    assert worktree.exists()
    assert inspect.exists()

    _insert_active_lock(home, "lock-project-remove", project_id)
    _assert_remove_resource_busy(
        ["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--force", "--confirm", project_id, "--cascade"],
        home,
        "project",
        project_id,
        "project_has_active_lock",
        capsys,
    )
    assert project_root.exists()
    assert control_path.exists()
    assert worktree.exists()
    assert inspect.exists()
    _delete_lock(home, "lock-project-remove")

    _assert_confirm_guard(
        ["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--cascade"],
        project_id,
        "project remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "--key", root_key, "project", "remove", "--project", project_id, "--force", "--confirm", project_id, "--cascade"]) == 0
    remove_out = capsys.readouterr().out
    assert _field_labels(remove_out) == _project_remove_field_labels(dry_run=False)
    audit_id = _field(remove_out, "audit id")
    assert "removed: true" in remove_out
    assert "deleted filesystem paths: 4" in remove_out
    assert "trash cleanup pending: false" in remove_out
    assert not project_root.exists()
    assert not control_path.exists()
    assert not worktree.exists()
    assert not inspect.exists()

    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects WHERE project_id = ?", (project_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM experiments WHERE project_id = ?", (project_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE project_id = ?", (project_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM log_streams WHERE project_id = ?", (project_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE project_id = ?", (project_id,)).fetchone()[0] == 0
        path_rows = conn.execute(
            """
            SELECT context_type, token_id, status, removed_at, removed_by_credential_id
            FROM path_registry
            WHERE project_id = ?
            ORDER BY context_type
            """,
            (project_id,),
        ).fetchall()
        credential_rows = conn.execute(
            "SELECT credential_id, credential_type, status, revoked_at FROM credentials WHERE project_id = ? ORDER BY credential_id",
            (project_id,),
        ).fetchall()
        audit_row = conn.execute(
            "SELECT actor_credential_id, object_type, object_id, cascade FROM audit_events WHERE audit_id = ?",
            (audit_id,),
        ).fetchone()
        metadata = json.loads(conn.execute("SELECT metadata_json FROM audit_events WHERE audit_id = ?", (audit_id,)).fetchone()[0])
        trash_rows = conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0]
    assert {row[0] for row in path_rows} == {"experiment", "inspection", "project"}
    assert audit_row == (root_credential_id, "project", project_id, 1)
    assert all(row[2] == "removed" and row[3] is not None and row[4] == root_credential_id for row in path_rows)
    retained_path_token_ids = {row[1] for row in path_rows if row[1]}
    retained_token_ids = {row[0] for row in credential_rows if row[1] == "token"}
    assert retained_path_token_ids == retained_token_ids
    assert len(credential_rows) == 3
    assert {row[2] for row in credential_rows} == {"revoked"}
    assert all(row[3] is not None for row in credential_rows)
    assert metadata["filesystem_target_count"] == 4
    assert metadata["filesystem_absent_count"] == 0
    assert {entry["kind"] for entry in metadata["trash"]} == {"experiment", "inspection", "project_control", "project_root"}
    assert str(worktree) not in json.dumps(metadata)
    assert trash_rows == 0


def test_artifact_and_log_remove_use_reference_counted_trash(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

print("shared stdout")
Path(os.environ["ALAB_RUN_DIR"], "artifact.txt").write_text(os.environ.get("ALAB_EXP_ID") or "validation", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Reference Counted Remove"
task = "Remove artifact and log bytes safely"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    worktree = tmp_path / "ref-count-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "ref-count", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "first"]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "run", "--message", "second"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)

    artifact_store = home / "projects" / project_id / "artifacts"
    with sqlite3.connect(home / "alab.db") as conn:
        artifacts = conn.execute(
            "SELECT artifact_id, blob_path FROM artifacts WHERE exp_id = ? AND blob_path IS NOT NULL ORDER BY created_at",
            (exp_id,),
        ).fetchall()
        stdout_log = conn.execute(
            "SELECT log_id, file_path FROM log_streams WHERE exp_id = ? AND stream = 'stdout' ORDER BY created_at LIMIT 1",
            (exp_id,),
        ).fetchone()
    assert len(artifacts) == 2
    first_artifact, second_artifact = artifacts
    assert first_artifact[1] == second_artifact[1]
    blob_path = artifact_store / first_artifact[1]
    log_path = artifact_store / stdout_log[1]
    assert blob_path.exists()
    assert log_path.exists()

    assert run(["--home", str(home), "--key", admin_key, "artifacts", "archive", first_artifact[0], "--project", project_id]) == 0
    first_artifact_archive = capsys.readouterr().out
    assert _field_labels(first_artifact_archive) == _archive_field_labels("artifact")
    first_artifact_archived_at = _field(first_artifact_archive, "archived at")
    assert _audit_count(home, "archive", "artifact", first_artifact[0]) == 1
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "archive", first_artifact[0], "--project", project_id]) == 0
    first_artifact_archive_repeat = capsys.readouterr().out
    assert _field_labels(first_artifact_archive_repeat) == _archive_field_labels("artifact")
    assert "previous archive status: archived" in first_artifact_archive_repeat
    assert _field(first_artifact_archive_repeat, "archived at") == first_artifact_archived_at
    assert _field(first_artifact_archive_repeat, "audit id") == "none"
    assert _audit_count(home, "archive", "artifact", first_artifact[0]) == 1
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "unarchive", first_artifact[0], "--project", project_id]) == 0
    first_artifact_unarchive = capsys.readouterr().out
    assert _field_labels(first_artifact_unarchive) == _unarchive_field_labels("artifact")
    first_artifact_unarchived_at = _field(first_artifact_unarchive, "unarchived at")
    assert _audit_count(home, "unarchive", "artifact", first_artifact[0]) == 1
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "unarchive", first_artifact[0], "--project", project_id]) == 0
    first_artifact_unarchive_repeat = capsys.readouterr().out
    assert _field_labels(first_artifact_unarchive_repeat) == _unarchive_field_labels("artifact")
    assert "previous archive status: active" in first_artifact_unarchive_repeat
    assert _field(first_artifact_unarchive_repeat, "unarchived at") == first_artifact_unarchived_at
    assert _field(first_artifact_unarchive_repeat, "audit id") == "none"
    assert _audit_count(home, "unarchive", "artifact", first_artifact[0]) == 1
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "archive", first_artifact[0], "--project", project_id]) == 0
    capsys.readouterr()
    assert _audit_count(home, "archive", "artifact", first_artifact[0]) == 2
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "remove", first_artifact[0], "--project", project_id, "--dry-run"]) == 0
    first_dry_run = capsys.readouterr().out
    assert _field_labels(first_dry_run) == _observe_remove_field_labels("artifact", dry_run=True)
    assert "deleted filesystem paths: 0" in first_dry_run
    _assert_remove_dry_run_preserved(home, "artifact", first_artifact[0], "artifacts", "artifact_id")
    assert blob_path.exists()
    _assert_confirm_guard(
        ["--home", str(home), "--key", admin_key, "artifacts", "remove", first_artifact[0], "--project", project_id],
        first_artifact[0],
        "artifact remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "remove", first_artifact[0], "--project", project_id, "--force", "--confirm", first_artifact[0]]) == 0
    first_remove = capsys.readouterr().out
    assert _field_labels(first_remove) == _observe_remove_field_labels("artifact", dry_run=False)
    assert "deleted filesystem paths: 0" in first_remove
    assert blob_path.exists()

    assert run(["--home", str(home), "--key", admin_key, "artifacts", "archive", second_artifact[0], "--project", project_id]) == 0
    capsys.readouterr()
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "remove", second_artifact[0], "--project", project_id, "--dry-run"]) == 0
    second_dry_run = capsys.readouterr().out
    assert _field_labels(second_dry_run) == _observe_remove_field_labels("artifact", dry_run=True, filesystem_path_count=1)
    assert "deleted filesystem paths: 1" in second_dry_run
    assert "planned trash move:" in second_dry_run
    _assert_remove_dry_run_preserved(home, "artifact", second_artifact[0], "artifacts", "artifact_id")
    assert blob_path.exists()
    _assert_confirm_guard(
        ["--home", str(home), "--key", admin_key, "artifacts", "remove", second_artifact[0], "--project", project_id],
        second_artifact[0],
        "artifact remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "remove", second_artifact[0], "--project", project_id, "--force", "--confirm", second_artifact[0]]) == 0
    second_remove = capsys.readouterr().out
    assert _field_labels(second_remove) == _observe_remove_field_labels("artifact", dry_run=False)
    artifact_audit_id = _field(second_remove, "audit id")
    assert "deleted filesystem paths: 1" in second_remove
    assert "trash cleanup pending: false" in second_remove
    assert not blob_path.exists()

    assert run(["--home", str(home), "--key", admin_key, "logs", "archive", stdout_log[0], "--project", project_id]) == 0
    log_archive = capsys.readouterr().out
    assert _field_labels(log_archive) == _archive_field_labels("log")
    log_archived_at = _field(log_archive, "archived at")
    assert _audit_count(home, "archive", "log", stdout_log[0]) == 1
    assert run(["--home", str(home), "--key", admin_key, "logs", "archive", stdout_log[0], "--project", project_id]) == 0
    log_archive_repeat = capsys.readouterr().out
    assert _field_labels(log_archive_repeat) == _archive_field_labels("log")
    assert "previous archive status: archived" in log_archive_repeat
    assert _field(log_archive_repeat, "archived at") == log_archived_at
    assert _field(log_archive_repeat, "audit id") == "none"
    assert _audit_count(home, "archive", "log", stdout_log[0]) == 1
    assert run(["--home", str(home), "--key", admin_key, "logs", "unarchive", stdout_log[0], "--project", project_id]) == 0
    log_unarchive = capsys.readouterr().out
    assert _field_labels(log_unarchive) == _unarchive_field_labels("log")
    log_unarchived_at = _field(log_unarchive, "unarchived at")
    assert _audit_count(home, "unarchive", "log", stdout_log[0]) == 1
    assert run(["--home", str(home), "--key", admin_key, "logs", "unarchive", stdout_log[0], "--project", project_id]) == 0
    log_unarchive_repeat = capsys.readouterr().out
    assert _field_labels(log_unarchive_repeat) == _unarchive_field_labels("log")
    assert "previous archive status: active" in log_unarchive_repeat
    assert _field(log_unarchive_repeat, "unarchived at") == log_unarchived_at
    assert _field(log_unarchive_repeat, "audit id") == "none"
    assert _audit_count(home, "unarchive", "log", stdout_log[0]) == 1
    assert run(["--home", str(home), "--key", admin_key, "logs", "archive", stdout_log[0], "--project", project_id]) == 0
    capsys.readouterr()
    assert _audit_count(home, "archive", "log", stdout_log[0]) == 2
    assert run(["--home", str(home), "--key", admin_key, "logs", "remove", stdout_log[0], "--project", project_id, "--dry-run"]) == 0
    log_dry_run = capsys.readouterr().out
    assert _field_labels(log_dry_run) == _observe_remove_field_labels("log", dry_run=True, filesystem_path_count=1)
    assert "deleted filesystem paths: 1" in log_dry_run
    assert "planned trash move:" in log_dry_run
    _assert_remove_dry_run_preserved(home, "log", stdout_log[0], "log_streams", "log_id")
    assert log_path.exists()
    _assert_confirm_guard(
        ["--home", str(home), "--key", admin_key, "logs", "remove", stdout_log[0], "--project", project_id],
        stdout_log[0],
        "log remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "logs", "remove", stdout_log[0], "--project", project_id, "--force", "--confirm", stdout_log[0]]) == 0
    log_remove = capsys.readouterr().out
    assert _field_labels(log_remove) == _observe_remove_field_labels("log", dry_run=False)
    log_audit_id = _field(log_remove, "audit id")
    assert "deleted filesystem paths: 1" in log_remove
    assert "trash cleanup pending: false" in log_remove
    assert not log_path.exists()

    with sqlite3.connect(home / "alab.db") as conn:
        artifact_metadata = json.loads(conn.execute("SELECT metadata_json FROM audit_events WHERE audit_id = ?", (artifact_audit_id,)).fetchone()[0])
        log_metadata = json.loads(conn.execute("SELECT metadata_json FROM audit_events WHERE audit_id = ?", (log_audit_id,)).fetchone()[0])
        trash_rows = conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0]
    assert artifact_metadata["filesystem_target_count"] == 1
    assert artifact_metadata["trash"][0]["kind"] == "artifact"
    assert log_metadata["filesystem_target_count"] == 1
    assert log_metadata["trash"][0]["kind"] == "log"
    assert trash_rows == 0


def test_validation_and_run_artifacts_share_blob_reference_counting(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

print(f"owner={os.environ.get('ALAB_EXP_ID') or 'validation'}")
Path(os.environ["ALAB_RUN_DIR"], "artifact.txt").write_text("shared validation run blob", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Shared Validation Run Blob"
task = "Prove validation and run artifacts share blob refs"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")
    validation_id = _field(project_out, "validation id")

    worktree = tmp_path / "shared-blob-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "shared-blob", "--path", str(worktree)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "shared blob"]) == 0
    run_id = _field(capsys.readouterr().out, "run id")
    monkeypatch.chdir(tmp_path)

    artifact_store = home / "projects" / project_id / "artifacts"
    with sqlite3.connect(home / "alab.db") as conn:
        validation_artifact_id, validation_blob = conn.execute(
            "SELECT artifact_id, blob_path FROM artifacts WHERE validation_id = ? AND blob_path IS NOT NULL",
            (validation_id,),
        ).fetchone()
        run_artifact_id, run_blob = conn.execute(
            "SELECT artifact_id, blob_path FROM artifacts WHERE run_id = ? AND blob_path IS NOT NULL",
            (run_id,),
        ).fetchone()
        shared_ref_count = conn.execute(
            "SELECT COUNT(*) FROM artifacts WHERE project_id = ? AND blob_path = ?",
            (project_id, validation_blob),
        ).fetchone()[0]
    assert validation_blob == run_blob
    assert shared_ref_count == 2
    blob_path = artifact_store / validation_blob
    assert blob_path.exists()

    assert run(["--home", str(home), "--key", admin_key, "artifacts", "archive", validation_artifact_id, "--project", project_id]) == 0
    validation_archive = capsys.readouterr().out
    assert _field_labels(validation_archive) == _archive_field_labels("artifact")
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "remove", validation_artifact_id, "--project", project_id, "--dry-run"]) == 0
    validation_dry_run = capsys.readouterr().out
    assert _field_labels(validation_dry_run) == _observe_remove_field_labels("artifact", dry_run=True)
    assert "deleted filesystem paths: 0" in validation_dry_run
    assert blob_path.exists()
    assert run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "artifacts",
            "remove",
            validation_artifact_id,
            "--project",
            project_id,
            "--force",
            "--confirm",
            validation_artifact_id,
        ]
    ) == 0
    validation_remove = capsys.readouterr().out
    assert _field_labels(validation_remove) == _observe_remove_field_labels("artifact", dry_run=False)
    assert "deleted filesystem paths: 0" in validation_remove
    assert blob_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE artifact_id = ?", (validation_artifact_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE artifact_id = ?", (run_artifact_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE project_id = ? AND blob_path = ?", (project_id, run_blob)).fetchone()[0] == 1

    assert run(["--home", str(home), "--key", admin_key, "artifacts", "archive", run_artifact_id, "--project", project_id]) == 0
    run_archive = capsys.readouterr().out
    assert _field_labels(run_archive) == _archive_field_labels("artifact")
    assert run(["--home", str(home), "--key", admin_key, "artifacts", "remove", run_artifact_id, "--project", project_id, "--dry-run"]) == 0
    run_dry_run = capsys.readouterr().out
    assert _field_labels(run_dry_run) == _observe_remove_field_labels("artifact", dry_run=True, filesystem_path_count=1)
    assert "deleted filesystem paths: 1" in run_dry_run
    assert "planned trash move:" in run_dry_run
    assert blob_path.exists()
    assert run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "artifacts",
            "remove",
            run_artifact_id,
            "--project",
            project_id,
            "--force",
            "--confirm",
            run_artifact_id,
        ]
    ) == 0
    run_remove = capsys.readouterr().out
    assert _field_labels(run_remove) == _observe_remove_field_labels("artifact", dry_run=False)
    assert "deleted filesystem paths: 1" in run_remove
    assert "trash cleanup pending: false" in run_remove
    assert not blob_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE artifact_id IN (?, ?)", (validation_artifact_id, run_artifact_id)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0] == 0


def test_shared_log_file_reference_counting(tmp_path, monkeypatch, capsys) -> None:
    data = _init_artifact_log_restore_project(tmp_path, monkeypatch, capsys)
    home = data["home"]
    project_id = data["project_id"]
    admin_key = data["admin_key"]
    stdout_log_id, _stream, stdout_log_path = next(row for row in data["logs"] if row[1] == "stdout")
    duplicate_log_id = new_id("log", "duplicate-shared-log")

    with sqlite3.connect(home / "alab.db") as conn:
        conn.execute(
            """
            INSERT INTO log_streams(
              log_id, project_id, exp_id, run_id, validation_id, stream, size_bytes,
              stored_bytes, content_hash, truncated, hidden, archive_status, file_path,
              preview_text, created_at
            )
            SELECT ?, project_id, exp_id, run_id, validation_id, stream, size_bytes,
              stored_bytes, content_hash, truncated, hidden, archive_status, file_path,
              preview_text, created_at
            FROM log_streams
            WHERE log_id = ?
            """,
            (duplicate_log_id, stdout_log_id),
        )
        shared_file_rel = conn.execute("SELECT file_path FROM log_streams WHERE log_id = ?", (stdout_log_id,)).fetchone()[0]
        assert conn.execute(
            "SELECT COUNT(*) FROM log_streams WHERE project_id = ? AND file_path = ?",
            (project_id, shared_file_rel),
        ).fetchone()[0] == 2
    assert stdout_log_path.exists()

    assert run(["--home", str(home), "--key", admin_key, "logs", "archive", stdout_log_id, "--project", project_id]) == 0
    first_archive = capsys.readouterr().out
    assert _field_labels(first_archive) == _archive_field_labels("log")
    assert run(["--home", str(home), "--key", admin_key, "logs", "remove", stdout_log_id, "--project", project_id, "--dry-run"]) == 0
    first_dry_run = capsys.readouterr().out
    assert _field_labels(first_dry_run) == _observe_remove_field_labels("log", dry_run=True)
    assert "deleted filesystem paths: 0" in first_dry_run
    assert stdout_log_path.exists()
    assert run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "logs",
            "remove",
            stdout_log_id,
            "--project",
            project_id,
            "--force",
            "--confirm",
            stdout_log_id,
        ]
    ) == 0
    first_remove = capsys.readouterr().out
    assert _field_labels(first_remove) == _observe_remove_field_labels("log", dry_run=False)
    assert "deleted filesystem paths: 0" in first_remove
    assert stdout_log_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM log_streams WHERE log_id = ?", (stdout_log_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM log_streams WHERE log_id = ?", (duplicate_log_id,)).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM log_streams WHERE project_id = ? AND file_path = ?",
            (project_id, shared_file_rel),
        ).fetchone()[0] == 1

    assert run(["--home", str(home), "--key", admin_key, "logs", "archive", duplicate_log_id, "--project", project_id]) == 0
    second_archive = capsys.readouterr().out
    assert _field_labels(second_archive) == _archive_field_labels("log")
    assert run(["--home", str(home), "--key", admin_key, "logs", "remove", duplicate_log_id, "--project", project_id, "--dry-run"]) == 0
    second_dry_run = capsys.readouterr().out
    assert _field_labels(second_dry_run) == _observe_remove_field_labels("log", dry_run=True, filesystem_path_count=1)
    assert "deleted filesystem paths: 1" in second_dry_run
    assert "planned trash move:" in second_dry_run
    assert stdout_log_path.exists()
    assert run(
        [
            "--home",
            str(home),
            "--key",
            admin_key,
            "logs",
            "remove",
            duplicate_log_id,
            "--project",
            project_id,
            "--force",
            "--confirm",
            duplicate_log_id,
        ]
    ) == 0
    second_remove = capsys.readouterr().out
    assert _field_labels(second_remove) == _observe_remove_field_labels("log", dry_run=False)
    assert "deleted filesystem paths: 1" in second_remove
    assert "trash cleanup pending: false" in second_remove
    assert not stdout_log_path.exists()
    with sqlite3.connect(home / "alab.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM log_streams WHERE log_id IN (?, ?)", (stdout_log_id, duplicate_log_id)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0] == 0


def test_run_remove_cascades_logs_artifacts_and_updates_experiment_metadata(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
from pathlib import Path

print(f"run={os.environ['ALAB_RUN_ID']}")
Path(os.environ["ALAB_RUN_DIR"], "artifact.txt").write_text(os.environ["ALAB_RUN_ID"], encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Run Cascade Remove"
task = "Remove run children safely"
allow_public_exp_create = true

[runner]
type = "local"
timeout_seconds = 30
working_directory = "."
env_mode = "none"
command = ["{sys.executable}", "main.py"]

[reward]
type = "exit_code"
direction = "maximize"
primary_metric = "reward"

[artifacts]
globs = ["run:artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    admin_key = _field(project_out, "admin key")

    worktree = tmp_path / "run-cascade-exp"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "run-cascade", "--path", str(worktree)]) == 0
    exp_id = _field(capsys.readouterr().out, "exp id")
    monkeypatch.chdir(worktree)
    assert run(["--home", str(home), "run", "--message", "first"]) == 0
    first_run_id = _field(capsys.readouterr().out, "run id")
    assert run(["--home", str(home), "run", "--message", "second"]) == 0
    second_run_id = _field(capsys.readouterr().out, "run id")
    assert first_run_id != second_run_id
    assert run(["--home", str(home), "submit", "--message", "final", "--summary", "done", "--feedback", "ok", "--ref", "none"]) == 0
    submit_out = capsys.readouterr().out
    final_run_id = _field(submit_out, "final run id")
    monkeypatch.chdir(tmp_path)

    artifact_store = home / "projects" / project_id / "artifacts"
    with sqlite3.connect(home / "alab.db") as conn:
        latest_run_id_before = conn.execute("SELECT latest_run_id FROM experiments WHERE exp_id = ?", (exp_id,)).fetchone()[0]
        final_artifact_id, final_artifact_rel = conn.execute(
            "SELECT artifact_id, blob_path FROM artifacts WHERE run_id = ? AND blob_path IS NOT NULL",
            (final_run_id,),
        ).fetchone()
        final_logs = conn.execute("SELECT log_id, file_path FROM log_streams WHERE run_id = ? ORDER BY stream", (final_run_id,)).fetchall()
        final_log_ids = [row[0] for row in final_logs]
        final_log_rels = [row[1] for row in final_logs]
    expected_latest_after = second_run_id if latest_run_id_before == final_run_id and final_run_id != second_run_id else latest_run_id_before
    if latest_run_id_before == final_run_id and final_run_id == second_run_id:
        expected_latest_after = first_run_id
    final_artifact_path = artifact_store / final_artifact_rel
    final_log_paths = [artifact_store / rel for rel in final_log_rels]
    assert final_artifact_path.exists()
    assert all(path.exists() for path in final_log_paths)

    assert run(["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    active_run_remove_dry_run = capsys.readouterr().out
    assert _field_labels(active_run_remove_dry_run) == _observe_remove_field_labels("run", dry_run=True, has_blocker=True, blocker_count=2, filesystem_path_count=3)
    assert "blocker: target_not_archived" in active_run_remove_dry_run
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--dry-run", "--dry-run", "--cascade"], "--dry-run", capsys)
    _assert_duplicate_option_error(["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--dry-run", "--cascade", "--cascade"], "--cascade", capsys)
    _assert_remove_dry_run_preserved(home, "run", final_run_id, "runs", "run_id")
    _assert_not_archived_remove_blocked(
        ["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--force", "--confirm", final_run_id, "--cascade"],
        home,
        "run",
        final_run_id,
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "runs", "archive", final_run_id, "--project", project_id]) == 0
    run_archive_out = capsys.readouterr().out
    assert _field_labels(run_archive_out) == _archive_field_labels("run")
    run_archived_at = _field(run_archive_out, "archived at")
    assert _audit_count(home, "archive", "run", final_run_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "runs", "archive", final_run_id, "--project", project_id]) == 0
    run_archive_repeat_out = capsys.readouterr().out
    assert _field_labels(run_archive_repeat_out) == _archive_field_labels("run")
    assert "previous archive status: archived" in run_archive_repeat_out
    assert _field(run_archive_repeat_out, "archived at") == run_archived_at
    assert _field(run_archive_repeat_out, "audit id") == "none"
    assert _audit_count(home, "archive", "run", final_run_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "runs", "unarchive", final_run_id, "--project", project_id]) == 0
    run_unarchive_out = capsys.readouterr().out
    assert _field_labels(run_unarchive_out) == _unarchive_field_labels("run")
    run_unarchived_at = _field(run_unarchive_out, "unarchived at")
    assert _audit_count(home, "unarchive", "run", final_run_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "runs", "unarchive", final_run_id, "--project", project_id]) == 0
    run_unarchive_repeat_out = capsys.readouterr().out
    assert _field_labels(run_unarchive_repeat_out) == _unarchive_field_labels("run")
    assert "previous archive status: active" in run_unarchive_repeat_out
    assert _field(run_unarchive_repeat_out, "unarchived at") == run_unarchived_at
    assert _field(run_unarchive_repeat_out, "audit id") == "none"
    assert _audit_count(home, "unarchive", "run", final_run_id) == 1
    assert run(["--home", str(home), "--key", admin_key, "runs", "archive", final_run_id, "--project", project_id]) == 0
    capsys.readouterr()
    assert _audit_count(home, "archive", "run", final_run_id) == 2
    assert run(["--home", str(home), "--key", admin_key, "runs", "list", "--project", project_id, "--exp", exp_id]) == 0
    archived_hidden_runs = capsys.readouterr().out
    assert final_run_id not in archived_hidden_runs
    assert run(["--home", str(home), "--key", admin_key, "runs", "list", "--project", project_id, "--exp", exp_id, "--include-archived"]) == 0
    archived_included_runs = capsys.readouterr().out
    assert f"run id: {final_run_id}" in archived_included_runs
    assert "run status: passed" in archived_included_runs
    assert run(["--home", str(home), "--key", admin_key, "runs", "show", final_run_id, "--project", project_id]) == 0
    archived_run_show = capsys.readouterr().out
    assert f"run id: {final_run_id}" in archived_run_show
    assert run(["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--dry-run"]) == 0
    blocked_dry_run = capsys.readouterr().out
    assert _field_labels(blocked_dry_run) == _observe_remove_field_labels("run", dry_run=True, has_blocker=True, filesystem_path_count=3)
    assert "blocker: dependent_records_require_cascade" in blocked_dry_run
    assert "deleted artifacts: 1" in blocked_dry_run
    assert "deleted logs: 2" in blocked_dry_run
    _assert_remove_resource_busy(
        ["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--force", "--confirm", final_run_id],
        home,
        "run",
        final_run_id,
        "dependent_records_require_cascade",
        capsys,
    )

    assert run(["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    active_child_dry_run = capsys.readouterr().out
    assert _field_labels(active_child_dry_run) == _observe_remove_field_labels("run", dry_run=True, has_blocker=True, filesystem_path_count=3)
    assert "blocker: dependent_records_not_archived" in active_child_dry_run
    assert "active dependent artifacts: 1" in active_child_dry_run
    assert "active dependent logs: 2" in active_child_dry_run
    _assert_remove_resource_busy(
        ["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--force", "--confirm", final_run_id, "--cascade"],
        home,
        "run",
        final_run_id,
        "dependent_records_not_archived",
        capsys,
    )
    _assert_remove_dry_run_preserved(home, "run", final_run_id, "runs", "run_id")
    assert _row_count(home, "artifacts", "artifact_id", final_artifact_id) == 1
    for log_id in final_log_ids:
        assert _row_count(home, "log_streams", "log_id", log_id) == 1
    assert final_artifact_path.exists()
    assert all(path.exists() for path in final_log_paths)

    assert run(["--home", str(home), "--key", admin_key, "artifacts", "archive", final_artifact_id, "--project", project_id]) == 0
    capsys.readouterr()
    for log_id in final_log_ids:
        assert run(["--home", str(home), "--key", admin_key, "logs", "archive", log_id, "--project", project_id]) == 0
        capsys.readouterr()

    assert run(["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--dry-run", "--cascade"]) == 0
    cascade_dry_run = capsys.readouterr().out
    assert _field_labels(cascade_dry_run) == _observe_remove_field_labels("run", dry_run=True, filesystem_path_count=3)
    assert "blocker:" not in cascade_dry_run
    assert "active dependent artifacts: 0" in cascade_dry_run
    assert "active dependent logs: 0" in cascade_dry_run
    assert "deleted filesystem paths: 3" in cascade_dry_run
    assert f"latest run id before: {latest_run_id_before}" in cascade_dry_run
    assert f"latest run id after: {expected_latest_after}" in cascade_dry_run
    assert "final run removed: true" in cascade_dry_run
    _assert_remove_dry_run_preserved(home, "run", final_run_id, "runs", "run_id")
    assert final_artifact_path.exists()
    assert all(path.exists() for path in final_log_paths)

    _assert_confirm_guard(
        ["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--cascade"],
        final_run_id,
        "run remove requires --force and matching --confirm",
        capsys,
    )
    assert run(["--home", str(home), "--key", admin_key, "runs", "remove", final_run_id, "--project", project_id, "--force", "--confirm", final_run_id, "--cascade"]) == 0
    remove_out = capsys.readouterr().out
    assert _field_labels(remove_out) == _observe_remove_field_labels("run", dry_run=False)
    audit_id = _field(remove_out, "audit id")
    assert "removed: true" in remove_out
    assert "deleted artifacts: 1" in remove_out
    assert "deleted logs: 2" in remove_out
    assert "deleted filesystem paths: 3" in remove_out
    assert "trash cleanup pending: false" in remove_out
    assert not final_artifact_path.exists()
    assert all(not path.exists() for path in final_log_paths)

    with sqlite3.connect(home / "alab.db") as conn:
        exp_row = conn.execute(
            "SELECT latest_run_id, final_run_id, final_run_removed_at, final_run_removed_by, final_run_removed_audit_id FROM experiments WHERE exp_id = ?",
            (exp_id,),
        ).fetchone()
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE run_id = ?", (final_run_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM artifacts WHERE run_id = ?", (final_run_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM log_streams WHERE run_id = ?", (final_run_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM experiment_submissions WHERE final_run_id = ?", (final_run_id,)).fetchone()[0] == 1
        metadata = json.loads(conn.execute("SELECT metadata_json FROM audit_events WHERE audit_id = ?", (audit_id,)).fetchone()[0])
        trash_rows = conn.execute("SELECT COUNT(*) FROM cache_entries WHERE cache_kind = 'trash' AND status = 'active'").fetchone()[0]
    assert exp_row[0] == expected_latest_after
    assert exp_row[1] == final_run_id
    assert exp_row[2] is not None
    assert exp_row[3] is not None
    assert exp_row[4] == audit_id
    assert metadata["deleted_artifact_count"] == 1
    assert metadata["deleted_log_count"] == 2
    assert metadata["active_dependent_artifact_count"] == 0
    assert metadata["active_dependent_log_count"] == 0
    assert metadata["latest_run_id_before"] == latest_run_id_before
    assert metadata["latest_run_id_after"] == expected_latest_after
    assert metadata["final_run_removed"] is True
    assert metadata["filesystem_target_count"] == 3
    assert {entry["kind"] for entry in metadata["trash"]} == {"artifact", "log"}
    assert trash_rows == 0


def test_experiment_search_best_and_same_project_visibility(tmp_path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text(
        """
import os
import sys
from pathlib import Path

print(f"reward={Path('score.txt').read_text(encoding='utf-8').strip()}")
print("stdout-only-search-needle")
print("stderr-only-search-needle", file=sys.stderr)
Path(os.environ["ALAB_RUN_DIR"], "search-artifact.txt").write_text("artifact-only-search-needle\\n", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (source / "score.txt").write_text("0\n", encoding="utf-8")
    config = tmp_path / "alab.project.toml"
    config.write_text(
        f"""
schema_version = 1

[project]
name = "Corpus Project"
task = "Project task corpus needle"
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
globs = ["run:search-artifact.txt"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert run(["--home", str(home), "auth", "init"]) == 0
    root_key = _field(capsys.readouterr().out, "root key")
    assert run(["--home", str(home), "--key", root_key, "project", "init", "local", "--config", str(config), "--source-path", str(source)]) == 0
    project_out = capsys.readouterr().out
    project_id = _field(project_out, "project id")
    project_source_id = _field(project_out, "source id")
    admin_key = _field(project_out, "admin key")

    def import_visibility(scope: str, experiment_ids: list[str] | None = None) -> None:
        with sqlite3.connect(home / "alab.db") as conn:
            latest_version = conn.execute(
                "SELECT latest_attempted_config_version FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            config_json = json.loads(
                conn.execute(
                    "SELECT canonical_config_json FROM project_config_versions WHERE project_id = ? AND version = ?",
                    (project_id, latest_version),
                ).fetchone()[0]
            )
        config_json["visibility"] = {"scope": scope}
        if scope == "explicit":
            config_json["visibility"]["experiment_ids"] = experiment_ids or []
        visibility_config = tmp_path / f"observe-visibility-{scope}-{len(experiment_ids or [])}.toml"
        visibility_config.write_text(services.dumps_toml(config_json), encoding="utf-8")
        assert (
            run(
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
                    str(visibility_config),
                    "--skip-baseline-test",
                ]
            )
            == 0
        )
        assert "runtime affecting: false" in capsys.readouterr().out

    def exp_ids(output: str) -> list[str]:
        return re.findall(r"^exp id: (.+)$", output, re.MULTILINE)

    extra_exp = tmp_path / "extra-exp"
    exp_count_before_extra_create = _table_count(home, "experiments")
    assert run(["--home", str(home), "exp", "create", "extra", "--project", project_id, "--name", "Extra", "--path", str(extra_exp)]) == 2
    extra_exp_create_err = capsys.readouterr().err
    assert _field_labels(extra_exp_create_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in extra_exp_create_err
    assert "exp create accepts no positional arguments" in extra_exp_create_err
    assert _table_count(home, "experiments") == exp_count_before_extra_create
    assert not extra_exp.exists()

    first = tmp_path / "first"
    second = tmp_path / "second"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "Alpha", "--goal", "Alpha goal corpus needle", "--path", str(first), "--tag", "rank"]) == 0
    first_id = _field(capsys.readouterr().out, "exp id")
    assert (
        run(
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
                "Bravo goal corpus needle",
                "--path",
                str(second),
                "--tag",
                "rank",
            ]
        )
        == 0
    )
    second_id = _field(capsys.readouterr().out, "exp id")

    (first / "score.txt").write_text("1\n", encoding="utf-8")
    monkeypatch.chdir(first)
    assert run(["--home", str(home), "run", "--message", "alpha"]) == 0
    first_run_out = capsys.readouterr().out
    assert "reward: 1" in first_run_out
    first_run_id = _field(first_run_out, "run id")

    (second / "score.txt").write_text("5\n", encoding="utf-8")
    monkeypatch.chdir(second)
    assert run(["--home", str(home), "run", "--message", "bravo"]) == 0
    second_run_out = capsys.readouterr().out
    assert "reward: 5" in second_run_out
    second_run_id = _field(second_run_out, "run id")
    assert run(["--home", str(home), "submit", "--message", "bravo final", "--summary", "Final summary corpus needle", "--feedback", "Feedback corpus needle", "--ref", "none"]) == 0
    assert "submit accepted: true" in capsys.readouterr().out
    with sqlite3.connect(home / "alab.db") as conn:
        second_artifact_id = conn.execute(
            "SELECT artifact_id FROM artifacts WHERE run_id = ? AND relative_path = 'search-artifact.txt'",
            (second_run_id,),
        ).fetchone()[0]
        second_stdout_log_id = conn.execute(
            "SELECT log_id FROM log_streams WHERE run_id = ? AND stream = 'stdout' AND hidden = 0",
            (second_run_id,),
        ).fetchone()[0]

    no_reward = tmp_path / "no-reward"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "No Reward", "--path", str(no_reward), "--tag", "rank"]) == 0
    no_reward_id = _field(capsys.readouterr().out, "exp id")

    assert run(["--home", str(home), "--key", admin_key, "annotate", "add", "--project", project_id, "--target", f"exp:{second_id}", "--body", "private search needle", "--private-to-exp", second_id]) == 0
    assert "visibility: private" in capsys.readouterr().out
    assert run(["--home", str(home), "--key", admin_key, "annotate", "add", "--project", project_id, "--target", f"exp:{second_id}", "--body", "historical annotation search needle"]) == 0
    visible_annotation_id = _field(capsys.readouterr().out, "annotation id")
    assert run(["--home", str(home), "--key", admin_key, "annotate", "edit", visible_annotation_id, "--project", project_id, "--body", "current annotation search needle"]) == 0
    assert "revision: 2" in capsys.readouterr().out
    experiment_times = {
        first_id: ("2026-01-01T00:00:00Z", "2026-01-01T00:10:00Z"),
        second_id: ("2026-01-01T00:01:00Z", "2026-01-01T00:20:00Z"),
        no_reward_id: ("2026-01-01T00:02:00Z", "2026-01-01T00:30:00Z"),
    }
    with sqlite3.connect(home / "alab.db") as conn:
        for exp_id, (created_at, updated_at) in experiment_times.items():
            conn.execute("UPDATE experiments SET created_at = ?, updated_at = ? WHERE exp_id = ?", (created_at, updated_at, exp_id))
        conn.commit()

    monkeypatch.chdir(first)
    assert run(["--home", str(home), "exp", "list", "--tag", "rank"]) == 0
    list_out = capsys.readouterr().out
    assert all(labels == _experiment_field_labels() for labels in _block_labels(list_out))
    assert first_id in list_out
    assert second_id in list_out
    assert no_reward_id in list_out
    for args, message in [
        (["--home", str(home), "exp", "list", "extra", "--project", project_id], "exp list accepts no positional arguments"),
        (["--home", str(home), "exp", "search", "extra", "--project", project_id, "--query", "bravo"], "exp search accepts no positional arguments"),
        (["--home", str(home), "exp", "best", "extra", "--project", project_id], "exp best accepts no positional arguments"),
    ]:
        assert run(args) == 2
        extra_exp_query_err = capsys.readouterr().err
        assert _field_labels(extra_exp_query_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in extra_exp_query_err
        assert message in extra_exp_query_err
    for args in [
        ["--home", str(home), "exp", "list", "--project", project_id, "--reason", "ignored"],
        ["--home", str(home), "exp", "search", "--project", project_id, "--query", "bravo", "--reason", "ignored"],
        ["--home", str(home), "exp", "best", "--project", project_id, "--reason", "ignored"],
    ]:
        assert run(args) == 2
        unsupported_exp_query_err = capsys.readouterr().err
        assert _field_labels(unsupported_exp_query_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in unsupported_exp_query_err
        assert "unsupported option --reason" in unsupported_exp_query_err
    with sqlite3.connect(home / "alab.db") as conn:
        second_filters = conn.execute(
            "SELECT source_id, bound_config_version, created_at, updated_at FROM experiments WHERE exp_id = ?",
            (second_id,),
        ).fetchone()
    assert second_filters[0] == project_source_id
    assert run(
        [
            "--home",
            str(home),
            "exp",
            "list",
            "--tag",
            "rank",
            "--source-id",
            project_source_id,
            "--name-query",
            "brav",
            "--config-version",
            str(second_filters[1]),
            "--created-after",
            second_filters[2],
            "--created-before",
            second_filters[2],
            "--updated-after",
            second_filters[3],
            "--updated-before",
            second_filters[3],
        ]
    ) == 0
    filtered_exp_list = capsys.readouterr().out
    assert _field_labels(filtered_exp_list) == _experiment_field_labels()
    assert second_id in filtered_exp_list
    assert first_id not in filtered_exp_list
    assert no_reward_id not in filtered_exp_list
    assert run(["--home", str(home), "exp", "list", "--source-id", project_source_id[:8]]) == 2
    short_source_filter_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in short_source_filter_err
    assert "object ids must be complete" in short_source_filter_err
    assert run(["--home", str(home), "exp", "list", "--name-query", "missing experiment"]) == 0
    missing_name_list = capsys.readouterr().out
    assert _field_labels(missing_name_list) == []
    assert run(["--home", str(home), "exp", "list", "--tag", "rank", "--status", "closed"]) == 0
    closed_status_list = capsys.readouterr().out
    assert exp_ids(closed_status_list) == [second_id]
    assert "experiment status: closed" in closed_status_list
    assert run(["--home", str(home), "exp", "list", "--tag", "rank", "--status", "open", "--sort", "name:asc"]) == 0
    open_name_sorted = capsys.readouterr().out
    assert exp_ids(open_name_sorted) == [first_id, no_reward_id]
    assert second_id not in open_name_sorted
    assert run(["--home", str(home), "exp", "list", "--tag", "rank", "--sort", "created:asc"]) == 0
    assert exp_ids(capsys.readouterr().out) == [first_id, second_id, no_reward_id]
    assert run(["--home", str(home), "exp", "list", "--tag", "rank", "--sort", "updated:desc"]) == 0
    assert exp_ids(capsys.readouterr().out) == [no_reward_id, second_id, first_id]
    assert run(["--home", str(home), "exp", "list", "--tag", "rank", "--sort", "name:desc"]) == 0
    assert exp_ids(capsys.readouterr().out) == [no_reward_id, second_id, first_id]
    assert run(["--home", str(home), "exp", "list", "--tag", "rank", "--sort", "status:asc"]) == 0
    status_sorted_ids = exp_ids(capsys.readouterr().out)
    assert status_sorted_ids[0] == second_id
    assert set(status_sorted_ids[1:]) == {first_id, no_reward_id}
    assert run(["--home", str(home), "exp", "list", "--tag", "rank", "--created-after", second_filters[2], "--created-before", experiment_times[first_id][0]]) == 2
    inverted_created_range_err = capsys.readouterr().err
    assert _field_labels(inverted_created_range_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in inverted_created_range_err
    assert "--created-after must be less than or equal to --created-before" in inverted_created_range_err

    assert run(["--home", str(home), "exp", "list", "--tag", "rank", "--sort", "reward:asc"]) == 0
    reward_sorted = capsys.readouterr().out
    assert all(labels == _experiment_field_labels() for labels in _block_labels(reward_sorted))
    assert reward_sorted.index(f"exp id: {first_id}") < reward_sorted.index(f"exp id: {second_id}") < reward_sorted.index(f"exp id: {no_reward_id}")
    assert run(["--home", str(home), "exp", "list", "--tag", "rank", "--sort", "reward:asc", "--limit", "1", "--offset", "1"]) == 0
    paged_exp_list = capsys.readouterr().out
    assert _field_labels(paged_exp_list) == _experiment_field_labels()
    assert second_id in paged_exp_list
    assert first_id not in paged_exp_list
    assert no_reward_id not in paged_exp_list
    assert run(["--home", str(home), "exp", "list", "--limit", "0"]) == 2
    list_limit_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in list_limit_err
    assert "--limit must be between 1 and 500" in list_limit_err
    assert run(["--home", str(home), "exp", "list", "--offset", "-1"]) == 2
    list_offset_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in list_offset_err
    assert "--offset must be zero or greater" in list_offset_err
    assert run(["--home", str(home), "exp", "list", "--reward-min", "3", "--reward-max", "2"]) == 2
    inverted_exp_list_reward_err = capsys.readouterr().err
    assert _field_labels(inverted_exp_list_reward_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in inverted_exp_list_reward_err
    assert "--reward-min must be less than or equal to --reward-max" in inverted_exp_list_reward_err
    for args, message in [
        (["exp", "list", "--project", project_id, "--project", project_id], "--project may be provided once"),
        (["exp", "list", "--created-after", second_filters[2], "--created-after", second_filters[2]], "--created-after may be provided once"),
        (["exp", "search", "--query", "rank", "--reward-min", "1", "--reward-min", "2"], "--reward-min may be provided once"),
        (["exp", "best", "--limit", "1", "--limit", "2"], "--limit may be provided once"),
    ]:
        assert run(["--home", str(home), *args]) == 2
        duplicate_exp_query_err = capsys.readouterr().err
        assert _field_labels(duplicate_exp_query_err) == _error_field_labels()
        assert "error code: CONFIG_INVALID" in duplicate_exp_query_err
        assert message in duplicate_exp_query_err

    assert run(["--home", str(home), "exp", "search", "--query", "bravo"]) == 0
    search_out = capsys.readouterr().out
    assert _field_labels(search_out) == _experiment_field_labels()
    assert second_id in search_out
    for query, expected_ids, unexpected_ids in [
        ("PROJECT TASK CORPUS NEEDLE", [first_id, second_id, no_reward_id], []),
        ("alpha goal corpus needle", [first_id], [second_id, no_reward_id]),
        ("RANK", [first_id, second_id, no_reward_id], []),
        ("final summary corpus needle", [second_id], [first_id, no_reward_id]),
        ("FEEDBACK CORPUS NEEDLE", [second_id], [first_id, no_reward_id]),
    ]:
        assert run(["--home", str(home), "exp", "search", "--query", query]) == 0
        corpus_search_out = capsys.readouterr().out
        assert all(labels == _experiment_field_labels() for labels in _block_labels(corpus_search_out))
        for expected_id in expected_ids:
            assert expected_id in corpus_search_out
        for unexpected_id in unexpected_ids:
            assert unexpected_id not in corpus_search_out
    assert run(["--home", str(home), "exp", "search", "--query", "rank", "--sort", "reward:asc", "--limit", "1", "--offset", "1"]) == 0
    paged_search_out = capsys.readouterr().out
    assert _field_labels(paged_search_out) == _experiment_field_labels()
    assert second_id in paged_search_out
    assert first_id not in paged_search_out
    assert no_reward_id not in paged_search_out

    for excluded_query in [
        "stdout-only-search-needle",
        "stderr-only-search-needle",
        "artifact-only-search-needle",
        "historical annotation search needle",
    ]:
        assert run(["--home", str(home), "exp", "search", "--query", excluded_query]) == 0
        excluded_search_out = capsys.readouterr().out
        assert _field_labels(excluded_search_out) == []
        assert first_id not in excluded_search_out
        assert second_id not in excluded_search_out

    assert run(["--home", str(home), "exp", "search", "--query", "current annotation search needle"]) == 0
    current_annotation_search = capsys.readouterr().out
    assert _field_labels(current_annotation_search) == _experiment_field_labels()
    assert second_id in current_annotation_search

    alt_source = tmp_path / "alt-source"
    alt_source.mkdir()
    (alt_source / "main.py").write_text((source / "main.py").read_text(encoding="utf-8"), encoding="utf-8")
    (alt_source / "score.txt").write_text("8\n", encoding="utf-8")
    tagged_filter_exp = tmp_path / "tagged-filter"
    assert (
        run(
            [
                "--home",
                str(home),
                "--key",
                admin_key,
                "exp",
                "create",
                "--project",
                project_id,
                "--name",
                "Echo",
                "--goal",
                "Tag filter corpus needle",
                "--source-path",
                str(alt_source),
                "--path",
                str(tagged_filter_exp),
                "--tag",
                "one",
                "--tag",
                "two",
            ]
        )
        == 0
    )
    tagged_filter_out = capsys.readouterr().out
    tagged_filter_id = _field(tagged_filter_out, "exp id")
    tagged_filter_source_id = _field(tagged_filter_out, "source id")
    assert tagged_filter_source_id != project_source_id
    assert run(["--home", str(home), "exp", "list", "--source-id", tagged_filter_source_id, "--tag", "one", "--tag", "two"]) == 0
    source_and_tag_filtered_list = capsys.readouterr().out
    assert exp_ids(source_and_tag_filtered_list) == [tagged_filter_id]
    assert "tag: one" in source_and_tag_filtered_list
    assert "tag: two" in source_and_tag_filtered_list
    assert first_id not in source_and_tag_filtered_list
    assert second_id not in source_and_tag_filtered_list
    assert run(["--home", str(home), "exp", "search", "--query", "tag filter corpus needle", "--source-id", tagged_filter_source_id, "--tag", "one", "--tag", "two", "--name-query", "ech", "--sort", "name:asc"]) == 0
    source_and_tag_filtered_search = capsys.readouterr().out
    assert exp_ids(source_and_tag_filtered_search) == [tagged_filter_id]
    assert first_id not in source_and_tag_filtered_search
    assert second_id not in source_and_tag_filtered_search
    assert run(["--home", str(home), "exp", "search", "--query", "rank", "--status", "closed", "--sort", "name:desc"]) == 0
    closed_status_search = capsys.readouterr().out
    assert exp_ids(closed_status_search) == [second_id]
    assert "experiment name: Bravo" in closed_status_search
    assert run(["--home", str(home), "exp", "search", "--query", "rank", "--sort", "name:desc"]) == 0
    assert exp_ids(capsys.readouterr().out) == [no_reward_id, second_id, first_id]

    assert run(["--home", str(home), "exp", "search", "--query", "rank", "--reward-min", "2"]) == 0
    reward_search_out = capsys.readouterr().out
    assert _field_labels(reward_search_out) == _experiment_field_labels()
    assert second_id in reward_search_out
    assert first_id not in reward_search_out
    assert no_reward_id not in reward_search_out
    assert run(["--home", str(home), "exp", "search", "--query", "rank", "--reward-max", "2"]) == 0
    reward_max_search_out = capsys.readouterr().out
    assert _field_labels(reward_max_search_out) == _experiment_field_labels()
    assert first_id in reward_max_search_out
    assert second_id not in reward_max_search_out
    assert no_reward_id not in reward_max_search_out
    assert run(["--home", str(home), "exp", "search", "--query", "rank", "--reward-min", "3", "--reward-max", "2"]) == 2
    inverted_exp_search_reward_err = capsys.readouterr().err
    assert _field_labels(inverted_exp_search_reward_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in inverted_exp_search_reward_err
    assert "--reward-min must be less than or equal to --reward-max" in inverted_exp_search_reward_err

    assert run(["--home", str(home), "exp", "search", "--query", "private search needle"]) == 0
    private_public_out = capsys.readouterr().out
    assert _field_labels(private_public_out) == []
    assert second_id not in private_public_out

    monkeypatch.chdir(second)
    assert run(["--home", str(home), "exp", "search", "--query", "private search needle"]) == 0
    private_exp_out = capsys.readouterr().out
    assert _field_labels(private_exp_out) == _experiment_field_labels()
    assert second_id in private_exp_out

    monkeypatch.chdir(tmp_path)
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "visibility.scope", '"none"', "--project", project_id]) == 0
    assert "runtime affecting: false" in capsys.readouterr().out
    monkeypatch.chdir(first)
    assert run(["--home", str(home), "exp", "list", "--tag", "rank"]) == 0
    tag_filtered_none_visibility = capsys.readouterr().out
    assert _field_labels(tag_filtered_none_visibility) == _experiment_field_labels()
    assert first_id in tag_filtered_none_visibility
    assert second_id not in tag_filtered_none_visibility
    assert no_reward_id not in tag_filtered_none_visibility

    inspection_path = tmp_path / "rank-inspection"
    assert run(["--home", str(home), "--key", admin_key, "exp", "checkout", second_id, "--project", project_id, "--path", str(inspection_path)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(inspection_path)
    assert run(["--home", str(home), "exp", "list", "--tag", "rank"]) == 0
    inspection_tag_filtered = capsys.readouterr().out
    assert _field_labels(inspection_tag_filtered) == _experiment_field_labels()
    assert second_id in inspection_tag_filtered
    assert first_id not in inspection_tag_filtered
    assert no_reward_id not in inspection_tag_filtered

    import_visibility("explicit", [second_id])
    monkeypatch.chdir(first)
    assert run(["--home", str(home), "exp", "list", "--tag", "rank"]) == 0
    explicit_first_list = capsys.readouterr().out
    assert all(labels == _experiment_field_labels() for labels in _block_labels(explicit_first_list))
    assert first_id in explicit_first_list
    assert second_id in explicit_first_list
    assert no_reward_id not in explicit_first_list
    assert run(["--home", str(home), "observe", "experiments", "show", second_id]) == 0
    explicit_first_show = capsys.readouterr().out
    assert _field_labels(explicit_first_show) == _experiment_field_labels()
    assert "experiment name: Bravo" in explicit_first_show
    assert run(["--home", str(home), "observe", "experiments", "show", no_reward_id]) == 4
    explicit_not_listed_err = capsys.readouterr().err
    assert _field_labels(explicit_not_listed_err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in explicit_not_listed_err
    assert "not visible or not found" in explicit_not_listed_err
    assert run(["--home", str(home), "runs", "show", second_run_id]) == 0
    explicit_run_show = capsys.readouterr().out
    assert f"run id: {second_run_id}" in explicit_run_show
    assert "hidden log available: false" in explicit_run_show
    assert run(["--home", str(home), "artifacts", "show", second_artifact_id]) == 0
    explicit_artifact_show = capsys.readouterr().out
    assert _field_labels(explicit_artifact_show) == _artifact_field_labels()
    assert f"artifact id: {second_artifact_id}" in explicit_artifact_show
    assert run(["--home", str(home), "logs", "show", second_stdout_log_id]) == 0
    explicit_log_show = capsys.readouterr().out
    assert _field_labels(explicit_log_show) == _log_show_field_labels()
    assert f"log id: {second_stdout_log_id}" in explicit_log_show

    import_visibility("explicit", [first_id])
    monkeypatch.chdir(inspection_path)
    assert run(["--home", str(home), "exp", "list", "--tag", "rank"]) == 0
    explicit_inspection_list = capsys.readouterr().out
    assert all(labels == _experiment_field_labels() for labels in _block_labels(explicit_inspection_list))
    assert first_id in explicit_inspection_list
    assert second_id in explicit_inspection_list
    assert no_reward_id not in explicit_inspection_list
    assert run(["--home", str(home), "observe", "experiments", "show", first_id]) == 0
    explicit_inspection_show = capsys.readouterr().out
    assert _field_labels(explicit_inspection_show) == _experiment_field_labels()
    assert "experiment name: Alpha" in explicit_inspection_show
    assert run(["--home", str(home), "runs", "show", first_run_id]) == 0
    explicit_inspection_run = capsys.readouterr().out
    assert f"run id: {first_run_id}" in explicit_inspection_run
    assert "hidden log available: false" in explicit_inspection_run
    assert run(["--home", str(home), "observe", "experiments", "show", no_reward_id]) == 4
    explicit_inspection_blocked_err = capsys.readouterr().err
    assert _field_labels(explicit_inspection_blocked_err) == _error_field_labels()
    assert "error code: SCOPE_VIOLATION" in explicit_inspection_blocked_err
    assert "not visible or not found" in explicit_inspection_blocked_err

    monkeypatch.chdir(tmp_path)
    import_visibility("same_project")
    monkeypatch.chdir(first)
    assert run(["--home", str(home), "observe", "experiments", "show", second_id]) == 0
    show_out = capsys.readouterr().out
    assert _field_labels(show_out) == _experiment_field_labels()
    assert "experiment name: Bravo" in show_out
    for command_name, object_id, object_type in [
        ("runs", second_run_id, "run"),
        ("artifacts", second_artifact_id, "artifact"),
        ("logs", second_stdout_log_id, "log"),
    ]:
        assert run(["--home", str(home), command_name, "archive", object_id]) == 4
        lifecycle_err = capsys.readouterr().err
        assert _field_labels(lifecycle_err) == _error_field_labels()
        assert "error code: SCOPE_VIOLATION" in lifecycle_err
        assert "not visible or not found" in lifecycle_err
        assert _audit_count(home, "archive", object_type, object_id) == 0
        assert run(["--home", str(home), "--key", admin_key, command_name, "archive", object_id, "--project", project_id]) == 0
        capsys.readouterr()
        assert run(["--home", str(home), command_name, "unarchive", object_id]) == 4
        unarchive_err = capsys.readouterr().err
        assert _field_labels(unarchive_err) == _error_field_labels()
        assert "error code: SCOPE_VIOLATION" in unarchive_err
        assert "not visible or not found" in unarchive_err
        assert _audit_count(home, "unarchive", object_type, object_id) == 0
        assert run(["--home", str(home), "--key", admin_key, command_name, "unarchive", object_id, "--project", project_id]) == 0
        capsys.readouterr()

    assert run(["--home", str(home), "exp", "best", "--limit", "1"]) == 0
    best_out = capsys.readouterr().out
    assert _field_labels(best_out) == _experiment_field_labels()
    assert _field(best_out, "exp id") == second_id
    assert "reward: 5" in best_out
    assert run(["--home", str(home), "exp", "best", "--limit", "1", "--offset", "1"]) == 0
    paged_best_out = capsys.readouterr().out
    assert _field_labels(paged_best_out) == _experiment_field_labels()
    assert _field(paged_best_out, "exp id") == first_id
    assert "reward: 1" in paged_best_out
    assert run(["--home", str(home), "exp", "best", "--limit", "501"]) == 2
    best_limit_err = capsys.readouterr().err
    assert "error code: CONFIG_INVALID" in best_limit_err
    assert "--limit must be between 1 and 500" in best_limit_err
    assert run(["--home", str(home), "exp", "best", "--config-version", str(second_filters[1]), "--limit", "1"]) == 0
    best_config_out = capsys.readouterr().out
    assert _field_labels(best_config_out) == _experiment_field_labels()
    assert _field(best_config_out, "exp id") == second_id
    assert "reward: 5" in best_config_out
    assert run(["--home", str(home), "exp", "best", "--reward-max", "2", "--limit", "1"]) == 0
    best_reward_max_out = capsys.readouterr().out
    assert _field_labels(best_reward_max_out) == _experiment_field_labels()
    assert _field(best_reward_max_out, "exp id") == first_id
    assert "reward: 1" in best_reward_max_out
    assert run(["--home", str(home), "exp", "best", "--reward-min", "6"]) == 0
    best_reward_empty_out = capsys.readouterr().out
    assert _field_labels(best_reward_empty_out) == []
    assert run(["--home", str(home), "exp", "best", "--reward-min", "3", "--reward-max", "2"]) == 2
    inverted_exp_best_reward_err = capsys.readouterr().err
    assert _field_labels(inverted_exp_best_reward_err) == _error_field_labels()
    assert "error code: CONFIG_INVALID" in inverted_exp_best_reward_err
    assert "--reward-min must be less than or equal to --reward-max" in inverted_exp_best_reward_err
    assert run(["--home", str(home), "exp", "best", "--sort", "reward:desc"]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().err

    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "reward.direction", '"minimize"', "--project", project_id]) == 0
    minimize_config_out = capsys.readouterr().out
    assert "validation status: passed" in minimize_config_out
    minimize_version = int(_field(minimize_config_out, "latest attempted config version"))

    third = tmp_path / "third"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "Charlie", "--path", str(third), "--tag", "rank"]) == 0
    third_id = _field(capsys.readouterr().out, "exp id")
    (third / "score.txt").write_text("2\n", encoding="utf-8")
    monkeypatch.chdir(third)
    assert run(["--home", str(home), "run", "--message", "charlie"]) == 0
    assert "reward: 2" in capsys.readouterr().out

    assert run(["--home", str(home), "observe", "experiments", "best", "--limit", "1"]) == 0
    incomparable_best_out = capsys.readouterr().out
    assert _block_labels(incomparable_best_out) == [
        _experiment_field_labels(),
        ["object", "warning code", "warning reason", "excluded count"],
    ]
    assert _field(incomparable_best_out, "exp id") == third_id
    assert "object: warning" in incomparable_best_out
    assert "warning code: BEST_INCOMPARABLE_RUNS_EXCLUDED" in incomparable_best_out
    assert "excluded count: 2" in incomparable_best_out

    archived_ranker = tmp_path / "archived-ranker"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "Delta", "--path", str(archived_ranker), "--tag", "rank"]) == 0
    archived_ranker_id = _field(capsys.readouterr().out, "exp id")
    (archived_ranker / "score.txt").write_text("1\n", encoding="utf-8")
    monkeypatch.chdir(archived_ranker)
    assert run(["--home", str(home), "run", "--message", "delta"]) == 0
    assert "reward: 1" in capsys.readouterr().out
    assert run(["--home", str(home), "--key", admin_key, "exp", "archive", archived_ranker_id, "--project", project_id]) == 0
    assert "experiment status: archived" in capsys.readouterr().out
    monkeypatch.chdir(third)

    assert run(["--home", str(home), "exp", "list", "--tag", "rank"]) == 0
    archived_hidden_list = capsys.readouterr().out
    assert archived_ranker_id not in archived_hidden_list
    assert run(["--home", str(home), "exp", "list", "--tag", "rank", "--include-archived"]) == 0
    archived_included_list = capsys.readouterr().out
    assert archived_ranker_id in archived_included_list
    assert run(["--home", str(home), "exp", "list", "--status", "archived", "--include-archived"]) == 0
    archived_status_list = capsys.readouterr().out
    assert exp_ids(archived_status_list) == [archived_ranker_id]
    assert "experiment status: archived" in archived_status_list

    assert run(["--home", str(home), "exp", "search", "--query", "delta"]) == 0
    archived_hidden_search = capsys.readouterr().out
    assert _field_labels(archived_hidden_search) == []
    assert archived_ranker_id not in archived_hidden_search
    assert run(["--home", str(home), "exp", "search", "--query", "delta", "--include-archived"]) == 0
    archived_included_search = capsys.readouterr().out
    assert _field_labels(archived_included_search) == _experiment_field_labels()
    assert archived_ranker_id in archived_included_search

    assert run(["--home", str(home), "observe", "experiments", "best", "--limit", "1"]) == 0
    archived_hidden_best = capsys.readouterr().out
    assert _field(archived_hidden_best, "exp id") == third_id
    assert archived_ranker_id not in archived_hidden_best
    assert run(["--home", str(home), "observe", "experiments", "best", "--limit", "1", "--include-archived"]) == 0
    archived_included_best = capsys.readouterr().out
    assert _field(archived_included_best, "exp id") == archived_ranker_id
    assert "reward: 1" in archived_included_best

    tie_older = tmp_path / "tie-older"
    tie_new_a = tmp_path / "tie-new-a"
    tie_new_b = tmp_path / "tie-new-b"
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "Tie Older", "--path", str(tie_older), "--tag", "tie"]) == 0
    tie_older_id = _field(capsys.readouterr().out, "exp id")
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "Tie New A", "--path", str(tie_new_a), "--tag", "tie"]) == 0
    tie_new_a_id = _field(capsys.readouterr().out, "exp id")
    assert run(["--home", str(home), "exp", "create", "--project", project_id, "--name", "Tie New B", "--path", str(tie_new_b), "--tag", "tie"]) == 0
    tie_new_b_id = _field(capsys.readouterr().out, "exp id")

    failing_command = json.dumps([sys.executable, "-c", "import sys; sys.exit(8)"])
    assert run(["--home", str(home), "--key", admin_key, "project", "config", "set", "runner.command", failing_command, "--project", project_id]) == 1
    invalid_config_out = capsys.readouterr().out
    assert "validation status: failed" in invalid_config_out
    assert "project status: invalid" in invalid_config_out
    with sqlite3.connect(home / "alab.db") as conn:
        invalid_project = conn.execute(
            "SELECT status, active_valid_config_version, active_validation_id FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert invalid_project[0] == "invalid"
    assert invalid_project[1] == minimize_version
    assert invalid_project[2] is not None

    assert run(["--home", str(home), "observe", "experiments", "best", "--limit", "1"]) == 0
    invalid_best_out = capsys.readouterr().out
    assert _field(invalid_best_out, "exp id") == third_id
    assert "reward: 2" in invalid_best_out
    assert "warning code: BEST_INCOMPARABLE_RUNS_EXCLUDED" in invalid_best_out
    assert "excluded count: 2" in invalid_best_out

    tie_new_a_older_run_id = new_id("run", "tie-new-a-older")
    tie_new_a_newer_run_id = new_id("run", "tie-new-a-newer")
    tie_new_b_run_id = new_id("run", "tie-new-b")
    tie_older_run_id = new_id("run", "tie-older")
    ignored_status_run_ids = [new_id("run", f"ignored-{status}") for status in ["running", "failed", "error", "timeout", "interrupted"]]
    ignored_unparsed_run_id = new_id("run", "ignored-unparsed")
    record_json = json.dumps({"schema_version": 1})
    with sqlite3.connect(home / "alab.db") as conn:
        tie_rows = {
            tie_older_id: (tie_older_run_id, tie_older, "2026-02-01T00:00:00Z"),
            tie_new_a_id: (tie_new_a_newer_run_id, tie_new_a, "2026-02-02T00:00:00Z"),
            tie_new_b_id: (tie_new_b_run_id, tie_new_b, "2026-02-02T00:00:00Z"),
        }
        conn.execute(
            """
            INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, exit_code,
              reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
            VALUES (?, ?, ?, ?, ?, 'passed', 0, 4, 'parsed', 'active', ?, ?, ?)
            """,
            (
                tie_new_a_older_run_id,
                tie_new_a_id,
                project_id,
                _git(["rev-parse", "HEAD"], tie_new_a),
                minimize_version,
                "2026-01-31T00:00:00Z",
                "2026-01-31T00:00:00Z",
                record_json,
            ),
        )
        for tie_exp_id, (run_id, tie_path, ended_at) in tie_rows.items():
            conn.execute(
                """
                INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, exit_code,
                  reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
                VALUES (?, ?, ?, ?, ?, 'passed', 0, 4, 'parsed', 'active', ?, ?, ?)
                """,
                (run_id, tie_exp_id, project_id, _git(["rev-parse", "HEAD"], tie_path), minimize_version, ended_at, ended_at, record_json),
            )
        ignored_statuses = ["running", "failed", "error", "timeout", "interrupted"]
        for run_id, status in zip(ignored_status_run_ids, ignored_statuses, strict=True):
            ended_at = None if status == "running" else "2026-02-03T00:00:00Z"
            conn.execute(
                """
                INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, exit_code,
                  reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
                VALUES (?, ?, ?, ?, ?, ?, 1, 999, 'parsed', 'active', '2026-02-03T00:00:00Z', ?, ?)
                """,
                (run_id, tie_older_id, project_id, _git(["rev-parse", "HEAD"], tie_older), minimize_version, status, ended_at, record_json),
            )
        conn.execute(
            """
            INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, exit_code,
              reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
            VALUES (?, ?, ?, ?, ?, 'passed', 0, 999, 'invalid', 'active', '2026-02-03T00:00:00Z', '2026-02-03T00:00:00Z', ?)
            """,
            (ignored_unparsed_run_id, tie_older_id, project_id, _git(["rev-parse", "HEAD"], tie_older), minimize_version, record_json),
        )
        conn.commit()

    assert run(["--home", str(home), "exp", "best", "--tag", "tie", "--reward-min", "4", "--reward-max", "4"]) == 0
    tie_best_out = capsys.readouterr().out
    assert all(labels == _experiment_field_labels() for labels in _block_labels(tie_best_out))
    tie_best_ids = re.findall(r"^exp id: (.+)$", tie_best_out, re.MULTILINE)
    assert tie_best_ids == [*sorted([tie_new_a_id, tie_new_b_id]), tie_older_id]
    assert tie_best_ids.count(tie_new_a_id) == 1
    assert f"best run id: {tie_new_a_newer_run_id}" in tie_best_out
    assert f"best run id: {tie_new_a_older_run_id}" not in tie_best_out
    assert run(["--home", str(home), "exp", "best", "--tag", "tie", "--reward-min", "900"]) == 0
    status_excluded_best_out = capsys.readouterr().out
    assert _field_labels(status_excluded_best_out) == []
