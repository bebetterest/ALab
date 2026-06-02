from __future__ import annotations

import json
import os
import secrets
import shutil
from pathlib import Path
from typing import Any

from .db import connect_initialized
from .errors import AlabError
from .home import Home
from .ids import new_id, require_complete_id
from .proc import run_cmd
from .rendering import ResultBlock, multiline_text
from .service_args import (
    _parse_int_option,
    _require_option_choice,
    command_arg,
    flag,
    optional_positional_selector,
    require_exactly_one_option_pair,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_auth import require_actor
from .service_models import Request
from .service_text import (
    _assert_display_name,
    _assert_non_empty_text,
    _assert_utf8_max_bytes,
    _lifecycle_reason,
    _read_text_input_file,
)
from .timeutil import utc_now

FEEDBACK_KINDS = {"suggestion", "question", "bug", "other"}
FEEDBACK_SESSION_ENV_KEYS = (
    "ALAB_SESSION_ID",
    "CODEX_THREAD_ID",
    "CODEX_SESSION_ID",
    "CLAUDE_SESSION_ID",
    "CURSOR_SESSION_ID",
    "TERM_SESSION_ID",
)
FEEDBACK_STATUSES = {"active", "archived"}
FEEDBACK_LIST_DEFAULT_LIMIT = 100
FEEDBACK_LIST_MAX_LIMIT = 500


def _feedback_role(req: Request) -> str:
    if req.actor:
        if req.actor.actor_type == "token" and req.actor.token_mode:
            return f"token:{req.actor.token_mode}"
        return req.actor.actor_type
    if req.context:
        return req.context.context_type
    return "none"


def _feedback_session() -> tuple[str | None, str | None]:
    for key in FEEDBACK_SESSION_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return value, key
    return None, None


def _feedback_git_state_for_path(path: Path) -> tuple[str | None, bool | None]:
    try:
        rev = run_cmd(["git", "rev-parse", "--verify", "HEAD"], cwd=path, check=False)
    except Exception:
        return None, None
    if rev.returncode != 0:
        return None, None
    commit = rev.stdout.decode("utf-8", errors="replace").strip()
    if not commit:
        return None, None
    dirty: bool | None = None
    try:
        status = run_cmd(["git", "status", "--porcelain"], cwd=path, check=False)
    except Exception:
        status = None
    if status is not None and status.returncode == 0:
        dirty = bool(status.stdout)
    return commit, dirty


def _feedback_git_state(req: Request) -> tuple[str | None, bool | None, str | None]:
    checked: set[Path] = set()
    cwd = Path.cwd()
    checked.add(cwd)
    commit, dirty = _feedback_git_state_for_path(cwd)
    if commit:
        return commit, dirty, "cwd"
    if req.context and req.context.path not in checked:
        commit, dirty = _feedback_git_state_for_path(req.context.path)
        if commit:
            return commit, dirty, "context"
    return None, None, None


def _feedback_record_dir(home: Home, created_at: str, feedback_id: str) -> Path:
    stamp = created_at.replace("-", "").replace(":", "")
    return home.feedback_path / f"{stamp}_{feedback_id}"


def _write_feedback_record(home: Home, *, metadata: dict[str, Any], body: str) -> Path:
    feedback_id = metadata["feedback_id"]
    feedback_root = home.feedback_path
    final_dir = _feedback_record_dir(home, metadata["created_at"], feedback_id)
    tmp_dir = feedback_root / f".{final_dir.name}.tmp-{secrets.token_hex(8)}"
    try:
        feedback_root.mkdir(parents=True, exist_ok=True)
        if final_dir.exists():
            raise AlabError("STORAGE_ERROR", f"feedback path already exists: {final_dir}")
        tmp_dir.mkdir(mode=0o700)
        (tmp_dir / "body.md").write_text(body, encoding="utf-8")
        (tmp_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_dir.replace(final_dir)
    except AlabError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    except OSError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise AlabError("STORAGE_ERROR", f"failed to write feedback record: {exc}") from exc
    return final_dir


def _feedback_metadata_path(record_dir: Path) -> Path:
    return record_dir / "metadata.json"


def _feedback_body_path(record_dir: Path) -> Path:
    return record_dir / "body.md"


def _feedback_metadata_with_defaults(metadata: dict[str, Any], *, record_dir: Path) -> dict[str, Any]:
    cleaned = dict(metadata)
    status = cleaned.get("status")
    if status not in FEEDBACK_STATUSES:
        status = "active"
    cleaned["status"] = status
    cleaned.setdefault("archived_at", None)
    cleaned.setdefault("archived_by", None)
    cleaned.setdefault("archive_reason", None)
    cleaned.setdefault("body_path", str(_feedback_body_path(record_dir)))
    return cleaned


def _feedback_metadata_rows(home: Home) -> list[tuple[dict[str, Any], Path]]:
    if not home.feedback_path.exists():
        return []
    rows: list[tuple[dict[str, Any], Path]] = []
    for metadata_path in home.feedback_path.glob("*/metadata.json"):
        if metadata_path.parent.name.startswith("."):
            continue
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        metadata = _feedback_metadata_with_defaults(raw, record_dir=metadata_path.parent)
        feedback_id = metadata.get("feedback_id")
        created_at = metadata.get("created_at")
        if not isinstance(feedback_id, str) or not feedback_id or not isinstance(created_at, str):
            continue
        rows.append((metadata, metadata_path.parent))
    rows.sort(key=lambda item: (str(item[0].get("created_at") or ""), item[1].name), reverse=True)
    return rows


def _find_feedback_record(home: Home, feedback_id: str) -> tuple[dict[str, Any], Path]:
    require_complete_id(feedback_id, "fb")
    for metadata, record_dir in _feedback_metadata_rows(home):
        if metadata.get("feedback_id") == feedback_id:
            return metadata, record_dir
    raise AlabError("FEEDBACK_NOT_FOUND", "feedback id is required" if not feedback_id else "feedback not found")


def _read_feedback_body(record_dir: Path) -> str:
    try:
        return _feedback_body_path(record_dir).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise AlabError("STORAGE_ERROR", "feedback body file is missing") from exc
    except UnicodeDecodeError as exc:
        raise AlabError("STORAGE_ERROR", "feedback body file must be UTF-8") from exc
    except OSError as exc:
        raise AlabError("STORAGE_ERROR", f"failed to read feedback body: {exc}") from exc


def _write_feedback_metadata(record_dir: Path, metadata: dict[str, Any]) -> None:
    metadata_path = _feedback_metadata_path(record_dir)
    tmp_path = record_dir / f".metadata.json.tmp-{secrets.token_hex(8)}"
    try:
        tmp_path.write_text(
            json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(metadata_path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise AlabError("STORAGE_ERROR", f"failed to update feedback metadata: {exc}") from exc


def _feedback_matches(metadata: dict[str, Any], body: str, query: str | None) -> bool:
    if query is None:
        return True
    needle = query.casefold()
    metadata_text = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    return needle in metadata_text.casefold() or needle in body.casefold()


def _feedback_result_fields(metadata: dict[str, Any], record_dir: Path) -> list[tuple[str, Any]]:
    return [
        ("feedback id", metadata.get("feedback_id")),
        ("kind", metadata.get("kind")),
        ("title", metadata.get("title")),
        ("status", metadata.get("status")),
        ("created at", metadata.get("created_at")),
        ("archived at", metadata.get("archived_at")),
        ("role", metadata.get("role")),
        ("session id", metadata.get("session_id")),
        ("commit", metadata.get("git_commit")),
        ("path", str(record_dir)),
    ]


def cmd_feedback(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--body", "--body-file", "--kind", "--title"))
    require_options_at_most_once(args, ("--body", "--body-file", "--kind", "--title"))
    require_positional_count(args, 0, "feedback accepts no positional arguments")
    require_exactly_one_option_pair(args, "--body", "--body-file", "feedback requires exactly one of --body or --body-file")
    if not req.globals.home.db_path.exists():
        raise AlabError("CONTEXT_NOT_FOUND", "ALab home is not initialized", "alab auth init")
    body_file = command_arg(args, "--body-file")
    body = _read_text_input_file(body_file, "feedback body") if body_file else command_arg(args, "--body") or ""
    _assert_non_empty_text("feedback body", body)
    _assert_utf8_max_bytes("feedback body", body, 65536)
    kind = _require_option_choice(command_arg(args, "--kind", default="suggestion"), "--kind", FEEDBACK_KINDS)
    if kind is None:
        kind = "suggestion"
    title = command_arg(args, "--title")
    if title is not None:
        _assert_display_name("feedback title", title)
    conn = connect_initialized(req.globals.home)
    conn.close()
    created_at = utc_now()
    feedback_id = new_id("fb", kind)
    role = _feedback_role(req)
    session_id, session_source = _feedback_session()
    git_commit, git_dirty, git_commit_source = _feedback_git_state(req)
    final_dir = _feedback_record_dir(req.globals.home, created_at, feedback_id)
    body_path = final_dir / "body.md"
    metadata = {
        "schema_version": 1,
        "feedback_id": feedback_id,
        "kind": kind,
        "title": title,
        "created_at": created_at,
        "status": "active",
        "archived_at": None,
        "archived_by": None,
        "archive_reason": None,
        "role": role,
        "actor_type": req.actor.actor_type if req.actor else None,
        "actor_credential_id": req.actor.credential_id if req.actor else None,
        "actor_project_id": req.actor.project_id if req.actor else None,
        "actor_exp_id": req.actor.exp_id if req.actor else None,
        "token_mode": req.actor.token_mode if req.actor else None,
        "context_type": req.context.context_type if req.context else None,
        "context_project_id": req.context.project_id if req.context else None,
        "context_exp_id": req.context.exp_id if req.context else None,
        "context_token_id": req.context.token_id if req.context else None,
        "cwd": str(Path.cwd()),
        "session_id": session_id,
        "session_source": session_source,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "git_commit_source": git_commit_source,
        "alab_home": str(req.globals.home.path),
        "body_path": str(body_path),
    }
    final_dir = _write_feedback_record(req.globals.home, metadata=metadata, body=body)
    body_path = final_dir / "body.md"
    metadata_path = final_dir / "metadata.json"
    return [
        ResultBlock(
            "feedback",
            [
                ("feedback id", feedback_id),
                ("kind", kind),
                ("title", title),
                ("created at", created_at),
                ("role", role),
                ("session id", session_id),
                ("commit", git_commit),
                ("path", str(final_dir)),
                ("metadata path", str(metadata_path)),
                ("body path", str(body_path)),
            ],
        )
    ]


def cmd_feedback_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--kind", "--query", "--limit", "--offset", "--include-archived"))
    require_options_at_most_once(args, ("--kind", "--query", "--limit", "--offset", "--include-archived"))
    require_actor(req, "root")
    require_positional_count(args, 0, "feedback list accepts no positional arguments", options_with_values=("--kind", "--query", "--limit", "--offset"))
    kind = command_arg(args, "--kind")
    if kind is not None:
        kind = _require_option_choice(kind, "--kind", FEEDBACK_KINDS)
    query = command_arg(args, "--query")
    limit = _parse_int_option(args, "--limit")
    if limit is None:
        limit = FEEDBACK_LIST_DEFAULT_LIMIT
    if limit < 1 or limit > FEEDBACK_LIST_MAX_LIMIT:
        raise AlabError("CONFIG_INVALID", f"--limit must be between 1 and {FEEDBACK_LIST_MAX_LIMIT}")
    offset = _parse_int_option(args, "--offset")
    if offset is None:
        offset = 0
    if offset < 0:
        raise AlabError("CONFIG_INVALID", "--offset must be non-negative")
    include_archived = flag(args, "--include-archived")

    rows: list[tuple[dict[str, Any], Path]] = []
    for metadata, record_dir in _feedback_metadata_rows(req.globals.home):
        if not include_archived and metadata.get("status") == "archived":
            continue
        if kind is not None and metadata.get("kind") != kind:
            continue
        body = _read_feedback_body(record_dir) if query is not None else ""
        if not _feedback_matches(metadata, body, query):
            continue
        rows.append((metadata, record_dir))
    selected = rows[offset : offset + limit]
    return [ResultBlock("feedback", _feedback_result_fields(metadata, record_dir)) for metadata, record_dir in selected]


def cmd_feedback_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ())
    require_actor(req, "root")
    feedback_id = optional_positional_selector(args, "feedback show accepts exactly one feedback id")
    if feedback_id is None:
        raise AlabError("FEEDBACK_NOT_FOUND", "feedback id is required")
    metadata, record_dir = _find_feedback_record(req.globals.home, feedback_id)
    body = _read_feedback_body(record_dir)
    metadata_path = _feedback_metadata_path(record_dir)
    body_path = _feedback_body_path(record_dir)
    return [
        ResultBlock(
            "feedback",
            [
                ("feedback id", metadata.get("feedback_id")),
                ("kind", metadata.get("kind")),
                ("title", metadata.get("title")),
                ("status", metadata.get("status")),
                ("created at", metadata.get("created_at")),
                ("archived at", metadata.get("archived_at")),
                ("archive reason", metadata.get("archive_reason")),
                ("role", metadata.get("role")),
                ("session id", metadata.get("session_id")),
                ("commit", metadata.get("git_commit")),
                ("path", str(record_dir)),
                ("metadata path", str(metadata_path)),
                ("body path", str(body_path)),
                ("body", multiline_text(body)),
            ],
        )
    ]


def cmd_feedback_archive(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--reason",))
    actor = require_actor(req, "root")
    reason = _lifecycle_reason(args)
    feedback_id = optional_positional_selector(args, "feedback archive accepts exactly one feedback id", options_with_values=("--reason",))
    if feedback_id is None:
        raise AlabError("FEEDBACK_NOT_FOUND", "feedback id is required")
    metadata, record_dir = _find_feedback_record(req.globals.home, feedback_id)
    previous_status = str(metadata.get("status") or "active")
    if previous_status != "archived":
        metadata["status"] = "archived"
        metadata["archived_at"] = utc_now()
        metadata["archived_by"] = actor.credential_id
        metadata["archive_reason"] = reason
        _write_feedback_metadata(record_dir, metadata)
    metadata_path = _feedback_metadata_path(record_dir)
    return [
        ResultBlock(
            "feedback",
            [
                ("feedback id", metadata.get("feedback_id")),
                ("previous status", previous_status),
                ("status", metadata.get("status")),
                ("archived at", metadata.get("archived_at")),
                ("archive reason", metadata.get("archive_reason")),
                ("path", str(record_dir)),
                ("metadata path", str(metadata_path)),
            ],
        )
    ]
