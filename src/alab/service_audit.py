from __future__ import annotations

from typing import Any

from .auth import Actor
from .db import canonical_json
from .ids import new_id
from .service_contracts import audit_deleted_ids_json_obj, audit_metadata_json_obj
from .timeutil import utc_now


def audit(
    conn,
    *,
    action: str,
    object_type: str,
    object_id: str,
    actor: Actor | None,
    audit_id: str | None = None,
    project_id: str | None = None,
    exp_id: str | None = None,
    cascade: bool = False,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    audit_id = audit_id or new_id("aud", action)
    conn.execute(
        """
        INSERT INTO audit_events(audit_id, project_id, exp_id, actor_credential_id, actor_type,
          action, object_type, object_id, cascade, reason, deleted_ids_json, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id,
            project_id,
            exp_id,
            actor.credential_id if actor else None,
            actor.actor_type if actor else "system",
            action,
            object_type,
            object_id,
            1 if cascade else 0,
            reason,
            canonical_json(audit_deleted_ids_json_obj(canonical_json({"schema_version": 1, "counts": {}, "ids": {}}))),
            canonical_json(audit_metadata_json_obj(canonical_json(metadata or {"schema_version": 1}))),
            utc_now(),
        ),
    )
    return audit_id
