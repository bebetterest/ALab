from __future__ import annotations

from pathlib import Path
from typing import Any

from .auth import Actor, read_token, verify_raw_credential
from .db import Database, all_rows, canonical_json, one
from .errors import AlabError
from .home import Home
from .ids import new_id, require_complete_id
from .proc import run_cmd
from .rendering import ResultBlock, multiline_text
from .service_args import (
    _append_time_filter,
    _register_observe_text_predicates,
    _require_option_choice,
    _require_ordered_time_range,
    _sql_order_limit_clause,
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
from .service_audit import audit
from .service_auth import require_home
from .service_contracts import annotation_target_json_obj, annotation_visibility_json_obj
from .service_models import (
    ANNOTATION_TARGET_ID_PREFIXES,
    ANNOTATION_TARGET_TYPES,
    Request,
)
from .service_text import _assert_utf8_max_bytes, _lifecycle_reason, _read_text_input_file
from .services import (
    _assert_text_has_no_secret,
    _authorize_observe,
    _complete_id_or_missing,
    _exp_row,
    _exp_visible,
    _project_id_from_request,
    _project_paths,
    _project_row,
    _resolve_exp_commit,
    _visible_exp_ids,
)
from .timeutil import utc_now


def _annotation_target_id_filter(target_type: str | None, target_id: str | None) -> str | None:
    if not target_id:
        return None
    if target_type == "none":
        raise AlabError("CONFIG_INVALID", "--target-id is not valid for target-type none")
    if target_type in ANNOTATION_TARGET_ID_PREFIXES:
        return require_complete_id(target_id, ANNOTATION_TARGET_ID_PREFIXES[target_type])
    if ":" not in target_id:
        for prefix in ANNOTATION_TARGET_ID_PREFIXES.values():
            if target_id.startswith(prefix + "-"):
                return require_complete_id(target_id, prefix)
    return target_id


def _annotation_created_by_filter(created_by: str | None) -> str | None:
    if not created_by:
        return None
    created_by = require_complete_id(created_by)
    if not (created_by.startswith("exp-") or created_by.startswith("cred-")):
        raise AlabError("CONFIG_INVALID", "--created-by must be an experiment or credential id")
    return created_by


def _read_annotation_body(args: list[str]) -> str:
    if flag(args, "--body-stdin"):
        raise AlabError("CONFIG_INVALID", "--body-stdin is not supported; use direct text or file input")
    require_exactly_one_option_pair(args, "--body", "--body-file", "annotation requires exactly one of --body or --body-file")
    body = command_arg(args, "--body")
    body_file = command_arg(args, "--body-file")
    text = _read_text_input_file(body_file, "annotation body") if body_file else body or ""
    _assert_utf8_max_bytes("annotation body", text, 65536)
    return text


def _read_annotation_title(args: list[str], *, required: bool) -> str | None:
    title = command_arg(args, "--title")
    if title is None:
        if required:
            raise AlabError("CONFIG_INVALID", "targetless annotation requires --title")
        return None
    normalized = title.strip()
    if not normalized:
        raise AlabError("CONFIG_INVALID", "annotation title must be non-empty")
    _assert_utf8_max_bytes("annotation title", normalized, 256)
    return normalized


def _authorize_annotation_actor(req: Request, project_id: str) -> Actor:
    raw = req.globals.key
    if raw:
        conn = require_home(req.globals.home)
        try:
            return verify_raw_credential(conn, raw, required=("root", "admin"), project_id=project_id)
        finally:
            conn.close()
    if req.context and req.context.context_type == "experiment" and req.context.project_id == project_id:
        conn = require_home(req.globals.home)
        try:
            token = read_token(req.context.path)
            return verify_raw_credential(conn, token, required="token", project_id=project_id, exp_id=req.context.exp_id, token_mode="worktree", path_hash=req.context.path_hash)
        finally:
            conn.close()
    if req.context and req.context.context_type == "inspection":
        raise AlabError("SCOPE_VIOLATION", "inspection tokens cannot mutate annotations")
    raise AlabError("AUTH_REQUIRED", "annotation command requires admin/root key or experiment token context")


def _annotation_private_exp_selector(args: list[str], actor: Actor) -> str | None:
    private_to_exp = command_arg(args, "--private-to-exp")
    if actor.actor_type == "token":
        if private_to_exp:
            raise AlabError("CONFIG_INVALID", "--private-to-exp is only valid with admin/root")
        return actor.exp_id if flag(args, "--private") else None
    if flag(args, "--private") and not private_to_exp:
        raise AlabError("CONFIG_INVALID", "--private requires --private-to-exp for admin/root")
    return require_complete_id(private_to_exp, "exp") if private_to_exp else None


def _validate_annotation_target_selector_ids(args: list[str]) -> None:
    raw_target = command_arg(args, "--target")
    if raw_target is None:
        raw_exp = command_arg(args, "--exp")
        if raw_exp:
            require_complete_id(raw_exp, "exp")
        return
    if raw_target == "":
        raise AlabError("CONFIG_INVALID", "annotation target must be non-empty")
    if command_arg(args, "--exp"):
        raise AlabError("CONFIG_INVALID", "--exp is only valid for targetless annotations")
    if raw_target.startswith("exp:"):
        require_complete_id(raw_target[4:], "exp")
        return
    if raw_target.startswith("run:"):
        require_complete_id(raw_target[4:], "run")
        return
    if raw_target.startswith("artifact:"):
        require_complete_id(raw_target[9:], "art")
        return
    if raw_target.startswith("path:") or raw_target.startswith("lines:"):
        _target_kind, _sep, rest = raw_target.partition(":")
        if "@" in rest and ":" in rest:
            exp_part, _rest_after_exp = rest.split(":", 1)
            exp_id, _at, _commitish = exp_part.partition("@")
            require_complete_id(exp_id, "exp")


def _assert_clean_worktree(path: Path) -> None:
    status = run_cmd(["git", "status", "--porcelain"], cwd=path, check=False).stdout.decode("utf-8", errors="replace")
    visible_changes = [line for line in status.splitlines() if ".alab/" not in line]
    if visible_changes:
        raise AlabError("GIT_STATE_INVALID", "path/line annotation shorthand requires a clean experiment worktree")


def _git_object_type_at_commit(home: Home, project_id: str, commit: str, repo_path: str) -> str:
    _project_root, repo_git, _artifact_store = _project_paths(home, project_id)
    result = run_cmd(["git", f"--git-dir={repo_git}", "cat-file", "-t", f"{commit}:{repo_path}"], check=False)
    if result.returncode != 0:
        raise AlabError("CONFIG_INVALID", "annotation target path does not exist at resolved commit")
    object_type = result.stdout.decode("utf-8", errors="replace").strip()
    if object_type not in {"blob", "tree"}:
        raise AlabError("CONFIG_INVALID", "annotation target path is not a file or directory")
    return object_type


def _git_blob_bytes_at_commit(home: Home, project_id: str, commit: str, repo_path: str) -> bytes:
    _project_root, repo_git, _artifact_store = _project_paths(home, project_id)
    result = run_cmd(["git", f"--git-dir={repo_git}", "cat-file", "-p", f"{commit}:{repo_path}"], check=False)
    if result.returncode != 0:
        raise AlabError("CONFIG_INVALID", "annotation target file cannot be read at resolved commit")
    return result.stdout


def _assert_annotation_path_target(home: Home, project_id: str, commit: str, repo_path: str, line_range: dict[str, int] | None) -> None:
    object_type = _git_object_type_at_commit(home, project_id, commit, repo_path)
    if line_range is None:
        return
    if object_type != "blob":
        raise AlabError("CONFIG_INVALID", "line annotation target must be a file")
    data = _git_blob_bytes_at_commit(home, project_id, commit, repo_path)
    line_count = len(data.splitlines())
    if line_range["end"] > line_count:
        raise AlabError("CONFIG_INVALID", "line range exceeds target file length")


def _assert_annotation_repo_path(value: Any, *, label: str, code: str) -> None:
    if not isinstance(value, str) or not value:
        raise AlabError(code, f"{label} must be relative")
    if "\0" in value or "\n" in value or "\r" in value or "\\" in value:
        raise AlabError(code, f"{label} must be relative")
    if len(value) >= 3 and value[1] == ":" and value[2] == "/":
        raise AlabError(code, f"{label} must be relative")
    if value.startswith("/"):
        raise AlabError(code, f"{label} must be relative")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise AlabError(code, f"{label} must be relative")


def _resolve_annotation_target(args: list[str], req: Request, conn, project_id: str, actor: Actor) -> dict[str, Any]:
    require_options_at_most_once(args, ("--target", "--exp"))
    raw_target = command_arg(args, "--target")
    if raw_target is None:
        if actor.actor_type == "token":
            if command_arg(args, "--exp"):
                raise AlabError("CONFIG_INVALID", "--exp is only valid with admin/root")
            exp_id = actor.exp_id
        else:
            exp_option = command_arg(args, "--exp")
            if exp_option:
                exp_id = require_complete_id(exp_option, "exp")
            elif req.context and req.context.context_type == "experiment" and req.context.project_id == project_id:
                exp_id = req.context.exp_id
            else:
                raise AlabError("CONFIG_INVALID", "targetless annotation requires --exp outside experiment context")
        exp = _exp_row(conn, project_id, exp_id)
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, exp_id):
            raise AlabError("SCOPE_VIOLATION", "target experiment is not visible to this token")
        return {"schema_version": 1, "target_type": "none", "target_id": "", "exp_id": exp["exp_id"], "commit": None}
    if raw_target == "":
        raise AlabError("CONFIG_INVALID", "annotation target must be non-empty")
    if raw_target.startswith("exp:"):
        exp_id = require_complete_id(raw_target[4:], "exp")
        exp = _exp_row(conn, project_id, exp_id)
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, exp_id):
            raise AlabError("SCOPE_VIOLATION", "target experiment is not visible to this token")
        commit = exp["latest_commit"] or exp["final_commit"] or exp["baseline_commit"]
        return {"schema_version": 1, "target_type": "experiment", "target_id": exp_id, "exp_id": exp_id, "commit": commit}
    if raw_target.startswith("run:"):
        run_id = require_complete_id(raw_target[4:], "run")
        row = one(conn, "SELECT * FROM runs WHERE project_id = ? AND run_id = ?", (project_id, run_id))
        if row is None:
            raise AlabError("RUN_NOT_FOUND", "target run not found")
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, row["exp_id"]):
            raise AlabError("SCOPE_VIOLATION", "target run is not visible to this token")
        return {"schema_version": 1, "target_type": "run", "target_id": run_id, "exp_id": row["exp_id"], "commit": row["commit_sha"]}
    if raw_target.startswith("artifact:"):
        artifact_id = require_complete_id(raw_target[9:], "art")
        row = one(conn, "SELECT * FROM artifacts WHERE project_id = ? AND artifact_id = ?", (project_id, artifact_id))
        if row is None:
            raise AlabError("ARTIFACT_NOT_FOUND", "target artifact not found")
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, row["exp_id"]):
            raise AlabError("SCOPE_VIOLATION", "target artifact is not visible to this token")
        return {"schema_version": 1, "target_type": "artifact", "target_id": artifact_id, "exp_id": row["exp_id"], "commit": None}
    if raw_target.startswith("path:") or raw_target.startswith("lines:"):
        target_kind, _, rest = raw_target.partition(":")
        if "@" in rest and ":" in rest:
            exp_part, rest_after_exp = rest.split(":", 1)
            exp_id, _at, commitish = exp_part.partition("@")
            exp = _exp_row(conn, project_id, exp_id)
            commit = _resolve_exp_commit(
                conn,
                req.globals.home,
                project_id,
                exp,
                commitish or "latest",
                allow_head_alias=True,
            )
            repo_part = rest_after_exp
        else:
            if not req.context or req.context.context_type != "experiment":
                raise AlabError("CONFIG_INVALID", "path/lines shorthand requires an experiment context")
            exp_id = req.context.exp_id
            exp = _exp_row(conn, project_id, exp_id)
            _assert_clean_worktree(req.context.path)
            commit = run_cmd(["git", "rev-parse", "HEAD"], cwd=req.context.path).stdout.decode("utf-8", errors="replace").strip()
            repo_part = rest
        if actor.actor_type == "token" and not _exp_visible(conn, project_id, actor, exp_id):
            raise AlabError("SCOPE_VIOLATION", "target path is not visible to this token")
        line_range = None
        repo_path = repo_part
        if target_kind == "lines":
            repo_path, _sep, range_text = repo_part.rpartition(":")
            start_text, _dash, end_text = range_text.partition("-")
            try:
                start = int(start_text)
                end = int(end_text)
            except ValueError as exc:
                raise AlabError("CONFIG_INVALID", "line target requires start-end") from exc
            if start < 1 or end < start:
                raise AlabError("CONFIG_INVALID", "invalid line range")
            line_range = {"start": start, "end": end}
        _assert_annotation_repo_path(repo_path, label="annotation repo path", code="CONFIG_INVALID")
        _assert_annotation_path_target(req.globals.home, project_id, commit, repo_path, line_range)
        target_id = f"{exp_id}:{commit}:{repo_path}"
        data = {"schema_version": 1, "target_type": target_kind, "target_id": target_id, "exp_id": exp_id, "commit": commit, "repo_path": repo_path}
        if line_range:
            data["line_range"] = line_range
        return data
    raise AlabError("CONFIG_INVALID", "invalid annotation target")


