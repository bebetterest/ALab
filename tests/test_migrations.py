from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from alab import annotations as annotation_services
from alab import context as context_module
from alab import db as db_module
from alab import services
from alab.configs import ProjectConfig, config_hash
from alab.context import path_hash
from alab.db import Database, _sha256, canonical_json, contract_json_obj
from alab.errors import AlabError
from alab.home import Home

MINIMAL_INITIAL_SQL = """
CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL
);
"""


def test_migrate_records_exact_file_checksum(tmp_path) -> None:
    home = Home(tmp_path / "home")

    Database(home).migrate()

    migration = db_module.MIGRATIONS_DIR / "1_initial.sql"
    with sqlite3.connect(home.db_path) as conn:
        row = conn.execute(
            "SELECT version, name, checksum FROM schema_migrations WHERE version = 1"
        ).fetchone()
    assert row == (1, "initial", _sha256(migration.read_bytes()))


def test_database_connections_use_wal_mode(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    with db.connect() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert busy_timeout == 5000


def test_database_connections_use_configured_busy_timeout(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()
    home.config_path.write_text(
        home.config_path.read_text(encoding="utf-8").replace("busy_timeout_ms = 5000", "busy_timeout_ms = 1234"),
        encoding="utf-8",
    )

    with db.connect() as conn:
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert busy_timeout == 1234


def test_required_storage_indexes_are_created(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    with db.connect() as conn:
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
            )
        }

    assert {
        "idx_audit_object",
        "idx_credential_project_status",
        "idx_token_project_exp_mode_status",
        "idx_projects_status_updated",
        "idx_config_project_hash",
        "idx_source_project_status",
        "idx_exp_project_status_updated",
        "idx_runs_project_exp_started",
        "idx_artifacts_project_run",
        "idx_logs_project_run",
        "idx_annotations_target",
        "idx_path_active_hash",
        "idx_locks_project_exp",
        "idx_cache_kind_status_used",
    } <= indexes


def test_required_storage_tables_and_columns_are_created(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    with db.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        columns = {
            table: {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for table in [
                "projects",
                "experiments",
                "experiment_submissions",
                "experiment_tags",
                "project_validations",
                "annotations",
                "runtime_capabilities",
                "catalogs",
                "cache_entries",
            ]
        }

    assert {
        "experiment_submissions",
        "experiment_tags",
        "runtime_capabilities",
        "catalogs",
        "cache_entries",
    } <= tables
    assert {"secret_fingerprint_key", "pre_archive_status", "active_validation_id"} <= columns["projects"]
    assert {
        "bound_validation_id",
        "worktree_state",
        "pre_archive_status",
        "final_run_removed_at",
        "final_run_removed_by",
        "final_run_removed_audit_id",
    } <= columns["experiments"]
    assert {"refs_json", "final_run_id", "final_commit"} <= columns["experiment_submissions"]
    assert {"tag_slug", "created_by_type", "created_by_id"} <= columns["experiment_tags"]
    assert {"archive_status", "archived_at", "unarchived_at"} <= columns["project_validations"]
    assert {"target_json", "visibility_json", "current_revision"} <= columns["annotations"]
    assert {"capability_key", "fingerprint", "details_json"} <= columns["runtime_capabilities"]
    assert {"catalog_key", "catalog_type", "metadata_json", "removed_at"} <= columns["catalogs"]
    assert {"cache_kind", "cache_key", "metadata_json", "removed_at"} <= columns["cache_entries"]


def test_representative_ddl_enum_checks_are_enforced(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    with db.connect() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO credentials(credential_id, credential_type, status, salt, verifier_hash, created_at, metadata_json)
                VALUES ('cred-bad-AAAAAAAAAAAAAAAAAAAAAA', 'bad', 'active', x'00', x'00', '2026-05-19T00:00:00Z', '{}')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO audit_events(audit_id, actor_type, action, object_type, object_id, cascade, deleted_ids_json, metadata_json, created_at)
                VALUES ('aud-bad-AAAAAAAAAAAAAAAAAAAAAA', 'root', 'bad', 'project', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 0, '{}', '{}', '2026-05-19T00:00:00Z')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, reward_parse_status, archive_status, started_at, record_json)
                VALUES ('run-bad-AAAAAAAAAAAAAAAAAAAAAA', 'exp-x-AAAAAAAAAAAAAAAAAAAAAA', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 'abc', 1, 'bad', 'not_attempted', 'active', '2026-05-19T00:00:00Z', '{}')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, reward_parse_status, archive_status, archived_at, started_at, ended_at, record_json)
                VALUES ('run-active-archive-AAAAAAAAAAAAAAAAAAAAAA', 'exp-x-AAAAAAAAAAAAAAAAAAAAAA', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 'abc', 1, 'passed', 'not_attempted', 'active', '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z', '2026-05-19T00:00:01Z', '{}')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status, reward_parse_status, archive_status, started_at, ended_at, record_json)
                VALUES ('run-ended-AAAAAAAAAAAAAAAAAAAAAA', 'exp-x-AAAAAAAAAAAAAAAAAAAAAA', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 'abc', 1, 'passed', 'not_attempted', 'active', '2026-05-19T00:00:00Z', NULL, '{}')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO project_validations(validation_id, project_id, config_version, source_ref, source_commit, status, reward_parse_status, archive_status, started_at, ended_at, record_json)
                VALUES ('val-ended-AAAAAAAAAAAAAAAAAAAAAA', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 1, 'alab/source/main', 'abc', 'skipped', 'not_attempted', 'active', '2026-05-19T00:00:00Z', NULL, '{}')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id, status, created_at, updated_at)
                VALUES ('path-bad-AAAAAAAAAAAAAAAAAAAAAA', 'sha256:bad', '/tmp/x', 'bad', 'home-x', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 'active', '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z')
                """
            )
        annotation_values = (
            "ann-valid-AAAAAAAAAAAAAAAAAAAAAA",
            "proj-x-AAAAAAAAAAAAAAAAAAAAAA",
            "experiment",
            "exp-x-AAAAAAAAAAAAAAAAAAAAAA",
            "{}",
            None,
            1,
            "{}",
            "active",
            "root",
            "cred-root-AAAAAAAAAAAAAAAAAAAAAA",
            "2026-05-19T00:00:00Z",
            "2026-05-19T00:00:00Z",
        )
        annotation_sql = """
            INSERT INTO annotations(annotation_id, project_id, target_type, target_id, target_json,
              resolved_commit, current_revision, visibility_json, status, created_by_type, created_by_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        for index, bad_value in ((2, "bad"), (6, 0), (8, "deleted"), (9, "system")):
            bad_values = list(annotation_values)
            bad_values[index] = bad_value
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(annotation_sql, bad_values)
        bad_path_values = list(annotation_values)
        bad_path_values[2] = "path"
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(annotation_sql, bad_path_values)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO annotation_revisions(annotation_id, revision, body, created_at, created_by_type, created_by_id)
                VALUES ('ann-valid-AAAAAAAAAAAAAAAAAAAAAA', 0, 'body', '2026-05-19T00:00:00Z', 'root', 'cred-root-AAAAAAAAAAAAAAAAAAAAAA')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO annotation_revisions(annotation_id, revision, body, created_at, created_by_type, created_by_id)
                VALUES ('ann-valid-AAAAAAAAAAAAAAAAAAAAAA', 1, 'body', '2026-05-19T00:00:00Z', 'system', 'cred-root-AAAAAAAAAAAAAAAAAAAAAA')
                """
            )


def test_project_source_and_experiment_lifecycle_ddl_contract_checks_are_enforced(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    with db.connect() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO projects(project_id, status, pre_archive_status, canonical_repo_path, control_path,
                  secret_fingerprint_key, created_at, updated_at)
                VALUES ('proj-bad-archive-AAAAAAAAAAAAAAAAAAAAAA', 'archived', NULL, '/tmp/repo-a', '/tmp/control-a',
                  x'00', '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO projects(project_id, status, pre_archive_status, canonical_repo_path, control_path,
                  secret_fingerprint_key, created_at, updated_at)
                VALUES ('proj-bad-pre-AAAAAAAAAAAAAAAAAAAAAA', 'valid', 'invalid', '/tmp/repo-b', '/tmp/control-b',
                  x'00', '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO project_config_versions(project_id, version, canonical_config_json, config_hash,
                  baseline_required, validation_status, inherited_from_validation_id, created_at)
                VALUES ('proj-x-AAAAAAAAAAAAAAAAAAAAAA', 1, '{}', 'sha256:abc', 0, 'inherited', NULL,
                  '2026-05-19T00:00:00Z')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO project_config_versions(project_id, version, canonical_config_json, config_hash,
                  baseline_required, validation_status, inherited_from_validation_id, created_at)
                VALUES ('proj-x-AAAAAAAAAAAAAAAAAAAAAA', 2, '{}', 'sha256:def', 1, 'running',
                  'val-x-AAAAAAAAAAAAAAAAAAAAAA', '2026-05-19T00:00:00Z')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO sources(source_id, project_id, name, name_slug, source_ref, source_commit, tree_hash,
                  status, origin_metadata_json, created_at)
                VALUES ('src-bad-AAAAAAAAAAAAAAAAAAAAAA', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 'Source', 'source',
                  'alab/source/wrong', 'abc', 'sha256:tree', 'active', '{}', '2026-05-19T00:00:00Z')
                """
            )

        exp_values = [
            "exp-valid-AAAAAAAAAAAAAAAAAAAAAA",
            "proj-x-AAAAAAAAAAAAAAAAAAAAAA",
            "src-x-AAAAAAAAAAAAAAAAAAAAAA",
            1,
            "val-x-AAAAAAAAAAAAAAAAAAAAAA",
            "abc123",
            "alab/exp/valid",
            "active",
            "open",
            None,
            "{}",
            "{}",
            None,
            None,
            None,
            None,
            "2026-05-19T00:00:00Z",
            "2026-05-19T00:00:00Z",
            None,
            None,
        ]
        exp_sql = """
            INSERT INTO experiments(exp_id, project_id, source_id, bound_config_version, bound_validation_id,
              baseline_commit, branch_name, worktree_state, status, pre_archive_status, metadata_json, policy_json,
              final_run_removed_at, final_run_removed_by, final_run_removed_audit_id, final_run_id, created_at,
              updated_at, closed_at, archived_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        bad_cases = [
            (8, "archived", "archived experiment requires pre_archive_status"),
            (9, "open", "active experiment must not keep pre_archive_status"),
        ]
        for index, bad_value, _label in bad_cases:
            values = list(exp_values)
            values[0] = f"exp-bad-{index}-AAAAAAAAAAAAAAAAAAAAAA"
            values[index] = bad_value
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(exp_sql, values)
        closed_at_on_open = list(exp_values)
        closed_at_on_open[0] = "exp-bad-closed-AAAAAAAAAAAAAAAAAAAAAA"
        closed_at_on_open[18] = "2026-05-19T00:00:01Z"
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(exp_sql, closed_at_on_open)
        archived_open_closed_at = list(exp_values)
        archived_open_closed_at[0] = "exp-bad-archclosed-AAAAAAAAAAAAAAAAAA"
        archived_open_closed_at[8] = "archived"
        archived_open_closed_at[9] = "open"
        archived_open_closed_at[18] = "2026-05-19T00:00:01Z"
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(exp_sql, archived_open_closed_at)
        partial_final_run_removed = list(exp_values)
        partial_final_run_removed[0] = "exp-bad-final-AAAAAAAAAAAAAAAAAAAAAA"
        partial_final_run_removed[12] = "2026-05-19T00:00:01Z"
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(exp_sql, partial_final_run_removed)


def test_audit_secret_submission_and_tag_ddl_contract_checks_are_enforced(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    with db.connect() as conn:
        audit_sql = """
            INSERT INTO audit_events(audit_id, actor_type, action, object_type, object_id, cascade,
              reason, deleted_ids_json, metadata_json, created_at)
            VALUES (?, 'root', 'remove', 'project', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 0,
              ?, '{}', '{}', '2026-05-19T00:00:00Z')
            """
        for audit_id, reason in (
            ("aud-reason-long-AAAAAAAAAAAAAAAAA", "x" * 65537),
            ("aud-reason-blob-AAAAAAAAAAAAAAAAA", sqlite3.Binary(b"not text")),
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(audit_sql, (audit_id, reason))

        secret_sql = """
            INSERT INTO secret_values(secret_value_id, project_id, name, value, fingerprint, created_at)
            VALUES (?, 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 'API_TOKEN', ?, ?, '2026-05-19T00:00:00Z')
            """
        good_fingerprint = "hmac-sha256:" + "a" * 64
        bad_secrets = [
            ("sec-short-AAAAAAAAAAAAAAAAAAAAAA", "abc", good_fingerprint),
            ("sec-nul-AAAAAAAAAAAAAAAAAAAAAAAA", "abcd\0ef", good_fingerprint),
            ("sec-blob-AAAAAAAAAAAAAAAAAAAAAAA", sqlite3.Binary(b"abcd"), good_fingerprint),
            ("sec-fp-prefix-AAAAAAAAAAAAAAAAAAA", "abcd", "plain"),
            ("sec-fp-empty-AAAAAAAAAAAAAAAAAAAA", "abcd", "hmac-sha256:"),
        ]
        for row in bad_secrets:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(secret_sql, row)

        refs_json = canonical_json({"schema_version": 1, "refs": ["none"]})
        submission_sql = """
            INSERT INTO experiment_submissions(submission_id, project_id, exp_id, final_run_id, final_commit,
              message, summary, feedback, refs_json, created_at, created_by_credential_id)
            VALUES (?, 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', ?, 'run-x-AAAAAAAAAAAAAAAAAAAAAA', 'abc123',
              ?, ?, ?, ?, '2026-05-19T00:00:00Z', 'cred-root-AAAAAAAAAAAAAAAAAAAAAA')
            """
        submission_values = [
            "sub-valid-AAAAAAAAAAAAAAAAAAAAAA",
            "exp-valid-AAAAAAAAAAAAAAAAAAAAAA",
            "ok",
            "summary",
            "feedback",
            refs_json,
        ]
        for index, bad_value in ((2, "x" * 301), (3, "x" * 65537), (4, "x" * 65537), (2, sqlite3.Binary(b"ok"))):
            values = list(submission_values)
            values[0] = f"sub-bad-{index}-{len(str(bad_value))}-AAAAAAAAAAAAAA"
            values[1] = f"exp-bad-{index}-{len(str(bad_value))}-AAAAAAAAAAAAAA"
            values[index] = bad_value
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(submission_sql, values)

        tag_sql = """
            INSERT INTO experiment_tags(project_id, exp_id, tag_slug, created_by_type, created_by_id, created_at)
            VALUES ('proj-x-AAAAAAAAAAAAAAAAAAAAAA', 'exp-x-AAAAAAAAAAAAAAAAAAAAAA',
              ?, ?, 'cred-root-AAAAAAAAAAAAAAAAAAAAAA', '2026-05-19T00:00:00Z')
            """
        bad_tags = [
            ("Bad", "root"),
            ("bad_tag", "root"),
            ("-bad", "root"),
            ("bad-", "root"),
            ("bad--tag", "root"),
            ("a" * 65, "root"),
            ("good-tag", "system"),
        ]
        for row in bad_tags:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(tag_sql, row)


def test_foundation_table_ddl_contract_checks_are_enforced(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    with db.connect() as conn:
        credential_sql = """
            INSERT INTO credentials(credential_id, credential_type, project_id, exp_id, token_mode,
              registered_path_hash, status, salt, verifier_hash, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, 'active', x'00', x'00', '2026-05-19T00:00:00Z', '{}')
            """
        invalid_credentials = [
            ("cred-root-project-AAAAAAAAAAAAAAAAAA", "root", "proj-x-AAAAAAAAAAAAAAAAAAAAAA", None, None, None),
            ("cred-admin-exp-AAAAAAAAAAAAAAAAAAAA", "admin", "proj-x-AAAAAAAAAAAAAAAAAAAAAA", "exp-x-AAAAAAAAAAAAAAAAAAAAAA", None, None),
            ("cred-token-mode-AAAAAAAAAAAAAAAAAAA", "token", "proj-x-AAAAAAAAAAAAAAAAAAAAAA", "exp-x-AAAAAAAAAAAAAAAAAAAAAA", "read", "sha256:path"),
            ("cred-token-path-AAAAAAAAAAAAAAAAAAA", "token", "proj-x-AAAAAAAAAAAAAAAAAAAAAA", "exp-x-AAAAAAAAAAAAAAAAAAAAAA", "worktree", None),
        ]
        for row in invalid_credentials:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(credential_sql, row)

        path_sql = """
            INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id,
              exp_id, token_id, status, removed_at, removed_by_credential_id, created_at, updated_at)
            VALUES (?, 'sha256:path', '/tmp/path', ?, 'home-x', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA',
              ?, ?, ?, ?, ?, '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z')
            """
        invalid_paths = [
            ("path-project-exp-AAAAAAAAAAAAAAAAAAA", "project", "exp-x-AAAAAAAAAAAAAAAAAAAAAA", None, "active", None, None),
            ("path-exp-missing-AAAAAAAAAAAAAAAAAAAA", "experiment", "exp-x-AAAAAAAAAAAAAAAAAAAAAA", None, "active", None, None),
            ("path-active-removed-AAAAAAAAAAAAAAAAA", "project", None, None, "active", "2026-05-19T00:00:00Z", None),
            ("path-removed-missing-AAAAAAAAAAAAAAAA", "project", None, None, "removed", None, None),
        ]
        for row in invalid_paths:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(path_sql, row)

        catalog_sql = """
            INSERT INTO catalogs(catalog_key, catalog_type, origin_url, pinned_commit, local_path,
              status, metadata_json, retrieved_at, updated_at, removed_at)
            VALUES (?, ?, 'https://example.invalid/catalog.git', 'aabbcc', '/tmp/catalog',
              ?, '{}', '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z', ?)
            """
        invalid_catalogs = [
            ("other", "skydiscover", "active", None),
            ("skydiscover", "other", "active", None),
            ("skydiscover", "skydiscover", "active", "2026-05-19T00:00:00Z"),
            ("skydiscover", "skydiscover", "removed", None),
        ]
        for row in invalid_catalogs:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(catalog_sql, row)

        cache_sql = """
            INSERT INTO cache_entries(cache_id, cache_kind, cache_key, path, docker_tag, size_bytes,
              status, metadata_json, created_at, removed_at)
            VALUES (?, ?, 'key', ?, ?, ?, ?, '{}', '2026-05-19T00:00:00Z', ?)
            """
        invalid_caches = [
            ("cache-kind-AAAAAAAAAAAAAAAAAAAAAA", "other", None, None, 0, "active", None),
            ("cache-size-AAAAAAAAAAAAAAAAAAAAAA", "trash", "/tmp/trash", None, -1, "active", None),
            ("cache-active-removed-AAAAAAAAAAAA", "trash", "/tmp/trash", None, 0, "active", "2026-05-19T00:00:00Z"),
            ("cache-removed-missing-AAAAAAAAAAA", "trash", "/tmp/trash", None, 0, "removed", None),
            ("cache-docker-path-AAAAAAAAAAAAAA", "docker_image", "/tmp/image", "alab-cache:test", 0, "active", None),
            ("cache-docker-tag-AAAAAAAAAAAAAAA", "docker_image", None, None, 0, "active", None),
            ("cache-trash-path-AAAAAAAAAAAAAAA", "trash", None, None, 0, "active", None),
            ("cache-trash-tag-AAAAAAAAAAAAAAAA", "trash", "/tmp/trash", "alab-cache:test", 0, "active", None),
        ]
        for row in invalid_caches:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(cache_sql, row)


def test_artifact_and_log_ddl_contract_checks_are_enforced(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    artifact_sql = """
        INSERT INTO artifacts(artifact_id, project_id, exp_id, run_id, validation_id, root, relative_path,
          size_bytes, content_hash, status, archive_status, blob_path, capture_error, archived_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    artifact_values = [
        "art-valid-AAAAAAAAAAAAAAAAAAAAAA",
        "proj-x-AAAAAAAAAAAAAAAAAAAAAA",
        "exp-x-AAAAAAAAAAAAAAAAAAAAAA",
        "run-x-AAAAAAAAAAAAAAAAAAAAAA",
        None,
        "workspace",
        "out.txt",
        3,
        "sha256:abc",
        "captured",
        "active",
        "blobs/sha256/ab/abc",
        None,
        None,
        "2026-05-19T00:00:00Z",
    ]
    artifact_bad_cases = [
        (5, "tmp"),
        (7, -1),
        (9, "missing"),
        (10, "deleted"),
        (11, None),
        (12, "unexpected"),
        (13, "2026-05-19T00:00:00Z"),
    ]
    log_sql = """
        INSERT INTO log_streams(log_id, project_id, exp_id, run_id, validation_id, stream, size_bytes,
          stored_bytes, content_hash, truncated, hidden, archive_status, file_path, preview_text, archived_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    log_values = [
        "log-valid-AAAAAAAAAAAAAAAAAAAAAA",
        "proj-x-AAAAAAAAAAAAAAAAAAAAAA",
        "exp-x-AAAAAAAAAAAAAAAAAAAAAA",
        "run-x-AAAAAAAAAAAAAAAAAAAAAA",
        None,
        "stdout",
        4,
        4,
        "sha256:abc",
        0,
        0,
        "active",
        "logs/stdout/ab/run-x.log",
        "text",
        None,
        "2026-05-19T00:00:00Z",
    ]
    log_bad_cases = [
        (5, "combined"),
        (6, -1),
        (7, -1),
        (9, 2),
        (10, 2),
        (11, "deleted"),
        (14, "2026-05-19T00:00:00Z"),
    ]

    with db.connect() as conn:
        for index, bad_value in artifact_bad_cases:
            values = list(artifact_values)
            values[0] = f"art-bad-{index}-AAAAAAAAAAAAAAAAAAAAAA"
            values[index] = bad_value
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(artifact_sql, values)
        for values in (
            [*artifact_values[:3], None, None, *artifact_values[5:]],
            [*artifact_values[:4], "val-x-AAAAAAAAAAAAAAAAAAAAAA", *artifact_values[5:]],
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(artifact_sql, values)
        error_without_capture_error = list(artifact_values)
        error_without_capture_error[0] = "art-error-AAAAAAAAAAAAAAAAAAAAAA"
        error_without_capture_error[9] = "error"
        error_without_capture_error[11] = None
        error_without_capture_error[12] = None
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(artifact_sql, error_without_capture_error)

        stored_larger_than_size = list(log_values)
        stored_larger_than_size[0] = "log-stored-AAAAAAAAAAAAAAAAAAAAAA"
        stored_larger_than_size[7] = 5
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(log_sql, stored_larger_than_size)
        hidden_mismatch = list(log_values)
        hidden_mismatch[0] = "log-hidden-AAAAAAAAAAAAAAAAAAAAAA"
        hidden_mismatch[5] = "hidden_stdout"
        hidden_mismatch[10] = 0
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(log_sql, hidden_mismatch)
        visible_mismatch = list(log_values)
        visible_mismatch[0] = "log-visible-AAAAAAAAAAAAAAAAAAAAAA"
        visible_mismatch[10] = 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(log_sql, visible_mismatch)
        for index, bad_value in log_bad_cases:
            values = list(log_values)
            values[0] = f"log-bad-{index}-AAAAAAAAAAAAAAAAAAAAAA"
            values[index] = bad_value
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(log_sql, values)
        for values in (
            [*log_values[:3], None, None, *log_values[5:]],
            [*log_values[:4], "val-x-AAAAAAAAAAAAAAAAAAAAAA", *log_values[5:]],
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(log_sql, values)


def test_run_records_allow_required_nullable_fields(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    with db.connect() as conn:
        for status, ended_at in [
            ("running", None),
            ("error", "2026-05-19T00:00:01Z"),
            ("interrupted", "2026-05-19T00:00:01Z"),
        ]:
            conn.execute(
                """
                INSERT INTO runs(run_id, exp_id, project_id, commit_sha, config_version, status,
                  exit_code, reward_value, reward_parse_status, archive_status, started_at, ended_at, record_json)
                VALUES (?, 'exp-nullable-AAAAAAAAAAAAAAAAAAAAAA', 'proj-nullable-AAAAAAAAAAAAAAAAAAAAAA',
                  'abc123', 1, ?, NULL, NULL, 'not_attempted', 'active', '2026-05-19T00:00:00Z', ?, '{}')
                """,
                (f"run-{status}-AAAAAAAAAAAAAAAAAAAAAA", status, ended_at),
            )

        rows = conn.execute(
            """
            SELECT status, exit_code, reward_value, ended_at
            FROM runs
            WHERE project_id = 'proj-nullable-AAAAAAAAAAAAAAAAAAAAAA'
            ORDER BY status
            """
        ).fetchall()

    assert [tuple(row) for row in rows] == [
        ("error", None, None, "2026-05-19T00:00:01Z"),
        ("interrupted", None, None, "2026-05-19T00:00:01Z"),
        ("running", None, None, None),
    ]


def test_canonical_json_ordering_and_hash_stability() -> None:
    first = {"b": 2, "a": {"z": "值", "m": [3, 1]}}
    second = {"a": {"m": [3, 1], "z": "值"}, "b": 2}

    assert canonical_json(first) == '{"a":{"m":[3,1],"z":"值"},"b":2}'
    assert canonical_json(first) == canonical_json(second)
    assert config_hash(first) == config_hash(second)


def test_contract_json_obj_enforces_schema_version_and_known_keys() -> None:
    allowed = {"schema_version", "safe_summary", "warnings"}

    assert contract_json_obj(
        '{"schema_version":1,"safe_summary":"ok","warnings":[]}',
        label="example.metadata_json",
        allowed_keys=allowed,
        required_keys={"safe_summary"},
    ) == {"schema_version": 1, "safe_summary": "ok", "warnings": []}

    invalid_cases = [
        ('{"schema_version":1,"safe_summary":"ok","secret":"leak"}', "contains unknown JSON keys: secret"),
        ('{"safe_summary":"ok"}', "missing JSON keys: schema_version"),
        ('{"schema_version":true,"safe_summary":"ok"}', "schema_version must be 1"),
        ('{"schema_version":2,"safe_summary":"ok"}', "schema_version must be 1"),
        ('["not","object"]', "stored JSON value is not an object"),
    ]
    for raw, message in invalid_cases:
        with pytest.raises(AlabError) as excinfo:
            contract_json_obj(raw, label="example.metadata_json", allowed_keys=allowed, required_keys={"safe_summary"})
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason


def test_project_config_json_contract_enforces_documented_shape() -> None:
    config = ProjectConfig.model_validate(
        {
            "schema_version": 1,
            "project": {"name": "Config Contract", "task": "Validate stored config JSON"},
            "runner": {"type": "local", "command": [sys.executable, "-c", "print('ok')"]},
            "reward": {"type": "exit_code"},
            "env": {"VISIBLE_ENV": "visible"},
        }
    ).canonical_dict()
    config["secret_env"] = {
        "API_TOKEN": {
            "secret_value_id": "sec-token-AAAAAAAAAAAAAAAAAAAAAA",
            "fingerprint": "hmac-sha256:" + "a" * 64,
        }
    }

    assert services.project_config_json_obj(canonical_json(config)) == config

    invalid_cases = [
        ({**config, "raw_secret": "x"}, "contains unknown JSON keys: raw_secret"),
        ({key: value for key, value in config.items() if key != "git"}, "missing JSON keys: git"),
        ({**config, "env": {"VISIBLE_ENV": 1}}, "env must be a string map"),
        ({**config, "secret_env": {"API_TOKEN": "raw-secret"}}, "secret_env entries must be stored secret marker objects"),
        (
            {**config, "secret_env": {"API_TOKEN": {"secret_value_id": "sec-token-AAAAAAAAAAAAAAAAAAAAAA"}}},
            "secret_env.API_TOKEN missing JSON keys: fingerprint",
        ),
        (
            {**config, "secret_env": {"API_TOKEN": {"secret_value_id": "sec-token-AAAAAAAAAAAAAAAAAAAAAA", "fingerprint": "plain"}}},
            "secret_env fingerprint must be an HMAC string",
        ),
    ]
    for value, message in invalid_cases:
        with pytest.raises(AlabError) as excinfo:
            services.project_config_json_obj(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason


def test_context_marker_json_contract_enforces_documented_shape() -> None:
    project_marker = {
        "marker_version": 1,
        "home_id": "home-AAAAAAAAAAAAAAAAAAAAAA",
        "context_type": "project",
        "project_id": "proj-alpha-AAAAAAAAAAAAAAAAAAAAAA",
        "exp_id": None,
        "token_id": None,
        "canonical_repo_path_hash": "sha256:" + "a" * 64,
        "created_at": "2026-05-20T00:00:00Z",
    }
    experiment_marker = {
        "marker_version": 1,
        "home_id": project_marker["home_id"],
        "context_type": "experiment",
        "project_id": project_marker["project_id"],
        "exp_id": "exp-alpha-AAAAAAAAAAAAAAAAAAAAAA",
        "token_id": "cred-token-AAAAAAAAAAAAAAAAAAAAAA",
        "created_at": "2026-05-20T00:00:00Z",
    }
    inspection_marker = {
        **experiment_marker,
        "context_type": "inspection",
        "inspection_commit": "abc123",
    }

    assert context_module.context_marker_obj(json.dumps(project_marker)) == project_marker
    assert context_module.context_marker_obj(json.dumps(experiment_marker)) == experiment_marker
    assert context_module.context_marker_obj(json.dumps(inspection_marker)) == inspection_marker

    invalid_cases = [
        ([project_marker], "context marker must be a JSON object"),
        ({**project_marker, "raw_token": "x"}, "contains unknown JSON keys: raw_token"),
        ({**project_marker, "marker_version": 2}, "marker_version must be 1"),
        ({**project_marker, "context_type": "other"}, "invalid context_type"),
        ({**project_marker, "token_id": "cred-token-AAAAAAAAAAAAAAAAAAAAAA"}, "project context marker must not contain exp_id or token_id"),
        ({**experiment_marker, "token_id": None}, "experiment context marker requires token_id"),
        ({**experiment_marker, "canonical_repo_path_hash": "sha256:" + "b" * 64}, "experiment context marker must not contain canonical_repo_path_hash"),
        ({**inspection_marker, "inspection_commit": ""}, "inspection context marker requires inspection_commit"),
    ]
    for value, message in invalid_cases:
        with pytest.raises(AlabError) as excinfo:
            context_module.context_marker_obj(json.dumps(value))
        assert excinfo.value.code == "CONTEXT_CONFLICT"
        assert message in excinfo.value.reason


def test_source_origin_metadata_contract_enforces_documented_shape() -> None:
    origin = {
        "origin_id": "origin-local-AAAAAAAAAAAAAAAAAAAAAA",
        "origin_type": "local",
        "safe_summary": "local",
        "exact": {"source_subdir": "app"},
        "warnings": [],
        "created_at": "2026-05-20T00:00:00Z",
    }
    metadata = {
        "schema_version": 1,
        "tree_hash_algorithm": "alab-tree-sha256-v1",
        "primary_origin": origin,
        "origins": [origin],
    }

    assert services.source_origin_metadata_obj(canonical_json(metadata)) == metadata

    invalid_cases = [
        ({**metadata, "source_path": "/tmp/raw"}, "contains unknown JSON keys: source_path"),
        ({**metadata, "tree_hash_algorithm": "other"}, "tree_hash_algorithm is invalid"),
        ({**metadata, "origins": []}, "origins must be a non-empty array"),
        ({**metadata, "origins": [{**origin, "origin_id": "origin-local-BBBBBBBBBBBBBBBBBBBBBB"}]}, "primary_origin must match origins[0]"),
        ({**metadata, "primary_origin": {**origin, "source_path": "/tmp/raw"}}, "contains unknown JSON keys: source_path"),
        ({**metadata, "primary_origin": {**origin, "warnings": ["ok", 1]}}, "warnings must be a string array"),
    ]
    for value, message in invalid_cases:
        with pytest.raises(AlabError) as excinfo:
            services.source_origin_metadata_obj(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason


def test_annotation_target_and_visibility_json_contracts() -> None:
    exp_id = "exp-alpha-AAAAAAAAAAAAAAAAAAAAAA"
    peer_exp_id = "exp-peer-DDDDDDDDDDDDDDDDDDDDDD"
    run_id = "run-alpha-BBBBBBBBBBBBBBBBBBBBBB"
    artifact_id = "art-alpha-CCCCCCCCCCCCCCCCCCCCCC"
    target = {
        "schema_version": 1,
        "target_type": "lines",
        "target_id": f"{exp_id}:abc123:src/main.py",
        "exp_id": exp_id,
        "commit": "abc123",
        "repo_path": "src/main.py",
        "line_range": {"start": 1, "end": 3},
    }
    visibility = {
        "schema_version": 1,
        "scope": "private",
        "creator_exp_id": exp_id,
        "constraints": {},
    }

    assert annotation_services.annotation_target_json_obj(canonical_json(target)) == target
    assert annotation_services.annotation_target_json_obj(
        canonical_json({"schema_version": 1, "target_type": "experiment", "target_id": exp_id, "exp_id": exp_id, "commit": "abc123"})
    ) == {"schema_version": 1, "target_type": "experiment", "target_id": exp_id, "exp_id": exp_id, "commit": "abc123"}
    assert annotation_services.annotation_target_json_obj(
        canonical_json({"schema_version": 1, "target_type": "run", "target_id": run_id, "exp_id": exp_id, "commit": "abc123"})
    ) == {"schema_version": 1, "target_type": "run", "target_id": run_id, "exp_id": exp_id, "commit": "abc123"}
    assert annotation_services.annotation_target_json_obj(
        canonical_json({"schema_version": 1, "target_type": "artifact", "target_id": artifact_id, "exp_id": exp_id, "commit": None})
    ) == {"schema_version": 1, "target_type": "artifact", "target_id": artifact_id, "exp_id": exp_id, "commit": None}
    assert annotation_services.annotation_visibility_json_obj(canonical_json(visibility)) == visibility
    private_peer_row = {
        "target_json": canonical_json(
            {
                "schema_version": 1,
                "target_type": "experiment",
                "target_id": peer_exp_id,
                "exp_id": peer_exp_id,
                "commit": "abc123",
            }
        ),
        "visibility_json": canonical_json(visibility),
        "created_by_type": "token",
        "created_by_id": exp_id,
    }
    creator_actor = annotation_services.Actor(actor_type="token", credential_id="cred-alpha", project_id="proj-alpha", exp_id=exp_id, token_mode="worktree")
    assert annotation_services._annotation_visible(private_peer_row, creator_actor, {exp_id, peer_exp_id})
    assert not annotation_services._annotation_visible(private_peer_row, creator_actor, {exp_id})
    assert annotation_services._annotation_editable(private_peer_row, creator_actor, {exp_id, peer_exp_id})
    assert not annotation_services._annotation_editable(private_peer_row, creator_actor, {exp_id})

    invalid_targets = [
        ({**target, "raw_path": "/tmp/main.py"}, "contains unknown JSON keys: raw_path"),
        ({**target, "target_type": "unknown"}, "target_type is invalid"),
        ({**target, "target_id": f"{exp_id}:wrong:src/main.py"}, "path target_id must match exp_id, commit, and repo_path"),
        ({**target, "repo_path": "../main.py"}, "repo_path must be relative"),
        ({**target, "repo_path": "src/./main.py"}, "repo_path must be relative"),
        ({**target, "repo_path": "C:/main.py"}, "repo_path must be relative"),
        ({**target, "repo_path": "src\\main.py"}, "repo_path must be relative"),
        ({**target, "repo_path": "src/\u0000main.py"}, "repo_path must be relative"),
        ({**target, "line_range": {"start": 1, "end": 3, "raw": "x"}}, "line_range contains unknown JSON keys: raw"),
        ({**target, "line_range": {"start": True, "end": 3}}, "line_range start/end must be integers"),
        ({**target, "line_range": {"start": 0, "end": 3}}, "line_range is invalid"),
        ({**target, "line_range": {"start": 3, "end": 2}}, "line_range is invalid"),
        ({**target, "target_type": "lines", "line_range": None}, "lines target requires line_range"),
        ({**target, "target_type": "path"}, "path target must not include line_range"),
        ({"schema_version": 1, "target_type": "experiment", "target_id": "run-alpha-BBBBBBBBBBBBBBBBBBBBBB", "exp_id": exp_id}, "target_id must be a complete experiment id"),
        ({"schema_version": 1, "target_type": "run", "target_id": run_id}, "object targets require exp_id"),
        ({"schema_version": 1, "target_type": "experiment", "target_id": exp_id, "exp_id": "exp-other-DDDDDDDDDDDDDDDDDDDDDD"}, "experiment target_id must match exp_id"),
    ]
    for value, message in invalid_targets:
        with pytest.raises(AlabError) as excinfo:
            annotation_services.annotation_target_json_obj(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason

    invalid_visibilities = [
        ({**visibility, "scope": "team"}, "scope is invalid"),
        ({"schema_version": 1, "scope": "private", "constraints": {}}, "private scope requires creator_exp_id"),
        ({"schema_version": 1, "scope": "project", "creator_exp_id": exp_id, "constraints": {}}, "project scope must not include creator_exp_id"),
        ({**visibility, "constraints": []}, "constraints must be a JSON object"),
    ]
    for value, message in invalid_visibilities:
        with pytest.raises(AlabError) as excinfo:
            annotation_services.annotation_visibility_json_obj(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason


def test_experiment_metadata_contract_enforces_documented_shape() -> None:
    source_id = "src-base-AAAAAAAAAAAAAAAAAAAAAA"
    exp_id = "exp-parent-BBBBBBBBBBBBBBBBBBBBBB"
    metadata = {
        "schema_version": 1,
        "name": "Child",
        "name_slug": "child",
        "goal": None,
        "creation_origin": {
            "kind": "from_exp",
            "source_exp_id": exp_id,
            "from_commit": "latest",
            "resolved_commit": "abc123",
            "source_id": source_id,
        },
        "requested_path": "/tmp/child",
        "source_selector": exp_id,
        "display": {"safe_summary": "Child"},
    }

    assert services.experiment_metadata_obj(canonical_json(metadata)) == metadata
    assert services.experiment_metadata_obj(
        canonical_json(
            {
                **metadata,
                "creation_origin": {"kind": "source", "source_id": source_id},
                "source_selector": "alab/source/base",
            }
        )
    ) == {
        **metadata,
        "creation_origin": {"kind": "source", "source_id": source_id},
        "source_selector": "alab/source/base",
    }
    assert services.experiment_metadata_obj(
        canonical_json(
            {
                **metadata,
                "creation_origin": {"kind": "inline_source", "source_id": source_id, "source_ref": f"alab/source/{source_id}"},
                "source_selector": f"alab/source/{source_id}",
            }
        )
    ) == {
        **metadata,
        "creation_origin": {"kind": "inline_source", "source_id": source_id, "source_ref": f"alab/source/{source_id}"},
        "source_selector": f"alab/source/{source_id}",
    }

    invalid_cases = [
        ({**metadata, "raw_token": "secret"}, "contains unknown JSON keys: raw_token"),
        ({**metadata, "source_selector": ""}, "source_selector must be a non-empty string"),
        ({**metadata, "creation_origin": []}, "creation_origin must be a JSON object"),
        ({**metadata, "creation_origin": {**metadata["creation_origin"], "kind": "unknown"}}, "kind is invalid"),
        ({**metadata, "creation_origin": {**metadata["creation_origin"], "source_id": "src-short"}}, "contains invalid object id"),
        (
            {
                **metadata,
                "creation_origin": {
                    "kind": "inline_source",
                    "source_id": source_id,
                    "source_ref": "alab/source/" + source_id,
                    "resolved_commit": "abc123",
                },
            },
            "contains unknown JSON keys: resolved_commit",
        ),
        ({**metadata, "display": {"safe_summary": "Child", "raw_path": "/tmp/child"}}, "display contains unknown JSON keys: raw_path"),
        ({**metadata, "display": {}}, "display.safe_summary must be a string"),
    ]
    for value, message in invalid_cases:
        with pytest.raises(AlabError) as excinfo:
            services.experiment_metadata_obj(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason


def test_experiment_policy_json_contract_enforces_documented_shape() -> None:
    exp_a = "exp-alpha-AAAAAAAAAAAAAAAAAAAAAA"
    exp_b = "exp-bravo-BBBBBBBBBBBBBBBBBBBBBB"
    policy = {
        "schema_version": 1,
        "mutable": {"include": ["src/**"], "exclude": ["src/generated/**"]},
        "mutable_override": {"include": ["src/allowed/**"], "exclude": []},
        "visibility_upper_bound": {
            "schema_version": 1,
            "scope": "explicit",
            "experiment_ids": [exp_b, exp_a, exp_a],
        },
    }
    expected = {
        **policy,
        "visibility_upper_bound": {
            "schema_version": 1,
            "scope": "explicit",
            "experiment_ids": [exp_a, exp_b],
        },
    }

    assert services.experiment_policy_json_obj(canonical_json(policy)) == expected

    invalid_cases = [
        ({**policy, "raw_path": "/tmp/worktree"}, "contains unknown JSON keys: raw_path"),
        ({**policy, "mutable": {"include": ["src/**"]}}, "mutable missing JSON keys: exclude"),
        ({**policy, "mutable": {"include": ["src/**"], "exclude": [], "raw_path": "/tmp"}}, "mutable contains unknown JSON keys: raw_path"),
        ({**policy, "mutable": {"include": [1], "exclude": []}}, "mutable.include must be a string array"),
        ({**policy, "mutable": {"include": [], "exclude": []}}, "mutable.include must contain at least one pattern"),
        ({**policy, "mutable": {"include": [""], "exclude": []}}, "mutable.include patterns must be non-empty single-line values"),
        ({**policy, "mutable": {"include": ["src/**"], "exclude": ["bad\npattern"]}}, "mutable.exclude patterns must be non-empty single-line values"),
        ({**policy, "mutable_override": []}, "mutable_override must be a JSON object"),
        ({**policy, "visibility_upper_bound": {"scope": "team", "experiment_ids": []}}, "visibility_upper_bound.scope is invalid"),
        (
            {**policy, "visibility_upper_bound": {"scope": "same_project", "experiment_ids": [], "raw": "x"}},
            "visibility_upper_bound contains unknown JSON keys: raw",
        ),
        (
            {**policy, "visibility_upper_bound": {"schema_version": True, "scope": "same_project", "experiment_ids": []}},
            "visibility_upper_bound schema_version must be 1",
        ),
        (
            {**policy, "visibility_upper_bound": {"schema_version": 2, "scope": "same_project", "experiment_ids": []}},
            "visibility_upper_bound schema_version must be 1",
        ),
        (
            {**policy, "visibility_upper_bound": {"scope": "explicit", "experiment_ids": [1]}},
            "visibility_upper_bound.experiment_ids must be a string array",
        ),
        (
            {**policy, "visibility_upper_bound": {"scope": "explicit", "experiment_ids": []}},
            "visibility_upper_bound.experiment_ids is required for explicit scope",
        ),
        (
            {**policy, "visibility_upper_bound": {"scope": "same_project", "experiment_ids": [exp_a]}},
            "visibility_upper_bound.experiment_ids is only valid for explicit scope",
        ),
        (
            {**policy, "visibility_upper_bound": {"scope": "explicit", "experiment_ids": ["exp-short"]}},
            "visibility_upper_bound.experiment_ids entries must be complete experiment ids",
        ),
    ]
    for value, message in invalid_cases:
        with pytest.raises(AlabError) as excinfo:
            services.experiment_policy_json_obj(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason


def test_execution_record_json_contract_enforces_documented_shape() -> None:
    record = {
        "schema_version": 1,
        "config_hash": "sha256:" + "a" * 64,
        "runner": {"type": "local", "safe_summary": "local runner"},
        "reward": {"type": "stdout_regex", "value": 1.5},
        "metrics": {"reward": 1.5, "steps": 3},
        "warnings": ["stdout_truncated"],
        "failure": None,
        "artifacts": {},
        "logs": {},
        "timeout": False,
        "adapter_feedback": {},
        "mutable_scope": {
            "schema_version": 1,
            "error_code": "SCOPE_VIOLATION",
            "violation_paths": ["README.md"],
            "rolled_back_commit": None,
        },
    }

    assert services.execution_record_json_obj(canonical_json(record)) == record

    invalid_cases = [
        ({**record, "raw_log": "secret"}, "contains unknown JSON keys: raw_log"),
        ({key: value for key, value in record.items() if key != "config_hash"}, "missing JSON keys: config_hash"),
        ({**record, "config_hash": ""}, "config_hash must be a non-empty string"),
        ({**record, "runner": {"safe_summary": "missing"}}, "runner missing JSON keys: type"),
        ({**record, "runner": {"type": "local", "raw_env": "SECRET"}}, "runner contains unknown JSON keys: raw_env"),
        ({**record, "reward": {"type": "stdout_regex", "value": "1"}}, "reward.value must be a finite number or null"),
        ({**record, "metrics": {"reward": "1"}}, "metrics must be a string-to-finite-number map"),
        ({**record, "warnings": ["ok", 1]}, "warnings must be a string array"),
        ({**record, "timeout": "false"}, "timeout must be a boolean"),
        (
            {**record, "mutable_scope": {**record["mutable_scope"], "schema_version": True}},
            "mutable_scope schema_version must be 1",
        ),
        (
            {**record, "mutable_scope": {**record["mutable_scope"], "error_code": "OTHER"}},
            "mutable_scope error_code is invalid",
        ),
    ]
    for value, message in invalid_cases:
        with pytest.raises(AlabError) as excinfo:
            services.execution_record_json_obj(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason


def test_audit_json_contracts_enforce_documented_shape() -> None:
    deleted = {
        "schema_version": 1,
        "counts": {"run": 2},
        "ids": {"run": ["run-b-AAAAAAAAAAAAAAAAAAAAAA", "run-a-AAAAAAAAAAAAAAAAAAAAAA"]},
    }
    assert services.audit_deleted_ids_json_obj(canonical_json(deleted)) == {
        "schema_version": 1,
        "counts": {"run": 2},
        "ids": {"run": ["run-a-AAAAAAAAAAAAAAAAAAAAAA", "run-b-AAAAAAAAAAAAAAAAAAAAAA"]},
    }

    metadata = {
        "schema_version": 1,
        "trash": [{"kind": "run", "label": "trash/audit"}],
        "blockers": ["target_not_archived"],
        "credential": {"credential_type": "admin"},
        "safe_summary": "removed run",
    }
    assert services.audit_metadata_json_obj(canonical_json(metadata)) == metadata

    invalid_deleted = [
        ({**deleted, "raw_secret": "x"}, "contains unknown JSON keys: raw_secret"),
        ({**deleted, "counts": []}, "counts must be a JSON object"),
        ({"schema_version": 1, "counts": {"unknown": 1}, "ids": {"unknown": ["id"]}}, "contains unknown object types: unknown"),
        ({"schema_version": 1, "counts": {"run": 1}, "ids": {"run": ["run-a-AAAAAAAAAAAAAAAAAAAAAA", "run-b-AAAAAAAAAAAAAAAAAAAAAA"]}}, "counts must match ids"),
        ({"schema_version": 1, "counts": {"run": 1}, "ids": {"run": [1]}}, "ids must be string arrays"),
    ]
    for value, message in invalid_deleted:
        with pytest.raises(AlabError) as excinfo:
            services.audit_deleted_ids_json_obj(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason

    invalid_metadata = [
        ({**metadata, "raw_secret": "x"}, "contains unknown JSON keys: raw_secret"),
        ({**metadata, "trash": "trash/audit"}, "trash must be an object or array"),
        ({**metadata, "blockers": ["ok", 1]}, "blockers must be a string array"),
        ({**metadata, "credential": []}, "credential must be a JSON object"),
    ]
    for value, message in invalid_metadata:
        with pytest.raises(AlabError) as excinfo:
            services.audit_metadata_json_obj(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason


def test_runtime_catalog_and_cache_metadata_contracts_enforce_documented_shape() -> None:
    capability = {
        "schema_version": 1,
        "capability": "docker.availability",
        "safe_summary": "Docker available",
        "probed_values": {"docker": "ok"},
        "error_code": "none",
    }
    catalog = {
        "schema_version": 1,
        "safe_summary": "SkyDiscover catalog",
        "task_refs": ["skydiscover:tasks/demo"],
        "evaluator_refs": ["skydiscover:evaluators/demo"],
        "warnings": [],
    }
    cache = {
        "schema_version": 1,
        "safe_summary": "docker image cache",
        "inputs_hash": "sha256:" + "a" * 64,
        "warnings": [],
    }

    assert services.runtime_capability_details_json_obj(canonical_json(capability)) == capability
    assert services.catalog_metadata_json_obj(canonical_json(catalog)) == catalog
    assert services.cache_metadata_json_obj(canonical_json(cache)) == cache

    invalid_cases = [
        (services.runtime_capability_details_json_obj, {**capability, "schema_version": True}, "schema_version must be 1"),
        (services.runtime_capability_details_json_obj, {**capability, "capability": ""}, "capability must be a non-empty string"),
        (services.runtime_capability_details_json_obj, {**capability, "probed_values": []}, "probed_values must be a JSON object"),
        (services.runtime_capability_details_json_obj, {**capability, "error_code": 1}, "error_code must be a string"),
        (services.catalog_metadata_json_obj, {**catalog, "hidden_path": "/tmp/hidden"}, "contains unknown JSON keys: hidden_path"),
        (services.catalog_metadata_json_obj, {**catalog, "task_refs": [1]}, "task_refs must be a string array"),
        (services.catalog_metadata_json_obj, {**catalog, "warnings": ["ok", 1]}, "warnings must be a string array"),
        (services.cache_metadata_json_obj, {**cache, "secret": "raw"}, "contains unknown JSON keys: secret"),
        (services.cache_metadata_json_obj, {**cache, "inputs_hash": ""}, "inputs_hash must be a non-empty string"),
        (services.cache_metadata_json_obj, {**cache, "warnings": ["ok", 1]}, "warnings must be a string array"),
    ]
    for parser, value, message in invalid_cases:
        with pytest.raises(AlabError) as excinfo:
            parser(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason


def test_submission_refs_json_contract_enforces_documented_shape() -> None:
    exp_a = "exp-alpha-AAAAAAAAAAAAAAAAAAAAAA"
    exp_b = "exp-bravo-BBBBBBBBBBBBBBBBBBBBBB"
    refs = {"schema_version": 1, "refs": [exp_a, exp_b]}

    assert services.submission_refs_json_obj(canonical_json(refs)) == refs
    assert services.submission_refs_json_obj(canonical_json({"schema_version": 1, "refs": ["none"]})) == {
        "schema_version": 1,
        "refs": ["none"],
    }

    invalid_cases = [
        ({**refs, "raw_path": "/tmp/worktree"}, "contains unknown JSON keys: raw_path"),
        ({"schema_version": 1, "refs": []}, "refs must be a non-empty string array"),
        ({"schema_version": 1, "refs": ["none", exp_a]}, "ref none must be the only ref"),
        ({"schema_version": 1, "refs": [exp_a, exp_a]}, "refs must be deduplicated"),
        ({"schema_version": 1, "refs": ["exp-short"]}, "refs must be complete experiment ids or none"),
    ]
    for value, message in invalid_cases:
        with pytest.raises(AlabError) as excinfo:
            services.submission_refs_json_obj(canonical_json(value))
        assert excinfo.value.code == "STORAGE_ERROR"
        assert message in excinfo.value.reason


def test_cache_entry_metadata_writers_use_safe_json_contract(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    cache_key = "sha256:" + "a" * 64
    result = SimpleNamespace(
        cache_metadata={
            "cache_kind": "docker_image",
            "cache_key": cache_key,
            "docker_tag": "alab-cache:test",
            "status": "built",
            "adapter": "harbor",
            "verifier_mode": "private",
            "path": "/should/not/be/in/json",
        }
    )
    now = "2026-05-20T00:00:00Z"
    with db.tx() as conn:
        conn.execute(
            """
            INSERT INTO cache_entries(cache_id, cache_kind, cache_key, project_id, path, docker_tag,
              size_bytes, status, metadata_json, created_at, last_used_at, removed_at)
            VALUES ('cache-existing-AAAAAAAAAAAAA', 'docker_image', ?, NULL, NULL,
              'alab-cache:old', NULL, 'active', ?, ?, ?, NULL)
            """,
            (
                cache_key,
                canonical_json({"schema_version": 1, "safe_summary": "legacy", "inputs_hash": cache_key}),
                now,
                now,
            ),
        )
        services._record_runner_cache(conn, result, "proj-cache-AAAAAAAAAAAAAAAAAAAAAA")

    payload_path = tmp_path / "payload.txt"
    payload_path.write_text("trash bytes\n", encoding="utf-8")
    trash_path = tmp_path / "trash"
    trash_path.mkdir()
    services._record_pending_trash_cleanup(
        home,
        services.TrashStage(
            audit_id="aud-cache-AAAAAAAAAAAAAAAAAAAAAA",
            original_path=payload_path,
            trash_path=trash_path,
            audit_label="payload",
            mode="home",
            moved=True,
            already_absent=False,
        ),
        "proj-cache-AAAAAAAAAAAAAAAAAAAAAA",
        RuntimeError("full local path should stay out of metadata"),
    )

    with db.connect() as conn:
        rows = {
            row["cache_kind"]: (row["path"], row["docker_tag"], json.loads(row["metadata_json"]))
            for row in conn.execute(
                """
                SELECT cache_kind, path, docker_tag, metadata_json
                FROM cache_entries
                ORDER BY cache_kind
                """
            )
        }

    assert rows == {
        "docker_image": (
            None,
            "alab-cache:test",
            {
                "schema_version": 1,
                "safe_summary": "harbor docker_image built",
                "inputs_hash": cache_key,
                "warnings": [],
            },
        ),
        "trash": (
            str(trash_path),
            None,
            {
                "schema_version": 1,
                "safe_summary": "pending trash cleanup for payload",
                "inputs_hash": path_hash(payload_path),
                "warnings": ["trash deletion failed: RuntimeError"],
            },
        ),
    }


def test_removed_path_registry_rows_do_not_block_path_reuse(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id, status, removed_at, created_at, updated_at)
            VALUES ('path-old-AAAAAAAAAAAAAAAAAAAAAA', 'sha256:abc', '/tmp/reused', 'project', 'home-x', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 'removed', '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id, status, created_at, updated_at)
            VALUES ('path-new-AAAAAAAAAAAAAAAAAAAAAA', 'sha256:abc', '/tmp/reused', 'project', 'home-x', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 'active', '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z')
            """
        )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO path_registry(path_registry_id, path_hash, path, context_type, home_id, project_id, status, created_at, updated_at)
                VALUES ('path-dupe-AAAAAAAAAAAAAAAAAAAAAA', 'sha256:abc', '/tmp/reused', 'project', 'home-x', 'proj-x-AAAAAAAAAAAAAAAAAAAAAA', 'active', '2026-05-19T00:00:00Z', '2026-05-19T00:00:00Z')
                """
            )


def test_migrate_rejects_checksum_mismatch(tmp_path) -> None:
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    with sqlite3.connect(home.db_path) as conn:
        conn.execute(
            "UPDATE schema_migrations SET checksum = ? WHERE version = 1",
            ("sha256:bad",),
        )

    with pytest.raises(AlabError) as excinfo:
        db.migrate()
    assert excinfo.value.code == "STORAGE_ERROR"
    assert "checksum mismatch" in excinfo.value.reason


def test_migrate_rejects_invalid_migration_filename(tmp_path, monkeypatch) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "1_initial.sql").write_text(MINIMAL_INITIAL_SQL, encoding="utf-8")
    (migrations / "bad-name.sql").write_text("SELECT 1;\n", encoding="utf-8")
    monkeypatch.setattr(db_module, "MIGRATIONS_DIR", migrations)
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", 1)

    with pytest.raises(AlabError) as excinfo:
        Database(Home(tmp_path / "home")).migrate()

    assert excinfo.value.code == "STORAGE_ERROR"
    assert "invalid migration filename: bad-name.sql" in excinfo.value.reason


def test_migrate_rejects_non_contiguous_migration_versions(tmp_path, monkeypatch) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "1_initial.sql").write_text(MINIMAL_INITIAL_SQL, encoding="utf-8")
    (migrations / "3_skip.sql").write_text("CREATE TABLE skipped_version (value TEXT);\n", encoding="utf-8")
    monkeypatch.setattr(db_module, "MIGRATIONS_DIR", migrations)
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", 3)

    with pytest.raises(AlabError) as excinfo:
        Database(Home(tmp_path / "home")).migrate()

    assert excinfo.value.code == "STORAGE_ERROR"
    assert "migration files do not match the supported schema version" in excinfo.value.reason


def test_migration_lock_serializes_migrate_processes(tmp_path) -> None:
    home = Home(tmp_path / "home")
    home.path.mkdir(parents=True)
    ready_file = tmp_path / "child-ready"
    lock_path = home.path / ".migration.lock"
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from alab.db import Database\n"
        "from alab.home import Home\n"
        "home = Path(sys.argv[1])\n"
        "Path(sys.argv[2]).write_text('ready', encoding='utf-8')\n"
        "Database(Home(home)).migrate()\n"
    )

    with lock_path.open("a+", encoding="utf-8") as lock_file:
        db_module.fcntl.flock(lock_file.fileno(), db_module.fcntl.LOCK_EX)
        proc = subprocess.Popen(
            [sys.executable, "-c", script, str(home.path), str(ready_file)],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 5
            while not ready_file.exists() and time.monotonic() < deadline:
                if proc.poll() is not None:
                    stdout, stderr = proc.communicate()
                    pytest.fail(f"child migration exited before reaching migrate\nstdout={stdout}\nstderr={stderr}")
                time.sleep(0.01)
            assert ready_file.exists()

            time.sleep(0.2)
            assert proc.poll() is None
            assert not home.db_path.exists()
        finally:
            db_module.fcntl.flock(lock_file.fileno(), db_module.fcntl.LOCK_UN)

        stdout, stderr = proc.communicate(timeout=10)

    assert proc.returncode == 0, f"stdout={stdout}\nstderr={stderr}"
    with sqlite3.connect(home.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == db_module.SCHEMA_VERSION


def test_migration_lock_timeout_uses_global_config(tmp_path) -> None:
    home = Home(tmp_path / "home")
    home.path.mkdir(parents=True)
    home.config_path.write_text(
        "schema_version = 1\n\n[locks]\nacquire_timeout_ms = 50\n",
        encoding="utf-8",
    )
    lock_path = home.path / ".migration.lock"
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from alab.db import Database\n"
        "from alab.errors import AlabError\n"
        "from alab.home import Home\n"
        "home = Path(sys.argv[1])\n"
        "try:\n"
        "    Database(Home(home)).migrate()\n"
        "except AlabError as exc:\n"
        "    print(exc.code)\n"
        "    print(exc.reason)\n"
        "    print(exc.next_action)\n"
        "    raise SystemExit(exc.exit_code)\n"
        "raise SystemExit(0)\n"
    )

    with lock_path.open("a+", encoding="utf-8") as lock_file:
        db_module.fcntl.flock(lock_file.fileno(), db_module.fcntl.LOCK_EX)
        proc = subprocess.run(
            [sys.executable, "-c", script, str(home.path)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=5,
        )
        db_module.fcntl.flock(lock_file.fileno(), db_module.fcntl.LOCK_UN)

    assert proc.returncode == 4, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert proc.stdout.splitlines() == [
        "RESOURCE_BUSY",
        "migration lock is busy",
        "retry after the current migration completes",
    ]
    assert proc.stderr == ""
    assert not home.db_path.exists()


def test_migrate_backs_up_existing_database_before_new_version(tmp_path, monkeypatch) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "1_initial.sql").write_text(MINIMAL_INITIAL_SQL, encoding="utf-8")
    monkeypatch.setattr(db_module, "MIGRATIONS_DIR", migrations)
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", 1)
    home = Home(tmp_path / "home")
    db = Database(home)

    db.migrate()
    assert list(home.backups_path.glob("*.db")) == []

    (migrations / "2_add_extra.sql").write_text(
        "CREATE TABLE extra_data (value TEXT NOT NULL);\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", 2)

    db.migrate()

    backups = list(home.backups_path.glob("alab-1-to-2-*.db"))
    assert len(backups) == 1
    with sqlite3.connect(home.db_path) as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'extra_data'"
        ).fetchone()
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 2
    with sqlite3.connect(backups[0]) as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'extra_data'"
        ).fetchone() is None
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_migrate_rolls_back_failed_version(tmp_path, monkeypatch) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "1_initial.sql").write_text(MINIMAL_INITIAL_SQL, encoding="utf-8")
    monkeypatch.setattr(db_module, "MIGRATIONS_DIR", migrations)
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", 1)
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    (migrations / "2_bad.sql").write_text(
        "CREATE TABLE should_rollback (value TEXT NOT NULL);\nSELECT * FROM missing_table;\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", 2)
    with pytest.raises(AlabError) as excinfo:
        db.migrate()

    assert excinfo.value.code == "STORAGE_ERROR"
    with sqlite3.connect(home.db_path) as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'should_rollback'"
        ).fetchone() is None
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_migrate_rejects_downgrade(tmp_path, monkeypatch) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "1_initial.sql").write_text(MINIMAL_INITIAL_SQL, encoding="utf-8")
    (migrations / "2_add_extra.sql").write_text(
        "CREATE TABLE extra_data (value TEXT NOT NULL);\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(db_module, "MIGRATIONS_DIR", migrations)
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", 2)
    home = Home(tmp_path / "home")
    db = Database(home)
    db.migrate()

    (migrations / "2_add_extra.sql").unlink()
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", 1)
    with pytest.raises(AlabError) as excinfo:
        db.migrate()

    assert excinfo.value.code == "STORAGE_ERROR"
    assert "newer than this ALab version" in excinfo.value.reason


def test_path_hash_case_normalizes_on_case_insensitive_filesystems(monkeypatch) -> None:
    monkeypatch.setattr(context_module, "_is_case_insensitive_path", lambda path: True)

    assert path_hash(Path("/tmp/ALab/CasePath")) == path_hash(Path("/tmp/alab/casepath"))


def test_path_hash_detects_case_insensitive_parent_for_missing_child(tmp_path, monkeypatch) -> None:
    root = tmp_path / "Parent"
    root.mkdir()

    def fake_exists(path: Path) -> bool:
        return path.name == "pARENT"

    def fake_samefile(left: Path, right: Path) -> bool:
        return left.name == "Parent" and right.name == "pARENT"

    context_module._device_is_case_insensitive.cache_clear()
    monkeypatch.setattr(context_module.Path, "exists", fake_exists)
    monkeypatch.setattr(context_module.os.path, "samefile", fake_samefile)

    assert path_hash(root / "MissingChild") == path_hash(root / "missingchild")


def test_path_hash_preserves_case_on_case_sensitive_filesystems(monkeypatch) -> None:
    monkeypatch.setattr(context_module, "_is_case_insensitive_path", lambda path: False)

    assert path_hash(Path("/tmp/ALab/CasePath")) != path_hash(Path("/tmp/alab/casepath"))
