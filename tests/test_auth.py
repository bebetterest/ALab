from __future__ import annotations

import json
import re
import sqlite3

import pytest

import alab.auth as auth_module
from alab.auth import (
    create_credential,
    credential_metadata_obj,
    parse_raw_credential,
    verify_raw_credential,
)
from alab.db import Database
from alab.errors import AlabError
from alab.home import Home
from alab.service_auth import require_actor
from alab.service_models import GlobalOptions, Request


def test_credentials_store_verifiers_not_raw_secrets(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()
    with db.tx() as conn:
        credential_id, raw = create_credential(
            conn,
            credential_type="admin",
            project_id="proj-example-AAAAAAAAAAAAAAAAAAAAAA",
        )
        kind, parsed_id, secret = parse_raw_credential(raw)
        row = conn.execute(
            "SELECT credential_id, credential_type, salt, verifier_hash, metadata_json FROM credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone()

    assert kind == "admin"
    assert parsed_id == credential_id
    assert raw.startswith(f"alab_admin_v1_{credential_id}_")
    assert row["credential_id"] == credential_id
    assert row["credential_type"] == "admin"
    assert raw not in row["metadata_json"]
    assert secret not in row["metadata_json"]
    assert bytes(row["salt"]) != secret.encode("utf-8")
    assert bytes(row["verifier_hash"]) != secret.encode("utf-8")
    assert json.loads(row["metadata_json"]) == {"schema_version": 1, "role": "admin"}


def test_credential_metadata_json_contract(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()
    path_hash = "sha256:" + "c" * 64
    with db.tx() as conn:
        token_id, raw_token = create_credential(
            conn,
            credential_type="token",
            project_id="proj-alpha-AAAAAAAAAAAAAAAAAAAAAA",
            exp_id="exp-alpha-BBBBBBBBBBBBBBBBBBBBBB",
            token_mode="inspection",
            registered_path_hash=path_hash,
            metadata={
                "schema_version": 1,
                "token_mode": "inspection",
                "created_for_path_hash": path_hash,
                "display_label": "inspection checkout",
            },
        )
        row = conn.execute(
            "SELECT credential_type, token_mode, registered_path_hash, metadata_json FROM credentials WHERE credential_id = ?",
            (token_id,),
        ).fetchone()

    assert credential_metadata_obj(
        row["metadata_json"],
        credential_type=row["credential_type"],
        token_mode=row["token_mode"],
        registered_path_hash=row["registered_path_hash"],
    ) == {
        "schema_version": 1,
        "token_mode": "inspection",
        "created_for_path_hash": path_hash,
        "display_label": "inspection checkout",
    }

    with db.tx() as conn:
        conn.execute(
            "UPDATE credentials SET metadata_json = ? WHERE credential_id = ?",
            (
                json.dumps(
                    {
                        "schema_version": 1,
                        "token_mode": "inspection",
                        "created_for_path_hash": path_hash,
                        "inspection_commit": "abc",
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                token_id,
            ),
        )

    with db.connect() as conn:
        with pytest.raises(AlabError, match="unknown JSON keys: inspection_commit"):
            verify_raw_credential(conn, raw_token, required="token", token_mode="inspection", path_hash=path_hash)

    with db.tx() as conn:
        with pytest.raises(AlabError, match="token_mode does not match credential row"):
            create_credential(
                conn,
                credential_type="token",
                project_id="proj-alpha-AAAAAAAAAAAAAAAAAAAAAA",
                exp_id="exp-beta-BBBBBBBBBBBBBBBBBBBBBBB",
                token_mode="worktree",
                registered_path_hash="sha256:" + "d" * 64,
                metadata={
                    "schema_version": 1,
                    "token_mode": "inspection",
                    "created_for_path_hash": "sha256:" + "d" * 64,
                },
            )


def test_credential_verification_requires_scope_project_status_mode_and_path(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()
    with db.tx() as conn:
        admin_id, admin_raw = create_credential(
            conn,
            credential_type="admin",
            project_id="proj-alpha-AAAAAAAAAAAAAAAAAAAAAA",
        )
        token_id, token_raw = create_credential(
            conn,
            credential_type="token",
            project_id="proj-alpha-AAAAAAAAAAAAAAAAAAAAAA",
            exp_id="exp-alpha-BBBBBBBBBBBBBBBBBBBBBB",
            token_mode="worktree",
            registered_path_hash="sha256:" + "c" * 64,
        )

    with db.connect() as conn:
        assert verify_raw_credential(
            conn,
            admin_raw,
            required="admin",
            project_id="proj-alpha-AAAAAAAAAAAAAAAAAAAAAA",
        ).credential_id == admin_id

        for invalid_call in [
            lambda: verify_raw_credential(conn, admin_raw, required="root"),
            lambda: verify_raw_credential(
                conn,
                admin_raw,
                required="admin",
                project_id="proj-other-DDDDDDDDDDDDDDDDDDDDDD",
            ),
        ]:
            with pytest.raises(AlabError) as exc_info:
                invalid_call()
            assert (exc_info.value.code, exc_info.value.reason) == ("AUTH_DENIED", "invalid credential")

        token_actor = verify_raw_credential(
            conn,
            token_raw,
            required="token",
            project_id="proj-alpha-AAAAAAAAAAAAAAAAAAAAAA",
            exp_id="exp-alpha-BBBBBBBBBBBBBBBBBBBBBB",
            token_mode="worktree",
            path_hash="sha256:" + "c" * 64,
        )
        assert token_actor.credential_id == token_id
        assert token_actor.token_mode == "worktree"

        for invalid_call in [
            lambda: verify_raw_credential(conn, token_raw, required="token", token_mode="inspection"),
            lambda: verify_raw_credential(
                conn,
                token_raw,
                required="token",
                path_hash="sha256:" + "d" * 64,
            ),
        ]:
            with pytest.raises(AlabError) as exc_info:
                invalid_call()
            assert (exc_info.value.code, exc_info.value.reason) == ("AUTH_DENIED", "invalid credential")

        conn.execute(
            "UPDATE credentials SET status = 'revoked', revoked_at = datetime('now') WHERE credential_id = ?",
            (token_id,),
        )
        with pytest.raises(AlabError) as exc_info:
            verify_raw_credential(conn, token_raw, required="token")
        assert (exc_info.value.code, exc_info.value.reason) == ("AUTH_DENIED", "invalid credential")


def test_credential_verification_failures_do_not_reveal_failure_part(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()
    with db.tx() as conn:
        admin_id, admin_raw = create_credential(
            conn,
            credential_type="admin",
            project_id="proj-alpha-AAAAAAAAAAAAAAAAAAAAAA",
        )

    wrong_secret = admin_raw[:-1] + ("0" if admin_raw[-1] != "0" else "1")
    type_prefix_mismatch = admin_raw.replace("alab_admin_v1_", "alab_root_v1_", 1)
    variants = [
        "",
        "not-a-valid-key",
        "alab_admin_v1__secret",
        "alab_admin_v1_cred-missing-AAAAAAAAAAAAAAAAAAAAAA_secret",
        type_prefix_mismatch,
        wrong_secret,
    ]

    with db.connect() as conn:
        for raw in variants:
            with pytest.raises(AlabError) as exc_info:
                verify_raw_credential(conn, raw)
            assert (exc_info.value.code, exc_info.value.reason) == ("AUTH_DENIED", "invalid credential")

        conn.execute(
            "UPDATE credentials SET status = 'revoked', revoked_at = datetime('now') WHERE credential_id = ?",
            (admin_id,),
        )
        with pytest.raises(AlabError) as exc_info:
            verify_raw_credential(conn, admin_raw)
        assert (exc_info.value.code, exc_info.value.reason) == ("AUTH_DENIED", "invalid credential")


def test_credential_generation_uses_high_entropy_secret_and_salt_sources(tmp_path, monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    def fake_token_hex(length: int) -> str:
        calls.append(("token_hex", length))
        return "a" * (length * 2)

    def fake_token_bytes(length: int) -> bytes:
        calls.append(("token_bytes", length))
        return bytes(range(length))

    monkeypatch.setattr(auth_module.secrets, "token_hex", fake_token_hex)
    monkeypatch.setattr(auth_module.secrets, "token_bytes", fake_token_bytes)

    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()
    with db.tx() as conn:
        credential_id, raw = create_credential(conn, credential_type="root")
        kind, parsed_id, secret = parse_raw_credential(raw)
        row = conn.execute(
            "SELECT salt, verifier_hash FROM credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone()

    assert calls == [("token_bytes", 16), ("token_hex", 32), ("token_bytes", 32)]
    assert (kind, parsed_id, secret) == ("root", credential_id, "a" * 64)
    assert re.fullmatch(r"[0-9a-f]{64}", secret)
    assert bytes(row["salt"]) == bytes(range(32))
    assert len(bytes(row["verifier_hash"])) == 32


def test_empty_ambient_alab_key_is_treated_as_absent(tmp_path, monkeypatch) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()
    req = Request(GlobalOptions(home=home), context=None)

    with pytest.raises(AlabError) as missing:
        require_actor(req, "root")
    assert missing.value.code == "AUTH_REQUIRED"

    monkeypatch.setenv("ALAB_KEY", "")
    with pytest.raises(AlabError) as empty:
        require_actor(req, "root")
    assert empty.value.code == "AUTH_REQUIRED"


def test_one_active_root_partial_uniqueness(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()
    with db.tx() as conn:
        create_credential(conn, credential_type="root")

        with pytest.raises(sqlite3.IntegrityError):
            create_credential(conn, credential_type="root")


def test_active_worktree_token_partial_uniqueness(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()
    project_id = "proj-alpha-AAAAAAAAAAAAAAAAAAAAAA"
    exp_id = "exp-alpha-BBBBBBBBBBBBBBBBBBBBBB"

    with db.tx() as conn:
        first_id, _raw = create_credential(
            conn,
            credential_type="token",
            project_id=project_id,
            exp_id=exp_id,
            token_mode="worktree",
            registered_path_hash="sha256:" + "a" * 64,
        )

        with pytest.raises(sqlite3.IntegrityError):
            create_credential(
                conn,
                credential_type="token",
                project_id=project_id,
                exp_id=exp_id,
                token_mode="worktree",
                registered_path_hash="sha256:" + "b" * 64,
            )

        create_credential(
            conn,
            credential_type="token",
            project_id=project_id,
            exp_id=exp_id,
            token_mode="inspection",
            registered_path_hash="sha256:" + "c" * 64,
        )
        create_credential(
            conn,
            credential_type="token",
            project_id=project_id,
            exp_id=exp_id,
            token_mode="inspection",
            registered_path_hash="sha256:" + "d" * 64,
        )

        conn.execute(
            "UPDATE credentials SET status = 'revoked', revoked_at = datetime('now') WHERE credential_id = ?",
            (first_id,),
        )
        second_id, _raw = create_credential(
            conn,
            credential_type="token",
            project_id=project_id,
            exp_id=exp_id,
            token_mode="worktree",
            registered_path_hash="sha256:" + "e" * 64,
        )

        row = conn.execute(
            """
            SELECT
              SUM(CASE WHEN token_mode = 'worktree' AND status = 'active' THEN 1 ELSE 0 END) AS active_worktree,
              SUM(CASE WHEN token_mode = 'worktree' AND status = 'revoked' THEN 1 ELSE 0 END) AS revoked_worktree,
              SUM(CASE WHEN token_mode = 'inspection' AND status = 'active' THEN 1 ELSE 0 END) AS active_inspection
            FROM credentials
            WHERE exp_id = ?
            """,
            (exp_id,),
        ).fetchone()

    assert second_id != first_id
    assert tuple(row) == (1, 1, 2)