def _annotation_visible(row: Any, actor: Actor, visible_exp_ids: set[str] | None = None) -> bool:
    visibility = annotation_visibility_json_obj(row["visibility_json"])
    if actor.actor_type in {"root", "admin"}:
        return True
    target = annotation_target_json_obj(row["target_json"])
    target_visible = _annotation_target_visible(target, actor, visible_exp_ids)
    if visibility.get("scope") == "private":
        return visibility.get("creator_exp_id") == actor.exp_id and target_visible
    return target_visible


def _annotation_target_visible(target: dict[str, Any], actor: Actor, visible_exp_ids: set[str] | None = None) -> bool:
    if actor.actor_type in {"root", "admin"}:
        return True
    exp_id = target.get("exp_id")
    if not exp_id:
        return False
    if visible_exp_ids is None:
        return exp_id == actor.exp_id
    return exp_id in visible_exp_ids


def _annotation_editable(row: Any, actor: Actor, visible_exp_ids: set[str] | None = None) -> bool:
    if actor.actor_type in {"root", "admin"}:
        return True
    target = annotation_target_json_obj(row["target_json"])
    if not _annotation_target_visible(target, actor, visible_exp_ids):
        return False
    visibility = annotation_visibility_json_obj(row["visibility_json"])
    if visibility.get("scope") == "private":
        return visibility.get("creator_exp_id") == actor.exp_id
    return row["created_by_type"] == "token" and row["created_by_id"] == actor.exp_id


