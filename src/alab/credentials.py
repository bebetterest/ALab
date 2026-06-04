from __future__ import annotations

from typing import Any

from .auth import create_credential, new_home_id
from .db import Database, all_rows, one
from .errors import AlabError
from .home import ensure_layout, is_initialized
from .ids import require_complete_id
from .rendering import ResultBlock
from .service_args import (
    _require_option_choice,
    command_arg,
    flag,
    optional_positional_selector,
    require_known_options,
    require_options_at_most_once,
    require_positional_count,
)
from .service_audit import audit
from .service_auth import require_actor, require_home
from .service_models import KEY_ROLES, Request
from .timeutil import utc_now


def _project_row(conn, project_id: str | None) -> Any:
    if project_id is None:
        raise AlabError("CONTEXT_NOT_FOUND", "project id is required")
    project_id = require_complete_id(project_id, "proj")
    row = one(conn, "SELECT * FROM projects WHERE project_id = ?", (project_id,))
    if row is None:
        raise AlabError("PROJECT_NOT_FOUND", "project not found")
    return row


def _complete_id_or_missing(value: str | None, *, prefix: str, code: str, label: str) -> str:
    if not value:
        raise AlabError(code, f"{label} is required")
    return require_complete_id(value, prefix)


def cmd_auth_init(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ())
    require_positional_count(args, 0, "auth init accepts no positional arguments")
    home = req.globals.home
    if home.path.exists() and any(home.path.iterdir()) and not is_initialized(home):
        raise AlabError("HOME_EXISTS", "home exists and is not an initialized ALab home")
    if is_initialized(home):
        raise AlabError("HOME_EXISTS", "ALab home is already initialized")
    ensure_layout(home)
    db = Database(home)
    db.migrate()
    with db.tx() as conn:
        now = utc_now()
        home_id = new_home_id()
        conn.execute(
            "INSERT INTO homes(home_id, schema_version, created_at, updated_at) VALUES (?, 1, ?, ?)",
            (home_id, now, now),
        )
        _, raw_root = create_credential(conn, credential_type="root", metadata={"schema_version": 1})
    return [
        ResultBlock(
            "auth",
            [
                ("home", str(home.path)),
                ("home id", home_id),
                ("root key", raw_root),
                ("created", now),
            ],
        )
    ]


def cmd_auth_root_regenerate(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ())
    actor = require_actor(req, "root")
    require_positional_count(args, 0, "auth root regenerate accepts no positional arguments")
    db = Database(req.globals.home)
    with db.tx() as conn:
        now = utc_now()
        conn.execute(
            "UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_type = 'root' AND status = 'active'",
            (now,),
        )
        key_id, raw = create_credential(conn, credential_type="root", metadata={"schema_version": 1})
        home_id = one(conn, "SELECT home_id FROM homes LIMIT 1")["home_id"]
        audit(
            conn,
            action="regenerate",
            object_type="credential",
            object_id=key_id,
            actor=actor,
            metadata={
                "schema_version": 1,
                "credential_type": "root",
                "revoked_credential_id": actor.credential_id,
                "created_credential_id": key_id,
                "revoked_at": now,
            },
        )
    return [
        ResultBlock(
            "auth",
            [
                ("home", str(req.globals.home.path)),
                ("home id", home_id),
                ("root key", raw),
                ("revoked key id", actor.credential_id),
                ("created key id", key_id),
            ],
        )
    ]


