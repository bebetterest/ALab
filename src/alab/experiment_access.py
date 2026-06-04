from __future__ import annotations

from pathlib import Path
from typing import Any

from . import services as _core
from .auth import Actor
from .context import context_marker_obj, path_hash
from .db import Database, all_rows, one
from .errors import AlabError
from .home import Home
from .rendering import ResultBlock
from .service_args import (
    _exp_commit_selector_filter,
    _is_commit_sha_selector,
    _require_option_choice,
    command_arg,
    flag,
    optional_positional_selector,
    require_dry_run_unforced,
    require_exactly_one_option_pair,
    require_force_confirm,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_auth import require_home
from .service_models import TOKEN_MODES, GitRefDeletion, Request
from .service_text import _lifecycle_reason
from .timeutil import utc_now

_project_row = _core._project_row
_project_id_from_request = _core._project_id_from_request
_complete_id_option = _core._complete_id_option
_complete_id_or_missing = _core._complete_id_or_missing
_assert_new_context_path = _core._assert_new_context_path
_require_project_admin = _core._require_project_admin
_exp_row = _core._exp_row
_exp_visible = _core._exp_visible
_best_run_for_experiment = _core._best_run_for_experiment
_optional_best_context = _core._optional_best_context
_project_paths = _core._project_paths
_assert_mutable_paths_allowed = _core._assert_mutable_paths_allowed
_path_present = _core._path_present
_worktree_dirty_state = _core._worktree_dirty_state
_trash_plan = _core._trash_plan
_stage_path_to_trash = _core._stage_path_to_trash
_raise_after_staged_trash_transaction_failure = _core._raise_after_staged_trash_transaction_failure
_finalize_staged_trash = _core._finalize_staged_trash
_write_git_exclude = _core._write_git_exclude
_authorize_observe = _core._authorize_observe


def audit(*args: Any, **kwargs: Any) -> str:
    return _core.audit(*args, **kwargs)


def create_credential(*args: Any, **kwargs: Any) -> tuple[str, str]:
    return _core.create_credential(*args, **kwargs)


def new_id(*args: Any, **kwargs: Any) -> str:
    return _core.new_id(*args, **kwargs)


def read_token(*args: Any, **kwargs: Any) -> str:
    return _core.read_token(*args, **kwargs)


def run_cmd(*args: Any, **kwargs: Any) -> Any:
    return _core.run_cmd(*args, **kwargs)


def verify_raw_credential(*args: Any, **kwargs: Any) -> Actor:
    return _core.verify_raw_credential(*args, **kwargs)


def write_marker(*args: Any, **kwargs: Any) -> None:
    return _core.write_marker(*args, **kwargs)


def write_token(*args: Any, **kwargs: Any) -> None:
    return _core.write_token(*args, **kwargs)


def _resolve_exp_commit(
    conn,
    home: Home,
    project_id: str,
    exp: Any,
    selector: str | None,
    *,
    allow_head_alias: bool = False,
) -> str:
    selector = selector or "latest"
    _project_root, repo_git, _artifact_store = _project_paths(home, project_id)
    branch_ref = f"refs/heads/{exp['branch_name']}"
    if selector == "latest" or (allow_head_alias and selector in {"HEAD", "head"}):
        if exp["latest_commit"]:
            commit = exp["latest_commit"]
        else:
            commit = (
                run_cmd(["git", f"--git-dir={repo_git}", "rev-parse", f"{branch_ref}^{{commit}}"])
                .stdout.decode("utf-8", errors="replace")
                .strip()
            )
    elif selector == "final":
        commit = exp["final_commit"]
        if not commit:
            raise AlabError("CONFIG_INVALID", "experiment has no final commit")
    elif selector == "best":
        project = _project_row(conn, project_id)
        reward_identity, direction = _optional_best_context(conn, project)
        row, _excluded = _best_run_for_experiment(
            conn,
            project_id=project_id,
            exp_id=exp["exp_id"],
            direction=direction,
            reward_identity=reward_identity,
        )
        if row is None:
            raise AlabError("CONFIG_INVALID", "experiment has no qualifying best run")
        commit = row["commit_sha"]
    else:
        if not _is_commit_sha_selector(selector):
            raise AlabError(
                "CONFIG_INVALID", "commit selector must be latest, final, best, or a commit SHA"
            )
        commit = _resolve_commit_sha_selector(repo_git, selector)
        reachable = run_cmd(
            ["git", f"--git-dir={repo_git}", "merge-base", "--is-ancestor", commit, branch_ref],
            check=False,
        )
        if reachable.returncode != 0:
            raise AlabError(
                "CONFIG_INVALID", "commit is not reachable from the source experiment branch"
            )
    if not commit:
        raise AlabError("CONFIG_INVALID", "commit selector did not resolve")
    return commit


def _resolve_commit_sha_selector(repo_git: Path, selector: str) -> str:
    prefix = selector.lower()
    candidates = run_cmd(
        ["git", f"--git-dir={repo_git}", "rev-parse", f"--disambiguate={prefix}"],
        check=False,
    )
    if candidates.returncode != 0:
        raise AlabError("CONFIG_INVALID", "commit selector did not resolve")
    object_ids = [
        line.strip()
        for line in candidates.stdout.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    if len(object_ids) != 1:
        if object_ids:
            raise AlabError("CONFIG_INVALID", "commit selector is ambiguous")
        raise AlabError("CONFIG_INVALID", "commit selector did not resolve")
    resolved = run_cmd(
        ["git", f"--git-dir={repo_git}", "rev-parse", f"{object_ids[0]}^{{commit}}"],
        check=False,
    )
    if resolved.returncode != 0:
        raise AlabError("CONFIG_INVALID", "commit selector did not resolve")
    commit = resolved.stdout.decode("utf-8", errors="replace").strip()
    if not commit:
        raise AlabError("CONFIG_INVALID", "commit selector did not resolve")
    return commit


def _path_registry_row_for_token(conn, token_id: str) -> Any | None:
    return one(
        conn, "SELECT * FROM path_registry WHERE token_id = ? AND status = 'active'", (token_id,)
    )


def _token_path_status(conn, token_id: str) -> str:
    row = _path_registry_row_for_token(conn, token_id)
    if row is None:
        return "removed"
    return "present" if Path(row["path"]).exists() else "missing"


def _active_worktree_token(conn, exp_id: str) -> Any | None:
    return one(
        conn,
        "SELECT * FROM credentials WHERE exp_id = ? AND credential_type = 'token' AND token_mode = 'worktree' AND status = 'active'",
        (exp_id,),
    )


def _experiment_branch_ref(branch_name: str) -> str:
    if not branch_name.startswith("alab/exp/"):
        raise AlabError("GIT_ERROR", "refusing to delete unexpected experiment branch")
    return f"refs/heads/{branch_name}"


def _git_ref_commit(repo_git: Path, branch_ref: str) -> str | None:
    result = run_cmd(
        ["git", f"--git-dir={repo_git}", "rev-parse", "--verify", f"{branch_ref}^{{commit}}"],
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip() or None


def _delete_experiment_branch_ref(repo_git: Path, branch_name: str) -> GitRefDeletion:
    branch_ref = _experiment_branch_ref(branch_name)
    commit = _git_ref_commit(repo_git, branch_ref)
    if commit is None:
        return GitRefDeletion(branch_ref, None, False, True)
    result = run_cmd(["git", f"--git-dir={repo_git}", "update-ref", "-d", branch_ref], check=False)
    if result.returncode != 0:
        reason = (
            result.stderr.decode("utf-8", errors="replace").strip()
            or "failed to delete experiment branch ref"
        )
        raise AlabError("GIT_ERROR", reason)
    return GitRefDeletion(branch_ref, commit, True, False)


def _restore_experiment_branch_ref(repo_git: Path, deletion: GitRefDeletion | None) -> None:
    if deletion is None or not deletion.deleted or deletion.commit is None:
        return
    result = run_cmd(
        ["git", f"--git-dir={repo_git}", "update-ref", deletion.branch_ref, deletion.commit],
        check=False,
    )
    if result.returncode != 0:
        reason = (
            result.stderr.decode("utf-8", errors="replace").strip()
            or "failed to restore experiment branch ref"
        )
        raise AlabError("GIT_ERROR", reason)


def _prune_missing_git_worktrees(repo_git: Path) -> None:
    run_cmd(["git", f"--git-dir={repo_git}", "worktree", "prune"], check=False)


def cmd_exp_worktree_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--force", "--confirm", "--reason"))
    require_options_at_most_once(args, ("--dry-run", "--reason"))
    require_dry_run_unforced(args)
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(
        args, "exp worktree remove accepts exactly one experiment id"
    )
    dry_run = flag(args, "--dry-run")
    conn = require_home(req.globals.home)
    try:
        exp = dict(_exp_row(conn, project["project_id"], exp_id))
        path_row = one(
            conn,
            "SELECT * FROM path_registry WHERE exp_id = ? AND context_type = 'experiment' AND status = 'active'",
            (exp["exp_id"],),
        )
        token = _active_worktree_token(conn, exp["exp_id"])
        old_path = path_row["path"] if path_row else exp["worktree_path"]
        dirty_state = _worktree_dirty_state(old_path)
        token_revoked = bool(token)
        token_id = token["credential_id"] if token else None
    finally:
        conn.close()
    reason = _lifecycle_reason(args)
    if dry_run:
        return [
            ResultBlock(
                "worktree",
                [
                    ("exp id", exp["exp_id"]),
                    ("old worktree path", old_path),
                    ("worktree state", exp["worktree_state"]),
                    ("dry run", True),
                    ("removed", False),
                    ("path exists", _path_present(Path(old_path)) if old_path else False),
                    ("dirty state", dirty_state),
                    ("token revocation target", token_id),
                    ("token revoked", token_revoked),
                    ("planned trash move", _trash_plan(req.globals.home, old_path)),
                    ("audit id", None),
                ],
            )
        ]
    require_force_confirm(
        args, exp["exp_id"], "exp worktree remove requires --force and matching --confirm"
    )
    _project_root, repo_git, _artifact_store = _project_paths(
        req.globals.home, project["project_id"]
    )
    audit_id = new_id("aud", "remove")
    stage = _stage_path_to_trash(req.globals.home, old_path, audit_id)
    try:
        with Database(req.globals.home).tx() as tx:
            now = utc_now()
            if token:
                tx.execute(
                    "UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?",
                    (now, token["credential_id"]),
                )
            tx.execute(
                "UPDATE path_registry SET status = 'removed', removed_at = ?, removed_by_credential_id = ?, updated_at = ? WHERE exp_id = ? AND context_type = 'experiment' AND status = 'active'",
                (now, actor.credential_id, now, exp["exp_id"]),
            )
            tx.execute(
                "UPDATE experiments SET worktree_state = 'removed', worktree_path = NULL, worktree_path_hash = NULL, updated_at = ? WHERE exp_id = ?",
                (now, exp["exp_id"]),
            )
            audit(
                tx,
                action="remove",
                object_type="worktree",
                object_id=exp["exp_id"],
                actor=actor,
                audit_id=audit_id,
                project_id=project["project_id"],
                exp_id=exp["exp_id"],
                reason=reason,
                metadata={
                    "schema_version": 1,
                    "filesystem_path_already_absent": stage.already_absent,
                    "dirty_state": dirty_state,
                    "token_revocation_target": token_id,
                    "trash": {
                        "mode": stage.mode,
                        "label": stage.audit_label,
                        "original_path_hash": path_hash(stage.original_path)
                        if stage.original_path
                        else None,
                    },
                },
            )
    except Exception as exc:
        _raise_after_staged_trash_transaction_failure(exc, [stage])
    _prune_missing_git_worktrees(repo_git)
    trash_cleanup_pending = _finalize_staged_trash(req.globals.home, stage, project["project_id"])
    return [
        ResultBlock(
            "worktree",
            [
                ("exp id", exp["exp_id"]),
                ("old worktree path", old_path),
                ("worktree state", "removed"),
                ("dry run", False),
                ("removed", True),
                ("path existed", not stage.already_absent),
                ("dirty state", dirty_state),
                ("token revocation target", token_id),
                ("token revoked", token_revoked),
                ("trash path", stage.audit_label),
                ("trash cleanup pending", trash_cleanup_pending),
                ("audit id", audit_id),
            ],
        )
    ]


def cmd_exp_worktree_restore(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--path"))
    require_options_at_most_once(args, ("--path",))
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(
        args, "exp worktree restore accepts exactly one experiment id"
    )
    restore_path = Path(command_arg(args, "--path", required=True)).expanduser().resolve()
    conn = require_home(req.globals.home)
    try:
        _assert_new_context_path(
            conn,
            target=restore_path,
            project_id=project["project_id"],
            context_type="experiment",
            label="restore",
        )
        exp = dict(_exp_row(conn, project["project_id"], exp_id))
        if exp["worktree_state"] == "active":
            raise AlabError("RESOURCE_BUSY", "experiment already has an active worktree")
        old_token = _active_worktree_token(conn, exp["exp_id"])
        home_id = one(conn, "SELECT home_id FROM homes LIMIT 1")["home_id"]
    finally:
        conn.close()
    _project_root, repo_git, _artifact_store = _project_paths(
        req.globals.home, project["project_id"]
    )
    run_cmd(
        ["git", f"--git-dir={repo_git}", "worktree", "add", str(restore_path), exp["branch_name"]]
    )
    restore_path_hash = path_hash(restore_path)
    with Database(req.globals.home).tx() as tx:
        now = utc_now()
        revoked_token_id = None
        if old_token:
            revoked_token_id = old_token["credential_id"]
            tx.execute(
                "UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?",
                (now, revoked_token_id),
            )
        token_id, raw_token = create_credential(
            tx,
            credential_type="token",
            project_id=project["project_id"],
            exp_id=exp["exp_id"],
            token_mode="worktree",
            registered_path_hash=restore_path_hash,
            metadata={
                "schema_version": 1,
                "token_mode": "worktree",
                "created_for_path_hash": restore_path_hash,
            },
        )
        write_marker(
            restore_path,
            {
                "marker_version": 1,
                "home_id": home_id,
                "context_type": "experiment",
                "project_id": project["project_id"],
                "exp_id": exp["exp_id"],
                "token_id": token_id,
                "created_at": now,
            },
        )
        write_token(restore_path, raw_token)
        _write_git_exclude(restore_path)
        path_registry_id = new_id("path", "experiment")
        tx.execute(
            """
            INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id,
              exp_id, token_id, status, created_at, updated_at)
            VALUES (?, ?, ?, 'experiment', ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                path_registry_id,
                restore_path_hash,
                str(restore_path),
                home_id,
                project["project_id"],
                exp["exp_id"],
                token_id,
                now,
                now,
            ),
        )
        tx.execute(
            "UPDATE experiments SET worktree_path = ?, worktree_path_hash = ?, worktree_state = 'active', updated_at = ? WHERE exp_id = ?",
            (str(restore_path), restore_path_hash, now, exp["exp_id"]),
        )
        audit(
            tx,
            action="restore",
            object_type="worktree",
            object_id=exp["exp_id"],
            actor=actor,
            project_id=project["project_id"],
            exp_id=exp["exp_id"],
            metadata={
                "schema_version": 1,
                "branch": exp["branch_name"],
                "worktree_state": "active",
                "restored_path_hash": restore_path_hash,
                "path_registry_id": path_registry_id,
                "revoked_token_id": revoked_token_id,
                "created_token_id": token_id,
                "token_mode": "worktree",
            },
        )
    return [
        ResultBlock(
            "worktree",
            [
                ("exp id", exp["exp_id"]),
                ("branch", exp["branch_name"]),
                ("worktree path", str(restore_path)),
                ("worktree state", "active"),
                ("token path", str(restore_path / ".alab" / "token")),
                ("revoked token id", revoked_token_id),
                ("new token id", token_id),
            ],
        )
    ]


def _credential_selector_sql(args: list[str], exp_id: str) -> tuple[str, tuple[Any, ...]]:
    require_options_at_most_once(args, ("--token-id", "--mode", "--all"))
    token_id = _complete_id_option(args, "--token-id", "cred")
    raw_mode = command_arg(args, "--mode")
    all_flag = flag(args, "--all")
    if all_flag and (token_id or raw_mode):
        raise AlabError("CONFIG_INVALID", "--all conflicts with --token-id or --mode")
    mode = _require_option_choice(raw_mode, "--mode", TOKEN_MODES)
    if token_id:
        return "exp_id = ? AND credential_id = ? AND credential_type = 'token'", (exp_id, token_id)
    if mode:
        return "exp_id = ? AND token_mode = ? AND credential_type = 'token'", (exp_id, mode)
    if all_flag:
        return "exp_id = ? AND credential_type = 'token'", (exp_id,)
    return "exp_id = ? AND token_mode = 'worktree' AND credential_type = 'token'", (exp_id,)


def cmd_exp_token_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--token-id", "--mode", "--all"))
    require_options_at_most_once(args, ("--token-id", "--mode", "--all"))
    project, _actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(args, "exp token list accepts exactly one experiment id")
    conn = require_home(req.globals.home)
    try:
        _exp_row(conn, project["project_id"], exp_id)
        where, params = _credential_selector_sql(args, exp_id)
        rows = all_rows(
            conn, f"SELECT * FROM credentials WHERE {where} ORDER BY created_at", params
        )
        return [
            ResultBlock(
                "credential",
                [
                    ("project id", project["project_id"]),
                    ("exp id", row["exp_id"]),
                    ("token id", row["credential_id"]),
                    ("token mode", row["token_mode"]),
                    ("status", row["status"]),
                    ("path status", _token_path_status(conn, row["credential_id"])),
                    ("created at", row["created_at"]),
                    ("revoked at", row["revoked_at"]),
                ],
            )
            for row in rows
        ]
    finally:
        conn.close()


def cmd_exp_token_revoke(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--token-id", "--mode", "--all"))
    require_options_at_most_once(args, ("--token-id", "--mode", "--all"))
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(
        args, "exp token revoke accepts exactly one experiment id"
    )
    with Database(req.globals.home).tx() as conn:
        _exp_row(conn, project["project_id"], exp_id)
        where, params = _credential_selector_sql(args, exp_id)
        rows = all_rows(
            conn, f"SELECT * FROM credentials WHERE {where} AND status = 'active'", params
        )
        if not rows:
            raise AlabError("CREDENTIAL_NOT_FOUND", "active token not found")
        now = utc_now()
        blocks: list[ResultBlock] = []
        for row in rows:
            conn.execute(
                "UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?",
                (now, row["credential_id"]),
            )
            audit(
                conn,
                action="revoke",
                object_type="credential",
                object_id=row["credential_id"],
                actor=actor,
                project_id=project["project_id"],
                exp_id=exp_id,
                metadata={
                    "schema_version": 1,
                    "credential_type": row["credential_type"],
                    "token_mode": row["token_mode"],
                    "previous_status": row["status"],
                    "credential_status": "revoked",
                    "revoked_at": now,
                    "registered_path_hash": row["registered_path_hash"],
                },
            )
            blocks.append(
                ResultBlock(
                    "credential",
                    [
                        ("project id", project["project_id"]),
                        ("exp id", exp_id),
                        ("token id", row["credential_id"]),
                        ("token mode", row["token_mode"]),
                        ("status", "revoked"),
                        ("revoked at", now),
                    ],
                )
            )
        return blocks


def cmd_exp_token_regenerate(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--token-id", "--mode", "--all"))
    project, actor = _require_project_admin(args, req)
    exp_id = optional_positional_selector(
        args, "exp token regenerate accepts exactly one experiment id"
    )
    require_options_at_most_once(args, ("--token-id", "--mode", "--all"))
    raw_mode = command_arg(args, "--mode", default="worktree")
    if command_arg(args, "--token-id") or flag(args, "--all"):
        raise AlabError("CONFIG_INVALID", "regenerate selects one token mode only")
    mode = _require_option_choice(raw_mode, "--mode", TOKEN_MODES)
    with Database(req.globals.home).tx() as conn:
        _exp_row(conn, project["project_id"], exp_id)
        old = one(
            conn,
            "SELECT * FROM credentials WHERE exp_id = ? AND token_mode = ? AND credential_type = 'token' AND status = 'active' ORDER BY created_at DESC LIMIT 1",
            (exp_id, mode),
        )
        if old is None:
            raise AlabError("CREDENTIAL_NOT_FOUND", "active token not found")
        path_row = _path_registry_row_for_token(conn, old["credential_id"])
        if path_row is None:
            raise AlabError("CONTEXT_NOT_FOUND", "active token has no active registered path")
        now = utc_now()
        conn.execute(
            "UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?",
            (now, old["credential_id"]),
        )
        new_token_id, raw_token = create_credential(
            conn,
            credential_type="token",
            project_id=project["project_id"],
            exp_id=exp_id,
            token_mode=mode,
            registered_path_hash=path_row["path_hash"],
            metadata={
                "schema_version": 1,
                "token_mode": mode,
                "created_for_path_hash": path_row["path_hash"],
            },
        )
        conn.execute(
            "UPDATE path_registry SET token_id = ?, updated_at = ? WHERE path_registry_id = ?",
            (new_token_id, now, path_row["path_registry_id"]),
        )
        path = Path(path_row["path"])
        write_token(path, raw_token)
        marker = context_marker_obj((path / ".alab" / "context.json").read_text(encoding="utf-8"))
        marker["token_id"] = new_token_id
        write_marker(path, marker)
        _write_git_exclude(path)
        audit(
            conn,
            action="regenerate",
            object_type="credential",
            object_id=new_token_id,
            actor=actor,
            project_id=project["project_id"],
            exp_id=exp_id,
            metadata={
                "schema_version": 1,
                "credential_type": "token",
                "token_mode": mode,
                "revoked_credential_id": old["credential_id"],
                "created_credential_id": new_token_id,
                "revoked_at": now,
                "registered_path_hash": path_row["path_hash"],
            },
        )
    return [
        ResultBlock(
            "credential",
            [
                ("project id", project["project_id"]),
                ("exp id", exp_id),
                ("revoked token id", old["credential_id"]),
                ("new token id", new_token_id),
                ("token mode", mode),
                ("token path", str(path / ".alab" / "token")),
                ("created at", now),
            ],
        )
    ]


def cmd_exp_checkout(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--path", "--commit"))
    require_options_at_most_once(args, ("--path", "--commit"))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    exp_id = optional_positional_selector(args, "exp checkout accepts exactly one experiment id")
    commit_selector = _exp_commit_selector_filter(command_arg(args, "--commit"))
    checkout_path = Path(command_arg(args, "--path", required=True)).expanduser().resolve()
    conn = require_home(req.globals.home)
    try:
        _project_row(conn, project_id)
        _assert_new_context_path(
            conn,
            target=checkout_path,
            project_id=project_id,
            context_type="inspection",
            label="inspection checkout",
        )
        exp = _exp_row(conn, project_id, exp_id)
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, exp["exp_id"]):
            raise AlabError("SCOPE_VIOLATION", "experiment is not visible to this token")
        commit = _resolve_exp_commit(conn, req.globals.home, project_id, exp, commit_selector)
        home_id = one(conn, "SELECT home_id FROM homes LIMIT 1")["home_id"]
    finally:
        conn.close()
    _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project_id)
    run_cmd(
        ["git", f"--git-dir={repo_git}", "worktree", "add", "--detach", str(checkout_path), commit]
    )
    with Database(req.globals.home).tx() as tx:
        now = utc_now()
        checkout_path_hash = path_hash(checkout_path)
        path_registry_id = new_id("path", "inspection")
        token_id, raw_token = create_credential(
            tx,
            credential_type="token",
            project_id=project_id,
            exp_id=exp["exp_id"],
            token_mode="inspection",
            registered_path_hash=checkout_path_hash,
            metadata={
                "schema_version": 1,
                "token_mode": "inspection",
                "created_for_path_hash": checkout_path_hash,
            },
        )
        write_marker(
            checkout_path,
            {
                "marker_version": 1,
                "home_id": home_id,
                "context_type": "inspection",
                "project_id": project_id,
                "exp_id": exp["exp_id"],
                "token_id": token_id,
                "inspection_commit": commit,
                "created_at": now,
            },
        )
        write_token(checkout_path, raw_token)
        _write_git_exclude(checkout_path)
        tx.execute(
            """
            INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id,
              exp_id, token_id, status, created_at, updated_at)
            VALUES (?, ?, ?, 'inspection', ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                path_registry_id,
                checkout_path_hash,
                str(checkout_path),
                home_id,
                project_id,
                exp["exp_id"],
                token_id,
                now,
                now,
            ),
        )
        audit(
            tx,
            action="add",
            object_type="inspection_checkout",
            object_id=token_id,
            actor=actor,
            project_id=project_id,
            exp_id=exp["exp_id"],
            metadata={
                "schema_version": 1,
                "credential_type": "token",
                "token_mode": "inspection",
                "created_token_id": token_id,
                "inspection_commit": commit,
                "path_registry_id": path_registry_id,
                "created_for_path_hash": checkout_path_hash,
            },
        )
    return [
        ResultBlock(
            "inspection_checkout",
            [
                ("exp id", exp["exp_id"]),
                ("inspection path", str(checkout_path)),
                ("inspection commit", commit),
                ("token path", str(checkout_path / ".alab" / "token")),
                ("token id", token_id),
                ("next", f"cd {checkout_path} && alab status"),
            ],
        )
    ]


def _authorize_checkout_remove(req: Request, project_id: str, path_row: Any) -> Actor:
    raw = req.globals.key
    if raw:
        conn = require_home(req.globals.home)
        try:
            return verify_raw_credential(
                conn, raw, required=("root", "admin"), project_id=project_id
            )
        finally:
            conn.close()
    if (
        req.context
        and req.context.context_type == "inspection"
        and req.context.token_id == path_row["token_id"]
    ):
        conn = require_home(req.globals.home)
        try:
            token = read_token(req.context.path)
            return verify_raw_credential(
                conn,
                token,
                required="token",
                project_id=project_id,
                exp_id=path_row["exp_id"],
                token_mode="inspection",
                path_hash=req.context.path_hash,
            )
        finally:
            conn.close()
    raise AlabError(
        "AUTH_REQUIRED",
        "checkout remove requires admin/root key or matching inspection token context",
    )


def cmd_exp_checkout_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args, ("--project", "--token-id", "--path", "--dry-run", "--force", "--confirm", "--reason")
    )
    require_options_at_most_once(args, ("--dry-run", "--reason"))
    require_dry_run_unforced(args)
    project_id = _project_id_from_request(args, req)
    require_exactly_one_option_pair(
        args, "--token-id", "--path", "checkout remove requires exactly one of --token-id or --path"
    )
    token_id = _complete_id_option(args, "--token-id", "cred")
    path_arg = command_arg(args, "--path")
    require_positional_count(args, 0, "exp checkout remove accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        if token_id:
            path_row = one(
                conn,
                "SELECT * FROM path_registry WHERE project_id = ? AND token_id = ? AND context_type = 'inspection' AND status = 'active'",
                (project_id, token_id),
            )
        else:
            ph = path_hash(Path(path_arg).expanduser().resolve())
            path_row = one(
                conn,
                "SELECT * FROM path_registry WHERE project_id = ? AND path_hash = ? AND context_type = 'inspection' AND status = 'active'",
                (project_id, ph),
            )
        if path_row is None:
            raise AlabError("CONTEXT_NOT_FOUND", "inspection checkout not found")
        actor = _authorize_checkout_remove(req, project_id, path_row)
    finally:
        conn.close()
    dry_run = flag(args, "--dry-run")
    expected_confirm = path_row["token_id"] if token_id else path_row["path_hash"]
    reason = _lifecycle_reason(args)
    if dry_run:
        return [
            ResultBlock(
                "inspection_checkout",
                [
                    ("exp id", path_row["exp_id"]),
                    ("inspection path", path_row["path"]),
                    ("token id", path_row["token_id"]),
                    ("dry run", True),
                    ("removed", False),
                    ("path exists", _path_present(Path(path_row["path"]))),
                    ("token revocation target", path_row["token_id"]),
                    ("token revoked", True),
                    ("planned trash move", _trash_plan(req.globals.home, path_row["path"])),
                    ("audit id", None),
                ],
            )
        ]
    require_force_confirm(
        args, expected_confirm, "checkout remove requires --force and matching --confirm"
    )
    _project_root, repo_git, _artifact_store = _project_paths(req.globals.home, project_id)
    audit_id = new_id("aud", "remove")
    stage = _stage_path_to_trash(req.globals.home, path_row["path"], audit_id)
    try:
        with Database(req.globals.home).tx() as tx:
            now = utc_now()
            tx.execute(
                "UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?",
                (now, path_row["token_id"]),
            )
            tx.execute(
                "UPDATE path_registry SET status = 'removed', removed_at = ?, removed_by_credential_id = ?, updated_at = ? WHERE path_registry_id = ?",
                (now, actor.credential_id, now, path_row["path_registry_id"]),
            )
            audit(
                tx,
                action="remove",
                object_type="inspection_checkout",
                object_id=path_row["token_id"],
                actor=actor,
                audit_id=audit_id,
                project_id=project_id,
                exp_id=path_row["exp_id"],
                reason=reason,
                metadata={
                    "schema_version": 1,
                    "filesystem_path_already_absent": stage.already_absent,
                    "token_revocation_target": path_row["token_id"],
                    "trash": {
                        "mode": stage.mode,
                        "label": stage.audit_label,
                        "original_path_hash": path_hash(stage.original_path)
                        if stage.original_path
                        else None,
                    },
                },
            )
    except Exception as exc:
        _raise_after_staged_trash_transaction_failure(exc, [stage])
    _prune_missing_git_worktrees(repo_git)
    trash_cleanup_pending = _finalize_staged_trash(req.globals.home, stage, project_id)
    return [
        ResultBlock(
            "inspection_checkout",
            [
                ("exp id", path_row["exp_id"]),
                ("inspection path", path_row["path"]),
                ("token id", path_row["token_id"]),
                ("dry run", False),
                ("removed", True),
                ("path existed", not stage.already_absent),
                ("token revocation target", path_row["token_id"]),
                ("token revoked", True),
                ("trash path", stage.audit_label),
                ("trash cleanup pending", trash_cleanup_pending),
                ("audit id", audit_id),
            ],
        )
    ]