def _assert_annotation_scope(row: Any, actor: Actor, *, edit: bool = False, visible_exp_ids: set[str] | None = None) -> None:
    allowed = _annotation_editable(row, actor, visible_exp_ids) if edit else _annotation_visible(row, actor, visible_exp_ids)
    if not allowed:
        raise AlabError("SCOPE_VIOLATION", "annotation is not visible in this context")


def _annotation_target_exp_id(target: dict[str, Any]) -> str:
    exp_id = target.get("exp_id")
    if not exp_id:
        raise AlabError("CONFIG_INVALID", "annotation target must resolve to exactly one experiment")
    return exp_id


def _annotation_block(conn, row: Any, *, history: bool = False) -> ResultBlock:
    revision = one(conn, "SELECT * FROM annotation_revisions WHERE annotation_id = ? AND revision = ?", (row["annotation_id"], row["current_revision"]))
    visibility = annotation_visibility_json_obj(row["visibility_json"])
    revisions: list[str] = []
    if history:
        revisions = [
            f"{rev['revision']}:{rev['created_at']}"
            for rev in all_rows(conn, "SELECT * FROM annotation_revisions WHERE annotation_id = ? ORDER BY revision", (row["annotation_id"],))
        ]
    return ResultBlock(
        "annotation",
        [
            ("annotation id", row["annotation_id"]),
            ("title", row["title"]),
            ("target type", row["target_type"]),
            ("target id", row["target_id"]),
            ("resolved commit", row["resolved_commit"]),
            ("status", row["status"]),
            ("current revision", row["current_revision"]),
            ("visibility", visibility.get("scope")),
            ("author", revision["author_label"] if revision else None),
            ("body", multiline_text(revision["body"] if revision else None)),
            ("created at", row["created_at"]),
            ("updated at", row["updated_at"]),
            ("revision", revisions),
        ],
    )