def cmd_key_create(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--role"))
    require_options_at_most_once(args, ("--project", "--role"))
    actor = require_actor(req, "root")
    require_positional_count(args, 0, "key create accepts no positional arguments")
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    role = _require_option_choice(command_arg(args, "--role", default="admin"), "--role", KEY_ROLES)
    with Database(req.globals.home).tx() as conn:
        _project_row(conn, project_id)
        key_id, raw_admin = create_credential(conn, credential_type="admin", project_id=project_id, metadata={"schema_version": 1, "role": "admin"})
        row = one(conn, "SELECT created_at FROM credentials WHERE credential_id = ?", (key_id,))
        audit(conn, action="add", object_type="credential", object_id=key_id, actor=actor, project_id=project_id)
    return [
        ResultBlock(
            "credential",
            [
                ("project id", project_id),
                ("key id", key_id),
                ("role", role),
                ("admin key", raw_admin),
                ("created", row["created_at"] if row else None),
            ],
        )
    ]


def cmd_key_list(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project", "--root"))
    require_options_at_most_once(args, ("--project", "--root"))
    root_scope = flag(args, "--root")
    explicit_project_id = command_arg(args, "--project")
    project_id = explicit_project_id or (req.context.project_id if req.context else None)
    if root_scope and explicit_project_id:
        raise AlabError("CONFIG_INVALID", "--root conflicts with --project")
    if root_scope:
        require_actor(req, "root")
        require_positional_count(args, 0, "key list accepts no positional arguments", options_with_values=("--project",))
        conn = require_home(req.globals.home)
        try:
            rows = all_rows(conn, "SELECT * FROM credentials WHERE credential_type = 'root' ORDER BY created_at", ())
            return [
                ResultBlock(
                    "credential",
                    [
                        ("key id", row["credential_id"]),
                        ("credential type", row["credential_type"]),
                        ("status", row["status"]),
                        ("created at", row["created_at"]),
                        ("revoked at", row["revoked_at"]),
                    ],
                )
                for row in rows
            ]
        finally:
            conn.close()
    require_actor(req, ("root", "admin"), project_id=project_id)
    require_positional_count(args, 0, "key list accepts no positional arguments", options_with_values=("--project",))
    conn = require_home(req.globals.home)
    try:
        _project_row(conn, project_id)
        rows = all_rows(conn, "SELECT * FROM credentials WHERE credential_type = 'admin' AND project_id = ? ORDER BY created_at", (project_id,))
        return [
            ResultBlock(
                "credential",
                [
                    ("project id", project_id),
                    ("key id", row["credential_id"]),
                    ("role", "admin"),
                    ("status", row["status"]),
                    ("created at", row["created_at"]),
                    ("revoked at", row["revoked_at"]),
                ],
            )
            for row in rows
        ]
    finally:
        conn.close()


def cmd_key_revoke(args: list[str], req: Request) -> list[ResultBlock]:
    require_known_options(args, ("--project",))
    require_options_at_most_once(args, ("--project",))
    actor = require_actor(req, "root")
    key_id = optional_positional_selector(args, "key revoke accepts exactly one key id")
    key_id = _complete_id_or_missing(key_id, prefix="cred", code="CREDENTIAL_NOT_FOUND", label="key id")
    project_id = command_arg(args, "--project") or (req.context.project_id if req.context else None)
    with Database(req.globals.home).tx() as conn:
        row = one(conn, "SELECT * FROM credentials WHERE credential_id = ?", (key_id,))
        if row is None:
            raise AlabError("CREDENTIAL_NOT_FOUND", "credential not found")
        if project_id and row["project_id"] != project_id:
            raise AlabError("CREDENTIAL_NOT_FOUND", "credential not found in project")
        if row["credential_type"] == "root" and row["status"] == "active":
            active_roots = one(conn, "SELECT count(*) AS c FROM credentials WHERE credential_type = 'root' AND status = 'active'")["c"]
            if active_roots <= 1:
                raise AlabError("CONFIG_INVALID", "cannot revoke the only active root key")
        revoked_at = row["revoked_at"] or utc_now()
        if row["status"] != "revoked":
            conn.execute("UPDATE credentials SET status = 'revoked', revoked_at = ? WHERE credential_id = ?", (revoked_at, key_id))
            audit(
                conn,
                action="revoke",
                object_type="credential",
                object_id=key_id,
                actor=actor,
                project_id=row["project_id"],
                exp_id=row["exp_id"],
                metadata={
                    "schema_version": 1,
                    "credential_type": row["credential_type"],
                    "token_mode": row["token_mode"],
                    "previous_status": row["status"],
                    "credential_status": "revoked",
                    "revoked_at": revoked_at,
                },
            )
    return [ResultBlock("credential", [("key id", key_id), ("status", "revoked"), ("revoked at", revoked_at)])]
