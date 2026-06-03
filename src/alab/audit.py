from __future__ import annotations

from typing import Any

from .db import all_rows, canonical_json, one
from .errors import AlabError
from .ids import require_complete_id
from .rendering import ResultBlock
from .service_args import (
    _append_time_filter,
    _parse_audit_limit_offset,
    _require_option_choice,
    _require_ordered_time_range,
    command_arg,
    optional_positional_selector,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_auth import require_actor, require_home
from .service_contracts import audit_deleted_ids_json_obj, audit_metadata_json_obj
from .service_models import (
    AUDIT_ACTIONS,
    AUDIT_OBJECT_ID_LITERALS,
    AUDIT_OBJECT_ID_PREFIXES,
    AUDIT_OBJECT_TYPES,
    Request,
)


def _complete_id_or_missing(value: str | None, *, prefix: str, code: str, label: str) -> str:
    if not value:
        raise AlabError(code, f"{label} is required")
    return require_complete_id(value, prefix)


def _complete_id_option(args: list[str], option: str, prefix: str) -> str | None:
    require_options_at_most_once(args, (option,))
    value = command_arg(args, option)
    return require_complete_id(value, prefix) if value else None


def _audit_object_id_filter(object_type: str | None, object_id: str | None) -> str | None:
    if not object_id:
        return None
    if not object_type:
        literal_ids = set().union(*AUDIT_OBJECT_ID_LITERALS.values())
        if object_id in literal_ids:
            return object_id
        return require_complete_id(object_id)
    if object_type in AUDIT_OBJECT_ID_PREFIXES:
        return require_complete_id(object_id, AUDIT_OBJECT_ID_PREFIXES[object_type])
    if object_type in AUDIT_OBJECT_ID_LITERALS and object_id not in AUDIT_OBJECT_ID_LITERALS[object_type]:
        raise AlabError("CONFIG_INVALID", f"--object-id must be one of {', '.join(sorted(AUDIT_OBJECT_ID_LITERALS[object_type]))}")
    return object_id


def cmd_audit_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(
        args,
        (
            "--project",
            "--object-type",
            "--object-id",
            "--action",
            "--actor",
            "--created-after",
            "--created-before",
            "--limit",
            "--offset",
        ),
    )
    require_options_at_most_once(
        args,
        (
            "--project",
            "--object-type",
            "--object-id",
            "--action",
            "--actor",
            "--created-after",
            "--created-before",
            "--limit",
            "--offset",
        ),
    )
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    if project_id:
        project_id = require_complete_id(project_id, "proj")
    if project_id:
        require_actor(req, ("root", "admin"), project_id=project_id)
    else:
        require_actor(req, "root")
    require_positional_count(args, 0, "audit list accepts no positional arguments")
    conn = require_home(req.globals.home)
    try:
        clauses: list[str] = []
        params: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        actor_filter = _complete_id_option(args, "--actor", "cred")
        object_type_filter = _require_option_choice(command_arg(args, "--object-type"), "--object-type", AUDIT_OBJECT_TYPES)
        object_id_filter = _audit_object_id_filter(object_type_filter, command_arg(args, "--object-id"))
        action_filter = _require_option_choice(command_arg(args, "--action"), "--action", AUDIT_ACTIONS)
        if action_filter:
            clauses.append("action = ?")
            params.append(action_filter)
        if object_type_filter:
            clauses.append("object_type = ?")
            params.append(object_type_filter)
        if object_id_filter:
            clauses.append("object_id = ?")
            params.append(object_id_filter)
        if actor_filter:
            clauses.append("actor_credential_id = ?")
            params.append(actor_filter)
        _require_ordered_time_range(args, "--created-after", "--created-before")
        _append_time_filter(args, clauses, params, "--created-after", "created_at", ">=")
        _append_time_filter(args, clauses, params, "--created-before", "created_at", "<=")
        limit, offset = _parse_audit_limit_offset(args)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = all_rows(conn, f"SELECT * FROM audit_events{where} ORDER BY created_at DESC LIMIT ? OFFSET ?", tuple(params + [limit, offset]))
        return [
            ResultBlock(
                "audit",
                [
                    ("audit id", row["audit_id"]),
                    ("project id", row["project_id"]),
                    ("exp id", row["exp_id"]),
                    ("actor type", row["actor_type"]),
                    ("actor credential id", row["actor_credential_id"]),
                    ("action", row["action"]),
                    ("object type", row["object_type"]),
                    ("object id", row["object_id"]),
                    ("cascade", bool(row["cascade"])),
                    ("reason", row["reason"]),
                    ("created at", row["created_at"]),
                ],
            )
            for row in rows
        ]
    finally:
        conn.close()


def cmd_audit_show(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    require_options_at_most_once(args, ("--project",))
    audit_id = optional_positional_selector(args, "audit show accepts exactly one audit id")
    audit_id = _complete_id_or_missing(audit_id, prefix="aud", code="AUDIT_NOT_FOUND", label="audit id")
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    if project_id:
        project_id = require_complete_id(project_id, "proj")
    if project_id:
        require_actor(req, ("root", "admin"), project_id=project_id)
    else:
        require_actor(req, "root")
    conn = require_home(req.globals.home)
    try:
        if project_id:
            row = one(conn, "SELECT * FROM audit_events WHERE audit_id = ? AND project_id = ?", (audit_id, project_id))
        else:
            row = one(conn, "SELECT * FROM audit_events WHERE audit_id = ?", (audit_id,))
        if row is None:
            raise AlabError("AUDIT_NOT_FOUND", "audit event not found")
        deleted_ids_json = canonical_json(audit_deleted_ids_json_obj(row["deleted_ids_json"]))
        metadata_json = canonical_json(audit_metadata_json_obj(row["metadata_json"]))
        return [
            ResultBlock(
                "audit",
                [
                    ("audit id", row["audit_id"]),
                    ("project id", row["project_id"]),
                    ("exp id", row["exp_id"]),
                    ("actor type", row["actor_type"]),
                    ("actor credential id", row["actor_credential_id"]),
                    ("action", row["action"]),
                    ("object type", row["object_type"]),
                    ("object id", row["object_id"]),
                    ("cascade", bool(row["cascade"])),
                    ("reason", row["reason"]),
                    ("deleted ids", deleted_ids_json),
                    ("sanitized metadata", metadata_json),
                    ("created at", row["created_at"]),
                ],
            )
        ]
    finally:
        conn.close()