def cmd_annotate_add(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--target", "--exp", "--title", "--body", "--body-file", "--body-stdin", "--author", "--private", "--private-to-exp"))
    require_options_at_most_once(args, ("--target", "--exp", "--title", "--body", "--body-file", "--body-stdin", "--author", "--private", "--private-to-exp"))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_annotation_actor(req, project_id)
    private_exp = _annotation_private_exp_selector(args, actor)
    require_positional_count(args, 0, "annotate add accepts no positional arguments")
    _validate_annotation_target_selector_ids(args)
    if command_arg(args, "--target") is None:
        if actor.actor_type == "token" and command_arg(args, "--exp"):
            raise AlabError("CONFIG_INVALID", "--exp is only valid with admin/root")
        if (
            actor.actor_type in {"root", "admin"}
            and not command_arg(args, "--exp")
            and not (req.context and req.context.context_type == "experiment" and req.context.project_id == project_id)
        ):
            raise AlabError("CONFIG_INVALID", "targetless annotation requires --exp outside experiment context")
    title = _read_annotation_title(args, required=command_arg(args, "--target") is None)
    body = _read_annotation_body(args)
    conn = require_home(req.globals.home)
    try:
        _project_row(conn, project_id)
        target = _resolve_annotation_target(args, req, conn, project_id, actor)
        if private_exp:
            _exp_row(conn, project_id, private_exp)
        target_exp_id = _annotation_target_exp_id(target)
        _assert_text_has_no_secret(conn, project_id, target_exp_id, body, "annotation body")
        if title is not None:
            _assert_text_has_no_secret(conn, project_id, target_exp_id, title, "annotation title")
    finally:
        conn.close()
    visibility = {"schema_version": 1, "scope": "private" if private_exp else "project", "constraints": {}}
    if private_exp:
        visibility["creator_exp_id"] = private_exp
    target_json = canonical_json(annotation_target_json_obj(canonical_json(target)))
    visibility_json = canonical_json(annotation_visibility_json_obj(canonical_json(visibility)))
    with Database(req.globals.home).tx() as tx:
        now = utc_now()
        annotation_id = new_id("ann", target["target_type"])
        creator_id = actor.exp_id if actor.actor_type == "token" else actor.credential_id
        tx.execute(
            """
            INSERT INTO annotations(annotation_id, project_id, title, target_type, target_id, target_json,
              resolved_commit, current_revision, visibility_json, status, created_by_type, created_by_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 'active', ?, ?, ?, ?)
            """,
            (
                annotation_id,
                project_id,
                title,
                target["target_type"],
                target["target_id"],
                target_json,
                target.get("commit"),
                visibility_json,
                actor.actor_type,
                creator_id,
                now,
                now,
            ),
        )
        tx.execute(
            """
            INSERT INTO annotation_revisions(annotation_id, revision, body, author_label, created_at, created_by_type, created_by_id)
            VALUES (?, 1, ?, ?, ?, ?, ?)
            """,
            (annotation_id, body, command_arg(args, "--author"), now, actor.actor_type, creator_id),
        )
    return [
        ResultBlock(
            "annotation",
            [
                ("annotation id", annotation_id),
                ("title", title),
                ("target type", target["target_type"]),
                ("target id", target["target_id"]),
                ("resolved commit", target.get("commit")),
                ("revision", 1),
                ("visibility", visibility["scope"]),
                ("created at", now),
            ],
        )
    ]


def _annotation_row(conn, project_id: str, annotation_id: str | None, actor: Actor | None = None) -> Any:
    annotation_id = _complete_id_or_missing(annotation_id, prefix="ann", code="ANNOTATION_NOT_FOUND", label="annotation id")
    row = one(conn, "SELECT * FROM annotations WHERE project_id = ? AND annotation_id = ?", (project_id, annotation_id))
    if row is None:
        if actor and actor.actor_type == "token":
            raise AlabError("SCOPE_VIOLATION", "annotation is not visible or not found")
        raise AlabError("ANNOTATION_NOT_FOUND", "annotation not found")
    return row


def cmd_annotate_edit(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--body", "--body-file", "--body-stdin", "--author"))
    require_options_at_most_once(args, ("--body", "--body-file", "--body-stdin", "--author"))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_annotation_actor(req, project_id)
    annotation_id = optional_positional_selector(args, "annotate edit accepts exactly one annotation id")
    body = _read_annotation_body(args)
    with Database(req.globals.home).tx() as conn:
        row = _annotation_row(conn, project_id, annotation_id, actor)
        _assert_annotation_scope(row, actor, edit=True, visible_exp_ids=_visible_exp_ids(conn, project_id, actor))
        target = annotation_target_json_obj(row["target_json"])
        _assert_text_has_no_secret(conn, project_id, target.get("exp_id"), body, "annotation body")
        revision = int(row["current_revision"]) + 1
        now = utc_now()
        creator_id = actor.exp_id if actor.actor_type == "token" else actor.credential_id
        conn.execute(
            "INSERT INTO annotation_revisions(annotation_id, revision, body, author_label, created_at, created_by_type, created_by_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row["annotation_id"], revision, body, command_arg(args, "--author"), now, actor.actor_type, creator_id),
        )
        conn.execute("UPDATE annotations SET current_revision = ?, updated_at = ? WHERE annotation_id = ?", (revision, now, row["annotation_id"]))
    return [ResultBlock("annotation", [("annotation id", annotation_id), ("revision", revision), ("updated at", now)])]


def _set_annotation_status(args: list[str], req: Request, status: str) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_annotation_actor(req, project_id)
    annotation_id = optional_positional_selector(args, "annotation status accepts exactly one annotation id")
    with Database(req.globals.home).tx() as conn:
        row = _annotation_row(conn, project_id, annotation_id, actor)
        _assert_annotation_scope(row, actor, edit=True, visible_exp_ids=_visible_exp_ids(conn, project_id, actor))
        previous = row["status"]
        now = utc_now() if previous != status else None
        if previous != status:
            conn.execute("UPDATE annotations SET status = ?, updated_at = ? WHERE annotation_id = ?", (status, now, row["annotation_id"]))
            audit(
                conn,
                action="archive" if status == "archived" else "unarchive",
                object_type="annotation",
                object_id=row["annotation_id"],
                actor=actor,
                project_id=project_id,
                exp_id=annotation_target_json_obj(row["target_json"]).get("exp_id"),
                metadata={
                    "schema_version": 1,
                    "previous_status": previous,
                    "annotation_status": status,
                    "archived_at" if status == "archived" else "unarchived_at": now,
                },
            )
        return [
            ResultBlock(
                "annotation",
                [
                    ("annotation id", row["annotation_id"]),
                    ("previous status", previous),
                    ("annotation status", status),
                    ("archived at" if status == "archived" else "unarchived at", now),
                ],
            )
        ]


def cmd_annotate_archive(args: list[str], req: Request) -> list[ResultBlock]:
    return _set_annotation_status(args, req, "archived")


def cmd_annotate_unarchive(args: list[str], req: Request) -> list[ResultBlock]:
    return _set_annotation_status(args, req, "active")


def cmd_annotate_remove(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--dry-run", "--force", "--confirm", "--reason"))
    require_options_at_most_once(args, ("--dry-run", "--reason"))
    require_dry_run_unforced(args)
    project_id = _project_id_from_request(args, req)
    actor = _authorize_annotation_actor(req, project_id)
    annotation_id = optional_positional_selector(args, "annotate remove accepts exactly one annotation id")
    dry_run = flag(args, "--dry-run")
    with Database(req.globals.home).tx() as conn:
        row = _annotation_row(conn, project_id, annotation_id, actor)
        _assert_annotation_scope(row, actor, edit=True, visible_exp_ids=_visible_exp_ids(conn, project_id, actor))
        blockers = [] if row["status"] == "archived" else ["target_not_archived"]
        revision_count = one(conn, "SELECT count(*) AS c FROM annotation_revisions WHERE annotation_id = ?", (row["annotation_id"],))["c"]
        reason = _lifecycle_reason(args)
        if dry_run:
            return [
                ResultBlock(
                    "annotation",
                    [
                        ("annotation id", row["annotation_id"]),
                        ("dry run", True),
                        ("removed", False),
                        ("audit id", None),
                        ("blocker", blockers),
                        ("deleted revisions", revision_count),
                        ("deleted filesystem paths", 0),
                    ],
                )
            ]
        require_force_confirm(args, row["annotation_id"], "annotation remove requires --force and matching --confirm")
        if blockers:
            raise AlabError("RESOURCE_BUSY", ", ".join(blockers))
        audit_id = audit(
            conn,
            action="remove",
            object_type="annotation",
            object_id=row["annotation_id"],
            actor=actor,
            project_id=project_id,
            exp_id=annotation_target_json_obj(row["target_json"]).get("exp_id"),
            reason=reason,
            metadata={
                "schema_version": 1,
                "deleted_revision_count": revision_count,
                "filesystem_target_count": 0,
                "filesystem_absent_count": 0,
                "trash": [],
            },
        )
        conn.execute("DELETE FROM annotation_revisions WHERE annotation_id = ?", (row["annotation_id"],))
        conn.execute("DELETE FROM annotations WHERE annotation_id = ?", (row["annotation_id"],))
    return [
        ResultBlock(
            "annotation",
            [
                ("annotation id", annotation_id),
                ("dry run", False),
                ("removed", True),
                ("audit id", audit_id),
                ("blocker", []),
                ("deleted revisions", revision_count),
                ("deleted filesystem paths", 0),
                ("trash cleanup pending", False),
            ],
        )
    ]


def cmd_observe_annotations_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--include-archived",
            "--target-type",
            "--target-id",
            "--target",
            "--created-by",
            "--private",
            "--author",
            "--query",
            "--history",
            "--created-after",
            "--created-before",
            "--updated-after",
            "--updated-before",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    require_options_at_most_once(
        args,
        (
            "--include-archived",
            "--target-type",
            "--target-id",
            "--target",
            "--created-by",
            "--private",
            "--author",
            "--query",
            "--history",
            "--created-after",
            "--created-before",
            "--updated-after",
            "--updated-before",
            "--sort",
            "--limit",
            "--offset",
        ),
    )
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    require_positional_count(args, 0, "annotations list accepts no positional arguments")
    if command_arg(args, "--target-id") and command_arg(args, "--target"):
        raise AlabError("CONFIG_INVALID", "annotations list accepts only one of --target-id or --target")
    conn = require_home(req.globals.home)
    try:
        clauses = ["a.project_id = ?"]
        params: list[Any] = [project_id]
        if not flag(args, "--include-archived"):
            clauses.append("a.status = 'active'")
        target_type = _require_option_choice(command_arg(args, "--target-type"), "--target-type", ANNOTATION_TARGET_TYPES)
        if target_type:
            clauses.append("a.target_type = ?")
            params.append(target_type)
        target_id = _annotation_target_id_filter(target_type, command_arg(args, "--target-id") or command_arg(args, "--target"))
        if target_id:
            clauses.append("a.target_id = ?")
            params.append(target_id)
        created_by = _annotation_created_by_filter(command_arg(args, "--created-by"))
        if created_by:
            clauses.append("a.created_by_id = ?")
            params.append(created_by)
        _require_ordered_time_range(args, "--created-after", "--created-before")
        _require_ordered_time_range(args, "--updated-after", "--updated-before")
        for option, column, op in [
            ("--created-after", "a.created_at", ">="),
            ("--created-before", "a.created_at", "<="),
            ("--updated-after", "a.updated_at", ">="),
            ("--updated-before", "a.updated_at", "<="),
        ]:
            _append_time_filter(args, clauses, params, option, column, op)
        visible_ids = _visible_exp_ids(conn, project_id, actor)
        if visible_ids is not None:
            if not visible_ids:
                clauses.append("1 = 0")
            else:
                target_clauses = []
                for visible_exp_id in sorted(visible_ids):
                    target_clauses.append("a.target_json LIKE ?")
                    params.append(f'%"exp_id":"{visible_exp_id}"%')
                clauses.append(f"({' OR '.join(target_clauses)})")
                clauses.append(
                    "(a.visibility_json LIKE ? OR (a.visibility_json LIKE ? AND a.visibility_json LIKE ?))"
                )
                params.extend(
                    (
                        '%"scope":"project"%',
                        '%"scope":"private"%',
                        f'%"creator_exp_id":"{actor.exp_id}"%',
                    )
                )
        if flag(args, "--private"):
            clauses.append("a.visibility_json LIKE ?")
            params.append('%"scope":"private"%')
        author = command_arg(args, "--author")
        query = command_arg(args, "--query")
        join_revision = bool(author or query)
        if author or query:
            if author:
                clauses.append("ar.author_label = ?")
                params.append(author)
            if query:
                _register_observe_text_predicates(conn)
                clauses.append("(alab_casefold_contains(COALESCE(a.title, ''), ?) = 1 OR alab_casefold_contains(ar.body, ?) = 1)")
                params.extend([query, query])
        order_sql, order_params = _sql_order_limit_clause(
            args,
            default="updated:desc",
            subject="annotations",
            allowed={
                "created": "a.created_at",
                "updated": "a.updated_at",
                "title": "LOWER(a.title)",
                "target-type": "LOWER(a.target_type)",
                "target-id": "a.target_id",
                "status": "LOWER(a.status)",
                "created-by": "a.created_by_id",
            },
            tie_breakers=("a.updated_at DESC", "a.rowid ASC"),
        )
        join_sql = " JOIN annotation_revisions ar ON ar.annotation_id = a.annotation_id AND ar.revision = a.current_revision" if join_revision else ""
        rows = all_rows(conn, f"SELECT a.* FROM annotations a{join_sql} WHERE {' AND '.join(clauses)} {order_sql}", (*params, *order_params))
        return [_annotation_block(conn, row, history=flag(args, "--history")) for row in rows]
    finally:
        conn.close()


def cmd_observe_annotations_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--history"))
    require_options_at_most_once(args, ("--history",))
    project_id = _project_id_from_request(args, req)
    actor = _authorize_observe(req, project_id)
    annotation_id = optional_positional_selector(args, "annotations show accepts exactly one annotation id")
    conn = require_home(req.globals.home)
    try:
        row = _annotation_row(conn, project_id, annotation_id, actor)
        if not _annotation_visible(row, actor, _visible_exp_ids(conn, project_id, actor)):
            raise AlabError("SCOPE_VIOLATION", "annotation is not visible or not found")
        return [_annotation_block(conn, row, history=flag(args, "--history"))]
    finally:
        conn.close()
