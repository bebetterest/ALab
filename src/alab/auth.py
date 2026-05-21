from __future__ import annotations

import hmac
import secrets
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .db import canonical_json, contract_json_obj, one
from .errors import AlabError
from .ids import new_id, random_suffix
from .timeutil import utc_now

ROOT_PREFIX = "alab_root_v1_"
ADMIN_PREFIX = "alab_admin_v1_"
TOKEN_PREFIX = "alab_token_v1_"


@dataclass(frozen=True)
class Actor:
    actor_type: str
    credential_id: str | None = None
    project_id: str | None = None
    exp_id: str | None = None
    token_mode: str | None = None


def _invalid_credential() -> AlabError:
    return AlabError("AUTH_DENIED", "invalid credential")


def _secret() -> str:
    return secrets.token_hex(32)


def _verifier(secret: str, salt: bytes) -> bytes:
    return hmac.new(salt, secret.encode("utf-8"), sha256).digest()


def credential_metadata_obj(
    text: str,
    *,
    credential_type: str,
    token_mode: str | None = None,
    registered_path_hash: str | None = None,
) -> dict[str, Any]:
    allowed_keys = {"schema_version", "display_label"}
    required_keys: set[str] = set()
    if credential_type == "admin":
        allowed_keys.add("role")
        required_keys.add("role")
    elif credential_type == "token":
        allowed_keys.update({"token_mode", "created_for_path_hash"})
        required_keys.update({"token_mode", "created_for_path_hash"})
    elif credential_type != "root":
        raise AlabError("STORAGE_ERROR", f"unknown credential_type for metadata: {credential_type}")

    value = contract_json_obj(
        text,
        label="credentials.metadata_json",
        allowed_keys=allowed_keys,
        required_keys=required_keys,
    )
    display_label = value.get("display_label")
    if display_label is not None and not isinstance(display_label, str):
        raise AlabError("STORAGE_ERROR", "credentials.metadata_json display_label must be a string")
    if credential_type == "admin" and value.get("role") != "admin":
        raise AlabError("STORAGE_ERROR", "credentials.metadata_json role must be admin")
    if credential_type == "token":
        if value.get("token_mode") != token_mode:
            raise AlabError("STORAGE_ERROR", "credentials.metadata_json token_mode does not match credential row")
        if value.get("created_for_path_hash") != registered_path_hash:
            raise AlabError("STORAGE_ERROR", "credentials.metadata_json created_for_path_hash does not match credential row")
    return value


def _default_credential_metadata(
    *,
    credential_type: str,
    token_mode: str | None,
    registered_path_hash: str | None,
) -> dict[str, Any]:
    if credential_type == "root":
        return {"schema_version": 1}
    if credential_type == "admin":
        return {"schema_version": 1, "role": "admin"}
    if credential_type == "token":
        return {
            "schema_version": 1,
            "token_mode": token_mode,
            "created_for_path_hash": registered_path_hash,
        }
    raise AlabError("STORAGE_ERROR", f"unknown credential_type for metadata: {credential_type}")


def create_credential(
    conn,
    *,
    credential_type: str,
    project_id: str | None = None,
    exp_id: str | None = None,
    token_mode: str | None = None,
    registered_path_hash: str | None = None,
    metadata: dict | None = None,
) -> tuple[str, str]:
    credential_id = new_id("cred", credential_type)
    secret = _secret()
    prefix = {"root": ROOT_PREFIX, "admin": ADMIN_PREFIX, "token": TOKEN_PREFIX}[credential_type]
    raw = f"{prefix}{credential_id}_{secret}"
    salt = secrets.token_bytes(32)
    now = utc_now()
    metadata_payload = metadata or _default_credential_metadata(
        credential_type=credential_type,
        token_mode=token_mode,
        registered_path_hash=registered_path_hash,
    )
    metadata_json = canonical_json(
        credential_metadata_obj(
            canonical_json(metadata_payload),
            credential_type=credential_type,
            token_mode=token_mode,
            registered_path_hash=registered_path_hash,
        )
    )
    conn.execute(
        """
        INSERT INTO credentials(
          credential_id, credential_type, project_id, exp_id, token_mode, registered_path_hash,
          status, salt, verifier_hash, created_at, revoked_at, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, NULL, ?)
        """,
        (
            credential_id,
            credential_type,
            project_id,
            exp_id,
            token_mode,
            registered_path_hash,
            salt,
            _verifier(secret, salt),
            now,
            metadata_json,
        ),
    )
    return credential_id, raw


def parse_raw_credential(raw: str) -> tuple[str, str, str]:
    for kind, prefix in [("root", ROOT_PREFIX), ("admin", ADMIN_PREFIX), ("token", TOKEN_PREFIX)]:
        if raw.startswith(prefix):
            rest = raw[len(prefix) :]
            credential_id, sep, secret = rest.rpartition("_")
            if not sep or not credential_id or not secret:
                raise _invalid_credential()
            return kind, credential_id, secret
    raise _invalid_credential()


def verify_raw_credential(
    conn,
    raw: str,
    *,
    required: str | tuple[str, ...] | None = None,
    project_id: str | None = None,
    exp_id: str | None = None,
    token_mode: str | None = None,
    path_hash: str | None = None,
) -> Actor:
    kind, credential_id, secret = parse_raw_credential(raw.strip())
    row = one(conn, "SELECT * FROM credentials WHERE credential_id = ?", (credential_id,))
    if row is None:
        raise _invalid_credential()
    if row["credential_type"] != kind or row["status"] != "active":
        raise _invalid_credential()
    allowed = (required,) if isinstance(required, str) else required
    if allowed and kind not in allowed:
        raise _invalid_credential()
    if not hmac.compare_digest(bytes(row["verifier_hash"]), _verifier(secret, bytes(row["salt"]))):
        raise _invalid_credential()
    credential_metadata_obj(
        row["metadata_json"],
        credential_type=row["credential_type"],
        token_mode=row["token_mode"],
        registered_path_hash=row["registered_path_hash"],
    )
    if project_id and row["project_id"] and row["project_id"] != project_id:
        raise _invalid_credential()
    if kind == "admin" and project_id and row["project_id"] != project_id:
        raise _invalid_credential()
    if kind == "token":
        if project_id and row["project_id"] != project_id:
            raise _invalid_credential()
        if exp_id and row["exp_id"] != exp_id:
            raise _invalid_credential()
        if token_mode and row["token_mode"] != token_mode:
            raise _invalid_credential()
        if path_hash and row["registered_path_hash"] != path_hash:
            raise _invalid_credential()
    return Actor(
        actor_type=kind,
        credential_id=row["credential_id"],
        project_id=row["project_id"],
        exp_id=row["exp_id"],
        token_mode=row["token_mode"],
    )


def read_token(path: Path) -> str:
    token_path = path / ".alab" / "token"
    try:
        raw = token_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise AlabError("AUTH_REQUIRED", "token file not found") from exc
    return raw.rstrip("\n")


def token_permission_warning(path: Path) -> str | None:
    token_path = path / ".alab" / "token"
    try:
        mode = stat.S_IMODE(token_path.stat().st_mode)
    except OSError:
        return None
    if mode & 0o077:
        return "TOKEN_FILE_PERMISSIONS"
    return None


def write_token(path: Path, raw_token: str) -> None:
    token_dir = path / ".alab"
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path = token_dir / "token"
    token_path.write_text(raw_token + "\n", encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except OSError:
        pass


def new_home_id() -> str:
    return f"home-{random_suffix()}"
