from __future__ import annotations

import os

from .auth import Actor, verify_raw_credential
from .db import connect_initialized
from .errors import AlabError
from .home import Home
from .service_models import Request


def require_home(home: Home):
    return connect_initialized(home)


def require_actor(req: Request, allowed: str | tuple[str, ...], project_id: str | None = None) -> Actor:
    conn = require_home(req.globals.home)
    try:
        raw = req.globals.key
        if raw is None:
            raw = os.environ.get("ALAB_KEY") or None
        if raw is None:
            raise AlabError("AUTH_REQUIRED", "credential is required")
        return verify_raw_credential(conn, raw, required=allowed, project_id=project_id)
    finally:
        conn.close()


def _actor_is_project_admin_or_root(actor: Actor | None, project_id: str | None) -> bool:
    if actor is None:
        return False
    if actor.actor_type == "root":
        return True
    return bool(project_id and actor.actor_type == "admin" and actor.project_id == project_id)
